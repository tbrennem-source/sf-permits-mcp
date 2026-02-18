"""Tool: permit_lookup — Look up permits by number, address, or parcel and show related permits."""

import logging

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL helpers
# ---------------------------------------------------------------------------

# Placeholder style: %s for Postgres, ? for DuckDB
_PH = "%s" if BACKEND == "postgres" else "?"


def _exec(conn, sql, params=None):
    """Execute SQL and return all rows. Handles Postgres/DuckDB cursor differences."""
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


def _exec_one(conn, sql, params=None):
    """Execute SQL and return first row, or None."""
    rows = _exec(conn, sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Column mappings (permits table column order for SELECT *)
# ---------------------------------------------------------------------------

PERMIT_COLS = [
    "permit_number", "permit_type", "permit_type_definition", "status",
    "status_date", "description", "filed_date", "issued_date", "approved_date",
    "completed_date", "estimated_cost", "revised_cost", "existing_use",
    "proposed_use", "existing_units", "proposed_units", "street_number",
    "street_name", "street_suffix", "zipcode", "neighborhood",
    "supervisor_district", "block", "lot", "adu", "data_as_of",
]


def _row_to_dict(row, cols=PERMIT_COLS) -> dict:
    """Convert a tuple row to a dict using column name list."""
    return {cols[i]: row[i] for i in range(min(len(cols), len(row)))}


# ---------------------------------------------------------------------------
# Lookup functions
# ---------------------------------------------------------------------------

def _lookup_by_number(conn, permit_number: str) -> list[dict]:
    """Exact match on permit_number (PK)."""
    sql = f"SELECT * FROM permits WHERE permit_number = {_PH}"
    rows = _exec(conn, sql, [permit_number])
    return [_row_to_dict(r) for r in rows]


def _strip_suffix(name: str) -> tuple[str, str | None]:
    """Split a street name into (base_name, suffix) if a known suffix is present.

    Examples:
        "16th Ave" → ("16th", "Ave")
        "Robin Hood Dr" → ("Robin Hood", "Dr")
        "Market" → ("Market", None)
    """
    import re
    m = re.match(
        r'^(.+?)\s+(St(?:reet)?|Ave(?:nue)?|Blvd|Boulevard|Rd|Road|Dr(?:ive)?'
        r'|Way|Ct|Court|Ln|Lane|Pl(?:ace)?|Ter(?:race)?)\.?\s*$',
        name,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return name, None


def _lookup_by_address(conn, street_number: str, street_name: str) -> list[dict]:
    """Match on street_number + street_name (indexed).

    Handles three DB storage patterns:
      1. street_name="MARKET", street_suffix="ST"  (suffix in separate column)
      2. street_name="MARKET ST", street_suffix=NULL  (suffix merged into name)
      3. street_name="16TH", street_suffix="AVE"  (numbered streets)

    The user may provide "Market St" or just "Market" — we search for the
    base name AND the full name+suffix against both column layouts.

    Also handles space-variant matches:
      "robin hood" matches "ROBINHOOD" and vice versa by comparing
      space-stripped versions of both the input and the stored name.
    """
    base_name, suffix = _strip_suffix(street_name)

    # Build patterns for all match scenarios
    base_pattern = f"%{base_name}%"
    full_pattern = f"%{street_name}%"
    # Space-stripped pattern for fuzzy space matching (e.g. "robin hood" → "robinhood")
    nospace_pattern = f"%{base_name.replace(' ', '')}%"

    sql = f"""
        SELECT * FROM permits
        WHERE street_number = {_PH}
          AND (
            UPPER(street_name) LIKE UPPER({_PH})
            OR UPPER(street_name) LIKE UPPER({_PH})
            OR UPPER(COALESCE(street_name, '') || ' ' || COALESCE(street_suffix, '')) LIKE UPPER({_PH})
            OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') LIKE UPPER({_PH})
          )
        ORDER BY filed_date DESC
        LIMIT 50
    """
    rows = _exec(conn, sql, [street_number, base_pattern, full_pattern, full_pattern, nospace_pattern])
    return [_row_to_dict(r) for r in rows]


def _lookup_by_block_lot(conn, block: str, lot: str) -> list[dict]:
    """Match on block + lot (indexed composite)."""
    sql = f"""
        SELECT * FROM permits
        WHERE block = {_PH} AND lot = {_PH}
        ORDER BY filed_date DESC
        LIMIT 50
    """
    rows = _exec(conn, sql, [block, lot])
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Enrichment functions
# ---------------------------------------------------------------------------

def _get_contacts(conn, permit_number: str) -> list[dict]:
    """Get contacts + entity enrichment for a permit."""
    sql = f"""
        SELECT c.role, c.name, c.firm_name, c.entity_id,
               e.canonical_name, e.canonical_firm, e.permit_count
        FROM contacts c
        LEFT JOIN entities e ON c.entity_id = e.entity_id
        WHERE c.permit_number = {_PH}
        ORDER BY
            CASE LOWER(COALESCE(c.role, ''))
                WHEN 'applicant' THEN 1
                WHEN 'contractor' THEN 2
                WHEN 'architect' THEN 3
                WHEN 'engineer' THEN 4
                ELSE 5
            END
    """
    rows = _exec(conn, sql, [permit_number])
    cols = ["role", "name", "firm_name", "entity_id",
            "canonical_name", "canonical_firm", "permit_count"]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


def _get_inspections(conn, permit_number: str) -> list[dict]:
    """Get inspections for a permit, ordered by date."""
    sql = f"""
        SELECT scheduled_date, inspector, result, inspection_description
        FROM inspections
        WHERE reference_number = {_PH}
        ORDER BY scheduled_date DESC
    """
    rows = _exec(conn, sql, [permit_number])
    cols = ["scheduled_date", "inspector", "result", "description"]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


def _get_timeline(conn, permit_number: str) -> dict | None:
    """Get pre-computed timeline stats if available."""
    sql = f"""
        SELECT days_to_issuance, days_to_completion
        FROM timeline_stats
        WHERE permit_number = {_PH}
        LIMIT 1
    """
    row = _exec_one(conn, sql, [permit_number])
    if row:
        return {"days_to_issuance": row[0], "days_to_completion": row[1]}
    return None


def _get_related_location(conn, block: str, lot: str, exclude: str) -> list[dict]:
    """Get other permits at the same parcel."""
    sql = f"""
        SELECT permit_number, permit_type_definition, status,
               filed_date, estimated_cost, description
        FROM permits
        WHERE block = {_PH} AND lot = {_PH}
          AND permit_number != {_PH}
        ORDER BY filed_date DESC
        LIMIT 25
    """
    rows = _exec(conn, sql, [block, lot, exclude])
    cols = ["permit_number", "type", "status", "filed_date", "cost", "description"]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


def _get_related_team(conn, permit_number: str) -> list[dict]:
    """Get permits sharing team members (via entity_id joins)."""
    sql = f"""
        SELECT DISTINCT ON (p.permit_number)
               p.permit_number, p.permit_type_definition, p.status,
               p.filed_date, p.estimated_cost, p.description,
               e.canonical_name, c2.role
        FROM contacts c1
        JOIN contacts c2 ON c1.entity_id = c2.entity_id
                         AND c2.permit_number != {_PH}
        JOIN permits p ON c2.permit_number = p.permit_number
        JOIN entities e ON c1.entity_id = e.entity_id
        WHERE c1.permit_number = {_PH}
          AND c1.entity_id IS NOT NULL
        ORDER BY p.permit_number, p.filed_date DESC
        LIMIT 25
    """
    # DuckDB doesn't support DISTINCT ON — use a different approach
    if BACKEND == "duckdb":
        sql = f"""
            SELECT p.permit_number, p.permit_type_definition, p.status,
                   p.filed_date, p.estimated_cost, p.description,
                   e.canonical_name, c2.role
            FROM contacts c1
            JOIN contacts c2 ON c1.entity_id = c2.entity_id
                             AND c2.permit_number != {_PH}
            JOIN permits p ON c2.permit_number = p.permit_number
            JOIN entities e ON c1.entity_id = e.entity_id
            WHERE c1.permit_number = {_PH}
              AND c1.entity_id IS NOT NULL
            GROUP BY p.permit_number, p.permit_type_definition, p.status,
                     p.filed_date, p.estimated_cost, p.description,
                     e.canonical_name, c2.role
            ORDER BY p.filed_date DESC
            LIMIT 25
        """
    rows = _exec(conn, sql, [permit_number, permit_number])
    cols = ["permit_number", "type", "status", "filed_date", "cost",
            "description", "shared_entity", "shared_role"]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


def _get_addenda(conn, permit_number: str) -> list[dict]:
    """Get addenda routing steps for a permit, ordered by addenda then step."""
    sql = f"""
        SELECT addenda_number, step, station, plan_checked_by,
               review_results, finish_date, hold_description, department,
               arrive, start_date
        FROM addenda
        WHERE application_number = {_PH}
        ORDER BY addenda_number, step
    """
    rows = _exec(conn, sql, [permit_number])
    cols = ["addenda_number", "step", "station", "reviewer",
            "result", "finish_date", "notes", "department",
            "arrive", "start_date"]
    return [{cols[i]: r[i] for i in range(len(cols))} for r in rows]


# ---------------------------------------------------------------------------
# Markdown formatters
# ---------------------------------------------------------------------------

def _format_addenda(addenda: list[dict]) -> str:
    """Format addenda routing as markdown table."""
    if not addenda:
        return "*No plan review routing data available for this permit.*"

    # Summary stats
    total_steps = len(addenda)
    completed = sum(1 for a in addenda if a.get("result"))
    pending = total_steps - completed
    stations = set(a.get("station") for a in addenda if a.get("station"))

    lines = [
        f"**{total_steps} routing steps** across **{len(stations)} stations** "
        f"({completed} completed, {pending} pending)\n",
        "| Station | Rev | Reviewer | Result | Finish Date | Notes |",
        "|---------|-----|----------|--------|-------------|-------|",
    ]
    for a in addenda[:50]:  # Cap at 50 rows
        station = a.get("station") or "---"
        rev = a.get("addenda_number")
        rev_str = str(rev) if rev is not None else "---"
        reviewer = a.get("reviewer") or "---"
        result = a.get("result") or "---"
        finish = a.get("finish_date") or "---"
        if finish and len(finish) > 10:
            finish = finish[:10]
        notes = a.get("notes") or "---"
        if len(notes) > 80:
            notes = notes[:80] + "..."
        lines.append(f"| {station} | {rev_str} | {reviewer} | {result} | {finish} | {notes} |")

    if len(addenda) > 50:
        lines.append(f"\n*Showing 50 of {len(addenda)} routing steps.*")

    return "\n".join(lines)


def _format_permit_detail(p: dict) -> str:
    """Format a single permit as markdown."""
    lines = []
    pn = p['permit_number']
    pn_url = f"https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber={pn}"
    from src.report_links import ReportLinks
    details_url = ReportLinks.dbi_permit_details(pn)
    lines.append(f"**Permit Number:** [{pn}]({pn_url}) | [DBI Permit Details]({details_url})")
    lines.append(f"**Type:** {p.get('permit_type_definition') or p.get('permit_type') or 'Unknown'}")
    lines.append(f"**Status:** {p.get('status') or 'Unknown'}")
    if p.get("status_date"):
        lines[-1] += f" (as of {p['status_date']})"
    if p.get("description"):
        desc = p["description"][:200]
        if len(p["description"]) > 200:
            desc += "..."
        lines.append(f"**Description:** {desc}")

    # Dates
    dates = []
    if p.get("filed_date"):
        dates.append(f"Filed: {p['filed_date']}")
    if p.get("issued_date"):
        dates.append(f"Issued: {p['issued_date']}")
    if p.get("approved_date"):
        dates.append(f"Approved: {p['approved_date']}")
    if p.get("completed_date"):
        dates.append(f"Completed: {p['completed_date']}")
    if dates:
        lines.append(f"**Dates:** {' | '.join(dates)}")

    # Cost
    cost_parts = []
    if p.get("estimated_cost"):
        cost_parts.append(f"${p['estimated_cost']:,.0f} estimated")
    if p.get("revised_cost") and p["revised_cost"] != p.get("estimated_cost"):
        cost_parts.append(f"${p['revised_cost']:,.0f} revised")
    if cost_parts:
        lines.append(f"**Cost:** {' / '.join(cost_parts)}")

    # Address
    addr_parts = [p.get("street_number", ""), p.get("street_name", ""),
                  p.get("street_suffix", "")]
    addr = " ".join(a for a in addr_parts if a).strip()
    if addr:
        lines.append(f"**Address:** {addr}, San Francisco CA {p.get('zipcode', '')}")
    if p.get("neighborhood"):
        lines.append(f"**Neighborhood:** {p['neighborhood']}")
    if p.get("block") and p.get("lot"):
        lines.append(f"**Parcel:** Block {p['block']}, Lot {p['lot']}")

    # Use
    if p.get("existing_use") or p.get("proposed_use"):
        use = f"{p.get('existing_use', '—')} → {p.get('proposed_use', '—')}"
        lines.append(f"**Use:** {use}")

    return "\n".join(lines)


def _format_contacts(contacts: list[dict]) -> str:
    """Format contacts/team as markdown."""
    if not contacts:
        return "*No team contacts on file for this permit.*"
    lines = []
    for c in contacts:
        role = (c.get("role") or "Unknown").title()
        name = c.get("canonical_name") or c.get("name") or "Unknown"
        firm = c.get("canonical_firm") or c.get("firm_name") or ""
        permit_count = c.get("permit_count")

        line = f"- **{role}:** {name}"
        if firm:
            line += f" ({firm})"
        if permit_count and permit_count > 1:
            line += f" — {permit_count:,} SF permits on file"
        lines.append(line)
    return "\n".join(lines)


def _format_inspections(inspections: list[dict]) -> str:
    """Format inspections as markdown table."""
    if not inspections:
        return "*No inspections recorded for this permit.*"
    lines = [
        "| Date | Inspector | Result | Description |",
        "|------|-----------|--------|-------------|",
    ]
    for insp in inspections[:30]:  # Cap at 30 rows
        date = insp.get("scheduled_date") or "—"
        inspector = insp.get("inspector") or "—"
        result = insp.get("result") or "—"
        desc = insp.get("description") or "—"
        if len(desc) > 60:
            desc = desc[:60] + "..."
        lines.append(f"| {date} | {inspector} | {result} | {desc} |")
    if len(inspections) > 30:
        lines.append(f"\n*Showing 30 of {len(inspections)} inspections.*")
    return "\n".join(lines)


def _format_related(location_permits: list[dict], team_permits: list[dict],
                    block: str | None, lot: str | None) -> str:
    """Format related permits section."""
    lines = []

    # Same location
    if block and lot:
        lines.append(f"### Same Location (Block {block}, Lot {lot})")
        if location_permits:
            lines.append(f"Found **{len(location_permits)}** other permits at this parcel:\n")
            lines.append("| Permit # | Type | Status | Filed | Cost |")
            lines.append("|----------|------|--------|-------|------|")
            for p in location_permits[:20]:
                pnum = p.get("permit_number", "")
                ptype = (p.get("type") or "")[:40]
                status = p.get("status") or "—"
                filed = p.get("filed_date") or "—"
                cost = f"${p['cost']:,.0f}" if p.get("cost") else "—"
                lines.append(f"| {pnum} | {ptype} | {status} | {filed} | {cost} |")
            if len(location_permits) > 20:
                lines.append(f"\n*Showing 20 of {len(location_permits)}.*")
        else:
            lines.append("*No other permits found at this parcel.*")

    # Same team
    lines.append("\n### Same Team Members")
    if team_permits:
        lines.append(f"Found **{len(team_permits)}** permits sharing team members:\n")
        lines.append("| Permit # | Type | Status | Filed | Shared Via |")
        lines.append("|----------|------|--------|-------|------------|")
        for p in team_permits[:20]:
            pnum = p.get("permit_number", "")
            ptype = (p.get("type") or "")[:35]
            status = p.get("status") or "—"
            filed = p.get("filed_date") or "—"
            shared = f"{p.get('shared_entity', '')} ({p.get('shared_role', '')})"
            lines.append(f"| {pnum} | {ptype} | {status} | {filed} | {shared} |")
        if len(team_permits) > 20:
            lines.append(f"\n*Showing 20 of {len(team_permits)}.*")
    else:
        lines.append("*No related permits found via shared team members.*")

    return "\n".join(lines)


def _format_permit_list(permits: list[dict], search_desc: str) -> str:
    """Format a list of permits for address/block-lot results."""
    lines = [
        f"# Permit Lookup Results\n",
        f"Found **{len(permits)}** permits matching {search_desc}.\n",
        "| Permit # | Type | Status | Filed | Cost | Description |",
        "|----------|------|--------|-------|------|-------------|",
    ]
    for p in permits:
        pnum = p.get("permit_number", "")
        ptype = (p.get("permit_type_definition") or "")[:30]
        status = p.get("status") or "—"
        filed = p.get("filed_date") or "—"
        cost = f"${p['estimated_cost']:,.0f}" if p.get("estimated_cost") else "—"
        desc = (p.get("description") or "")[:50]
        if len(p.get("description", "")) > 50:
            desc += "..."
        lines.append(f"| {pnum} | {ptype} | {status} | {filed} | {cost} | {desc} |")

    lines.append(f"\n*Source: sfpermits.ai local database ({BACKEND})*")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main tool entry point
# ---------------------------------------------------------------------------

async def permit_lookup(
    permit_number: str | None = None,
    street_number: str | None = None,
    street_name: str | None = None,
    block: str | None = None,
    lot: str | None = None,
) -> str:
    """Look up SF permits by number, address, or parcel. Shows full details and related permits.

    Searches the local database of 1.1M+ SF building permits. Provide ONE of:
    - permit_number: exact permit number (e.g., '202301015555')
    - street_number + street_name: address search (e.g., '123' + 'Main')
    - block + lot: SF parcel identifier (e.g., '3512' + '001')

    Returns permit details, project team, inspections, and related permits.
    """
    # Validate input — at least one search mode
    has_permit = bool(permit_number and permit_number.strip())
    has_address = bool(street_number and street_number.strip() and street_name and street_name.strip())
    has_parcel = bool(block and block.strip() and lot and lot.strip())

    if not has_permit and not has_address and not has_parcel:
        return "Please provide a permit number, address (street number + street name), or parcel (block + lot)."

    conn = get_connection()
    try:
        # 1. Find the permit(s)
        if has_permit:
            permits = _lookup_by_number(conn, permit_number.strip())
            if not permits:
                return f"No permit found with number **{permit_number.strip()}**."
        elif has_address:
            permits = _lookup_by_address(conn, street_number.strip(), street_name.strip())
            if not permits:
                return f"No permits found at **{street_number.strip()} {street_name.strip()}**."
        else:
            permits = _lookup_by_block_lot(conn, block.strip(), lot.strip())
            if not permits:
                return f"No permits found at **Block {block.strip()}, Lot {lot.strip()}**."

        # 2. If multiple permits (address/parcel search), show list + detail for first
        primary = permits[0]
        pnum = primary["permit_number"]

        lines = ["# Permit Lookup Results\n"]

        # If address/parcel returned multiple, show the list first
        if len(permits) > 1:
            search_desc = ""
            if has_address:
                search_desc = f"{street_number.strip()} {street_name.strip()}"
            elif has_parcel:
                search_desc = f"Block {block.strip()}, Lot {lot.strip()}"
            lines.append(f"Found **{len(permits)}** permits at **{search_desc}**.\n")
            lines.append("| Permit # | Type | Status | Filed | Cost |")
            lines.append("|----------|------|--------|-------|------|")
            for p in permits[:20]:
                pn = p.get("permit_number", "")
                # Hyperlink permit number to DBI tracker
                pn_link = f"[{pn}](https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber={pn})" if pn else "—"
                pt = (p.get("permit_type_definition") or "")[:35]
                st = p.get("status") or "—"
                fd = p.get("filed_date") or "—"
                c = f"${p['estimated_cost']:,.0f}" if p.get("estimated_cost") else "—"
                lines.append(f"| {pn_link} | {pt} | {st} | {fd} | {c} |")
            if len(permits) > 20:
                lines.append(f"\n*Showing 20 of {len(permits)}.*")
            lines.append(f"\n---\n\n**Showing details for most recent: {pnum}**\n")

        # 3. Detailed view of primary permit
        lines.append("## Permit Details\n")
        lines.append(_format_permit_detail(primary))

        # Timeline stats
        try:
            timeline = _get_timeline(conn, pnum)
            if timeline:
                if timeline.get("days_to_issuance"):
                    lines.append(f"\n**Filing → Issuance:** {timeline['days_to_issuance']} days")
                if timeline.get("days_to_completion"):
                    lines.append(f"**Issuance → Completion:** {timeline['days_to_completion']} days")
        except Exception:
            pass  # timeline_stats table might not exist in all envs

        # 4. Team
        lines.append("\n## Project Team\n")
        contacts = _get_contacts(conn, pnum)
        lines.append(_format_contacts(contacts))

        # 5. Inspections
        lines.append("\n## Inspection History\n")
        inspections = _get_inspections(conn, pnum)
        lines.append(_format_inspections(inspections))

        # 5.5 Plan Review Routing (Addenda)
        lines.append("\n## Plan Review Routing\n")
        try:
            addenda_rows = _get_addenda(conn, pnum)
            lines.append(_format_addenda(addenda_rows))
        except Exception:
            lines.append("*Plan review routing data not available.*")

        # 6. Related permits
        lines.append("\n## Related Permits\n")

        # Related by location
        p_block = primary.get("block")
        p_lot = primary.get("lot")
        location_permits = []
        if p_block and p_lot:
            location_permits = _get_related_location(conn, p_block, p_lot, pnum)

        # Related by team
        team_permits = []
        try:
            team_permits = _get_related_team(conn, pnum)
        except Exception as e:
            logger.warning("Related team query failed: %s", e)

        lines.append(_format_related(location_permits, team_permits, p_block, p_lot))

        # Source citation
        lines.append(f"\n---\n*Source: sfpermits.ai local database ({BACKEND}) — 1.1M permits, 1.8M contacts, 671K inspections*")

        return "\n".join(lines)

    finally:
        conn.close()
