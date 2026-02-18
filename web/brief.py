"""Morning brief — data logic for the /brief dashboard.

Provides six sections:
  1. What Changed — status changes on watched permits
  2. Permit Health — are watched permits on track vs statistical norms?
  3. Inspection Results — recent pass/fail on watched permits
  4. New Filings — new permits at watched addresses/parcels
  5. Team Activity — watched contractors/architects appearing on new permits
  6. Expiring Permits — permits approaching Table B expiration deadline
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import BACKEND, query, query_one, get_connection

logger = logging.getLogger(__name__)

# Table B (SFBC Section 106A.4.4) — permit expiration by valuation tier.
# Demolition permits have a flat 180-day limit regardless of valuation.
EXPIRATION_WARNING_DAYS = 30


def _validity_days(permit: dict) -> int:
    """Look up Table B expiration period based on permit valuation.

    SFBC Section 106A.4.4 — Maximum Time Allowed to Complete Work:
      - $1 to $100,000:          360 days  (extension: 360 days)
      - $100,001 to $2,499,999:  1,080 days (extension: 720 days)
      - $2,500,000 and above:    1,440 days (extension: 720 days)
      - Demolition permits:      180 days  (extension: 180 days)
    """
    ptype = (permit.get("permit_type_definition") or "").lower()
    if "demolition" in ptype:
        return 180
    cost = permit.get("revised_cost") or permit.get("estimated_cost") or 0
    try:
        cost = float(cost)
    except (ValueError, TypeError):
        cost = 0
    if cost >= 2_500_000:
        return 1440
    if cost >= 100_001:
        return 1080
    return 360


def _ph() -> str:
    """Placeholder for parameterized queries (%s for Postgres, ? for DuckDB)."""
    return "%s" if BACKEND == "postgres" else "?"


def _parse_date(text: str | None) -> date | None:
    """Parse a TEXT date field to a Python date."""
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


# ── Main entry point ──────────────────────────────────────────────

def get_morning_brief(user_id: int, lookback_days: int = 1,
                      primary_address: dict | None = None) -> dict:
    """Build the complete morning brief data structure.

    Args:
        user_id: Current user's ID.
        lookback_days: How many days back to look for changes (1=today, 7=week).
        primary_address: Optional dict with ``street_number`` and ``street_name``
            for the user's primary (home) address.  When provided, a property
            synopsis section is included in the brief.

    Returns:
        Dict with keys: changes, health, inspections, new_filings,
        team_activity, expiring, property_synopsis, summary, lookback_days.
    """
    since = date.today() - timedelta(days=lookback_days)

    changes = _get_watched_changes(user_id, since)
    plan_reviews = _get_plan_review_activity(user_id, since)
    health = _get_predictability(user_id)
    inspections = _get_inspection_results(user_id, since)
    new_filings = _get_new_filings(user_id, since)
    team_activity = _get_team_activity(user_id, since)
    expiring = _get_expiring_permits(user_id)
    regulatory_alerts = _get_regulatory_alerts()

    # Property synopsis for primary address
    property_synopsis = None
    if primary_address:
        property_synopsis = _get_property_synopsis(
            primary_address["street_number"],
            primary_address["street_name"],
        )

    # Count watches
    watch_count_row = query(
        f"SELECT COUNT(*) FROM watch_items WHERE user_id = {_ph()} AND is_active = TRUE",
        (user_id,),
    )
    total_watches = watch_count_row[0][0] if watch_count_row else 0

    at_risk = sum(1 for h in health if h.get("status") in ("behind", "at_risk"))

    # Data freshness from cron_log
    last_refresh = _get_last_refresh()

    return {
        "changes": changes,
        "plan_reviews": plan_reviews,
        "health": health,
        "inspections": inspections,
        "new_filings": new_filings,
        "team_activity": team_activity,
        "expiring": expiring,
        "regulatory_alerts": regulatory_alerts,
        "property_synopsis": property_synopsis,
        "last_refresh": last_refresh,
        "summary": {
            "total_watches": total_watches,
            "changes_count": len(changes),
            "plan_reviews_count": len(plan_reviews),
            "at_risk_count": at_risk,
            "inspections_count": len(inspections),
            "new_filings_count": len(new_filings),
            "team_count": len(team_activity),
            "expiring_count": len(expiring),
            "regulatory_count": len(regulatory_alerts),
        },
        "lookback_days": lookback_days,
    }


# ── Section 1: What Changed ──────────────────────────────────────

def _get_watched_changes(user_id: int, since: date) -> list[dict]:
    """Get permit status changes matching any of the user's watches."""
    ph = _ph()
    results: list[dict] = []

    # Permit watches — direct match on permit_number
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.old_status, pc.new_status, "
        f"pc.change_type, pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.permit_number = pc.permit_number "
        f"  AND wi.watch_type = 'permit' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = FALSE "
        f"ORDER BY pc.change_date DESC",
        (user_id, since),
    )
    results.extend(_rows_to_changes(rows, "permit"))

    # Address watches
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.old_status, pc.new_status, "
        f"pc.change_type, pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.street_number = pc.street_number "
        f"  AND UPPER(wi.street_name) = UPPER(pc.street_name) "
        f"  AND wi.watch_type = 'address' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = FALSE "
        f"ORDER BY pc.change_date DESC",
        (user_id, since),
    )
    results.extend(_rows_to_changes(rows, "address"))

    # Parcel watches
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.old_status, pc.new_status, "
        f"pc.change_type, pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.block = pc.block AND wi.lot = pc.lot "
        f"  AND wi.watch_type = 'parcel' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = FALSE "
        f"ORDER BY pc.change_date DESC",
        (user_id, since),
    )
    results.extend(_rows_to_changes(rows, "parcel"))

    # Neighborhood watches (capped)
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.old_status, pc.new_status, "
        f"pc.change_type, pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.neighborhood = pc.neighborhood "
        f"  AND wi.watch_type = 'neighborhood' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = FALSE "
        f"ORDER BY pc.change_date DESC "
        f"LIMIT 20",
        (user_id, since),
    )
    results.extend(_rows_to_changes(rows, "neighborhood"))

    # Deduplicate (a permit could match multiple watches)
    seen = set()
    unique = []
    for r in results:
        key = (r["permit_number"], str(r["change_date"]), r["new_status"])
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _rows_to_changes(rows: list[tuple], watch_type: str) -> list[dict]:
    return [
        {
            "permit_number": r[0],
            "change_date": r[1],
            "old_status": r[2],
            "new_status": r[3],
            "change_type": r[4],
            "permit_type": r[5],
            "street_number": r[6],
            "street_name": r[7],
            "neighborhood": r[8],
            "label": r[9],
            "watch_type": watch_type,
        }
        for r in rows
    ]


# ── Section 2: Permit Health / Predictability ─────────────────────

def _get_predictability(user_id: int) -> list[dict]:
    """Compare watched permits' elapsed time against statistical benchmarks."""
    ph = _ph()

    # Get watched permits in active status
    # NOTE: The `permits` table only exists in DuckDB (local), not in PostgreSQL (prod).
    # Gracefully return empty if the table doesn't exist.
    try:
        rows = query(
            f"SELECT p.permit_number, p.status, p.filed_date, p.issued_date, "
            f"p.permit_type_definition, p.neighborhood, p.estimated_cost, "
            f"p.street_number, p.street_name, wi.label "
            f"FROM watch_items wi "
            f"JOIN permits p ON wi.permit_number = p.permit_number "
            f"WHERE wi.user_id = {ph} AND wi.watch_type = 'permit' "
            f"  AND wi.is_active = TRUE "
            f"  AND p.status IN ('filed', 'approved', 'issued', 'reinstated')",
            (user_id,),
        )
    except Exception:
        logger.debug("Permit health query failed (permits table may not exist)", exc_info=True)
        return []

    results = []
    conn = get_connection()
    try:
        for row in rows:
            (permit_number, status, filed_date, issued_date,
             permit_type, neighborhood, estimated_cost,
             street_number, street_name, label) = row

            filed = _parse_date(filed_date)
            if not filed:
                continue

            elapsed_days = (date.today() - filed).days
            if elapsed_days <= 0:
                continue

            # Get benchmarks using the same logic as estimate_timeline.py
            try:
                from src.tools.estimate_timeline import _query_timeline, _cost_bracket
                review_path = "otc" if permit_type and "otc" in permit_type.lower() else "in_house"
                bracket = _cost_bracket(estimated_cost)
                benchmarks = _query_timeline(conn, review_path, neighborhood, bracket, permit_type)

                if not benchmarks and neighborhood:
                    benchmarks = _query_timeline(conn, review_path, None, bracket, permit_type)
                if not benchmarks and bracket:
                    benchmarks = _query_timeline(conn, review_path, None, None, permit_type)
                if not benchmarks:
                    benchmarks = _query_timeline(conn, review_path, None, None, None)
            except Exception:
                # timeline_stats table may not exist in all environments
                benchmarks = None

            if not benchmarks:
                continue

            p50 = benchmarks["p50_days"] or 1
            p75 = benchmarks["p75_days"] or p50
            p90 = benchmarks["p90_days"] or p75

            if elapsed_days <= p50:
                health_status = "on_track"
            elif elapsed_days <= p75:
                health_status = "slower"
            elif elapsed_days <= p90:
                health_status = "behind"
            else:
                health_status = "at_risk"

            pct_of_typical = round(elapsed_days / p50 * 100) if p50 else 0

            results.append({
                "permit_number": permit_number,
                "status": health_status,
                "permit_status": status,
                "elapsed_days": elapsed_days,
                "p50": p50,
                "p75": p75,
                "p90": p90,
                "pct_of_typical": pct_of_typical,
                "permit_type": permit_type,
                "street_number": street_number,
                "street_name": street_name,
                "label": label,
                "sample_size": benchmarks["sample_size"],
            })
    finally:
        conn.close()

    # Sort: at_risk first, then behind, then slower, then on_track
    status_order = {"at_risk": 0, "behind": 1, "slower": 2, "on_track": 3}
    results.sort(key=lambda x: status_order.get(x["status"], 4))
    return results


# ── Section 3: Inspection Results ─────────────────────────────────

def _get_inspection_results(user_id: int, since: date) -> list[dict]:
    """Get recent inspection results for watched permits."""
    ph = _ph()

    # NOTE: The `inspections` table only exists in DuckDB (local), not in PostgreSQL (prod).
    try:
        rows = query(
            f"SELECT i.reference_number, i.scheduled_date, i.result, "
            f"i.inspection_description, i.inspector, wi.label "
            f"FROM inspections i "
            f"JOIN watch_items wi ON wi.permit_number = i.reference_number "
            f"  AND wi.watch_type = 'permit' AND wi.is_active = TRUE "
            f"WHERE wi.user_id = {ph} AND i.scheduled_date >= {ph} "
            f"ORDER BY i.scheduled_date DESC "
            f"LIMIT 50",
            (user_id, str(since)),
        )
    except Exception:
        logger.debug("Inspection results query failed (inspections table may not exist)", exc_info=True)
        return []

    return [
        {
            "permit_number": r[0],
            "date": r[1],
            "result": r[2],
            "description": r[3],
            "inspector": r[4],
            "label": r[5],
            "is_pass": r[2] and r[2].lower() in ("approved", "ok", "pass", "passed"),
            "is_fail": r[2] and r[2].lower() in ("disapproved", "fail", "failed", "not approved"),
        }
        for r in rows
    ]


# ── Section 4: New Filings ────────────────────────────────────────

def _get_new_filings(user_id: int, since: date) -> list[dict]:
    """Get new permits filed at watched addresses/parcels/neighborhoods."""
    ph = _ph()
    results: list[dict] = []

    # Address watches
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.new_status, "
        f"pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.street_number = pc.street_number "
        f"  AND UPPER(wi.street_name) = UPPER(pc.street_name) "
        f"  AND wi.watch_type = 'address' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = TRUE "
        f"ORDER BY pc.change_date DESC",
        (user_id, since),
    )
    results.extend(_rows_to_filings(rows))

    # Parcel watches
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.new_status, "
        f"pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.block = pc.block AND wi.lot = pc.lot "
        f"  AND wi.watch_type = 'parcel' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = TRUE "
        f"ORDER BY pc.change_date DESC",
        (user_id, since),
    )
    results.extend(_rows_to_filings(rows))

    # Neighborhood watches (capped)
    rows = query(
        f"SELECT pc.permit_number, pc.change_date, pc.new_status, "
        f"pc.permit_type, pc.street_number, pc.street_name, "
        f"pc.neighborhood, wi.label "
        f"FROM permit_changes pc "
        f"JOIN watch_items wi ON wi.neighborhood = pc.neighborhood "
        f"  AND wi.watch_type = 'neighborhood' AND wi.is_active = TRUE "
        f"WHERE wi.user_id = {ph} AND pc.change_date >= {ph} "
        f"  AND pc.is_new_permit = TRUE "
        f"ORDER BY pc.change_date DESC "
        f"LIMIT 20",
        (user_id, since),
    )
    results.extend(_rows_to_filings(rows))

    return results


def _rows_to_filings(rows: list[tuple]) -> list[dict]:
    return [
        {
            "permit_number": r[0],
            "change_date": r[1],
            "status": r[2],
            "permit_type": r[3],
            "street_number": r[4],
            "street_name": r[5],
            "neighborhood": r[6],
            "label": r[7],
        }
        for r in rows
    ]


# ── Section 5: Team Activity ─────────────────────────────────────

def _get_team_activity(user_id: int, since: date) -> list[dict]:
    """Get new permits involving watched entities (contractors/architects)."""
    ph = _ph()

    # NOTE: The `permits`, `entities`, and `contacts` tables only exist in DuckDB (local),
    # not in PostgreSQL (prod).
    try:
        rows = query(
            f"SELECT p.permit_number, p.permit_type_definition, p.status, "
            f"p.filed_date, p.street_number, p.street_name, p.neighborhood, "
            f"c.role, e.canonical_name, wi.label "
            f"FROM watch_items wi "
            f"JOIN entities e ON wi.entity_id = e.entity_id "
            f"JOIN contacts c ON e.entity_id = c.entity_id "
            f"JOIN permits p ON c.permit_number = p.permit_number "
            f"WHERE wi.user_id = {ph} AND wi.watch_type = 'entity' "
            f"  AND wi.is_active = TRUE AND p.filed_date >= {ph} "
            f"ORDER BY p.filed_date DESC "
            f"LIMIT 30",
            (user_id, str(since)),
        )
    except Exception:
        logger.debug("Team activity query failed (permits/entities tables may not exist)", exc_info=True)
        return []

    return [
        {
            "permit_number": r[0],
            "permit_type": r[1],
            "status": r[2],
            "filed_date": r[3],
            "street_number": r[4],
            "street_name": r[5],
            "neighborhood": r[6],
            "role": r[7],
            "entity_name": r[8],
            "label": r[9],
        }
        for r in rows
    ]


# ── Section 5.5: Plan Review Activity ────────────────────────────

def _get_plan_review_activity(user_id: int, since: date) -> list[dict]:
    """Get recent plan review routing activity for watched permits.

    Queries addenda_changes for reviews completed on watched permits
    since the given date.
    """
    ph = _ph()
    results: list[dict] = []

    # Permit watches — direct match
    try:
        rows = query(
            f"SELECT ac.application_number, ac.change_date, ac.station, "
            f"ac.plan_checked_by, ac.new_review_results, ac.hold_description, "
            f"ac.change_type, ac.department, ac.finish_date, "
            f"ac.permit_type, ac.street_number, ac.street_name, "
            f"ac.neighborhood, wi.label "
            f"FROM addenda_changes ac "
            f"JOIN watch_items wi ON wi.permit_number = ac.application_number "
            f"  AND wi.watch_type = 'permit' AND wi.is_active = TRUE "
            f"WHERE wi.user_id = {ph} AND ac.change_date >= {ph} "
            f"ORDER BY ac.change_date DESC, ac.finish_date DESC "
            f"LIMIT 50",
            (user_id, since),
        )
    except Exception:
        logger.debug("Plan review activity query failed (addenda_changes may not exist)", exc_info=True)
        return []

    results.extend(_rows_to_plan_reviews(rows))

    # Address watches
    try:
        rows = query(
            f"SELECT ac.application_number, ac.change_date, ac.station, "
            f"ac.plan_checked_by, ac.new_review_results, ac.hold_description, "
            f"ac.change_type, ac.department, ac.finish_date, "
            f"ac.permit_type, ac.street_number, ac.street_name, "
            f"ac.neighborhood, wi.label "
            f"FROM addenda_changes ac "
            f"JOIN watch_items wi ON wi.street_number = ac.street_number "
            f"  AND UPPER(wi.street_name) = UPPER(ac.street_name) "
            f"  AND wi.watch_type = 'address' AND wi.is_active = TRUE "
            f"WHERE wi.user_id = {ph} AND ac.change_date >= {ph} "
            f"ORDER BY ac.change_date DESC "
            f"LIMIT 30",
            (user_id, since),
        )
        results.extend(_rows_to_plan_reviews(rows))
    except Exception:
        pass

    # Parcel watches
    try:
        rows = query(
            f"SELECT ac.application_number, ac.change_date, ac.station, "
            f"ac.plan_checked_by, ac.new_review_results, ac.hold_description, "
            f"ac.change_type, ac.department, ac.finish_date, "
            f"ac.permit_type, ac.street_number, ac.street_name, "
            f"ac.neighborhood, wi.label "
            f"FROM addenda_changes ac "
            f"JOIN watch_items wi ON wi.block = ac.block AND wi.lot = ac.lot "
            f"  AND wi.watch_type = 'parcel' AND wi.is_active = TRUE "
            f"WHERE wi.user_id = {ph} AND ac.change_date >= {ph} "
            f"ORDER BY ac.change_date DESC "
            f"LIMIT 30",
            (user_id, since),
        )
        results.extend(_rows_to_plan_reviews(rows))
    except Exception:
        pass

    # Deduplicate by (permit_number, station, change_date)
    seen = set()
    unique = []
    for r in results:
        key = (r["permit_number"], r["station"], str(r["change_date"]))
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def _rows_to_plan_reviews(rows: list[tuple]) -> list[dict]:
    return [
        {
            "permit_number": r[0],
            "change_date": r[1],
            "station": r[2],
            "reviewer": r[3],
            "result": r[4],
            "notes": (r[5] or "")[:120],
            "change_type": r[6],
            "department": r[7],
            "finish_date": r[8],
            "permit_type": r[9],
            "street_number": r[10],
            "street_name": r[11],
            "neighborhood": r[12],
            "label": r[13],
        }
        for r in rows
    ]


# ── Section 6: Expiring Permits ──────────────────────────────────

def _get_expiring_permits(user_id: int) -> list[dict]:
    """Flag watched permits approaching Table B expiration deadline."""
    ph = _ph()

    # NOTE: The `permits` table only exists in DuckDB (local), not in PostgreSQL (prod).
    try:
        rows = query(
            f"SELECT p.permit_number, p.issued_date, p.status, "
            f"p.permit_type_definition, p.street_number, p.street_name, "
            f"p.neighborhood, wi.label, p.revised_cost, p.estimated_cost "
            f"FROM watch_items wi "
            f"JOIN permits p ON wi.permit_number = p.permit_number "
            f"WHERE wi.user_id = {ph} AND wi.watch_type = 'permit' "
            f"  AND wi.is_active = TRUE "
            f"  AND p.issued_date IS NOT NULL "
            f"  AND p.completed_date IS NULL "
            f"  AND p.status NOT IN ('completed', 'expired', 'cancelled', 'withdrawn')",
            (user_id,),
        )
    except Exception:
        logger.debug("Expiring permits query failed (permits table may not exist)", exc_info=True)
        return []

    results = []
    for row in rows:
        (permit_number, issued_date, status, permit_type,
         street_number, street_name, neighborhood, label,
         revised_cost, estimated_cost) = row

        issued = _parse_date(issued_date)
        if not issued:
            continue

        permit_dict = {
            "permit_type_definition": permit_type,
            "revised_cost": revised_cost,
            "estimated_cost": estimated_cost,
        }
        validity = _validity_days(permit_dict)
        days_since_issued = (date.today() - issued).days
        expires_in = validity - days_since_issued

        # Only flag if within warning window or already past
        if expires_in > EXPIRATION_WARNING_DAYS:
            continue

        results.append({
            "permit_number": permit_number,
            "issued_date": issued_date,
            "status": status,
            "permit_type": permit_type,
            "street_number": street_number,
            "street_name": street_name,
            "neighborhood": neighborhood,
            "label": label,
            "days_since_issued": days_since_issued,
            "validity_days": validity,
            "expires_in": expires_in,
            "is_expired": expires_in <= 0,
        })

    # Sort: expired first, then soonest to expire
    results.sort(key=lambda x: x["expires_in"])
    return results


# ── Section 7: Property Synopsis ─────────────────────────────────

def _get_property_synopsis(street_number: str, street_name: str) -> dict | None:
    """Build a property overview from permits at the user's primary address.

    Returns a dict with total counts, status breakdown, latest permit info,
    neighborhood, and parcel identifier — or None if no permits found.
    """
    ph = _ph()

    # Match the same way permit_lookup does — base name + full name+suffix
    # Includes fuzzy space matching: "robin hood" matches "ROBINHOOD"
    # NOTE: The `permits` table only exists in DuckDB (local), not in PostgreSQL (prod).
    try:
        from src.tools.permit_lookup import _strip_suffix
        base_name, _suffix = _strip_suffix(street_name)
        base_pattern = f"%{base_name}%"
        full_pattern = f"%{street_name}%"
        nospace_pattern = f"%{base_name.replace(' ', '')}%"
        rows = query(
            f"SELECT permit_number, permit_type_definition, status, "
            f"filed_date, issued_date, completed_date, estimated_cost, "
            f"description, neighborhood, block, lot, street_suffix "
            f"FROM permits "
            f"WHERE street_number = {ph} "
            f"  AND ("
            f"    UPPER(street_name) LIKE UPPER({ph})"
            f"    OR UPPER(street_name) LIKE UPPER({ph})"
            f"    OR UPPER(COALESCE(street_name, '') || ' ' || COALESCE(street_suffix, '')) LIKE UPPER({ph})"
            f"    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') LIKE UPPER({ph})"
            f"  ) "
            f"ORDER BY filed_date DESC",
            (street_number, base_pattern, full_pattern, full_pattern, nospace_pattern),
        )
    except Exception:
        logger.debug("Property synopsis query failed (permits table may not exist)", exc_info=True)
        return None

    if not rows:
        return None

    total = len(rows)

    # Status breakdown
    status_counts: dict[str, int] = {}
    for r in rows:
        st = (r[2] or "unknown").lower()
        status_counts[st] = status_counts.get(st, 0) + 1

    active_statuses = {"filed", "approved", "issued", "reinstated"}
    active_count = sum(v for k, v in status_counts.items() if k in active_statuses)
    completed_count = status_counts.get("complete", 0) + status_counts.get("completed", 0)

    # Most recent permit
    latest = rows[0]
    latest_info = {
        "permit_number": latest[0],
        "type": latest[1] or "Unknown",
        "status": latest[2] or "Unknown",
        "filed_date": latest[3],
        "description": (latest[7] or "")[:120],
    }

    # Collect unique permit types
    type_counts: dict[str, int] = {}
    for r in rows:
        pt = r[1] or "Other"
        type_counts[pt] = type_counts.get(pt, 0) + 1
    top_types = sorted(type_counts.items(), key=lambda x: -x[1])[:5]

    # Neighborhood + parcel from first row
    neighborhood = latest[8]
    block = latest[9]
    lot = latest[10]
    street_suffix = latest[11] or ""

    # Full display address
    display_address = f"{street_number} {street_name}"
    if street_suffix and street_suffix.lower() not in street_name.lower():
        display_address = f"{street_number} {street_name} {street_suffix}"

    # Date range
    dates = [r[3] for r in rows if r[3]]
    earliest_date = min(dates) if dates else None
    latest_date = max(dates) if dates else None

    return {
        "address": display_address,
        "neighborhood": neighborhood,
        "block": block,
        "lot": lot,
        "total_permits": total,
        "active_count": active_count,
        "completed_count": completed_count,
        "status_counts": status_counts,
        "latest_permit": latest_info,
        "top_types": top_types,
        "earliest_date": earliest_date,
        "latest_date": latest_date,
    }


# ── Section 8: Regulatory Alerts ──────────────────────────────────

def _get_regulatory_alerts() -> list[dict]:
    """Get active regulatory watch items for the morning brief.

    Returns items with status 'monitoring' or 'passed' (not 'effective' or
    'withdrawn') so users stay aware of pending changes.
    """
    try:
        from web.regulatory_watch import get_regulatory_alerts
        return get_regulatory_alerts()
    except Exception:
        logger.debug("Regulatory watch query failed (non-fatal)", exc_info=True)
        return []


# ── Section 9: Data Freshness ────────────────────────────────────

def _get_last_refresh() -> dict | None:
    """Get data freshness info from cron_log.

    Returns dict with last_success timestamp, hours_ago, and is_stale flag,
    or None if cron_log table doesn't exist or has no entries.
    """
    try:
        row = query_one(
            "SELECT started_at, completed_at, was_catchup "
            "FROM cron_log "
            "WHERE job_type = 'nightly' AND status = 'success' "
            "ORDER BY started_at DESC LIMIT 1"
        )
    except Exception:
        # Table doesn't exist yet (first deploy before any cron run)
        return None

    if not row:
        return None

    started_at = row[0]
    was_catchup = row[2] if len(row) > 2 else False

    # Parse timestamp
    if isinstance(started_at, str):
        try:
            from datetime import datetime, timezone
            ts = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
    else:
        ts = started_at

    # Calculate hours ago
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = now - ts
    hours_ago = delta.total_seconds() / 3600

    return {
        "last_success": ts.strftime("%b %d, %Y at %I:%M %p UTC"),
        "last_success_date": ts.strftime("%b %d"),
        "hours_ago": round(hours_ago, 1),
        "is_stale": hours_ago > 36,  # Allow some buffer beyond 24h
        "was_catchup": bool(was_catchup),
    }
