"""SF Permits MCP Server — FastMCP entry point.

Exposes San Francisco public permitting data to Claude via MCP tools.
Phase 1: Live SODA API queries for permits, businesses, properties.
Phase 2: Local DuckDB network analysis for entity search, relationships, anomalies.
"""

from fastmcp import FastMCP

from src.tools.search_permits import search_permits
from src.tools.get_permit_details import get_permit_details
from src.tools.permit_stats import permit_stats
from src.tools.search_businesses import search_businesses
from src.tools.property_lookup import property_lookup

# Phase 2 tools (local DuckDB)
from src.tools.search_entity import search_entity
from src.tools.entity_network import entity_network
from src.tools.network_anomalies import network_anomalies

# Create MCP server
mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "Tools cover building permits, business locations, property assessments, "
        "and network analysis of permit actors (contractors, architects, etc). "
        "Phase 1 tools query data.sfgov.org live. "
        "Phase 2 tools (search_entity, entity_network, network_anomalies) query "
        "a local DuckDB database of 1.8M+ resolved contact records."
    ),
)

# Phase 1 tools (live SODA API)
mcp.tool()(search_permits)
mcp.tool()(get_permit_details)
mcp.tool()(permit_stats)
mcp.tool()(search_businesses)
mcp.tool()(property_lookup)

# Phase 2 tools (local DuckDB network analysis)
mcp.tool()(search_entity)
mcp.tool()(entity_network)
mcp.tool()(network_anomalies)


if __name__ == "__main__":
    mcp.run()
