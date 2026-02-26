"""Tool: property_lookup — Look up SF property information by address or block/lot."""

import logging

from src.soda_client import SODAClient
from src.formatters import format_property

logger = logging.getLogger(__name__)

# Property Tax Rolls — historical assessed values, property characteristics, zoning
# NOTE: i8ew-h6z7 (Property Information Map) is NOT a data API — it's an interactive map.
# Using wv5m-vpq2 (Assessor Historical Secured Property Tax Rolls) instead.
ENDPOINT_ID = "wv5m-vpq2"


def _format_tax_roll_local(row: tuple) -> str:
    """Format a tax_rolls row (local DB) as markdown property summary."""
    (
        zoning_code, use_definition, number_of_stories, number_of_units,
        lot_area, property_area, assessed_land_value, assessed_improvement_value,
        tax_year, neighborhood, property_location, parcel_number,
    ) = row

    lines = ["## Property Information (Local Tax Rolls)\n"]

    if property_location:
        lines.append(f"**Address:** {property_location}")
    if parcel_number:
        lines.append(f"**Parcel Number:** {parcel_number}")
    if neighborhood:
        lines.append(f"**Neighborhood:** {neighborhood}")
    if tax_year:
        lines.append(f"**Tax Year:** {tax_year}")

    lines.append("")
    lines.append("### Zoning & Use")
    if zoning_code:
        lines.append(f"- **Zoning Code:** {zoning_code}")
    if use_definition:
        lines.append(f"- **Use:** {use_definition}")

    lines.append("")
    lines.append("### Physical Characteristics")
    if number_of_stories:
        lines.append(f"- **Stories:** {number_of_stories}")
    if number_of_units:
        lines.append(f"- **Units:** {number_of_units}")
    if lot_area:
        lines.append(f"- **Lot Area:** {int(lot_area):,} sq ft")
    if property_area:
        lines.append(f"- **Building Area:** {int(property_area):,} sq ft")

    lines.append("")
    lines.append("### Assessed Values")
    if assessed_land_value:
        lines.append(f"- **Land:** ${int(assessed_land_value):,}")
    if assessed_improvement_value:
        lines.append(f"- **Improvements:** ${int(assessed_improvement_value):,}")
    if assessed_land_value and assessed_improvement_value:
        total = int(assessed_land_value) + int(assessed_improvement_value)
        lines.append(f"- **Total:** ${total:,}")

    lines.append("\n*Source: sfpermits.ai local tax_rolls table*")
    return "\n".join(lines)


def _format_pim_enrichment(pim_data: dict, block: str, lot: str) -> str:
    """Format PIM ArcGIS data as an additive markdown section.

    Returns empty string if no useful data is present.
    Sprint 61A: additive enrichment — does not modify existing tax_rolls output.
    """
    lines = ["### Planning Data (SF Planning GIS — PIM)\n"]
    lines.append(f"*Block {block} / Lot {lot} — authoritative parcel data from SF Planning.*\n")

    has_data = False
    zoning_code = pim_data.get("ZONING_CODE")
    if zoning_code:
        lines.append(f"- **Zoning Code:** {zoning_code}")
        has_data = True
    zoning_cat = pim_data.get("ZONING_CATEGORY")
    if zoning_cat:
        lines.append(f"- **Zoning Category:** {zoning_cat}")
        has_data = True
    height_dist = pim_data.get("HEIGHT_DIST")
    if height_dist:
        lines.append(f"- **Height District:** {height_dist}")
        has_data = True
    special_use = pim_data.get("SPECIAL_USE_DIST")
    if special_use:
        lines.append(f"- **Special Use District:** {special_use}")
        has_data = True
    historic = pim_data.get("HISTORIC_DISTRICT")
    if historic:
        lines.append(f"- **Historic District:** {historic}")
        has_data = True
    landmark = pim_data.get("LANDMARK")
    if landmark:
        lines.append(f"- **Landmark:** {landmark}")
        has_data = True

    if not has_data:
        return ""

    return "\n".join(lines)


async def property_lookup(
    address: str | None = None,
    block: str | None = None,
    lot: str | None = None,
    tax_year: str | None = None,
) -> str:
    """Look up property information for a San Francisco parcel.

    Args:
        address: Street address to search (e.g., '123 MAIN ST')
        block: Assessor block number (e.g., '3512')
        lot: Assessor lot number (e.g., '001')
        tax_year: Tax roll year (e.g., '2024'). Defaults to most recent.

    Returns:
        Property details including assessed value, zoning, characteristics,
        and neighborhood information.
    """
    # --- Local DB fallback (tax_rolls table) ---
    # Try local DB first for block/lot lookups — faster and avoids SODA API calls.
    if block and lot:
        try:
            from src.db import get_connection, BACKEND
            conn = get_connection()
            try:
                _ph = "%s" if BACKEND == "postgres" else "?"
                base_sql = f"""
                    SELECT zoning_code, use_definition, number_of_stories, number_of_units,
                           lot_area, property_area, assessed_land_value, assessed_improvement_value,
                           tax_year, neighborhood, property_location, parcel_number
                    FROM tax_rolls
                    WHERE block = {_ph} AND lot = {_ph}
                """
                params = [block, lot]
                if tax_year:
                    base_sql += f" AND tax_year = {_ph}"
                    params.append(tax_year)
                base_sql += " ORDER BY tax_year DESC LIMIT 1"

                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(base_sql, params)
                        row = cur.fetchone()
                else:
                    row = conn.execute(base_sql, params).fetchone()

                if row:
                    base_output = _format_tax_roll_local(row)
                    # === Sprint 61A: Enrich with PIM data (additive) ===
                    try:
                        from src.pim_client import query_pim_cached
                        pim_data = await query_pim_cached(block, lot)
                        if pim_data:
                            pim_section = _format_pim_enrichment(pim_data, block, lot)
                            if pim_section:
                                base_output = base_output + "\n\n" + pim_section
                    except Exception as pim_exc:
                        logger.debug("PIM enrichment failed (non-fatal): %s", pim_exc)
                    return base_output
            finally:
                conn.close()
        except Exception:
            logger.debug("Local tax_rolls lookup failed, falling back to SODA", exc_info=True)

    # --- SODA API fallback ---
    if not block and not lot and not address:
        return "Please provide either an address or block/lot numbers."

    conditions = []

    if block and lot:
        conditions.append(f"block='{_escape(block)}' AND lot='{_escape(lot)}'")
    elif address:
        conditions.append(
            f"upper(property_location) LIKE '%{_escape(address.upper())}%'"
        )
    else:
        return "Please provide either an address or block/lot numbers."

    if tax_year:
        conditions.append(f"closed_roll_year='{_escape(tax_year)}'")
    else:
        # Get the most recent year by ordering
        pass

    where = " AND ".join(conditions) if conditions else None

    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=where,
            order="closed_roll_year DESC",
            limit=5,
        )
        if not results:
            search_desc = (
                f"block {block}, lot {lot}" if block and lot else f"address '{address}'"
            )
            return f"No property found matching {search_desc}."
        return format_property(results)
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
