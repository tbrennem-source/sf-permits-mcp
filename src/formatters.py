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
