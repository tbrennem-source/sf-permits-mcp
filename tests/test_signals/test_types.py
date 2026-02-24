"""Tests for signal types catalog and dataclasses."""

import pytest

from src.signals.types import (
    Signal,
    SignalType,
    PropertyHealth,
    SIGNAL_CATALOG,
)


class TestSignalCatalog:
    def test_catalog_has_13_types(self):
        assert len(SIGNAL_CATALOG) == 13

    def test_all_keys_match_signal_type(self):
        for key, st in SIGNAL_CATALOG.items():
            assert key == st.signal_type

    def test_all_severities_valid(self):
        valid = {"at_risk", "behind", "slower"}
        for st in SIGNAL_CATALOG.values():
            assert st.default_severity in valid, f"{st.signal_type}: {st.default_severity}"

    def test_all_actionable_valid(self):
        valid = {"yes", "warning", "info"}
        for st in SIGNAL_CATALOG.values():
            assert st.actionable in valid, f"{st.signal_type}: {st.actionable}"

    def test_at_risk_signals(self):
        at_risk = [k for k, v in SIGNAL_CATALOG.items() if v.default_severity == "at_risk"]
        assert set(at_risk) == {
            "hold_comments", "hold_stalled_planning", "nov", "abatement",
            "expired_uninspected", "stale_with_activity",
        }

    def test_behind_signals(self):
        behind = [k for k, v in SIGNAL_CATALOG.items() if v.default_severity == "behind"]
        assert set(behind) == {
            "hold_stalled", "expired_minor_activity", "expired_inconclusive", "station_slow",
        }

    def test_slower_signals(self):
        slower = [k for k, v in SIGNAL_CATALOG.items() if v.default_severity == "slower"]
        assert set(slower) == {"complaint", "expired_otc", "stale_no_activity"}

    def test_source_datasets(self):
        sources = {st.source_dataset for st in SIGNAL_CATALOG.values()}
        assert "addenda" in sources
        assert "violations" in sources
        assert "permits" in sources
        assert "complaints" in sources


class TestSignalDataclass:
    def test_create_signal(self):
        s = Signal("nov", "at_risk", None, "3512/001", "5 open NOVs")
        assert s.signal_type == "nov"
        assert s.severity == "at_risk"
        assert s.permit_number is None
        assert s.block_lot == "3512/001"

    def test_signal_with_permit(self):
        s = Signal("hold_comments", "at_risk", "202301015555", "3600/010", "Issued Comments at BLDG")
        assert s.permit_number == "202301015555"


class TestPropertyHealth:
    def test_create_health(self):
        h = PropertyHealth("3512/001", "high_risk", 5, 3)
        assert h.block_lot == "3512/001"
        assert h.tier == "high_risk"
        assert h.signal_count == 5
        assert h.at_risk_count == 3
        assert h.signals == []

    def test_health_with_signals(self):
        signals = [
            Signal("nov", "at_risk", None, "3512/001", "Open NOV"),
            Signal("hold_comments", "at_risk", "P001", "3512/001", "Hold"),
        ]
        h = PropertyHealth("3512/001", "high_risk", 2, 2, signals)
        assert len(h.signals) == 2
