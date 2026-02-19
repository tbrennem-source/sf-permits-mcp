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

    # ── Addenda-based rules (Tier 0 — plan review intelligence) ──
    all_pnums = [p["permit_number"] for p in permit_dicts if p["permit_number"]]
    if all_pnums:
        # ── Rule 9: Station Stall ──
        items.extend(_rule_station_stall(all_pnums, permit_dicts, today))
        # ── Rule 10: Hold Unresolved ──
        items.extend(_rule_hold_unresolved(all_pnums, permit_dicts))
        # ── Rule 11: All Stations Clear ──
        items.extend(_rule_all_stations_clear(all_pnums, permit_dicts))
        # ── Rule 12: Fresh Approval ──
        items.extend(_rule_fresh_approval(all_pnums, permit_dicts, today))
        # ── Rule 13: Comment Response Needed ──
        items.extend(_rule_comment_response_needed(all_pnums, permit_dicts, today))
        # ── Rule 14: Revision Escalation ──
        items.extend(_rule_revision_escalation(all_pnums, permit_dicts))

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


# ---------------------------------------------------------------------------
# Addenda-based rules (Tier 0 — plan review operational intelligence)
# ---------------------------------------------------------------------------

def _permit_address(permit_dicts: list[dict], permit_number: str) -> str:
    """Look up address for a permit number from the already-loaded permit data."""
    for p in permit_dicts:
        if p["permit_number"] == permit_number:
            return p["address"]
    return ""


def _rule_station_stall(permit_numbers: list[str], permit_dicts: list[dict],
                        today: date) -> list[dict]:
    """Routing step arrived >30 days ago with no finish_date and no hold → stalled."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    placeholders = ",".join([ph] * len(permit_numbers))
    cutoff = str(today - timedelta(days=30))
    try:
        rows = query(
            f"SELECT application_number, station, plan_checked_by, arrive, "
            f"       addenda_number, step "
            f"FROM addenda "
            f"WHERE application_number IN ({placeholders}) "
            f"  AND finish_date IS NULL "
            f"  AND (hold_description IS NULL OR hold_description = '') "
            f"  AND arrive IS NOT NULL "
            f"  AND CAST(arrive AS TEXT) <= {ph} "
            f"ORDER BY arrive ASC "
            f"LIMIT 10",
            permit_numbers + [cutoff],
        )
    except Exception:
        logger.debug("station_stall query failed", exc_info=True)
        return items

    for r in rows:
        pnum, station, reviewer, arrive, addenda_num, step = r
        arrive_dt = _parse_date(str(arrive) if arrive else None)
        if not arrive_dt:
            continue
        days_pending = (today - arrive_dt).days
        address = _permit_address(permit_dicts, pnum)
        reviewer_str = f" (assigned to {reviewer})" if reviewer else ""
        severity = "critical" if days_pending > 60 else "warning"
        items.append(_make_item(
            "station_stall", severity,
            f"Plan review stalled at {station}",
            f"Permit {pnum}: {station} has had this for {days_pending} days "
            f"with no activity{reviewer_str}.",
            [pnum], address,
            f"Follow up with {station} on routing step status",
            "Unblock plan review progress",
        ))
    return items


def _rule_hold_unresolved(permit_numbers: list[str],
                          permit_dicts: list[dict]) -> list[dict]:
    """Routing step has hold_description but no finish_date → outstanding hold."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    placeholders = ",".join([ph] * len(permit_numbers))
    try:
        rows = query(
            f"SELECT application_number, station, hold_description, "
            f"       plan_checked_by, addenda_number, arrive "
            f"FROM addenda "
            f"WHERE application_number IN ({placeholders}) "
            f"  AND hold_description IS NOT NULL AND hold_description != '' "
            f"  AND finish_date IS NULL "
            f"ORDER BY arrive ASC "
            f"LIMIT 10",
            permit_numbers,
        )
    except Exception:
        logger.debug("hold_unresolved query failed", exc_info=True)
        return items

    for r in rows:
        pnum, station, hold, reviewer, addenda_num, arrive = r
        address = _permit_address(permit_dicts, pnum)
        hold_preview = (hold or "")[:120]
        if len(hold or "") > 120:
            hold_preview += "…"
        items.append(_make_item(
            "hold_unresolved", "warning",
            f"Outstanding hold at {station}",
            f"Permit {pnum}: {station} placed a hold — \"{hold_preview}\"",
            [pnum], address,
            f"Address hold comments to unblock {station} sign-off",
            "Remove plan review blocker",
        ))
    return items


def _rule_all_stations_clear(permit_numbers: list[str],
                             permit_dicts: list[dict]) -> list[dict]:
    """Every routing step for latest addenda has finish_date → ready for issuance."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    # Only check permits that are still in 'filed' or 'plancheck' status
    filed_permits = [p for p in permit_dicts if p["status"] in ("filed", "plancheck")]
    if not filed_permits:
        return items

    for p in filed_permits:
        pnum = p["permit_number"]
        try:
            # Get the latest addenda_number
            rev_rows = query(
                f"SELECT MAX(addenda_number) FROM addenda "
                f"WHERE application_number = {ph}",
                (pnum,),
            )
            if not rev_rows or rev_rows[0][0] is None:
                continue
            rev = rev_rows[0][0]

            # Count total vs completed
            count_rows = query(
                f"SELECT COUNT(*), "
                f"       COUNT(*) FILTER (WHERE finish_date IS NOT NULL) "
                f"FROM addenda "
                f"WHERE application_number = {ph} AND addenda_number = {ph}",
                (pnum, rev),
            )
            if not count_rows or not count_rows[0]:
                continue
            total, completed = count_rows[0]
            if total > 0 and total == completed:
                items.append(_make_item(
                    "all_stations_clear", "opportunity",
                    f"All stations signed off — {p['address']}",
                    f"Permit {pnum}: all {total} plan review stations have completed review "
                    f"(rev {rev}). Follow up on permit issuance.",
                    [pnum], p["address"],
                    "Contact DBI about permit issuance — all reviews complete",
                    "Accelerate issuance by days-to-weeks",
                ))
        except Exception:
            logger.debug("all_stations_clear query failed for %s", pnum, exc_info=True)
            continue
    return items


def _rule_fresh_approval(permit_numbers: list[str], permit_dicts: list[dict],
                         today: date) -> list[dict]:
    """Routing step approved in last 7 days → notify of progress."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    placeholders = ",".join([ph] * len(permit_numbers))
    cutoff = str(today - timedelta(days=7))
    try:
        rows = query(
            f"SELECT application_number, station, plan_checked_by, "
            f"       review_results, finish_date, addenda_number "
            f"FROM addenda "
            f"WHERE application_number IN ({placeholders}) "
            f"  AND LOWER(review_results) LIKE '%approv%' "
            f"  AND finish_date IS NOT NULL "
            f"  AND CAST(finish_date AS TEXT) >= {ph} "
            f"ORDER BY finish_date DESC "
            f"LIMIT 10",
            permit_numbers + [cutoff],
        )
    except Exception:
        logger.debug("fresh_approval query failed", exc_info=True)
        return items

    # Group by permit to avoid noise
    seen_permits = set()
    for r in rows:
        pnum, station, reviewer, result, finish, addenda_num = r
        if pnum in seen_permits:
            continue
        seen_permits.add(pnum)
        address = _permit_address(permit_dicts, pnum)
        finish_str = str(finish)[:10] if finish else "recently"
        reviewer_str = f" by {reviewer}" if reviewer else ""
        items.append(_make_item(
            "fresh_approval", "opportunity",
            f"Plan review approved at {station}",
            f"Permit {pnum}: {station} approved{reviewer_str} on {finish_str}.",
            [pnum], address,
            "Check remaining stations — project is moving",
        ))
    return items


def _rule_comment_response_needed(permit_numbers: list[str],
                                  permit_dicts: list[dict],
                                  today: date) -> list[dict]:
    """'Issued Comments' result in last 14 days → needs response."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    placeholders = ",".join([ph] * len(permit_numbers))
    cutoff = str(today - timedelta(days=14))
    try:
        rows = query(
            f"SELECT application_number, station, plan_checked_by, "
            f"       review_results, finish_date, hold_description "
            f"FROM addenda "
            f"WHERE application_number IN ({placeholders}) "
            f"  AND LOWER(review_results) LIKE '%comment%' "
            f"  AND finish_date IS NOT NULL "
            f"  AND CAST(finish_date AS TEXT) >= {ph} "
            f"ORDER BY finish_date DESC "
            f"LIMIT 10",
            permit_numbers + [cutoff],
        )
    except Exception:
        logger.debug("comment_response query failed", exc_info=True)
        return items

    seen_permits = set()
    for r in rows:
        pnum, station, reviewer, result, finish, hold = r
        if pnum in seen_permits:
            continue
        seen_permits.add(pnum)
        address = _permit_address(permit_dicts, pnum)
        finish_str = str(finish)[:10] if finish else "recently"
        reviewer_str = f" by {reviewer}" if reviewer else ""
        hold_str = ""
        if hold:
            hold_preview = (hold or "")[:100]
            if len(hold or "") > 100:
                hold_preview += "…"
            hold_str = f" Comments: \"{hold_preview}\""
        items.append(_make_item(
            "comment_response_needed", "warning",
            f"Plan checker comments at {station}",
            f"Permit {pnum}: {station} issued comments{reviewer_str} on {finish_str}.{hold_str}",
            [pnum], address,
            "Prepare and submit correction response",
            "Unblock plan review — delays compound",
        ))
    return items


def _rule_revision_escalation(permit_numbers: list[str],
                              permit_dicts: list[dict]) -> list[dict]:
    """addenda_number > 3 → project in multiple revision cycles."""
    items = []
    if not permit_numbers:
        return items
    ph = _ph()
    # Only check filed permits (still in plan review)
    filed_permits = [p for p in permit_dicts if p["status"] in ("filed", "plancheck")]
    if not filed_permits:
        return items

    for p in filed_permits:
        pnum = p["permit_number"]
        try:
            rev_rows = query(
                f"SELECT MAX(addenda_number) FROM addenda "
                f"WHERE application_number = {ph}",
                (pnum,),
            )
            if not rev_rows or rev_rows[0][0] is None:
                continue
            max_rev = rev_rows[0][0]
            if max_rev > 3:
                items.append(_make_item(
                    "revision_escalation", "warning",
                    f"Multiple revision cycles at {p['address']}",
                    f"Permit {pnum} is on revision {max_rev} — projects with 4+ "
                    f"revision cycles benefit from a supervisor meeting.",
                    [pnum], p["address"],
                    "Request meeting with plan check supervisor to resolve outstanding issues",
                    "Break the correction cycle",
                ))
        except Exception:
            logger.debug("revision_escalation query failed for %s", pnum, exc_info=True)
            continue
    return items
