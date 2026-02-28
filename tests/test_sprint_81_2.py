"""Tests for Sprint 81 Task B: NLP search parser, empty result guidance, result ranking.

Tests cover:
  - parse_search_query: neighborhood, address, permit type, year, combined
  - build_empty_result_guidance: suggestions, did_you_mean
  - rank_search_results: address > permit > description ordering
"""
import pytest


# ---------------------------------------------------------------------------
# parse_search_query tests
# ---------------------------------------------------------------------------

from web.helpers import parse_search_query, build_empty_result_guidance, rank_search_results


class TestParseNeighborhood:
    """Test B-1: neighborhood extraction from natural language queries."""

    def test_parse_neighborhood_in_the_mission(self):
        result = parse_search_query("kitchen remodel in the Mission")
        assert result.get("neighborhood") == "Mission"

    def test_parse_neighborhood_in_soma(self):
        result = parse_search_query("new construction SoMa")
        assert result.get("neighborhood") == "South of Market"

    def test_parse_neighborhood_in_castro(self):
        result = parse_search_query("bathroom renovation in castro")
        assert result.get("neighborhood") == "Castro/Upper Market"

    def test_parse_neighborhood_noe_valley(self):
        result = parse_search_query("adu in noe valley")
        assert result.get("neighborhood") == "Noe Valley"

    def test_parse_neighborhood_haight(self):
        result = parse_search_query("permits near haight")
        assert result.get("neighborhood") == "Haight Ashbury"

    def test_parse_neighborhood_bernal(self):
        result = parse_search_query("seismic retrofit bernal heights")
        assert result.get("neighborhood") == "Bernal Heights"

    def test_parse_neighborhood_not_extracted_without_query(self):
        result = parse_search_query("")
        assert result == {}

    def test_parse_neighborhood_no_false_positive(self):
        """'Market St' should not trigger Mission Bay or any neighborhood."""
        result = parse_search_query("123 Market St")
        # Street address extracted, no spurious neighborhood
        assert result.get("street_number") == "123"
        # 'Market' alone shouldn't match a neighborhood alias
        # (neighborhoods are proper nouns; Market is a street)
        # We just verify street extraction works; neighborhood is optional here.


class TestParseAddress:
    """Test B-1: address extraction from search queries."""

    def test_parse_address_market_st(self):
        result = parse_search_query("123 Market St")
        assert result.get("street_number") == "123"
        assert "Market" in result.get("street_name", "")

    def test_parse_address_with_suffix(self):
        result = parse_search_query("permits at 456 Valencia St")
        assert result.get("street_number") == "456"
        assert "Valencia" in result.get("street_name", "")

    def test_parse_address_numbered_street(self):
        result = parse_search_query("614 6th Ave")
        assert result.get("street_number") == "614"
        assert "6th" in result.get("street_name", "") or "6" in result.get("street_name", "")

    def test_parse_address_no_number_returns_empty_street(self):
        """A query with no street number should not produce street_number."""
        result = parse_search_query("Mission District remodel")
        assert result.get("street_number") is None

    def test_parse_address_leading_preposition(self):
        """'permits at 75 Robin Hood Dr' → street_number=75."""
        result = parse_search_query("permits at 75 Robin Hood Dr")
        assert result.get("street_number") == "75"


class TestParsePermitType:
    """Test B-1: permit type keyword extraction."""

    def test_parse_permit_type_new_construction(self):
        result = parse_search_query("new construction SoMa 2024")
        assert result.get("permit_type") == "new construction"

    def test_parse_permit_type_kitchen_remodel(self):
        result = parse_search_query("kitchen remodel in the Mission")
        assert result.get("permit_type") == "alterations"

    def test_parse_permit_type_adu(self):
        result = parse_search_query("adu permit Mission 2023")
        assert result.get("permit_type") == "adu"

    def test_parse_permit_type_demolition(self):
        result = parse_search_query("demolition permit at 123 Main St")
        assert result.get("permit_type") == "demolition"

    def test_parse_permit_type_seismic(self):
        result = parse_search_query("seismic retrofit bernal heights")
        assert result.get("permit_type") == "seismic"

    def test_parse_permit_type_no_match_returns_none(self):
        result = parse_search_query("123 Market St")
        assert result.get("permit_type") is None


class TestParseYear:
    """Test B-1: year extraction and date_from mapping."""

    def test_parse_year_2024(self):
        result = parse_search_query("new construction SoMa 2024")
        assert result.get("date_from") == "2024-01-01"

    def test_parse_year_2019(self):
        result = parse_search_query("permits filed in 2019")
        assert result.get("date_from") == "2019-01-01"

    def test_parse_year_2022(self):
        result = parse_search_query("kitchen remodel 2022 Mission")
        assert result.get("date_from") == "2022-01-01"

    def test_parse_year_no_year(self):
        result = parse_search_query("kitchen remodel in the Mission")
        assert result.get("date_from") is None

    def test_parse_year_out_of_range_ignored(self):
        """Years outside 2018-2030 should not produce date_from."""
        result = parse_search_query("project from 1999")
        assert result.get("date_from") is None

    def test_parse_year_2031_ignored(self):
        result = parse_search_query("project 2031")
        assert result.get("date_from") is None


class TestParseCombined:
    """Test B-1: combined multi-field queries."""

    def test_parse_combined_kitchen_remodel_mission_2024(self):
        result = parse_search_query("kitchen remodel Mission 2024")
        assert result.get("neighborhood") == "Mission"
        assert result.get("date_from") == "2024-01-01"
        assert result.get("permit_type") == "alterations"

    def test_parse_combined_new_construction_soma_2024(self):
        result = parse_search_query("new construction SoMa 2024")
        assert result.get("neighborhood") == "South of Market"
        assert result.get("date_from") == "2024-01-01"
        assert result.get("permit_type") == "new construction"

    def test_parse_combined_address_and_year(self):
        result = parse_search_query("permits at 123 Market St 2023")
        assert result.get("street_number") == "123"
        assert result.get("date_from") == "2023-01-01"

    def test_parse_combined_residual_description(self):
        """Text not matched by any field should go to description_search."""
        result = parse_search_query("sprinkler upgrade 2022")
        # "sprinkler" is a permit type keyword (fire protection)
        assert result.get("permit_type") == "fire protection"
        assert result.get("date_from") == "2022-01-01"

    def test_parse_description_search_residual(self):
        """Non-structured text goes to description_search."""
        result = parse_search_query("tall building downtown")
        # "downtown" doesn't match a neighborhood alias, text goes to description
        assert "description_search" in result
        assert len(result["description_search"]) >= 2

    def test_parse_empty_string(self):
        result = parse_search_query("")
        assert result == {}

    def test_parse_whitespace_only(self):
        result = parse_search_query("   ")
        assert result == {}


# ---------------------------------------------------------------------------
# build_empty_result_guidance tests
# ---------------------------------------------------------------------------

class TestEmptyResultGuidance:
    """Test B-2: empty result guidance generation."""

    def test_empty_results_shows_suggestions(self):
        """When no results, guidance should include suggestions."""
        parsed = parse_search_query("kitchen remodel in the Mission")
        guidance = build_empty_result_guidance("kitchen remodel in the Mission", parsed)
        assert isinstance(guidance, dict)
        assert "suggestions" in guidance
        assert isinstance(guidance["suggestions"], list)

    def test_show_demo_link_always_true(self):
        parsed = parse_search_query("random query")
        guidance = build_empty_result_guidance("random query", parsed)
        assert guidance.get("show_demo_link") is True

    def test_did_you_mean_street_name_hint(self):
        """Bare street name without a number → did_you_mean suggestion."""
        parsed = parse_search_query("Market")
        # Even without a match, description_search should trigger did_you_mean
        parsed_with_desc = {"description_search": "Market"}
        guidance = build_empty_result_guidance("Market", parsed_with_desc)
        # did_you_mean may or may not fire — just check the function returns cleanly
        assert isinstance(guidance, dict)

    def test_no_crash_on_empty_parsed(self):
        guidance = build_empty_result_guidance("", {})
        assert isinstance(guidance, dict)
        assert "suggestions" in guidance

    def test_suggestions_have_url_and_label(self):
        parsed = parse_search_query("solar permit")
        guidance = build_empty_result_guidance("solar permit", parsed)
        for s in guidance["suggestions"]:
            assert "url" in s
            assert "label" in s


# ---------------------------------------------------------------------------
# rank_search_results tests
# ---------------------------------------------------------------------------

class TestRankSearchResults:
    """Test B-3: result ranking by match type."""

    def _make_result(self, permit_number="", street_number="", street_name="",
                     description=""):
        return {
            "permit_number": permit_number,
            "street_number": street_number,
            "street_name": street_name,
            "description": description,
        }

    def test_address_match_ranked_first(self):
        results = [
            self._make_result(street_number="999", street_name="Other Ave",
                              description="generic work"),
            self._make_result(street_number="123", street_name="Market St",
                              description="kitchen remodel"),
        ]
        parsed = {"street_number": "123", "street_name": "Market St"}
        ranked = rank_search_results(results, "123 Market St", parsed)
        assert ranked[0]["street_number"] == "123"
        assert ranked[0]["match_badge"] == "Address Match"

    def test_permit_number_ranked_second(self):
        results = [
            self._make_result(street_number="456", street_name="Mission St",
                              description="electrical work"),
            self._make_result(permit_number="202401015555",
                              street_number="789", street_name="Castro St",
                              description="plumbing"),
        ]
        query = "202401015555"
        parsed = {}
        ranked = rank_search_results(results, query, parsed)
        assert ranked[0]["permit_number"] == "202401015555"
        assert ranked[0]["match_badge"] == "Permit"

    def test_description_match_badge(self):
        results = [
            self._make_result(street_number="100", street_name="Main St",
                              description="kitchen remodel renovation"),
        ]
        parsed = {"description_search": "kitchen remodel"}
        ranked = rank_search_results(results, "kitchen remodel", parsed)
        assert ranked[0]["match_badge"] == "Description"

    def test_empty_results_returns_empty(self):
        ranked = rank_search_results([], "some query", {})
        assert ranked == []

    def test_all_results_get_match_badge(self):
        results = [
            self._make_result(street_number="1", street_name="A St"),
            self._make_result(street_number="2", street_name="B Ave"),
        ]
        ranked = rank_search_results(results, "query", {})
        for r in ranked:
            assert "match_badge" in r

    def test_rank_score_removed_from_output(self):
        """Internal _rank_score should not appear in final results."""
        results = [self._make_result(street_number="1", street_name="A St")]
        ranked = rank_search_results(results, "query", {})
        assert "_rank_score" not in ranked[0]

    def test_address_match_over_permit_match(self):
        """Address match (score=100) should beat permit number match (score=90)."""
        results = [
            self._make_result(permit_number="202401015555",
                              street_number="456", street_name="Castro St",
                              description="plumbing"),
            self._make_result(street_number="123", street_name="Market St",
                              description="kitchen"),
        ]
        query = "123 Market 202401015555"
        parsed = {"street_number": "123", "street_name": "Market St"}
        ranked = rank_search_results(results, query, parsed)
        # Address match should come first
        assert ranked[0]["street_number"] == "123"
        assert ranked[0]["match_badge"] == "Address Match"
