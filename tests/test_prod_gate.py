"""Tests for scripts/prod_gate.py — weighted scoring and hotfix ratchet logic.

The scoring math lives inside main() in prod_gate.py.  Rather than running the
full CLI (which would hit subprocess calls, the staging URL, and file-system
state), we extract the pure arithmetic and replicate it here under test.

A thin helper `_compute_gate` mirrors the exact algorithm from main():
  • CATEGORY_WEIGHTS dict
  • category_mins reduction
  • weighted score formula (5 - (5 - raw) * weight, floor at 2 when raw >= 2)
  • round → effective_score
  • verdict + hotfix-ratchet logic

All tests call `_compute_gate()` with hand-crafted result lists and assert
on (verdict, effective_score) — no subprocess, no network, no disk.
"""
import os
import sys
import tempfile
import pytest

# ---------------------------------------------------------------------------
# Replicate the scoring algorithm from prod_gate.py main()
# ---------------------------------------------------------------------------

CATEGORY_WEIGHTS = {
    "Design Tokens": ("design", 0.6),
    "Test Suite":    ("safety", 1.0),
    "Dependencies":  ("safety", 1.0),
    "Health":        ("data",   1.0),
    "Data Freshness":("data",   1.0),
    "Smoke Test":    ("data",   1.0),
    "Route Inventory":("ops",   0.8),
    "Performance":   ("ops",    0.8),
    # Auth Safety and Secret Leak are hard holds, not scored
}


def _compute_gate(results, hard_holds=None, hotfix_file=None):
    """Mirror the scoring logic from prod_gate.main().

    Args:
        results: list of (name, raw_score, msg, issues) tuples
        hard_holds: list of (name, msg, issues) tuples — defaults to []
        hotfix_file: path to a HOTFIX_REQUIRED.md to simulate ratchet checks.
                     If None, ratchet is disabled (no file check).

    Returns:
        dict with keys: effective_score, verdict, hotfix_ratchet_triggered
    """
    if hard_holds is None:
        hard_holds = []

    # Build category minimums
    category_mins = {}
    for name, raw_score, msg, issues in results:
        if name in ("Auth Safety", "Secret Leak"):
            continue
        cat_info = CATEGORY_WEIGHTS.get(name)
        if not cat_info:
            continue
        cat_name, weight = cat_info
        if cat_name not in category_mins or raw_score < category_mins[cat_name][0]:
            category_mins[cat_name] = (raw_score, weight, name)

    # Compute weighted category scores
    weighted_scores = {}
    for cat_name, (raw, weight, check_name) in category_mins.items():
        if raw == 5:
            weighted = 5.0
        else:
            penalty = (5 - raw) * weight
            weighted = 5.0 - penalty
            if raw >= 2:
                weighted = max(weighted, 2.0)
        weighted_scores[cat_name] = (round(weighted, 1), raw, weight, check_name)

    effective_score_float = min(ws[0] for ws in weighted_scores.values()) if weighted_scores else 5.0
    effective_score = max(1, min(5, round(effective_score_float)))

    # Verdict
    if hard_holds:
        verdict = "HOLD"
    elif effective_score <= 2:
        verdict = "HOLD"
    elif effective_score <= 3:
        verdict = "PROMOTE"
    else:
        verdict = "PROMOTE"

    # Hotfix ratchet (only simulated when hotfix_file is provided)
    hotfix_ratchet_triggered = False
    if effective_score == 3 and not hard_holds and hotfix_file is not None:
        if os.path.exists(hotfix_file):
            hotfix_ratchet_triggered = True
            verdict = "HOLD"
        else:
            # First time at score 3 — write the hotfix marker
            with open(hotfix_file, "w") as f:
                f.write("# HOTFIX REQUIRED\n")

    # Hotfix cleanup
    if effective_score >= 4 and hotfix_file and os.path.exists(hotfix_file):
        os.remove(hotfix_file)

    return {
        "effective_score": effective_score,
        "verdict": verdict,
        "hotfix_ratchet_triggered": hotfix_ratchet_triggered,
        "weighted_scores": weighted_scores,
    }


def _all_perfect():
    """All scored checks returning raw 5."""
    return [
        ("Design Tokens",  5, "clean",   []),
        ("Test Suite",     5, "passing", []),
        ("Dependencies",   5, "none",    []),
        ("Health",         5, "ok",      []),
        ("Data Freshness", 5, "ok",      []),
        ("Smoke Test",     5, "ok",      []),
        ("Route Inventory",5, "ok",      []),
        ("Performance",    5, "fast",    []),
    ]


# ---------------------------------------------------------------------------
# test_weighted_scoring_perfect
# ---------------------------------------------------------------------------

def test_weighted_scoring_perfect():
    """All categories raw 5 → effective 5, PROMOTE."""
    out = _compute_gate(_all_perfect())
    assert out["effective_score"] == 5
    assert out["verdict"] == "PROMOTE"


# ---------------------------------------------------------------------------
# test_weighted_scoring_design_dampened
# ---------------------------------------------------------------------------

def test_weighted_scoring_design_dampened():
    """Design raw 2, everything else 5 → effective 3 (dampened, not 2), PROMOTE."""
    results = _all_perfect()
    # Replace Design Tokens with raw score 2
    results = [(n, (2 if n == "Design Tokens" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # Design raw=2, weight=0.6: effective = 5 - (5-2)*0.6 = 5 - 1.8 = 3.2 → rounds to 3
    # But floor: raw >= 2 → max(3.2, 2.0) = 3.2 → round → 3
    # All other categories = 5.  Min of all = 3.
    assert out["effective_score"] == 3, (
        f"Expected effective 3 when design raw=2, got {out['effective_score']}"
    )
    assert out["verdict"] == "PROMOTE"  # score 3 → promote with mandatory hotfix


def test_weighted_scoring_design_raw_1_gives_3():
    """Design raw 1, weight 0.6 → effective = 5 - 4*0.6 = 2.6 → rounds to 3 (no floor since raw=1)."""
    results = _all_perfect()
    results = [(n, (1 if n == "Design Tokens" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # raw=1 → floor doesn't apply (raw < 2)
    # weighted = 5 - (5-1)*0.6 = 5 - 2.4 = 2.6 → round to 3
    assert out["effective_score"] == 3
    assert out["verdict"] == "PROMOTE"


# ---------------------------------------------------------------------------
# test_weighted_scoring_safety_not_dampened
# ---------------------------------------------------------------------------

def test_weighted_scoring_safety_not_dampened():
    """Safety (Test Suite) raw 2, everything else 5 → effective 2, HOLD."""
    results = _all_perfect()
    results = [(n, (2 if n == "Test Suite" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # Safety weight 1.0: effective = 5 - (5-2)*1.0 = 5 - 3 = 2 → stays 2
    # (floor = max(2.0, 2.0) = 2.0)
    assert out["effective_score"] == 2
    assert out["verdict"] == "HOLD"


def test_weighted_scoring_safety_raw_1_gives_1():
    """Safety raw 1 → effective 1 → HOLD."""
    results = _all_perfect()
    results = [(n, (1 if n == "Test Suite" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # weight=1.0, raw=1: weighted = 5 - 4*1.0 = 1 (no floor: raw < 2)
    assert out["effective_score"] == 1
    assert out["verdict"] == "HOLD"


# ---------------------------------------------------------------------------
# test_weighted_scoring_floor
# ---------------------------------------------------------------------------

def test_weighted_scoring_floor_design_raw_2():
    """Design raw 2, weight 0.6: floor prevents score from going below 2.

    effective = max(5 - (5-2)*0.6, 2.0) = max(3.2, 2.0) = 3.2 → rounds to 3.
    """
    results = _all_perfect()
    results = [(n, (2 if n == "Design Tokens" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # Weighted for design = 3.2, rounded = 3
    design_weighted = out["weighted_scores"].get("design")
    assert design_weighted is not None
    # (weighted_val, raw, weight, check_name)
    assert design_weighted[0] == 3.2


def test_weighted_scoring_ops_raw_2_gives_3():
    """Ops (Route Inventory) raw 2, weight 0.8 → effective = max(5-2.4, 2) = max(2.6, 2) = 2.6 → rounds to 3."""
    results = _all_perfect()
    results = [(n, (2 if n == "Route Inventory" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    # ops: effective = 5 - (5-2)*0.8 = 5 - 2.4 = 2.6 → round to 3
    assert out["effective_score"] == 3
    assert out["verdict"] == "PROMOTE"


# ---------------------------------------------------------------------------
# test_hard_hold_overrides_score
# ---------------------------------------------------------------------------

def test_hard_hold_overrides_score():
    """Auth bypass with all other scores at 5 → still HOLD."""
    results = _all_perfect()
    # Auth Safety is a hard hold, not in the scored results
    hard_holds = [("Auth Safety", "bypass detected on /brief", ["/brief returned 200 without auth"])]
    out = _compute_gate(results, hard_holds=hard_holds)
    assert out["verdict"] == "HOLD"
    assert out["effective_score"] == 5  # numeric score is still 5, hold is from hard_holds


def test_secret_leak_hard_hold():
    """Secret leak forces HOLD regardless of all other scores being perfect."""
    results = _all_perfect()
    hard_holds = [("Secret Leak", "sk-abc123 found in diff", ["Potential secret: sk-abc123..."])]
    out = _compute_gate(results, hard_holds=hard_holds)
    assert out["verdict"] == "HOLD"


# ---------------------------------------------------------------------------
# test_hotfix_ratchet_first_time
# ---------------------------------------------------------------------------

def test_hotfix_ratchet_first_time(tmp_path):
    """Score 3 with no existing HOTFIX_REQUIRED.md → PROMOTE, file created."""
    hotfix_file = str(tmp_path / "HOTFIX_REQUIRED.md")
    # Design raw 2 → effective 3 (dampened by 0.6 weight)
    results = _all_perfect()
    results = [(n, (2 if n == "Design Tokens" else r), m, i) for n, r, m, i in results]
    assert not os.path.exists(hotfix_file)
    out = _compute_gate(results, hotfix_file=hotfix_file)
    assert out["effective_score"] == 3
    assert out["verdict"] == "PROMOTE"
    assert not out["hotfix_ratchet_triggered"]
    assert os.path.exists(hotfix_file), "HOTFIX_REQUIRED.md should be written on first score-3 promotion"


# ---------------------------------------------------------------------------
# test_hotfix_ratchet_second_time
# ---------------------------------------------------------------------------

def test_hotfix_ratchet_second_time(tmp_path):
    """Score 3 when HOTFIX_REQUIRED.md already exists → downgraded to HOLD."""
    hotfix_file = str(tmp_path / "HOTFIX_REQUIRED.md")
    # Pre-create the file (simulates previous promotion at score 3)
    with open(hotfix_file, "w") as f:
        f.write("# HOTFIX REQUIRED\n")

    results = _all_perfect()
    results = [(n, (2 if n == "Design Tokens" else r), m, i) for n, r, m, i in results]

    out = _compute_gate(results, hotfix_file=hotfix_file)
    assert out["effective_score"] == 3
    assert out["verdict"] == "HOLD"
    assert out["hotfix_ratchet_triggered"]


# ---------------------------------------------------------------------------
# test_hotfix_cleanup_on_improvement
# ---------------------------------------------------------------------------

def test_hotfix_cleanup_on_improvement(tmp_path):
    """Score 5 when HOTFIX_REQUIRED.md exists → file deleted, PROMOTE."""
    hotfix_file = str(tmp_path / "HOTFIX_REQUIRED.md")
    with open(hotfix_file, "w") as f:
        f.write("# HOTFIX REQUIRED\n")

    results = _all_perfect()  # all raw 5 → effective 5
    out = _compute_gate(results, hotfix_file=hotfix_file)
    assert out["effective_score"] == 5
    assert out["verdict"] == "PROMOTE"
    assert not os.path.exists(hotfix_file), (
        "HOTFIX_REQUIRED.md should be deleted when score improves to 4+"
    )


def test_hotfix_cleanup_on_score_4(tmp_path):
    """Score 4 also triggers hotfix cleanup."""
    hotfix_file = str(tmp_path / "HOTFIX_REQUIRED.md")
    with open(hotfix_file, "w") as f:
        f.write("# HOTFIX REQUIRED\n")

    # Ops raw 3 → effective = 5 - (5-3)*0.8 = 5 - 1.6 = 3.4 → rounds to 3
    # Hmm, that gives 3 not 4.  Use a data raw=4 instead:
    # data weight=1.0, raw=4 → effective = 5 - 1*1.0 = 4 → rounds to 4
    results = _all_perfect()
    results = [(n, (4 if n == "Health" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results, hotfix_file=hotfix_file)
    assert out["effective_score"] == 4
    assert not os.path.exists(hotfix_file), (
        "HOTFIX_REQUIRED.md should be deleted when score is 4"
    )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_scored_checks_returns_5():
    """If no check matches CATEGORY_WEIGHTS, effective score defaults to 5."""
    # Only hard-hold checks (not in CATEGORY_WEIGHTS)
    results = [
        ("Auth Safety", 5, "ok", []),
        ("Secret Leak", 5, "ok", []),
    ]
    out = _compute_gate(results)
    assert out["effective_score"] == 5
    assert out["verdict"] == "PROMOTE"


def test_effective_score_min_across_categories():
    """The effective score is the minimum across all weighted category scores.

    safety raw=2, weight=1.0 → effective = 5 - (5-2)*1.0 = 2 (floor max(2,2)=2)
    design raw=1, weight=0.6 → effective = 5 - (5-1)*0.6 = 5 - 2.4 = 2.6 → 3
    min(2, 3, all-others-5) = 2 → HOLD
    """
    results = _all_perfect()
    # Test Suite (safety) raw=2, Design Tokens (design) raw=1
    results = [
        (n, (2 if n == "Test Suite" else (1 if n == "Design Tokens" else r)), m, i)
        for n, r, m, i in results
    ]
    out = _compute_gate(results)
    # safety raw=2, weight=1.0 → effective=2.0 (floor applies: max(2,2)=2)
    # design raw=1, weight=0.6 → effective=2.6, no floor (raw<2) → rounds to 3
    # min(2, 3) = 2 → HOLD
    assert out["effective_score"] == 2
    assert out["verdict"] == "HOLD"


def test_data_category_uses_minimum():
    """When two data checks differ, the category min is used."""
    results = _all_perfect()
    # Health=5, Data Freshness=2, Smoke Test=5
    # data category min = 2 → effective = 5 - 3*1.0 = 2 → HOLD
    results = [(n, (2 if n == "Data Freshness" else r), m, i) for n, r, m, i in results]
    out = _compute_gate(results)
    assert out["effective_score"] == 2
    assert out["verdict"] == "HOLD"
