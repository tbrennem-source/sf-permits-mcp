"""Create signal tables + seed signal_types on Postgres.

Usage:
    python -m scripts.migrate_signals          # dry-run
    python -m scripts.migrate_signals --apply  # execute
"""

import argparse
import sys

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

SEED_SIGNAL_TYPES = [
    ("hold_comments", "at_risk", "addenda", "yes", "Reviewer issued corrections via Issued Comments"),
    ("hold_stalled_planning", "at_risk", "addenda", "yes", "Stalled 1yr+ at PPC/CP-ZOC/CPB planning station"),
    ("hold_stalled", "behind", "addenda", "warning", "Stalled 30d+ at non-planning station"),
    ("nov", "at_risk", "violations", "yes", "Open Notice of Violation"),
    ("abatement", "at_risk", "violations", "yes", "Order of Abatement or Directors Hearing"),
    ("expired_uninspected", "at_risk", "permits+inspections", "yes", "Expired with 4+ real inspections, no final"),
    ("stale_with_activity", "at_risk", "permits+inspections", "yes", "Issued 2yr+, latest real inspection within 5yr, 2+ real inspections"),
    ("expired_minor_activity", "behind", "permits+inspections", "warning", "Expired with 1-3 real inspections"),
    ("expired_inconclusive", "behind", "permits", "warning", "Expired, zero real inspections, non-OTC"),
    ("complaint", "slower", "complaints", "info", "Open complaint, no associated NOV"),
    ("expired_otc", "slower", "permits", "info", "Expired, zero real inspections, OTC type"),
    ("stale_no_activity", "slower", "permits", "info", "Issued 2yr+, no meaningful recent inspections"),
    ("station_slow", "behind", "addenda+velocity", "warning", "Station dwell exceeding velocity baseline"),
]


def main():
    parser = argparse.ArgumentParser(description="Migrate signal tables to Postgres")
    parser.add_argument("--apply", action="store_true", help="Execute migration (default: dry-run)")
    args = parser.parse_args()

    if not args.apply:
        print("DRY RUN — pass --apply to execute\n")
        print(DDL)
        print("\n-- Seed signal_types:")
        for row in SEED_SIGNAL_TYPES:
            print(f"  {row[0]}: {row[1]} ({row[2]})")
        return

    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        print("ERROR: This migration requires DATABASE_URL (Postgres). Exiting.")
        sys.exit(1)

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)

            for row in SEED_SIGNAL_TYPES:
                cur.execute(
                    """INSERT INTO signal_types (signal_type, default_severity, source_dataset, actionable, description)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (signal_type) DO UPDATE SET
                         default_severity = EXCLUDED.default_severity,
                         source_dataset = EXCLUDED.source_dataset,
                         actionable = EXCLUDED.actionable,
                         description = EXCLUDED.description""",
                    row,
                )

            conn.commit()
        print(f"Migration complete: 4 tables created, {len(SEED_SIGNAL_TYPES)} signal_types seeded.")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
