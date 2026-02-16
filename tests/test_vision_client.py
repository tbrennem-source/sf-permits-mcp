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
