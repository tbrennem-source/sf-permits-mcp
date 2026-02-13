"""SF Permits MCP Server — FastMCP entry point.

Exposes San Francisco public permitting data to Claude via MCP tools.
"""

from fastmcp import FastMCP

from src.tools.search_permits import search_permits
from src.tools.get_permit_details import get_permit_details
from src.tools.permit_stats import permit_stats
from src.tools.search_businesses import search_businesses
from src.tools.property_lookup import property_lookup

# Create MCP server
mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "Tools cover building permits, business locations, and property assessments. "
        "All data sourced from data.sfgov.org (Socrata SODA API)."
    ),
)

# Register tools
mcp.tool()(search_permits)
mcp.tool()(get_permit_details)
mcp.tool()(permit_stats)
mcp.tool()(search_businesses)
mcp.tool()(property_lookup)


if __name__ == "__main__":
    mcp.run()
