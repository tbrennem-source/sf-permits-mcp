"""Tests for question-type query routing in the intent router.

Verifies that natural language questions (do I, can I, how long, etc.)
classify as intent='question' and that non-question queries are unaffected.
"""

import pytest
from src.tools.intent_router import classify


# ---------------------------------------------------------------------------
# Question prefix patterns — should classify as 'question'
# ---------------------------------------------------------------------------

class TestQuestionPrefixPatterns:
    """Queries starting with known question words route to question intent."""

    def test_do_i_need_permit_for_kitchen(self):
        """'Do I need a permit for a kitchen remodel?' → question."""
        result = classify("Do I need a permit for a kitchen remodel?")
        assert result.intent == "question"
        assert result.confidence >= 0.85

    def test_do_i_need_permit_lowercase(self):
        """Lowercase 'do i' prefix is detected."""
        result = classify("do i need a permit to replace my roof?")
        assert result.intent == "question"

    def test_can_i_build_deck(self):
        """'Can I build a deck without a permit?' → question."""
        result = classify("Can I build a deck without a permit?")
        assert result.intent == "question"

    def test_should_i_get_permit(self):
        """'Should I get a permit for a bathroom remodel?' → question."""
        result = classify("Should I get a permit for a bathroom remodel?")
        assert result.intent == "question"

    def test_how_long_does_permit_take(self):
        """'How long does a permit take in SF?' → question."""
        result = classify("How long does a permit take in SF?")
        assert result.intent == "question"

    def test_what_do_i_need_for_adu(self):
        """'What do I need to build an ADU?' → question."""
        result = classify("What do I need to build an ADU?")
        assert result.intent == "question"

    def test_is_it_legal_to_convert_garage(self):
        """'Is it legal to convert a garage to living space?' → question."""
        result = classify("Is it legal to convert a garage to living space?")
        assert result.intent == "question"

    def test_will_i_need_permit_for_windows(self):
        """'Will I need a permit to replace windows?' → question."""
        result = classify("Will I need a permit to replace windows?")
        assert result.intent == "question"

    def test_what_permits_do_i_need_solar(self):
        """'What permits do I need for solar panels?' → question."""
        result = classify("What permits do I need for solar panels?")
        assert result.intent == "question"

    def test_how_much_does_permit_cost(self):
        """'How much does a building permit cost?' → question."""
        result = classify("How much does a building permit cost?")
        assert result.intent == "question"


# ---------------------------------------------------------------------------
# Question phrase patterns (anywhere in text) — should classify as 'question'
# ---------------------------------------------------------------------------

class TestQuestionPhrasePatterns:
    """Queries containing question phrases anywhere in the text."""

    def test_contains_need_a_permit(self):
        """Phrase 'need a permit' mid-query → question."""
        result = classify("For a bathroom remodel, do I need a permit in SF?")
        assert result.intent == "question"

    def test_contains_permits_required(self):
        """Phrase 'permits required' → question."""
        result = classify("What permits are required for a new deck?")
        assert result.intent == "question"

    def test_how_many_permits(self):
        """'How many permits do I need?' → question."""
        result = classify("How many permits do I need for a major remodel?")
        assert result.intent == "question"


# ---------------------------------------------------------------------------
# Non-question queries — should NOT classify as 'question'
# ---------------------------------------------------------------------------

class TestNonQuestionQueries:
    """Address, permit number, and project description queries are unaffected."""

    def test_address_query_unchanged(self):
        """Street address should still route to search_address."""
        result = classify("123 Main St")
        assert result.intent == "search_address"

    def test_permit_number_unchanged(self):
        """9-digit permit number should still route to lookup_permit."""
        result = classify("202401015555")
        assert result.intent == "lookup_permit"

    def test_project_description_unchanged(self):
        """Project description without question prefix still routes correctly."""
        result = classify("Kitchen remodel at 456 Oak Ave")
        # Should route to analyze_project or search_address — not question
        assert result.intent != "question"

    def test_address_signal_unchanged(self):
        """'Permits at 123 Main St' still routes to search_address."""
        result = classify("permits at 123 Main St")
        assert result.intent in ("search_address", "search_complaint")

    def test_generic_search_unchanged(self):
        """Person name search still routes to search_person."""
        result = classify("Amy Lee's projects")
        assert result.intent == "search_person"

    def test_entities_contain_query(self):
        """Question intent includes the original query in entities."""
        result = classify("Do I need a permit for a kitchen remodel?")
        assert result.intent == "question"
        assert "query" in result.entities
        assert "kitchen remodel" in result.entities["query"].lower()
