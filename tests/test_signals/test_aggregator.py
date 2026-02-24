"""Tests for src.signals.aggregator — tier derivation + HIGH_RISK logic.

MUST test all tier derivation cases per the spec:
- on_track: no signals
- slower: only 'slower' severity signals
- behind: 'behind' severity signal(s)
- at_risk: single at_risk signal
- high_risk: 2+ unique compounding types at at_risk
- NOT high_risk: 2 at_risk from same type, or non-compounding types
"""

import pytest
from src.signals.types import Signal, COMPOUNDING_TYPES
from src.signals.aggregator import compute_property_health


def _sig(signal_type: str, severity: str, permit: str | None = None) -> Signal:
    """Convenience helper to create a Signal."""
    return Signal(
        signal_type=signal_type,
        severity=severity,
        permit_number=permit,
        block_lot="0001/001",
        detail=f"test {signal_type}",
    )


# ── on_track ─────────────────────────────────────────────────────

class TestOnTrack:
    def test_no_signals(self):
        h = compute_property_health("0001/001", [])
        assert h.tier == "on_track"
        assert h.signal_count == 0
        assert h.at_risk_count == 0

    def test_non_risk_severity_only(self):
        """Signals with no recognized risk severity → on_track."""
        h = compute_property_health("0001/001", [
            _sig("expired_otc", "info"),
        ])
        assert h.tier == "on_track"

    def test_multiple_non_risk(self):
        h = compute_property_health("0001/001", [
            _sig("expired_otc", "info"),
            _sig("expired_otc", "info", "P2"),
        ])
        assert h.tier == "on_track"
        assert h.signal_count == 2


# ── slower ───────────────────────────────────────────────────────

class TestSlower:
    def test_single_slower(self):
        h = compute_property_health("0001/001", [
            _sig("complaint", "slower"),
        ])
        assert h.tier == "slower"

    def test_multiple_slower(self):
        h = compute_property_health("0001/001", [
            _sig("complaint", "slower"),
            _sig("complaint", "slower"),
        ])
        assert h.tier == "slower"

    def test_slower_plus_non_risk(self):
        h = compute_property_health("0001/001", [
            _sig("complaint", "slower"),
            _sig("expired_otc", "info"),
        ])
        assert h.tier == "slower"


# ── behind ───────────────────────────────────────────────────────

class TestBehind:
    def test_single_behind(self):
        h = compute_property_health("0001/001", [
            _sig("hold_stalled", "behind"),
        ])
        assert h.tier == "behind"

    def test_behind_beats_slower(self):
        h = compute_property_health("0001/001", [
            _sig("hold_stalled", "behind"),
            _sig("complaint", "slower"),
        ])
        assert h.tier == "behind"

    def test_behind_plus_non_risk(self):
        h = compute_property_health("0001/001", [
            _sig("hold_stalled", "behind"),
            _sig("expired_otc", "info"),
        ])
        assert h.tier == "behind"


# ── at_risk ──────────────────────────────────────────────────────

class TestAtRisk:
    def test_single_at_risk(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.at_risk_count == 1

    def test_at_risk_beats_behind(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("hold_stalled", "behind"),
        ])
        assert h.tier == "at_risk"

    def test_at_risk_beats_slower(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("complaint", "slower"),
        ])
        assert h.tier == "at_risk"

    def test_single_compounding_at_risk_is_at_risk_not_high(self):
        """One compounding type at at_risk → at_risk, NOT high_risk."""
        h = compute_property_health("0001/001", [
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"

    def test_two_at_risk_same_compounding_type_is_at_risk(self):
        """Two at_risk from SAME compounding type → at_risk, NOT high_risk."""
        h = compute_property_health("0001/001", [
            _sig("nov", "at_risk"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.at_risk_count == 2

    def test_two_at_risk_from_non_compounding_types(self):
        """Two at_risk from non-compounding types → at_risk, NOT high_risk."""
        # station_slow is not in COMPOUNDING_TYPES
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),  # compounding
            _sig("station_slow", "at_risk"),   # NOT compounding
        ])
        # Only 1 unique compounding type → at_risk
        assert h.tier == "at_risk"

    def test_one_compounding_one_non_compounding_at_risk(self):
        """One compounding + one non-compounding at_risk → at_risk (not high_risk)."""
        h = compute_property_health("0001/001", [
            _sig("nov", "at_risk"),
            _sig("station_slow", "at_risk"),
        ])
        assert h.tier == "at_risk"


# ── high_risk ────────────────────────────────────────────────────

class TestHighRisk:
    def test_two_different_compounding_types(self):
        """The core HIGH_RISK rule: 2+ unique compounding types at at_risk."""
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "high_risk"

    def test_three_different_compounding_types(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("nov", "at_risk"),
            _sig("abatement", "at_risk"),
        ])
        assert h.tier == "high_risk"

    def test_all_six_compounding_types(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("hold_stalled_planning", "at_risk"),
            _sig("nov", "at_risk"),
            _sig("abatement", "at_risk"),
            _sig("expired_uninspected", "at_risk"),
            _sig("stale_with_activity", "at_risk"),
        ])
        assert h.tier == "high_risk"
        assert h.at_risk_count == 6

    def test_high_risk_with_mixed_severities(self):
        """HIGH_RISK fires even with behind/slower signals mixed in."""
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("nov", "at_risk"),
            _sig("hold_stalled", "behind"),
            _sig("complaint", "slower"),
        ])
        assert h.tier == "high_risk"

    def test_high_risk_signal_counts(self):
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("nov", "at_risk"),
            _sig("hold_stalled", "behind"),
        ])
        assert h.tier == "high_risk"
        assert h.signal_count == 3
        assert h.at_risk_count == 2

    def test_hold_stalled_behind_does_not_compound(self):
        """hold_stalled (behind) should NOT trigger high_risk even with another at_risk."""
        # hold_stalled is NOT in COMPOUNDING_TYPES
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),   # compounding
            _sig("hold_stalled", "behind"),      # NOT compounding, NOT at_risk
        ])
        # Only 1 unique compounding type at at_risk → at_risk
        assert h.tier == "at_risk"

    def test_complaint_slower_does_not_compound(self):
        """complaint (slower) should NOT trigger high_risk."""
        h = compute_property_health("0001/001", [
            _sig("hold_comments", "at_risk"),
            _sig("complaint", "slower"),
        ])
        assert h.tier == "at_risk"


# ── PropertyHealth output validation ─────────────────────────────

class TestPropertyHealthOutput:
    def test_block_lot_preserved(self):
        h = compute_property_health("3512/001", [])
        assert h.block_lot == "3512/001"

    def test_signals_list_preserved(self):
        sigs = [_sig("nov", "at_risk"), _sig("complaint", "slower")]
        h = compute_property_health("3512/001", sigs)
        assert h.signals == sigs
        assert len(h.signals) == 2

    def test_signal_count_matches_input(self):
        sigs = [_sig("nov", "at_risk")] * 5
        h = compute_property_health("3512/001", sigs)
        assert h.signal_count == 5

    def test_at_risk_count_only_counts_at_risk(self):
        sigs = [
            _sig("nov", "at_risk"),
            _sig("hold_stalled", "behind"),
            _sig("complaint", "slower"),
            _sig("abatement", "at_risk"),
        ]
        h = compute_property_health("3512/001", sigs)
        assert h.at_risk_count == 2
