"""Unit tests for severity scoring model — pure functions, no DB needed."""

from datetime import date, timedelta

import pytest

from src.severity import (
    PermitInput,
    SeverityResult,
    classify_description,
    score_permit,
    score_permits_batch,
    DESCRIPTION_CATEGORY_KEYWORDS,
    CATEGORY_RISK_SCORES,
    EXPECTED_INSPECTIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date(2026, 2, 23)


def _make_permit(**kwargs) -> PermitInput:
    """Build a PermitInput with sensible defaults."""
    defaults = {
        "permit_number": "TEST001",
        "status": "issued",
        "permit_type_definition": "additions alterations or repairs",
        "description": "general interior renovation",
        "filed_date": TODAY - timedelta(days=90),
        "issued_date": TODAY - timedelta(days=30),
        "status_date": TODAY - timedelta(days=10),
        "estimated_cost": 50_000,
        "inspection_count": 0,
    }
    defaults.update(kwargs)
    return PermitInput(**defaults)


# ---------------------------------------------------------------------------
# classify_description tests
# ---------------------------------------------------------------------------

class TestClassifyDescription:
    """Tests for keyword-based description classification."""

    def test_seismic(self):
        assert classify_description("seismic retrofit of foundation") == "seismic_structural"

    def test_fire_safety(self):
        assert classify_description("install fire sprinkler system") == "fire_safety"

    def test_adu(self):
        assert classify_description("construct accessory dwelling unit") == "adu"

    def test_new_construction(self):
        assert classify_description("erect a new building") == "new_construction"

    def test_kitchen_bath(self):
        assert classify_description("kitchen remodel with new cabinets") == "kitchen_bath"

    def test_electrical(self):
        assert classify_description("panel upgrade 200A service") == "electrical"

    def test_plumbing(self):
        assert classify_description("replace water heater") == "plumbing"

    def test_structural(self):
        assert classify_description("new retaining wall at rear") == "structural"

    def test_windows_doors(self):
        assert classify_description("replace 6 windows") == "windows_doors"

    def test_reroofing(self):
        assert classify_description("reroof existing residence") == "reroofing"

    def test_solar(self):
        assert classify_description("install rooftop solar panels photovoltaic") == "solar"

    def test_demolition(self):
        assert classify_description("demolition of existing structure") == "demolition"

    def test_general_fallback(self):
        assert classify_description("paint exterior walls") == "general"

    def test_uses_permit_type_definition(self):
        """Falls back to permit_type_definition if description doesn't match."""
        result = classify_description("misc work", permit_type_def="demolitions")
        assert result == "demolition"

    def test_case_insensitive(self):
        assert classify_description("SEISMIC RETROFIT") == "seismic_structural"

    def test_all_categories_have_keywords(self):
        """Every category in the keywords dict has at least 2 keywords."""
        for cat, kws in DESCRIPTION_CATEGORY_KEYWORDS.items():
            assert len(kws) >= 2, f"{cat} has fewer than 2 keywords"

    def test_all_categories_have_risk_scores(self):
        """Every category has a corresponding risk score."""
        for cat in DESCRIPTION_CATEGORY_KEYWORDS:
            assert cat in CATEGORY_RISK_SCORES, f"{cat} missing from CATEGORY_RISK_SCORES"

    def test_all_categories_have_expected_inspections(self):
        """Every category has expected inspection counts."""
        for cat in DESCRIPTION_CATEGORY_KEYWORDS:
            assert cat in EXPECTED_INSPECTIONS, f"{cat} missing from EXPECTED_INSPECTIONS"


# ---------------------------------------------------------------------------
# score_permit — dimension tests
# ---------------------------------------------------------------------------

class TestInspectionActivityDimension:
    """Tests for the inspection activity dimension."""

    def test_filed_permit_no_penalty(self):
        """Filed permits don't need inspections — score should be 0."""
        p = _make_permit(status="filed", issued_date=None, inspection_count=0)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["inspection_activity"]["score"] == 0.0

    def test_issued_just_issued_no_penalty(self):
        """Recently issued permits (<30d) shouldn't be penalized."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=10),
            inspection_count=0,
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["inspection_activity"]["score"] == 0.0

    def test_issued_stale_no_inspections(self):
        """Issued permit with no inspections after significant time should score high."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=400),
            inspection_count=0,
            description="seismic retrofit",
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["inspection_activity"]["score"] > 50

    def test_complete_zero_inspections_life_safety(self):
        """Completed life-safety permit with 0 inspections = very concerning."""
        p = _make_permit(
            status="complete",
            description="seismic retrofit",
            inspection_count=0,
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["inspection_activity"]["score"] >= 80

    def test_complete_with_adequate_inspections(self):
        """Completed permit with expected inspections should score low."""
        p = _make_permit(
            status="complete",
            description="kitchen remodel",
            inspection_count=5,
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["inspection_activity"]["score"] == 0.0


class TestAgeStaleness:
    """Tests for the age/staleness dimension."""

    def test_fresh_permit(self):
        """Recently filed permit should score low."""
        p = _make_permit(
            filed_date=TODAY - timedelta(days=30),
            status_date=TODAY - timedelta(days=5),
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["age_staleness"]["score"] < 10

    def test_old_permit(self):
        """4-year-old permit should score near max."""
        p = _make_permit(
            filed_date=TODAY - timedelta(days=1500),
            status_date=TODAY - timedelta(days=400),
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["age_staleness"]["score"] > 80

    def test_stalled_permit(self):
        """Permit with no activity in 200+ days gets staleness boost."""
        p = _make_permit(
            filed_date=TODAY - timedelta(days=400),
            status_date=TODAY - timedelta(days=200),
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["age_staleness"]["score"] > 30

    def test_completed_permit_reduced(self):
        """Completed permits get age reduced by 90%."""
        p = _make_permit(
            status="complete",
            filed_date=TODAY - timedelta(days=1000),
            status_date=TODAY - timedelta(days=10),
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["age_staleness"]["score"] < 15


class TestExpirationProximity:
    """Tests for the expiration proximity dimension."""

    def test_non_issued_no_score(self):
        """Only issued permits should be scored for expiration."""
        p = _make_permit(status="filed", issued_date=None)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 0.0

    def test_recently_issued(self):
        """Recently issued permit should have very low expiration score."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=30),
            estimated_cost=50_000,  # 360-day validity, 330 days remaining
        )
        result = score_permit(p, today=TODAY)
        # Small non-zero score from being within last year — acceptable
        assert result.dimensions["expiration_proximity"]["score"] < 10

    def test_freshly_issued_high_cost_zero(self):
        """High-cost permit issued 30 days ago has lots of runway — near 0."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=30),
            estimated_cost=200_000,  # 1080-day validity, 1050 days remaining
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 0.0

    def test_expired_permit(self):
        """Expired permit should score 100."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=400),
            estimated_cost=50_000,  # 360-day validity
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 100.0

    def test_expiring_soon(self):
        """Permit expiring within 30 days should score 90."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=340),
            estimated_cost=50_000,  # 360-day validity → 20 days left
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 90.0

    def test_expiring_90_days(self):
        """Permit expiring in 60 days should score 70."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=300),
            estimated_cost=50_000,  # 360-day validity → 60 days left
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 70.0

    def test_high_cost_longer_validity(self):
        """$200k permit has 1080-day validity — no expiration pressure at 300 days."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=300),
            estimated_cost=200_000,  # 1080-day validity
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 0.0

    def test_demolition_short_validity(self):
        """Demolition permits only have 180 days."""
        p = _make_permit(
            status="issued",
            issued_date=TODAY - timedelta(days=200),
            permit_type_definition="demolitions",
            description="demolish structure",
            estimated_cost=50_000,
        )
        result = score_permit(p, today=TODAY)
        assert result.dimensions["expiration_proximity"]["score"] == 100.0


class TestCostTier:
    """Tests for the cost tier dimension."""

    def test_zero_cost(self):
        p = _make_permit(estimated_cost=0)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 0.0

    def test_small_cost(self):
        p = _make_permit(estimated_cost=10_000)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 10.0

    def test_medium_cost(self):
        p = _make_permit(estimated_cost=100_000)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 20.0

    def test_high_cost(self):
        p = _make_permit(estimated_cost=1_000_000)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 80.0

    def test_very_high_cost(self):
        p = _make_permit(estimated_cost=3_000_000)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 100.0

    def test_revised_cost_preferred(self):
        """When revised_cost is set, it should be used over estimated_cost."""
        p = _make_permit(estimated_cost=10_000, revised_cost=2_500_000)
        result = score_permit(p, today=TODAY)
        assert result.dimensions["cost_tier"]["score"] == 100.0


class TestCategoryRisk:
    """Tests for the category risk dimension."""

    def test_seismic_highest(self):
        p = _make_permit(description="seismic retrofit")
        result = score_permit(p, today=TODAY)
        assert result.dimensions["category_risk"]["score"] == 100.0

    def test_reroofing_lowest(self):
        p = _make_permit(description="reroof existing residence")
        result = score_permit(p, today=TODAY)
        assert result.dimensions["category_risk"]["score"] == 10.0

    def test_general_fallback(self):
        p = _make_permit(description="paint exterior walls")
        result = score_permit(p, today=TODAY)
        assert result.dimensions["category_risk"]["score"] == 30.0


# ---------------------------------------------------------------------------
# Tier boundary tests
# ---------------------------------------------------------------------------

class TestTierBoundaries:
    """Tests for tier classification at exact boundaries."""

    def test_score_80_is_critical(self):
        """An expired, old, high-cost, life-safety permit with 0 inspections should be CRITICAL."""
        # Expired: $50k permit, 360-day validity, issued 400 days ago
        # Old: filed 1500 days ago
        # Stale: no activity in 300 days
        # Life-safety: seismic
        p = _make_permit(
            status="issued",
            filed_date=TODAY - timedelta(days=1500),
            issued_date=TODAY - timedelta(days=400),
            status_date=TODAY - timedelta(days=300),
            estimated_cost=50_000,
            description="seismic retrofit",
            inspection_count=0,
        )
        result = score_permit(p, today=TODAY)
        # Expired + old + life-safety + stale should push to CRITICAL
        assert result.tier == "CRITICAL"
        assert result.score >= 80

    def test_green_permit(self):
        """Fresh, low-cost, just-filed permit should be GREEN."""
        p = _make_permit(
            status="filed",
            filed_date=TODAY - timedelta(days=5),
            issued_date=None,
            status_date=TODAY - timedelta(days=2),
            estimated_cost=5_000,
            description="paint exterior",
            inspection_count=0,
        )
        result = score_permit(p, today=TODAY)
        assert result.tier == "GREEN"
        assert result.score < 20

    def test_medium_permit(self):
        """Moderately old, medium cost, issued permit should be MEDIUM or above."""
        p = _make_permit(
            status="issued",
            filed_date=TODAY - timedelta(days=500),
            issued_date=TODAY - timedelta(days=200),
            status_date=TODAY - timedelta(days=100),
            estimated_cost=200_000,
            description="kitchen remodel",
            inspection_count=0,
        )
        result = score_permit(p, today=TODAY)
        assert result.score >= 20  # At least LOW


# ---------------------------------------------------------------------------
# SeverityResult fields
# ---------------------------------------------------------------------------

class TestSeverityResult:
    """Tests for SeverityResult structure."""

    def test_has_all_dimensions(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        expected_dims = {
            "inspection_activity", "age_staleness", "expiration_proximity",
            "cost_tier", "category_risk",
        }
        assert set(result.dimensions.keys()) == expected_dims

    def test_dimensions_have_score_and_weight(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        for name, dim in result.dimensions.items():
            assert "score" in dim, f"{name} missing 'score'"
            assert "weight" in dim, f"{name} missing 'weight'"

    def test_top_driver_is_valid_dimension(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        assert result.top_driver in result.dimensions

    def test_explanation_not_empty(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        assert len(result.explanation) > 10

    def test_score_bounded(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        assert 0 <= result.score <= 100

    def test_tier_is_valid(self):
        p = _make_permit()
        result = score_permit(p, today=TODAY)
        assert result.tier in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "GREEN"}

    def test_category_set(self):
        p = _make_permit(description="seismic retrofit")
        result = score_permit(p, today=TODAY)
        assert result.category == "seismic_structural"


# ---------------------------------------------------------------------------
# PermitInput.from_dict
# ---------------------------------------------------------------------------

class TestPermitInputFromDict:
    """Tests for PermitInput.from_dict construction."""

    def test_basic_from_dict(self):
        d = {
            "permit_number": "202401010001",
            "status": "issued",
            "permit_type_definition": "additions alterations or repairs",
            "description": "kitchen remodel",
            "filed_date": "2024-01-15",
            "issued_date": "2024-06-01",
            "estimated_cost": 80000,
        }
        p = PermitInput.from_dict(d, inspection_count=3)
        assert p.permit_number == "202401010001"
        assert p.status == "issued"
        assert p.filed_date == date(2024, 1, 15)
        assert p.issued_date == date(2024, 6, 1)
        assert p.estimated_cost == 80000.0
        assert p.inspection_count == 3

    def test_from_dict_with_none_values(self):
        d = {
            "permit_number": "TEST",
            "status": None,
            "filed_date": None,
            "estimated_cost": None,
        }
        p = PermitInput.from_dict(d)
        assert p.status == ""
        assert p.filed_date is None
        assert p.estimated_cost is None

    def test_from_dict_date_parsing(self):
        """Handles various date formats."""
        d = {
            "permit_number": "TEST",
            "filed_date": "2024-03-15T00:00:00",  # ISO with time
            "issued_date": "2024-06-01",
        }
        p = PermitInput.from_dict(d)
        assert p.filed_date == date(2024, 3, 15)
        assert p.issued_date == date(2024, 6, 1)


# ---------------------------------------------------------------------------
# Batch scoring
# ---------------------------------------------------------------------------

class TestBatchScoring:
    """Tests for score_permits_batch."""

    def test_batch_returns_list(self):
        permits = [_make_permit(permit_number=f"P{i}") for i in range(5)]
        results = score_permits_batch(permits, today=TODAY)
        assert len(results) == 5
        assert all(isinstance(r, SeverityResult) for r in results)

    def test_batch_consistent_with_single(self):
        """Batch should produce identical results to individual scoring."""
        p = _make_permit()
        single = score_permit(p, today=TODAY)
        batch = score_permits_batch([p], today=TODAY)
        assert batch[0].score == single.score
        assert batch[0].tier == single.tier

    def test_empty_batch(self):
        results = score_permits_batch([], today=TODAY)
        assert results == []
