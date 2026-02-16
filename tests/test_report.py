"""Tests for property report: ReportLinks, risk assessment, expeditor signal scoring."""

import pytest

from src.report_links import ReportLinks


# ── ReportLinks URL builder tests ─────────────────────────────────

class TestReportLinks:
    def test_permit_url(self):
        url = ReportLinks.permit("202210144403")
        assert "PermitNumber=202210144403" in url
        assert "dbiweb02.sfgov.org" in url

    def test_complaint_url(self):
        url = ReportLinks.complaint("202429366")
        assert "ComplaintNumber=202429366" in url
        assert "dbiweb02.sfgov.org" in url

    def test_parcel_url(self):
        url = ReportLinks.parcel("2991", "012")
        assert "block=2991" in url
        assert "lot=012" in url
        assert "sfassessor.org" in url

    def test_planning_code_known_section(self):
        url = ReportLinks.planning_code("311")
        assert "0-0-0-21240" in url
        assert "amlegal.com" in url

    def test_planning_code_unknown_section_returns_base(self):
        url = ReportLinks.planning_code("999")
        assert url == "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning"

    def test_entity_url_encodes_spaces(self):
        url = ReportLinks.entity("Schaeffer Nelson")
        assert "Schaeffer+Nelson" in url
        assert "sfpermits-ai-production.up.railway.app" in url

    def test_entity_url_encodes_special_chars(self):
        url = ReportLinks.entity("O'Brien & Associates")
        assert "O%27Brien" in url or "O'Brien" in url  # quote_plus handles this
        assert "sfpermits-ai-production.up.railway.app" in url

    def test_ethics_registry_url(self):
        url = ReportLinks.ethics_registry()
        assert "sfethics.org" in url
        assert "permit-consultant-disclosure" in url


# ── Risk assessment tests ─────────────────────────────────────────

class TestRiskAssessment:
    """Tests for _compute_risk_assessment in web/report.py."""

    def test_active_complaint_is_high_risk(self):
        from web.report import _compute_risk_assessment
        complaints = [{"status": "OPEN", "complaint_number": "202429366", "description": "Work beyond scope"}]
        risks = _compute_risk_assessment(
            permits=[], complaints=complaints, violations=[], property_data=[]
        )
        assert len(risks) > 0
        assert risks[0]["severity"] == "high"

    def test_active_violation_is_high_risk(self):
        from web.report import _compute_risk_assessment
        violations = [{"status": "OPEN", "complaint_number": "202429366", "nov_category_description": "Building"}]
        risks = _compute_risk_assessment(
            permits=[], complaints=[], violations=violations, property_data=[]
        )
        assert len(risks) > 0
        assert risks[0]["severity"] == "high"

    def test_high_cost_permit_is_moderate_risk(self):
        from web.report import _compute_risk_assessment
        permits = [{"estimated_cost": 600000, "permit_number": "2022001", "status": "ISSUED", "description": "Major renovation"}]
        risks = _compute_risk_assessment(
            permits=permits, complaints=[], violations=[], property_data=[]
        )
        # High cost alone is moderate, not high
        high_cost_risks = [r for r in risks if "cost" in r.get("title", "").lower() or "cost" in r.get("description", "").lower()]
        if high_cost_risks:
            assert high_cost_risks[0]["severity"] in ("moderate", "low")

    def test_no_issues_returns_empty(self):
        from web.report import _compute_risk_assessment
        risks = _compute_risk_assessment(
            permits=[], complaints=[], violations=[], property_data=[]
        )
        assert risks == []


# ── Expeditor signal scoring tests ────────────────────────────────

class TestExpediterSignal:
    """Tests for _compute_expediter_signal in web/report.py."""

    def test_no_risk_factors_is_cold(self):
        from web.report import _compute_expediter_signal
        result = _compute_expediter_signal(
            complaints=[], violations=[], permits=[], property_data=[]
        )
        assert result["score"] == 0
        assert result["signal"] == "cold"

    def test_active_complaint_adds_3(self):
        from web.report import _compute_expediter_signal
        complaints = [{"status": "OPEN"}]
        result = _compute_expediter_signal(
            complaints=complaints, violations=[], permits=[], property_data=[]
        )
        assert result["score"] >= 3
        assert result["signal"] in ("recommended", "strongly_recommended", "essential")

    def test_prior_violations_adds_2(self):
        from web.report import _compute_expediter_signal
        violations = [{"status": "OPEN"}]
        result = _compute_expediter_signal(
            complaints=[], violations=violations, permits=[], property_data=[]
        )
        assert result["score"] >= 2

    def test_high_cost_permit_adds_points(self):
        from web.report import _compute_expediter_signal
        permits = [{"estimated_cost": 600000}]
        result = _compute_expediter_signal(
            complaints=[], violations=[], permits=permits, property_data=[]
        )
        assert result["score"] >= 2  # $500K+ = +2

    def test_essential_threshold(self):
        from web.report import _compute_expediter_signal
        # Active complaint (+3) + violations (+2) + high cost (+2) + restrictive zoning (+1) = 8+
        result = _compute_expediter_signal(
            complaints=[{"status": "OPEN"}],
            violations=[{"status": "OPEN"}],
            permits=[{"estimated_cost": 600000}],
            property_data=[{"zoning_code": "RH-1(D)"}],
        )
        assert result["score"] >= 8
        assert result["signal"] == "essential"

    def test_signal_thresholds(self):
        from web.report import _compute_expediter_signal
        # Verify the threshold mapping
        # 0 = cold, 1-2 = warm, 3-4 = recommended, 5-7 = strongly_recommended, 8+ = essential
        result_0 = _compute_expediter_signal(complaints=[], violations=[], permits=[], property_data=[])
        assert result_0["signal"] == "cold"

        # warm: 1-2 points — e.g., high cost permit alone ($100K-$500K = +1)
        result_warm = _compute_expediter_signal(complaints=[], violations=[], permits=[{"estimated_cost": 200000}], property_data=[])
        assert result_warm["signal"] == "warm"


# ── Risk type field tests ─────────────────────────────────────────

class TestRiskItemTypes:
    """Verify that every risk item produced by _compute_risk_assessment includes a risk_type field."""

    def test_active_complaint_has_risk_type(self):
        from web.report import _compute_risk_assessment
        complaints = [{"status": "OPEN", "complaint_number": "1234", "description": "noise"}]
        risks = _compute_risk_assessment(permits=[], complaints=complaints, violations=[], property_data=[])
        assert len(risks) >= 1
        assert risks[0]["risk_type"] == "active_complaint"

    def test_active_violation_has_risk_type(self):
        from web.report import _compute_risk_assessment
        violations = [{"status": "OPEN", "nov_number": "V001", "description": "Building"}]
        risks = _compute_risk_assessment(permits=[], complaints=[], violations=violations, property_data=[])
        assert len(risks) >= 1
        assert risks[0]["risk_type"] == "active_violation"

    def test_high_cost_project_has_risk_type(self):
        from web.report import _compute_risk_assessment
        permits = [{"estimated_cost": 600000, "permit_number": "P001", "status": "ISSUED", "description": "reno"}]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        cost_risks = [r for r in risks if r["risk_type"] == "high_cost_project"]
        assert len(cost_risks) == 1

    def test_moderate_cost_project_has_risk_type(self):
        from web.report import _compute_risk_assessment
        permits = [{"estimated_cost": 200000, "permit_number": "P002", "status": "ISSUED", "description": "small reno"}]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        cost_risks = [r for r in risks if r["risk_type"] == "moderate_cost_project"]
        assert len(cost_risks) == 1

    def test_multiple_active_permits_has_risk_type(self):
        from web.report import _compute_risk_assessment
        permits = [
            {"estimated_cost": 5000, "permit_number": "P003", "status": "ISSUED"},
            {"estimated_cost": 8000, "permit_number": "P004", "status": "FILED"},
        ]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        multi_risks = [r for r in risks if r["risk_type"] == "multiple_active_permits"]
        assert len(multi_risks) == 1

    def test_restrictive_zoning_has_risk_type(self):
        from web.report import _compute_risk_assessment
        risks = _compute_risk_assessment(
            permits=[], complaints=[], violations=[], property_data=[{"zoning_code": "RH-1(D)"}]
        )
        zone_risks = [r for r in risks if r["risk_type"] == "restrictive_zoning"]
        assert len(zone_risks) == 1

    def test_all_risk_items_have_risk_type_field(self):
        """Every risk item must have a risk_type key regardless of data mix."""
        from web.report import _compute_risk_assessment
        risks = _compute_risk_assessment(
            permits=[
                {"estimated_cost": 600000, "permit_number": "P1", "status": "ISSUED", "description": "big"},
                {"estimated_cost": 200000, "permit_number": "P2", "status": "FILED", "description": "med"},
            ],
            complaints=[{"status": "OPEN", "complaint_number": "C1", "description": "noise"}],
            violations=[{"status": "OPEN", "nov_number": "V1", "description": "Building"}],
            property_data=[{"zoning_code": "RH-1"}],
        )
        assert len(risks) > 0
        for risk in risks:
            assert "risk_type" in risk, f"Missing risk_type in: {risk}"


# ── Standalone signal helper tests ────────────────────────────────

class TestSignalHelpers:
    """Tests for standalone _score_to_signal and _signal_to_message functions."""

    def test_score_to_signal_cold(self):
        from web.report import _score_to_signal
        assert _score_to_signal(0) == "cold"

    def test_score_to_signal_warm(self):
        from web.report import _score_to_signal
        assert _score_to_signal(1) == "warm"
        assert _score_to_signal(2) == "warm"

    def test_score_to_signal_recommended(self):
        from web.report import _score_to_signal
        assert _score_to_signal(3) == "recommended"
        assert _score_to_signal(4) == "recommended"

    def test_score_to_signal_strongly_recommended(self):
        from web.report import _score_to_signal
        assert _score_to_signal(5) == "strongly_recommended"
        assert _score_to_signal(7) == "strongly_recommended"

    def test_score_to_signal_essential(self):
        from web.report import _score_to_signal
        assert _score_to_signal(8) == "essential"
        assert _score_to_signal(15) == "essential"

    def test_signal_to_message_valid(self):
        from web.report import _signal_to_message
        for signal in ("cold", "warm", "recommended", "strongly_recommended", "essential"):
            msg = _signal_to_message(signal)
            assert isinstance(msg, str)
            assert len(msg) > 10

    def test_signal_to_message_unknown_falls_back(self):
        from web.report import _signal_to_message
        assert _signal_to_message("nonexistent") == _signal_to_message("cold")
