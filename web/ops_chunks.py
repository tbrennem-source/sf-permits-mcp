"""Operational knowledge chunk generator — Tier 0 live data → RAG embeddings.

Generates knowledge chunks from live operational data (station velocity baselines,
addenda routing patterns, and system-wide statistics) and embeds them into the
pgvector knowledge store as source_tier='learned' with trust_weight=0.7.

These chunks give the AI assistant current operational context:
- How long each plan review station typically takes
- Which stations are currently bottlenecks
- Common routing patterns and sequences
- Station-specific guidance for consultants

Designed to run after station_velocity refresh in the nightly cron,
or independently via /cron/rag-ingest?tier=ops.
"""

from __future__ import annotations

import logging
import time
from datetime import date

from src.db import BACKEND, query

logger = logging.getLogger(__name__)

# Source file tag for all operational chunks (enables targeted clear + refresh)
OPS_SOURCE_FILE = "ops-live-data"
OPS_SOURCE_TIER = "learned"
OPS_TRUST_WEIGHT = 0.7


def generate_ops_chunks() -> list[dict]:
    """Generate RAG chunks from live operational data.

    Returns list of chunk dicts ready for embedding:
        [{content, source_file, source_section, metadata}, ...]
    """
    chunks = []
    chunks.extend(_station_velocity_chunks())
    chunks.extend(_routing_pattern_chunks())
    chunks.extend(_system_stats_chunk())
    logger.info("Generated %d operational chunks", len(chunks))
    return chunks


def ingest_ops_chunks(dry_run: bool = False) -> int:
    """Full pipeline: generate, embed, and store operational chunks.

    Clears previous ops chunks first to avoid stale data accumulation.
    Returns count of chunks stored.
    """
    if BACKEND != "postgres":
        logger.info("Ops chunk ingestion skipped (requires PostgreSQL)")
        return 0

    chunks = generate_ops_chunks()
    if not chunks:
        logger.info("No operational chunks generated")
        return 0

    if dry_run:
        for i, c in enumerate(chunks[:5]):
            preview = c["content"][:120].replace("\n", " ")
            logger.info("  [%d] %s > %s: %s...", i + 1,
                        c.get("source_file"), c.get("source_section"), preview)
        if len(chunks) > 5:
            logger.info("  ... and %d more chunks", len(chunks) - 5)
        return len(chunks)

    try:
        from src.rag.embeddings import embed_texts
        from src.rag.store import insert_chunks, clear_file

        # Clear previous ops chunks
        cleared = clear_file(OPS_SOURCE_FILE)
        if cleared:
            logger.info("Cleared %d previous ops chunks", cleared)

        texts = [c["content"] for c in chunks]
        start = time.time()
        embeddings = embed_texts(texts)
        elapsed = time.time() - start
        logger.info("Embedded %d ops chunks in %.1fs", len(texts), elapsed)

        insert_chunks(chunks, embeddings,
                      source_tier=OPS_SOURCE_TIER,
                      trust_weight=OPS_TRUST_WEIGHT)
        logger.info("Stored %d ops chunks (tier=%s, trust=%.2f)",
                    len(chunks), OPS_SOURCE_TIER, OPS_TRUST_WEIGHT)
        return len(chunks)

    except Exception:
        logger.error("Ops chunk ingestion failed", exc_info=True)
        return 0


# ---------------------------------------------------------------------------
# Chunk generators
# ---------------------------------------------------------------------------

def _station_velocity_chunks() -> list[dict]:
    """Generate one chunk per station from velocity baselines.

    Each chunk contains the station's turnaround statistics in natural
    language, optimized for RAG retrieval when users ask about wait times.
    """
    if BACKEND != "postgres":
        return []

    try:
        rows = query(
            "SELECT station, samples, avg_days, median_days, p75_days, "
            "       p90_days, min_days, max_days, baseline_date "
            "FROM station_velocity "
            "WHERE baseline_date = (SELECT MAX(baseline_date) FROM station_velocity) "
            "ORDER BY median_days DESC NULLS LAST"
        )
    except Exception:
        logger.debug("Station velocity query failed (table may not exist yet)", exc_info=True)
        return []

    if not rows:
        return []

    chunks = []
    today_str = str(date.today())

    for r in rows:
        station, samples, avg_d, med_d, p75_d, p90_d, min_d, max_d, bdate = r

        # Build natural language description
        parts = [f"Plan review station '{station}' turnaround statistics "
                 f"(based on {samples} reviews in the last 90 days):"]

        if med_d is not None:
            parts.append(f"- Median turnaround: {float(med_d):.1f} days")
        if avg_d is not None:
            parts.append(f"- Average turnaround: {float(avg_d):.1f} days")
        if p75_d is not None:
            parts.append(f"- 75th percentile: {float(p75_d):.1f} days (75% of reviews complete within this time)")
        if p90_d is not None:
            parts.append(f"- 90th percentile: {float(p90_d):.1f} days (90% of reviews complete within this time)")
        if min_d is not None and max_d is not None:
            parts.append(f"- Range: {float(min_d):.1f} to {float(max_d):.1f} days")

        # Add interpretive guidance
        if med_d is not None:
            md = float(med_d)
            if md < 1:
                parts.append("This station typically completes review same-day — very fast turnaround.")
            elif md < 7:
                parts.append(f"This station typically takes about {md:.0f} days — relatively quick.")
            elif md < 21:
                weeks = md / 7
                parts.append(f"This station typically takes about {weeks:.0f} weeks — moderate wait time.")
            elif md < 60:
                weeks = md / 7
                parts.append(f"This station typically takes about {weeks:.0f} weeks — this is a slower station, expect delays.")
            else:
                months = md / 30
                parts.append(f"This station typically takes about {months:.1f} months — this is one of the slowest stations in the review pipeline.")

        content = "\n".join(parts)
        chunks.append({
            "content": content,
            "source_file": OPS_SOURCE_FILE,
            "source_section": f"station-velocity/{station}",
            "metadata": {
                "station": station,
                "samples": samples,
                "median_days": float(med_d) if med_d is not None else None,
                "computed_date": today_str,
                "chunk_type": "station_velocity",
            },
        })

    # Add a summary chunk with all stations ranked
    if len(rows) >= 3:
        slowest = [(r[0], float(r[3])) for r in rows[:5] if r[3] is not None]
        fastest = [(r[0], float(r[3])) for r in rows[-5:] if r[3] is not None]
        fastest.reverse()

        summary_parts = [
            f"Plan review station velocity summary (as of {today_str}, "
            f"based on {len(rows)} stations with 90-day rolling data):",
            "",
            "Slowest stations (by median turnaround):",
        ]
        for name, med in slowest:
            summary_parts.append(f"  - {name}: {med:.1f} days median")

        summary_parts.append("")
        summary_parts.append("Fastest stations (by median turnaround):")
        for name, med in fastest:
            summary_parts.append(f"  - {name}: {med:.1f} days median")

        summary_parts.append("")
        summary_parts.append(
            "When a permit is pending at a slow station, consultants should "
            "set expectations accordingly. When a permit is at a fast station, "
            "check more frequently for results."
        )

        chunks.append({
            "content": "\n".join(summary_parts),
            "source_file": OPS_SOURCE_FILE,
            "source_section": "station-velocity/summary",
            "metadata": {
                "chunk_type": "station_velocity_summary",
                "station_count": len(rows),
                "computed_date": today_str,
            },
        })

    return chunks


def _routing_pattern_chunks() -> list[dict]:
    """Generate chunks about common routing patterns and station sequences.

    Captures which stations frequently appear together and typical
    addenda structure patterns.
    """
    if BACKEND != "postgres":
        return []

    chunks = []
    today_str = str(date.today())

    # Most common stations by volume
    try:
        rows = query(
            "SELECT station, COUNT(*) as cnt, "
            "       COUNT(DISTINCT permit_number) as permits "
            "FROM addenda "
            "WHERE station IS NOT NULL "
            "GROUP BY station "
            "ORDER BY cnt DESC "
            "LIMIT 25"
        )
    except Exception:
        logger.debug("Routing pattern query failed", exc_info=True)
        return []

    if rows:
        parts = [
            f"Most common plan review stations by volume (as of {today_str}):",
            "",
        ]
        for r in rows:
            parts.append(f"- {r[0]}: {r[1]:,} reviews across {r[2]:,} permits")

        parts.append("")
        parts.append(
            "Stations with high volume are the backbone of the review process. "
            "A delay at a high-volume station affects many permits simultaneously."
        )

        chunks.append({
            "content": "\n".join(parts),
            "source_file": OPS_SOURCE_FILE,
            "source_section": "routing-patterns/station-volume",
            "metadata": {
                "chunk_type": "routing_pattern",
                "computed_date": today_str,
            },
        })

    # Typical addenda counts per permit
    try:
        rows = query(
            "SELECT "
            "  ROUND(AVG(addenda_ct), 1) as avg_addenda, "
            "  PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY addenda_ct) as med_addenda, "
            "  PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY addenda_ct) as p90_addenda, "
            "  MAX(addenda_ct) as max_addenda "
            "FROM ("
            "  SELECT permit_number, COUNT(DISTINCT addenda_number) as addenda_ct "
            "  FROM addenda "
            "  WHERE permit_number IS NOT NULL "
            "  GROUP BY permit_number"
            ") sub"
        )
    except Exception:
        logger.debug("Addenda count query failed", exc_info=True)
        rows = []

    if rows and rows[0] and rows[0][0] is not None:
        r = rows[0]
        parts = [
            f"Addenda (plan review cycle) statistics across all permits (as of {today_str}):",
            f"- Average addenda per permit: {float(r[0]):.1f}",
            f"- Median addenda per permit: {float(r[1]):.1f}",
            f"- 90th percentile: {float(r[2]):.0f} addenda",
            f"- Maximum observed: {int(r[3])} addenda",
            "",
            "Most permits go through 1-3 addenda cycles. Permits with more than "
            f"{float(r[2]):.0f} addenda cycles are in the top 10% by complexity — "
            "these often indicate significant plan revisions or complex projects "
            "that required multiple rounds of review comments.",
        ]

        chunks.append({
            "content": "\n".join(parts),
            "source_file": OPS_SOURCE_FILE,
            "source_section": "routing-patterns/addenda-counts",
            "metadata": {
                "chunk_type": "routing_pattern",
                "computed_date": today_str,
            },
        })

    # Common results (approved, comments, etc.)
    try:
        rows = query(
            "SELECT result, COUNT(*) as cnt "
            "FROM addenda "
            "WHERE result IS NOT NULL AND result != '' "
            "GROUP BY result "
            "ORDER BY cnt DESC "
            "LIMIT 10"
        )
    except Exception:
        logger.debug("Result distribution query failed", exc_info=True)
        rows = []

    if rows:
        total = sum(r[1] for r in rows)
        parts = [
            f"Plan review result distribution (as of {today_str}, "
            f"based on {total:,} completed reviews):",
            "",
        ]
        for r in rows:
            pct = (r[1] / total * 100) if total > 0 else 0
            parts.append(f"- {r[0]}: {r[1]:,} ({pct:.1f}%)")

        parts.append("")
        parts.append(
            "When advising on a permit stuck in plan review, understanding "
            "the typical result distribution helps set expectations. Most "
            "reviews result in approval or approval with comments."
        )

        chunks.append({
            "content": "\n".join(parts),
            "source_file": OPS_SOURCE_FILE,
            "source_section": "routing-patterns/result-distribution",
            "metadata": {
                "chunk_type": "routing_pattern",
                "computed_date": today_str,
            },
        })

    return chunks


def _system_stats_chunk() -> list[dict]:
    """Generate a single summary chunk with system-wide operational stats."""
    if BACKEND != "postgres":
        return []

    today_str = str(date.today())
    parts = [f"SF DBI Plan Review System operational statistics (as of {today_str}):"]

    # Total addenda records
    try:
        rows = query("SELECT COUNT(*), COUNT(DISTINCT permit_number) FROM addenda")
        if rows and rows[0]:
            parts.append(f"- Total addenda records: {rows[0][0]:,}")
            parts.append(f"- Permits with routing data: {rows[0][1]:,}")
    except Exception:
        pass

    # Active permits in review
    try:
        rows = query(
            "SELECT COUNT(DISTINCT permit_number) FROM addenda "
            "WHERE finish_date IS NULL AND arrive IS NOT NULL"
        )
        if rows and rows[0] and rows[0][0]:
            parts.append(f"- Permits currently in active review: {rows[0][0]:,}")
    except Exception:
        pass

    # Station count
    try:
        rows = query("SELECT COUNT(DISTINCT station) FROM addenda WHERE station IS NOT NULL")
        if rows and rows[0]:
            parts.append(f"- Unique review stations: {rows[0][0]}")
    except Exception:
        pass

    # Total permits in system
    try:
        rows = query("SELECT COUNT(*) FROM permits")
        if rows and rows[0]:
            parts.append(f"- Total permits in database: {rows[0][0]:,}")
    except Exception:
        pass

    if len(parts) <= 1:
        return []

    parts.append("")
    parts.append(
        "This data covers San Francisco Department of Building Inspection (DBI) "
        "permit routing and plan review activity. The addenda table tracks each "
        "station's review of a permit, including arrive date, finish date, result, "
        "and any comments."
    )

    return [{
        "content": "\n".join(parts),
        "source_file": OPS_SOURCE_FILE,
        "source_section": "system-stats/overview",
        "metadata": {
            "chunk_type": "system_stats",
            "computed_date": today_str,
        },
    }]
