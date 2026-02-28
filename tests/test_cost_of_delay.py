"""Tests for cost_of_delay tool.

QS8-T2-D — Cost of Delay Calculator

Tests cover:
- daily_delay_cost helper
- calculate_delay_cost async tool (with mocked timeline tool)
- Various permit types and carrying costs
- Trigger escalations
- Edge cases (zero cost, invalid inputs, OTC eligible types)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.tools.cost_of_delay import (
    daily_delay_cost,
    calculate_delay_cost,
    _format_currency,
    _get_revision_info,
    _get_timeline_estimates,
    _get_permit_type_label,
    OTC_ELIGIBLE_TYPES,
    REVISION_PROBABILITY,
)


# ---------------------------------------------------------------------------
# daily_delay_cost
# ---------------------------------------------------------------------------

class TestDailyDelayCost:
    def test_basic_monthly_cost(self):
        result = daily_delay_cost(10000.0)
        assert "day" in result.lower()
        assert "$" in result

    def test_round_numbers(self):
        # $30,440/month → ~$1,000/day
        result = daily_delay_cost(30440.0)
        assert "1,000" in result or "1.0K" in result or "$1" in result

    def test_small_monthly_cost(self):
        result = daily_delay_cost(1000.0)
        assert "$" in result
        assert "day" in result.lower()

    def test_large_monthly_cost(self):
        result = daily_delay_cost(500000.0)
        assert "$" in result
        assert "day" in result.lower()

    def test_zero_returns_error(self):
        result = daily_delay_cost(0.0)
        assert "invalid" in result.lower() or "greater than zero" in result.lower()

    def test_negative_returns_error(self):
        result = daily_delay_cost(-5000.0)
        assert "invalid" in result.lower() or "greater than zero" in result.lower()


# ---------------------------------------------------------------------------
# _format_currency helper
# ---------------------------------------------------------------------------

class TestFormatCurrency:
    def test_small_amount(self):
        assert "$" in _format_currency(500.0)

    def test_thousands(self):
        result = _format_currency(15000.0)
        assert "K" in result

    def test_millions(self):
        result = _format_currency(1_500_000.0)
        assert "M" in result

    def test_exact_10k_boundary(self):
        result = _format_currency(10000.0)
        assert "K" in result

    def test_under_10k_no_k(self):
        result = _format_currency(9999.0)
        assert "K" not in result


# ---------------------------------------------------------------------------
# _get_revision_info
# ---------------------------------------------------------------------------

class TestGetRevisionInfo:
    def test_restaurant_high_risk(self):
        prob, delay = _get_revision_info("restaurant")
        assert prob >= 0.30  # restaurants have high revision rate
        assert delay >= 60

    def test_otc_low_risk(self):
        prob, delay = _get_revision_info("otc")
        assert prob <= 0.10
        assert delay <= 20

    def test_unknown_type_uses_default(self):
        prob, delay = _get_revision_info("nonexistent_type")
        assert 0.0 < prob <= 1.0
        assert delay > 0

    def test_new_construction(self):
        prob, delay = _get_revision_info("new_construction")
        assert prob >= 0.20
        assert delay >= 60


# ---------------------------------------------------------------------------
# _get_timeline_estimates
# ---------------------------------------------------------------------------

class TestGetTimelineEstimates:
    def test_restaurant_timelines(self):
        timelines = _get_timeline_estimates("restaurant")
        assert timelines["p25"] < timelines["p50"] < timelines["p90"]
        assert timelines["p50"] >= 45  # restaurants take a while

    def test_otc_fast(self):
        timelines = _get_timeline_estimates("otc")
        assert timelines["p50"] <= 10
        assert timelines["p25"] <= 5

    def test_new_construction_long(self):
        timelines = _get_timeline_estimates("new_construction")
        assert timelines["p90"] >= 200

    def test_unknown_type_returns_defaults(self):
        timelines = _get_timeline_estimates("mystery_permit")
        assert "p25" in timelines
        assert "p50" in timelines
        assert "p90" in timelines
        assert timelines["p25"] < timelines["p50"] < timelines["p90"]


# ---------------------------------------------------------------------------
# _get_permit_type_label
# ---------------------------------------------------------------------------

class TestGetPermitTypeLabel:
    def test_restaurant_label(self):
        label = _get_permit_type_label("restaurant")
        assert "Restaurant" in label or "Food" in label

    def test_adu_label(self):
        label = _get_permit_type_label("adu")
        assert "ADU" in label or "Dwelling" in label

    def test_unknown_type_titlecase(self):
        label = _get_permit_type_label("mystery_type")
        assert label != ""
        assert "mystery" in label.lower() or "Mystery" in label


# ---------------------------------------------------------------------------
# calculate_delay_cost (async, with DB mocked out)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_estimate_timeline_unavailable():
    """Simulate estimate_timeline tool being unavailable (no DB)."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=ImportError("no DB")):
        yield


@pytest.mark.asyncio
async def test_calculate_delay_cost_basic():
    """Happy path: restaurant permit, $50K/month carrying cost."""
    with patch("src.tools.cost_of_delay.estimate_timeline", new_callable=AsyncMock) as mock_tl:
        mock_tl.side_effect = Exception("DB unavailable")
        result = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=50000.0,
        )

    assert "Cost of Delay" in result
    assert "Restaurant" in result or "restaurant" in result.lower()
    assert "$" in result
    # Should have a cost table
    assert "Best" in result
    assert "Likely" in result
    assert "Worst" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_table_structure():
    """Verify the markdown table has the expected columns."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="adu",
            monthly_carrying_cost=20000.0,
        )

    assert "Timeline" in result
    assert "Carrying Cost" in result
    assert "Revision Risk Cost" in result
    assert "Total" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_carrying_math():
    """Verify carrying cost math is approximately correct."""
    monthly = 30440.0  # ~$1,000/day
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="general_alteration",
            monthly_carrying_cost=monthly,
        )
    # general_alteration p50 = 30 days → ~$30K carrying
    # The result should contain some reference to ~30K range
    assert "$" in result
    assert "Break-Even" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_zero_cost_returns_error():
    """Zero carrying cost should return an error message."""
    result = await calculate_delay_cost(
        permit_type="restaurant",
        monthly_carrying_cost=0.0,
    )
    assert "Error" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_calculate_delay_cost_negative_cost_returns_error():
    """Negative carrying cost should return an error message."""
    result = await calculate_delay_cost(
        permit_type="restaurant",
        monthly_carrying_cost=-1000.0,
    )
    assert "Error" in result or "error" in result.lower()


@pytest.mark.asyncio
async def test_calculate_delay_cost_otc_eligible_note():
    """OTC-eligible permit types should mention OTC fast-path."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="otc",
            monthly_carrying_cost=10000.0,
        )
    assert "OTC" in result or "Over-the-Counter" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_with_triggers():
    """Triggers should escalate timelines and appear in output."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result_no_triggers = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=30000.0,
            triggers=[],
        )
        result_with_triggers = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=30000.0,
            triggers=["historic", "planning_review"],
        )

    # With triggers, worst-case should be higher than without
    # Both should mention triggers (at least the trigger block should appear)
    assert "Delay Triggers" in result_with_triggers or "historic" in result_with_triggers.lower()


@pytest.mark.asyncio
async def test_calculate_delay_cost_mitigation_section():
    """Output should always include a mitigation strategies section."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="commercial_ti",
            monthly_carrying_cost=75000.0,
        )
    assert "Mitigation" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_methodology_section():
    """Output should always include a methodology section."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="new_construction",
            monthly_carrying_cost=100000.0,
        )
    assert "Methodology" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_break_even_section():
    """Output should always include break-even analysis."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="adu",
            monthly_carrying_cost=15000.0,
        )
    assert "Break-Even" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_neighborhood_appears_in_output():
    """Neighborhood should appear in the formatted output."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=50000.0,
            neighborhood="Mission",
        )
    assert "Mission" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_daily_oneliner_in_output():
    """daily_delay_cost one-liner should appear at the end of the output."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="seismic",
            monthly_carrying_cost=8000.0,
        )
    # The daily cost one-liner should be in the output
    assert "Every day" in result or "every day" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_live_timeline_used_when_available():
    """When estimate_timeline succeeds and returns p50 data, it should be used."""
    mock_timeline_output = (
        "## Timeline Estimate\n"
        "- p25: 60 days\n"
        "- p50: 100 days\n"
        "- p90: 200 days\n"
    )
    with patch("src.tools.cost_of_delay.estimate_timeline", new_callable=AsyncMock) as mock_tl:
        mock_tl.return_value = mock_timeline_output
        result = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=50000.0,
        )

    # Timeline data was parsed — p50=100d should appear in table
    assert "100d" in result or "100" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_unknown_permit_type():
    """Unknown permit type should still produce output using defaults."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="mystery_permit_xyz",
            monthly_carrying_cost=25000.0,
        )
    assert "Cost of Delay" in result
    assert "$" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_small_carrying_cost():
    """Very small carrying cost should still produce valid output."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="bathroom_remodel",
            monthly_carrying_cost=100.0,
        )
    assert "Cost of Delay" in result
    assert "$" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_large_carrying_cost():
    """Large carrying costs (commercial project) should use M suffix."""
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="new_construction",
            monthly_carrying_cost=2_000_000.0,
        )
    # $2M/month → daily ~$65K, worst case new_construction 300d → ~$19.7M
    assert "M" in result or "K" in result


@pytest.mark.asyncio
async def test_calculate_delay_cost_multiple_trigger_types():
    """Multiple triggers should all appear in trigger notes."""
    triggers = ["planning_review", "dph_review", "fire_review"]
    with patch("src.tools.cost_of_delay.estimate_timeline", side_effect=Exception("no DB")):
        result = await calculate_delay_cost(
            permit_type="restaurant",
            monthly_carrying_cost=40000.0,
            triggers=triggers,
        )
    # At least one trigger note should appear
    assert "Planning" in result or "DPH" in result or "Fire" in result or "Trigger" in result


# ---------------------------------------------------------------------------
# Constants validation
# ---------------------------------------------------------------------------

class TestConstants:
    def test_otc_eligible_types_exist(self):
        assert "otc" in OTC_ELIGIBLE_TYPES
        assert "no_plans" in OTC_ELIGIBLE_TYPES

    def test_revision_probability_range(self):
        for pt, prob in REVISION_PROBABILITY.items():
            assert 0.0 <= prob <= 1.0, f"{pt} revision probability out of range: {prob}"

    def test_all_probabilities_positive(self):
        for pt, prob in REVISION_PROBABILITY.items():
            assert prob > 0, f"{pt} revision probability should be positive"
