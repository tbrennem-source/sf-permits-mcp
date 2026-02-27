#!/usr/bin/env python3
"""Send dashboard screenshots to Claude Vision for scoring."""
import anthropic
import base64
import json
import sys
import os

VISION_PROMPT = """You are a strict web design reviewer. Score this page on an ABSOLUTE scale, not relative to anything else.

RUBRIC:
5/5 EXCELLENT: Content in centered max-width container (~1100px). Glass-morphism cards with rounded corners and subtle borders for each content section. Monospace display font for headings, clean sans-serif for body. Navigation is a clean horizontal bar with no wrapping. Adequate whitespace between sections (24px+). Dark theme with consistent color tokens. Professional, polished, ready for paying customers.

4/5 GOOD: Centered content, cards present, good spacing. Minor issues like slightly inconsistent fonts or one section without a card. Nav works but could be tighter.

3/5 MEDIOCRE: Some centering but inconsistent. Some sections have cards, others are raw. Font usage mixed. Nav functional but crowded. Spacing uneven. Looks like a dev tool, not a product.

2/5 POOR: Content mostly flush-left or full-width. Few or no cards. Nav overflows or wraps. Large unstyled sections. Poor spacing. Looks unfinished.

1/5 BROKEN: No centering, no cards, nav broken, raw HTML, light theme on a dark-theme site, fundamentally unstyled.

CHECK EACH:
1. CENTERING: Is main content in a centered max-width container? Or flush-left/full-width sprawl?
2. NAV: Does nav display on one line without wrapping? Are items reasonably sized?
3. CARDS: Are content sections wrapped in card containers (rounded borders, background, shadow)?
4. TYPOGRAPHY: Monospace headings? Sans-serif body? Consistent sizing hierarchy?
5. SPACING: Adequate gaps between sections? Not cramped?
6. SEARCH BAR: If present, is it styled as a prominent input with rounded corners?
7. RECENT ITEMS: If present, are they styled as cards/chips, not raw text links?
8. ACTION LINKS: If present, are they styled as buttons, not tiny text?

For EACH failing check, describe the SPECIFIC CSS fix needed (property: value).

Return ONLY this JSON:
{"score": N, "checks": {"centering": {"pass": bool, "fix": "css fix or null"}, "nav": {"pass": bool, "fix": "css fix or null"}, "cards": {"pass": bool, "fix": "css fix or null"}, "typography": {"pass": bool, "fix": "css fix or null"}, "spacing": {"pass": bool, "fix": "css fix or null"}, "search_bar": {"pass": bool, "fix": "css fix or null"}, "recent_items": {"pass": bool, "fix": "css fix or null"}, "action_links": {"pass": bool, "fix": "css fix or null"}}, "summary": "one line overall assessment"}"""


def score_screenshot(image_path: str, label: str = ""):
    """Send a screenshot to Claude Vision and return the score."""
    client = anthropic.Anthropic()

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    suffix = f" ({label})" if label else ""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": VISION_PROMPT + f"\n\nThis is a screenshot of the authenticated dashboard{suffix}.",
                    },
                ],
            }
        ],
    )

    text = response.content[0].text
    # Try to parse JSON from response
    try:
        # Find JSON in the response
        start = text.index("{")
        end = text.rindex("}") + 1
        result = json.loads(text[start:end])
        return result
    except (ValueError, json.JSONDecodeError):
        print(f"WARNING: Could not parse JSON from Vision response:\n{text}")
        return {"score": 0, "raw": text}


if __name__ == "__main__":
    screenshot_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "qa-results", "screenshots", "dashboard-loop"
    )

    round_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    results = {}
    for variant in ["desktop", "mobile"]:
        path = os.path.join(screenshot_dir, f"round-{round_num}-{variant}.png")
        if os.path.exists(path):
            print(f"\n--- Scoring round-{round_num}-{variant}.png ---")
            result = score_screenshot(path, label=f"round {round_num}, {variant}")
            results[variant] = result
            print(json.dumps(result, indent=2))
        else:
            print(f"SKIP: {path} not found")

    # Write results to file
    results_path = os.path.join(screenshot_dir, f"round-{round_num}-scores.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nScores saved to {results_path}")
