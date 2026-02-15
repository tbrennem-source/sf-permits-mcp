"""Tests for intent_router — intent classification and entity extraction.

Pure unit tests, no mocks, no DB. Tests the rule-based intent
classifier and entity extraction patterns.
"""

import pytest

from src.tools.intent_router import classify, _match_neighborhood, IntentResult


# Sample neighborhoods for testing
NEIGHBORHOODS = [
    "Bayview Hunters Point", "Bernal Heights", "Castro/Upper Market",
    "Financial District/South Beach", "Haight Ashbury", "Mission",
    "Mission Bay", "Nob Hill", "Noe Valley", "Pacific Heights",
    "South of Market", "Sunset/Parkside", "Tenderloin",
]


# ---------------------------------------------------------------------------
# Permit number intent
# ---------------------------------------------------------------------------

def test_bare_permit_number():
    r = classify("202301015555")
    assert r.intent == "lookup_permit"
    assert r.entities["permit_number"] == "202301015555"


def test_permit_with_text():
    r = classify("what's happening with permit 202301015555")
    assert r.intent == "lookup_permit"
    assert r.entities["permit_number"] == "202301015555"


def test_m_series_permit():
    r = classify("M012345")
    assert r.intent == "lookup_permit"
    assert r.entities["permit_number"] == "M012345"


def test_permit_number_in_sentence():
    r = classify("check status of 202401019876 please")
    assert r.intent == "lookup_permit"
    assert r.entities["permit_number"] == "202401019876"


def test_short_number_not_permit():
    """6-digit numbers should NOT match as permit numbers."""
    r = classify("123456")
    assert r.intent != "lookup_permit"


def test_very_short_number():
    """4-digit numbers should not be permits."""
    r = classify("1234")
    assert r.intent != "lookup_permit"


# ---------------------------------------------------------------------------
# Block/lot intent
# ---------------------------------------------------------------------------

def test_block_lot():
    r = classify("block 3512 lot 001")
    assert r.intent == "search_parcel"
    assert r.entities["block"] == "3512"
    assert r.entities["lot"] == "001"


def test_block_lot_with_comma():
    r = classify("Block 3512, Lot 14")
    assert r.intent == "search_parcel"
    assert r.entities["block"] == "3512"
    assert r.entities["lot"] == "14"


def test_block_lot_with_slash():
    r = classify("block 0582/lot 003")
    assert r.intent == "search_parcel"
    assert r.entities["block"] == "0582"
    assert r.entities["lot"] == "003"


# ---------------------------------------------------------------------------
# Complaint / enforcement intent
# ---------------------------------------------------------------------------

def test_complaint_keyword():
    """'complaint at 75 robin hood' should route to search_complaint."""
    r = classify("complaint at 75 robin hood dr")
    assert r.intent == "search_complaint"


def test_violation_keyword():
    """'violations on block 2920 lot 020' should route to search_complaint."""
    r = classify("violations on block 2920 lot 020")
    assert r.intent == "search_complaint"
    assert r.entities.get("block") == "2920"
    assert r.entities.get("lot") == "020"


def test_nov_keyword():
    """'notice of violation' should trigger complaint intent."""
    r = classify("notice of violation at 100 Market St")
    assert r.intent == "search_complaint"


def test_enforcement_keyword():
    """'enforcement action' should trigger complaint intent."""
    r = classify("any enforcement actions on this property")
    assert r.intent == "search_complaint"


def test_complaint_with_address():
    """Complaint intent should extract address entities."""
    r = classify("complaint at 75 Robin Hood Dr")
    assert r.intent == "search_complaint"
    assert "street_name" in r.entities or "street_number" in r.entities


def test_complaint_beats_validate():
    """'complaint' keyword should win over general question."""
    r = classify("is there a complaint filed against my building?")
    assert r.intent == "search_complaint"


# ---------------------------------------------------------------------------
# Validate intent
# ---------------------------------------------------------------------------

def test_validate_check_plans():
    r = classify("check my plans")
    assert r.intent == "validate_plans"


def test_validate_pdf():
    r = classify("validate my PDF")
    assert r.intent == "validate_plans"


def test_validate_epr():
    r = classify("EPR compliance check")
    assert r.intent == "validate_plans"


def test_validate_upload():
    r = classify("upload pdf for review")
    assert r.intent == "validate_plans"


# ---------------------------------------------------------------------------
# Address intent
# ---------------------------------------------------------------------------

def test_address_with_signal():
    r = classify("find permits at 123 Main St")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "123"
    assert "main" in r.entities["street_name"].lower()


def test_bare_short_address():
    r = classify("456 Market")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "456"
    assert "market" in r.entities["street_name"].lower()


def test_address_whats_going_on():
    r = classify("what's going on at 789 Valencia St")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "789"


def test_address_whats_happening():
    r = classify("what's happening at 100 Folsom")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "100"


def test_address_with_suffix():
    r = classify("permits at 555 California Blvd")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "555"


def test_full_mailing_address():
    """Regression: pasted mailing address with city/state/zip should still match."""
    r = classify("146 Lake St 1425 San Francisco, CA 94118 US")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "146"
    assert "lake" in r.entities["street_name"].lower()


def test_address_with_city_state():
    r = classify("200 Valencia St San Francisco CA")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "200"
    assert "valencia" in r.entities["street_name"].lower()


def test_address_with_unit_number():
    """Bare trailing number after street suffix should be treated as unit, not block query."""
    r = classify("350 Bush St #400")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "350"
    assert "bush" in r.entities["street_name"].lower()


def test_address_with_apt():
    r = classify("500 Folsom Ave Apt 12B")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "500"
    assert "folsom" in r.entities["street_name"].lower()


def test_long_address_with_suffix():
    """A long query with a street suffix should still match as address."""
    r = classify("I need permits at 1200 Pacific Ave San Francisco CA 94109")
    assert r.intent == "search_address"
    assert r.entities["street_number"] == "1200"
    assert "pacific" in r.entities["street_name"].lower()


def test_address_no_suffix_still_needs_gate():
    """Bare address without suffix in a long query should NOT match (prevents false positives)."""
    r = classify("tell me about 500 Market in a very long query sentence with many words here")
    assert r.intent != "search_address"


# ---------------------------------------------------------------------------
# Person search intent
# ---------------------------------------------------------------------------

def test_person_possessive():
    r = classify("Amy Lee's projects")
    assert r.intent == "search_person"
    assert "amy lee" in r.entities["person_name"].lower()


def test_person_projects_by():
    r = classify("show me projects by John Smith")
    assert r.intent == "search_person"
    assert "john smith" in r.entities["person_name"].lower()


def test_person_permits_for():
    r = classify("permits for Jane Doe")
    assert r.intent == "search_person"
    assert "jane doe" in r.entities["person_name"].lower()


def test_person_with_role():
    r = classify("find contractor Bob Wilson")
    assert r.intent == "search_person"
    assert r.entities.get("role") == "contractor"
    assert "bob wilson" in r.entities["person_name"].lower()


def test_person_who_is():
    r = classify("who is Mike Chen")
    assert r.intent == "search_person"
    assert "mike chen" in r.entities["person_name"].lower()


def test_person_portfolio():
    r = classify("Smith Construction's portfolio")
    assert r.intent == "search_person"
    assert "smith construction" in r.entities["person_name"].lower()


def test_person_misspelled_role():
    """Regression: 'show me expiditer amy lee's projects' should extract 'amy lee'."""
    r = classify("show me expiditer amy lee's projects")
    assert r.intent == "search_person"
    assert r.entities["person_name"].lower() == "amy lee"
    assert r.entities.get("role") == "expediter"


def test_person_misspelled_architect():
    r = classify("show architech john doe's work")
    assert r.intent == "search_person"
    assert r.entities["person_name"].lower() == "john doe"
    assert r.entities.get("role") == "architect"


def test_person_show_me_with_role():
    """'show me expediter X' should not include 'me' in name."""
    r = classify("show me expediter Amy Lee")
    assert r.intent == "search_person"
    assert r.entities["person_name"].lower() == "amy lee"
    assert r.entities.get("role") == "expediter"


def test_person_trailing_projects_stripped():
    r = classify("find Amy Lee's projects")
    assert r.intent == "search_person"
    assert r.entities["person_name"].lower() == "amy lee"


def test_person_role_expiditor():
    r = classify("look up expiditor jane smith")
    assert r.intent == "search_person"
    assert r.entities["person_name"].lower() == "jane smith"
    assert r.entities.get("role") == "expediter"


# ---------------------------------------------------------------------------
# Analyze project intent
# ---------------------------------------------------------------------------

def test_analyze_kitchen():
    r = classify("I want to renovate my kitchen in Noe Valley for $85K", NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities.get("estimated_cost") == 85000.0
    assert r.entities.get("neighborhood") == "Noe Valley"


def test_analyze_adu():
    r = classify("convert garage to ADU, 450 sqft, $180K budget", NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities.get("estimated_cost") == 180000.0
    assert r.entities.get("square_footage") == 450.0


def test_analyze_cost_no_k():
    r = classify("remodel bathroom for $25,000", NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities.get("estimated_cost") == 25000.0


def test_analyze_with_neighborhood():
    r = classify("restaurant buildout in the Mission for $250K", NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities.get("neighborhood") == "Mission"


def test_analyze_description_preserved():
    text = "I want to build an addition on my house"
    r = classify(text, NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities["description"] == text


def test_analyze_large_cost():
    r = classify("new construction commercial building $2,500,000", NEIGHBORHOODS)
    assert r.intent == "analyze_project"
    assert r.entities.get("estimated_cost") == 2500000.0


# ---------------------------------------------------------------------------
# General question intent (fallback)
# ---------------------------------------------------------------------------

def test_general_otc():
    r = classify("what's the OTC threshold?")
    assert r.intent == "general_question"
    assert r.entities["query"] == "what's the OTC threshold?"


def test_general_plan_review():
    r = classify("how long does plan review take?")
    assert r.intent == "general_question"


def test_general_empty():
    r = classify("")
    assert r.intent == "general_question"
    assert r.confidence == 0.0


def test_general_short_question():
    r = classify("fees?")
    assert r.intent == "general_question"


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

def test_permit_number_beats_address():
    """A 10-digit number should be a permit, not a street number."""
    r = classify("1234567890 Main St")
    assert r.intent == "lookup_permit"


def test_block_lot_beats_address():
    r = classify("block 3512 lot 001 at 123 Main")
    assert r.intent == "search_parcel"


def test_validate_beats_general():
    r = classify("how do I validate plans?")
    assert r.intent == "validate_plans"


def test_validate_beats_analyze():
    """'validate' keyword should win over project analysis signals."""
    r = classify("validate my building plans")
    assert r.intent == "validate_plans"


# ---------------------------------------------------------------------------
# Neighborhood matching
# ---------------------------------------------------------------------------

def test_match_noe_valley():
    assert _match_neighborhood("kitchen remodel in Noe Valley", NEIGHBORHOODS) == "Noe Valley"


def test_match_mission():
    assert _match_neighborhood("restaurant in the Mission", NEIGHBORHOODS) == "Mission"


def test_match_mission_bay_over_mission():
    """'Mission Bay' should match before 'Mission' (longer match wins)."""
    assert _match_neighborhood("new project in Mission Bay", NEIGHBORHOODS) == "Mission Bay"


def test_match_none():
    assert _match_neighborhood("simple bathroom project", NEIGHBORHOODS) is None


def test_match_case_insensitive():
    assert _match_neighborhood("project in noe valley", NEIGHBORHOODS) == "Noe Valley"


def test_match_pacific_heights():
    assert _match_neighborhood("historic renovation pacific heights", NEIGHBORHOODS) == "Pacific Heights"


# ---------------------------------------------------------------------------
# IntentResult structure
# ---------------------------------------------------------------------------

def test_intent_result_defaults():
    r = IntentResult(intent="test", confidence=0.5)
    assert r.entities == {}


def test_intent_result_with_entities():
    r = IntentResult(intent="test", confidence=0.5, entities={"key": "value"})
    assert r.entities["key"] == "value"
