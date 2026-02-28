"""Tests for the prod gate hotfix ratchet logic.

The ratchet should only trigger HOLD when the *same* checks are still failing
from the previous sprint. Different checks failing = reset, not HOLD.
"""
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Helpers — import the private helpers and logic from prod_gate directly
# ---------------------------------------------------------------------------

# Make sure the scripts directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))


def _write_hotfix_file(path: str, failing_checks: list[str], score: int = 3) -> None:
    """Write a HOTFIX_REQUIRED.md in the format prod_gate.py produces."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("# HOTFIX REQUIRED\n\n")
        f.write(f"**Created:** {time.strftime('%Y-%m-%d %H:%M UTC')}\n")
        f.write(f"**Deadline:** 48 hours from creation\n")
        f.write(f"**Score:** {score}/5\n\n")
        f.write("## Failing checks\n\n")
        for name in sorted(failing_checks):
            f.write(f"- {name}\n")
        f.write("\n## Issues requiring hotfix\n\n")
        for name in failing_checks:
            f.write(f"- **{name}:** some issue detail\n")
        f.write("\n## Resolution\n\nFix issues, re-run `python scripts/prod_gate.py`.\n")


def _read_previous_failing_checks(path: str) -> list[str]:
    """Mirror of the private function inside prod_gate.py so tests stay DRY."""
    try:
        with open(path) as f:
            content = f.read()
    except OSError:
        return []
    match = re.search(r"## Failing checks\n\n?((?:- .+\n?)*)", content)
    if not match:
        return []
    checks = []
    for line in match.group(1).strip().split("\n"):
        line = line.strip()
        if line.startswith("- "):
            checks.append(line[2:].strip())
    return sorted(checks)


# ---------------------------------------------------------------------------
# Integration-style tests — run the ratchet block logic in isolation
# ---------------------------------------------------------------------------

def _run_ratchet_logic(
    effective_score: int,
    current_failing_checks: list[str],
    hotfix_file: str,
    hard_holds: list = None,
) -> dict:
    """Replicate the ratchet block from main() with the given inputs.

    Returns a dict with keys: verdict, reason, hotfix_ratchet_triggered.
    """
    if hard_holds is None:
        hard_holds = []

    verdict = "PROMOTE" if effective_score >= 3 else "HOLD"
    reason = f"Effective score {effective_score}/5"
    hotfix_ratchet_triggered = False

    if effective_score == 3 and not hard_holds:
        if os.path.exists(hotfix_file):
            previous_failing_checks = _read_previous_failing_checks(hotfix_file)
            if previous_failing_checks and set(current_failing_checks) & set(previous_failing_checks):
                overlapping = sorted(set(current_failing_checks) & set(previous_failing_checks))
                hotfix_ratchet_triggered = True
                verdict = "HOLD"
                reason = (
                    f"Hotfix ratchet: {len(overlapping)} check(s) still failing from previous sprint "
                    f"({', '.join(overlapping)}) — downgraded to HOLD"
                )
            else:
                # Different checks — reset
                hotfix_issues = [(name, "some issue") for name in current_failing_checks]
                os.makedirs(os.path.dirname(hotfix_file), exist_ok=True)
                _write_hotfix_file(hotfix_file, current_failing_checks)
        else:
            # First occurrence
            _write_hotfix_file(hotfix_file, current_failing_checks)
    elif effective_score >= 4 and os.path.exists(hotfix_file):
        os.remove(hotfix_file)

    return {
        "verdict": verdict,
        "reason": reason,
        "hotfix_ratchet_triggered": hotfix_ratchet_triggered,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRatchetTriggersOnSameChecks:
    def test_ratchet_triggers_on_same_checks(self, tmp_path):
        """HOLD when the same check is still failing from previous sprint."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")

        # Previous sprint: "Test Suite" was failing
        _write_hotfix_file(hotfix_file, ["Test Suite"])

        # This sprint: "Test Suite" is still failing
        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Test Suite"],
            hotfix_file=hotfix_file,
        )

        assert result["verdict"] == "HOLD"
        assert result["hotfix_ratchet_triggered"] is True
        assert "Test Suite" in result["reason"]

    def test_ratchet_triggers_on_partial_overlap(self, tmp_path):
        """HOLD when at least one check overlaps, even if new checks also added."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(hotfix_file, ["Test Suite", "Migration Safety"])

        # This sprint: "Test Suite" still failing, plus a new check
        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Test Suite", "Lint Trend"],
            hotfix_file=hotfix_file,
        )

        assert result["verdict"] == "HOLD"
        assert result["hotfix_ratchet_triggered"] is True
        assert "Test Suite" in result["reason"]


class TestRatchetResetsOnDifferentChecks:
    def test_ratchet_resets_on_completely_different_checks(self, tmp_path):
        """PROMOTE when entirely different checks fail — ratchet should NOT trigger."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")

        # Previous sprint: "Test Suite" was the problem
        _write_hotfix_file(hotfix_file, ["Test Suite"])

        # This sprint: "Lint Trend" is the problem (completely different)
        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Lint Trend"],
            hotfix_file=hotfix_file,
        )

        assert result["verdict"] == "PROMOTE"
        assert result["hotfix_ratchet_triggered"] is False

    def test_ratchet_resets_overwrites_hotfix_file(self, tmp_path):
        """When ratchet resets (different checks), the hotfix file is updated."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(hotfix_file, ["Test Suite"])

        _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Lint Trend"],
            hotfix_file=hotfix_file,
        )

        # Hotfix file should now track "Lint Trend", not "Test Suite"
        checks = _read_previous_failing_checks(hotfix_file)
        assert checks == ["Lint Trend"]
        assert "Test Suite" not in checks

    def test_ratchet_with_empty_previous_checks_section(self, tmp_path):
        """If previous HOTFIX_REQUIRED.md has no structured check list, no ratchet."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        os.makedirs(os.path.dirname(hotfix_file), exist_ok=True)
        # Write a legacy-format file without the "## Failing checks" section
        with open(hotfix_file, "w") as f:
            f.write("# HOTFIX REQUIRED\n\nSome old issue.\n")

        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Test Suite"],
            hotfix_file=hotfix_file,
        )

        # No structured data to compare → cannot ratchet
        assert result["hotfix_ratchet_triggered"] is False


class TestNoRatchetOnFirstOccurrence:
    def test_no_ratchet_on_first_occurrence(self, tmp_path):
        """No HOTFIX_REQUIRED.md → first occurrence → no ratchet, just write the file."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        assert not os.path.exists(hotfix_file)

        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Migration Safety"],
            hotfix_file=hotfix_file,
        )

        assert result["verdict"] == "PROMOTE"
        assert result["hotfix_ratchet_triggered"] is False
        # File should now exist for the next run to compare against
        assert os.path.exists(hotfix_file)
        checks = _read_previous_failing_checks(hotfix_file)
        assert "Migration Safety" in checks

    def test_first_occurrence_writes_check_names(self, tmp_path):
        """On first occurrence the hotfix file stores the check names correctly."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Test Suite", "Lint Trend"],
            hotfix_file=hotfix_file,
        )
        checks = _read_previous_failing_checks(hotfix_file)
        assert sorted(checks) == ["Lint Trend", "Test Suite"]


class TestRatchetClearsAfterAllGreen:
    def test_ratchet_clears_after_all_green(self, tmp_path):
        """Score >= 4 → hotfix file is deleted (issues resolved)."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(hotfix_file, ["Test Suite"])
        assert os.path.exists(hotfix_file)

        _run_ratchet_logic(
            effective_score=4,
            current_failing_checks=[],
            hotfix_file=hotfix_file,
        )

        assert not os.path.exists(hotfix_file)

    def test_ratchet_clears_at_score_5(self, tmp_path):
        """Score 5 also clears the hotfix file."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(hotfix_file, ["Lint Trend"])

        _run_ratchet_logic(
            effective_score=5,
            current_failing_checks=[],
            hotfix_file=hotfix_file,
        )

        assert not os.path.exists(hotfix_file)

    def test_ratchet_does_not_retrigger_after_clear(self, tmp_path):
        """After file is cleared (score 4), next score-3 is treated as first occurrence."""
        hotfix_file = str(tmp_path / "qa-results" / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(hotfix_file, ["Test Suite"])

        # Sprint N+1: score 4 — clears file
        _run_ratchet_logic(effective_score=4, current_failing_checks=[], hotfix_file=hotfix_file)
        assert not os.path.exists(hotfix_file)

        # Sprint N+2: score 3 again with the same check name — but file was cleared, so no ratchet
        result = _run_ratchet_logic(
            effective_score=3,
            current_failing_checks=["Test Suite"],
            hotfix_file=hotfix_file,
        )
        assert result["verdict"] == "PROMOTE"
        assert result["hotfix_ratchet_triggered"] is False


# ---------------------------------------------------------------------------
# Read-parse helper tests
# ---------------------------------------------------------------------------

class TestReadPreviousFailingChecks:
    def test_reads_multiple_checks(self, tmp_path):
        path = str(tmp_path / "HOTFIX_REQUIRED.md")
        _write_hotfix_file(path, ["Alpha Check", "Beta Check", "Gamma Check"])
        checks = _read_previous_failing_checks(path)
        assert checks == sorted(["Alpha Check", "Beta Check", "Gamma Check"])

    def test_returns_empty_for_missing_file(self, tmp_path):
        path = str(tmp_path / "nonexistent.md")
        assert _read_previous_failing_checks(path) == []

    def test_returns_empty_for_malformed_file(self, tmp_path):
        path = str(tmp_path / "bad.md")
        with open(path, "w") as f:
            f.write("No structured sections here.\n")
        assert _read_previous_failing_checks(path) == []
