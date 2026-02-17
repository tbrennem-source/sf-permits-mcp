"""Tests for Owner Mode: detection, What's Missing analysis, remediation roadmap, extended signal factors."""

import pytest
from web.owner_mode import (
    detect_owner,
    compute_whats_missing,
    compute_remediation_roadmap,
    compute_extended_consultant_factors,
    attach_kb_citations,
    _normalize_street_name,
    _parse_address,
    _check_classification_drift,
    _check_assessor_mismatch,
    _check_complaint_timing,
    _uses_equivalent,
)
from src.report_links import ReportLinks


class TestOwnerDetection:
    """Test is_owner detection logic."""

    def test_no_user_not_owner(self):
        """Anonymous user is never owner."""
        assert detect_owner(None, "75 Robinhood Dr") is False

    def test_no_user_explicit_toggle_ignored(self):
        """?owner=1 without login returns False."""
        assert detect_owner(None, "75 Robinhood Dr", explicit_toggle=True) is False

    def test_explicit_toggle_logged_in(self):
        """Logged-in user with ?owner=1 is owner regardless of address."""
        user = {"primary_street_number": "", "primary_street_name": ""}
        assert detect_owner(user, "999 Nowhere St", explicit_toggle=True) is True

    def test_address_match_auto_detects(self):
        """User's primary address matching report address auto-detects owner."""
        user = {"primary_street_number": "75", "primary_street_name": "Robinhood Dr"}
        assert detect_owner(user, "75 Robinhood Dr") is True

    def test_address_match_normalizes_suffix(self):
        """'Robinhood' matches 'Robinhood Dr' after suffix stripping."""
        user = {"primary_street_number": "75", "primary_street_name": "Robinhood"}
        assert detect_owner(user, "75 Robinhood Dr") is True

    def test_address_match_case_insensitive(self):
        """'robinhood dr' matches 'ROBINHOOD DR'."""
        user = {"primary_street_number": "75", "primary_street_name": "robinhood dr"}
        assert detect_owner(user, "75 ROBINHOOD DR") is True

    def test_address_no_match_different_number(self):
        """Matching street but different number is not owner."""
        user = {"primary_street_number": "77", "primary_street_name": "Robinhood Dr"}
        assert detect_owner(user, "75 Robinhood Dr") is False

    def test_address_no_match_different_street(self):
        """Different street entirely is not owner."""
        user = {"primary_street_number": "75", "primary_street_name": "Polk St"}
        assert detect_owner(user, "75 Robinhood Dr") is False

    def test_user_without_primary_address(self):
        """User with no primary address set is not auto-detected."""
        user = {"primary_street_number": None, "primary_street_name": None}
        assert detect_owner(user, "75 Robinhood Dr") is False


class TestNormalization:
    """Test address normalization helpers."""

    def test_normalize_strips_st(self):
        assert _normalize_street_name("Polk St") == "POLK"

    def test_normalize_strips_avenue(self):
        assert _normalize_street_name("16th Avenue") == "16TH"

    def test_normalize_strips_blvd(self):
        assert _normalize_street_name("Geary Blvd") == "GEARY"

    def test_normalize_preserves_multiword(self):
        assert _normalize_street_name("Van Ness Ave") == "VAN NESS"

    def test_normalize_empty_string(self):
        assert _normalize_street_name("") == ""

    def test_normalize_single_word_no_suffix(self):
        assert _normalize_street_name("Broadway") == "BROADWAY"

    def test_parse_address_standard(self):
        num, street = _parse_address("75 Robinhood Dr")
        assert num == "75"
        assert street == "Robinhood Dr"

    def test_parse_address_empty(self):
        assert _parse_address("") == ("", "")

    def test_parse_address_number_only(self):
        """Single token (no street) returns empty tuple."""
        assert _parse_address("75") == ("", "")


class TestWhatsMissing:
    """Test cross-reference analysis."""

    def test_classification_drift_detected(self):
        """Use changing from '1 family' to '2 family' without conversion."""
        permits = [
            {"filed_date": "2015-01-01", "existing_use": "1 family dwelling", "permit_number": "P1", "description": "reroofing"},
            {"filed_date": "2025-03-27", "existing_use": "2 family dwelling", "permit_number": "P2", "description": "reroofing"},
        ]
        results = _check_classification_drift(permits)
        assert len(results) == 1
        assert results[0]["type"] == "classification_drift"
        assert results[0]["severity"] == "moderate"

    def test_no_drift_when_conversion_exists(self):
        """No flag when conversion permit exists between use changes."""
        permits = [
            {"filed_date": "2015-01-01", "existing_use": "1 family dwelling", "permit_number": "P1", "description": "reroofing"},
            {"filed_date": "2020-06-15", "existing_use": "1 family dwelling", "permit_number": "P2", "description": "ADU legalization and conversion"},
            {"filed_date": "2025-03-27", "existing_use": "2 family dwelling", "permit_number": "P3", "description": "reroofing"},
        ]
        results = _check_classification_drift(permits)
        assert len(results) == 0

    def test_assessor_mismatch_detected(self):
        """Assessor use differs from permit."""
        permits = [{"filed_date": "2025-01-01", "existing_use": "2 family dwelling", "permit_number": "P1"}]
        property_data = [{"use_definition": "Single Family Dwelling"}]
        results = _check_assessor_mismatch(permits, property_data)
        assert len(results) == 1
        assert results[0]["type"] == "assessor_mismatch"

    def test_assessor_equivalent_not_flagged(self):
        """Known equivalent terms don't trigger mismatch."""
        permits = [{"filed_date": "2025-01-01", "existing_use": "1 family dwelling", "permit_number": "P1"}]
        property_data = [{"use_definition": "Single Family Dwelling"}]
        results = _check_assessor_mismatch(permits, property_data)
        assert len(results) == 0

    def test_complaint_timing_in_window(self):
        """Permit filed 15 days after complaint is flagged."""
        complaints = [{"date_filed": "2013-08-14T00:00:00.000", "complaint_number": "C1"}]
        permits = [{"filed_date": "2013-08-16T00:00:00.000", "permit_number": "P1"}]
        results = _check_complaint_timing(permits, complaints)
        assert len(results) == 1
        assert results[0]["evidence"]["days_gap"] == 2

    def test_complaint_timing_outside_window(self):
        """Permit filed 45 days after complaint is NOT flagged."""
        complaints = [{"date_filed": "2013-08-14T00:00:00.000", "complaint_number": "C1"}]
        permits = [{"filed_date": "2013-10-01T00:00:00.000", "permit_number": "P1"}]
        results = _check_complaint_timing(permits, complaints)
        assert len(results) == 0

    def test_empty_data_returns_empty(self):
        """No data -> no findings."""
        results = compute_whats_missing([], [], [])
        assert results == []

    def test_uses_equivalent(self):
        """Known equivalent use terms."""
        assert _uses_equivalent("1 family dwelling", "single family dwelling") is True
        assert _uses_equivalent("office", "offices") is True
        assert _uses_equivalent("1 family dwelling", "2 family dwelling") is False

    def test_assessor_single_family_residential_equivalent(self):
        """Assessor 'Single Family Residential' matches permit '1 family dwelling'."""
        assert _uses_equivalent("Single Family Residential", "1 family dwelling") is True

    def test_assessor_single_family_residential_no_mismatch(self):
        """Assessor 'Single Family Residential' should NOT flag mismatch against '1 family dwelling'."""
        permits = [{"filed_date": "2024-08-01", "existing_use": "1 family dwelling", "permit_number": "202408068071"}]
        property_data = [{"use_definition": "Single Family Residential"}]
        results = _check_assessor_mismatch(permits, property_data)
        assert len(results) == 0

    def test_compute_whats_missing_sorts_by_severity(self):
        """Moderate findings sort before low findings."""
        permits = [
            {"filed_date": "2015-01-01", "existing_use": "1 family dwelling", "permit_number": "P1", "description": "reroofing"},
            {"filed_date": "2025-03-27", "existing_use": "2 family dwelling", "permit_number": "P2", "description": "reroofing"},
        ]
        complaints = [{"date_filed": "2025-03-20T00:00:00.000", "complaint_number": "C1"}]
        results = compute_whats_missing(permits, complaints, [])
        if len(results) > 1:
            severities = [r["severity"] for r in results]
            moderate_idx = [i for i, s in enumerate(severities) if s == "moderate"]
            low_idx = [i for i, s in enumerate(severities) if s == "low"]
            if moderate_idx and low_idx:
                assert max(moderate_idx) < min(low_idx)

    def test_classification_drift_evidence_fields(self):
        """Drift findings include all expected evidence fields."""
        permits = [
            {"filed_date": "2015-01-01", "existing_use": "1 family dwelling", "permit_number": "P1", "description": "roof"},
            {"filed_date": "2025-03-27", "existing_use": "2 family dwelling", "permit_number": "P2", "description": "roof"},
        ]
        results = _check_classification_drift(permits)
        assert len(results) == 1
        evidence = results[0]["evidence"]
        assert "old_use" in evidence
        assert "new_use" in evidence
        assert "trigger_permit" in evidence
        assert "trigger_date" in evidence


class TestRemediationRoadmap:
    """Test remediation card generation."""

    @pytest.fixture
    def sample_templates(self):
        return {
            "remediation_templates": {
                "active_complaint": {
                    "what_at_stake": "An open complaint can delay permits.",
                    "options": [
                        {"label": "Resolve", "effort": "least_effort", "description": "Contact DBI", "steps": ["Call DBI"]},
                        {"label": "Full fix", "effort": "full_compliance", "description": "Address issue", "steps": ["Fix it"]},
                        {"label": "Status quo", "effort": "status_quo", "description": "Wait", "steps": ["Monitor"]},
                    ],
                    "sources": [{"type": "dbi_contact", "label": "DBI", "url": "https://sf.gov"}],
                },
                "classification_drift": {
                    "what_at_stake": "Undocumented use change could affect insurance.",
                    "options": [{"label": "Legalize", "effort": "full_compliance", "description": "File conversion permit", "steps": ["File"]}],
                    "sources": [],
                },
            }
        }

    def test_high_risk_generates_card(self, sample_templates):
        """Active complaint (high) generates remediation card."""
        risks = [{"severity": "high", "risk_type": "active_complaint", "title": "Active DBI complaint"}]
        cards = compute_remediation_roadmap(risks, [], sample_templates)
        assert len(cards) == 1
        assert cards[0]["risk_type"] == "active_complaint"
        assert len(cards[0]["options"]) == 3

    def test_low_risk_skipped(self, sample_templates):
        """Low-severity risks don't get remediation cards."""
        risks = [{"severity": "low", "risk_type": "active_complaint", "title": "Minor"}]
        cards = compute_remediation_roadmap(risks, [], sample_templates)
        assert len(cards) == 0

    def test_unknown_type_graceful(self, sample_templates):
        """Risk type not in templates returns no card."""
        risks = [{"severity": "high", "risk_type": "unknown_type", "title": "Mystery"}]
        cards = compute_remediation_roadmap(risks, [], sample_templates)
        assert len(cards) == 0

    def test_whats_missing_generates_card(self, sample_templates):
        """Classification drift (moderate) from What's Missing generates remediation card."""
        whats_missing = [{"type": "classification_drift", "severity": "moderate", "title": "Use changed"}]
        cards = compute_remediation_roadmap([], whats_missing, sample_templates)
        assert len(cards) == 1
        assert cards[0]["risk_type"] == "classification_drift"

    def test_card_has_required_fields(self, sample_templates):
        """Remediation cards have all required fields."""
        risks = [{"severity": "high", "risk_type": "active_complaint", "title": "Test"}]
        cards = compute_remediation_roadmap(risks, [], sample_templates)
        card = cards[0]
        assert "what_at_stake" in card
        assert "options" in card
        assert "sources" in card
        assert "severity" in card
        assert "title" in card

    def test_moderate_risk_generates_card(self, sample_templates):
        """Moderate-severity risk also gets a remediation card."""
        risks = [{"severity": "moderate", "risk_type": "active_complaint", "title": "Moderate issue"}]
        cards = compute_remediation_roadmap(risks, [], sample_templates)
        assert len(cards) == 1

    def test_both_risks_and_whats_missing_combined(self, sample_templates):
        """Cards from both risk items and What's Missing are combined."""
        risks = [{"severity": "high", "risk_type": "active_complaint", "title": "Complaint"}]
        whats_missing = [{"type": "classification_drift", "severity": "moderate", "title": "Drift"}]
        cards = compute_remediation_roadmap(risks, whats_missing, sample_templates)
        assert len(cards) == 2
        types = {c["risk_type"] for c in cards}
        assert types == {"active_complaint", "classification_drift"}


class TestExtendedConsultantFactors:
    """Test new consultant signal factors for owner context."""

    def test_classification_mismatch_adds_points(self):
        """Classification drift adds +2, dwelling unit change adds +1 more."""
        whats_missing = [{
            "type": "classification_drift",
            "severity": "moderate",
            "evidence": {"old_use": "1 family dwelling", "new_use": "2 family dwelling"},
        }]
        factors = compute_extended_consultant_factors(whats_missing)
        total = sum(f["points"] for f in factors)
        assert total >= 2  # +2 for mismatch, +1 for multi-agency

    def test_dwelling_unit_change_adds_multi_agency(self):
        """Dwelling unit change specifically adds the multi-agency factor."""
        whats_missing = [{
            "type": "classification_drift",
            "severity": "moderate",
            "evidence": {"old_use": "1 family dwelling", "new_use": "2 family dwelling"},
        }]
        factors = compute_extended_consultant_factors(whats_missing)
        labels = [f["label"] for f in factors]
        assert "Multi-agency review required (dwelling unit change)" in labels

    def test_no_mismatch_no_extra_points(self):
        """Clean whats_missing adds 0 points."""
        factors = compute_extended_consultant_factors([])
        assert len(factors) == 0

    def test_non_dwelling_drift_no_multi_agency(self):
        """Classification drift not involving dwelling units does not add multi-agency."""
        whats_missing = [{
            "type": "classification_drift",
            "severity": "moderate",
            "evidence": {"old_use": "office", "new_use": "retail"},
        }]
        factors = compute_extended_consultant_factors(whats_missing)
        labels = [f["label"] for f in factors]
        assert "Use classification mismatch detected" in labels
        assert "Multi-agency review required (dwelling unit change)" not in labels
        total = sum(f["points"] for f in factors)
        assert total == 2


class TestKBCitations:
    """Test knowledge base citation attachment."""

    def test_complaint_risk_gets_citations(self):
        """Active complaint risk gets relevant KB citations."""
        risks = [{"risk_type": "active_complaint", "severity": "high", "title": "Test"}]
        attach_kb_citations(risks, [])
        assert len(risks[0]["kb_citations"]) > 0

    def test_no_risk_type_gets_empty_citations(self):
        """Item with unknown risk_type gets empty citations."""
        risks = [{"risk_type": "unknown", "severity": "high", "title": "Test"}]
        attach_kb_citations(risks, [])
        assert risks[0]["kb_citations"] == []

    def test_remediation_cards_get_citations(self):
        """Remediation cards also get annotated with citations."""
        cards = [{"risk_type": "classification_drift", "severity": "moderate", "title": "Drift"}]
        attach_kb_citations([], cards)
        assert len(cards[0]["kb_citations"]) > 0
        concepts = [c["concept"] for c in cards[0]["kb_citations"]]
        assert "use_classification" in concepts

    def test_multiple_items_all_annotated(self):
        """All items in list get kb_citations added."""
        risks = [
            {"risk_type": "active_complaint", "severity": "high", "title": "A"},
            {"risk_type": "active_violation", "severity": "high", "title": "B"},
        ]
        attach_kb_citations(risks, [])
        assert "kb_citations" in risks[0]
        assert "kb_citations" in risks[1]
        assert len(risks[0]["kb_citations"]) > 0
        assert len(risks[1]["kb_citations"]) > 0


class TestNewReportLinks:
    """Test new URL builder methods added for Owner Mode."""

    def test_admin_bulletin_url(self):
        url = ReportLinks.admin_bulletin("AB-004")
        assert "sf.gov" in url

    def test_state_legislation_url(self):
        url = ReportLinks.state_legislation("202320240AB2533")
        assert "leginfo.legislature" in url
        assert "202320240AB2533" in url

    def test_dbi_contact_url(self):
        url = ReportLinks.dbi_contact()
        assert "sf.gov" in url
        assert "building-inspection" in url

    def test_planning_adu_url(self):
        url = ReportLinks.planning_adu()
        assert "sfplanning.org" in url
