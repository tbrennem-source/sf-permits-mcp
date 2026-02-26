"""Shared helpers for RELAY QA runs with video recording + step markers."""
import json
import os
from datetime import datetime
from pathlib import Path

# Use Railway volume if available, otherwise local
QA_ROOT = Path(os.environ.get("QA_STORAGE_DIR", "qa-results"))
VIDEOS_DIR = QA_ROOT / "videos"
MARKERS_DIR = QA_ROOT / "markers"
SCREENSHOTS_DIR = QA_ROOT / "screenshots"


def create_relay_context(browser, run_name=None):
    """Create a Playwright browser context with video recording enabled.

    Returns (context, page, markers_file) — page is pre-created so video
    starts immediately.
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_name = run_name or f"relay-{timestamp}"

    video_dir = VIDEOS_DIR / run_name
    video_dir.mkdir(parents=True, exist_ok=True)

    screenshot_dir = SCREENSHOTS_DIR / run_name
    screenshot_dir.mkdir(parents=True, exist_ok=True)

    context = browser.new_context(
        record_video_dir=str(video_dir),
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720},
    )

    page = context.new_page()

    # Initialize step markers file
    markers_file = MARKERS_DIR / f"{run_name}.json"
    markers_file.parent.mkdir(parents=True, exist_ok=True)
    markers_file.write_text(
        json.dumps(
            {
                "run_name": run_name,
                "started_at": datetime.now().isoformat(),
                "steps": [],
                "video_dir": str(video_dir),
                "screenshot_dir": str(screenshot_dir),
            },
            indent=2,
        )
    )

    return context, page, markers_file


def mark_step(page, markers_file, step_name, result="PASS", note=""):
    """Record a timestamped step marker. Auto-screenshots on FAIL."""
    data = json.loads(markers_file.read_text())
    elapsed = (
        datetime.now() - datetime.fromisoformat(data["started_at"])
    ).total_seconds()

    step_entry = {
        "step": step_name,
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "result": result,
        "note": note,
        "screenshot": None,
    }

    # Auto-screenshot on FAIL or BLOCKED
    if result in ("FAIL", "BLOCKED"):
        screenshot_dir = Path(data["screenshot_dir"])
        screenshot_path = (
            screenshot_dir / f"{len(data['steps']):02d}-FAIL-{step_name}.png"
        )
        try:
            page.screenshot(path=str(screenshot_path), full_page=True)
            step_entry["screenshot"] = screenshot_path.name
        except Exception as e:
            step_entry["note"] += f" [screenshot failed: {e}]"

    data["steps"].append(step_entry)
    markers_file.write_text(json.dumps(data, indent=2))

    icon = "+" if result == "PASS" else "X" if result == "FAIL" else ">"
    print(
        f"  [{icon}] [{elapsed:6.1f}s] {step_name}: {result}"
        + (f" -- {note}" if note else "")
    )


def close_relay_context(context, markers_file):
    """Close context (finalizes video) and write summary."""
    for page in context.pages:
        page.close()
    context.close()

    data = json.loads(markers_file.read_text())
    data["completed_at"] = datetime.now().isoformat()
    data["total_steps"] = len(data["steps"])
    data["passed"] = sum(1 for s in data["steps"] if s["result"] == "PASS")
    data["failed"] = sum(1 for s in data["steps"] if s["result"] == "FAIL")
    data["blocked"] = sum(1 for s in data["steps"] if s["result"] == "BLOCKED")
    data["duration_seconds"] = round(
        (
            datetime.fromisoformat(data["completed_at"])
            - datetime.fromisoformat(data["started_at"])
        ).total_seconds(),
        1,
    )

    # Find video file path (Playwright names it after the page GUID)
    video_dir = Path(data["video_dir"])
    videos = list(video_dir.glob("*.webm"))
    if videos:
        data["video_file"] = videos[0].name

    markers_file.write_text(json.dumps(data, indent=2))

    print(f"\n{'=' * 60}")
    print(f"RELAY RUN: {data['run_name']}")
    print(f"Duration: {data['duration_seconds']}s")
    print(
        f"Steps: {data['total_steps']} | PASS: {data['passed']}"
        f" | FAIL: {data['failed']} | BLOCKED: {data['blocked']}"
    )
    if videos:
        print(f"Video: {videos[0]}")
    print(f"Markers: {markers_file}")
    if data["failed"] > 0:
        print(f"FAIL screenshots: {data['screenshot_dir']}")
    print(f"{'=' * 60}\n")

    return data
