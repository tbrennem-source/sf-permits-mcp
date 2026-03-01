"""HTTP transport entry point for SF Permits MCP server.

Exposes public-facing permit data tools over Streamable HTTP
for Claude.ai custom connector access.

SECURITY: Only safe, read-only public-data tools are registered here.
Project intelligence tools (run_query, read_source, search_source, schema_info,
list_tests) and list_feedback are EXCLUDED — they expose internal DB, source code,
and user data. Those tools are available only via stdio transport (local Claude Code).

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
import time

from mcp.server.fastmcp import FastMCP
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

from src.oauth_provider import SFPermitsAuthProvider
from src.oauth_models import VALID_SCOPES

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

# Phase 5.5 / 6 tools (severity, health — safe, read-only public data)
from src.tools.permit_severity import permit_severity
from src.tools.property_health import property_health

# EXCLUDED from HTTP endpoint (security risk on public-facing server):
# - run_query: arbitrary SQL against DB (exposes user tables, auth_tokens)
# - read_source: reads source code files (exposes secrets, architecture)
# - search_source: searches codebase (finds API keys, passwords)
# - schema_info: exposes full DB schema (reconnaissance)
# - list_tests: test file inventory (minor info leak)
# - list_feedback: user feedback data (has emails, page URLs)

# Phase 8 tools (similar projects)
from src.tools.similar_projects import similar_projects

# Phase 9 tools (station prediction, stuck permits, simulation, delay cost)
from src.tools.predict_next_stations import predict_next_stations
from src.tools.stuck_permit import diagnose_stuck_permit
from src.tools.what_if_simulator import simulate_what_if
from src.tools.cost_of_delay import calculate_delay_cost

# ── Create MCP server with HTTP transport config and OAuth 2.1 ────
port = int(os.environ.get("PORT", 8001))

provider = SFPermitsAuthProvider()

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

# Phase 5.5 / 6 tools (severity, health — safe public data)
mcp.tool()(permit_severity)
mcp.tool()(property_health)

# Phase 8 tools (similar projects)
mcp.tool()(similar_projects)

# Phase 9 tools (station prediction, stuck permits, simulation, delay cost)
mcp.tool()(predict_next_stations)
mcp.tool()(diagnose_stuck_permit)
mcp.tool()(simulate_what_if)
mcp.tool()(calculate_delay_cost)


# ── Rate limiting middleware ───────────────────────────────────────
from starlette.requests import Request as StarletteRequest
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send
from src.mcp_rate_limiter import get_limiter, truncate_if_needed

# Track request counts for security monitoring (in-memory, resets on restart)
_request_log: dict = {"total": 0, "by_ip": {}, "started_at": time.time()}


def _ensure_access_log_table():
    """Create mcp_access_log table if it doesn't exist."""
    try:
        from src.db import get_connection, BACKEND
        if BACKEND != "postgres":
            return
        conn = get_connection()
        try:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS mcp_access_log (
                        id SERIAL PRIMARY KEY,
                        ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        ip VARCHAR(45) NOT NULL,
                        method VARCHAR(10),
                        path VARCHAR(200),
                        user_agent VARCHAR(200),
                        rate_limited BOOLEAN DEFAULT FALSE
                    )
                """)
                # Index for daily report queries
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_mcp_access_log_ts
                    ON mcp_access_log (ts)
                """)
        finally:
            conn.close()
    except Exception as e:
        logger.warning("Could not create mcp_access_log table: %s", e)


def _log_access_to_db(ip: str, method: str, path: str, user_agent: str,
                       rate_limited: bool = False):
    """Write one access log row. Non-blocking — caller catches exceptions."""
    from src.db import get_connection, BACKEND
    if BACKEND != "postgres":
        return
    conn = get_connection()
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO mcp_access_log (ip, method, path, user_agent, rate_limited) "
                "VALUES (%s, %s, %s, %s, %s)",
                (ip, method, path[:200], user_agent[:200], rate_limited),
            )
    finally:
        conn.close()

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

        # Extract headers once
        headers = dict(scope.get("headers", []))

        # Log every /mcp request for security monitoring
        client = scope.get("client", ("unknown", 0))
        ip = client[0] if client else "unknown"
        user_agent = headers.get(b"user-agent", b"").decode()[:100]
        method = scope.get("method", "?")
        _request_log["total"] += 1
        _request_log["by_ip"][ip] = _request_log["by_ip"].get(ip, 0) + 1
        logger.info(
            "MCP request: ip=%s method=%s path=%s ua=%s total=%d",
            ip, method, path, user_agent, _request_log["total"],
        )

        # Persist to DB (non-blocking — failure doesn't block the request)
        try:
            _log_access_to_db(ip, method, path, user_agent)
        except Exception:
            pass  # Never let logging failure block a request

        # Extract bearer token or fall back to IP
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
            try:
                _log_access_to_db(ip, method, path, user_agent, rate_limited=True)
            except Exception:
                pass
            logger.warning("RATE LIMITED: ip=%s key=%s path=%s", ip, rate_key, path)
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
        # Initialize access log table at startup
        _ensure_access_log_table()

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
