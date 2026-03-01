"""HTTP transport entry point for SF Permits MCP server.

Exposes public-facing permit data tools over Streamable HTTP
for Claude.ai custom connector access.

SECURITY NOTE: Only safe, read-only public-data tools are registered here.
Project intelligence tools (run_query, read_source, search_source, schema_info,
list_tests) and list_feedback are EXCLUDED from the HTTP endpoint because they
expose internal DB, source code, and user data. Those tools are available only
via the stdio transport (local MCP / Claude Code).

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
import time

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Import safe, public-data tool functions only
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

# EXCLUDED from HTTP endpoint (security risk on public-facing server):
# - run_query: arbitrary SQL against DB (exposes user data, all tables)
# - read_source: reads source code files (exposes secrets, architecture)
# - search_source: searches codebase (finds passwords, API keys)
# - schema_info: exposes full DB schema (reconnaissance)
# - list_tests: test file inventory (minor info leak)
# - list_feedback: user feedback data (has emails, page URLs)

# ── Create MCP server with HTTP transport config ──────────────────
port = int(os.environ.get("PORT", 8001))

mcp = FastMCP(
    "SF Permits",
    instructions=(
        "SF Permits MCP server — query San Francisco public permitting data. "
        "28 tools: live SODA API queries, entity network analysis, "
        "permit decision tools, plan set validation, AI vision analysis, "
        "and addenda routing search across 3.9M+ records."
    ),
    host="0.0.0.0",
    port=port,
    stateless_http=True,
    streamable_http_path="/mcp",
)

# Register 28 public-data tools (no project intelligence / internal tools)
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

# ── Request logging + optional auth middleware ────────────────────
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

_MCP_AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN", "")

# Track request counts for monitoring
_request_log = {"total": 0, "by_ip": {}, "started_at": time.time()}


class RequestLoggingMiddleware:
    """ASGI middleware: log all /mcp requests with IP, user-agent, and timing.

    Also enforces bearer token auth when MCP_AUTH_TOKEN is set.
    Every request is logged regardless of auth status — this is how we
    detect unauthorized access attempts.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip logging for health/root endpoints
        if path in ("/", "/health"):
            await self.app(scope, receive, send)
            return

        # Extract client info
        headers = dict(scope.get("headers", []))
        client = scope.get("client", ("unknown", 0))
        ip = client[0] if client else "unknown"
        user_agent = headers.get(b"user-agent", b"").decode()[:100]
        method = scope.get("method", "?")

        # Log every request
        _request_log["total"] += 1
        _request_log["by_ip"][ip] = _request_log["by_ip"].get(ip, 0) + 1
        logger.info(
            "MCP request: ip=%s method=%s path=%s ua=%s total=%d ip_count=%d",
            ip, method, path, user_agent,
            _request_log["total"], _request_log["by_ip"][ip],
        )

        # Rate limit: 100 requests per IP per hour (rough — resets on restart)
        if _request_log["by_ip"][ip] > 100:
            uptime_hours = (time.time() - _request_log["started_at"]) / 3600
            if uptime_hours < 1:
                logger.warning("RATE LIMIT: ip=%s hit %d requests in %.1f hours",
                               ip, _request_log["by_ip"][ip], uptime_hours)
                response = JSONResponse(
                    {"error": "Rate limit exceeded. Try again later."},
                    status_code=429,
                )
                await response(scope, receive, send)
                return

        # Bearer token auth (if configured)
        if _MCP_AUTH_TOKEN:
            auth_header = headers.get(b"authorization", b"").decode()
            if not auth_header.startswith("Bearer "):
                logger.warning("AUTH FAIL: ip=%s path=%s — no bearer token", ip, path)
                response = JSONResponse(
                    {"error": "Authentication required."},
                    status_code=401,
                )
                await response(scope, receive, send)
                return
            provided_token = auth_header[7:]
            if not secrets.compare_digest(provided_token, _MCP_AUTH_TOKEN):
                logger.warning("AUTH FAIL: ip=%s path=%s — invalid token", ip, path)
                response = JSONResponse(
                    {"error": "Invalid authentication token"},
                    status_code=403,
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)


if _MCP_AUTH_TOKEN:
    logger.info("MCP bearer token auth enabled (blocks claude.ai — remove MCP_AUTH_TOKEN to allow)")
else:
    logger.info("MCP server open — request logging active, rate limiting at 100/hr per IP")


# ── Health check endpoint (for Railway) ───────────────────────────
async def health_check(request: StarletteRequest) -> JSONResponse:
    uptime_hours = round((time.time() - _request_log["started_at"]) / 3600, 1)
    return JSONResponse({
        "status": "healthy",
        "server": "SF Permits MCP",
        "tools": 28,
        "requests_total": _request_log["total"],
        "unique_ips": len(_request_log["by_ip"]),
        "uptime_hours": uptime_hours,
    })


mcp._custom_starlette_routes.append(Route("/health", health_check))
mcp._custom_starlette_routes.append(Route("/", health_check))


# ── Entry point ───────────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    import uvicorn

    async def main():
        app = mcp.streamable_http_app()

        # Always wrap with logging middleware (also handles auth if MCP_AUTH_TOKEN set)
        app = RequestLoggingMiddleware(app)

        config = uvicorn.Config(
            app,
            host=mcp.settings.host,
            port=mcp.settings.port,
            log_level=mcp.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(main())
