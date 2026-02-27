#!/usr/bin/env python3
"""Video QA Review Pipeline v2 — dual-viewport + parallel reference-based Vision scoring.

Launches Playwright Chromium with video recording at desktop (1280x720) and mobile (375x812)
viewports, navigates key pages, takes full-page screenshots, then sends ALL screenshots to
Claude Vision in parallel for strict reference-based quality scoring.

The landing page screenshot serves as the "reference" (score 5/5). Every other page is
scored relative to that reference using a detailed checklist prompt.

Usage:
    python scripts/video_qa_review.py --url https://sfpermits-ai-staging-production.up.railway.app
    python scripts/video_qa_review.py --url https://... --test-login-secret SECRET

Environment:
    TEST_LOGIN_SECRET — enables authenticated page checks (or use --test-login-secret)
    ANTHROPIC_API_KEY — required for Vision scoring
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VIEWPORTS = {
    "desktop": {"width": 1280, "height": 720},
    "mobile": {"width": 375, "height": 812},
}

PAGES: list[dict] = [
    # --- Public (no auth) ---
    {"slug": "landing", "path": "/", "auth": "public", "label": "Landing (ref)", "is_reference": True},
    {"slug": "demo", "path": "/demo", "auth": "public", "label": "Demo Page"},
    {"slug": "methodology", "path": "/methodology", "auth": "public", "label": "Methodology"},
    {"slug": "about-data", "path": "/about-data", "auth": "public", "label": "About Data"},
    # --- Auth (logged-in user) ---
    {"slug": "dashboard", "path": "/", "auth": "auth", "label": "Dashboard (auth)"},
    {"slug": "search", "path": "/search", "auth": "auth", "label": "Search Page"},
    {"slug": "brief", "path": "/brief", "auth": "auth", "label": "Morning Brief"},
    {"slug": "account", "path": "/account", "auth": "auth", "label": "Account Settings"},
    # --- Admin ---
    {"slug": "admin-ops", "path": "/admin/ops", "auth": "admin", "label": "Admin Ops"},
]

VISION_PROMPT = """You are a strict visual QA reviewer for a web application.

REFERENCE IMAGE: The first image is the landing page — this represents the target design quality (score 5/5). It uses the Obsidian design system: dark theme, JetBrains Mono headings, IBM Plex Sans body, glass-card containers, centered content with max-width, proper spacing.

TEST IMAGE: The second image is the page being scored. Score it 1-5 relative to the reference.

CHECK EACH ITEM (each "no" = -1 point from 5):
1. CENTERING: Is the main content centered with a max-width container? Or is it flush-left/full-width?
2. NAV: Does the navigation bar display cleanly without wrapping to a second line or overflowing?
3. CARDS: Are content sections wrapped in card containers (rounded borders, subtle background)?
4. TYPOGRAPHY: Are headings in a monospace/display font? Is body text in a sans-serif?
5. SPACING: Is there adequate spacing between sections (not cramped)?

HARD FAIL (automatic score 1):
- Content flush left with no centering container
- Nav items wrapping to multiple lines
- No dark theme (light/white background)
- Raw unstyled HTML elements (default browser styling)

Return ONLY this JSON (no markdown, no explanation):
{"score": N, "centering": true/false, "nav_clean": true/false, "has_cards": true/false, "good_typography": true/false, "good_spacing": true/false, "hard_fail": true/false, "hard_fail_reason": "reason or null", "issues": ["issue1", ...], "summary": "one line"}"""

VISION_PROMPT_REFERENCE = """You are a strict visual QA reviewer. This is the REFERENCE landing page for a web application using the Obsidian design system: dark theme, JetBrains Mono headings, IBM Plex Sans body, glass-card containers, centered content with max-width, proper spacing.

Score this page itself 1-5 on those criteria. Be honest — this is the baseline.

CHECK EACH ITEM (each "no" = -1 point from 5):
1. CENTERING: Is the main content centered with a max-width container?
2. NAV: Does the navigation bar display cleanly?
3. CARDS: Are content sections in card containers?
4. TYPOGRAPHY: Monospace headings, sans-serif body?
5. SPACING: Adequate spacing between sections?

Return ONLY this JSON (no markdown, no explanation):
{"score": N, "centering": true/false, "nav_clean": true/false, "has_cards": true/false, "good_typography": true/false, "good_spacing": true/false, "hard_fail": false, "hard_fail_reason": null, "issues": [], "summary": "one line"}"""

MAX_VISION_HEIGHT = 4000  # Resize screenshots taller than this before sending to Vision


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PageResult:
    slug: str
    label: str
    url: str
    viewport: str = ""
    screenshot_path: str = ""
    status_code: int = 0
    load_error: Optional[str] = None
    vision_score: float = 0.0
    vision_data: dict = field(default_factory=dict)
    vision_issues: list[str] = field(default_factory=list)
    vision_summary: str = ""
    vision_error: Optional[str] = None
    passed: bool = True
    is_reference: bool = False


# ---------------------------------------------------------------------------
# Browser navigation — one viewport at a time
# ---------------------------------------------------------------------------

def navigate_viewport(
    base_url: str,
    viewport_name: str,
    viewport_size: dict,
    screenshot_dir: Path,
    video_dir: Path,
    test_login_secret: Optional[str] = None,
) -> tuple[list[PageResult], str]:
    """Navigate all pages in one viewport, capture screenshots, return results + video path."""
    from playwright.sync_api import sync_playwright

    results: list[PageResult] = []
    video_path = ""

    print(f"\n{'='*60}")
    print(f"  VIEWPORT: {viewport_name} ({viewport_size['width']}x{viewport_size['height']})")
    print(f"{'='*60}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        context = browser.new_context(
            viewport=viewport_size,
            record_video_dir=str(video_dir),
            record_video_size=viewport_size,
        )

        page = context.new_page()
        authenticated = False
        is_admin = False

        # --- Public pages ---
        print(f"\n  --- Public Pages ---")
        for pg in PAGES:
            if pg["auth"] != "public":
                continue
            result = _visit_page(page, base_url, pg, screenshot_dir, viewport_name)
            results.append(result)

        # --- Login ---
        if test_login_secret:
            print(f"\n  --- Authenticating via test-login ---")
            try:
                login_url = f"{base_url}/auth/test-login"
                login_result = page.evaluate(
                    """async ([url, secret]) => {
                        const resp = await fetch(url, {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({secret: secret, email: 'test-admin@sfpermits.ai'}),
                            credentials: 'same-origin'
                        });
                        return {status: resp.status, body: await resp.text()};
                    }""",
                    [login_url, test_login_secret],
                )
                login_status = login_result.get("status", 0)
                if login_status == 200:
                    authenticated = True
                    is_admin = True
                    print(f"    Logged in (status {login_status})")
                    time.sleep(1)
                else:
                    print(f"    Login failed (status {login_status}) — skipping auth pages")
            except Exception as e:
                print(f"    Login error: {e} — skipping auth pages")
        else:
            print(f"\n  --- No TEST_LOGIN_SECRET — skipping auth pages ---")

        # --- Authenticated pages ---
        if authenticated:
            print(f"\n  --- Authenticated Pages ---")
            for pg in PAGES:
                if pg["auth"] == "public":
                    continue
                if pg["auth"] == "admin" and not is_admin:
                    continue
                result = _visit_page(page, base_url, pg, screenshot_dir, viewport_name)
                results.append(result)
        else:
            for pg in PAGES:
                if pg["auth"] != "public":
                    results.append(PageResult(
                        slug=pg["slug"],
                        label=pg["label"],
                        url=f"{base_url}{pg['path']}",
                        viewport=viewport_name,
                        load_error="SKIPPED — not authenticated",
                        passed=True,
                    ))

        # Close context to finalize video
        context.close()
        browser.close()

    # Find the video file
    video_files = sorted(video_dir.glob("*.webm"), key=lambda f: f.stat().st_mtime)
    if video_files:
        video_path = str(video_files[-1])
        print(f"\n  Video saved: {video_path}")
    else:
        print(f"\n  WARNING: No video file found")

    return results, video_path


def _visit_page(page, base_url: str, pg: dict, screenshot_dir: Path, viewport_name: str) -> PageResult:
    """Visit a single page, take screenshot, return result."""
    url = f"{base_url}{pg['path']}"
    slug = pg["slug"]
    label = pg["label"]
    screenshot_path = str(screenshot_dir / f"{slug}.png")

    print(f"    {label} ({pg['path']})", end=" ", flush=True)

    result = PageResult(
        slug=slug,
        label=label,
        url=url,
        viewport=viewport_name,
        is_reference=pg.get("is_reference", False),
    )

    try:
        try:
            resp = page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception:
            print("(retry) ", end="", flush=True)
            resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)

        result.status_code = resp.status if resp else 0

        if resp and resp.status >= 400:
            result.load_error = f"HTTP {resp.status}"
            print(f"-> {resp.status}")
        else:
            time.sleep(1.0)
            page.screenshot(path=screenshot_path, full_page=True)
            result.screenshot_path = screenshot_path
            print(f"-> {resp.status if resp else '?'} OK")

    except Exception as e:
        result.load_error = str(e)
        print(f"-> ERROR: {e}")

    return result


# ---------------------------------------------------------------------------
# Image processing for Vision API
# ---------------------------------------------------------------------------

def _prepare_image_for_vision(screenshot_path: str) -> tuple[str, bool]:
    """Read screenshot, resize if taller than MAX_VISION_HEIGHT, return (base64 str, was_resized)."""
    from PIL import Image
    import io

    img = Image.open(screenshot_path)
    w, h = img.size
    was_resized = False

    if h > MAX_VISION_HEIGHT:
        scale = MAX_VISION_HEIGHT / h
        new_w = int(w * scale)
        new_h = MAX_VISION_HEIGHT
        img = img.resize((new_w, new_h), Image.LANCZOS)
        was_resized = True

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8"), was_resized


def _parse_vision_json(raw_text: str) -> dict:
    """Parse JSON from Vision response, handling markdown code fences."""
    text = raw_text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.startswith("```")]
        text = "\n".join(lines).strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find a JSON object in the text
        match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


# ---------------------------------------------------------------------------
# Claude Vision scoring — parallel, reference-based
# ---------------------------------------------------------------------------

def _score_single_page(
    client,
    result: PageResult,
    reference_b64: Optional[str],
    reference_resized: bool,
) -> PageResult:
    """Score a single page with Vision API. Called from ThreadPoolExecutor."""
    if not result.screenshot_path or not Path(result.screenshot_path).exists():
        result.vision_error = "No screenshot available"
        return result

    try:
        test_b64, test_resized = _prepare_image_for_vision(result.screenshot_path)

        if result.is_reference:
            # Reference page — score standalone
            prompt = VISION_PROMPT_REFERENCE
            if test_resized:
                prompt = (
                    "NOTE: Image resized from tall screenshot. "
                    "Small text is a resize artifact — ignore text size.\n\n"
                    + prompt
                )
            content = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": test_b64},
                },
                {"type": "text", "text": prompt},
            ]
        else:
            # Non-reference — send reference + test image pair
            prompt = VISION_PROMPT
            resize_note = ""
            if test_resized or reference_resized:
                resize_note = (
                    "NOTE: One or both images were resized from tall screenshots. "
                    "Small text is a resize artifact — ignore text size.\n\n"
                )
            content = [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": reference_b64},
                },
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": test_b64},
                },
                {"type": "text", "text": resize_note + prompt},
            ]

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=512,
            messages=[{"role": "user", "content": content}],
        )

        raw_text = response.content[0].text.strip()
        parsed = _parse_vision_json(raw_text)

        result.vision_score = float(parsed.get("score", 0))
        result.vision_data = parsed
        result.vision_issues = parsed.get("issues", [])
        result.vision_summary = parsed.get("summary", "")
        result.passed = result.vision_score > 2.0

    except json.JSONDecodeError as e:
        result.vision_error = f"JSON parse error: {e}"
    except Exception as e:
        result.vision_error = str(e)

    return result


def score_all_with_vision(
    desktop_results: list[PageResult],
    mobile_results: list[PageResult],
) -> None:
    """Send ALL screenshots to Vision in parallel using ThreadPoolExecutor."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\nWARNING: ANTHROPIC_API_KEY not set — skipping Vision scoring")
        for r in desktop_results + mobile_results:
            r.vision_error = "No API key"
        return

    import anthropic
    client = anthropic.Anthropic(api_key=api_key)

    print(f"\n{'='*60}")
    print(f"  VISION SCORING — parallel, reference-based")
    print(f"{'='*60}")

    # Prepare reference images for each viewport
    desktop_ref = next((r for r in desktop_results if r.is_reference and r.screenshot_path), None)
    mobile_ref = next((r for r in mobile_results if r.is_reference and r.screenshot_path), None)

    desktop_ref_b64, desktop_ref_resized = None, False
    mobile_ref_b64, mobile_ref_resized = None, False

    if desktop_ref and Path(desktop_ref.screenshot_path).exists():
        desktop_ref_b64, desktop_ref_resized = _prepare_image_for_vision(desktop_ref.screenshot_path)
        print(f"  Desktop reference prepared: {desktop_ref.screenshot_path}")
    else:
        print("  WARNING: No desktop reference screenshot")

    if mobile_ref and Path(mobile_ref.screenshot_path).exists():
        mobile_ref_b64, mobile_ref_resized = _prepare_image_for_vision(mobile_ref.screenshot_path)
        print(f"  Mobile reference prepared: {mobile_ref.screenshot_path}")
    else:
        print("  WARNING: No mobile reference screenshot")

    # Build task list: (result, reference_b64, reference_resized)
    tasks = []
    for r in desktop_results:
        if r.screenshot_path and Path(r.screenshot_path).exists():
            tasks.append((r, desktop_ref_b64, desktop_ref_resized))
    for r in mobile_results:
        if r.screenshot_path and Path(r.screenshot_path).exists():
            tasks.append((r, mobile_ref_b64, mobile_ref_resized))

    # Mark results with no screenshot
    for r in desktop_results + mobile_results:
        if not r.screenshot_path or not Path(r.screenshot_path).exists():
            if not r.load_error:
                r.vision_error = "No screenshot available"

    total = len(tasks)
    print(f"\n  Scoring {total} screenshots in parallel...\n")
    start_time = time.time()

    # Fire all Vision API calls in parallel
    with ThreadPoolExecutor(max_workers=min(total, 10)) as executor:
        futures = {
            executor.submit(_score_single_page, client, r, ref_b64, ref_resized): r
            for r, ref_b64, ref_resized in tasks
        }

        completed = 0
        for future in as_completed(futures):
            completed += 1
            result = futures[future]
            try:
                future.result()  # Re-raise any exception from the thread
                if result.vision_error:
                    print(f"    [{completed:2d}/{total}] {result.viewport:>7} | {result.label:<25} | ERR: {result.vision_error}")
                else:
                    status = "PASS" if result.passed else "FAIL"
                    print(f"    [{completed:2d}/{total}] {result.viewport:>7} | {result.label:<25} | {result.vision_score}/5 [{status}]")
            except Exception as e:
                result.vision_error = str(e)
                print(f"    [{completed:2d}/{total}] {result.viewport:>7} | {result.label:<25} | ERR: {e}")

    elapsed = time.time() - start_time
    print(f"\n  Vision scoring complete in {elapsed:.1f}s")


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def _bool_display(val) -> str:
    """Convert bool to YES/NO for report tables."""
    if val is True:
        return "YES"
    elif val is False:
        return "NO"
    return "-"


def _add_results_rows(lines: list[str], results: list[PageResult]) -> None:
    """Add table rows for a viewport's results."""
    for r in results:
        if r.load_error and "SKIPPED" in str(r.load_error):
            lines.append(f"| {r.label} | SKIP | - | - | - | - | - | {r.load_error} |")
            continue
        if r.load_error:
            lines.append(f"| {r.label} | ERR | - | - | - | - | - | {r.load_error} |")
            continue
        if r.vision_error:
            lines.append(f"| {r.label} | ERR | - | - | - | - | - | Vision: {r.vision_error} |")
            continue

        d = r.vision_data
        centering = _bool_display(d.get("centering"))
        nav = _bool_display(d.get("nav_clean"))
        cards = _bool_display(d.get("has_cards"))
        typo = _bool_display(d.get("good_typography"))
        spacing = _bool_display(d.get("good_spacing"))
        issues_str = ", ".join(r.vision_issues[:3]) if r.vision_issues else "-"

        lines.append(
            f"| {r.label} | {r.vision_score}/5 | {centering} | {nav} | {cards} | {typo} | {spacing} | {issues_str} |"
        )


def generate_report(
    desktop_results: list[PageResult],
    mobile_results: list[PageResult],
    desktop_video: str,
    mobile_video: str,
    report_path: Path,
    base_url: str,
) -> str:
    """Generate the dual-viewport markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"# Video QA Review — {now}",
        "",
        f"**Target:** {base_url}",
        "",
    ]

    # Desktop table
    lines.extend([
        "## Desktop (1280x720)",
        "",
        "| Page | Score | Centering | Nav | Cards | Type | Spacing | Issues |",
        "|------|-------|-----------|-----|-------|------|---------|--------|",
    ])
    _add_results_rows(lines, desktop_results)

    # Mobile table
    lines.extend([
        "",
        "## Mobile (375x812)",
        "",
        "| Page | Score | Centering | Nav | Cards | Type | Spacing | Issues |",
        "|------|-------|-----------|-----|-------|------|---------|--------|",
    ])
    _add_results_rows(lines, mobile_results)

    # Videos section
    lines.extend([
        "",
        "## Videos",
        "",
        f"- Desktop: `{desktop_video or 'Not recorded'}`",
        f"- Mobile: `{mobile_video or 'Not recorded'}`",
        "",
    ])

    # Failures section
    all_results = desktop_results + mobile_results
    fails = [r for r in all_results if r.vision_score > 0 and r.vision_score <= 2.0]

    lines.append("## FAILURES (score <= 2)")
    lines.append("")
    if fails:
        for r in fails:
            issues_str = ", ".join(r.vision_issues) if r.vision_issues else r.vision_summary
            lines.append(f"- **[{r.viewport}] {r.label}** ({r.vision_score}/5): {issues_str}")
    else:
        lines.append("None.")
    lines.append("")

    # Summary stats
    scored = [r for r in all_results if r.vision_score > 0]
    skipped = [r for r in all_results if r.load_error and "SKIPPED" in str(r.load_error)]
    avg = sum(r.vision_score for r in scored) / len(scored) if scored else 0

    lines.extend([
        "## Summary",
        "",
        f"- Pages per viewport: {len(PAGES)}",
        f"- Total screenshots scored: {len(scored)}",
        f"- Skipped (no auth): {len(skipped)}",
        f"- Average score: {avg:.1f}/5",
        f"- Failures: {len(fails)}",
        "",
    ])

    report_text = "\n".join(lines)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text)
    print(f"\nReport saved: {report_path}")

    return report_text


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Video QA Review v2 — dual viewport + parallel reference-based Vision scoring"
    )
    parser.add_argument("--url", required=True, help="Base URL of staging site")
    parser.add_argument("--test-login-secret", help="TEST_LOGIN_SECRET (falls back to env var)")
    parser.add_argument("--output-dir", default="qa-results", help="Output directory")
    parser.add_argument("--skip-vision", action="store_true", help="Skip Vision scoring")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")
    output_base = Path(args.output_dir)
    report_path = output_base / "video-qa-test-results.md"

    test_login_secret = args.test_login_secret or os.environ.get("TEST_LOGIN_SECRET")

    print("Video QA Review Pipeline (v2)")
    print("=" * 60)
    print(f"Target:      {base_url}")
    print(f"Viewports:   desktop (1280x720), mobile (375x812)")
    print(f"Auth:        {'enabled' if test_login_secret else 'disabled (no TEST_LOGIN_SECRET)'}")
    print(f"Vision:      {'disabled' if args.skip_vision else 'parallel, reference-based'}")
    print(f"Output:      {output_base}")

    all_desktop_results: list[PageResult] = []
    all_mobile_results: list[PageResult] = []
    desktop_video = ""
    mobile_video = ""

    # Navigate both viewports sequentially (each gets its own browser context)
    for vp_name, vp_size in VIEWPORTS.items():
        ss_dir = output_base / "screenshots" / "video-qa-test" / vp_name
        vid_dir = output_base / "videos" / "video-qa-test" / vp_name
        ss_dir.mkdir(parents=True, exist_ok=True)
        vid_dir.mkdir(parents=True, exist_ok=True)

        results, video_path = navigate_viewport(
            base_url=base_url,
            viewport_name=vp_name,
            viewport_size=vp_size,
            screenshot_dir=ss_dir,
            video_dir=vid_dir,
            test_login_secret=test_login_secret,
        )

        if vp_name == "desktop":
            all_desktop_results = results
            desktop_video = video_path
        else:
            all_mobile_results = results
            mobile_video = video_path

    # Vision scoring — all screenshots from both viewports in parallel
    if not args.skip_vision:
        score_all_with_vision(all_desktop_results, all_mobile_results)

    # Generate report
    report = generate_report(
        desktop_results=all_desktop_results,
        mobile_results=all_mobile_results,
        desktop_video=desktop_video,
        mobile_video=mobile_video,
        report_path=report_path,
        base_url=base_url,
    )

    print(f"\n{'='*60}")
    print(report)
    print("=" * 60)

    # Exit code based on failures
    all_results = all_desktop_results + all_mobile_results
    fails = [r for r in all_results if r.vision_score > 0 and r.vision_score <= 2.0]
    if fails:
        print(f"\n{len(fails)} page(s) FAILED visual QA (score <= 2).")
        sys.exit(1)
    else:
        print("\nAll scored pages PASSED visual QA.")
        sys.exit(0)


if __name__ == "__main__":
    main()
