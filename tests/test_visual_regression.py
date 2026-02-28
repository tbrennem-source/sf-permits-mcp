"""Tests for scripts/visual_qa.py structural mode.

All tests are Playwright-free and server-free — they mock page.evaluate()
or work with serialised fingerprint dicts directly.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SAMPLE_FINGERPRINT: dict = {
    "body_classes": ["obsidian", "page-landing"],
    "container_classes": ["obs-container"],
    "component_counts": {
        "glass_card": 3,
        "obs_table": 1,
        "nav": 1,
        "footer": 1,
        "ghost_cta": 2,
        "form": 0,
        "status_dot": 0,
    },
    "htmx_presence": {
        "hx_get": True,
        "hx_post": False,
        "hx_target": True,
        "hx_swap": False,
    },
    "viewport_overflow": False,
    "centered": True,
}


def _make_page_mock(fingerprint: dict | None = None) -> MagicMock:
    """Return a mock Playwright page whose evaluate() returns `fingerprint`."""
    page = MagicMock()
    page.evaluate.return_value = fingerprint if fingerprint is not None else SAMPLE_FINGERPRINT.copy()
    return page


# ---------------------------------------------------------------------------
# 1. get_page_fingerprint — mocked page.evaluate
# ---------------------------------------------------------------------------

def test_get_page_fingerprint_returns_dict():
    """get_page_fingerprint should return the dict produced by page.evaluate."""
    from scripts.visual_qa import get_page_fingerprint

    page = _make_page_mock(SAMPLE_FINGERPRINT.copy())
    result = get_page_fingerprint(page)

    assert isinstance(result, dict)
    assert result["body_classes"] == ["obsidian", "page-landing"]
    assert result["component_counts"]["glass_card"] == 3
    assert result["htmx_presence"]["hx_get"] is True


def test_get_page_fingerprint_propagates_evaluate_error():
    """If page.evaluate raises, get_page_fingerprint should propagate the exception."""
    from scripts.visual_qa import get_page_fingerprint

    page = MagicMock()
    page.evaluate.side_effect = RuntimeError("JS execution failed")

    with pytest.raises(RuntimeError, match="JS execution failed"):
        get_page_fingerprint(page)


def test_get_page_fingerprint_calls_evaluate_once():
    """get_page_fingerprint should call page.evaluate exactly once."""
    from scripts.visual_qa import get_page_fingerprint

    page = _make_page_mock()
    get_page_fingerprint(page)
    page.evaluate.assert_called_once()


# ---------------------------------------------------------------------------
# 2. diff_fingerprints — structural change detection
# ---------------------------------------------------------------------------

def test_diff_fingerprints_identical_is_empty():
    """Identical fingerprints should produce no diffs."""
    from scripts.visual_qa import diff_fingerprints

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, SAMPLE_FINGERPRINT.copy())
    assert diffs == []


def test_diff_fingerprints_body_class_added():
    """Adding a CSS class to body should appear in diffs."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["body_classes"].append("new-class")

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert any("body_classes added" in d and "new-class" in d for d in diffs)


def test_diff_fingerprints_body_class_removed():
    """Removing a CSS class from body should appear in diffs."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["body_classes"] = [c for c in current["body_classes"] if c != "obsidian"]

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert any("body_classes removed" in d and "obsidian" in d for d in diffs)


def test_diff_fingerprints_component_count_changed():
    """A changed component count (e.g., glass-card: 3 → 5) should be detected."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["component_counts"]["glass_card"] = 5

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert any("component_counts.glass_card" in d and "3" in d and "5" in d for d in diffs)


def test_diff_fingerprints_htmx_presence_changed():
    """A changed HTMX boolean should appear in diffs."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["htmx_presence"]["hx_post"] = True  # baseline is False

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert any("htmx_presence.hx_post" in d for d in diffs)


def test_diff_fingerprints_viewport_overflow_changed():
    """viewport_overflow flipping should be detected."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["viewport_overflow"] = True  # baseline is False

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert any("viewport_overflow" in d for d in diffs)


def test_diff_fingerprints_multiple_changes_all_reported():
    """All independent structural changes should be reported in the same call."""
    from scripts.visual_qa import diff_fingerprints

    current = json.loads(json.dumps(SAMPLE_FINGERPRINT))
    current["body_classes"].append("extra-class")
    current["component_counts"]["nav"] = 0  # removed nav
    current["viewport_overflow"] = True

    diffs = diff_fingerprints(SAMPLE_FINGERPRINT, current)
    assert len(diffs) >= 3  # at least three distinct diff lines


# ---------------------------------------------------------------------------
# 3. slugs_for_changed_files — template-to-slug mapping
# ---------------------------------------------------------------------------

def test_slugs_for_changed_files_known_template():
    """A changed landing template should map to the 'landing' slug."""
    from scripts.visual_qa import slugs_for_changed_files

    slugs = slugs_for_changed_files(["web/templates/landing.html"])
    assert "landing" in slugs


def test_slugs_for_changed_files_admin_template():
    """A changed admin/feedback template should map to 'admin-feedback'."""
    from scripts.visual_qa import slugs_for_changed_files

    slugs = slugs_for_changed_files(["web/templates/admin/feedback.html"])
    assert "admin-feedback" in slugs


def test_slugs_for_changed_files_shared_template_returns_all():
    """Changing a shared layout template (base.html) should return ALL page slugs."""
    from scripts.visual_qa import slugs_for_changed_files, PAGES

    slugs = slugs_for_changed_files(["web/templates/base.html"])
    all_slugs = {p["slug"] for p in PAGES}
    # All pages must be included
    assert all_slugs.issubset(set(slugs))


def test_slugs_for_changed_files_css_returns_all():
    """Changing a shared CSS file should return ALL page slugs."""
    from scripts.visual_qa import slugs_for_changed_files, PAGES

    slugs = slugs_for_changed_files(["web/static/css/obsidian.css"])
    all_slugs = {p["slug"] for p in PAGES}
    assert all_slugs.issubset(set(slugs))


def test_slugs_for_changed_files_unknown_returns_empty():
    """A non-template file (e.g., Python module) should return no slugs."""
    from scripts.visual_qa import slugs_for_changed_files

    slugs = slugs_for_changed_files(["src/server.py", "tests/test_something.py"])
    assert slugs == []


def test_slugs_for_changed_files_empty_input_returns_empty():
    """Empty changed-files list should return no slugs."""
    from scripts.visual_qa import slugs_for_changed_files

    slugs = slugs_for_changed_files([])
    assert slugs == []


# ---------------------------------------------------------------------------
# 4. Baseline save / load round-trip
# ---------------------------------------------------------------------------

def test_baseline_round_trip(tmp_path: Path):
    """A fingerprint saved to JSON and reloaded should be identical."""
    fp = SAMPLE_FINGERPRINT.copy()
    baseline_file = tmp_path / "landing-desktop.json"
    baseline_file.write_text(json.dumps(fp, indent=2))

    reloaded = json.loads(baseline_file.read_text())
    assert reloaded == fp


def test_baseline_round_trip_diff_is_empty(tmp_path: Path):
    """After a round-trip, diffing baseline against itself should produce no diffs."""
    from scripts.visual_qa import diff_fingerprints

    fp = SAMPLE_FINGERPRINT.copy()
    baseline_file = tmp_path / "landing-desktop.json"
    baseline_file.write_text(json.dumps(fp, indent=2))

    reloaded = json.loads(baseline_file.read_text())
    diffs = diff_fingerprints(fp, reloaded)
    assert diffs == []


def test_baseline_captures_all_fingerprint_keys(tmp_path: Path):
    """Saved baseline JSON must contain all expected top-level keys."""
    fp = SAMPLE_FINGERPRINT.copy()
    baseline_file = tmp_path / "search-mobile.json"
    baseline_file.write_text(json.dumps(fp, indent=2))

    reloaded = json.loads(baseline_file.read_text())
    required_keys = {
        "body_classes", "container_classes", "component_counts",
        "htmx_presence", "viewport_overflow", "centered",
    }
    assert required_keys.issubset(set(reloaded.keys()))
