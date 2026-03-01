"""HTTP transport entry point for SF Permits MCP server.

Exposes the same 34 tools as the stdio server, but over Streamable HTTP
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

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

from src.oauth_provider import SFPermitsAuthProvider
from src.oauth_models import VALID_SCOPES

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

# ── Create MCP server with HTTP transport config and OAuth 2.1 ────
port = int(os.environ.get("PORT", 8001))

provider = SFPermitsAuthProvider()

mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "34 tools across 8 phases: live SODA API queries, entity network analysis, "
        "permit decision tools, plan set validation, AI vision analysis, "
        "addenda routing search across 3.9M+ records, and project intelligence "
        "tools for read-only database queries, source code reading, codebase search, "
        "schema introspection, and test inventory."
    ),
    host="0.0.0.0",
    port=port,
    stateless_http=True,
    streamable_http_path="/mcp",
    auth_server_provider=provider,
    auth=AuthSettings(
        issuer_url="https://sfpermits-mcp-api-production.up.railway.app",
        resource_server_url="https://sfpermits-mcp-api-production.up.railway.app",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=VALID_SCOPES,
            default_scopes=["demo"],
        ),
        revocation_options=RevocationOptions(enabled=True),
    ),
)

# Register all 34 tools
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


# ── Rate limiting middleware ───────────────────────────────────────
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send
from src.mcp_rate_limiter import get_limiter, truncate_if_needed

# Paths that bypass rate limiting (health + OAuth endpoints)
_RATE_LIMIT_SKIP_PATHS = frozenset([
    "/",
    "/health",
    "/.well-known/oauth-authorization-server",
    "/register",
    "/authorize",
    "/token",
    "/revoke",
])


class RateLimitMiddleware:
    """ASGI middleware: per-token/IP rate limiting."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip rate limiting for health/OAuth endpoints
        if path in _RATE_LIMIT_SKIP_PATHS:
            await self.app(scope, receive, send)
            return

        # Extract bearer token or fall back to IP
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        scope_str = None

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            rate_key = f"token:{token}"
            # scope_str remains None — anonymous tier.
            # In production the OAuth middleware has already validated the token;
            # scope enforcement (professional/unlimited) is handled there.
            # Using None here applies the safe anonymous limit as a floor for
            # any request that reaches the rate limiter without scope context.
        else:
            # Anonymous: key by IP
            client = scope.get("client")
            ip = client[0] if client else "unknown"
            rate_key = f"ip:{ip}"

        limiter = get_limiter()
        allowed, rl_headers = limiter.check_and_increment(rate_key, scope_str)

        if not allowed:
            response = JSONResponse(
                {"error": "Rate limit exceeded. Upgrade at https://sfpermits.ai/docs for more calls."},
                status_code=429,
                headers=rl_headers,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# ── Health check endpoint (for Railway) ───────────────────────────


async def health_check(request: StarletteRequest) -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "server": "SF Permits MCP",
        "tools": 34,
    })


mcp._custom_starlette_routes.append(Route("/health", health_check))
mcp._custom_starlette_routes.append(Route("/", health_check))


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def main():
        # Initialize OAuth tables at startup
        from src.db import get_connection, init_oauth_schema, BACKEND
        if BACKEND == "postgres":
            conn = get_connection()
            try:
                init_oauth_schema(conn)
            finally:
                conn.close()
        else:
            logger.info("DuckDB backend — skipping OAuth schema init")

        app = mcp.streamable_http_app()
        app = RateLimitMiddleware(app)
        config = uvicorn.Config(
            app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(main())
