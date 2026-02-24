"""Database migration: create api_usage + api_daily_summary tables.

Creates 2 tables for Claude API cost tracking:
  api_usage          — per-call log with token counts and USD cost
  api_daily_summary  — pre-computed daily rollup for fast dashboard queries

Safe to re-run: uses CREATE TABLE IF NOT EXISTS.

Usage:
    python -m scripts.migrate_cost_tracking
"""

import logging
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


DDL = """
CREATE TABLE IF NOT EXISTS api_usage (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    endpoint VARCHAR(100) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0.0,
    extra JSONB,
    called_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS api_daily_summary (
    id SERIAL PRIMARY KEY,
    summary_date DATE NOT NULL UNIQUE,
    total_calls INTEGER NOT NULL DEFAULT 0,
    total_cost_usd NUMERIC(12,6) NOT NULL DEFAULT 0.0,
    breakdown_json JSONB,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_usage_called_at ON api_usage(called_at);
CREATE INDEX IF NOT EXISTS idx_api_usage_user_id ON api_usage(user_id);
CREATE INDEX IF NOT EXISTS idx_api_usage_endpoint ON api_usage(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_daily_summary_date ON api_daily_summary(summary_date);
"""


def run_migration():
    """Run the cost tracking tables migration on Postgres."""
    from src.db import get_connection, BACKEND

    if BACKEND != "postgres":
        logger.info(
            "Not on Postgres — skipping migration "
            "(DuckDB creates tables lazily via web.cost_tracking.ensure_schema)"
        )
        return {"ok": True, "backend": "duckdb", "message": "Skipped — DuckDB mode"}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        logger.info("Cost tracking tables created/verified.")
        return {"ok": True, "backend": "postgres"}
    except Exception as e:
        conn.rollback()
        logger.error("Migration failed: %s", e)
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


if __name__ == "__main__":
    result = run_migration()
    if result["ok"]:
        print(f"OK: {result.get('message', 'Migration complete')}")
        sys.exit(0)
    else:
        print(f"ERROR: {result.get('error', 'Unknown error')}")
        sys.exit(1)
