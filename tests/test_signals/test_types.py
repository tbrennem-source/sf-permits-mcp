"""Tests for src.signals.types — catalog, dataclasses, severity mapping."""

import pytest
from src.signals.types import (
    SignalType,
    Signal,
    PropertyHealth,
    SIGNAL_CATALOG,
    COMPOUNDING_TYPES,
)


# ── SIGNAL_CATALOG tests ─────────────────────────────────────────

class TestSignalCatalog:
    """Tests for the SIGNAL_CATALOG and COMPOUNDING_TYPES constants."""

    def test_catalog_has_13_entries(self):
        assert len(SIGNAL_CATALOG) == 13

    def test_catalog_keys_match_signal_type_field(self):
        for key, st in SIGNAL_CATALOG.items():
            assert key == st.signal_type, f"Key '{key}' != signal_type '{st.signal_type}'"

    def test_all_severities_are_valid(self):
        valid = {"at_risk", "behind", "slower"}
        for key, st in SIGNAL_CATALOG.items():
            assert st.default_severity in valid, (
                f"{key} has invalid severity '{st.default_severity}'"
            )

    def test_all_actionable_values_valid(self):
        valid = {"yes", "warning", "info"}
        for key, st in SIGNAL_CATALOG.items():
            assert st.actionable in valid, (
                f"{key} has invalid actionable '{st.actionable}'"
            )

    def test_all_have_descriptions(self):
        for key, st in SIGNAL_CATALOG.items():
            assert st.description, f"{key} missing description"

    def test_all_have_source_dataset(self):
        for key, st in SIGNAL_CATALOG.items():
            assert st.source_dataset, f"{key} missing source_dataset"

    def test_expected_signal_types_present(self):
        expected = {
            "hold_comments", "hold_stalled_planning", "hold_stalled",
            "nov", "abatement", "expired_uninspected", "stale_with_activity",
            "expired_minor_activity", "expired_inconclusive", "expired_otc",
            "stale_no_activity", "complaint", "station_slow",
        }
        assert set(SIGNAL_CATALOG.keys()) == expected

    def test_hold_comments_is_at_risk(self):
        assert SIGNAL_CATALOG["hold_comments"].default_severity == "at_risk"

    def test_hold_stalled_is_behind(self):
        assert SIGNAL_CATALOG["hold_stalled"].default_severity == "behind"

    def test_complaint_is_slower(self):
        assert SIGNAL_CATALOG["complaint"].default_severity == "slower"

    def test_expired_otc_is_slower(self):
        assert SIGNAL_CATALOG["expired_otc"].default_severity == "slower"

    def test_nov_is_at_risk(self):
        assert SIGNAL_CATALOG["nov"].default_severity == "at_risk"

    def test_abatement_is_at_risk(self):
        assert SIGNAL_CATALOG["abatement"].default_severity == "at_risk"


# ── COMPOUNDING_TYPES tests ──────────────────────────────────────

class TestCompoundingTypes:
    """Tests for the COMPOUNDING_TYPES set."""

    def test_has_6_types(self):
        assert len(COMPOUNDING_TYPES) == 6

    def test_expected_members(self):
        expected = {
            "hold_comments", "hold_stalled_planning", "nov",
            "abatement", "expired_uninspected", "stale_with_activity",
        }
        assert COMPOUNDING_TYPES == expected

    def test_hold_stalled_does_not_compound(self):
        assert "hold_stalled" not in COMPOUNDING_TYPES

    def test_complaint_does_not_compound(self):
        assert "complaint" not in COMPOUNDING_TYPES

    def test_station_slow_does_not_compound(self):
        assert "station_slow" not in COMPOUNDING_TYPES

    def test_expired_otc_does_not_compound(self):
        assert "expired_otc" not in COMPOUNDING_TYPES

    def test_all_compounding_types_in_catalog(self):
        for ct in COMPOUNDING_TYPES:
            assert ct in SIGNAL_CATALOG, f"Compounding type '{ct}' not in catalog"


# ── SignalType dataclass tests ───────────────────────────────────

class TestSignalType:
    def test_create(self):
        st = SignalType(
            signal_type="test",
            default_severity="at_risk",
            source_dataset="permits",
            actionable="yes",
            description="A test signal",
        )
        assert st.signal_type == "test"
        assert st.default_severity == "at_risk"

    def test_fields_accessible(self):
        st = SIGNAL_CATALOG["hold_comments"]
        assert hasattr(st, "signal_type")
        assert hasattr(st, "default_severity")
        assert hasattr(st, "source_dataset")
        assert hasattr(st, "actionable")
        assert hasattr(st, "description")


# ── Signal dataclass tests ───────────────────────────────────────

class TestSignal:
    def test_create_with_all_fields(self):
        s = Signal(
            signal_type="hold_comments",
            severity="at_risk",
            permit_number="202401010001",
            block_lot="3512/001",
            detail="Issued Comments at station CPC",
        )
        assert s.signal_type == "hold_comments"
        assert s.severity == "at_risk"
        assert s.permit_number == "202401010001"
        assert s.block_lot == "3512/001"
        assert s.detail == "Issued Comments at station CPC"

    def test_create_without_permit(self):
        s = Signal(
            signal_type="nov",
            severity="at_risk",
            permit_number=None,
            block_lot="3512/001",
            detail="3 open NOVs",
        )
        assert s.permit_number is None

    def test_create_without_block_lot(self):
        s = Signal(
            signal_type="hold_comments",
            severity="at_risk",
            permit_number="202401010001",
            block_lot="",
            detail="test",
        )
        assert s.block_lot == ""


# ── PropertyHealth dataclass tests ───────────────────────────────

class TestPropertyHealth:
    def test_create(self):
        ph = PropertyHealth(
            block_lot="3512/001",
            tier="at_risk",
            signal_count=3,
            at_risk_count=1,
            signals=[],
        )
        assert ph.block_lot == "3512/001"
        assert ph.tier == "at_risk"
        assert ph.signal_count == 3
        assert ph.at_risk_count == 1
        assert ph.signals == []

    def test_with_signals(self):
        s = Signal("nov", "at_risk", None, "3512/001", "test")
        ph = PropertyHealth("3512/001", "at_risk", 1, 1, [s])
        assert len(ph.signals) == 1
        assert ph.signals[0].signal_type == "nov"
