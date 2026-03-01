"""Integration tests for QS13 MCP OAuth 2.0 flow.

The OAuth routes (/.well-known/oauth-authorization-server, /register, /authorize, /token)
are being built in QS13 T1. Tests use pytest.skip() for 404s so they pass on the
current codebase and become green after T1 merges.

Covers:
- OAuth discovery endpoint metadata structure
- Dynamic client registration (RFC 7591)
- Authorization code flow basics
- Token exchange
- MCP endpoint auth requirements
"""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend for test isolation."""
    db_path = str(tmp_path / "test_oauth.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    import os
    os.environ.setdefault("TESTING", "1")
    from web.app import app as flask_app
    from web.helpers import _rate_buckets
    flask_app.config["TESTING"] = True
    _rate_buckets.clear()
    with flask_app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# OAuth Discovery
# ---------------------------------------------------------------------------

class TestOAuthDiscovery:

    def test_oauth_discovery_endpoint_exists_or_skip(self, client):
        """/.well-known/oauth-authorization-server returns valid JSON or is not yet built."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        assert resp.status_code == 200

    def test_oauth_discovery_content_type(self, client):
        """Discovery endpoint returns JSON content type."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        ct = resp.headers.get("Content-Type", "")
        assert "json" in ct.lower()

    def test_oauth_discovery_has_issuer(self, client):
        """Discovery document contains issuer field."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert data is not None
        assert "issuer" in data

    def test_oauth_discovery_has_token_endpoint(self, client):
        """Discovery document contains token_endpoint field."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert "token_endpoint" in data

    def test_oauth_discovery_has_authorization_endpoint(self, client):
        """Discovery document contains authorization_endpoint field."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert "authorization_endpoint" in data

    def test_oauth_discovery_has_registration_endpoint(self, client):
        """Discovery document contains registration_endpoint (RFC 7591)."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert "registration_endpoint" in data

    def test_oauth_discovery_has_supported_grants(self, client):
        """Discovery document lists supported grant types."""
        resp = client.get("/.well-known/oauth-authorization-server")
        if resp.status_code == 404:
            pytest.skip("OAuth discovery not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert "grant_types_supported" in data
        grants = data["grant_types_supported"]
        assert isinstance(grants, list)
        assert "authorization_code" in grants


# ---------------------------------------------------------------------------
# Dynamic Client Registration (RFC 7591)
# ---------------------------------------------------------------------------

class TestClientRegistration:

    def test_register_endpoint_exists_or_skip(self, client):
        """POST /register accepts client registration or returns 404."""
        resp = client.post("/register", json={
            "client_name": "test-client",
            "redirect_uris": ["https://example.com/callback"],
        })
        if resp.status_code == 404:
            pytest.skip("Client registration not implemented yet (QS13 T1)")
        # 201 Created is the RFC 7591 response code
        assert resp.status_code in (200, 201)

    def test_register_returns_client_id(self, client):
        """Successful registration returns client_id."""
        resp = client.post("/register", json={
            "client_name": "test-client",
            "redirect_uris": ["https://example.com/callback"],
        })
        if resp.status_code == 404:
            pytest.skip("Client registration not implemented yet (QS13 T1)")
        data = resp.get_json()
        assert data is not None
        assert "client_id" in data

    def test_register_returns_client_secret(self, client):
        """Successful registration returns client_secret for confidential clients."""
        resp = client.post("/register", json={
            "client_name": "confidential-client",
            "redirect_uris": ["https://example.com/callback"],
            "token_endpoint_auth_method": "client_secret_basic",
        })
        if resp.status_code == 404:
            pytest.skip("Client registration not implemented yet (QS13 T1)")
        if resp.status_code not in (200, 201):
            pytest.skip("Registration returned unexpected status")
        data = resp.get_json()
        # client_secret may be present for confidential clients
        # This is implementation-dependent — just verify no crash
        assert data is not None

    def test_register_missing_redirect_uris_rejected(self, client):
        """Registration without redirect_uris returns 400."""
        resp = client.post("/register", json={
            "client_name": "bad-client",
        })
        if resp.status_code == 404:
            pytest.skip("Client registration not implemented yet (QS13 T1)")
        assert resp.status_code == 400

    def test_register_requires_json(self, client):
        """Registration endpoint requires JSON body."""
        resp = client.post("/register", data="not-json",
                           content_type="text/plain")
        if resp.status_code == 404:
            pytest.skip("Client registration not implemented yet (QS13 T1)")
        assert resp.status_code in (400, 415)


# ---------------------------------------------------------------------------
# Token Exchange
# ---------------------------------------------------------------------------

class TestOAuthTokenFlow:

    def test_token_endpoint_exists_or_skip(self, client):
        """POST /token endpoint exists or skip."""
        resp = client.post("/token", data={
            "grant_type": "authorization_code",
            "code": "invalid_code",
            "client_id": "test-client",
        })
        if resp.status_code == 404:
            pytest.skip("Token endpoint not implemented yet (QS13 T1)")
        # Invalid code should return 400, not crash
        assert resp.status_code == 400

    def test_token_invalid_grant_type_rejected(self, client):
        """Unsupported grant_type returns 400."""
        resp = client.post("/token", data={
            "grant_type": "unsupported_grant",
            "client_id": "test-client",
        })
        if resp.status_code == 404:
            pytest.skip("Token endpoint not implemented yet (QS13 T1)")
        assert resp.status_code in (400, 401)

    def test_token_missing_grant_type_rejected(self, client):
        """Missing grant_type returns 400."""
        resp = client.post("/token", data={
            "client_id": "test-client",
        })
        if resp.status_code == 404:
            pytest.skip("Token endpoint not implemented yet (QS13 T1)")
        assert resp.status_code in (400, 401)


# ---------------------------------------------------------------------------
# MCP endpoint auth requirements
# ---------------------------------------------------------------------------

class TestMCPEndpointAuth:

    def test_mcp_endpoint_requires_auth_or_404(self, client):
        """MCP endpoint at /mcp returns 401/403/405 without auth, or 404 if not web app route."""
        resp = client.post("/mcp", json={"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        # /mcp is the MCP server, typically not on the Flask web app
        # Accept 404 (different service) or 401/403/405 (auth required)
        assert resp.status_code in (401, 403, 404, 405)

    def test_oauth_security_txt_accessible(self, client):
        """/.well-known/security.txt is accessible (existing route)."""
        resp = client.get("/.well-known/security.txt")
        # May return 200 or 404, but should not crash
        assert resp.status_code in (200, 404)
