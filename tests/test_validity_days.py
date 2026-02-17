"""Tests for Table B validity-days lookup (SFBC Section 106A.4.4)."""

import pytest

from web.brief import _validity_days


class TestValidityDays:
    """Unit tests for _validity_days() — Table B expiration tiers."""

    def test_tier1_low_cost(self):
        """$1–$100,000 -> 360 days."""
        assert _validity_days({"estimated_cost": 50000}) == 360

    def test_tier1_boundary_100k(self):
        """$100,000 exactly -> still tier 1 (360 days)."""
        assert _validity_days({"estimated_cost": 100000}) == 360

    def test_tier2_just_above_100k(self):
        """$100,001 -> 1,080 days."""
        assert _validity_days({"estimated_cost": 100001}) == 1080

    def test_tier2_mid_range(self):
        """$1,000,000 -> 1,080 days."""
        assert _validity_days({"estimated_cost": 1000000}) == 1080

    def test_tier2_boundary_2499999(self):
        """$2,499,999 -> still tier 2 (1,080 days)."""
        assert _validity_days({"estimated_cost": 2499999}) == 1080

    def test_tier3_2500000(self):
        """$2,500,000 -> 1,440 days."""
        assert _validity_days({"estimated_cost": 2500000}) == 1440

    def test_tier3_large_project(self):
        """$10,000,000 -> 1,440 days."""
        assert _validity_days({"estimated_cost": 10000000}) == 1440

    def test_demolition_overrides_cost(self):
        """Demolition permits always get 180 days regardless of cost."""
        assert _validity_days({
            "permit_type_definition": "demolitions",
            "estimated_cost": 5000000,
        }) == 180

    def test_demolition_case_insensitive(self):
        """Demolition detection is case-insensitive."""
        assert _validity_days({
            "permit_type_definition": "FULL DEMOLITION",
            "estimated_cost": 50000,
        }) == 180

    def test_zero_cost_defaults_tier1(self):
        """$0 cost -> tier 1 (360 days)."""
        assert _validity_days({"estimated_cost": 0}) == 360

    def test_missing_cost_defaults_tier1(self):
        """No cost fields -> tier 1 (360 days)."""
        assert _validity_days({}) == 360

    def test_none_cost_defaults_tier1(self):
        """None cost -> tier 1 (360 days)."""
        assert _validity_days({"estimated_cost": None}) == 360

    def test_revised_cost_takes_precedence(self):
        """revised_cost is preferred over estimated_cost when present."""
        assert _validity_days({
            "revised_cost": 2500000,
            "estimated_cost": 50000,
        }) == 1440

    def test_revised_cost_none_falls_to_estimated(self):
        """If revised_cost is None, fall through to estimated_cost."""
        assert _validity_days({
            "revised_cost": None,
            "estimated_cost": 2500000,
        }) == 1440

    def test_string_cost_parsed(self):
        """Cost as string should be parsed to float."""
        assert _validity_days({"estimated_cost": "150000"}) == 1080

    def test_invalid_cost_string_defaults_tier1(self):
        """Non-numeric cost string -> tier 1 (360 days)."""
        assert _validity_days({"estimated_cost": "N/A"}) == 360

    def test_none_permit_type_not_demolition(self):
        """None permit_type_definition should not be treated as demolition."""
        assert _validity_days({
            "permit_type_definition": None,
            "estimated_cost": 50000,
        }) == 360

    def test_alterations_permit_uses_cost_tiers(self):
        """Alteration permits use cost-based tiers, not 180-day flat."""
        assert _validity_days({
            "permit_type_definition": "additions alterations or repairs",
            "estimated_cost": 1090000,
        }) == 1080

    def test_otc_permit_uses_cost_tiers(self):
        """OTC permits use cost-based tiers."""
        assert _validity_days({
            "permit_type_definition": "otc alterations permit",
            "estimated_cost": 50000,
        }) == 360


class TestValidityDaysInReport:
    """Verify that report.py imports and uses _validity_days correctly."""

    def test_dormant_permit_uses_table_b(self):
        """A $1M permit issued 400 days ago is NOT dormant (1,080-day limit)."""
        from web.report import _compute_risk_assessment
        permits = [{
            "permit_number": "P100", "status": "ISSUED",
            "issued_date": "2024-06-01", "filed_date": "2024-05-01",
            "completed_date": None,
            "estimated_cost": 1000000,
            "permit_type_definition": "additions alterations or repairs",
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        dormant = [r for r in risks if r["risk_type"] == "dormant_permit"]
        assert len(dormant) == 0, "A $1M permit at 400 days should NOT be flagged (limit is 1,080)"

    def test_dormant_low_cost_permit(self):
        """A $50K permit issued 400 days ago IS dormant (360-day limit)."""
        from web.report import _compute_risk_assessment
        permits = [{
            "permit_number": "P101", "status": "ISSUED",
            "issued_date": "2024-01-01", "filed_date": "2023-12-01",
            "completed_date": None,
            "estimated_cost": 50000,
            "permit_type_definition": "otc alterations permit",
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        dormant = [r for r in risks if r["risk_type"] == "dormant_permit"]
        assert len(dormant) == 1
        assert "360" in dormant[0]["title"] or "360" in dormant[0]["description"]

    def test_aging_permit_uses_table_b(self):
        """A $50K permit issued 300 days ago is aging (within 90 days of 360-day limit)."""
        from datetime import datetime, timedelta
        from web.report import _compute_risk_assessment
        issued = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
        permits = [{
            "permit_number": "P102", "status": "ISSUED",
            "issued_date": issued, "filed_date": issued,
            "completed_date": None,
            "estimated_cost": 50000,
            "permit_type_definition": "otc alterations permit",
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        aging = [r for r in risks if r["risk_type"] == "aging_permit"]
        assert len(aging) == 1
        assert "360" in aging[0]["description"]

    def test_high_cost_not_aging_at_300_days(self):
        """A $2.5M permit at 300 days is NOT aging (1,440-day limit, 90-day window starts at 1,350)."""
        from datetime import datetime, timedelta
        from web.report import _compute_risk_assessment
        issued = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
        permits = [{
            "permit_number": "P103", "status": "ISSUED",
            "issued_date": issued, "filed_date": issued,
            "completed_date": None,
            "estimated_cost": 2500000,
            "permit_type_definition": "additions alterations or repairs",
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        aging_or_dormant = [r for r in risks if r["risk_type"] in ("aging_permit", "dormant_permit")]
        assert len(aging_or_dormant) == 0

    def test_demolition_dormant_at_200_days(self):
        """A demolition permit at 200 days IS dormant (180-day limit)."""
        from datetime import datetime, timedelta
        from web.report import _compute_risk_assessment
        issued = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
        permits = [{
            "permit_number": "P104", "status": "ISSUED",
            "issued_date": issued, "filed_date": issued,
            "completed_date": None,
            "estimated_cost": 50000,
            "permit_type_definition": "demolitions",
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        dormant = [r for r in risks if r["risk_type"] == "dormant_permit"]
        assert len(dormant) == 1
        assert "180" in dormant[0]["title"] or "180" in dormant[0]["description"]
