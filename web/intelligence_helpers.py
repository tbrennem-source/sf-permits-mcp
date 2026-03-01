"""Sync wrappers for intelligence tools used in the morning brief.

These helpers call the underlying data-fetching logic directly (no async)
and return structured dicts suitable for Jinja2 template rendering.

QS14-T4-B
"""

from __future__ import annotations

import logging
from datetime import date

logger = logging.getLogger(__name__)


def get_stuck_diagnosis_sync(permit_number: str) -> dict | None:
    """Return a structured stuck-permit diagnosis dict for a single permit.

    Calls src.tools.stuck_permit internals directly (sync) to avoid running
    an async event loop inside the Flask request context.

    Returns a dict with keys:
        permit_number, severity, stuck_stations (list), interventions (list)
    or None if the permit is not found or the diagnosis fails.

    ``severity`` is one of: "CRITICAL", "HIGH", "NORMAL", or None.
    Severity "HIGH" maps to stuck_permit status "stalled".
    Severity "CRITICAL" maps to status "critically_stalled".
    """
    permit_number = str(permit_number).strip()
    if not permit_number:
        return None

    try:
        from src.tools.stuck_permit import (
            _fetch_permit,
            _fetch_active_stations,
            _fetch_revision_count,
            _fetch_velocity,
            _diagnose_station,
            _overall_status,
        )
        from src.db import get_connection
    except ImportError as e:
        logger.warning("intelligence_helpers: stuck_permit import failed: %s", e)
        return None

    conn = None
    try:
        conn = get_connection()
        today = date.today()

        permit = _fetch_permit(conn, permit_number)
        if not permit:
            return None

        active_stations = _fetch_active_stations(conn, permit_number)
        revision_count = _fetch_revision_count(conn, permit_number)

        diagnoses = []
        for station_entry in active_stations:
            station = station_entry.get("station", "")
            if not station:
                continue
            addenda_num = station_entry.get("addenda_number") or 0
            metric_type = "revision" if addenda_num >= 1 else "initial"
            velocity = _fetch_velocity(conn, station, metric_type=metric_type)
            diagnosis = _diagnose_station(station_entry, velocity, today)
            diagnoses.append(diagnosis)

        overall = _overall_status(diagnoses)

        # Map internal status to brief severity label
        severity_map = {
            "critically_stalled": "CRITICAL",
            "stalled": "HIGH",
            "normal": "NORMAL",
        }
        severity = severity_map.get(overall)

        # Build stuck_stations list (only stalled/critically_stalled)
        stuck_stations = [
            {
                "station": d["station"],
                "days": d["dwell_days"] or 0,
                "status": d["status"],
            }
            for d in diagnoses
            if d["status"] in ("stalled", "critically_stalled")
        ]

        # Build interventions list (action text only, for brief display)
        interventions = []
        for d in sorted(
            diagnoses,
            key=lambda x: {"critically_stalled": 0, "stalled": 1, "normal": 2}.get(x["status"], 3),
        ):
            if d.get("recommendation"):
                interventions.append({"action": d["recommendation"]})

        return {
            "permit_number": permit_number,
            "severity": severity,
            "stuck_stations": stuck_stations,
            "interventions": interventions,
            "revision_count": revision_count,
        }

    except Exception as e:
        logger.warning("get_stuck_diagnosis_sync(%s) failed: %s", permit_number, e)
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def get_delay_cost_sync(
    permit_type: str,
    monthly_carrying_cost: float,
) -> dict | None:
    """Return a structured delay-cost estimate dict for the morning brief.

    Does NOT call the async calculate_delay_cost tool — instead it calls
    the underlying pure-Python helpers directly for zero-latency estimates.

    Returns a dict with keys:
        permit_type, daily_cost, weekly_cost, monthly_cost
    or None on error.
    """
    if monthly_carrying_cost <= 0:
        return None

    try:
        from src.tools.cost_of_delay import _get_timeline_estimates
    except ImportError as e:
        logger.warning("intelligence_helpers: cost_of_delay import failed: %s", e)
        return None

    try:
        daily_cost = monthly_carrying_cost / 30.44
        weekly_cost = daily_cost * 7

        return {
            "permit_type": permit_type,
            "daily_cost": round(daily_cost, 2),
            "weekly_cost": round(weekly_cost, 2),
            "monthly_cost": round(monthly_carrying_cost, 2),
        }
    except Exception as e:
        logger.warning("get_delay_cost_sync(%s) failed: %s", permit_type, e)
        return None
