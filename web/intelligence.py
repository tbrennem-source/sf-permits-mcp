"""Proactive intelligence — rule-based action items for permit portfolios.

Analyzes watched permits to generate specific, actionable recommendations
like bundling inspections, filing extensions, coordinating companion permits.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import BACKEND, query
from web.auth import get_watches

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except (ValueError, TypeError):
        return None


def get_action_items(user_id: int) -> list[dict]:
    """Generate proactive action items for a user's watched permits.

    Runs all rules against the user's watched permits and returns
    a prioritized list of recommendations.

    Returns empty list if permit/inspection tables are unavailable
    (e.g. on production where bulk data is in DuckDB, not Postgres).
    """
    watches = get_watches(user_id)
    if not watches:
        return []

    # Gather all watched permit numbers and parcels
    permit_numbers = set()
    parcels = set()  # (block, lot) tuples

    for w in watches:
        if w["watch_type"] == "permit" and w.get("permit_number"):
            permit_numbers.add(w["permit_number"])
        if w.get("block") and w.get("lot"):
            parcels.add((w["block"], w["lot"]))

    # Also find permits at watched addresses
    for w in watches:
        if w["watch_type"] == "address" and w.get("street_number") and w.get("street_name"):
            try:
                rows = query(
                    f"SELECT permit_number, block, lot FROM permits "
                    f"WHERE street_number = {_ph()} AND UPPER(street_name) = {_ph()} "
                    f"AND status IN ('filed', 'issued', 'triage')",
                    (w["street_number"], w["street_name"].upper()),
                )
            except Exception as e:
                logger.warning("permits table query failed (address): %s", e)
                return []
            for r in rows:
                permit_numbers.add(r[0])
                if r[1] and r[2]:
                    parcels.add((r[1], r[2]))

    if not permit_numbers and not parcels:
        return []

    # Get active permits data
    try:
        if permit_numbers:
            placeholders = ",".join([_ph()] * len(permit_numbers))
            permits = query(
                f"SELECT permit_number, permit_type, permit_type_definition, status, "
                f"status_date, filed_date, issued_date, estimated_cost, revised_cost, "
                f"description, street_number, street_name, block, lot "
                f"FROM permits WHERE permit_number IN ({placeholders}) "
                f"AND status IN ('filed', 'issued', 'triage')",
                list(permit_numbers),
            )
        else:
            permits = []

        # Also get permits at watched parcels not already found
        for block, lot in parcels:
            extra = query(
                f"SELECT permit_number, permit_type, permit_type_definition, status, "
                f"status_date, filed_date, issued_date, estimated_cost, revised_cost, "
                f"description, street_number, street_name, block, lot "
                f"FROM permits WHERE block = {_ph()} AND lot = {_ph()} "
                f"AND status IN ('filed', 'issued', 'triage')",
                (block, lot),
            )
            seen = {p[0] for p in permits}
            permits.extend(r for r in extra if r[0] not in seen)
    except Exception as e:
        logger.warning("permits table query failed: %s", e)
        return []

    # Parse into dicts
    permit_dicts = []
    for row in permits:
        permit_dicts.append({
            "permit_number": row[0],
            "permit_type": row[1] or "",
            "permit_type_def": row[2] or "",
            "status": row[3] or "",
            "status_date": _parse_date(row[4]),
            "filed_date": _parse_date(row[5]),
            "issued_date": _parse_date(row[6]),
            "estimated_cost": row[7] or 0,
            "revised_cost": row[8] or 0,
            "description": (row[9] or "")[:200],
            "address": f"{row[10] or ''} {row[11] or ''}".strip(),
            "block": row[12] or "",
            "lot": row[13] or "",
        })

    items: list[dict] = []
    today = date.today()

    # ── Rule 1: Bundle Inspections ──
    items.extend(_rule_bundle_inspections(permit_dicts, today))

    # ── Rule 2: Companion Permit Coordination ──
    items.extend(_rule_companion_permits(permit_dicts))

    # ── Rule 3: Triage Delay ──
    items.extend(_rule_triage_delay(permit_dicts, today))

    # ── Rule 4: Plan Check Delay ──
    items.extend(_rule_plan_check_delay(permit_dicts, today))

    # ── Rule 5: Completion Push ──
    items.extend(_rule_completion_push(permit_dicts))

    # ── Rule 6: Extension Needed ──
    items.extend(_rule_extension_needed(permit_dicts, today))

    # ── Rule 7: Cost Variance ──
    items.extend(_rule_cost_variance(permit_dicts))

    # ── Rule 8: Fresh Issuance ──
    items.extend(_rule_fresh_issuance(permit_dicts, today))

    # Sort: critical → warning → opportunity
    severity_order = {"critical": 0, "warning": 1, "opportunity": 2}
    items.sort(key=lambda x: severity_order.get(x["severity"], 3))

    return items


def _make_item(rule, severity, title, detail, permits, address, action, savings=""):
    return {
        "rule": rule,
        "severity": severity,
        "title": title,
        "detail": detail,
        "permits": permits,
        "address": address,
        "suggested_action": action,
        "savings_estimate": savings,
    }


def _rule_bundle_inspections(permits, today):
    """2+ permits at same block/lot with active inspections → bundle."""
    items = []
    by_parcel = {}
    for p in permits:
        if p["status"] == "issued" and p["block"] and p["lot"]:
            key = (p["block"], p["lot"])
            by_parcel.setdefault(key, []).append(p)

    for (block, lot), group in by_parcel.items():
        if len(group) >= 2:
            # Check if recent inspection activity (last 90 days)
            try:
                insp = query(
                    f"SELECT COUNT(*) FROM inspections WHERE block = {_ph()} AND lot = {_ph()} "
                    f"AND scheduled_date >= {_ph()}",
                    (block, lot, str(today - timedelta(days=90))),
                )
            except Exception:
                continue
            if insp and insp[0][0] > 0:
                pnums = [p["permit_number"] for p in group]
                items.append(_make_item(
                    "bundle_inspections", "opportunity",
                    f"Bundle inspections at {group[0]['address']}",
                    f"{len(group)} permits at this address have active inspections — "
                    f"request same-day scheduling to save time.",
                    pnums, group[0]["address"],
                    "Request bundled inspection for all permits",
                    "1 day of contractor wait time",
                ))
    return items


def _rule_companion_permits(permits):
    """Related permits at same address (deferred MEP, fire + building)."""
    items = []
    by_parcel = {}
    for p in permits:
        if p["block"] and p["lot"]:
            key = (p["block"], p["lot"])
            by_parcel.setdefault(key, []).append(p)

    for (block, lot), group in by_parcel.items():
        if len(group) < 2:
            continue
        # Check for deferred/companion patterns
        desc_lower = " ".join(p["description"].lower() for p in group)
        if "deferred" in desc_lower or "ref pa#" in desc_lower or "ref app#" in desc_lower:
            pnums = [p["permit_number"] for p in group]
            items.append(_make_item(
                "companion_permits", "opportunity",
                f"Coordinate companion permits at {group[0]['address']}",
                f"{len(group)} related permits — coordinate plan check and inspections together.",
                pnums, group[0]["address"],
                "Align inspection schedules for coordinated closeout",
                "Avoid sequential delays",
            ))
    return items


def _rule_triage_delay(permits, today):
    """Permit in triage > 30 days."""
    items = []
    for p in permits:
        if p["status"] == "triage" and p["status_date"]:
            days = (today - p["status_date"]).days
            if days > 30:
                items.append(_make_item(
                    "triage_delay", "warning",
                    f"Triage delay at {p['address']}",
                    f"Permit {p['permit_number']} has been in triage for {days} days — "
                    f"typical triage takes 5-10 business days.",
                    [p["permit_number"]], p["address"],
                    "Follow up with DBI intake on triage status",
                ))
    return items


def _rule_plan_check_delay(permits, today):
    """Filed > 180 days without issuance."""
    items = []
    for p in permits:
        if p["status"] == "filed" and p["filed_date"]:
            days = (today - p["filed_date"]).days
            if days > 365:
                items.append(_make_item(
                    "plan_check_delay", "critical",
                    f"Plan check stalled at {p['address']}",
                    f"Permit {p['permit_number']} filed {days} days ago with no issuance.",
                    [p["permit_number"]], p["address"],
                    "Schedule station assignment meeting or consider re-filing",
                ))
            elif days > 180:
                items.append(_make_item(
                    "plan_check_delay", "warning",
                    f"Plan check delay at {p['address']}",
                    f"Permit {p['permit_number']} filed {days} days ago — "
                    f"check for outstanding corrections.",
                    [p["permit_number"]], p["address"],
                    "Check plan check status for outstanding corrections",
                ))
    return items


def _rule_completion_push(permits):
    """Pre-final passed but no final yet → schedule final."""
    items = []
    for p in permits:
        if p["status"] != "issued" or not p["block"] or not p["lot"]:
            continue
        try:
            insp = query(
                f"SELECT inspection_description, result FROM inspections "
                f"WHERE block = {_ph()} AND lot = {_ph()} "
                f"AND UPPER(inspection_description) LIKE '%PRE-FINAL%' "
                f"AND result = 'PASSED' "
                f"ORDER BY scheduled_date DESC LIMIT 1",
                (p["block"], p["lot"]),
            )
        except Exception:
            continue
        if not insp:
            continue
        # Check if final already passed
        try:
            final = query(
                f"SELECT result FROM inspections "
                f"WHERE block = {_ph()} AND lot = {_ph()} "
                f"AND UPPER(inspection_description) LIKE '%FINAL INSPECT%' "
                f"AND result = 'PASSED' "
                f"ORDER BY scheduled_date DESC LIMIT 1",
                (p["block"], p["lot"]),
            )
        except Exception:
            continue
        if not final:
            items.append(_make_item(
                "completion_push", "opportunity",
                f"Ready for final at {p['address']}",
                f"Pre-final inspection passed — schedule final to close out "
                f"permit {p['permit_number']}.",
                [p["permit_number"]], p["address"],
                "Schedule final inspection",
                "Close out permit, stop carrying costs",
            ))
    return items


def _rule_extension_needed(permits, today):
    """Issued > 2.5 years → approaching 3-year expiration."""
    items = []
    for p in permits:
        if p["status"] == "issued" and p["issued_date"]:
            years = (today - p["issued_date"]).days / 365.25
            if years >= 2.75:
                days_until = int(3 * 365.25 - (today - p["issued_date"]).days)
                items.append(_make_item(
                    "extension_needed", "critical",
                    f"Extension needed at {p['address']}",
                    f"Permit {p['permit_number']} issued {int(years * 12)} months ago — "
                    f"~{max(0, days_until)} days until expiration.",
                    [p["permit_number"]], p["address"],
                    "File permit extension ($200-500) before 3-year expiration",
                    f"Avoid ${max(5000, int((p['revised_cost'] or p['estimated_cost'] or 0) * 0.02)):,} in re-filing costs",
                ))
            elif years >= 2.5:
                days_until = int(3 * 365.25 - (today - p["issued_date"]).days)
                items.append(_make_item(
                    "extension_needed", "warning",
                    f"Expiration approaching at {p['address']}",
                    f"Permit {p['permit_number']} issued {int(years * 12)} months ago — "
                    f"~{max(0, days_until)} days until 3-year expiration.",
                    [p["permit_number"]], p["address"],
                    "Plan permit extension filing",
                ))
    return items


def _rule_cost_variance(permits):
    """Revised cost significantly different from estimated (>100% increase)."""
    items = []
    for p in permits:
        est = p["estimated_cost"]
        rev = p["revised_cost"]
        if est and rev and est > 100 and rev > est * 2:
            pct = int((rev - est) / est * 100)
            items.append(_make_item(
                "cost_variance", "warning",
                f"Cost increase at {p['address']}",
                f"Permit {p['permit_number']}: estimated ${est:,.0f} → revised ${rev:,.0f} (+{pct}%).",
                [p["permit_number"]], p["address"],
                "Review scope change and fee implications",
            ))
    return items


def _rule_fresh_issuance(permits, today):
    """Permit just issued in last 7 days → start clock reminder."""
    items = []
    for p in permits:
        if p["status"] == "issued" and p["issued_date"]:
            days = (today - p["issued_date"]).days
            if 0 <= days <= 7:
                items.append(_make_item(
                    "fresh_issuance", "opportunity",
                    f"Permit just issued at {p['address']}",
                    f"Permit {p['permit_number']} issued {days} days ago — "
                    f"schedule first inspection within 180 days to avoid expiration.",
                    [p["permit_number"]], p["address"],
                    "Schedule site verification or first inspection",
                    "Prevent 180-day inactivity expiration",
                ))
    return items
