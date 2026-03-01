"""HTTP transport entry point for SF Permits MCP server.

Exposes the same 27 tools as the stdio server, but over Streamable HTTP
for Claude.ai custom connector access.

Uses mcp[cli] package (same as Chief MCP server — proven claude.ai compatibility).

Run locally:
    python -m src.mcp_http

Deploy:
    Railway service with Dockerfile.mcp

Connect from Claude.ai:
    Settings > Integrations > Add MCP server > paste URL + /mcp
"""

import logging
import os
import secrets

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Import all tool functions (same as server.py)
from src.tools.search_permits import search_permits
from src.tools.get_permit_details import get_permit_details
from src.tools.permit_stats import permit_stats
from src.tools.search_businesses import search_businesses
from src.tools.property_lookup import property_lookup
from src.tools.search_complaints import search_complaints
from src.tools.search_violations import search_violations
from src.tools.search_inspections import search_inspections
from src.tools.search_entity import search_entity
from src.tools.entity_network import entity_network
from src.tools.network_anomalies import network_anomalies
from src.tools.predict_permits import predict_permits
from src.tools.estimate_timeline import estimate_timeline
from src.tools.estimate_fees import estimate_fees
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk
from src.tools.validate_plans import validate_plans
from src.tools.analyze_plans import analyze_plans
from src.tools.recommend_consultants import recommend_consultants
from src.tools.permit_lookup import permit_lookup
from src.tools.search_addenda import search_addenda
from src.tools.list_feedback import list_feedback

# Phase 7 tools (project intelligence)
from src.tools.project_intel import run_query, read_source, search_source, schema_info, list_tests

# ── Create MCP server with HTTP transport config ──────────────────
port = int(os.environ.get("PORT", 8001))

mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "27 tools across 7 phases: live SODA API queries, entity network analysis, "
        "permit decision tools, plan set validation, AI vision analysis, "
        "addenda routing search across 3.9M+ records, and project intelligence "
        "tools for read-only database queries, source code reading, codebase search, "
        "schema introspection, and test inventory."
    ),
    host="0.0.0.0",
    port=port,
    stateless_http=True,
    streamable_http_path="/mcp",
)

# Register all 27 tools
mcp.tool()(search_permits)
mcp.tool()(get_permit_details)
mcp.tool()(permit_stats)
mcp.tool()(search_businesses)
mcp.tool()(property_lookup)
mcp.tool()(search_complaints)
mcp.tool()(search_violations)
mcp.tool()(search_inspections)
mcp.tool()(search_entity)
mcp.tool()(entity_network)
mcp.tool()(network_anomalies)
mcp.tool()(predict_permits)
mcp.tool()(estimate_timeline)
mcp.tool()(estimate_fees)
mcp.tool()(required_documents)
mcp.tool()(revision_risk)
mcp.tool()(validate_plans)
mcp.tool()(analyze_plans)
mcp.tool()(recommend_consultants)
mcp.tool()(permit_lookup)
mcp.tool()(search_addenda)
mcp.tool()(list_feedback)

# Phase 7 tools (project intelligence)
mcp.tool()(run_query)
mcp.tool()(read_source)
mcp.tool()(search_source)
mcp.tool()(schema_info)
mcp.tool()(list_tests)

# ── Bearer token auth middleware (stopgap until OAuth in QS13) ────
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

_MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")


class BearerTokenMiddleware:
    """ASGI middleware: reject unauthenticated /mcp requests when MCP_AUTH_TOKEN is set."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip auth for health/root endpoints
        if path in ("/", "/health"):
            await self.app(scope, receive, send)
            return

        # Skip auth if no token configured (backwards compatible)
        if not _MCP_AUTH_TOKEN:
            await self.app(scope, receive, send)
            return

        # Extract Authorization header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()

        if not auth_header.startswith("Bearer "):
            response = JSONResponse(
                {"error": "Authentication required. Provide Authorization: Bearer <token>"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        provided_token = auth_header[7:]  # Strip "Bearer "
        if not secrets.compare_digest(provided_token, _MCP_AUTH_TOKEN):
            response = JSONResponse(
                {"error": "Invalid authentication token"},
                status_code=403,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


if _MCP_AUTH_TOKEN:
    logger.info("MCP bearer token auth enabled")
else:
    logger.warning("MCP_AUTH_TOKEN not set — MCP server is unauthenticated")


# ── Health check endpoint (for Railway) ───────────────────────────
async def health_check(request: StarletteRequest) -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "server": "SF Permits MCP",
        "tools": 27,
    })


mcp._custom_starlette_routes.append(Route("/health", health_check))
mcp._custom_starlette_routes.append(Route("/", health_check))


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def main():
        app = mcp.streamable_http_app()

        # Wrap with bearer token auth if configured
        if _MCP_AUTH_TOKEN:
            app = BearerTokenMiddleware(app)

        config = uvicorn.Config(
            app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(main())
