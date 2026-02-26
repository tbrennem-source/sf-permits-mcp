"""Generate a Pillow-based OG card PNG for social media sharing.

Generates web/static/og-card.png (1200x630) — the recommended Open Graph image size.
Uses only Pillow's built-in default font (no external font files required).

Usage:
    python -m scripts.generate_og_card
    # or
    python scripts/generate_og_card.py
"""

import os
from PIL import Image, ImageDraw, ImageFont


def generate_og_card(output_path: str = "web/static/og-card.png") -> None:
    """Generate the OG card PNG and save to output_path."""
    # Canvas: 1200x630 (Facebook/Twitter recommended OG size)
    width, height = 1200, 630
    bg_color = (26, 26, 46)      # Dark navy matching site theme
    accent_color = (74, 158, 255)  # Blue accent (#4a9eff)
    text_primary = (200, 200, 210)  # Near-white
    text_muted = (136, 136, 150)   # Muted grey

    img = Image.new("RGB", (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Decorative top accent bar
    draw.rectangle([(0, 0), (width, 6)], fill=accent_color)

    # Left accent stripe
    draw.rectangle([(80, 60), (86, 570)], fill=(74, 158, 255, 80))

    # Use default PIL fonts at different sizes
    # load_default(size=) requires Pillow 10+; fall back gracefully
    try:
        font_logo = ImageFont.load_default(size=64)
        font_tagline = ImageFont.load_default(size=32)
        font_sub = ImageFont.load_default(size=26)
        font_small = ImageFont.load_default(size=22)
    except TypeError:
        # Pillow < 10 — load_default doesn't accept size
        font_logo = ImageFont.load_default()
        font_tagline = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Logo / brand name
    draw.text((110, 140), "sfpermits.ai", fill=accent_color, font=font_logo)

    # Tagline
    draw.text(
        (110, 250),
        "San Francisco Building Permit Intelligence",
        fill=text_primary,
        font=font_tagline,
    )

    # Feature list
    draw.text(
        (110, 340),
        "Permits  \u00b7  Timeline  \u00b7  Fees  \u00b7  Documents  \u00b7  Risk",
        fill=text_muted,
        font=font_sub,
    )

    # Bottom badge
    draw.text(
        (110, 440),
        "Free instant analysis \u2014 no signup required",
        fill=text_muted,
        font=font_small,
    )

    # Bottom decorative bar
    draw.rectangle([(0, height - 6), (width, height)], fill=accent_color)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    img.save(output_path, "PNG", optimize=True)
    print(f"OG card saved to {output_path} ({width}x{height})")


if __name__ == "__main__":
    # Resolve relative to this script's repo root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.dirname(script_dir)
    output = os.path.join(repo_root, "web", "static", "og-card.png")
    generate_og_card(output)
