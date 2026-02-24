"""Database migration: create signal tables + seed signal_types.

Creates 4 Postgres tables (signal_types, permit_signals, property_signals,
property_health) and seeds signal_types with 13 rows from the catalog.

Safe to re-run: uses CREATE IF NOT EXISTS and UPSERT for seeding.

Usage:
    python -m scripts.migrate_signals
"""

import logging
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.signals.types import SIGNAL_CATALOG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = """
CREATE TABLE IF NOT EXISTS signal_types (
    signal_type VARCHAR(50) PRIMARY KEY,
    default_severity VARCHAR(20) NOT NULL,
    source_dataset VARCHAR(50) NOT NULL,
    actionable VARCHAR(10) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS permit_signals (
    id SERIAL PRIMARY KEY,
    permit_number VARCHAR(30) NOT NULL,
    signal_type VARCHAR(50) NOT NULL REFERENCES signal_types(signal_type),
    severity VARCHAR(20) NOT NULL,
    detail TEXT,
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS property_signals (
    id SERIAL PRIMARY KEY,
    block_lot VARCHAR(20) NOT NULL,
    signal_type VARCHAR(50) NOT NULL REFERENCES signal_types(signal_type),
    severity VARCHAR(20) NOT NULL,
    detail TEXT,
    source_permit VARCHAR(30),
    detected_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS property_health (
    block_lot VARCHAR(20) PRIMARY KEY,
    tier VARCHAR(20) NOT NULL,
    signal_count INTEGER DEFAULT 0,
    at_risk_count INTEGER DEFAULT 0,
    signals_json JSONB,
    computed_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_permit_signals_permit ON permit_signals(permit_number);
CREATE INDEX IF NOT EXISTS idx_permit_signals_type ON permit_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_property_signals_blocklot ON property_signals(block_lot);
CREATE INDEX IF NOT EXISTS idx_property_signals_severity ON property_signals(severity);
CREATE INDEX IF NOT EXISTS idx_property_health_tier ON property_health(tier);
CREATE INDEX IF NOT EXISTS idx_property_health_at_risk ON property_health(at_risk_count);
"""


def run_migration():
    """Run the signal tables migration on Postgres."""
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        logger.info("Not on Postgres — skipping migration (DuckDB creates tables lazily)")
        return {"ok": True, "backend": "duckdb", "message": "Skipped — DuckDB mode"}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)

            # Seed signal_types
            for st in SIGNAL_CATALOG.values():
                cur.execute(
                    """INSERT INTO signal_types
                       (signal_type, default_severity, source_dataset, actionable, description)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (signal_type) DO UPDATE SET
                           default_severity = EXCLUDED.default_severity,
                           source_dataset = EXCLUDED.source_dataset,
                           actionable = EXCLUDED.actionable,
                           description = EXCLUDED.description
                    """,
                    (st.signal_type, st.default_severity, st.source_dataset,
                     st.actionable, st.description),
                )

            conn.commit()
            logger.info("Migration complete: 4 tables created, %d signal types seeded",
                        len(SIGNAL_CATALOG))
            return {"ok": True, "tables": 4, "signal_types": len(SIGNAL_CATALOG)}
    except Exception as e:
        conn.rollback()
        logger.error("Migration failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    result = run_migration()
    print(result)
