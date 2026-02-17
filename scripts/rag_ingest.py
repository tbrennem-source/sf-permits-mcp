#!/usr/bin/env python3
"""RAG ingestion CLI — chunk, embed, and store all knowledge tiers.

Usage:
    python -m scripts.rag_ingest                  # Ingest all tiers
    python -m scripts.rag_ingest --tier tier1     # Ingest only tier1
    python -m scripts.rag_ingest --tier tier2     # Ingest only tier2
    python -m scripts.rag_ingest --tier tier3     # Ingest only tier3
    python -m scripts.rag_ingest --dry-run        # Preview chunks without embedding
    python -m scripts.rag_ingest --stats          # Show current DB stats

Requires:
    DATABASE_URL  — PostgreSQL connection string (Railway)
    OPENAI_API_KEY — OpenAI API key for embeddings
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rag_ingest")

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "knowledge"

# Trust weights per tier
TIER_TRUST = {
    "tier1": 1.0,   # Official structured content
    "tier2": 0.95,  # Info sheets (official, less structured)
    "tier3": 0.90,  # Administrative bulletins
    "tier4": 0.85,  # Code corpus (verbose, raw)
}

# Source tier labels for pgvector
TIER_SOURCE = {
    "tier1": "official",
    "tier2": "official",
    "tier3": "official",
    "tier4": "official",
}


def ingest_tier1(dry_run: bool = False) -> int:
    """Chunk and embed all tier1 structured JSON files."""
    from src.rag.chunker import chunk_tier1_json

    tier1_dir = DATA_DIR / "tier1"
    if not tier1_dir.exists():
        logger.error("tier1 directory not found: %s", tier1_dir)
        return 0

    json_files = sorted(tier1_dir.glob("*.json"))
    # Skip the semantic index — it's metadata, not content
    json_files = [f for f in json_files if f.name != "semantic-index.json"]

    logger.info("Found %d tier1 JSON files", len(json_files))

    all_chunks = []
    for filepath in json_files:
        chunks = chunk_tier1_json(filepath)
        logger.info("  %s → %d chunks", filepath.name, len(chunks))
        all_chunks.extend(chunks)

    logger.info("Total tier1 chunks: %d", len(all_chunks))

    if dry_run:
        _preview_chunks(all_chunks, "tier1")
        return len(all_chunks)

    return _embed_and_store(all_chunks, "official", TIER_TRUST["tier1"])


def ingest_tier2(dry_run: bool = False) -> int:
    """Chunk and embed all tier2 raw text info sheets."""
    from src.rag.chunker import chunk_raw_text

    tier2_dir = DATA_DIR / "tier2"
    if not tier2_dir.exists():
        logger.error("tier2 directory not found: %s", tier2_dir)
        return 0

    # Also include .txt files at top of tier1 (G-13-raw-text.txt etc.)
    text_files = []

    # tier2 subdirectories
    for subdir in sorted(tier2_dir.iterdir()):
        if subdir.is_dir():
            text_files.extend(sorted(subdir.glob("*.txt")))
        elif subdir.suffix == ".txt":
            text_files.append(subdir)

    # tier1 raw text files
    tier1_dir = DATA_DIR / "tier1"
    if tier1_dir.exists():
        text_files.extend(sorted(tier1_dir.glob("*-raw-text.txt")))

    logger.info("Found %d tier2 text files", len(text_files))

    all_chunks = []
    for filepath in text_files:
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except IOError as e:
            logger.warning("Could not read %s: %s", filepath.name, e)
            continue

        source_name = f"tier2/{filepath.parent.name}/{filepath.name}" if filepath.parent.name != "tier1" else f"tier1/{filepath.name}"
        chunks = chunk_raw_text(text, source_name)
        logger.info("  %s → %d chunks", filepath.name, len(chunks))
        all_chunks.extend(chunks)

    logger.info("Total tier2 chunks: %d", len(all_chunks))

    if dry_run:
        _preview_chunks(all_chunks, "tier2")
        return len(all_chunks)

    return _embed_and_store(all_chunks, "official", TIER_TRUST["tier2"])


def ingest_tier3(dry_run: bool = False) -> int:
    """Chunk and embed all tier3 administrative bulletins."""
    from src.rag.chunker import chunk_raw_text

    tier3_dir = DATA_DIR / "tier3"
    if not tier3_dir.exists():
        logger.error("tier3 directory not found: %s", tier3_dir)
        return 0

    text_files = sorted(tier3_dir.glob("*.txt"))
    logger.info("Found %d tier3 bulletin files", len(text_files))

    all_chunks = []
    for filepath in text_files:
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except IOError as e:
            logger.warning("Could not read %s: %s", filepath.name, e)
            continue

        chunks = chunk_raw_text(text, f"tier3/{filepath.name}")
        logger.info("  %s → %d chunks", filepath.name, len(chunks))
        all_chunks.extend(chunks)

    logger.info("Total tier3 chunks: %d", len(all_chunks))

    if dry_run:
        _preview_chunks(all_chunks, "tier3")
        return len(all_chunks)

    return _embed_and_store(all_chunks, "official", TIER_TRUST["tier3"])


def _embed_and_store(chunks: list[dict], source_tier: str, trust_weight: float) -> int:
    """Embed chunks and insert into pgvector store."""
    from src.rag.embeddings import embed_texts
    from src.rag.store import insert_chunks

    if not chunks:
        return 0

    texts = [c["content"] for c in chunks]

    logger.info("Embedding %d chunks...", len(texts))
    start = time.time()
    embeddings = embed_texts(texts)
    elapsed = time.time() - start
    logger.info("Embedded %d chunks in %.1fs (%.0f chunks/s)",
                len(texts), elapsed, len(texts) / elapsed if elapsed > 0 else 0)

    logger.info("Inserting into pgvector store...")
    insert_chunks(chunks, embeddings, source_tier=source_tier, trust_weight=trust_weight)
    logger.info("Stored %d chunks (tier=%s, trust=%.2f)", len(chunks), source_tier, trust_weight)

    return len(chunks)


def _preview_chunks(chunks: list[dict], tier_label: str, max_show: int = 5):
    """Print a preview of chunks for dry-run mode."""
    print(f"\n{'='*60}")
    print(f"  {tier_label}: {len(chunks)} chunks (dry-run, not embedding)")
    print(f"{'='*60}")
    for i, c in enumerate(chunks[:max_show]):
        content_preview = c["content"][:120].replace("\n", " ")
        print(f"  [{i+1}] {c.get('source_file', '?')} > {c.get('source_section', '?')}")
        print(f"      {content_preview}...")
        print()
    if len(chunks) > max_show:
        print(f"  ... and {len(chunks) - max_show} more chunks\n")


def show_stats():
    """Print current pgvector store statistics."""
    from src.rag.store import get_stats
    stats = get_stats()
    print(f"\nRAG Knowledge Store Stats:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"\n  By tier:")
    for tier, count in sorted(stats.get("by_tier", {}).items()):
        print(f"    {tier}: {count}")
    print(f"\n  Top files:")
    for f, count in list(stats.get("top_files", {}).items())[:10]:
        print(f"    {f}: {count}")
    print()


def main():
    parser = argparse.ArgumentParser(description="RAG knowledge ingestion")
    parser.add_argument("--tier", choices=["tier1", "tier2", "tier3", "all"],
                        default="all", help="Which tier to ingest (default: all)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview chunks without embedding or storing")
    parser.add_argument("--stats", action="store_true",
                        help="Show current store statistics")
    parser.add_argument("--clear", action="store_true",
                        help="Clear existing chunks before ingesting")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="Rebuild IVFFlat index after ingestion")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    # Ensure table exists
    if not args.dry_run:
        from src.rag.store import ensure_table
        ensure_table()

    # Clear if requested
    if args.clear and not args.dry_run:
        from src.rag.store import clear_tier
        logger.info("Clearing existing 'official' chunks...")
        deleted = clear_tier("official")
        logger.info("Cleared %d chunks", deleted)

    total = 0
    start = time.time()

    if args.tier in ("tier1", "all"):
        total += ingest_tier1(dry_run=args.dry_run)

    if args.tier in ("tier2", "all"):
        total += ingest_tier2(dry_run=args.dry_run)

    if args.tier in ("tier3", "all"):
        total += ingest_tier3(dry_run=args.dry_run)

    elapsed = time.time() - start

    if args.dry_run:
        print(f"\nDry run complete: {total} chunks would be created")
    else:
        logger.info("Ingestion complete: %d chunks in %.1fs", total, elapsed)

        # Rebuild index if requested or if we did a full ingestion
        if args.rebuild_index or (args.tier == "all" and total > 0):
            from src.rag.store import rebuild_ivfflat_index
            logger.info("Rebuilding IVFFlat index...")
            try:
                rebuild_ivfflat_index()
            except Exception as e:
                logger.warning("Index rebuild skipped (may need more rows): %s", e)

        show_stats()


if __name__ == "__main__":
    main()
