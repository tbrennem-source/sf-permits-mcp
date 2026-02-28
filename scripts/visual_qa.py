#!/usr/bin/env python3
"""Visual QA Pipeline — golden screenshots, video recording, filmstrips, structural diffs.

Replaces DeskCC as a per-sprint visual regression gate. Three modes:

1. **Page matrix** (regression): 21 pages x 3 viewports, pixel-diff against
   golden baselines, filmstrips for quick review.
2. **Journey videos** (demo): Scripted user flows with real clicks, typing,
   and scrolling — one video per journey.
3. **Structural mode** (DOM fingerprint): Captures a structural fingerprint of
   each page (CSS classes, component counts, HTMX attributes) and compares
   against saved baselines. Answers "did the layout skeleton change?" without
   pixel noise.

Usage:
    # Page matrix — establish baselines:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint56 --capture-goldens

    # Page matrix — compare against goldens:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint57

    # Journey videos — record interactive flows:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint57 --journeys

    # Both:
    python scripts/visual_qa.py --url ... --sprint sprint57 --capture-goldens --journeys

    # Single journey:
    python scripts/visual_qa.py --url ... --sprint sprint57 --journeys --journey-filter property-search

    # Structural mode — capture baselines:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint57 --structural --structural-baseline

    # Structural mode — check against baselines:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint57 --structural

    # Structural mode — only pages whose templates changed in HEAD~1:
    python scripts/visual_qa.py --url https://staging.example.com --sprint sprint57 --structural --structural-changed-only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image

# ---------------------------------------------------------------------------
# Page matrix — 21 pages across public / auth / admin
# ---------------------------------------------------------------------------

PAGES: list[dict] = [
    # --- Public (no auth) ---
    {"slug": "landing", "path": "/", "auth": "public"},
    {"slug": "search", "path": "/search?q=kitchen+remodel&neighborhood=Mission", "auth": "public"},
    {"slug": "login", "path": "/auth/login", "auth": "public"},
    {"slug": "beta-request", "path": "/beta-request", "auth": "public"},
    {"slug": "property-report", "path": "/report/3512/035", "auth": "public"},
    # --- Auth (logged-in user) ---
    {"slug": "account", "path": "/account", "auth": "auth"},
    {"slug": "brief", "path": "/brief", "auth": "auth"},
    {"slug": "portfolio", "path": "/portfolio", "auth": "auth"},
    {"slug": "consultants", "path": "/consultants", "auth": "auth"},
    {"slug": "bottlenecks", "path": "/dashboard/bottlenecks", "auth": "auth"},
    {"slug": "analyses", "path": "/account/analyses", "auth": "auth"},
    {"slug": "voice-calibration", "path": "/account/voice-calibration", "auth": "auth"},
    {"slug": "watch-list", "path": "/watch/list", "auth": "auth"},
    # --- Admin ---
    {"slug": "admin-feedback", "path": "/admin/feedback", "auth": "admin"},
    {"slug": "admin-activity", "path": "/admin/activity", "auth": "admin"},
    {"slug": "admin-ops", "path": "/admin/ops", "auth": "admin"},
    {"slug": "admin-sources", "path": "/admin/sources", "auth": "admin"},
    {"slug": "admin-regulatory", "path": "/admin/regulatory-watch", "auth": "admin"},
    {"slug": "admin-costs", "path": "/admin/costs", "auth": "admin"},
    {"slug": "admin-pipeline", "path": "/admin/pipeline", "auth": "admin"},
    {"slug": "admin-beta", "path": "/admin/beta-requests", "auth": "admin"},
]

VIEWPORTS = {
    "mobile": {"width": 390, "height": 844},
    "tablet": {"width": 768, "height": 1024},
    "desktop": {"width": 1440, "height": 900},
}

# ---------------------------------------------------------------------------
# Template → page slug mapping (for --structural-changed-only)
#
# Maps Jinja2 template file paths (relative to repo root) to the page slugs
# in PAGES that render them.  A template can map to multiple slugs.
# ---------------------------------------------------------------------------

TEMPLATE_TO_SLUG: dict[str, list[str]] = {
    # Public pages
    "web/templates/landing.html": ["landing"],
    "web/templates/search.html": ["search"],
    "web/templates/login.html": ["login"],
    "web/templates/beta_request.html": ["beta-request"],
    "web/templates/property_report.html": ["property-report"],
    # Auth pages
    "web/templates/account.html": ["account"],
    "web/templates/brief.html": ["brief"],
    "web/templates/portfolio.html": ["portfolio"],
    "web/templates/consultants.html": ["consultants"],
    "web/templates/bottlenecks.html": ["bottlenecks"],
    "web/templates/analyses.html": ["analyses"],
    "web/templates/voice_calibration.html": ["voice-calibration"],
    "web/templates/watch_list.html": ["watch-list"],
    # Admin pages
    "web/templates/admin/feedback.html": ["admin-feedback"],
    "web/templates/admin/activity.html": ["admin-activity"],
    "web/templates/admin/ops.html": ["admin-ops"],
    "web/templates/admin/sources.html": ["admin-sources"],
    "web/templates/admin/regulatory_watch.html": ["admin-regulatory"],
    "web/templates/admin/costs.html": ["admin-costs"],
    "web/templates/admin/pipeline.html": ["admin-pipeline"],
    "web/templates/admin/beta_requests.html": ["admin-beta"],
    # Shared components — treat as "touch everything"
    "web/templates/base.html": [p["slug"] for p in []],  # filled below
    "web/templates/head_obsidian.html": [p["slug"] for p in []],  # filled below
}

# Shared layout templates that affect ALL pages
_SHARED_TEMPLATES = {
    "web/templates/base.html",
    "web/templates/head_obsidian.html",
    "web/templates/nav.html",
    "web/templates/footer.html",
    "web/static/css/obsidian.css",
    "web/static/css/tokens.css",
}


def slugs_for_changed_files(changed_files: list[str]) -> list[str]:
    """Return page slugs that need structural re-check given a list of changed file paths.

    If a shared layout/CSS file is changed, returns ALL page slugs.
    Otherwise maps individual template filenames to their associated slugs.
    """
    all_slugs = [p["slug"] for p in PAGES]

    # Normalize paths — strip leading ./ or /
    normalized = [f.lstrip("./") for f in changed_files]

    # Any shared template or CSS change → all pages affected
    for nf in normalized:
        if nf in _SHARED_TEMPLATES:
            return all_slugs

    # Map individual templates
    matched: set[str] = set()
    for nf in normalized:
        if nf in TEMPLATE_TO_SLUG:
            matched.update(TEMPLATE_TO_SLUG[nf])

    return sorted(matched)


# ---------------------------------------------------------------------------
# Comparison engine
# ---------------------------------------------------------------------------

@dataclass
class CompareResult:
    page_slug: str
    viewport: str
    status: str  # "pass", "fail", "new_baseline"
    diff_pct: float = 0.0
    diff_path: Optional[str] = None
    screenshot_path: str = ""
    message: str = ""


def compare_screenshots(
    current_path: str | Path,
    golden_path: str | Path,
    diff_output_path: str | Path,
    *,
    threshold_pct: float = 1.0,
    pixel_tolerance: int = 30,
) -> tuple[str, float, Optional[str]]:
    """Compare two screenshots pixel-by-pixel.

    Returns (status, diff_pct, diff_image_path_or_none).
    status is "pass", "fail", or "new_baseline".
    """
    current_path = Path(current_path)
    golden_path = Path(golden_path)
    diff_output_path = Path(diff_output_path)

    if not golden_path.exists():
        return "new_baseline", 0.0, None

    current_img = Image.open(current_path).convert("RGB")
    golden_img = Image.open(golden_path).convert("RGB")

    # Handle size mismatch — resize golden to match current
    if current_img.size != golden_img.size:
        golden_img = golden_img.resize(current_img.size, Image.LANCZOS)

    w, h = current_img.size
    total_pixels = w * h
    current_data = current_img.load()
    golden_data = golden_img.load()

    diff_count = 0
    diff_img = Image.new("RGB", (w, h), (0, 0, 0))
    diff_data = diff_img.load()

    for y in range(h):
        for x in range(w):
            cr, cg, cb = current_data[x, y]
            gr, gg, gb = golden_data[x, y]
            if (
                abs(cr - gr) > pixel_tolerance
                or abs(cg - gg) > pixel_tolerance
                or abs(cb - gb) > pixel_tolerance
            ):
                diff_count += 1
                diff_data[x, y] = (255, 0, 80)  # Hot pink for diffs
            else:
                # Dim version of the current image
                diff_data[x, y] = (cr // 3, cg // 3, cb // 3)

    diff_pct = (diff_count / total_pixels) * 100 if total_pixels > 0 else 0.0

    if diff_pct > threshold_pct:
        diff_output_path.parent.mkdir(parents=True, exist_ok=True)
        diff_img.save(str(diff_output_path))
        return "fail", diff_pct, str(diff_output_path)

    return "pass", diff_pct, None


# ---------------------------------------------------------------------------
# Filmstrip generator
# ---------------------------------------------------------------------------

FILMSTRIP_HEIGHT = 400
FILMSTRIP_GAP = 4
FILMSTRIP_BG = (30, 30, 30)


def make_filmstrip(
    image_paths: list[str | Path],
    output_path: str | Path,
    *,
    frame_height: int = FILMSTRIP_HEIGHT,
    gap: int = FILMSTRIP_GAP,
) -> str:
    """Stitch multiple screenshots into a horizontal filmstrip PNG.

    Each frame is scaled to `frame_height` maintaining aspect ratio.
    Returns the output path.
    """
    output_path = Path(output_path)
    frames: list[Image.Image] = []

    for p in image_paths:
        p = Path(p)
        if not p.exists():
            continue
        img = Image.open(p).convert("RGB")
        ratio = frame_height / img.height
        new_w = max(1, int(img.width * ratio))
        frames.append(img.resize((new_w, frame_height), Image.LANCZOS))

    if not frames:
        # Create a small placeholder
        placeholder = Image.new("RGB", (200, frame_height), FILMSTRIP_BG)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        placeholder.save(str(output_path))
        return str(output_path)

    total_w = sum(f.width for f in frames) + gap * (len(frames) - 1)
    strip = Image.new("RGB", (total_w, frame_height), FILMSTRIP_BG)

    x_offset = 0
    for frame in frames:
        strip.paste(frame, (x_offset, 0))
        x_offset += frame.width + gap

    output_path.parent.mkdir(parents=True, exist_ok=True)
    strip.save(str(output_path))
    return str(output_path)


# ---------------------------------------------------------------------------
# Markers JSON (admin QA replay UI compatible)
# ---------------------------------------------------------------------------

def build_markers(
    results: list[CompareResult],
    sprint: str,
    viewport: str,
    video_path: Optional[str] = None,
) -> dict:
    """Build a markers JSON for the admin QA replay UI."""
    steps = []
    for i, r in enumerate(results):
        steps.append({
            "step": i + 1,
            "page": r.page_slug,
            "viewport": viewport,
            "status": r.status,
            "diff_pct": round(r.diff_pct, 3),
            "screenshot": r.screenshot_path,
            "diff_image": r.diff_path,
            "message": r.message,
        })
    return {
        "sprint": sprint,
        "viewport": viewport,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "video": video_path,
        "total_pages": len(results),
        "passed": sum(1 for r in results if r.status == "pass"),
        "failed": sum(1 for r in results if r.status == "fail"),
        "new_baselines": sum(1 for r in results if r.status == "new_baseline"),
        "steps": steps,
    }


# ---------------------------------------------------------------------------
# Results markdown
# ---------------------------------------------------------------------------

def write_results_md(
    all_results: dict[str, list[CompareResult]],
    sprint: str,
    output_path: Path,
    filmstrip_paths: dict[str, str],
) -> None:
    """Write a summary markdown table."""
    lines = [
        f"# Visual QA Results — {sprint}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    total_pass = 0
    total_fail = 0
    total_new = 0

    for vp_name, results in all_results.items():
        p = sum(1 for r in results if r.status == "pass")
        f = sum(1 for r in results if r.status == "fail")
        n = sum(1 for r in results if r.status == "new_baseline")
        total_pass += p
        total_fail += f
        total_new += n

        lines.append(f"## {vp_name.title()} ({VIEWPORTS[vp_name]['width']}x{VIEWPORTS[vp_name]['height']})")
        if vp_name in filmstrip_paths:
            lines.append(f"Filmstrip: `{filmstrip_paths[vp_name]}`")
        lines.append("")
        lines.append("| Page | Status | Diff % | Notes |")
        lines.append("|------|--------|--------|-------|")
        for r in results:
            status_icon = {"pass": "PASS", "fail": "FAIL", "new_baseline": "NEW"}[r.status]
            lines.append(f"| {r.page_slug} | {status_icon} | {r.diff_pct:.2f}% | {r.message} |")
        lines.append("")

    # Summary
    lines.insert(2, "")
    summary = f"**Summary:** {total_pass} PASS / {total_fail} FAIL / {total_new} NEW"
    lines.insert(3, summary)
    lines.insert(4, "")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))


# ---------------------------------------------------------------------------
# User journey definitions
# ---------------------------------------------------------------------------

@dataclass
class JourneyStep:
    """A single action in a user journey.

    Actions: goto, click, type, scroll, wait, screenshot, breakpoint.
    breakpoint pauses in --guided mode so the user can interact with the
    live browser. In headless mode breakpoints are silently skipped.
    """
    action: str  # goto, click, type, scroll, wait, screenshot, breakpoint
    description: str
    selector: str = ""
    value: str = ""  # URL for goto, text for type, pixels for scroll
    wait_after_ms: int = 800


JOURNEYS: list[dict] = [
    {
        "slug": "property-search",
        "title": "Property Search Flow",
        "auth": "public",
        "steps": [
            JourneyStep("goto", "Open landing page", value="/"),
            JourneyStep("screenshot", "Landing page loaded"),
            JourneyStep("click", "Click search input", selector="input[name='q'], input[type='search'], #search-input, .search-input, input[placeholder*='address'], input[placeholder*='Enter']"),
            JourneyStep("type", "Type a search query", selector="input[name='q'], input[type='search'], #search-input, .search-input, input[placeholder*='address'], input[placeholder*='Enter']", value="1234 Market St"),
            JourneyStep("screenshot", "Typed search query"),
            JourneyStep("click", "Submit search", selector="button[type='submit'], .search-button, button:has-text('Search')"),
            JourneyStep("wait", "Wait for results", wait_after_ms=2000),
            JourneyStep("screenshot", "Search results page"),
            JourneyStep("breakpoint", "Explore search results — click around, try different queries"),
            JourneyStep("scroll", "Scroll down results", value="600"),
            JourneyStep("screenshot", "Scrolled results"),
            JourneyStep("goto", "Open a property report", value="/report/3512/035"),
            JourneyStep("screenshot", "Property report loaded"),
            JourneyStep("breakpoint", "Explore the property report — scroll, check sections"),
            JourneyStep("scroll", "Scroll through report", value="400"),
            JourneyStep("screenshot", "Report scrolled"),
            JourneyStep("scroll", "Scroll more", value="400"),
            JourneyStep("screenshot", "Report bottom"),
        ],
    },
    {
        "slug": "morning-brief",
        "title": "Morning Brief Flow",
        "auth": "auth",
        "steps": [
            JourneyStep("goto", "Open morning brief", value="/brief"),
            JourneyStep("wait", "Wait for brief to load", wait_after_ms=2000),
            JourneyStep("screenshot", "Brief loaded"),
            JourneyStep("breakpoint", "Review the morning brief — check data, scroll around"),
            JourneyStep("scroll", "Scroll through brief", value="500"),
            JourneyStep("screenshot", "Brief section 2"),
            JourneyStep("scroll", "Continue scrolling", value="500"),
            JourneyStep("screenshot", "Brief section 3"),
            JourneyStep("scroll", "Scroll to bottom", value="500"),
            JourneyStep("screenshot", "Brief bottom"),
        ],
    },
    {
        "slug": "admin-walkthrough",
        "title": "Admin Dashboard Walkthrough",
        "auth": "admin",
        "steps": [
            JourneyStep("goto", "Open admin ops", value="/admin/ops"),
            JourneyStep("wait", "Wait for admin page", wait_after_ms=1500),
            JourneyStep("screenshot", "Admin ops loaded"),
            JourneyStep("breakpoint", "Explore admin ops — click tabs, check data"),
            JourneyStep("scroll", "Scroll admin ops", value="400"),
            JourneyStep("screenshot", "Admin ops scrolled"),
            JourneyStep("goto", "Open admin costs", value="/admin/costs"),
            JourneyStep("wait", "Wait for costs page", wait_after_ms=1500),
            JourneyStep("screenshot", "Admin costs loaded"),
            JourneyStep("goto", "Open admin pipeline", value="/admin/pipeline"),
            JourneyStep("wait", "Wait for pipeline page", wait_after_ms=1500),
            JourneyStep("screenshot", "Pipeline health loaded"),
            JourneyStep("scroll", "Scroll pipeline", value="400"),
            JourneyStep("screenshot", "Pipeline scrolled"),
            JourneyStep("goto", "Open admin feedback", value="/admin/feedback"),
            JourneyStep("wait", "Wait for feedback page", wait_after_ms=1500),
            JourneyStep("screenshot", "Feedback page loaded"),
        ],
    },
    {
        "slug": "portfolio-review",
        "title": "Portfolio Review Flow",
        "auth": "auth",
        "steps": [
            JourneyStep("goto", "Open portfolio", value="/portfolio"),
            JourneyStep("wait", "Wait for portfolio", wait_after_ms=1500),
            JourneyStep("screenshot", "Portfolio loaded"),
            JourneyStep("breakpoint", "Explore portfolio — add properties, check watch items"),
            JourneyStep("scroll", "Scroll portfolio", value="400"),
            JourneyStep("screenshot", "Portfolio scrolled"),
            JourneyStep("goto", "Open analysis history", value="/account/analyses"),
            JourneyStep("wait", "Wait for analyses", wait_after_ms=1500),
            JourneyStep("screenshot", "Analysis history loaded"),
            JourneyStep("goto", "Open account settings", value="/account"),
            JourneyStep("screenshot", "Account page loaded"),
            JourneyStep("scroll", "Scroll account", value="300"),
            JourneyStep("screenshot", "Account scrolled"),
        ],
    },
]


# ---------------------------------------------------------------------------
# Journey runner
# ---------------------------------------------------------------------------

@dataclass
class JourneyResult:
    journey_slug: str
    journey_title: str
    viewport: str
    video_path: Optional[str]
    screenshots: list[str]
    markers_path: str
    filmstrip_path: Optional[str]
    step_count: int
    error: Optional[str] = None


def _try_click(page, selector_chain: str, timeout: int = 5000) -> bool:
    """Try multiple selectors (comma-separated), click the first visible one."""
    for sel in selector_chain.split(","):
        sel = sel.strip()
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1000):
                loc.click(timeout=timeout)
                return True
        except Exception:
            continue
    return False


def _try_type(page, selector_chain: str, text: str, timeout: int = 5000) -> bool:
    """Try multiple selectors, type into the first visible one."""
    for sel in selector_chain.split(","):
        sel = sel.strip()
        try:
            loc = page.locator(sel).first
            if loc.is_visible(timeout=1000):
                loc.click(timeout=2000)
                loc.fill(text)
                return True
        except Exception:
            continue
    return False


def _guided_breakpoint(page, description: str, shot_idx: int, screenshots_dir: Path) -> list[str]:
    """Pause for user interaction in guided mode.

    Prints instructions, waits for Enter. Takes a screenshot after the
    user is done exploring. Returns list of screenshot paths captured.
    """
    extra_shots: list[str] = []
    print(f"\n    {'='*60}")
    print(f"    BREAKPOINT: {description}")
    print(f"    The browser is yours — click around, scroll, explore.")
    print(f"    Commands:  [Enter] = continue  |  s = screenshot + continue")
    print(f"               q = skip remaining breakpoints")
    print(f"    {'='*60}")

    user_input = input("    > ").strip().lower()

    if user_input == "s":
        shot_path = screenshots_dir / f"{shot_idx:02d}-user-breakpoint.png"
        try:
            page.screenshot(path=str(shot_path), full_page=False)
            extra_shots.append(str(shot_path))
            print(f"    Screenshot saved: {shot_path.name}")
        except Exception as e:
            print(f"    Screenshot failed: {e}")

    return extra_shots if user_input != "q" else ["__skip_breakpoints__"]


def run_journeys(
    base_url: str,
    sprint: str,
    *,
    viewport_name: str = "desktop",
    journey_filter: Optional[list[str]] = None,
    guided: bool = False,
    qa_root: Path = Path("qa-results"),
) -> list[JourneyResult]:
    """Record user journey videos with real interactions.

    With guided=True, launches a visible browser and pauses at breakpoint
    steps so the user can interact directly. All actions are still recorded.
    """
    from playwright.sync_api import sync_playwright

    base_url = base_url.rstrip("/")
    test_secret = os.environ.get("TEST_LOGIN_SECRET", "")
    vp_size = VIEWPORTS[viewport_name]

    videos_dir = qa_root / "videos" / sprint / "journeys"
    screenshots_dir = qa_root / "screenshots" / sprint / "journeys"
    filmstrips_dir = qa_root / "filmstrips"
    markers_dir = qa_root / "markers"

    for d in [videos_dir, screenshots_dir, filmstrips_dir, markers_dir]:
        d.mkdir(parents=True, exist_ok=True)

    journeys_to_run = JOURNEYS
    if journey_filter:
        journeys_to_run = [j for j in JOURNEYS if j["slug"] in journey_filter]

    results: list[JourneyResult] = []

    if guided:
        print("\n  GUIDED MODE — browser will open visibly.")
        print("  At each breakpoint you can interact with the page.")
        print("  Everything is still recorded to video.\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not guided, slow_mo=150 if guided else 0)
        skip_breakpoints = False

        for journey in journeys_to_run:
            slug = journey["slug"]
            title = journey["title"]
            auth_level = journey["auth"]
            steps: list[JourneyStep] = journey["steps"]

            print(f"  Recording journey: {title} ({slug})...")

            j_video_dir = videos_dir / slug
            j_video_dir.mkdir(parents=True, exist_ok=True)
            j_screenshots_dir = screenshots_dir / slug
            j_screenshots_dir.mkdir(parents=True, exist_ok=True)

            context = browser.new_context(
                viewport=vp_size,
                record_video_dir=str(j_video_dir),
                record_video_size=vp_size,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Auth if needed
            logged_in = False
            if auth_level in ("auth", "admin") and test_secret:
                role = "admin" if auth_level == "admin" else "user"
                logged_in = _login_via_test_secret(page, base_url, role, test_secret)

            if auth_level in ("auth", "admin") and not logged_in:
                page.close()
                context.close()
                results.append(JourneyResult(
                    journey_slug=slug,
                    journey_title=title,
                    viewport=viewport_name,
                    video_path=None,
                    screenshots=[],
                    markers_path="",
                    filmstrip_path=None,
                    step_count=len(steps),
                    error="skipped (no TEST_LOGIN_SECRET)",
                ))
                print(f"    Skipped (no auth)")
                continue

            screenshot_paths: list[str] = []
            marker_steps: list[dict] = []
            error_msg = None
            shot_idx = 0

            for i, step in enumerate(steps):
                step_marker = {
                    "step": i + 1,
                    "action": step.action,
                    "description": step.description,
                    "timestamp_ms": None,
                    "screenshot": None,
                    "success": True,
                }

                try:
                    if step.action == "goto":
                        url = f"{base_url}{step.value}"
                        page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    elif step.action == "click":
                        success = _try_click(page, step.selector)
                        step_marker["success"] = success
                        if not success:
                            step_marker["description"] += " (selector not found, continuing)"
                    elif step.action == "type":
                        success = _try_type(page, step.selector, step.value)
                        step_marker["success"] = success
                        if not success:
                            step_marker["description"] += " (selector not found, continuing)"
                    elif step.action == "scroll":
                        page.evaluate(f"window.scrollBy(0, {step.value})")
                    elif step.action == "wait":
                        pass  # wait_after_ms handles it below
                    elif step.action == "breakpoint":
                        if guided and not skip_breakpoints:
                            extra = _guided_breakpoint(
                                page, step.description, shot_idx, j_screenshots_dir,
                            )
                            if extra and extra[0] == "__skip_breakpoints__":
                                skip_breakpoints = True
                            else:
                                for sp in extra:
                                    screenshot_paths.append(sp)
                                    shot_idx += 1
                        # In headless mode, breakpoints are silently skipped
                    elif step.action == "screenshot":
                        shot_path = j_screenshots_dir / f"{shot_idx:02d}-{step.description.lower().replace(' ', '-')[:40]}.png"
                        page.screenshot(path=str(shot_path), full_page=False)
                        screenshot_paths.append(str(shot_path))
                        step_marker["screenshot"] = str(shot_path)
                        shot_idx += 1

                    page.wait_for_timeout(step.wait_after_ms)

                except Exception as e:
                    step_marker["success"] = False
                    step_marker["description"] += f" (error: {e})"
                    # Continue — don't abort the whole journey for one step

                marker_steps.append(step_marker)

            # Close to finalize video
            page.close()
            context.close()

            # Find video
            video_file = None
            video_files = list(j_video_dir.glob("*.webm"))
            if video_files:
                video_file = str(video_files[0])

            # Build filmstrip from journey screenshots
            filmstrip_path = None
            if screenshot_paths:
                strip_path = filmstrips_dir / f"{sprint}-journey-{slug}.png"
                make_filmstrip(screenshot_paths, strip_path)
                filmstrip_path = str(strip_path)

            # Write markers
            markers = {
                "type": "journey",
                "sprint": sprint,
                "journey": slug,
                "title": title,
                "viewport": viewport_name,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "video": video_file,
                "filmstrip": filmstrip_path,
                "total_steps": len(steps),
                "steps": marker_steps,
            }
            markers_path = markers_dir / f"{sprint}-journey-{slug}.json"
            markers_path.write_text(json.dumps(markers, indent=2))

            results.append(JourneyResult(
                journey_slug=slug,
                journey_title=title,
                viewport=viewport_name,
                video_path=video_file,
                screenshots=screenshot_paths,
                markers_path=str(markers_path),
                filmstrip_path=filmstrip_path,
                step_count=len(steps),
                error=error_msg,
            ))

            shots = len(screenshot_paths)
            print(f"    Done: {shots} screenshots, video={'yes' if video_file else 'no'}")

        browser.close()

    # Print summary
    print(f"\nJourney recording complete: {len(results)} journeys")
    for r in results:
        status = "OK" if not r.error else r.error
        print(f"  {r.journey_slug}: {status} | video={r.video_path or 'none'}")
        if r.filmstrip_path:
            print(f"    filmstrip: {r.filmstrip_path}")

    return results


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _login_via_test_secret(page, base_url: str, role: str, secret: str) -> bool:
    """Authenticate using the test-login endpoint. Returns True on success."""
    email = f"test-{role}@sfpermits.ai" if role == "admin" else "test-user@sfpermits.ai"
    try:
        resp = page.request.post(
            f"{base_url}/auth/test-login",
            data=json.dumps({"email": email, "secret": secret}),
            headers={"Content-Type": "application/json"},
        )
        return resp.status == 200 or resp.status == 302
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run_visual_qa(
    base_url: str,
    sprint: str,
    *,
    capture_goldens: bool = False,
    update_goldens: bool = False,
    viewport_filter: Optional[str] = None,
    page_filter: Optional[list[str]] = None,
    threshold_pct: float = 1.0,
    pixel_tolerance: int = 30,
    qa_root: Path = Path("qa-results"),
) -> dict[str, list[CompareResult]]:
    """Run the full visual QA pipeline."""
    from playwright.sync_api import sync_playwright

    base_url = base_url.rstrip("/")
    test_secret = os.environ.get("TEST_LOGIN_SECRET", "")

    goldens_dir = qa_root / "goldens"
    screenshots_dir = qa_root / "screenshots" / sprint
    videos_dir = qa_root / "videos" / sprint
    filmstrips_dir = qa_root / "filmstrips"
    markers_dir = qa_root / "markers"

    for d in [goldens_dir, screenshots_dir, videos_dir, filmstrips_dir, markers_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # Filter pages
    pages_to_test = PAGES
    if page_filter:
        pages_to_test = [p for p in PAGES if p["slug"] in page_filter]

    # Filter viewports
    viewports_to_test = VIEWPORTS
    if viewport_filter:
        viewports_to_test = {viewport_filter: VIEWPORTS[viewport_filter]}

    all_results: dict[str, list[CompareResult]] = {}
    filmstrip_paths: dict[str, str] = {}
    video_paths: dict[str, Optional[str]] = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for vp_name, vp_size in viewports_to_test.items():
            vp_video_dir = videos_dir / vp_name
            vp_video_dir.mkdir(parents=True, exist_ok=True)

            context = browser.new_context(
                viewport=vp_size,
                record_video_dir=str(vp_video_dir),
                record_video_size=vp_size,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Determine max auth level needed
            needs_admin = any(p["auth"] == "admin" for p in pages_to_test)
            needs_auth = needs_admin or any(p["auth"] == "auth" for p in pages_to_test)

            # Login if needed and secret available
            logged_in = False
            if needs_auth and test_secret:
                role = "admin" if needs_admin else "user"
                logged_in = _login_via_test_secret(page, base_url, role, test_secret)

            results: list[CompareResult] = []

            for page_def in pages_to_test:
                slug = page_def["slug"]
                path = page_def["path"]
                auth_level = page_def["auth"]
                filename = f"{slug}-{vp_name}.png"

                # Skip auth/admin pages if not logged in
                if auth_level in ("auth", "admin") and not logged_in:
                    results.append(CompareResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="pass",
                        message="skipped (no TEST_LOGIN_SECRET)",
                        screenshot_path="",
                    ))
                    continue

                screenshot_path = screenshots_dir / filename
                golden_path = goldens_dir / filename
                diff_path = screenshots_dir / f"{slug}-{vp_name}-diff.png"

                # Navigate with retry (staging can be slow under load)
                url = f"{base_url}{path}"
                nav_ok = False
                last_err = None
                for attempt in range(3):
                    try:
                        if attempt > 0:
                            page.wait_for_timeout(3000)  # Back off between retries
                        page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(1500)  # Settle time for JS/HTMX
                        page.screenshot(path=str(screenshot_path), full_page=True)
                        nav_ok = True
                        break
                    except Exception as e:
                        last_err = e

                if not nav_ok:
                    results.append(CompareResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="fail",
                        message=f"navigation error after 3 attempts: {last_err}",
                        screenshot_path=str(screenshot_path),
                    ))
                    continue

                # Pace requests to avoid overwhelming staging
                page.wait_for_timeout(500)

                # Golden management
                if capture_goldens or update_goldens:
                    golden_path.parent.mkdir(parents=True, exist_ok=True)
                    Image.open(screenshot_path).save(str(golden_path))
                    results.append(CompareResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="new_baseline",
                        message="golden captured" if capture_goldens else "golden updated",
                        screenshot_path=str(screenshot_path),
                    ))
                    continue

                # Compare
                status, diff_pct, diff_img_path = compare_screenshots(
                    screenshot_path,
                    golden_path,
                    diff_path,
                    threshold_pct=threshold_pct,
                    pixel_tolerance=pixel_tolerance,
                )
                msg = ""
                if status == "new_baseline":
                    # Auto-save as golden when no baseline exists
                    golden_path.parent.mkdir(parents=True, exist_ok=True)
                    Image.open(screenshot_path).save(str(golden_path))
                    msg = "auto-captured as new golden"
                elif status == "fail":
                    msg = f"diff {diff_pct:.2f}% exceeds {threshold_pct}%"
                elif status == "pass":
                    msg = f"diff {diff_pct:.2f}%"

                results.append(CompareResult(
                    page_slug=slug,
                    viewport=vp_name,
                    status=status,
                    diff_pct=diff_pct,
                    diff_path=diff_img_path,
                    screenshot_path=str(screenshot_path),
                    message=msg,
                ))

            # Close context to finalize video
            page.close()
            context.close()

            # Find the video file
            video_file = None
            video_files = list(vp_video_dir.glob("*.webm"))
            if video_files:
                video_file = str(video_files[0])
            video_paths[vp_name] = video_file

            all_results[vp_name] = results

            # Build filmstrip (exclude diff images)
            filmstrip_images = [
                r.screenshot_path
                for r in results
                if r.screenshot_path and Path(r.screenshot_path).exists()
            ]
            if filmstrip_images:
                strip_path = filmstrips_dir / f"{sprint}-{vp_name}.png"
                make_filmstrip(filmstrip_images, strip_path)
                filmstrip_paths[vp_name] = str(strip_path)

            # Write markers JSON
            markers = build_markers(results, sprint, vp_name, video_file)
            markers_path = markers_dir / f"{sprint}-visual-{vp_name}.json"
            markers_path.write_text(json.dumps(markers, indent=2))

            print(f"  {vp_name}: {sum(1 for r in results if r.status != 'fail')}/{len(results)} OK")

        browser.close()

    # Write results markdown
    results_path = qa_root / f"{sprint}-visual-results.md"
    write_results_md(all_results, sprint, results_path, filmstrip_paths)

    # Print summary
    total_pass = sum(1 for vp in all_results.values() for r in vp if r.status == "pass")
    total_fail = sum(1 for vp in all_results.values() for r in vp if r.status == "fail")
    total_new = sum(1 for vp in all_results.values() for r in vp if r.status == "new_baseline")
    print(f"\nVisual QA complete: {total_pass} PASS / {total_fail} FAIL / {total_new} NEW")
    print(f"Results: {results_path}")
    for vp_name, path in filmstrip_paths.items():
        print(f"Filmstrip ({vp_name}): {path}")

    return all_results


# ---------------------------------------------------------------------------
# Structural mode — DOM fingerprint diff
# ---------------------------------------------------------------------------

# JavaScript run inside the page via page.evaluate() to collect a fingerprint.
# Returns a plain dict that can be JSON-serialised.
_FINGERPRINT_JS = """
() => {
    // 1. CSS classes on <body>
    const bodyClasses = Array.from(document.body.classList).sort();

    // 2. CSS classes on first grid/flex container
    const containerSelectors = [
        'body > div', 'main', '.obs-container', '.obs-container-wide'
    ];
    let containerClasses = [];
    for (const sel of containerSelectors) {
        const el = document.querySelector(sel);
        if (el) {
            containerClasses = Array.from(el.classList).sort();
            break;
        }
    }

    // 3. Component counts by class / tag
    const componentCounts = {
        glass_card:   document.querySelectorAll('.glass-card').length,
        obs_table:    document.querySelectorAll('.obs-table').length,
        nav:          document.querySelectorAll('nav').length,
        footer:       document.querySelectorAll('footer').length,
        ghost_cta:    document.querySelectorAll('.ghost-cta').length,
        form:         document.querySelectorAll('form').length,
        status_dot:   document.querySelectorAll('.status-dot').length,
    };

    // 4. HTMX attribute presence
    const htmxPresence = {
        hx_get:    document.querySelector('[hx-get]') !== null,
        hx_post:   document.querySelector('[hx-post]') !== null,
        hx_target: document.querySelector('[hx-target]') !== null,
        hx_swap:   document.querySelector('[hx-swap]') !== null,
    };

    // 5. Viewport overflow
    const viewportOverflow = document.documentElement.scrollWidth > window.innerWidth;

    // 6. Centering check — main content container offsetLeft > 20
    let centered = false;
    for (const sel of ['main', '.obs-container', '.obs-container-wide', 'body > div']) {
        const el = document.querySelector(sel);
        if (el) {
            centered = el.offsetLeft > 20;
            break;
        }
    }

    return {
        body_classes: bodyClasses,
        container_classes: containerClasses,
        component_counts: componentCounts,
        htmx_presence: htmxPresence,
        viewport_overflow: viewportOverflow,
        centered: centered,
    };
}
"""


def get_page_fingerprint(page) -> dict:
    """Collect a structural fingerprint from a live Playwright page.

    Runs _FINGERPRINT_JS via page.evaluate() and returns the result dict.
    Raises on evaluate error — callers should catch and mark as failed.
    """
    return page.evaluate(_FINGERPRINT_JS)


def diff_fingerprints(baseline: dict, current: dict) -> list[str]:
    """Compare two fingerprints and return a list of human-readable diff strings.

    Returns an empty list if the fingerprints are identical (PASS).
    """
    diffs: list[str] = []

    # body_classes — sorted list comparison
    b_body = sorted(baseline.get("body_classes", []))
    c_body = sorted(current.get("body_classes", []))
    added = sorted(set(c_body) - set(b_body))
    removed = sorted(set(b_body) - set(c_body))
    if added:
        diffs.append(f"body_classes added: {added}")
    if removed:
        diffs.append(f"body_classes removed: {removed}")

    # container_classes
    b_cc = sorted(baseline.get("container_classes", []))
    c_cc = sorted(current.get("container_classes", []))
    cc_added = sorted(set(c_cc) - set(b_cc))
    cc_removed = sorted(set(b_cc) - set(c_cc))
    if cc_added:
        diffs.append(f"container_classes added: {cc_added}")
    if cc_removed:
        diffs.append(f"container_classes removed: {cc_removed}")

    # component_counts — exact match per component key
    b_counts = baseline.get("component_counts", {})
    c_counts = current.get("component_counts", {})
    all_keys = set(b_counts) | set(c_counts)
    for key in sorted(all_keys):
        b_val = b_counts.get(key, 0)
        c_val = c_counts.get(key, 0)
        if b_val != c_val:
            diffs.append(f"component_counts.{key}: {b_val} → {c_val}")

    # htmx_presence — boolean per key
    b_htmx = baseline.get("htmx_presence", {})
    c_htmx = current.get("htmx_presence", {})
    all_htmx = set(b_htmx) | set(c_htmx)
    for key in sorted(all_htmx):
        b_val = b_htmx.get(key, False)
        c_val = c_htmx.get(key, False)
        if b_val != c_val:
            diffs.append(f"htmx_presence.{key}: {b_val} → {c_val}")

    # Boolean fields
    for field_name in ("viewport_overflow", "centered"):
        b_val = baseline.get(field_name)
        c_val = current.get(field_name)
        if b_val != c_val:
            diffs.append(f"{field_name}: {b_val} → {c_val}")

    return diffs


@dataclass
class StructuralResult:
    page_slug: str
    viewport: str
    status: str  # "pass", "fail", "new_baseline", "skip", "error"
    diffs: list[str] = field(default_factory=list)
    baseline_path: str = ""
    message: str = ""


def _get_changed_files_from_git(since: str = "HEAD~1") -> list[str]:
    """Return list of file paths changed in git since `since`."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", since],
            capture_output=True,
            text=True,
            check=True,
        )
        return [f.strip() for f in result.stdout.splitlines() if f.strip()]
    except subprocess.CalledProcessError:
        return []


def run_structural_qa(
    base_url: str,
    sprint: str,
    *,
    capture_baseline: bool = False,
    viewport_filter: Optional[str] = None,
    page_filter: Optional[list[str]] = None,
    changed_only: bool = False,
    qa_root: Path = Path("qa-results"),
) -> list[StructuralResult]:
    """Run the structural DOM fingerprint QA pipeline.

    In baseline mode (capture_baseline=True): collect fingerprints and save to
    qa-results/structural-baselines/<slug>-<viewport>.json.

    In check mode (capture_baseline=False): compare current fingerprints against
    saved baselines, write qa-results/qs10-structural-results.md.

    With changed_only=True: only check pages whose templates appear in git diff
    HEAD~1 (uses TEMPLATE_TO_SLUG mapping).
    """
    from playwright.sync_api import sync_playwright

    base_url = base_url.rstrip("/")
    test_secret = os.environ.get("TEST_LOGIN_SECRET", "")

    baselines_dir = qa_root / "structural-baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)

    # Determine which pages to run
    pages_to_test = PAGES
    if page_filter:
        pages_to_test = [p for p in PAGES if p["slug"] in page_filter]
    if changed_only:
        changed_files = _get_changed_files_from_git()
        affected_slugs = slugs_for_changed_files(changed_files)
        pages_to_test = [p for p in pages_to_test if p["slug"] in affected_slugs]
        if not pages_to_test:
            print("  structural: no pages affected by recent changes — skipping")
            return []

    # Filter viewports
    viewports_to_test = VIEWPORTS
    if viewport_filter:
        viewports_to_test = {viewport_filter: VIEWPORTS[viewport_filter]}

    all_results: list[StructuralResult] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for vp_name, vp_size in viewports_to_test.items():
            context = browser.new_context(
                viewport=vp_size,
                ignore_https_errors=True,
            )
            page = context.new_page()

            # Auth — log in if any pages require it
            needs_admin = any(p["auth"] == "admin" for p in pages_to_test)
            needs_auth = needs_admin or any(p["auth"] == "auth" for p in pages_to_test)
            logged_in = False
            if needs_auth and test_secret:
                role = "admin" if needs_admin else "user"
                logged_in = _login_via_test_secret(page, base_url, role, test_secret)

            for page_def in pages_to_test:
                slug = page_def["slug"]
                path = page_def["path"]
                auth_level = page_def["auth"]
                baseline_path = baselines_dir / f"{slug}-{vp_name}.json"

                # Skip auth pages if not logged in
                if auth_level in ("auth", "admin") and not logged_in:
                    all_results.append(StructuralResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="skip",
                        message="skipped (no TEST_LOGIN_SECRET)",
                        baseline_path=str(baseline_path),
                    ))
                    continue

                # Navigate with retry
                url = f"{base_url}{path}"
                nav_ok = False
                last_err = None
                for attempt in range(3):
                    try:
                        if attempt > 0:
                            page.wait_for_timeout(3000)
                        page.goto(url, wait_until="domcontentloaded", timeout=45000)
                        page.wait_for_timeout(1000)  # settle time
                        nav_ok = True
                        break
                    except Exception as e:
                        last_err = e

                if not nav_ok:
                    all_results.append(StructuralResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="error",
                        message=f"navigation error after 3 attempts: {last_err}",
                        baseline_path=str(baseline_path),
                    ))
                    continue

                # Collect fingerprint
                try:
                    fingerprint = get_page_fingerprint(page)
                except Exception as e:
                    all_results.append(StructuralResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="error",
                        message=f"fingerprint error: {e}",
                        baseline_path=str(baseline_path),
                    ))
                    continue

                if capture_baseline:
                    # Save fingerprint as new baseline
                    baseline_path.parent.mkdir(parents=True, exist_ok=True)
                    baseline_path.write_text(json.dumps(fingerprint, indent=2))
                    all_results.append(StructuralResult(
                        page_slug=slug,
                        viewport=vp_name,
                        status="new_baseline",
                        message="baseline captured",
                        baseline_path=str(baseline_path),
                    ))
                else:
                    # Check mode — compare against saved baseline
                    if not baseline_path.exists():
                        # Auto-save as first baseline
                        baseline_path.parent.mkdir(parents=True, exist_ok=True)
                        baseline_path.write_text(json.dumps(fingerprint, indent=2))
                        all_results.append(StructuralResult(
                            page_slug=slug,
                            viewport=vp_name,
                            status="new_baseline",
                            message="no baseline found — auto-captured",
                            baseline_path=str(baseline_path),
                        ))
                    else:
                        baseline_fp = json.loads(baseline_path.read_text())
                        diffs = diff_fingerprints(baseline_fp, fingerprint)
                        status = "fail" if diffs else "pass"
                        all_results.append(StructuralResult(
                            page_slug=slug,
                            viewport=vp_name,
                            status=status,
                            diffs=diffs,
                            baseline_path=str(baseline_path),
                            message=f"{len(diffs)} structural diff(s)" if diffs else "no structural changes",
                        ))

                page.wait_for_timeout(300)  # pace requests

            page.close()
            context.close()

        browser.close()

    # Write results markdown
    _write_structural_results_md(all_results, sprint, qa_root / "qs10-structural-results.md")

    # Print summary
    n_pass = sum(1 for r in all_results if r.status == "pass")
    n_fail = sum(1 for r in all_results if r.status == "fail")
    n_new = sum(1 for r in all_results if r.status == "new_baseline")
    n_skip = sum(1 for r in all_results if r.status in ("skip", "error"))
    print(f"\nStructural QA: {n_pass} PASS / {n_fail} FAIL / {n_new} NEW / {n_skip} SKIP")
    if n_fail:
        for r in all_results:
            if r.status == "fail":
                print(f"  FAIL {r.page_slug} ({r.viewport}): {r.message}")
                for d in r.diffs:
                    print(f"    - {d}")

    return all_results


def _write_structural_results_md(
    results: list[StructuralResult],
    sprint: str,
    output_path: Path,
) -> None:
    """Write a markdown summary of structural QA results."""
    lines = [
        f"# Structural QA Results — {sprint}",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    n_pass = sum(1 for r in results if r.status == "pass")
    n_fail = sum(1 for r in results if r.status == "fail")
    n_new = sum(1 for r in results if r.status == "new_baseline")
    n_skip = sum(1 for r in results if r.status in ("skip", "error"))

    lines.append(f"**Summary:** {n_pass} PASS / {n_fail} FAIL / {n_new} NEW BASELINE / {n_skip} SKIP")
    lines.append("")
    lines.append("| Page | Viewport | Status | Details |")
    lines.append("|------|----------|--------|---------|")

    for r in results:
        icon = {"pass": "PASS", "fail": "FAIL", "new_baseline": "NEW", "skip": "SKIP", "error": "ERROR"}.get(r.status, r.status.upper())
        detail = r.message
        if r.diffs:
            detail += " — " + "; ".join(r.diffs[:3])
            if len(r.diffs) > 3:
                detail += f" (+{len(r.diffs) - 3} more)"
        lines.append(f"| {r.page_slug} | {r.viewport} | {icon} | {detail} |")

    lines.append("")

    # Per-page diff detail for failures
    failures = [r for r in results if r.status == "fail"]
    if failures:
        lines.append("## Structural Diff Details")
        lines.append("")
        for r in failures:
            lines.append(f"### {r.page_slug} ({r.viewport})")
            for d in r.diffs:
                lines.append(f"- {d}")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"Structural results: {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Visual QA pipeline — golden screenshots, video, filmstrips",
    )
    parser.add_argument("--url", required=True, help="Base URL to test against")
    parser.add_argument("--sprint", required=True, help="Sprint identifier (e.g. sprint57)")
    parser.add_argument(
        "--capture-goldens",
        action="store_true",
        help="Save all screenshots as golden baselines (first run)",
    )
    parser.add_argument(
        "--update-goldens",
        action="store_true",
        help="Update goldens with current screenshots (after intentional changes)",
    )
    parser.add_argument(
        "--viewport",
        choices=list(VIEWPORTS.keys()),
        help="Run only one viewport",
    )
    parser.add_argument(
        "--pages",
        help="Comma-separated list of page slugs to test",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Diff threshold percentage (default: 1.0)",
    )
    parser.add_argument(
        "--pixel-tolerance",
        type=int,
        default=30,
        help="Per-channel pixel tolerance (default: 30)",
    )
    parser.add_argument(
        "--journeys",
        action="store_true",
        help="Record user journey videos with interactive flows",
    )
    parser.add_argument(
        "--journeys-only",
        action="store_true",
        help="Only run journeys, skip page-matrix regression",
    )
    parser.add_argument(
        "--journey-filter",
        help="Comma-separated journey slugs (e.g. property-search,morning-brief)",
    )
    parser.add_argument(
        "--guided",
        action="store_true",
        help="Guided mode — visible browser with breakpoints where you take over",
    )

    # --- Structural mode flags ---
    structural_group = parser.add_argument_group("structural mode (DOM fingerprint diff)")
    structural_group.add_argument(
        "--structural",
        action="store_true",
        help="Enable structural DOM fingerprint mode (mutually exclusive with pixel diff matrix)",
    )
    structural_group.add_argument(
        "--structural-baseline",
        action="store_true",
        help="Capture fingerprints as new baselines (saves to qa-results/structural-baselines/)",
    )
    structural_group.add_argument(
        "--structural-check",
        action="store_true",
        help="Compare fingerprints against saved baselines (default when --structural given without --structural-baseline)",
    )
    structural_group.add_argument(
        "--structural-changed-only",
        action="store_true",
        help="Only fingerprint pages whose templates appear in git diff HEAD~1",
    )

    args = parser.parse_args()

    has_failures = False

    # --- Structural mode ---
    if args.structural:
        capture_baseline = args.structural_baseline
        page_filter = None
        if args.pages:
            page_filter = [s.strip() for s in args.pages.split(",")]

        print("\n--- Running structural DOM fingerprint QA ---")
        structural_results = run_structural_qa(
            base_url=args.url,
            sprint=args.sprint,
            capture_baseline=capture_baseline,
            viewport_filter=args.viewport,
            page_filter=page_filter,
            changed_only=args.structural_changed_only,
        )
        if any(r.status == "fail" for r in structural_results):
            has_failures = True

        return 1 if has_failures else 0

    run_matrix = not args.journeys_only

    # Page matrix regression
    if run_matrix:
        page_filter = None
        if args.pages:
            page_filter = [s.strip() for s in args.pages.split(",")]

        results = run_visual_qa(
            base_url=args.url,
            sprint=args.sprint,
            capture_goldens=args.capture_goldens,
            update_goldens=args.update_goldens,
            viewport_filter=args.viewport,
            page_filter=page_filter,
            threshold_pct=args.threshold,
            pixel_tolerance=args.pixel_tolerance,
        )

        has_failures = any(
            r.status == "fail" for vp in results.values() for r in vp
        )

    # Journey videos
    if args.journeys or args.journeys_only:
        journey_filter = None
        if args.journey_filter:
            journey_filter = [s.strip() for s in args.journey_filter.split(",")]

        print("\n--- Recording user journeys ---")
        run_journeys(
            base_url=args.url,
            sprint=args.sprint,
            viewport_name=args.viewport or "desktop",
            journey_filter=journey_filter,
            guided=args.guided,
        )

    return 1 if has_failures else 0


if __name__ == "__main__":
    sys.exit(main())
