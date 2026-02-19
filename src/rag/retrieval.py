"""Hybrid retrieval pipeline: vector similarity + keyword boost + trust reranking.

Combines pgvector cosine similarity with the existing KnowledgeBase keyword
matching to produce a unified ranked result set.

Scoring formula:
    final_score = (vector_sim * VECTOR_WEIGHT
                   + keyword_score * KEYWORD_WEIGHT
                   + tier_boost) * trust_weight

Where:
    vector_sim  = cosine similarity from pgvector (0.0 – 1.0)
    keyword_score = from KnowledgeBase.match_concepts_scored (0.0 – ~2.0, normalized)
    tier_boost  = bonus for tier1 structured content
    trust_weight = 1.0 (official), 0.9 (amy), 0.7 (learned)
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# --- Scoring weights ---
VECTOR_WEIGHT = 0.60
KEYWORD_WEIGHT = 0.30
TIER_BOOST_WEIGHT = 0.10

# Tier bonuses (fraction of TIER_BOOST_WEIGHT)
TIER_BOOSTS = {
    "tier1": 1.0,
    "tier2": 0.6,
    "tier3": 0.5,
    "tier4": 0.3,
}

# Defaults
DEFAULT_TOP_K_VECTOR = 30   # Fetch more from pgvector, then rerank
DEFAULT_FINAL_K = 10        # Return top N after reranking
MIN_SIMILARITY = 0.20       # Floor for vector results


def retrieve(
    query: str,
    top_k: int = DEFAULT_FINAL_K,
    source_tier: Optional[str] = None,
    include_keyword_boost: bool = True,
    vector_top_k: int = DEFAULT_TOP_K_VECTOR,
) -> list[dict]:
    """Run hybrid retrieval: embed query → vector search → keyword boost → rerank.

    Args:
        query: Natural language question.
        top_k: Number of final results to return.
        source_tier: Optional filter (e.g. 'official', 'amy').
        include_keyword_boost: Whether to blend keyword scores.
        vector_top_k: How many candidates to fetch from pgvector.

    Returns:
        List of result dicts sorted by final_score descending.
        Each dict has: content, source_file, source_section, source_tier,
        trust_weight, similarity, metadata, final_score, scoring_breakdown.
    """
    from src.rag.embeddings import embed_query
    from src.rag.store import search as vector_search

    # 1) Embed the query
    try:
        query_embedding = embed_query(query)
    except Exception as e:
        logger.error("Failed to embed query: %s", e)
        return _fallback_keyword_only(query, top_k)

    # 2) Vector similarity search
    candidates = vector_search(
        query_embedding=query_embedding,
        top_k=vector_top_k,
        source_tier=source_tier,
    )

    if not candidates:
        logger.info("No vector results for query, falling back to keyword-only")
        return _fallback_keyword_only(query, top_k)

    # 3) Keyword boost from existing KnowledgeBase
    keyword_scores = {}
    if include_keyword_boost:
        keyword_scores = _get_keyword_scores(query)

    # 4) Score and rerank
    scored = []
    for c in candidates:
        if c["similarity"] < MIN_SIMILARITY:
            continue

        vector_sim = c["similarity"]
        kw_score = _match_keyword_to_chunk(c, keyword_scores)
        tier = c.get("metadata", {}).get("tier", "unknown")
        tier_boost = TIER_BOOSTS.get(tier, 0.0)
        trust = c.get("trust_weight", 1.0) or 1.0

        raw_score = (
            vector_sim * VECTOR_WEIGHT
            + kw_score * KEYWORD_WEIGHT
            + tier_boost * TIER_BOOST_WEIGHT
        )
        final_score = raw_score * trust

        c["final_score"] = round(final_score, 4)
        c["scoring_breakdown"] = {
            "vector_sim": round(vector_sim, 4),
            "keyword_score": round(kw_score, 4),
            "tier_boost": round(tier_boost, 2),
            "trust_weight": round(trust, 2),
            "raw_score": round(raw_score, 4),
        }
        scored.append(c)

    # Sort by final score descending
    scored.sort(key=lambda x: x["final_score"], reverse=True)

    # Deduplicate near-identical content
    deduped = _deduplicate(scored)

    return deduped[:top_k]


def retrieve_with_context(
    query: str,
    top_k: int = DEFAULT_FINAL_K,
    source_tier: Optional[str] = None,
) -> dict:
    """Retrieve results plus assembled context string for LLM augmentation.

    Returns:
        {
            "results": [...],
            "context": "assembled context string",
            "query": original query,
            "result_count": int,
        }
    """
    results = retrieve(query, top_k=top_k, source_tier=source_tier)

    context_parts = []
    for i, r in enumerate(results, 1):
        source = r.get("source_file", "unknown")
        section = r.get("source_section", "")
        tier = r.get("source_tier", "")
        score = r.get("final_score", 0)

        header = f"[Source {i}: {source}"
        if section:
            header += f" > {section}"
        header += f" | tier={tier} | score={score:.3f}]"

        context_parts.append(f"{header}\n{r['content']}")

    return {
        "results": results,
        "context": "\n\n---\n\n".join(context_parts),
        "query": query,
        "result_count": len(results),
    }


# --- Internal helpers ---

def _get_keyword_scores(query: str) -> dict[str, float]:
    """Get keyword match scores from the existing KnowledgeBase semantic index.

    Returns dict of {concept_name: normalized_score}.
    """
    try:
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        matches = kb.match_concepts_scored(query)
        if not matches:
            return {}
        # Normalize scores to 0-1 range (max observed is ~2.0)
        max_score = max(score for _, score in matches)
        if max_score <= 0:
            return {}
        return {name: min(score / max_score, 1.0) for name, score in matches}
    except Exception as e:
        logger.warning("Keyword scoring failed: %s", e)
        return {}


def _match_keyword_to_chunk(chunk: dict, keyword_scores: dict) -> float:
    """Score how well a chunk matches keyword concepts.

    Checks if the chunk's source_file or source_section aligns with
    any matched concepts. Also does a simple content overlap check.
    """
    if not keyword_scores:
        return 0.0

    content_lower = chunk.get("content", "").lower()
    source_file = (chunk.get("source_file") or "").lower().replace("-", "_").replace(".json", "")
    source_section = (chunk.get("source_section") or "").lower().replace("-", "_")

    best_score = 0.0
    for concept, score in keyword_scores.items():
        concept_lower = concept.lower().replace("-", "_")

        # Strong match: concept name appears in source file or section
        if concept_lower in source_file or concept_lower in source_section:
            best_score = max(best_score, score)
            continue

        # Medium match: concept keywords appear in chunk content
        concept_words = concept_lower.replace("_", " ").split()
        if len(concept_words) >= 2:
            # Multi-word concept: check if most words appear
            hits = sum(1 for w in concept_words if w in content_lower)
            if hits >= len(concept_words) * 0.6:
                best_score = max(best_score, score * 0.7)
        elif concept_words:
            # Single-word concept: check content
            if concept_words[0] in content_lower:
                best_score = max(best_score, score * 0.5)

    return best_score


def _deduplicate(results: list[dict], similarity_threshold: float = 0.85) -> list[dict]:
    """Remove near-duplicate chunks based on content overlap.

    Uses a simple Jaccard-like word set comparison.
    """
    if not results:
        return results

    deduped = [results[0]]
    seen_word_sets = [_word_set(results[0].get("content", ""))]

    for r in results[1:]:
        r_words = _word_set(r.get("content", ""))
        is_dup = False

        for seen in seen_word_sets:
            if not seen or not r_words:
                continue
            intersection = len(seen & r_words)
            union = len(seen | r_words)
            if union > 0 and intersection / union > similarity_threshold:
                is_dup = True
                break

        if not is_dup:
            deduped.append(r)
            seen_word_sets.append(r_words)

    return deduped


def _word_set(text: str) -> set:
    """Extract a set of lowercase words from text for dedup comparison."""
    return set(text.lower().split()) if text else set()


def _fallback_keyword_only(query: str, top_k: int) -> list[dict]:
    """Fallback when vector search is unavailable — use keyword matching only.

    Returns concept-level results from the existing KnowledgeBase.
    """
    try:
        from src.tools.knowledge_base import get_knowledge_base
        kb = get_knowledge_base()
        matches = kb.match_concepts_scored(query)
        results = []
        for name, score in matches[:top_k]:
            results.append({
                "content": f"Matched concept: {name} (keyword score: {score:.2f})",
                "source_file": "semantic-index",
                "source_section": name,
                "source_tier": "official",
                "trust_weight": 1.0,
                "similarity": 0.0,
                "metadata": {"tier": "tier1", "type": "keyword_fallback"},
                "final_score": round(score, 4),
                "scoring_breakdown": {
                    "vector_sim": 0.0,
                    "keyword_score": round(score, 4),
                    "tier_boost": 1.0,
                    "trust_weight": 1.0,
                    "raw_score": round(score, 4),
                },
            })
        return results
    except Exception as e:
        logger.error("Keyword fallback also failed: %s", e)
        return []
