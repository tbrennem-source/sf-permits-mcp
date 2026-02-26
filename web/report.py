"""Property report data assembly — orchestrates fetching from multiple sources.

Builds a structured property report for a given block/lot parcel by:
  1. Querying local DB for permits, contacts, inspections, nearby activity
  2. Querying SODA API in parallel for complaints, violations, property tax data
  3. Computing risk assessment and consultant signal from combined data

Called from synchronous Flask routes; handles async SODA calls internally.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from typing import Any

from src.db import get_connection, BACKEND
from src.soda_client import SODAClient
from src.report_links import ReportLinks
from web.routing import get_routing_progress_batch
from src.tools.permit_lookup import (
    _lookup_by_block_lot,
    _get_contacts,
    _get_inspections,
    _exec,
)

logger = logging.getLogger(__name__)

# Placeholder style: %s for Postgres, ? for DuckDB
_PH = "%s" if BACKEND == "postgres" else "?"

# Zoning codes considered restrictive (single-family residential)
_RESTRICTIVE_ZONES = {"RH-1", "RH-1(D)", "RH-1(S)", "RH-1D", "RH-1S"}


# ---------------------------------------------------------------------------
# SODA fetch helpers (async)
# ---------------------------------------------------------------------------

async def _fetch_complaints(client: SODAClient, block: str, lot: str) -> list[dict]:
    """Fetch DBI complaints for a parcel from SODA API."""
    safe_block = block.replace("'", "''")
    safe_lot = lot.replace("'", "''")
    results = await client.query(
        endpoint_id="gm2e-bten",
        where=f"block='{safe_block}' AND lot='{safe_lot}'",
        order="date_filed DESC",
        limit=50,
    )
    return results or []


async def _fetch_violations(client: SODAClient, block: str, lot: str) -> list[dict]:
    """Fetch DBI violations/NOVs for a parcel from SODA API."""
    safe_block = block.replace("'", "''")
    safe_lot = lot.replace("'", "''")
    results = await client.query(
        endpoint_id="nbtm-fbw5",
        where=f"block='{safe_block}' AND lot='{safe_lot}'",
        order="date_filed DESC",
        limit=50,
    )
    return results or []


async def _fetch_property(client: SODAClient, block: str, lot: str) -> list[dict]:
    """Fetch property tax roll records for a parcel from SODA API."""
    safe_block = block.replace("'", "''")
    safe_lot = lot.replace("'", "''")
    results = await client.query(
        endpoint_id="wv5m-vpq2",
        where=f"block='{safe_block}' AND lot='{safe_lot}'",
        order="closed_roll_year DESC",
        limit=5,
    )
    return results or []


# ---------------------------------------------------------------------------
# Nearby activity
# ---------------------------------------------------------------------------

def _get_nearby_activity(
    conn, block: str, lot: str, neighborhood: str
) -> list[dict]:
    """Query permits in the same neighborhood (excluding this parcel).

    Returns the 10 most recently filed permits nearby.
    """
    if not neighborhood:
        return []

    sql = f"""
        SELECT permit_number, permit_type_definition, status, filed_date,
               estimated_cost, description, street_number, street_name, street_suffix
        FROM permits
        WHERE neighborhood = {_PH} AND NOT (block = {_PH} AND lot = {_PH})
        ORDER BY filed_date DESC
        LIMIT 10
    """
    rows = _exec(conn, sql, [neighborhood, block, lot])
    cols = [
        "permit_number", "permit_type_definition", "status", "filed_date",
        "estimated_cost", "description", "street_number", "street_name",
        "street_suffix",
    ]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


# ---------------------------------------------------------------------------
# Property profile formatting
# ---------------------------------------------------------------------------

def _format_number(value: float | int | None) -> str:
    """Format a number with commas, or return empty string."""
    if value is None:
        return ""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _format_currency(value: float | int | None) -> str:
    """Format a dollar value, or return empty string."""
    if value is None:
        return ""
    try:
        return f"${int(value):,}"
    except (ValueError, TypeError):
        return ""


def _format_property_profile(property_records: list[dict]) -> dict:
    """Extract a clean property profile from SODA tax roll records.

    Uses the first (most recent) record from the wv5m-vpq2 endpoint.
    """
    if not property_records:
        return {}

    rec = property_records[0]

    # Assessed value: sum of land + improvement
    land_val = _safe_float(rec.get("assessed_land_value"))
    improvement_val = _safe_float(rec.get("assessed_improvement_value"))
    total_val = None
    if land_val is not None or improvement_val is not None:
        total_val = (land_val or 0) + (improvement_val or 0)

    # Building / lot area
    building_area = rec.get("property_area")
    lot_area = rec.get("lot_area")

    return {
        "assessed_value": _format_currency(total_val) if total_val else None,
        "assessed_value_raw": total_val,
        "zoning": rec.get("zoning_code") or None,
        "property_class": rec.get("property_class_code_definition") or None,
        "use_code": rec.get("use_definition") or None,
        "neighborhood": rec.get("neighborhood_code_definition") or None,
        "year_built": rec.get("year_property_built") or None,
        "building_area": (
            f"{_format_number(_safe_float(building_area))} sq ft"
            if building_area
            else None
        ),
        "lot_area": (
            f"{_format_number(_safe_float(lot_area))} sq ft"
            if lot_area
            else None
        ),
        "tax_year": rec.get("closed_roll_year") or None,
    }


def _safe_float(val: Any) -> float | None:
    """Convert a value to float, returning None on failure."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Risk assessment
# ---------------------------------------------------------------------------

def _compute_risk_assessment(
    permits: list[dict],
    complaints: list[dict],
    violations: list[dict],
    property_data: list[dict],
) -> list[dict]:
    """Compute risk items from combined report data.

    Returns a list of risk items sorted by severity (high -> moderate -> low).
    """
    risks: list[dict] = []
    severity_order = {"high": 0, "moderate": 1, "low": 2}

    # Active complaints -> high
    for c in complaints:
        status = (c.get("status") or "").upper()
        if "OPEN" in status or "ACTIVE" in status:
            complaint_num = c.get("complaint_number", "")
            desc = c.get("complaint_type") or c.get("description") or "complaint on file"
            link = ReportLinks.complaint(complaint_num) if complaint_num else None
            risks.append({
                "severity": "high",
                "risk_type": "active_complaint",
                "title": f"Active DBI complaint — {desc}",
                "description": (
                    f"An open complaint (#{complaint_num}) is on file for this parcel. "
                    "Active complaints can trigger additional review and delay permit approvals."
                ),
                "section_ref": "complaints",
                "link": link,
            })

    # Active violations/NOVs -> high
    for v in violations:
        status = (v.get("status") or "").upper()
        if "OPEN" in status or "ACTIVE" in status or "NOV" in status:
            violation_id = v.get("nov_number") or v.get("violation_number") or ""
            desc = v.get("violation_type") or v.get("description") or "violation on file"
            risks.append({
                "severity": "high",
                "risk_type": "active_violation",
                "title": f"Active violation/NOV — {desc}",
                "description": (
                    f"An active notice of violation ({violation_id}) is on file. "
                    "Outstanding violations must typically be resolved before new permits are approved."
                ),
                "section_ref": "violations",
                "link": None,
            })

    # Permit cost thresholds
    for p in permits:
        cost = _safe_float(p.get("estimated_cost"))
        if cost and cost > 500_000:
            risks.append({
                "severity": "moderate",
                "risk_type": "high_cost_project",
                "title": f"High-value project — ${cost:,.0f}",
                "description": (
                    f"Permit {p.get('permit_number', '')} has an estimated cost of ${cost:,.0f}. "
                    "Projects over $500K often face additional scrutiny and longer review times."
                ),
                "section_ref": "permits",
                "link": ReportLinks.permit(p["permit_number"]) if p.get("permit_number") else None,
            })
        elif cost and cost > 100_000:
            risks.append({
                "severity": "low",
                "risk_type": "moderate_cost_project",
                "title": f"Moderate-value project — ${cost:,.0f}",
                "description": (
                    f"Permit {p.get('permit_number', '')} has an estimated cost of ${cost:,.0f}."
                ),
                "section_ref": "permits",
                "link": ReportLinks.permit(p["permit_number"]) if p.get("permit_number") else None,
            })

    # Multiple active permits -> complexity note
    active_statuses = {"filed", "approved", "issued", "reinstated"}
    active_permits = [
        p for p in permits
        if (p.get("status") or "").lower() in active_statuses
    ]
    if len(active_permits) > 1:
        risks.append({
            "severity": "low",
            "risk_type": "multiple_active_permits",
            "title": f"Multiple active permits ({len(active_permits)})",
            "description": (
                f"There are {len(active_permits)} active permits on this parcel. "
                "Overlapping permits may require coordination between contractors and inspectors."
            ),
            "section_ref": "permits",
            "link": None,
        })

    # Restrictive zoning — with detailed interpretation
    if property_data:
        zoning = (property_data[0].get("zoning_code") or "").upper().strip()
        if zoning in _RESTRICTIVE_ZONES:
            zoning_detail = _get_zoning_interpretation(zoning)
            risks.append({
                "severity": "low",
                "risk_type": "restrictive_zoning",
                "title": f"Restrictive zoning — {zoning}",
                "description": zoning_detail,
                "section_ref": "property_profile",
                "link": None,
            })

    # Permit expiration / dormancy — based on Table B (SFBC 106A.4.4) valuation tiers
    from datetime import datetime, timedelta
    from web.brief import _validity_days

    now = datetime.now()
    for p in permits:
        status_lower = (p.get("status") or "").lower()
        if status_lower not in ("issued", "filed", "approved", "reinstated"):
            continue
        # Use issued_date for expiration (Table B clock starts at issuance)
        ref_date = p.get("issued_date") or p.get("filed_date")
        if not ref_date:
            continue
        try:
            ref_dt = datetime.fromisoformat(str(ref_date)[:10])
            age_days = (now - ref_dt).days
            completed = p.get("completed_date")
            pnum = p.get("permit_number", "")
            validity = _validity_days(p)

            if age_days > validity and not completed:
                risks.append({
                    "severity": "moderate",
                    "risk_type": "dormant_permit",
                    "title": f"Likely expired permit — {pnum} ({age_days} days, limit {validity})",
                    "description": (
                        f"Permit {pnum} has exceeded its Table B expiration limit of "
                        f"{validity} days (SFBC 106A.4.4). Status: {p.get('status', 'unknown')}. "
                        "Unless an extension was granted, a new application or alteration permit "
                        "may be required to continue work."
                    ),
                    "section_ref": "permits",
                    "link": ReportLinks.permit(pnum) if pnum else None,
                })
            elif age_days > validity - 90 and not completed:
                risks.append({
                    "severity": "low",
                    "risk_type": "aging_permit",
                    "title": f"Permit approaching expiration — {pnum} ({validity - age_days} days left)",
                    "description": (
                        f"Permit {pnum} expires in approximately {validity - age_days} days "
                        f"under Table B ({validity}-day limit). Consider requesting an extension "
                        "before the deadline if work is not yet complete."
                    ),
                    "section_ref": "permits",
                    "link": ReportLinks.permit(pnum) if pnum else None,
                })
        except (ValueError, TypeError):
            continue

    # Conflicting unit counts across permits
    unit_counts = set()
    for p in permits:
        existing = p.get("existing_units")
        proposed = p.get("proposed_units")
        if existing is not None:
            try:
                unit_counts.add(("existing", int(float(existing))))
            except (ValueError, TypeError):
                pass
        if proposed is not None:
            try:
                unit_counts.add(("proposed", int(float(proposed))))
            except (ValueError, TypeError):
                pass
    existing_counts = {c for label, c in unit_counts if label == "existing" and c > 0}
    if len(existing_counts) > 1:
        counts_str = ", ".join(str(c) for c in sorted(existing_counts))
        risks.append({
            "severity": "moderate",
            "risk_type": "unit_count_ambiguity",
            "title": f"Unit count ambiguity — {counts_str} units reported",
            "description": (
                f"Different permits report conflicting existing unit counts ({counts_str}). "
                "This may indicate unauthorized unit conversions, recording errors, or "
                "a property that has been modified without proper permits. "
                "Clarify the correct unit count before filing new permits."
            ),
            "section_ref": "permits",
            "link": None,
        })

    # Contractor turnover — many different contractors on same property
    all_contractors = set()
    for p in permits:
        for contact in p.get("contacts", []):
            role = (contact.get("role") or "").lower()
            name = (contact.get("name") or "").strip()
            if role in ("contractor", "agent") and name:
                all_contractors.add(name.upper())
    if len(all_contractors) >= 5:
        risks.append({
            "severity": "low",
            "risk_type": "high_contractor_turnover",
            "title": f"High contractor turnover ({len(all_contractors)} different contractors)",
            "description": (
                f"This property has {len(all_contractors)} different contractors across its permits. "
                "Frequent contractor changes can indicate project complications, disputes, "
                "or abandoned work. Verify the status of previous work with the current contractor."
            ),
            "section_ref": "permits",
            "link": None,
        })

    # Pending regulation — check if any regulatory watch items affect this property's permits
    try:
        from web.regulatory_watch import get_alerts_for_concepts
        # Infer concepts from permit types on this property
        property_concepts = set()
        for p in permits:
            ptype = (p.get("permit_type_definition") or "").lower()
            # Map common permit types to semantic concepts
            if any(w in ptype for w in ("addition", "alteration", "renovation", "remodel")):
                property_concepts.add("permit_expiration")
            if "demolition" in ptype:
                property_concepts.update(("permit_expiration", "enforcement"))
            if "new construction" in ptype:
                property_concepts.update(("permit_expiration", "permit_requirements"))
            if any(w in ptype for w in ("adu", "accessory dwelling")):
                property_concepts.add("permit_requirements")
        if property_concepts:
            reg_alerts = get_alerts_for_concepts(list(property_concepts))
            for alert in reg_alerts:
                risks.append({
                    "severity": "low" if alert.get("impact_level") != "high" else "moderate",
                    "risk_type": "pending_regulation",
                    "title": f"Pending regulation — {alert['title']}",
                    "description": (
                        f"{alert['source_id']}: {alert.get('description') or alert['title']}. "
                        f"Status: {alert['status']}. "
                        "This pending change may affect permits on this property."
                    ),
                    "section_ref": "permits",
                    "link": alert.get("url"),
                })
    except Exception:
        pass  # Non-fatal: regulatory_watch table may not exist yet

    # Owner Mode: risk items now include risk_type field for remediation
    # roadmap mapping. See web/owner_mode.py for remediation logic.

    # Sort by severity: high first, then moderate, then low
    risks.sort(key=lambda r: severity_order.get(r["severity"], 99))
    return risks


def _get_zoning_interpretation(zoning: str) -> str:
    """Return a detailed zoning interpretation for common SF zoning codes."""
    interpretations = {
        "RH-1": (
            f"This parcel is zoned {zoning} (Residential-House, One Family). "
            "Only one dwelling unit is permitted. Additions, ADUs, and structural changes "
            "may require neighborhood notification under Section 311. Projects expanding "
            "the building envelope may face discretionary review."
        ),
        "RH-1(D)": (
            f"This parcel is zoned {zoning} (Residential-House, One Family — Detached). "
            "The most restrictive residential zone. Only one detached dwelling unit is allowed. "
            "Any modification to the building footprint or height triggers Section 311 notification. "
            "ADU applications are possible but subject to strict design standards."
        ),
        "RH-1(S)": (
            f"This parcel is zoned {zoning} (Residential-House, One Family — Small Lot). "
            "Similar to RH-1 but on smaller lots. Building envelope restrictions are tighter. "
            "Setback and rear yard requirements may limit what can be built."
        ),
        "RH-1D": (
            f"This parcel is zoned {zoning} (Residential-House, One Family — Detached). "
            "Only one detached dwelling unit is allowed. "
            "Section 311 notification applies to envelope changes."
        ),
        "RH-1S": (
            f"This parcel is zoned {zoning} (Residential-House, One Family — Small Lot). "
            "Similar to RH-1 but designed for smaller lot sizes."
        ),
    }
    return interpretations.get(zoning, (
        f"This parcel is zoned {zoning} (single-family residential). "
        "Projects in RH-1 districts may face neighborhood notification requirements "
        "and discretionary review."
    ))


# ---------------------------------------------------------------------------
# Consultant signal
# ---------------------------------------------------------------------------

# Signal threshold messages — shared between base scoring and Owner Mode augmentation
_SIGNAL_MESSAGES = {
    "cold": "No significant risk factors detected. A consultant is unlikely to be necessary.",
    "warm": "Minor complexity factors present. A consultant could be helpful but is not critical.",
    "recommended": "Multiple risk factors suggest professional permit consulting would be beneficial.",
    "strongly_recommended": (
        "A consultant is strongly advised given the combination of active complaints, "
        "violations, high project cost, or zoning restrictions."
    ),
    "essential": (
        "Strong recommendation to engage a land use consultant. Multiple high-risk factors "
        "make professional navigation of the permitting process essential."
    ),
}


def _score_to_signal(score: int) -> str:
    """Map a numeric consultant score to a signal tier.

    Thresholds: 0=cold, 1-2=warm, 3-4=recommended, 5-7=strongly_recommended, 8+=essential.
    """
    if score == 0:
        return "cold"
    elif score <= 2:
        return "warm"
    elif score <= 4:
        return "recommended"
    elif score <= 7:
        return "strongly_recommended"
    else:
        return "essential"


def _signal_to_message(signal: str) -> str:
    """Get the human-readable message for a signal tier."""
    return _SIGNAL_MESSAGES.get(signal, _SIGNAL_MESSAGES["cold"])


def _compute_consultant_signal(
    complaints: list[dict],
    violations: list[dict],
    permits: list[dict],
    property_data: list[dict],
) -> dict:
    """Score the recommendation for hiring a land use consultant.

    Factors and weights:
        Active DBI complaint:             +3
        Prior NOVs on parcel:             +2
        Permit cost > $500K:              +2  (replaces $100K, not cumulative)
        Permit cost > $100K (but <=500K): +1
        Cost revision > 50%:              +2
        Restrictive zoning (RH-1):        +1
        Stalled plan review station:      +2
        Multiple revision cycles (>=3):   +1

    Signal thresholds:
        0       -> cold
        1-2     -> warm
        3-4     -> recommended
        5-7     -> strongly_recommended
        8+      -> essential

    Note: Owner Mode adds additional factors via compute_extended_consultant_factors()
    in web/owner_mode.py, which augments the score after this base computation.
    """
    score = 0
    factors: list[str] = []

    # Active complaints
    active_complaints = [
        c for c in complaints
        if "OPEN" in (c.get("status") or "").upper()
        or "ACTIVE" in (c.get("status") or "").upper()
    ]
    if active_complaints:
        score += 3
        factors.append(f"Active DBI complaint (+3)")

    # Prior NOVs
    has_novs = any(
        ("OPEN" in (v.get("status") or "").upper()
         or "ACTIVE" in (v.get("status") or "").upper()
         or "NOV" in (v.get("status") or "").upper())
        for v in violations
    )
    if has_novs:
        score += 2
        factors.append("Prior NOVs on parcel (+2)")

    # Permit cost — find the max cost across permits
    max_cost = 0.0
    for p in permits:
        cost = _safe_float(p.get("estimated_cost"))
        if cost and cost > max_cost:
            max_cost = cost

    if max_cost > 500_000:
        score += 2
        factors.append(f"Permit cost > $500K (+2)")
    elif max_cost > 100_000:
        score += 1
        factors.append(f"Permit cost > $100K (+1)")

    # Cost revision variance > 50%
    for p in permits:
        est = _safe_float(p.get("estimated_cost"))
        rev = _safe_float(p.get("revised_cost"))
        if est and rev and est > 0:
            variance = abs(rev - est) / est
            if variance > 0.5:
                score += 2
                factors.append(f"Cost revision > 50% (+2)")
                break

    # Restrictive zoning
    if property_data:
        zoning = (property_data[0].get("zoning_code") or "").upper().strip()
        if zoning in _RESTRICTIVE_ZONES:
            score += 1
            factors.append("Restrictive zoning (+1)")

    # Plan review routing factors (Tier 0 operational intelligence)
    score, factors = _add_routing_factors(permits, score, factors)

    signal = _score_to_signal(score)

    return {
        "score": score,
        "signal": signal,
        "factors": factors,
        "message": _signal_to_message(signal),
    }


def _add_routing_factors(
    permits: list[dict], score: int, factors: list[str],
) -> tuple[int, list[str]]:
    """Add plan review routing factors to consultant signal score.

    Checks active permits for stalled stations and multiple revision cycles.
    Returns updated (score, factors) tuple.
    """
    try:
        from web.routing import get_routing_progress
    except ImportError:
        return score, factors

    added_stall = False
    added_revision = False

    for p in permits:
        pnum = p.get("permit_number", "")
        status = (p.get("status") or "").lower()
        if status not in ("filed", "plancheck"):
            continue
        if not pnum:
            continue

        try:
            rp = get_routing_progress(pnum)
            if not rp:
                continue

            # Stalled stations (>14 days pending)
            if not added_stall and rp.stalled_stations:
                score += 2
                factors.append("Stalled plan review station (+2)")
                added_stall = True

            # Multiple revision cycles
            if not added_revision and rp.addenda_number and rp.addenda_number >= 3:
                score += 1
                factors.append(
                    f"Multiple revision cycles — addenda #{rp.addenda_number} (+1)"
                )
                added_revision = True

        except Exception:
            continue

    return score, factors


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def get_property_report(block: str, lot: str, is_owner: bool = False) -> dict:
    """Build a complete property report for a given parcel.

    Synchronous entry point suitable for Flask routes. Handles async SODA
    queries internally via asyncio.

    Args:
        block: SF Assessor block number (e.g., "2991")
        lot: SF Assessor lot number (e.g., "012")
        is_owner: If True, compute Owner Mode sections (remediation roadmap,
            extended consultant factors, KB citations). Default False.

    Returns:
        Dict with keys: block, lot, address, property_profile, permits,
        complaints, violations, risk_assessment, consultant_signal,
        nearby_activity, links, is_owner, whats_missing, remediation_roadmap.
    """
    block = block.strip()
    lot = lot.strip()

    # ── 1. Synchronous DB queries ─────────────────────────────────
    conn = get_connection()
    try:
        permits = _lookup_by_block_lot(conn, block, lot)

        # Enrich each permit with contacts and inspections
        for permit in permits:
            pnum = permit.get("permit_number", "")
            if pnum:
                try:
                    permit["contacts"] = _get_contacts(conn, pnum)
                except Exception:
                    permit["contacts"] = []
                try:
                    permit["inspections"] = _get_inspections(conn, pnum)
                except Exception:
                    permit["inspections"] = []
                permit["link"] = ReportLinks.permit(pnum)

        # Enrich active permits with routing progress
        active_pnums = [
            p["permit_number"] for p in permits
            if p.get("permit_number")
            and (p.get("status") or "").lower() in ("filed", "plancheck", "issued", "reinstated")
        ]
        routing_map = {}
        if active_pnums:
            try:
                routing_map = get_routing_progress_batch(active_pnums)
            except Exception:
                logger.debug("Routing progress batch failed", exc_info=True)

        for permit in permits:
            pnum = permit.get("permit_number", "")
            rp = routing_map.get(pnum)
            if rp:
                permit["routing"] = {
                    "total": rp.total_stations,
                    "completed": rp.completed_stations,
                    "approved": rp.approved_stations,
                    "comments": rp.comments_issued,
                    "pending": rp.pending_stations,
                    "pct": rp.completion_pct,
                    "is_all_clear": rp.is_all_clear,
                    "addenda_number": rp.addenda_number,
                    "pending_stations": rp.pending_station_names,
                    "stalled": [
                        {"station": s.station, "days": s.days_pending}
                        for s in rp.stalled_stations
                    ],
                    "latest": {
                        "station": rp.latest_activity.station if rp.latest_activity else None,
                        "result": rp.latest_activity.result if rp.latest_activity else None,
                        "date": rp.latest_activity.finish_date if rp.latest_activity else None,
                    } if rp.latest_activity else None,
                }
            else:
                permit["routing"] = None

        # Nearby activity
        neighborhood = ""
        if permits:
            neighborhood = permits[0].get("neighborhood") or ""
        nearby = _get_nearby_activity(conn, block, lot, neighborhood)
    finally:
        conn.close()

    # ── 2. Async SODA queries (parallel) ──────────────────────────

    async def _fetch_soda() -> tuple[list[dict], list[dict], list[dict]]:
        client = SODAClient()
        try:
            results = await asyncio.gather(
                _fetch_complaints(client, block, lot),
                _fetch_violations(client, block, lot),
                _fetch_property(client, block, lot),
            )
            return results[0], results[1], results[2]
        finally:
            await client.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Running inside an existing event loop (e.g., Flask with async).
            # Use a thread pool to run a fresh event loop.
            with concurrent.futures.ThreadPoolExecutor() as pool:
                complaints, violations, property_data = pool.submit(
                    asyncio.run, _fetch_soda()
                ).result(timeout=30)
        else:
            complaints, violations, property_data = asyncio.run(_fetch_soda())
    except RuntimeError:
        # No current event loop — create one via asyncio.run
        complaints, violations, property_data = asyncio.run(_fetch_soda())
    except Exception as e:
        logger.warning("SODA fetch failed: %s", e)
        complaints, violations, property_data = [], [], []

    # ── 3. Compute derived sections ───────────────────────────────
    risk_assessment = _compute_risk_assessment(
        permits, complaints, violations, property_data,
    )
    consultant_signal = _compute_consultant_signal(
        complaints, violations, permits, property_data,
    )
    property_profile = _format_property_profile(property_data)

    # ── 3b. Cross-reference analysis (always — uses public data) ──
    from web.owner_mode import (
        compute_whats_missing,
        compute_remediation_roadmap,
        compute_extended_consultant_factors,
        attach_kb_citations,
    )
    whats_missing = compute_whats_missing(permits, complaints, property_data)

    # ── 3c. Owner Mode extensions ─────────────────────────────────
    remediation_roadmap: list[dict] = []
    if is_owner:
        try:
            from src.tools.knowledge_base import get_knowledge_base
            kb = get_knowledge_base()
            templates = getattr(kb, "remediation_roadmap", {})

            # Remediation cards for Moderate+ risks
            moderate_plus = [
                r for r in risk_assessment
                if r.get("severity") in ("high", "moderate")
            ]
            remediation_roadmap = compute_remediation_roadmap(
                moderate_plus, whats_missing, templates,
            )

            # Extended consultant signal factors
            extra_factors = compute_extended_consultant_factors(whats_missing)
            for ef in extra_factors:
                consultant_signal["score"] += ef["points"]
                consultant_signal["factors"].append(
                    f"{ef['label']} (+{ef['points']})"
                )
            # Recompute signal tier after augmentation
            consultant_signal["signal"] = _score_to_signal(consultant_signal["score"])
            consultant_signal["message"] = _signal_to_message(consultant_signal["signal"])

            # Knowledge base citations
            attach_kb_citations(risk_assessment, remediation_roadmap)
        except Exception as e:
            logger.warning("Owner Mode extensions failed: %s", e)

    # ── 4. Build address from first permit ────────────────────────
    address = ""
    if permits:
        p = permits[0]
        parts = [
            p.get("street_number", ""),
            p.get("street_name", ""),
            p.get("street_suffix", ""),
        ]
        address = " ".join(part for part in parts if part)

    # ── 5. Assemble final report ──────────────────────────────────
    return {
        "block": block,
        "lot": lot,
        "address": address,
        "property_profile": property_profile,
        "permits": permits,
        "complaints": complaints,
        "violations": violations,
        "risk_assessment": risk_assessment,
        "consultant_signal": consultant_signal,
        "nearby_activity": nearby,
        "links": {
            "parcel": ReportLinks.parcel(block, lot),
        },
        # Owner Mode fields
        "is_owner": is_owner,
        "whats_missing": whats_missing,
        "remediation_roadmap": remediation_roadmap,
    }
