"""Portfolio dashboard — property card grid with health indicators.

Aggregates watched permits into property-level cards with status,
cost, health, latest inspection, and filtering support.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import BACKEND, query, query_one
from web.auth import get_watches

logger = logging.getLogger(__name__)


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


def get_portfolio(user_id: int) -> dict:
    """Build the portfolio dashboard data.

    Groups watched items into property cards with health indicators,
    permit details, and latest inspection data.

    Returns dict with keys: properties, summary
    """
    watches = get_watches(user_id)
    if not watches:
        return {"properties": [], "summary": _empty_summary()}

    # Collect all permit numbers and address/parcel pairs from watches
    watch_permits = set()
    watch_addresses = set()
    watch_parcels = set()

    for w in watches:
        if w["watch_type"] == "permit" and w.get("permit_number"):
            watch_permits.add(w["permit_number"])
        elif w["watch_type"] == "address" and w.get("street_number") and w.get("street_name"):
            watch_addresses.add((w["street_number"], w["street_name"].upper()))
        elif w["watch_type"] == "parcel" and w.get("block") and w.get("lot"):
            watch_parcels.add((w["block"], w["lot"]))
        elif w["watch_type"] == "neighborhood" and w.get("neighborhood"):
            # Neighborhoods could produce too many results; skip for portfolio
            pass
        elif w["watch_type"] == "entity" and w.get("entity_id"):
            # Entity watches — find their permits
            eid = w["entity_id"]
            rows = query(
                f"SELECT DISTINCT permit_number FROM contacts WHERE entity_id = {_ph()}",
                (eid,),
            )
            for r in rows:
                watch_permits.add(r[0])

    # Build SQL to get all matching permits
    conditions = []
    params = []

    if watch_permits:
        placeholders = ",".join([_ph()] * len(watch_permits))
        conditions.append(f"p.permit_number IN ({placeholders})")
        params.extend(watch_permits)

    if watch_addresses:
        addr_conds = []
        for sn, st in watch_addresses:
            addr_conds.append(f"(p.street_number = {_ph()} AND UPPER(p.street_name) = {_ph()})")
            params.extend([sn, st])
        conditions.append("(" + " OR ".join(addr_conds) + ")")

    if watch_parcels:
        parcel_conds = []
        for b, l in watch_parcels:
            parcel_conds.append(f"(p.block = {_ph()} AND p.lot = {_ph()})")
            params.extend([b, l])
        conditions.append("(" + " OR ".join(parcel_conds) + ")")

    if not conditions:
        return {"properties": [], "summary": _empty_summary()}

    where = " OR ".join(conditions)

    rows = query(
        f"SELECT p.permit_number, p.permit_type, p.permit_type_definition, "
        f"p.status, p.status_date, p.filed_date, p.issued_date, "
        f"p.estimated_cost, p.revised_cost, p.description, "
        f"p.street_number, p.street_name, p.block, p.lot, p.neighborhood "
        f"FROM permits p WHERE {where} "
        f"ORDER BY p.status_date DESC",
        params,
    )

    # Group by address (block/lot)
    property_map: dict[str, dict] = {}
    today = date.today()

    for row in rows:
        pn, ptype, ptype_def = row[0], row[1], row[2]
        status, status_date_str = row[3], row[4]
        filed_str, issued_str = row[5], row[6]
        est_cost, rev_cost = row[7], row[8]
        desc = (row[9] or "")[:150]
        snum, sname = row[10] or "", row[11] or ""
        block, lot = row[12] or "", row[13] or ""
        neighborhood = row[14] or ""

        addr = f"{snum} {sname}".strip()
        key = f"{block}/{lot}" if block and lot else addr

        status_date = _parse_date(status_date_str)
        filed_date = _parse_date(filed_str)
        issued_date = _parse_date(issued_str)
        cost = rev_cost or est_cost or 0

        # Health calculation — action-signal based, not pure age thresholds.
        # Filed: stalled (no activity 60+d) = AT RISK; slow but moving = BEHIND/SLOWER.
        # Issued: expiration approaching = AT RISK/BEHIND; long construction is NORMAL.
        health = "on_track"
        health_reason = ""
        days_in_status = (today - status_date).days if status_date else 0

        if status == "filed" and filed_date:
            days_filed = (today - filed_date).days
            stalled = days_in_status > 60  # no status change in 60+ days
            if days_filed > 365 and stalled:
                health = "at_risk"
                health_reason = f"{pn} filed {days_filed}d ago, no activity in {days_in_status}d"
            elif days_filed > 365:
                health = "behind"
                health_reason = f"{pn} filed {days_filed}d ago (plan check)"
            elif days_filed > 180:
                health = "slower"
                health_reason = f"{pn} filed {days_filed}d ago (plan check)"

        if status == "issued" and issued_date:
            from web.brief import _validity_days
            permit_dict = {
                "permit_type_definition": ptype_def or ptype or "",
                "revised_cost": rev_cost,
                "estimated_cost": est_cost,
            }
            validity = _validity_days(permit_dict)
            days_issued = (today - issued_date).days
            expires_in = validity - days_issued
            recently_active = days_in_status <= 30
            if expires_in <= 0:
                # Permit already expired — severity depends on site activity
                if recently_active:
                    health = "behind"
                    health_reason = f"{pn} permit expired {abs(expires_in)}d ago (active site)"
                else:
                    health = "at_risk"
                    health_reason = f"{pn} permit expired {abs(expires_in)}d ago"
            elif expires_in <= 30:
                health = "at_risk"
                health_reason = f"{pn} expires in {expires_in}d"
            elif expires_in <= 90:
                health = "behind"
                health_reason = f"{pn} expires in {expires_in}d"
            elif expires_in <= 180:
                health = "slower"
                health_reason = f"{pn} expires in {expires_in}d"

        days_in_status = (today - status_date).days if status_date else 0
        permit_data = {
            "permit_number": pn,
            "permit_type": ptype_def or ptype or "",
            "status": status or "",
            "status_date": str(status_date) if status_date else "",
            "filed_date": str(filed_date) if filed_date else "",
            "issued_date": str(issued_date) if issued_date else "",
            "cost": cost,
            "description": desc,
            "health": health,
            "days_in_status": days_in_status,
        }

        if key not in property_map:
            property_map[key] = {
                "address": addr,
                "block": block,
                "lot": lot,
                "neighborhood": neighborhood,
                "permits": [],
                "worst_health": "on_track",
                "health_reason": "",
                "total_cost": 0,
                "latest_activity": str(status_date) if status_date else "",
                "active_count": 0,
                "tags": "",
            }

        prop = property_map[key]
        prop["permits"].append(permit_data)
        prop["total_cost"] += cost

        # Track latest activity
        if status_date and str(status_date) > prop["latest_activity"]:
            prop["latest_activity"] = str(status_date)

        # Track worst health
        health_order = {"on_track": 0, "slower": 1, "behind": 2, "at_risk": 3}
        if health_order.get(health, 0) > health_order.get(prop["worst_health"], 0):
            prop["worst_health"] = health
            prop["health_reason"] = health_reason

        # Count active permits
        if status in ("filed", "issued", "triage"):
            prop["active_count"] += 1

    properties = list(property_map.values())

    # Compute days_since_activity for recency signal
    for prop in properties:
        la = _parse_date(prop.get("latest_activity", ""))
        prop["days_since_activity"] = (today - la).days if la else None

    # Get tags from watch items
    watch_tags = {}
    for w in watches:
        tags = w.get("tags", "")
        if tags:
            if w.get("block") and w.get("lot"):
                watch_tags[f"{w['block']}/{w['lot']}"] = tags
            elif w.get("street_number") and w.get("street_name"):
                watch_tags[f"{w['street_number']} {w['street_name']}".strip().upper()] = tags

    for prop in properties:
        key = f"{prop['block']}/{prop['lot']}" if prop["block"] and prop["lot"] else prop["address"].upper()
        prop["tags"] = watch_tags.get(key, "")

    # Get latest inspection for each property
    for prop in properties:
        if prop["block"] and prop["lot"]:
            insp = query(
                f"SELECT scheduled_date, result, inspection_description "
                f"FROM inspections WHERE block = {_ph()} AND lot = {_ph()} "
                f"ORDER BY scheduled_date DESC LIMIT 1",
                (prop["block"], prop["lot"]),
            )
            if insp:
                prop["last_inspection"] = {
                    "date": str(_parse_date(insp[0][0])) if insp[0][0] else "",
                    "result": insp[0][1] or "",
                    "type": insp[0][2] or "",
                }
            else:
                prop["last_inspection"] = None
        else:
            prop["last_inspection"] = None

    # Get enforcement data (violations + complaints) for each property
    for prop in properties:
        if prop["block"] and prop["lot"]:
            try:
                vrow = query(
                    f"SELECT COUNT(*) FROM violations "
                    f"WHERE block = {_ph()} AND lot = {_ph()} AND LOWER(status) = 'open'",
                    (prop["block"], prop["lot"]),
                )
                prop["open_violations"] = int(vrow[0][0]) if vrow else 0
            except Exception:
                prop["open_violations"] = None
            try:
                crow = query(
                    f"SELECT COUNT(*) FROM complaints "
                    f"WHERE block = {_ph()} AND lot = {_ph()} AND LOWER(status) = 'open'",
                    (prop["block"], prop["lot"]),
                )
                prop["open_complaints"] = int(crow[0][0]) if crow else 0
            except Exception:
                prop["open_complaints"] = None
        else:
            prop["open_violations"] = None
            prop["open_complaints"] = None

    # Get routing progress for permits currently in plan check (filed status)
    # Collect all filed permit numbers across all properties
    all_filed_permits: list[str] = []
    prop_by_permit: dict[str, dict] = {}
    for prop in properties:
        for pm in prop.get("permits", []):
            if pm.get("status") == "filed":
                pn = pm["permit_number"]
                all_filed_permits.append(pn)
                prop_by_permit[pn] = prop

    if all_filed_permits:
        try:
            from web.routing import get_routing_progress_batch
            routing_map = get_routing_progress_batch(all_filed_permits)
        except Exception:
            routing_map = {}

        # Assign the best-progress routing to each property (pick permit with most stations)
        prop_routing: dict[int, object] = {}  # id(prop) -> RoutingProgress
        for pn, progress in routing_map.items():
            prop = prop_by_permit.get(pn)
            if prop is None:
                continue
            pid = id(prop)
            existing = prop_routing.get(pid)
            if existing is None or progress.total_stations > existing.total_stations:
                prop_routing[pid] = progress

        health_order = {"on_track": 0, "slower": 1, "behind": 2, "at_risk": 3}
        for prop in properties:
            rp = prop_routing.get(id(prop))
            if rp:
                pending_names = [s.station for s in rp.stations if not s.is_complete]
                stalled = [
                    s.station for s in rp.stations
                    if not s.is_complete and not s.has_hold
                    and s.arrive_date
                    and (date.today() - _parse_date(s.arrive_date)).days > 30
                ]
                held = [s.station for s in rp.stations if not s.is_complete and s.has_hold]
                pct = int(rp.completed_stations * 100 / rp.total_stations) if rp.total_stations else 0
                prop["routing"] = {
                    "permit_number": rp.permit_number,
                    "completion_pct": pct,
                    "total_stations": rp.total_stations,
                    "completed_stations": rp.completed_stations,
                    "pending_station_names": pending_names,
                    "stalled_stations": stalled,
                    "held_stations": held,
                }
                # Upgrade to AT RISK if permit has active holds
                if held and health_order.get(prop["worst_health"], 0) < health_order["at_risk"]:
                    prop["worst_health"] = "at_risk"
                    prop["health_reason"] = f"Hold at {', '.join(held[:2])}"
            else:
                prop["routing"] = None

            # Upgrade to AT RISK if property has open enforcement
            viol = prop.get("open_violations") or 0
            comp = prop.get("open_complaints") or 0
            if (viol + comp) > 0 and health_order.get(prop["worst_health"], 0) < health_order["at_risk"]:
                parts = []
                if viol:
                    parts.append(f"{viol} violation{'s' if viol != 1 else ''}")
                if comp:
                    parts.append(f"{comp} complaint{'s' if comp != 1 else ''}")
                prop["worst_health"] = "at_risk"
                prop["health_reason"] = f"Open enforcement: {', '.join(parts)}"
    else:
        for prop in properties:
            prop["routing"] = None

    # Summary
    total_active = sum(p["active_count"] for p in properties)
    action_needed = sum(1 for p in properties if p["worst_health"] in ("behind", "at_risk"))
    in_review = sum(1 for p in properties if any(pm["status"] == "filed" for pm in p["permits"]))
    total_value = sum(p["total_cost"] for p in properties)

    summary = {
        "total_properties": len(properties),
        "total_active_permits": total_active,
        "action_needed": action_needed,
        "in_review": in_review,
        "total_value": total_value,
    }

    return {"properties": properties, "summary": summary}


def _empty_summary():
    return {
        "total_properties": 0,
        "total_active_permits": 0,
        "action_needed": 0,
        "in_review": 0,
        "total_value": 0,
    }


# ── Inspection Timeline ──────────────────────────────────────────

INSPECTION_SEQUENCE = [
    "SITE VERIFICATION",
    "REINFORCING STEEL",
    "OK TO POUR",
    "ROUGH FRAME",
    "SHEAR WALL",
    "SHEETROCK NAILING",
    "INSULATION",
    "LATH, EXTERIOR",
    "CEILING INSPECTION",
    "PRE-FINAL",
    "FINAL INSPECT/APPRVD",
]

# Aliases for fuzzy matching inspection descriptions
_SEQUENCE_ALIASES = {
    "ROUGH FRAME, PARTIAL": "ROUGH FRAME",
    "FINAL INSPECTION": "FINAL INSPECT/APPRVD",
    "FINAL INSPECT": "FINAL INSPECT/APPRVD",
}


def get_inspection_timeline(block: str, lot: str) -> dict | None:
    """Get inspection progress for a property.

    Returns:
        {
            "completed": [...],
            "current_phase": "SHEETROCK NAILING",
            "suggested_next": "INSULATION",
            "progress_pct": 65,
            "failed_needing_reinspection": [...],
            "total_inspections": 12,
        }
    Or None if no inspections found.
    """
    if not block or not lot:
        return None

    rows = query(
        f"SELECT scheduled_date, result, inspection_description, inspector "
        f"FROM inspections WHERE block = {_ph()} AND lot = {_ph()} "
        f"ORDER BY scheduled_date ASC",
        (block, lot),
    )

    if not rows:
        return None

    # Map inspections to sequence positions
    completed_types: dict[str, dict] = {}  # type -> latest passed info
    failed_types: set[str] = set()
    all_inspections = []

    for row in rows:
        sched_date, result, desc, inspector = (
            row[0],
            row[1],
            (row[2] or "").upper().strip(),
            row[3],
        )

        # Normalize to sequence type
        seq_type = _SEQUENCE_ALIASES.get(desc, desc)

        insp_info = {
            "type": desc,
            "normalized_type": seq_type,
            "date": str(_parse_date(sched_date)) if sched_date else "",
            "result": result or "",
            "inspector": inspector or "",
        }
        all_inspections.append(insp_info)

        if result == "PASSED" and seq_type in INSPECTION_SEQUENCE:
            completed_types[seq_type] = insp_info
        elif result == "FAILED" and seq_type in INSPECTION_SEQUENCE:
            failed_types.add(seq_type)

    # Remove from failed if subsequently passed
    failed_needing_reinspection = []
    for ft in failed_types:
        if ft not in completed_types:
            # Find the latest failed inspection for this type
            for insp in reversed(all_inspections):
                if insp["normalized_type"] == ft and insp["result"] == "FAILED":
                    failed_needing_reinspection.append(insp)
                    break

    # Find current phase (highest completed position)
    current_idx = -1
    current_phase = None
    for i, step in enumerate(INSPECTION_SEQUENCE):
        if step in completed_types:
            current_idx = i
            current_phase = step

    # Suggested next
    suggested_next = None
    if current_idx < len(INSPECTION_SEQUENCE) - 1:
        suggested_next = INSPECTION_SEQUENCE[current_idx + 1]

    # Progress percentage
    progress_pct = 0
    if current_idx >= 0:
        progress_pct = int((current_idx + 1) / len(INSPECTION_SEQUENCE) * 100)

    # Build completed list in sequence order
    completed_list = []
    for step in INSPECTION_SEQUENCE:
        if step in completed_types:
            completed_list.append(completed_types[step])

    return {
        "completed": completed_list,
        "current_phase": current_phase,
        "suggested_next": suggested_next,
        "progress_pct": progress_pct,
        "failed_needing_reinspection": failed_needing_reinspection,
        "total_inspections": len(all_inspections),
        "sequence": INSPECTION_SEQUENCE,
        "completed_types": set(completed_types.keys()),
    }


# ── Portfolio Discovery (Bulk Onboarding) ───────────────────────


def discover_portfolio(name: str, firm: str | None = None) -> dict:
    """Search entities + contacts to discover permits for a consultant.

    Handles entity fragmentation (like Amy Lee's 210 fragments) by searching
    across all matching entity_ids and aggregating by address.

    Returns:
        {
            "entity_count": 210,
            "total_permits": 199,
            "addresses": [
                {
                    "street_number": "505",
                    "street_name": "Mission Rock",
                    "block": "8711",
                    "lot": "029B",
                    "permit_count": 2,
                    "active_count": 2,
                    "total_cost": 117550000,
                    "owner_firms": ["Google"],
                    "latest_activity": "2026-02-06",
                },
            ],
        }
    """
    ph = _ph()

    # Search entities by name and firm
    conditions = []
    params = []

    if name:
        name_lower = name.strip().lower()
        conditions.append(f"lower(canonical_name) LIKE {ph}")
        params.append(f"%{name_lower}%")

    if firm:
        firm_lower = firm.strip().lower()
        conditions.append(f"lower(canonical_firm) LIKE {ph}")
        params.append(f"%{firm_lower}%")

    if not conditions:
        return {"entity_count": 0, "total_permits": 0, "addresses": []}

    where = " OR ".join(conditions)

    # Find all matching entity IDs
    entity_rows = query(
        f"SELECT entity_id FROM entities WHERE {where}",
        params,
    )

    if not entity_rows:
        return {"entity_count": 0, "total_permits": 0, "addresses": []}

    entity_ids = [r[0] for r in entity_rows]
    entity_count = len(entity_ids)

    # Get all permits via contacts (batch in chunks to avoid huge IN clauses)
    all_permits = []
    chunk_size = 500
    for i in range(0, len(entity_ids), chunk_size):
        chunk = entity_ids[i : i + chunk_size]
        placeholders = ",".join([ph] * len(chunk))
        rows = query(
            f"SELECT DISTINCT p.permit_number, p.status, p.status_date, "
            f"p.filed_date, p.issued_date, p.estimated_cost, p.revised_cost, "
            f"p.street_number, p.street_name, p.block, p.lot "
            f"FROM permits p "
            f"JOIN contacts c ON c.permit_number = p.permit_number "
            f"WHERE c.entity_id IN ({placeholders})",
            chunk,
        )
        all_permits.extend(rows)

    # Deduplicate by permit_number
    seen_permits: set[str] = set()
    unique_permits = []
    for row in all_permits:
        if row[0] not in seen_permits:
            seen_permits.add(row[0])
            unique_permits.append(row)

    # Group by address (block/lot)
    address_map: dict[str, dict] = {}
    for row in unique_permits:
        pn, status, status_date, filed, issued, est_cost, rev_cost = row[0:7]
        snum, sname, block, lot = row[7:11]

        addr = f"{snum or ''} {sname or ''}".strip()
        key = f"{block}/{lot}" if block and lot else addr

        if key not in address_map:
            address_map[key] = {
                "street_number": snum or "",
                "street_name": sname or "",
                "block": block or "",
                "lot": lot or "",
                "permit_count": 0,
                "active_count": 0,
                "total_cost": 0,
                "latest_activity": "",
                "permit_numbers": [],
            }

        entry = address_map[key]
        entry["permit_count"] += 1
        entry["permit_numbers"].append(pn)
        cost = rev_cost or est_cost or 0
        entry["total_cost"] += cost

        if status in ("filed", "issued", "triage"):
            entry["active_count"] += 1

        sd = str(_parse_date(status_date))[:10] if status_date else ""
        if sd > entry["latest_activity"]:
            entry["latest_activity"] = sd

    # Find owner firms for each address (for auto-tagging)
    for key, entry in address_map.items():
        if entry["block"] and entry["lot"]:
            owner_rows = query(
                f"SELECT DISTINCT e.canonical_name, e.canonical_firm "
                f"FROM entities e "
                f"JOIN contacts c ON c.entity_id = e.entity_id "
                f"JOIN permits p ON p.permit_number = c.permit_number "
                f"WHERE p.block = {ph} AND p.lot = {ph} "
                f"AND e.entity_type IN ('owner', 'owner of record', 'property owner') "
                f"LIMIT 5",
                (entry["block"], entry["lot"]),
            )
            firms: set[str] = set()
            for r in owner_rows:
                if r[1] and r[1].strip():
                    firms.add(r[1].strip())
                elif r[0] and r[0].strip():
                    firms.add(r[0].strip())
            entry["owner_firms"] = sorted(firms)
        else:
            entry["owner_firms"] = []

    addresses = sorted(
        address_map.values(),
        key=lambda a: a["latest_activity"],
        reverse=True,
    )

    return {
        "entity_count": entity_count,
        "total_permits": len(unique_permits),
        "addresses": addresses,
    }


def bulk_add_watches(user_id: int, addresses: list[dict]) -> int:
    """Bulk-create watch items for multiple addresses.

    Args:
        addresses: list of {"street_number", "street_name", "block", "lot"}

    Returns: number of watches created (skips duplicates via add_watch idempotency)
    """
    from web.auth import add_watch

    created = 0
    for addr in addresses:
        snum = addr.get("street_number", "").strip()
        sname = addr.get("street_name", "").strip()
        block = addr.get("block", "").strip()
        lot = addr.get("lot", "").strip()
        label = f"{snum} {sname}".strip()

        if block and lot:
            result = add_watch(user_id, "parcel", block=block, lot=lot, label=label)
        elif snum and sname:
            result = add_watch(
                user_id, "address", street_number=snum, street_name=sname, label=label
            )
        else:
            continue

        if result:
            created += 1

    return created
