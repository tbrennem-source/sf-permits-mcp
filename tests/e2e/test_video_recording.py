"""Validate RELAY video recording produces playable artifacts + markers.

Run with: python -m pytest tests/e2e/test_video_recording.py -v
Requires: playwright installed (pip install -e ".[dev]" && playwright install chromium)
"""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from relay_helpers import create_relay_context, mark_step, close_relay_context  # noqa: E402

TARGET = os.environ.get(
    "E2E_BASE_URL", "https://sfpermits-ai-staging-production.up.railway.app"
)

# Skip if playwright not installed or no target configured
try:
    from playwright.sync_api import sync_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False


@pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="playwright not installed")
def test_video_recording_full_pipeline(tmp_path, monkeypatch):
    """End-to-end: record video, mark steps (including a deliberate FAIL),
    verify all artifacts."""
    # Use tmp_path so test artifacts don't pollute the repo
    monkeypatch.setenv("QA_STORAGE_DIR", str(tmp_path))
    # Re-import to pick up new env var
    import importlib
    import tests.e2e.relay_helpers as rh

    importlib.reload(rh)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context, page, markers_file = rh.create_relay_context(
            browser, run_name="validation-test"
        )

        # Step 1: Landing page loads
        page.goto(TARGET, timeout=30000)
        page.wait_for_load_state("networkidle")
        rh.mark_step(
            page,
            markers_file,
            "landing-page-loads",
            "PASS" if page.title() else "FAIL",
        )

        # Step 2: Search box present
        search = page.query_selector(
            "input[name='q'], input[type='search'], input[type='text']"
        )
        rh.mark_step(
            page,
            markers_file,
            "search-box-present",
            "PASS" if search else "FAIL",
        )

        # Step 3: Health endpoint
        page.goto(f"{TARGET}/health", timeout=15000)
        page.wait_for_load_state("networkidle")
        content = page.content()
        rh.mark_step(
            page,
            markers_file,
            "health-endpoint-ok",
            "PASS"
            if "ok" in content.lower() or "status" in content.lower()
            else "FAIL",
        )

        # Step 4: Deliberate FAIL to test screenshot capture
        page.goto(f"{TARGET}/this-page-does-not-exist-404", timeout=15000)
        page.wait_for_load_state("networkidle")
        rh.mark_step(
            page,
            markers_file,
            "deliberate-404-fail",
            "FAIL",
            note="Intentional failure to validate screenshot capture",
        )

        # Step 5: Back to landing (proves video continues after failure)
        page.goto(TARGET, timeout=15000)
        page.wait_for_load_state("networkidle")
        rh.mark_step(page, markers_file, "recovery-after-fail", "PASS")

        # Finalize
        summary = rh.close_relay_context(context, markers_file)
        browser.close()

    # --- Artifact assertions ---

    # Video exists and is substantial
    video_dir = Path(summary["video_dir"])
    videos = list(video_dir.glob("*.webm"))
    assert len(videos) >= 1, "No .webm video files produced"
    assert videos[0].stat().st_size > 5000, (
        f"Video too small ({videos[0].stat().st_size} bytes)"
    )

    # Markers are complete
    data = json.loads(markers_file.read_text())
    assert data["total_steps"] == 5, f"Expected 5 steps, got {data['total_steps']}"
    assert data["passed"] >= 3, f"Expected 3+ PASS, got {data['passed']}"
    assert data["failed"] >= 1, f"Expected 1+ FAIL (deliberate), got {data['failed']}"
    assert data.get("completed_at"), "Missing completed_at"
    assert data.get("duration_seconds", 0) > 0, "Duration should be positive"
    assert data.get("video_file"), "Missing video_file in markers"

    # Failure screenshot exists
    fail_steps = [s for s in data["steps"] if s["result"] == "FAIL"]
    assert any(s.get("screenshot") for s in fail_steps), (
        "FAIL step should have a screenshot"
    )
    screenshot_dir = Path(data["screenshot_dir"])
    screenshots = list(screenshot_dir.glob("*.png"))
    assert len(screenshots) >= 1, "No failure screenshots captured"
    assert screenshots[0].stat().st_size > 1000, "Screenshot too small"

    # Elapsed times are monotonically increasing
    times = [s["elapsed_seconds"] for s in data["steps"]]
    assert all(times[i] <= times[i + 1] for i in range(len(times) - 1)), (
        f"Step times not monotonically increasing: {times}"
    )

    print(f"\nFull pipeline validation PASSED")
    print(f"   Video: {videos[0].name} ({videos[0].stat().st_size / 1024:.0f} KB)")
    print(f"   Screenshots: {len(screenshots)} failure captures")
    print(f"   Steps: {data['total_steps']} ({data['passed']}P / {data['failed']}F)")
