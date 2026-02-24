"""Nightly signal pipeline — orchestrates detection, aggregation, and persistence.

Pipeline steps:
1. Ensure signal tables exist
2. Truncate permit_signals, property_signals, property_health
3. Run ALL detectors → collect signals
4. Insert permit_signals (signals with permit_number)
5. Group by block_lot → insert property_signals
6. Compute tier per property → upsert property_health
7. Return stats
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict

from src.signals.types import Signal, SIGNAL_CATALOG
from src.signals.detector import ALL_DETECTORS
from src.signals.aggregator import compute_property_health

logger = logging.getLogger(__name__)


def _ensure_signal_tables(conn) -> None:
    """Create signal tables if they don't exist (DuckDB)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signal_types (
            signal_type VARCHAR(50) PRIMARY KEY,
            default_severity VARCHAR(20) NOT NULL,
            source_dataset VARCHAR(50) NOT NULL,
            actionable VARCHAR(10) NOT NULL,
            description TEXT
        )
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_permit_signals START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permit_signals (
            id INTEGER DEFAULT nextval('seq_permit_signals') PRIMARY KEY,
            permit_number VARCHAR(30) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            detail TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS seq_property_signals START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS property_signals (
            id INTEGER DEFAULT nextval('seq_property_signals') PRIMARY KEY,
            block_lot VARCHAR(20) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            detail TEXT,
            source_permit VARCHAR(30),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS property_health (
            block_lot VARCHAR(20) PRIMARY KEY,
            tier VARCHAR(20) NOT NULL,
            signal_count INTEGER DEFAULT 0,
            at_risk_count INTEGER DEFAULT 0,
            signals_json TEXT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _seed_signal_types(conn) -> None:
    """Seed the signal_types table from the catalog."""
    conn.execute("DELETE FROM signal_types")
    for st in SIGNAL_CATALOG.values():
        conn.execute(
            """INSERT INTO signal_types
               (signal_type, default_severity, source_dataset, actionable, description)
               VALUES (?, ?, ?, ?, ?)""",
            (st.signal_type, st.default_severity, st.source_dataset,
             st.actionable, st.description),
        )


def _truncate_signals(conn) -> None:
    """Truncate computed signal tables before refresh."""
    for table in ("permit_signals", "property_signals", "property_health"):
        try:
            conn.execute(f"DELETE FROM {table}")
        except Exception:
            pass


def run_signal_pipeline(conn) -> dict:
    """Run the full signal detection + aggregation pipeline.

    Args:
        conn: DuckDB or Postgres connection with permits, addenda, violations,
              inspections, and complaints tables populated.

    Returns:
        Stats dict with signal counts, property counts, tier distribution.
    """
    # 1. Ensure tables
    _ensure_signal_tables(conn)

    # 2. Seed signal types
    _seed_signal_types(conn)

    # 3. Truncate
    _truncate_signals(conn)

    # 4. Run detectors
    all_signals: list[Signal] = []
    detector_stats = {}

    for detector in ALL_DETECTORS:
        name = detector.__name__
        try:
            signals = detector(conn)
            all_signals.extend(signals)
            detector_stats[name] = len(signals)
            logger.info("Detector %s: %d signals", name, len(signals))
        except Exception:
            logger.warning("Detector %s failed", name, exc_info=True)
            detector_stats[name] = -1

    # 5. Insert permit_signals (signals that have a permit_number)
    permit_signal_count = 0
    for s in all_signals:
        if s.permit_number:
            conn.execute(
                """INSERT INTO permit_signals
                   (permit_number, signal_type, severity, detail)
                   VALUES (?, ?, ?, ?)""",
                (s.permit_number, s.signal_type, s.severity, s.detail),
            )
            permit_signal_count += 1

    # 6. Group by block_lot → insert property_signals
    by_property: dict[str, list[Signal]] = defaultdict(list)
    for s in all_signals:
        if s.block_lot:
            by_property[s.block_lot].append(s)

    property_signal_count = 0
    for block_lot, signals in by_property.items():
        for s in signals:
            conn.execute(
                """INSERT INTO property_signals
                   (block_lot, signal_type, severity, detail, source_permit)
                   VALUES (?, ?, ?, ?, ?)""",
                (block_lot, s.signal_type, s.severity, s.detail, s.permit_number),
            )
            property_signal_count += 1

    # 7. Compute property health
    tier_counts: dict[str, int] = defaultdict(int)
    for block_lot, signals in by_property.items():
        health = compute_property_health(block_lot, signals)
        tier_counts[health.tier] += 1

        signals_json = json.dumps([
            {"type": s.signal_type, "severity": s.severity,
             "permit": s.permit_number, "detail": s.detail}
            for s in signals
        ])

        conn.execute(
            """INSERT INTO property_health
               (block_lot, tier, signal_count, at_risk_count, signals_json)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT (block_lot) DO UPDATE SET
                   tier = EXCLUDED.tier,
                   signal_count = EXCLUDED.signal_count,
                   at_risk_count = EXCLUDED.at_risk_count,
                   signals_json = EXCLUDED.signals_json""",
            (health.block_lot, health.tier, health.signal_count,
             health.at_risk_count, signals_json),
        )

    stats = {
        "total_signals": len(all_signals),
        "permit_signals": permit_signal_count,
        "property_signals": property_signal_count,
        "properties": len(by_property),
        "tier_distribution": dict(tier_counts),
        "detectors": detector_stats,
    }

    logger.info(
        "Signal pipeline complete: %d signals, %d properties, tiers=%s",
        len(all_signals), len(by_property), dict(tier_counts),
    )
    return stats
