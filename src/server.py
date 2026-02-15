"""SF Permits MCP Server — FastMCP entry point.

Exposes San Francisco public permitting data to Claude via MCP tools.
Phase 1: Live SODA API queries for permits, businesses, properties.
Phase 2: Local DuckDB network analysis for entity search, relationships, anomalies.
Phase 2.75: Permit decision tools — prediction, timelines, fees, documents, revision risk.
"""

from fastmcp import FastMCP

from src.tools.search_permits import search_permits
from src.tools.get_permit_details import get_permit_details
from src.tools.permit_stats import permit_stats
from src.tools.search_businesses import search_businesses
from src.tools.property_lookup import property_lookup

# Phase 1.5 tools (DBI enforcement — live SODA API)
from src.tools.search_complaints import search_complaints
from src.tools.search_violations import search_violations
from src.tools.search_inspections import search_inspections

# Phase 2 tools (local DuckDB)
from src.tools.search_entity import search_entity
from src.tools.entity_network import entity_network
from src.tools.network_anomalies import network_anomalies

# Phase 2.75 tools (knowledge base + DuckDB)
from src.tools.predict_permits import predict_permits
from src.tools.estimate_timeline import estimate_timeline
from src.tools.estimate_fees import estimate_fees
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk

# Phase 3 tools (document analysis)
from src.tools.validate_plans import validate_plans

# Phase 2 tools (expediter recommender)
from src.tools.recommend_expediters import recommend_expediters

# Phase 4 tools (lookup / status)
from src.tools.permit_lookup import permit_lookup

# Create MCP server
mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "Phase 1 tools (search_permits, get_permit_details, permit_stats, "
        "search_businesses, property_lookup) query data.sfgov.org live. "
        "Phase 2 tools (search_entity, entity_network, network_anomalies) query "
        "a local DuckDB database of 1.8M+ resolved contact records. "
        "Phase 2.75 tools (predict_permits, estimate_timeline, estimate_fees, "
        "required_documents, revision_risk) walk a 7-step SF permit decision tree "
        "backed by structured knowledge (fee tables, routing matrix, OTC criteria, "
        "fire/planning code) plus DuckDB historical statistics from 1.1M+ permits. "
        "Phase 3 tool (validate_plans) checks PDF plan sets against DBI EPR requirements. "
        "Phase 1.5 tools (search_complaints, search_violations, search_inspections) query "
        "DBI enforcement datasets via SODA API for building complaints, notices of violation, "
        "and inspection records — useful for due diligence and property analysis. "
        "Phase 4 tool (permit_lookup) searches local DB by permit number, address, or parcel "
        "and returns full details, project team, inspections, and related permits."
    ),
)

# Phase 1 tools (live SODA API)
mcp.tool()(search_permits)
mcp.tool()(get_permit_details)
mcp.tool()(permit_stats)
mcp.tool()(search_businesses)
mcp.tool()(property_lookup)

# Phase 1.5 tools (DBI enforcement — live SODA API)
mcp.tool()(search_complaints)
mcp.tool()(search_violations)
mcp.tool()(search_inspections)

# Phase 2 tools (local DuckDB network analysis)
mcp.tool()(search_entity)
mcp.tool()(entity_network)
mcp.tool()(network_anomalies)

# Phase 2.75 tools (permit decision tools)
mcp.tool()(predict_permits)
mcp.tool()(estimate_timeline)
mcp.tool()(estimate_fees)
mcp.tool()(required_documents)
mcp.tool()(revision_risk)

# Phase 3 tools (document analysis)
mcp.tool()(validate_plans)

# Phase 2 tools (expediter recommender)
mcp.tool()(recommend_expediters)

# Phase 4 tools (lookup / status)
mcp.tool()(permit_lookup)


if __name__ == "__main__":
    mcp.run()
