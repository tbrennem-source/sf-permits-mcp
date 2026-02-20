"""HTTP transport entry point for SF Permits MCP server.

Exposes the same 21 tools as the stdio server, but over Streamable HTTP
for Claude.ai custom connector access.

Run locally:
    uvicorn src.mcp_http:app --host 0.0.0.0 --port 8001

Deploy:
    Railway service with Dockerfile.mcp

Connect from Claude.ai:
    Settings > Connectors > Add custom connector > paste URL + /mcp
"""

import os

from src.server import mcp

# ── Optional bearer token auth ────────────────────────────────────
# Set MCP_AUTH_TOKEN env var to require a bearer token.
# If unset, server runs authless (fine for testing / personal use).
token = os.environ.get("MCP_AUTH_TOKEN")
if token:
    from fastmcp.server.auth import StaticTokenVerifier

    verifier = StaticTokenVerifier(
        tokens={token: {"client_id": "claude-ai", "scopes": ["tools"]}}
    )
    mcp.auth = verifier

# ── ASGI app ──────────────────────────────────────────────────────
app = mcp.http_app(
    path="/mcp",
    stateless_http=True,
    json_response=True,
)
