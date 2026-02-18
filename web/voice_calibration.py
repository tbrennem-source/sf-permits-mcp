"""Voice calibration — per-scenario style preferences.

Manages the calibration workflow where an expert rewrites template
responses for different audience × situation combinations.  The diff
between template and rewrite is later analysed by AI to extract
actionable style rules (Phase B).

Pattern follows web/regulatory_watch.py.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.db import BACKEND, execute_write, get_connection, init_user_schema, query, query_one
from web.voice_templates import SCENARIO_MAP, SCENARIOS, get_scenarios_by_audience

logger = logging.getLogger(__name__)

_schema_initialized = False


def _ensure_schema():
    global _schema_initialized
    if _schema_initialized:
        return
    if BACKEND == "duckdb":
        init_user_schema()
    _schema_initialized = True


def _now_expr() -> str:
    return "NOW()" if BACKEND == "postgres" else "CURRENT_TIMESTAMP"


# ── Seeding ──────────────────────────────────────────────────────


def seed_scenarios(user_id: int) -> int:
    """Insert all SCENARIOS for a user, skipping any that already exist.

    Returns the number of newly inserted rows.
    """
    _ensure_schema()
    existing = {r[0] for r in query(
        "SELECT scenario_key FROM voice_calibrations WHERE user_id = %s",
        (user_id,),
    )}

    inserted = 0
    for sc in SCENARIOS:
        if sc["key"] in existing:
            continue

        if BACKEND == "postgres":
            execute_write(
                "INSERT INTO voice_calibrations "
                "(user_id, scenario_key, audience, situation, template_text) "
                "VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (user_id, scenario_key) DO NOTHING",
                (user_id, sc["key"], sc["audience"], sc["situation"], sc["template_text"]),
            )
        else:
            # DuckDB — manual id generation
            row = query_one("SELECT COALESCE(MAX(calibration_id), 0) + 1 FROM voice_calibrations")
            cal_id = row[0]
            conn = get_connection()
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO voice_calibrations "
                    "(calibration_id, user_id, scenario_key, audience, situation, template_text) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (cal_id, user_id, sc["key"], sc["audience"], sc["situation"], sc["template_text"]),
                )
            finally:
                conn.close()
        inserted += 1

    return inserted


# ── Read ─────────────────────────────────────────────────────────


def get_all_calibrations(user_id: int) -> list[dict]:
    """All calibrations for a user, ordered by audience then situation."""
    _ensure_schema()
    rows = query(
        "SELECT calibration_id, user_id, scenario_key, audience, situation, "
        "template_text, user_text, style_notes, is_calibrated, created_at, updated_at "
        "FROM voice_calibrations WHERE user_id = %s "
        "ORDER BY audience, situation",
        (user_id,),
    )
    return [_row_to_dict(r) for r in rows]


def get_calibration(user_id: int, scenario_key: str) -> dict | None:
    """Get a single calibration by user + scenario key."""
    _ensure_schema()
    row = query_one(
        "SELECT calibration_id, user_id, scenario_key, audience, situation, "
        "template_text, user_text, style_notes, is_calibrated, created_at, updated_at "
        "FROM voice_calibrations WHERE user_id = %s AND scenario_key = %s",
        (user_id, scenario_key),
    )
    return _row_to_dict(row) if row else None


def get_calibrations_by_audience(user_id: int) -> dict[str, list[dict]]:
    """Return calibrations grouped by audience key, maintaining order."""
    all_cals = get_all_calibrations(user_id)
    grouped: dict[str, list[dict]] = {}
    for cal in all_cals:
        audience = cal["audience"]
        if audience not in grouped:
            grouped[audience] = []
        grouped[audience].append(cal)
    return grouped


def get_style_for_scenario(user_id: int, scenario_key: str) -> str | None:
    """Get style_notes for a specific scenario. Returns None if not calibrated."""
    _ensure_schema()
    row = query_one(
        "SELECT style_notes FROM voice_calibrations "
        "WHERE user_id = %s AND scenario_key = %s AND is_calibrated = TRUE",
        (user_id, scenario_key),
    )
    return row[0] if row else None


def get_calibration_stats(user_id: int) -> dict:
    """Return {total, calibrated, uncalibrated} counts."""
    _ensure_schema()
    rows = query(
        "SELECT is_calibrated, COUNT(*) FROM voice_calibrations "
        "WHERE user_id = %s GROUP BY is_calibrated",
        (user_id,),
    )
    calibrated = 0
    uncalibrated = 0
    for row in rows:
        if row[0]:  # is_calibrated = True
            calibrated = row[1]
        else:
            uncalibrated = row[1]
    return {
        "total": calibrated + uncalibrated,
        "calibrated": calibrated,
        "uncalibrated": uncalibrated,
    }


# ── Write ────────────────────────────────────────────────────────


def save_calibration(user_id: int, scenario_key: str, user_text: str) -> bool:
    """Save the expert's rewritten version for a scenario.

    Sets is_calibrated=True and updated_at=now.
    Style notes are NOT extracted here — that's Phase B (AI extraction).
    Returns True on success.
    """
    _ensure_schema()
    execute_write(
        f"UPDATE voice_calibrations "
        f"SET user_text = %s, is_calibrated = TRUE, updated_at = {_now_expr()} "
        f"WHERE user_id = %s AND scenario_key = %s",
        (user_text, user_id, scenario_key),
    )
    return True


def reset_calibration(user_id: int, scenario_key: str) -> bool:
    """Clear user_text, style_notes, and is_calibrated for a scenario."""
    _ensure_schema()
    execute_write(
        f"UPDATE voice_calibrations "
        f"SET user_text = NULL, style_notes = NULL, is_calibrated = FALSE, "
        f"updated_at = {_now_expr()} "
        f"WHERE user_id = %s AND scenario_key = %s",
        (user_id, scenario_key),
    )
    return True


# ── Template helpers ─────────────────────────────────────────────


def get_scenario_info(scenario_key: str) -> dict | None:
    """Get template info for a scenario key (from SCENARIOS constant)."""
    return SCENARIO_MAP.get(scenario_key)


# ── Internal ─────────────────────────────────────────────────────


def _row_to_dict(row) -> dict:
    """Convert a query row tuple to a dict."""
    scenario_key = row[2]
    # Enrich with template metadata
    tpl = SCENARIO_MAP.get(scenario_key, {})

    return {
        "calibration_id": row[0],
        "user_id": row[1],
        "scenario_key": scenario_key,
        "audience": row[3],
        "situation": row[4],
        "template_text": row[5],
        "user_text": row[6],
        "style_notes": row[7],
        "is_calibrated": bool(row[8]),
        "created_at": row[9],
        "updated_at": row[10],
        # Template metadata
        "context_hint": tpl.get("context_hint", ""),
        "audience_label": _audience_label(row[3]),
        "situation_label": _situation_label(row[4]),
    }


def _audience_label(key: str) -> str:
    from web.voice_templates import AUDIENCE_MAP
    aud = AUDIENCE_MAP.get(key)
    return aud["label"] if aud else key.replace("_", " ").title()


def _situation_label(key: str) -> str:
    from web.voice_templates import SITUATION_MAP
    sit = SITUATION_MAP.get(key)
    return sit["label"] if sit else key.replace("_", " ").title()
