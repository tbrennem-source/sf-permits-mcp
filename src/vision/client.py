"""Claude Vision API client for architectural plan analysis.

Wraps the Anthropic SDK for vision calls. Isolated so the rest of the
codebase does not import ``anthropic`` directly.

Environment variables:
    ANTHROPIC_API_KEY: Required for vision calls.
    VISION_MODEL: Override model (default: claude-sonnet-4-20250514).
"""

import logging
import os
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 2048
VISION_TIMEOUT_SECS = 30.0

# Anthropic pricing per million tokens (claude-sonnet-4, as of 2025-05)
_INPUT_COST_PER_MTOK = 3.00
_OUTPUT_COST_PER_MTOK = 15.00


@dataclass
class VisionResult:
    """Result of a vision API call."""

    success: bool
    text: str  # Raw text response
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0


@dataclass
class VisionCallRecord:
    """Single API call record for audit and aggregation."""

    call_type: str  # e.g. "cover_page_count", "title_block", "annotation", "hatching"
    page_number: int | None
    duration_ms: int
    input_tokens: int
    output_tokens: int
    success: bool


@dataclass
class VisionUsageSummary:
    """Aggregated token and timing stats for a full analysis job."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_duration_ms: int = 0
    model: str = ""
    calls: list[VisionCallRecord] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def estimated_cost_usd(self) -> float:
        """Estimate cost based on Anthropic pricing."""
        input_cost = (self.total_input_tokens / 1_000_000) * _INPUT_COST_PER_MTOK
        output_cost = (self.total_output_tokens / 1_000_000) * _OUTPUT_COST_PER_MTOK
        return round(input_cost + output_cost, 6)

    def add_call(self, record: VisionCallRecord) -> None:
        """Add a call record and update aggregates."""
        self.calls.append(record)
        self.total_calls += 1
        self.total_duration_ms += record.duration_ms
        self.total_input_tokens += record.input_tokens
        self.total_output_tokens += record.output_tokens
        if record.success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1

    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict for DB storage."""
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_duration_ms": self.total_duration_ms,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "model": self.model,
            "calls": [
                {
                    "call_type": c.call_type,
                    "page_number": c.page_number,
                    "duration_ms": c.duration_ms,
                    "input_tokens": c.input_tokens,
                    "output_tokens": c.output_tokens,
                    "success": c.success,
                }
                for c in self.calls
            ],
        }


def is_vision_available() -> bool:
    """Check if ANTHROPIC_API_KEY is configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def analyze_image(
    image_base64: str,
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: float | None = None,
) -> VisionResult:
    """Send a single image to Claude Vision for analysis.

    Args:
        image_base64: Base64-encoded PNG (no ``data:`` prefix).
        prompt: User prompt describing what to extract.
        system_prompt: Optional system prompt for context.
        model: Model name override.
        max_tokens: Max response tokens.
        timeout: API call timeout in seconds. Defaults to VISION_TIMEOUT_SECS.

    Returns:
        VisionResult with success status and text response.
        On timeout, returns VisionResult with success=False and
        error="Vision API timeout" for graceful degradation.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return VisionResult(
            success=False,
            text="",
            error="ANTHROPIC_API_KEY not configured",
        )

    effective_timeout = timeout if timeout is not None else VISION_TIMEOUT_SECS

    try:
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=api_key)

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt,
                    },
                ],
            }
        ]

        kwargs: dict = {
            "model": model or os.environ.get("VISION_MODEL", DEFAULT_MODEL),
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        t0 = time.perf_counter()
        response = await client.messages.create(timeout=effective_timeout, **kwargs)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(
            "[vision] call=%s model=%s duration_ms=%d in_tok=%d out_tok=%d",
            prompt[:40].replace("\n", " "),
            kwargs.get("model", DEFAULT_MODEL),
            duration_ms,
            response.usage.input_tokens,
            response.usage.output_tokens,
        )

        text = response.content[0].text if response.content else ""
        return VisionResult(
            success=True,
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            duration_ms=duration_ms,
        )
    except Exception as e:
        error_str = str(e)
        # Detect timeout errors from httpx/anthropic
        is_timeout = any(kw in error_str.lower() for kw in ("timeout", "timed out", "deadline"))
        if is_timeout:
            logger.warning(
                "Vision API timeout after %.0fs: %s",
                effective_timeout,
                prompt[:40].replace("\n", " "),
            )
            return VisionResult(
                success=False,
                text="",
                error="Vision API timeout",
            )
        logger.error("Vision API call failed: %s", e)
        return VisionResult(
            success=False,
            text="",
            error=error_str,
        )


async def analyze_images_batch(
    images: list[tuple[int, str]],
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    parallel: bool = False,
) -> list[tuple[int, VisionResult]]:
    """Analyze multiple images with the same prompt.

    Args:
        images: List of ``(page_number, base64_png)`` tuples.
        prompt: Prompt to apply to each image.
        system_prompt: Optional system context.
        model: Model override.
        parallel: If True, run all calls concurrently via asyncio.gather.

    Returns:
        List of ``(page_number, VisionResult)`` tuples.
    """
    if parallel and len(images) > 1:
        import asyncio

        async def _call(page_num: int, b64: str) -> tuple[int, VisionResult]:
            result = await analyze_image(b64, prompt, system_prompt, model)
            return (page_num, result)

        tasks = [_call(pn, b64) for pn, b64 in images]
        return list(await asyncio.gather(*tasks))

    # Sequential fallback
    results = []
    for page_num, b64 in images:
        result = await analyze_image(b64, prompt, system_prompt, model)
        results.append((page_num, result))
    return results
