"""Property report data assembly — orchestrates fetching from multiple sources.

Builds a structured property report for a given block/lot parcel by:
  1. Querying local DB for permits, contacts, inspections, nearby activity
  2. Querying SODA API in parallel for complaints, violations, property tax data
  3. Computing risk assessment and expediter signal from combined data

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
            "title": f"Multiple active permits ({len(active_permits)})",
            "description": (
                f"There are {len(active_permits)} active permits on this parcel. "
                "Overlapping permits may require coordination between contractors and inspectors."
            ),
            "section_ref": "permits",
            "link": None,
        })

    # Restrictive zoning
    if property_data:
        zoning = (property_data[0].get("zoning_code") or "").upper().strip()
        if zoning in _RESTRICTIVE_ZONES:
            risks.append({
                "severity": "low",
                "title": f"Restrictive zoning — {zoning}",
                "description": (
                    f"This parcel is zoned {zoning} (single-family residential). "
                    "Projects in RH-1 districts may face neighborhood notification requirements "
                    "and discretionary review."
                ),
                "section_ref": "property_profile",
                "link": None,
            })

    # FUTURE: Owner Mode will add a Section 1.5 "Remediation Roadmap"
    # which generates recommended next-steps from the risk items here.
    # Risk items should include enough structured data for remediation
    # logic to consume (complaint_number, violation_type, etc.).

    # Sort by severity: high first, then moderate, then low
    risks.sort(key=lambda r: severity_order.get(r["severity"], 99))
    return risks


# ---------------------------------------------------------------------------
# Expediter signal
# ---------------------------------------------------------------------------

def _compute_expediter_signal(
    complaints: list[dict],
    violations: list[dict],
    permits: list[dict],
    property_data: list[dict],
) -> dict:
    """Score the recommendation for hiring a permit expediter.

    Factors and weights:
        Active DBI complaint:           +3
        Prior NOVs on parcel:           +2
        Permit cost > $500K:            +2  (replaces the $100K score, not cumulative)
        Permit cost > $100K (but <=500K): +1
        Restrictive zoning (RH-1):      +1

    Signal thresholds:
        0       -> cold
        1-2     -> warm
        3-4     -> recommended
        5-7     -> strongly_recommended
        8+      -> essential
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

    # Restrictive zoning
    if property_data:
        zoning = (property_data[0].get("zoning_code") or "").upper().strip()
        if zoning in _RESTRICTIVE_ZONES:
            score += 1
            factors.append("Restrictive zoning (+1)")

    # FUTURE: Owner Mode will add additional signal factors:
    #   - Active permit with cost revision > 50%  (+2)
    #   - Project requires Planning review (not OTC) (+1)
    #   - Section 311 notification required (+1)
    #   - Historic district or 45+ yr building with exterior work (+1)
    #   - Unit legality question (zoning vs. recorded use mismatch) (+2)

    # Map score to signal
    if score == 0:
        signal = "cold"
    elif score <= 2:
        signal = "warm"
    elif score <= 4:
        signal = "recommended"
    elif score <= 7:
        signal = "strongly_recommended"
    else:
        signal = "essential"

    # Human-readable message
    messages = {
        "cold": "No significant risk factors detected. An expeditor is unlikely to be necessary.",
        "warm": "Minor complexity factors present. An expeditor could be helpful but is not critical.",
        "recommended": "Multiple risk factors suggest professional permit expediting would be beneficial.",
        "strongly_recommended": (
            "An expeditor is strongly advised given the combination of active complaints, "
            "violations, high project cost, or zoning restrictions."
        ),
        "essential": (
            "Strong recommendation to engage a permit expeditor. Multiple high-risk factors "
            "make professional navigation of the permitting process essential."
        ),
    }

    return {
        "score": score,
        "signal": signal,
        "factors": factors,
        "message": messages[signal],
    }


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def get_property_report(block: str, lot: str) -> dict:
    """Build a complete property report for a given parcel.

    Synchronous entry point suitable for Flask routes. Handles async SODA
    queries internally via asyncio.

    Args:
        block: SF Assessor block number (e.g., "2991")
        lot: SF Assessor lot number (e.g., "012")

    Returns:
        Dict with keys: block, lot, address, property_profile, permits,
        complaints, violations, risk_assessment, expediter_signal,
        nearby_activity, links.
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
                permit["contacts"] = _get_contacts(conn, pnum)
                permit["inspections"] = _get_inspections(conn, pnum)
                permit["link"] = ReportLinks.permit(pnum)

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
    expediter_signal = _compute_expediter_signal(
        complaints, violations, permits, property_data,
    )
    property_profile = _format_property_profile(property_data)

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
        "expediter_signal": expediter_signal,
        "nearby_activity": nearby,
        "links": {
            "parcel": ReportLinks.parcel(block, lot),
        },
    }
