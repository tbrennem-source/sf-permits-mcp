"""
Tests for scripts/notify.sh

Verifies:
- Script exists and is executable
- All named event types are handled (case statement coverage)
- Unknown event type falls back to default sound
- NOTIFY_ENABLED=0 check is present in the script
"""

import os
import stat
import subprocess
from pathlib import Path

# Absolute path to notify.sh relative to the repo root
REPO_ROOT = Path(__file__).parent.parent
NOTIFY_SH = REPO_ROOT / "scripts" / "notify.sh"


def test_notify_sh_exists():
    """scripts/notify.sh must exist."""
    assert NOTIFY_SH.exists(), f"scripts/notify.sh not found at {NOTIFY_SH}"


def test_notify_sh_is_executable():
    """scripts/notify.sh must be executable."""
    mode = os.stat(NOTIFY_SH).st_mode
    assert bool(mode & stat.S_IXUSR), "scripts/notify.sh is not executable (missing user execute bit)"


def _script_content() -> str:
    return NOTIFY_SH.read_text()


def test_agent_done_event_handled():
    """Case statement must include agent-done."""
    content = _script_content()
    assert "agent-done)" in content, "scripts/notify.sh missing case branch for agent-done"


def test_terminal_done_event_handled():
    """Case statement must include terminal-done."""
    content = _script_content()
    assert "terminal-done)" in content, "scripts/notify.sh missing case branch for terminal-done"


def test_sprint_done_event_handled():
    """Case statement must include sprint-done."""
    content = _script_content()
    assert "sprint-done)" in content, "scripts/notify.sh missing case branch for sprint-done"


def test_qa_fail_event_handled():
    """Case statement must include qa-fail."""
    content = _script_content()
    assert "qa-fail)" in content, "scripts/notify.sh missing case branch for qa-fail"


def test_prod_promoted_event_handled():
    """Case statement must include prod-promoted."""
    content = _script_content()
    assert "prod-promoted)" in content, "scripts/notify.sh missing case branch for prod-promoted"


def test_unknown_event_fallback_exists():
    """Case statement must have a wildcard/default branch for unknown events."""
    content = _script_content()
    # The default case is expressed as *) in bash case statements
    assert "*)" in content, "scripts/notify.sh missing default case branch (*) for unknown events"


def test_notify_enabled_check_present():
    """Script must respect NOTIFY_ENABLED=0 to allow disabling notifications."""
    content = _script_content()
    assert 'NOTIFY_ENABLED' in content, "scripts/notify.sh missing NOTIFY_ENABLED check"
    # Verify it's checking for the disable value
    assert '"0"' in content or "'0'" in content, (
        "scripts/notify.sh NOTIFY_ENABLED check should compare against '0'"
    )


def test_notify_disabled_exits_early():
    """With NOTIFY_ENABLED=0, the script should exit without playing sounds."""
    env = os.environ.copy()
    env["NOTIFY_ENABLED"] = "0"
    result = subprocess.run(
        ["bash", str(NOTIFY_SH), "agent-done", "test"],
        capture_output=True,
        text=True,
        env=env,
        timeout=5,
    )
    # Script should exit 0 silently (no afplay, no osascript called)
    assert result.returncode == 0, f"Expected exit 0 with NOTIFY_ENABLED=0, got {result.returncode}"


def test_afplay_command_present():
    """Script must use afplay for sound playback."""
    content = _script_content()
    assert "afplay" in content, "scripts/notify.sh must use afplay for macOS sound playback"


def test_osascript_notification_present():
    """Script must use osascript for macOS notification center."""
    content = _script_content()
    assert "osascript" in content, "scripts/notify.sh must use osascript for notification center alerts"


def test_all_sounds_are_different():
    """Each event type should have a distinct sound file assigned."""
    content = _script_content()
    # Extract afplay lines from the script
    afplay_lines = [line.strip() for line in content.splitlines() if "afplay" in line and "/System/Library/Sounds/" in line]
    sound_files = []
    for line in afplay_lines:
        # Extract the sound filename
        parts = line.split("/")
        if parts:
            sound = parts[-1].replace(" &", "").strip()
            sound_files.append(sound)
    # We expect at least 5 distinct sounds (one per named event + default)
    unique_sounds = set(sound_files)
    assert len(unique_sounds) >= 5, (
        f"Expected at least 5 distinct sounds, found {len(unique_sounds)}: {unique_sounds}"
    )
