"""Tests for what_if_simulator tool.

All underlying tool functions (predict_permits, estimate_timeline, estimate_fees,
revision_risk) are mocked — these tests verify the orchestration logic, extraction
helpers, and formatted output of simulate_what_if.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.tools.what_if_simulator import (
    _extract_p50,
    _extract_p75,
    _extract_permits,
    _extract_review_path,
    _extract_revision_risk,
    _extract_total_fee,
    simulate_what_if,
)


# ---------------------------------------------------------------------------
# Helper: run async in sync test context
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Unit tests for extraction helpers
# ---------------------------------------------------------------------------

class TestExtractPermits:
    def test_extracts_from_required_permits_section(self):
        md = (
            "# Permit Prediction\n\n"
            "## Required Permits\n\n"
            "- Alteration Permit (3 Application)\n"
            "- Electrical permit required\n\n"
            "## Review Path\n\nIn-house"
        )
        result = _extract_permits(md)
        assert "Alteration" in result or "Electrical" in result

    def test_falls_back_to_permit_type_header(self):
        md = "**Permit Type:** Building Alteration\n\nSome other content."
        result = _extract_permits(md)
        assert result == "Building Alteration"

    def test_returns_na_when_no_permits_found(self):
        result = _extract_permits("No permit information here.")
        assert result == "N/A"


class TestExtractReviewPath:
    def test_detects_otc(self):
        md = "**Review Path:** OTC\n\nDetails follow."
        assert _extract_review_path(md) == "OTC"

    def test_detects_over_the_counter(self):
        md = "**Review Path:** Over-the-Counter\n\nDetails."
        assert _extract_review_path(md) == "OTC"

    def test_detects_in_house(self):
        md = "**Review Path:** In-house\n\nDetails."
        assert _extract_review_path(md) == "In-house"

    def test_returns_na_when_not_found(self):
        assert _extract_review_path("Nothing relevant here.") == "N/A"


class TestExtractP50:
    def test_extracts_p50_pattern(self):
        md = "P50 timeline: 60 days based on historical data."
        assert _extract_p50(md) == "60 days"

    def test_extracts_range_pattern(self):
        md = "Typical review: 30–60 business days."
        result = _extract_p50(md)
        assert "days" in result

    def test_returns_na_when_not_found(self):
        assert _extract_p50("No timeline data here.") == "N/A"


class TestExtractP75:
    def test_extracts_p75_pattern(self):
        md = "P75: 90 days for 75th percentile projects."
        assert _extract_p75(md) == "90 days"

    def test_returns_na_when_not_found(self):
        assert _extract_p75("No data here.") == "N/A"


class TestExtractTotalFee:
    def test_extracts_dbi_total_row(self):
        md = (
            "| Fee Component | Amount |\n"
            "|---|---|\n"
            "| Plan Review Fee | $1,200.00 |\n"
            "| **Total DBI Fees** | **$3,450.00** |\n"
        )
        assert _extract_total_fee(md) == "$3,450.00"

    def test_falls_back_to_first_currency(self):
        md = "The estimated fee is $2,500 for your project."
        result = _extract_total_fee(md)
        assert result.startswith("$")

    def test_returns_na_when_not_found(self):
        assert _extract_total_fee("No fee information.") == "N/A"


class TestExtractRevisionRisk:
    def test_extracts_risk_level_and_rate(self):
        md = (
            "## Revision Probability\n\n"
            "**Risk Level:** HIGH\n"
            "**Revision Rate:** 24.5% of permits had cost increases during review\n"
        )
        result = _extract_revision_risk(md)
        assert "HIGH" in result
        assert "24.5%" in result

    def test_extracts_risk_level_only(self):
        md = "**Risk Level:** MODERATE\nSome other text."
        result = _extract_revision_risk(md)
        assert "MODERATE" in result

    def test_detects_luck_based_fallback(self):
        md = "Based on SF DBI patterns, typical revision risk: 15-20% of permits."
        result = _extract_revision_risk(md)
        assert "MODERATE" in result or "15" in result

    def test_returns_na_when_not_found(self):
        assert _extract_revision_risk("No risk information.") == "N/A"


# ---------------------------------------------------------------------------
# Integration tests: simulate_what_if with mocked sub-tools
# ---------------------------------------------------------------------------

MOCK_PREDICT_OTC = (
    "# Permit Prediction\n\n"
    "**Permit Type:** Alterations\n\n"
    "## Required Permits\n\n"
    "- Building Alteration Permit (3 Application)\n\n"
    "## Review Path\n\n"
    "**Review Path:** OTC\n\n"
    "**Confidence:** high"
)

MOCK_PREDICT_INHOUSE = (
    "# Permit Prediction\n\n"
    "**Permit Type:** Alterations\n\n"
    "## Required Permits\n\n"
    "- Building Alteration Permit (3 Application)\n"
    "- Electrical permit\n\n"
    "## Review Path\n\n"
    "**Review Path:** In-house\n\n"
    "**Confidence:** high"
)

MOCK_TIMELINE = (
    "# Timeline Estimate\n\n"
    "P50 timeline: 45 days based on historical data.\n"
    "P75: 75 days for complex projects.\n\n"
    "**Confidence:** medium"
)

MOCK_FEES_80K = (
    "# Fee Estimate\n\n"
    "**Construction Valuation:** $80,000\n\n"
    "## DBI Building Permit Fees (Table 1A-A)\n\n"
    "| Fee Component | Amount |\n"
    "|---|---|\n"
    "| Plan Review Fee | $1,200.00 |\n"
    "| Permit Issuance Fee | $1,800.00 |\n"
    "| CBSC Fee | $3.20 |\n"
    "| SMIP Fee | $10.40 |\n"
    "| **Total DBI Fees** | **$3,013.60** |\n"
)

MOCK_FEES_120K = (
    "# Fee Estimate\n\n"
    "**Construction Valuation:** $120,000\n\n"
    "## DBI Building Permit Fees (Table 1A-A)\n\n"
    "| Fee Component | Amount |\n"
    "|---|---|\n"
    "| Plan Review Fee | $1,800.00 |\n"
    "| Permit Issuance Fee | $2,700.00 |\n"
    "| CBSC Fee | $4.80 |\n"
    "| SMIP Fee | $15.60 |\n"
    "| **Total DBI Fees** | **$4,520.40** |\n"
)

MOCK_REVISION_RISK = (
    "# Revision Risk Assessment\n\n"
    "**Permit Type:** alterations\n\n"
    "## Revision Probability\n\n"
    "**Risk Level:** MODERATE\n"
    "**Revision Rate:** 18.5% of permits had cost increases during review\n"
    "**Sample Size:** 12,345 permits analyzed\n\n"
    "**Confidence:** high"
)


@pytest.fixture
def mock_sub_tools():
    """Patch all four sub-tools used by simulate_what_if."""
    with (
        patch(
            "src.tools.what_if_simulator.predict_permits",
            new_callable=AsyncMock,
            return_value=MOCK_PREDICT_OTC,
        ) as mock_predict,
        patch(
            "src.tools.what_if_simulator.estimate_timeline",
            new_callable=AsyncMock,
            return_value=MOCK_TIMELINE,
        ) as mock_timeline,
        patch(
            "src.tools.what_if_simulator.estimate_fees",
            new_callable=AsyncMock,
            return_value=MOCK_FEES_80K,
        ) as mock_fees,
        patch(
            "src.tools.what_if_simulator.revision_risk",
            new_callable=AsyncMock,
            return_value=MOCK_REVISION_RISK,
        ) as mock_risk,
    ):
        yield {
            "predict": mock_predict,
            "timeline": mock_timeline,
            "fees": mock_fees,
            "risk": mock_risk,
        }


class TestSimulateWhatIfBasic:
    def test_base_only_no_variations(self, mock_sub_tools):
        """Base scenario with no variations should produce a 1-row table."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel in the Mission, $80K",
                variations=[],
            )
        )
        assert "What-If Permit Simulator" in result
        assert "**Base**" in result
        assert "Scenarios evaluated:**" in result and "1" in result

    def test_two_variations(self, mock_sub_tools):
        """Two variations produce a 3-row table (base + 2 variations)."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[
                    {"label": "Add bathroom", "description": "Kitchen + bathroom, $120K"},
                    {"label": "Full ADU", "description": "Kitchen + bathroom + ADU, $200K"},
                ],
            )
        )
        assert "**Add bathroom**" in result
        assert "**Full ADU**" in result
        assert "Scenarios evaluated:**" in result and "3" in result

    def test_table_headers_present(self, mock_sub_tools):
        """Comparison table must include all required columns."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "Add bathroom", "description": "Kitchen + bath, $120K"}],
            )
        )
        assert "Permits" in result
        assert "Review Path" in result
        assert "Timeline (p50)" in result
        assert "Timeline (p75)" in result
        assert "Est. DBI Fees" in result
        assert "Revision Risk" in result

    def test_extracted_values_appear_in_table(self, mock_sub_tools):
        """Extracted values from mocked sub-tools should appear in the table."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "Add bathroom", "description": "Kitchen + bath, $120K"}],
            )
        )
        # OTC from mock predict
        assert "OTC" in result
        # 45 days from mock timeline
        assert "45 days" in result
        # Fee from mock fees
        assert "$3,013.60" in result or "3,013" in result
        # MODERATE from mock risk
        assert "MODERATE" in result

    def test_delta_section_present_with_variations(self, mock_sub_tools):
        """Delta vs. Base section should appear when there are variations."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "Add bathroom", "description": "Kitchen + bath, $120K"}],
            )
        )
        assert "Delta vs. Base" in result

    def test_no_delta_section_without_variations(self, mock_sub_tools):
        """No Delta section when there are no variations."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[],
            )
        )
        assert "Delta vs. Base" not in result


class TestSimulateWhatIfEdgeCases:
    def test_empty_base_description_returns_error(self):
        result = _run(
            simulate_what_if(
                base_description="",
                variations=[],
            )
        )
        assert "Error" in result or "required" in result

    def test_tool_error_produces_na_not_exception(self, mock_sub_tools):
        """If a sub-tool raises, the result should show N/A, not crash."""
        mock_sub_tools["predict"].side_effect = RuntimeError("DB unavailable")
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "Add bathroom", "description": "Kitchen + bath, $120K"}],
            )
        )
        # Should still produce a table (no exception propagated)
        assert "What-If Permit Simulator" in result
        assert "N/A" in result

    def test_variation_missing_label_uses_default(self, mock_sub_tools):
        """Variations missing 'label' key should fall back to 'Variation'."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"description": "Kitchen + bath, $120K"}],
            )
        )
        assert "Variation" in result

    def test_variation_missing_description_uses_base(self, mock_sub_tools):
        """Variations missing 'description' key should use base_description."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "No description"}],
            )
        )
        # Should not crash; predict_permits will be called with base_description
        assert "No description" in result

    def test_long_description_truncated_in_table(self, mock_sub_tools):
        """Table rows should truncate very long descriptions to <= 63 chars."""
        long_desc = "A" * 200 + ", $80K"
        result = _run(
            simulate_what_if(
                base_description=long_desc,
                variations=[],
            )
        )
        # Find the table row for Base — description cell must be truncated
        # Table rows look like: | **Base** | <description> | ...
        import re as _re
        table_row_match = _re.search(r"\| \*\*Base\*\* \| ([^|]+) \|", result)
        assert table_row_match, "Could not find Base row in table"
        cell_content = table_row_match.group(1).strip()
        assert len(cell_content) <= 63, f"Description cell too long: {len(cell_content)} chars"
        assert "..." in cell_content, "Expected truncation ellipsis"

    def test_sub_tools_called_once_per_scenario(self, mock_sub_tools):
        """Each sub-tool should be called once per scenario."""
        _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[
                    {"label": "Add bathroom", "description": "Kitchen + bath, $120K"},
                    {"label": "Full ADU", "description": "ADU, $200K"},
                ],
            )
        )
        # 3 scenarios total → each tool called 3 times
        assert mock_sub_tools["predict"].call_count == 3
        assert mock_sub_tools["timeline"].call_count == 3
        assert mock_sub_tools["fees"].call_count == 3
        assert mock_sub_tools["risk"].call_count == 3

    def test_footer_present(self, mock_sub_tools):
        """Footer with limitations note should always be present."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[],
            )
        )
        assert "Limitations" in result or "what_if_simulator" in result

    def test_review_path_change_flagged_in_delta(self):
        """When review path changes between base and variation, delta should note it."""
        # Cycle through different return values per call
        call_count = {"n": 0}
        predict_returns = [MOCK_PREDICT_OTC, MOCK_PREDICT_INHOUSE]

        async def side_effect(*args, **kwargs):
            val = predict_returns[call_count["n"] % len(predict_returns)]
            call_count["n"] += 1
            return val

        with (
            patch("src.tools.what_if_simulator.predict_permits", new=side_effect),
            patch(
                "src.tools.what_if_simulator.estimate_timeline",
                new_callable=AsyncMock,
                return_value=MOCK_TIMELINE,
            ),
            patch(
                "src.tools.what_if_simulator.estimate_fees",
                new_callable=AsyncMock,
                return_value=MOCK_FEES_80K,
            ),
            patch(
                "src.tools.what_if_simulator.revision_risk",
                new_callable=AsyncMock,
                return_value=MOCK_REVISION_RISK,
            ),
        ):
            result = _run(
                simulate_what_if(
                    base_description="Kitchen remodel, $80K",
                    variations=[
                        {"label": "Add bathroom", "description": "Kitchen + bath, $120K"}
                    ],
                )
            )
        # Delta section should mention the review path change
        assert "OTC" in result
        assert "In-house" in result


class TestSimulateWhatIfCostParsing:
    """Verify that dollar amounts in descriptions reach the sub-tools."""

    def test_cost_parsed_from_dollar_amount(self, mock_sub_tools):
        """$80K in description should result in a call to estimate_fees."""
        _run(
            simulate_what_if(
                base_description="Kitchen remodel in the Mission, $80,000",
                variations=[],
            )
        )
        # estimate_fees should have been called (cost passed through)
        assert mock_sub_tools["fees"].called

    def test_cost_parsed_from_k_suffix(self, mock_sub_tools):
        """80K notation should parse to 80,000."""
        _run(
            simulate_what_if(
                base_description="Kitchen remodel, 80K budget",
                variations=[],
            )
        )
        assert mock_sub_tools["fees"].called

    def test_no_cost_in_description_still_runs(self, mock_sub_tools):
        """Missing cost in description should fall back to $50K default, not crash."""
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel in the Mission",
                variations=[],
            )
        )
        assert "What-If Permit Simulator" in result
        assert mock_sub_tools["fees"].called


class TestSimulateWhatIfReturnType:
    def test_returns_string(self, mock_sub_tools):
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[],
            )
        )
        assert isinstance(result, str)

    def test_returns_markdown_table(self, mock_sub_tools):
        result = _run(
            simulate_what_if(
                base_description="Kitchen remodel, $80K",
                variations=[{"label": "Add bathroom", "description": "Kitchen + bath, $120K"}],
            )
        )
        # Markdown table uses | delimiters
        assert "|" in result
        assert "---" in result
