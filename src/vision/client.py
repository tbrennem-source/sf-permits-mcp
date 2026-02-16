"""Claude Vision API client for architectural plan analysis.

Wraps the Anthropic SDK for vision calls. Isolated so the rest of the
codebase does not import ``anthropic`` directly.

Environment variables:
    ANTHROPIC_API_KEY: Required for vision calls.
    VISION_MODEL: Override model (default: claude-sonnet-4-20250514).
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 2048


@dataclass
class VisionResult:
    """Result of a vision API call."""

    success: bool
    text: str  # Raw text response
    error: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0


def is_vision_available() -> bool:
    """Check if ANTHROPIC_API_KEY is configured."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


async def analyze_image(
    image_base64: str,
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> VisionResult:
    """Send a single image to Claude Vision for analysis.

    Args:
        image_base64: Base64-encoded PNG (no ``data:`` prefix).
        prompt: User prompt describing what to extract.
        system_prompt: Optional system prompt for context.
        model: Model name override.
        max_tokens: Max response tokens.

    Returns:
        VisionResult with success status and text response.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return VisionResult(
            success=False,
            text="",
            error="ANTHROPIC_API_KEY not configured",
        )

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

        response = await client.messages.create(**kwargs)

        text = response.content[0].text if response.content else ""
        return VisionResult(
            success=True,
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
    except Exception as e:
        logger.error("Vision API call failed: %s", e)
        return VisionResult(
            success=False,
            text="",
            error=str(e),
        )


async def analyze_images_batch(
    images: list[tuple[int, str]],
    prompt: str,
    system_prompt: str | None = None,
    model: str | None = None,
) -> list[tuple[int, VisionResult]]:
    """Analyze multiple images with the same prompt.

    Processes sequentially to avoid rate limits.

    Args:
        images: List of ``(page_number, base64_png)`` tuples.
        prompt: Prompt to apply to each image.
        system_prompt: Optional system context.
        model: Model override.

    Returns:
        List of ``(page_number, VisionResult)`` tuples.
    """
    results = []
    for page_num, b64 in images:
        result = await analyze_image(b64, prompt, system_prompt, model)
        results.append((page_num, result))
    return results
