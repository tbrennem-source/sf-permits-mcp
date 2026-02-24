"""Nightly signal pipeline — truncate, detect, aggregate, derive.

Orchestrates the full signal refresh cycle. Designed to be called from
/cron/signals endpoint or manually via CLI.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

from src.db import BACKEND
from src.signals.types import Signal
from src.signals.detector import ALL_DETECTORS
from src.signals.aggregator import compute_property_health

logger = logging.getLogger(__name__)


def _exec_write(conn, sql, params=None, *, backend="postgres"):
    """Execute a write statement."""
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
    else:
        if params:
            sql = sql.replace("%s", "?")
        conn.execute(sql, params or [])


def _table_exists(conn, table_name: str, backend: str) -> bool:
    """Check if a table exists."""
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                [table_name],
            )
            return cur.fetchone()[0]
    else:
        rows = conn.execute(
            "SELECT COUNT(*) FROM information_schema_schemata() WHERE table_name = ?",
            [table_name],
        ).fetchone()
        # DuckDB fallback: try querying the table
        try:
            conn.execute(f"SELECT 1 FROM {table_name} LIMIT 0")
            return True
        except Exception:
            return False


def _ensure_tables_duckdb(conn):
    """Create signal tables in DuckDB for dev/test."""
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
        CREATE TABLE IF NOT EXISTS permit_signals (
            id INTEGER PRIMARY KEY,
            permit_number VARCHAR(30) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            detail TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS permit_signals_id_seq START 1
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS property_signals (
            id INTEGER PRIMARY KEY,
            block_lot VARCHAR(20) NOT NULL,
            signal_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL,
            detail TEXT,
            source_permit VARCHAR(30),
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE SEQUENCE IF NOT EXISTS property_signals_id_seq START 1
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


def run_signal_pipeline(conn, backend: str | None = None) -> dict:
    """Run the full signal detection pipeline.

    Steps:
      1. Truncate permit_signals, property_signals, property_health
      2. Run ALL detectors → collect signals
      3. Insert permit_signals (per-permit signals)
      4. Aggregate by block_lot → insert property_signals
      5. Compute tier per property → upsert property_health
      6. Return stats

    Args:
        conn: Database connection (Postgres or DuckDB).
        backend: Override backend detection. Defaults to src.db.BACKEND.

    Returns:
        Dict with signal counts, property counts, tier distribution, timing.
    """
    if backend is None:
        backend = BACKEND

    t0 = time.time()

    # Ensure tables exist (DuckDB dev mode)
    if backend == "duckdb":
        _ensure_tables_duckdb(conn)

    # Step 1: Truncate
    for table in ("permit_signals", "property_signals", "property_health"):
        _exec_write(conn, f"DELETE FROM {table}", backend=backend)

    # Step 2: Run all detectors
    all_signals: list[Signal] = []
    detector_stats = {}

    for detector_fn in ALL_DETECTORS:
        name = detector_fn.__name__
        try:
            signals = detector_fn(conn, backend=backend)
            all_signals.extend(signals)
            detector_stats[name] = len(signals)
            logger.info("Detector %s: %d signals", name, len(signals))
        except Exception as e:
            logger.error("Detector %s failed: %s", name, e)
            detector_stats[name] = f"ERROR: {e}"

    # Step 3: Insert permit_signals
    permit_signal_count = 0
    for s in all_signals:
        if s.permit_number:
            if backend == "postgres":
                _exec_write(
                    conn,
                    """INSERT INTO permit_signals (permit_number, signal_type, severity, detail)
                       VALUES (%s, %s, %s, %s)""",
                    [s.permit_number, s.signal_type, s.severity, s.detail],
                    backend=backend,
                )
            else:
                _exec_write(
                    conn,
                    """INSERT INTO permit_signals (id, permit_number, signal_type, severity, detail)
                       VALUES (nextval('permit_signals_id_seq'), %s, %s, %s, %s)""",
                    [s.permit_number, s.signal_type, s.severity, s.detail],
                    backend=backend,
                )
            permit_signal_count += 1

    # Step 4: Group by block_lot → insert property_signals
    property_signals: dict[str, list[Signal]] = defaultdict(list)
    for s in all_signals:
        property_signals[s.block_lot].append(s)

    property_signal_count = 0
    for block_lot, signals in property_signals.items():
        for s in signals:
            if backend == "postgres":
                _exec_write(
                    conn,
                    """INSERT INTO property_signals (block_lot, signal_type, severity, detail, source_permit)
                       VALUES (%s, %s, %s, %s, %s)""",
                    [block_lot, s.signal_type, s.severity, s.detail, s.permit_number],
                    backend=backend,
                )
            else:
                _exec_write(
                    conn,
                    """INSERT INTO property_signals (id, block_lot, signal_type, severity, detail, source_permit)
                       VALUES (nextval('property_signals_id_seq'), %s, %s, %s, %s, %s)""",
                    [block_lot, s.signal_type, s.severity, s.detail, s.permit_number],
                    backend=backend,
                )
            property_signal_count += 1

    # Step 5: Compute tier per property → upsert property_health
    tier_counts = defaultdict(int)
    for block_lot, signals in property_signals.items():
        health = compute_property_health(block_lot, signals)
        tier_counts[health.tier] += 1

        signals_json = json.dumps([
            {
                "signal_type": s.signal_type,
                "severity": s.severity,
                "permit_number": s.permit_number,
                "detail": s.detail,
            }
            for s in health.signals
        ])

        if backend == "postgres":
            _exec_write(
                conn,
                """INSERT INTO property_health (block_lot, tier, signal_count, at_risk_count, signals_json)
                   VALUES (%s, %s, %s, %s, %s::jsonb)
                   ON CONFLICT (block_lot) DO UPDATE SET
                     tier = EXCLUDED.tier,
                     signal_count = EXCLUDED.signal_count,
                     at_risk_count = EXCLUDED.at_risk_count,
                     signals_json = EXCLUDED.signals_json,
                     computed_at = NOW()""",
                [block_lot, health.tier, health.signal_count, health.at_risk_count, signals_json],
                backend=backend,
            )
        else:
            _exec_write(
                conn,
                """INSERT OR REPLACE INTO property_health (block_lot, tier, signal_count, at_risk_count, signals_json)
                   VALUES (%s, %s, %s, %s, %s)""",
                [block_lot, health.tier, health.signal_count, health.at_risk_count, signals_json],
                backend=backend,
            )

    if backend == "postgres":
        conn.commit()

    elapsed = round(time.time() - t0, 2)

    return {
        "status": "ok",
        "elapsed_seconds": elapsed,
        "total_signals": len(all_signals),
        "permit_signals_inserted": permit_signal_count,
        "property_signals_inserted": property_signal_count,
        "properties_scored": len(property_signals),
        "tier_distribution": dict(tier_counts),
        "detector_stats": detector_stats,
    }
