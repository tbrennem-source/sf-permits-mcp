"""Tests for the RAG knowledge retrieval system.

Tests chunker, retrieval scoring, and deduplication logic.
Embedding and store tests use mocks to avoid API/DB dependencies.
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Chunker tests
# ---------------------------------------------------------------------------

class TestChunkerTier1:
    """Test tier1 JSON chunking."""

    def test_chunk_dict_json(self, tmp_path):
        """Chunk a dict-style JSON file."""
        from src.rag.chunker import chunk_tier1_json

        data = {
            "source": "test source",
            "description": "Test data",
            "topic_a": {
                "detail": "This is a detailed section about topic A with enough content to be a valid chunk",
                "steps": ["step 1", "step 2", "step 3"],
            },
            "topic_b": "Another section with enough text to exceed the minimum chunk size threshold for inclusion",
        }
        filepath = tmp_path / "test-data.json"
        filepath.write_text(json.dumps(data))

        chunks = chunk_tier1_json(filepath)
        assert len(chunks) >= 1
        assert all(c["source_file"] == "test-data.json" for c in chunks)
        assert all("content" in c for c in chunks)
        assert all("source_section" in c for c in chunks)

    def test_chunk_list_json(self, tmp_path):
        """Chunk a list-style JSON file."""
        from src.rag.chunker import chunk_tier1_json

        data = [
            {"name": "Item A", "description": "A long enough description for a valid chunk to be created from this item"},
            {"name": "Item B", "description": "Another long enough description for a valid chunk to be created from this item"},
        ]
        filepath = tmp_path / "list-data.json"
        filepath.write_text(json.dumps(data))

        chunks = chunk_tier1_json(filepath)
        assert len(chunks) == 2
        assert chunks[0]["source_section"] == "item_0"
        assert chunks[1]["source_section"] == "item_1"

    def test_chunk_skips_metadata_keys(self, tmp_path):
        """Should skip source, source_url, last_verified, description."""
        from src.rag.chunker import chunk_tier1_json

        data = {
            "source": "sf.gov",
            "source_url": "https://sf.gov",
            "last_verified": "2026-01-01",
            "description": "Test",
            "actual_content": {
                "info": "This is the real content that should be chunked into a valid piece of text",
            },
        }
        filepath = tmp_path / "meta-test.json"
        filepath.write_text(json.dumps(data))

        chunks = chunk_tier1_json(filepath)
        # Only actual_content should be chunked
        assert len(chunks) == 1
        assert "actual_content" in chunks[0]["source_section"]

    def test_chunk_invalid_json(self, tmp_path):
        """Should return empty list for invalid JSON."""
        from src.rag.chunker import chunk_tier1_json

        filepath = tmp_path / "bad.json"
        filepath.write_text("not valid json {{{")

        chunks = chunk_tier1_json(filepath)
        assert chunks == []

    def test_real_tier1_files_chunk(self):
        """Verify actual tier1 files produce non-zero chunks."""
        from src.rag.chunker import chunk_tier1_json

        tier1_dir = Path(__file__).resolve().parent.parent / "data" / "knowledge" / "tier1"
        if not tier1_dir.exists():
            pytest.skip("tier1 directory not available")

        # Test a few known files
        for name in ["otc-criteria.json", "fee-tables.json", "epr-requirements.json"]:
            filepath = tier1_dir / name
            if filepath.exists():
                chunks = chunk_tier1_json(filepath)
                assert len(chunks) > 0, f"{name} produced no chunks"


class TestChunkerRawText:
    """Test tier2/3 raw text chunking."""

    def test_basic_paragraph_chunking(self):
        from src.rag.chunker import chunk_raw_text

        text = "\n\n".join([
            f"Paragraph {i}: " + "This is a test paragraph with enough content. " * 5
            for i in range(10)
        ])

        chunks = chunk_raw_text(text, "test-file.txt")
        assert len(chunks) > 1
        assert all(c["source_file"] == "test-file.txt" for c in chunks)

    def test_empty_text(self):
        from src.rag.chunker import chunk_raw_text
        assert chunk_raw_text("", "test.txt") == []
        assert chunk_raw_text("   ", "test.txt") == []

    def test_section_header_detection(self):
        from src.rag.chunker import chunk_raw_text

        text = (
            "# Introduction\n\n"
            "This section introduces the concept with enough text to be a valid chunk.\n\n"
            "# Requirements\n\n"
            "This section covers requirements with enough text to be a valid chunk too.\n\n"
            "More requirements detail that adds to the paragraph length sufficiently."
        )

        chunks = chunk_raw_text(text, "test.txt")
        assert len(chunks) >= 1
        # At least one chunk should pick up a section header
        sections = [c["source_section"] for c in chunks]
        assert any(s != "body" for s in sections)


class TestChunkerCodeSections:
    """Test tier4 code section chunking."""

    def test_split_at_section_headers(self):
        from src.rag.chunker import chunk_code_sections

        text = (
            "Section 101.1 General Provisions\n"
            "This section establishes the general provisions for building code compliance "
            "with all requirements specified herein.\n\n"
            "Section 102.1 Applicability\n"
            "This section defines applicability criteria for the building code to various "
            "construction types and project scopes.\n\n"
            "Section 103.1 Enforcement\n"
            "This section covers code enforcement procedures and penalties for non-compliance "
            "including stop work orders and citations.\n"
        )

        chunks = chunk_code_sections(text, "building-code.txt")
        assert len(chunks) == 3
        assert "Section 101.1" in chunks[0]["source_section"]

    def test_falls_back_to_paragraph_chunking(self):
        from src.rag.chunker import chunk_code_sections

        text = "No section headers here.\n\n" + "Some paragraph content. " * 20

        chunks = chunk_code_sections(text, "test.txt")
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# Retrieval scoring tests (no API/DB calls)
# ---------------------------------------------------------------------------

class TestRetrievalScoring:
    """Test the scoring and reranking logic in retrieval.py."""

    def test_tier_boost_values(self):
        from src.rag.retrieval import TIER_BOOSTS
        assert TIER_BOOSTS["tier1"] > TIER_BOOSTS["tier4"]
        assert TIER_BOOSTS["tier2"] > TIER_BOOSTS["tier3"]

    def test_weight_sum(self):
        """Scoring weights should approximately sum to 1."""
        from src.rag.retrieval import VECTOR_WEIGHT, KEYWORD_WEIGHT, TIER_BOOST_WEIGHT
        assert abs((VECTOR_WEIGHT + KEYWORD_WEIGHT + TIER_BOOST_WEIGHT) - 1.0) < 0.01

    def test_deduplicate_identical(self):
        from src.rag.retrieval import _deduplicate

        results = [
            {"content": "The same content repeated here", "final_score": 0.9},
            {"content": "The same content repeated here", "final_score": 0.8},
            {"content": "Completely different content about something else", "final_score": 0.7},
        ]
        deduped = _deduplicate(results)
        assert len(deduped) == 2

    def test_deduplicate_preserves_diverse(self):
        from src.rag.retrieval import _deduplicate

        results = [
            {"content": "Topic A about permits and fees", "final_score": 0.9},
            {"content": "Topic B about inspections and timelines", "final_score": 0.8},
            {"content": "Topic C about zoning and land use", "final_score": 0.7},
        ]
        deduped = _deduplicate(results)
        assert len(deduped) == 3

    def test_keyword_to_chunk_matching(self):
        from src.rag.retrieval import _match_keyword_to_chunk

        chunk = {
            "content": "OTC permits require specific criteria including scope limitations",
            "source_file": "otc-criteria.json",
            "source_section": "residential_interior",
        }
        keyword_scores = {"otc_criteria": 0.95, "inspections": 0.5}

        score = _match_keyword_to_chunk(chunk, keyword_scores)
        # Should get a high score because "otc_criteria" matches source_file
        assert score >= 0.9

    def test_keyword_to_chunk_no_match(self):
        from src.rag.retrieval import _match_keyword_to_chunk

        chunk = {
            "content": "Some unrelated content about vegetables",
            "source_file": "random.json",
            "source_section": "cooking",
        }
        keyword_scores = {"otc_criteria": 0.95}

        score = _match_keyword_to_chunk(chunk, keyword_scores)
        assert score == 0.0

    def test_keyword_to_chunk_empty_scores(self):
        from src.rag.retrieval import _match_keyword_to_chunk

        chunk = {"content": "test", "source_file": "test.json", "source_section": "s"}
        assert _match_keyword_to_chunk(chunk, {}) == 0.0

    @patch("src.rag.embeddings.embed_query")
    @patch("src.rag.store.search")
    def test_retrieve_full_pipeline(self, mock_vector_search, mock_embed):
        """Test the full retrieve pipeline with mocked vector search."""
        from src.rag.retrieval import retrieve

        mock_embed.return_value = [0.1] * 1536

        mock_vector_search.return_value = [
            {
                "content": "OTC permits for residential interior work require scope limits",
                "source_file": "otc-criteria.json",
                "source_section": "residential_interior",
                "source_tier": "official",
                "trust_weight": 1.0,
                "similarity": 0.85,
                "metadata": {"tier": "tier1", "type": "structured"},
            },
            {
                "content": "Fee schedules for building permits based on construction cost",
                "source_file": "fee-tables.json",
                "source_section": "building_fees",
                "source_tier": "official",
                "trust_weight": 1.0,
                "similarity": 0.60,
                "metadata": {"tier": "tier1", "type": "structured"},
            },
        ]

        results = retrieve("What are OTC permit requirements?", top_k=5)
        assert len(results) == 2
        assert all("final_score" in r for r in results)
        assert all("scoring_breakdown" in r for r in results)
        # OTC result should score higher (better similarity + keyword match)
        assert results[0]["source_file"] == "otc-criteria.json"

    @patch("src.rag.embeddings.embed_query")
    @patch("src.rag.store.search")
    def test_retrieve_filters_low_similarity(self, mock_vector_search, mock_embed):
        """Results below MIN_SIMILARITY threshold should be filtered."""
        from src.rag.retrieval import retrieve, MIN_SIMILARITY

        mock_embed.return_value = [0.1] * 1536
        mock_vector_search.return_value = [
            {
                "content": "Low quality match",
                "source_file": "test.json",
                "source_section": "s",
                "source_tier": "official",
                "trust_weight": 1.0,
                "similarity": MIN_SIMILARITY - 0.01,
                "metadata": {"tier": "tier1"},
            },
        ]

        results = retrieve("test query")
        assert len(results) == 0

    @patch("src.rag.embeddings.embed_query", side_effect=RuntimeError("No API key"))
    def test_retrieve_falls_back_on_embed_error(self, mock_embed):
        """Should fall back to keyword-only when embedding fails."""
        from src.rag.retrieval import retrieve

        # This should not raise, should return keyword-only results
        results = retrieve("OTC permit requirements")
        # May return results from keyword fallback (depends on knowledge base state)
        assert isinstance(results, list)


class TestRetrieveWithContext:
    """Test the context assembly for LLM augmentation."""

    @patch("src.rag.embeddings.embed_query")
    @patch("src.rag.store.search")
    def test_context_format(self, mock_vector_search, mock_embed):
        from src.rag.retrieval import retrieve_with_context

        mock_embed.return_value = [0.1] * 1536
        mock_vector_search.return_value = [
            {
                "content": "Test content about permits",
                "source_file": "permit-guide.json",
                "source_section": "overview",
                "source_tier": "official",
                "trust_weight": 1.0,
                "similarity": 0.80,
                "metadata": {"tier": "tier1"},
            },
        ]

        result = retrieve_with_context("How do permits work?")
        assert "results" in result
        assert "context" in result
        assert "query" in result
        assert result["result_count"] == 1
        assert "permit-guide.json" in result["context"]
        assert "Test content about permits" in result["context"]


# ---------------------------------------------------------------------------
# Embeddings tests (mocked)
# ---------------------------------------------------------------------------

class TestEmbeddings:
    """Test embedding client with mocked OpenAI API."""

    def test_embed_query_calls_embed_texts(self):
        from src.rag.embeddings import embed_query

        with patch("src.rag.embeddings.embed_texts") as mock:
            mock.return_value = [[0.1] * 1536]
            result = embed_query("test text")
            assert len(result) == 1536
            mock.assert_called_once_with(["test text"], model="text-embedding-3-small")

    def test_embed_texts_missing_key(self):
        from src.rag.embeddings import embed_texts

        with patch.dict(os.environ, {}, clear=True):
            # Remove OPENAI_API_KEY if present
            env = dict(os.environ)
            env.pop("OPENAI_API_KEY", None)
            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                    embed_texts(["test"])


# ---------------------------------------------------------------------------
# Store tests (mocked DB)
# ---------------------------------------------------------------------------

class TestStore:
    """Test store module functions with mocked database."""

    @patch("src.rag.store._get_conn")
    def test_ensure_table(self, mock_conn):
        from src.rag.store import ensure_table

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor

        ensure_table()

        # Should execute CREATE EXTENSION, CREATE TABLE, and 2 indexes
        assert mock_cursor.execute.call_count >= 4
        mock_conn.return_value.commit.assert_called_once()
        mock_conn.return_value.close.assert_called_once()

    @patch("src.rag.store._get_conn")
    def test_insert_chunks(self, mock_conn):
        from src.rag.store import insert_chunks

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor

        chunks = [
            {"content": "Test chunk 1", "source_file": "test.json", "source_section": "s1", "metadata": {}},
            {"content": "Test chunk 2", "source_file": "test.json", "source_section": "s2", "metadata": {}},
        ]
        embeddings = [[0.1] * 1536, [0.2] * 1536]

        insert_chunks(chunks, embeddings, source_tier="official", trust_weight=1.0)

        assert mock_cursor.execute.call_count == 2
        mock_conn.return_value.commit.assert_called_once()

    @patch("src.rag.store._get_conn")
    def test_insert_chunks_mismatched_lengths(self, mock_conn):
        from src.rag.store import insert_chunks

        with pytest.raises(ValueError, match="Chunk count"):
            insert_chunks([{"content": "a"}], [[0.1] * 1536, [0.2] * 1536])

    @patch("src.rag.store._get_conn")
    def test_search_returns_results(self, mock_conn):
        from src.rag.store import search

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("content text", "file.json", "section", "official", 1.0, 0.85, "{}"),
        ]

        results = search([0.1] * 1536, top_k=5)
        assert len(results) == 1
        assert results[0]["content"] == "content text"
        assert results[0]["similarity"] == 0.85

    @patch("src.rag.store._get_conn")
    def test_search_with_tier_filter(self, mock_conn):
        from src.rag.store import search

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        results = search([0.1] * 1536, top_k=5, source_tier="official")
        assert results == []
        # Should have used the tier-filtered query
        call_args = mock_cursor.execute.call_args
        assert "source_tier" in call_args[0][0]

    @patch("src.rag.store._get_conn")
    def test_get_stats(self, mock_conn):
        from src.rag.store import get_stats

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.fetchall.side_effect = [
            [("official", 100), ("amy", 20)],  # tier counts
            [("file1.json", 50), ("file2.json", 30)],  # top files
        ]
        mock_cursor.fetchone.return_value = (120,)

        stats = get_stats()
        assert stats["total_chunks"] == 120
        assert stats["by_tier"]["official"] == 100

    @patch("src.rag.store._get_conn")
    def test_clear_tier(self, mock_conn):
        from src.rag.store import clear_tier

        mock_cursor = MagicMock()
        mock_conn.return_value.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 50

        deleted = clear_tier("official")
        assert deleted == 50
        mock_conn.return_value.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Ingestion script tests
# ---------------------------------------------------------------------------

class TestIngestionScript:
    """Test the ingestion script helper functions."""

    def test_ingest_tier1_dry_run(self):
        """Dry run should count chunks without calling API."""
        from scripts.rag_ingest import ingest_tier1

        count = ingest_tier1(dry_run=True)
        # Should produce chunks from actual tier1 files
        assert count > 0

    def test_tier_trust_weights(self):
        from scripts.rag_ingest import TIER_TRUST

        assert TIER_TRUST["tier1"] == 1.0
        assert TIER_TRUST["tier2"] < TIER_TRUST["tier1"]
        assert TIER_TRUST["tier3"] < TIER_TRUST["tier2"]
