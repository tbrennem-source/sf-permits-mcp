"""Tool: network_anomalies — Scan for anomalous patterns in the permit network."""

from src.validate import anomaly_scan


async def network_anomalies(min_permits: int = 10) -> str:
    """Scan for anomalous patterns in the permit network.

    Flags unusual concentrations, relationships, and timing patterns
    that may indicate corruption, fraud, or regulatory capture.

    Args:
        min_permits: Minimum permit count to consider an entity (default 10).
                    Lower values find more results but include more noise.

    Returns:
        Categorized list of anomalous entities and patterns.
    """
    results = anomaly_scan(min_permits=min_permits)

    if not results:
        return "No anomalies detected (or DuckDB database not populated — run ingestion first)."

    anomalies = results.get("anomalies", {})
    lines = ["# Permit Network Anomaly Scan\n"]

    # High volume entities
    high_volume = anomalies.get("high_permit_volume", [])
    if high_volume:
        lines.append(f"## High Volume Entities ({len(high_volume)} flagged)\n")
        lines.append("Entities with permit count > 3x the median for their type:\n")
        for e in high_volume[:15]:
            lines.append(
                f"- **{e.get('canonical_name', 'Unknown')}** "
                f"({e.get('entity_type', '?')}) — "
                f"{e.get('permit_count', 0)} permits "
                f"(threshold: {e.get('threshold', 'N/A')})"
            )
        lines.append("")

    # Inspector concentration
    inspector_conc = anomalies.get("inspector_concentration", [])
    if inspector_conc:
        lines.append(f"## Inspector Concentration ({len(inspector_conc)} flagged)\n")
        lines.append("Contractors with 50%+ of permits inspected by the same inspector:\n")
        for e in inspector_conc[:15]:
            lines.append(
                f"- **{e.get('canonical_name', 'Unknown')}** — "
                f"{e.get('concentration_pct', 0):.0f}% of permits inspected by "
                f"**{e.get('inspector', 'Unknown')}** "
                f"({e.get('permits_by_inspector', 0)}/{e.get('total_inspected', 0)} permits)"
            )
        lines.append("")

    # Geographic concentration
    geo_conc = anomalies.get("geographic_concentration", [])
    if geo_conc:
        lines.append(f"## Geographic Concentration ({len(geo_conc)} flagged)\n")
        lines.append("Entities with 80%+ of permits in the same neighborhood:\n")
        for e in geo_conc[:15]:
            lines.append(
                f"- **{e.get('canonical_name', 'Unknown')}** — "
                f"{e.get('concentration_pct', 0):.0f}% in {e.get('neighborhood', 'Unknown')} "
                f"({e.get('permits_in_neighborhood', 0)}/{e.get('total_permits', 0)} permits)"
            )
        lines.append("")

    # Fast approvals
    fast = anomalies.get("fast_approvals", [])
    if fast:
        lines.append(f"## Unusually Fast Approvals ({len(fast)} flagged)\n")
        lines.append("Permits with < 7 days to issuance AND cost > $100K:\n")
        for p in fast[:15]:
            cost = p.get('estimated_cost', 0)
            cost_str = f"${cost:,.0f}" if cost else "N/A"
            lines.append(
                f"- **{p.get('permit_number', 'N/A')}** — "
                f"{cost_str} | "
                f"{p.get('days_to_issue', '?')} days | "
                f"{p.get('neighborhood', 'N/A')}"
            )
        lines.append("")

    summary = results.get("summary", {})
    total_flags = sum(summary.values())
    lines.append(f"\n**Total anomalies flagged: {total_flags}**")

    return "\n".join(lines)
