"""Response formatters for MCP tool outputs.

Format raw SODA API responses into structured, readable text
optimized for Claude consumption.
"""


def format_permit_list(permits: list[dict]) -> str:
    """Format a list of permits for display."""
    if not permits:
        return "No permits found matching your criteria."

    lines = [f"Found {len(permits)} permits:\n"]
    for p in permits:
        cost = (
            f"${float(p.get('estimated_cost', 0)):,.0f}"
            if p.get("estimated_cost")
            else "N/A"
        )
        filed = (
            p.get("filed_date", "N/A")[:10] if p.get("filed_date") else "N/A"
        )
        desc = (p.get("description") or "N/A")[:150]
        address_parts = [
            p.get("street_number", ""),
            p.get("street_name", ""),
            p.get("street_suffix", ""),
        ]
        address = " ".join(part for part in address_parts if part).strip()

        lines.append(
            f"- **{p.get('permit_number', 'N/A')}** — "
            f"{p.get('permit_type_definition', 'Unknown type')}\n"
            f"  Status: {p.get('status', 'N/A')} | Cost: {cost}\n"
            f"  Address: {address or 'N/A'}\n"
            f"  Neighborhood: {p.get('neighborhoods_analysis_boundaries', 'N/A')}\n"
            f"  Filed: {filed}\n"
            f"  Description: {desc}\n"
        )
    return "\n".join(lines)


def format_permit_detail(permit: dict) -> str:
    """Format a single permit with all available fields."""
    lines = [f"# Permit {permit.get('permit_number', 'N/A')}\n"]

    # Group fields logically
    key_fields = [
        ("permit_number", "Permit Number"),
        ("permit_type_definition", "Type"),
        ("status", "Status"),
        ("status_date", "Status Date"),
        ("description", "Description"),
    ]
    address_fields = [
        ("street_number", "Street Number"),
        ("street_number_suffix", "Street Number Suffix"),
        ("street_name", "Street Name"),
        ("street_suffix", "Street Suffix"),
        ("unit", "Unit"),
        ("unit_suffix", "Unit Suffix"),
        ("zipcode", "Zip Code"),
        ("neighborhoods_analysis_boundaries", "Neighborhood"),
        ("supervisor_district", "Supervisor District"),
    ]
    date_fields = [
        ("permit_creation_date", "Created"),
        ("filed_date", "Filed"),
        ("approved_date", "Approved"),
        ("issued_date", "Issued"),
        ("completed_date", "Completed"),
        ("first_construction_document_date", "First Construction Doc"),
        ("last_permit_activity_date", "Last Activity"),
    ]
    cost_fields = [
        ("estimated_cost", "Estimated Cost"),
        ("revised_cost", "Revised Cost"),
    ]
    use_fields = [
        ("existing_use", "Existing Use"),
        ("proposed_use", "Proposed Use"),
        ("existing_units", "Existing Units"),
        ("proposed_units", "Proposed Units"),
        ("number_of_existing_stories", "Existing Stories"),
        ("number_of_proposed_stories", "Proposed Stories"),
        ("existing_construction_type_description", "Existing Construction"),
        ("proposed_construction_type_description", "Proposed Construction"),
        ("adu", "ADU"),
    ]

    sections = [
        ("Key Details", key_fields),
        ("Address", address_fields),
        ("Dates", date_fields),
        ("Cost", cost_fields),
        ("Use & Construction", use_fields),
    ]

    for section_name, fields in sections:
        section_lines = []
        for field_key, label in fields:
            value = permit.get(field_key)
            if value is not None and value != "":
                if "cost" in field_key.lower() and value:
                    try:
                        value = f"${float(value):,.0f}"
                    except (ValueError, TypeError):
                        pass
                if "date" in field_key.lower() and isinstance(value, str) and len(value) > 10:
                    value = value[:10]
                section_lines.append(f"**{label}:** {value}")
        if section_lines:
            lines.append(f"\n## {section_name}")
            lines.extend(section_lines)

    # Remaining fields not in the groups above
    grouped_keys = set()
    for _, fields in sections:
        grouped_keys.update(k for k, _ in fields)

    remaining = {
        k: v
        for k, v in sorted(permit.items())
        if k not in grouped_keys and v is not None and v != ""
    }
    if remaining:
        lines.append("\n## Other Fields")
        for key, value in remaining.items():
            lines.append(f"**{key}:** {value}")

    return "\n".join(lines)


def format_stats(stats: list[dict], group_by: str) -> str:
    """Format aggregated statistics."""
    if not stats:
        return "No data found for the specified criteria."

    lines = [f"Permit statistics grouped by {group_by}:\n"]
    for row in stats:
        category = row.get("category", "Unknown")
        total = row.get("total", 0)
        avg_cost = (
            f"${float(row.get('avg_cost', 0)):,.0f}"
            if row.get("avg_cost")
            else "N/A"
        )
        total_cost = (
            f"${float(row.get('total_cost', 0)):,.0f}"
            if row.get("total_cost")
            else "N/A"
        )
        lines.append(
            f"- **{category}**: {total} permits | "
            f"Avg cost: {avg_cost} | Total cost: {total_cost}"
        )
    return "\n".join(lines)


def format_business_list(businesses: list[dict]) -> str:
    """Format business search results."""
    if not businesses:
        return "No businesses found matching your criteria."

    lines = [f"Found {len(businesses)} businesses:\n"]
    for b in businesses:
        name = b.get("dba_name") or b.get("ownership_name") or "Unknown"
        address = b.get("full_business_address", "N/A")
        start = b.get("dba_start_date", "")
        start_display = start[:10] if start else "N/A"
        end = b.get("dba_end_date") or b.get("location_end_date")
        status = "Closed" if end else "Active"

        lines.append(
            f"- **{name}**\n"
            f"  Address: {address}\n"
            f"  Status: {status} | Started: {start_display}\n"
            f"  Zip: {b.get('business_zip', 'N/A')}\n"
        )
    return "\n".join(lines)


def format_complaint_list(complaints: list[dict]) -> str:
    """Format a list of DBI complaints for display."""
    if not complaints:
        return "No complaints found matching your criteria."

    lines = [f"Found {len(complaints)} complaints:\n"]
    for c in complaints:
        date_filed = (
            c.get("date_filed", "N/A")[:10] if c.get("date_filed") else "N/A"
        )
        date_abated = (
            c.get("date_abated", "")[:10] if c.get("date_abated") else ""
        )
        abated_str = f" | Abated: {date_abated}" if date_abated else ""

        address_parts = [
            c.get("street_number", ""),
            c.get("street_name", ""),
            c.get("street_suffix", ""),
        ]
        address = " ".join(part for part in address_parts if part).strip()

        desc = (c.get("complaint_description") or "N/A")[:200]
        nov_type = c.get("nov_type", "")
        nov_str = f" | NOV Type: {nov_type}" if nov_type else ""

        lines.append(
            f"- **{c.get('complaint_number', 'N/A')}** — "
            f"{c.get('status', 'N/A')}\n"
            f"  Address: {address or 'N/A'} "
            f"(Block {c.get('block', '?')}, Lot {c.get('lot', '?')})\n"
            f"  Filed: {date_filed}{abated_str}{nov_str}\n"
            f"  Division: {c.get('receiving_division', 'N/A')} → "
            f"{c.get('assigned_division', 'N/A')}\n"
            f"  Description: {desc}\n"
        )
    return "\n".join(lines)


def format_violation_list(violations: list[dict]) -> str:
    """Format a list of Notices of Violation for display."""
    if not violations:
        return "No violations found matching your criteria."

    lines = [f"Found {len(violations)} violations:\n"]
    for v in violations:
        date_filed = (
            v.get("date_filed", "N/A")[:10] if v.get("date_filed") else "N/A"
        )
        address_parts = [
            v.get("street_number", ""),
            v.get("street_name", ""),
            v.get("street_suffix", ""),
        ]
        address = " ".join(part for part in address_parts if part).strip()

        category = v.get("nov_category_description", "N/A")
        desc = (v.get("nov_item_description") or "N/A")[:200]

        lines.append(
            f"- **{v.get('complaint_number', 'N/A')}** "
            f"(Item {v.get('item_sequence_number', '?')}) — "
            f"{v.get('status', 'N/A')}\n"
            f"  Address: {address or 'N/A'} "
            f"(Block {v.get('block', '?')}, Lot {v.get('lot', '?')})\n"
            f"  Filed: {date_filed} | Category: {category}\n"
            f"  Description: {desc}\n"
        )
    return "\n".join(lines)


def format_inspection_list(inspections: list[dict]) -> str:
    """Format a list of building inspections for display."""
    if not inspections:
        return "No inspections found matching your criteria."

    lines = [f"Found {len(inspections)} inspections:\n"]
    for i in inspections:
        sched = (
            i.get("scheduled_date", "N/A")[:10]
            if i.get("scheduled_date")
            else "N/A"
        )
        ref_num = i.get("reference_number", "N/A")
        ref_type = i.get("reference_number_type", "")
        ref_str = f"{ref_num} ({ref_type})" if ref_type else ref_num

        # Build address from avs_ fields (inspections use avs_street_name)
        address_parts = [
            i.get("avs_street_number") or i.get("street_number", ""),
            i.get("avs_street_name") or i.get("street_name", ""),
            i.get("avs_street_sfx") or i.get("street_suffix", ""),
        ]
        address = " ".join(part for part in address_parts if part).strip()

        status = i.get("status", "N/A")
        inspector_name = i.get("inspector", "N/A")
        desc = (i.get("inspection_type_description") or "N/A")[:150]

        lines.append(
            f"- **{ref_str}** — {sched}\n"
            f"  Address: {address or 'N/A'} "
            f"(Block {i.get('block', '?')}, Lot {i.get('lot', '?')})\n"
            f"  **Result: {status}** | Inspector: {inspector_name}\n"
            f"  Type: {desc}\n"
        )
    return "\n".join(lines)


def format_property(properties: list[dict]) -> str:
    """Format property lookup results."""
    if not properties:
        return "No property found."

    lines = []
    for p in properties:
        address = p.get("property_location") or p.get("address", "Unknown")
        lines.append(f"# Property: {address}\n")

        key_fields = [
            ("parcel_number", "Parcel (Block/Lot)"),
            ("use_definition", "Use"),
            ("property_class_code_definition", "Property Class"),
            ("zoning_code", "Zoning"),
            ("year_property_built", "Year Built"),
            ("number_of_units", "Units"),
            ("number_of_stories", "Stories"),
            ("number_of_bedrooms", "Bedrooms"),
            ("number_of_bathrooms", "Bathrooms"),
            ("number_of_rooms", "Rooms"),
            ("lot_area", "Lot Area (sq ft)"),
            ("property_area", "Property Area (sq ft)"),
            ("assessed_land_value", "Assessed Land Value"),
            ("assessed_improvement_value", "Assessed Improvement Value"),
            ("assessed_fixtures_value", "Assessed Fixtures Value"),
            ("assessor_neighborhood", "Assessor Neighborhood"),
            ("supervisor_district", "Supervisor District"),
            ("analysis_neighborhood", "Analysis Neighborhood"),
            ("closed_roll_year", "Tax Roll Year"),
        ]

        for field_key, label in key_fields:
            value = p.get(field_key)
            if value is not None and value != "":
                if "value" in field_key.lower():
                    try:
                        value = f"${float(value):,.0f}"
                    except (ValueError, TypeError):
                        pass
                lines.append(f"**{label}:** {value}")

        lines.append("---")
    return "\n".join(lines)
