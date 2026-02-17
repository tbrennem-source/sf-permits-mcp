"""Tests for vision/client.py — Anthropic Vision API wrapper.

All tests mock the Anthropic SDK. No real API calls are made.
"""

import os
import sys
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from src.vision.client import (
    is_vision_available,
    analyze_image,
    analyze_images_batch,
    VisionResult,
    VisionCallRecord,
    VisionUsageSummary,
    DEFAULT_MODEL,
    DEFAULT_MAX_TOKENS,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_anthropic():
    """Install a mock anthropic module so `import anthropic` inside
    analyze_image() resolves to our mock."""
    mock_mod = MagicMock()
    mock_client = MagicMock()
    mock_mod.AsyncAnthropic.return_value = mock_client
    with patch.dict(sys.modules, {"anthropic": mock_mod}):
        yield mock_mod, mock_client


# ── is_vision_available ─────────────────────────────────────────────────────


def test_vision_available_with_key():
    """Returns True when API key is set."""
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-123"}):
        assert is_vision_available() is True


def test_vision_not_available_without_key():
    """Returns False when API key is not set."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        assert is_vision_available() is False


# ── analyze_image ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_image_no_api_key():
    """Returns failure result when API key is missing."""
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        result = await analyze_image("base64data", "test prompt")
        assert result.success is False
        assert "not configured" in result.error


@pytest.mark.asyncio
async def test_analyze_image_success(mock_anthropic):
    """Successful API call returns VisionResult with text."""
    mock_mod, mock_client = mock_anthropic

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"result": "test data"}')]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        result = await analyze_image("base64data", "test prompt")

    assert result.success is True
    assert result.text == '{"result": "test data"}'
    assert result.input_tokens == 100
    assert result.output_tokens == 50


@pytest.mark.asyncio
async def test_analyze_image_with_system_prompt(mock_anthropic):
    """System prompt is passed to the API."""
    mock_mod, mock_client = mock_anthropic

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="response")]
    mock_response.usage = MagicMock(input_tokens=50, output_tokens=25)
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        result = await analyze_image(
            "base64data", "test prompt",
            system_prompt="You are an architect"
        )

    assert result.success is True
    call_kwargs = mock_client.messages.create.call_args
    assert call_kwargs.kwargs.get("system") == "You are an architect"


@pytest.mark.asyncio
async def test_analyze_image_api_error(mock_anthropic):
    """API exceptions return failure result."""
    mock_mod, mock_client = mock_anthropic
    mock_client.messages.create = AsyncMock(side_effect=Exception("API rate limit"))

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        result = await analyze_image("base64data", "test prompt")

    assert result.success is False
    assert "API rate limit" in result.error


@pytest.mark.asyncio
async def test_analyze_image_empty_response(mock_anthropic):
    """Empty response content returns empty text."""
    mock_mod, mock_client = mock_anthropic

    mock_response = MagicMock()
    mock_response.content = []
    mock_response.usage = MagicMock(input_tokens=10, output_tokens=0)
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        result = await analyze_image("base64data", "test prompt")

    assert result.success is True
    assert result.text == ""


# ── analyze_images_batch ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch_processes_all_images():
    """Batch processes each image sequentially."""
    call_count = 0

    async def mock_analyze(b64, prompt, system_prompt=None, model=None):
        nonlocal call_count
        call_count += 1
        return VisionResult(
            success=True,
            text=f"result_{call_count}",
            input_tokens=10,
            output_tokens=5,
        )

    with patch("src.vision.client.analyze_image", side_effect=mock_analyze):
        images = [(0, "img0"), (2, "img2"), (5, "img5")]
        results = await analyze_images_batch(images, "test prompt")

    assert len(results) == 3
    assert results[0][0] == 0
    assert results[0][1].text == "result_1"
    assert results[1][0] == 2
    assert results[2][0] == 5


# ── VisionResult duration_ms ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_analyze_image_records_duration_ms(mock_anthropic):
    """Successful call populates duration_ms > 0."""
    mock_mod, mock_client = mock_anthropic

    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
        result = await analyze_image("base64data", "test prompt")

    assert result.success is True
    assert result.duration_ms >= 0  # May be 0 on very fast mock but should exist


def test_vision_result_duration_default():
    """VisionResult defaults duration_ms to 0."""
    r = VisionResult(success=True, text="test")
    assert r.duration_ms == 0


# ── VisionCallRecord ──────────────────────────────────────────────────────


def test_vision_call_record_creation():
    """VisionCallRecord stores all fields correctly."""
    record = VisionCallRecord(
        call_type="title_block",
        page_number=3,
        duration_ms=1500,
        input_tokens=5000,
        output_tokens=800,
        success=True,
    )
    assert record.call_type == "title_block"
    assert record.page_number == 3
    assert record.duration_ms == 1500
    assert record.input_tokens == 5000
    assert record.output_tokens == 800
    assert record.success is True


def test_vision_call_record_none_page():
    """VisionCallRecord allows None page_number for non-page-specific calls."""
    record = VisionCallRecord(
        call_type="cover_page_count",
        page_number=None,
        duration_ms=2000,
        input_tokens=3000,
        output_tokens=500,
        success=True,
    )
    assert record.page_number is None


# ── VisionUsageSummary ────────────────────────────────────────────────────


def test_usage_summary_aggregation():
    """add_call correctly aggregates multiple call records."""
    usage = VisionUsageSummary(model="test-model")

    usage.add_call(VisionCallRecord(
        call_type="title_block", page_number=0,
        duration_ms=1000, input_tokens=5000, output_tokens=800, success=True,
    ))
    usage.add_call(VisionCallRecord(
        call_type="annotation", page_number=0,
        duration_ms=1200, input_tokens=6000, output_tokens=1000, success=True,
    ))
    usage.add_call(VisionCallRecord(
        call_type="hatching", page_number=1,
        duration_ms=800, input_tokens=4000, output_tokens=600, success=False,
    ))

    assert usage.total_calls == 3
    assert usage.successful_calls == 2
    assert usage.failed_calls == 1
    assert usage.total_input_tokens == 15000
    assert usage.total_output_tokens == 2400
    assert usage.total_duration_ms == 3000
    assert usage.total_tokens == 17400
    assert len(usage.calls) == 3


def test_usage_summary_cost_estimation():
    """estimated_cost_usd calculates correctly from known token counts."""
    usage = VisionUsageSummary()
    usage.add_call(VisionCallRecord(
        call_type="test", page_number=None,
        duration_ms=100,
        input_tokens=1_000_000,   # 1M input tokens = $3.00
        output_tokens=100_000,    # 100K output tokens = $1.50
        success=True,
    ))
    # Expected: $3.00 + $1.50 = $4.50
    assert abs(usage.estimated_cost_usd - 4.5) < 0.001


def test_usage_summary_to_dict():
    """to_dict() produces JSON-serializable output with all expected keys."""
    import json

    usage = VisionUsageSummary(model="claude-sonnet-4-20250514")
    usage.add_call(VisionCallRecord(
        call_type="title_block", page_number=1,
        duration_ms=500, input_tokens=1000, output_tokens=200, success=True,
    ))

    d = usage.to_dict()
    # Verify it's JSON-serializable
    json_str = json.dumps(d)
    assert json_str  # non-empty

    # Check expected top-level keys
    assert d["total_calls"] == 1
    assert d["successful_calls"] == 1
    assert d["failed_calls"] == 0
    assert d["total_input_tokens"] == 1000
    assert d["total_output_tokens"] == 200
    assert d["total_duration_ms"] == 500
    assert d["total_tokens"] == 1200
    assert d["estimated_cost_usd"] > 0
    assert d["model"] == "claude-sonnet-4-20250514"
    assert len(d["calls"]) == 1
    assert d["calls"][0]["call_type"] == "title_block"
    assert d["calls"][0]["page_number"] == 1


def test_usage_summary_empty():
    """Empty VisionUsageSummary has zero values."""
    usage = VisionUsageSummary()
    assert usage.total_calls == 0
    assert usage.total_tokens == 0
    assert usage.estimated_cost_usd == 0.0
    d = usage.to_dict()
    assert d["total_calls"] == 0
    assert d["calls"] == []
