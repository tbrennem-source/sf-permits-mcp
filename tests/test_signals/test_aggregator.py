"""Tests for property-level health tier aggregation.

Covers ALL required cases from the spec:
  - on_track (no signals)
  - slower (complaint only)
  - behind (hold_stalled only)
  - at_risk (single nov)
  - high_risk (hold_comments + nov)
  - high_risk (hold_stalled_planning + stale_with_activity)
  - high_risk (3 different at_risk types)
  - NOT high_risk: hold_stalled + nov
  - NOT high_risk: complaint + nov
  - NOT high_risk: at_risk + slower
  - NOT high_risk: two same-type signals
"""

import pytest

from src.signals.types import Signal
from src.signals.aggregator import compute_property_health, COMPOUNDING_TYPES


def _sig(signal_type, severity, permit=None, block_lot="3512/001", detail=""):
    return Signal(signal_type, severity, permit, block_lot, detail)


class TestTierDerivation:
    def test_on_track_no_signals(self):
        h = compute_property_health("3512/001", [])
        assert h.tier == "on_track"
        assert h.signal_count == 0
        assert h.at_risk_count == 0

    def test_slower_complaint_only(self):
        h = compute_property_health("3512/001", [
            _sig("complaint", "slower"),
        ])
        assert h.tier == "slower"

    def test_behind_hold_stalled_only(self):
        h = compute_property_health("3512/001", [
            _sig("hold_stalled", "behind", "P001"),
        ])
        assert h.tier == "behind"

    def test_at_risk_single_nov(self):
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.at_risk_count == 1

    def test_high_risk_hold_comments_plus_nov(self):
        h = compute_property_health("3512/001", [
            _sig("hold_comments", "at_risk", "P001"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "high_risk"

    def test_high_risk_hold_planning_plus_stale(self):
        h = compute_property_health("3512/001", [
            _sig("hold_stalled_planning", "at_risk", "P001"),
            _sig("stale_with_activity", "at_risk", "P002"),
        ])
        assert h.tier == "high_risk"

    def test_high_risk_three_at_risk_types(self):
        h = compute_property_health("3512/001", [
            _sig("hold_comments", "at_risk", "P001"),
            _sig("nov", "at_risk"),
            _sig("expired_uninspected", "at_risk", "P002"),
        ])
        assert h.tier == "high_risk"
        assert h.at_risk_count == 3

    def test_not_high_risk_hold_stalled_plus_nov(self):
        """hold_stalled is 'behind' severity, not in COMPOUNDING_TYPES."""
        h = compute_property_health("3512/001", [
            _sig("hold_stalled", "behind", "P001"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.tier != "high_risk"

    def test_not_high_risk_complaint_plus_nov(self):
        """complaint is 'slower', not in COMPOUNDING_TYPES."""
        h = compute_property_health("3512/001", [
            _sig("complaint", "slower"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.tier != "high_risk"

    def test_not_high_risk_at_risk_plus_slower(self):
        """Slower signals never compound."""
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
            _sig("stale_no_activity", "slower", "P002"),
        ])
        assert h.tier == "at_risk"
        assert h.tier != "high_risk"

    def test_not_high_risk_same_type_twice(self):
        """Two signals of same type = 1 unique compounding type, not 2."""
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"
        assert h.tier != "high_risk"

    def test_high_risk_nov_plus_stale_with_activity(self):
        """The dominant compound pattern (82.5% of HIGH_RISK)."""
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
            _sig("stale_with_activity", "at_risk", "P001"),
        ])
        assert h.tier == "high_risk"

    def test_high_risk_expired_uninspected_plus_stale(self):
        h = compute_property_health("3512/001", [
            _sig("expired_uninspected", "at_risk", "P001"),
            _sig("stale_with_activity", "at_risk", "P002"),
        ])
        assert h.tier == "high_risk"

    def test_high_risk_abatement_plus_nov(self):
        h = compute_property_health("3512/001", [
            _sig("abatement", "at_risk"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "high_risk"


class TestTierPriority:
    def test_at_risk_overrides_behind(self):
        h = compute_property_health("3512/001", [
            _sig("hold_stalled", "behind", "P001"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"

    def test_behind_overrides_slower(self):
        h = compute_property_health("3512/001", [
            _sig("complaint", "slower"),
            _sig("expired_inconclusive", "behind", "P001"),
        ])
        assert h.tier == "behind"

    def test_slower_overrides_on_track(self):
        h = compute_property_health("3512/001", [
            _sig("complaint", "slower"),
        ])
        assert h.tier == "slower"


class TestSignalCounts:
    def test_signal_count(self):
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
            _sig("complaint", "slower"),
            _sig("hold_stalled", "behind", "P001"),
        ])
        assert h.signal_count == 3

    def test_at_risk_count(self):
        h = compute_property_health("3512/001", [
            _sig("nov", "at_risk"),
            _sig("abatement", "at_risk"),
            _sig("complaint", "slower"),
        ])
        assert h.at_risk_count == 2

    def test_signals_preserved(self):
        signals = [
            _sig("nov", "at_risk"),
            _sig("hold_comments", "at_risk", "P001"),
        ]
        h = compute_property_health("3512/001", signals)
        assert h.signals == signals


class TestCompoundingTypes:
    def test_compounding_set(self):
        assert COMPOUNDING_TYPES == frozenset({
            "hold_comments", "hold_stalled_planning", "nov",
            "abatement", "expired_uninspected", "stale_with_activity",
        })

    def test_hold_stalled_not_compounding(self):
        assert "hold_stalled" not in COMPOUNDING_TYPES

    def test_complaint_not_compounding(self):
        assert "complaint" not in COMPOUNDING_TYPES

    def test_expired_otc_not_compounding(self):
        assert "expired_otc" not in COMPOUNDING_TYPES

    def test_stale_no_activity_not_compounding(self):
        assert "stale_no_activity" not in COMPOUNDING_TYPES


class TestEdgeCases:
    def test_empty_block_lot(self):
        h = compute_property_health("", [_sig("nov", "at_risk")])
        assert h.tier == "at_risk"
        assert h.block_lot == ""

    def test_four_signal_types(self):
        """1281 8th Ave showcase — 4 signal types."""
        h = compute_property_health("1234/001", [
            _sig("hold_comments", "at_risk", "P001"),
            _sig("nov", "at_risk"),
            _sig("expired_uninspected", "at_risk", "P002"),
            _sig("stale_with_activity", "at_risk", "P003"),
        ])
        assert h.tier == "high_risk"
        assert h.at_risk_count == 4

    def test_mixed_severity_and_types(self):
        """Multiple behind + multiple slower + one at_risk = at_risk, not high_risk."""
        h = compute_property_health("3512/001", [
            _sig("hold_stalled", "behind", "P001"),
            _sig("expired_minor_activity", "behind", "P002"),
            _sig("complaint", "slower"),
            _sig("nov", "at_risk"),
        ])
        assert h.tier == "at_risk"

    def test_triple_threat_different_at_risk(self):
        """3 different compounding types."""
        h = compute_property_health("3512/001", [
            _sig("hold_comments", "at_risk", "P001"),
            _sig("nov", "at_risk"),
            _sig("stale_with_activity", "at_risk", "P002"),
        ])
        assert h.tier == "high_risk"
