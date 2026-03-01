"""Tests for OAuth 2.1 provider implementation.

All tests mock the database layer so they work without a live PostgreSQL connection.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta


# ── oauth_models tests ─────────────────────────────────────────────

def test_generate_token():
    """generate_token returns a 43-char URL-safe base64 string."""
    from src.oauth_models import generate_token
    t = generate_token()
    # secrets.token_urlsafe(32) produces 43 characters
    assert len(t) == 43


def test_generate_token_unique():
    """Each generate_token call returns a unique value."""
    from src.oauth_models import generate_token
    tokens = {generate_token() for _ in range(10)}
    assert len(tokens) == 10


def test_scope_rate_limits():
    """SCOPE_RATE_LIMITS maps scopes to correct rate limits."""
    from src.oauth_models import SCOPE_RATE_LIMITS
    assert SCOPE_RATE_LIMITS["demo"] == 10
    assert SCOPE_RATE_LIMITS["professional"] == 1000
    assert SCOPE_RATE_LIMITS["unlimited"] is None
    assert SCOPE_RATE_LIMITS[None] == 5


def test_valid_scopes():
    """VALID_SCOPES contains exactly the three expected scopes."""
    from src.oauth_models import VALID_SCOPES
    assert set(VALID_SCOPES) == {"demo", "professional", "unlimited"}


def test_expiry_constants():
    """Token expiry constants have sensible positive values."""
    from src.oauth_models import (
        ACCESS_TOKEN_EXPIRY_SECONDS,
        REFRESH_TOKEN_EXPIRY_SECONDS,
        AUTH_CODE_EXPIRY_SECONDS,
    )
    assert ACCESS_TOKEN_EXPIRY_SECONDS == 3600
    assert REFRESH_TOKEN_EXPIRY_SECONDS == 2592000
    assert AUTH_CODE_EXPIRY_SECONDS == 600
    # Access token should expire before refresh token
    assert ACCESS_TOKEN_EXPIRY_SECONDS < REFRESH_TOKEN_EXPIRY_SECONDS


# ── oauth_provider instantiation ─────────────────────────────────

def test_provider_instantiates():
    """SFPermitsAuthProvider can be instantiated without errors."""
    from src.oauth_provider import SFPermitsAuthProvider
    p = SFPermitsAuthProvider()
    assert p is not None


# ── load_access_token ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_load_access_token_not_found():
    """load_access_token returns None for unknown token."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.load_access_token("nonexistent-token")

    assert result is None


@pytest.mark.asyncio
async def test_load_access_token_expired():
    """load_access_token returns None for an expired token."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    # Use a timezone-aware datetime that is in the past (DB returns naive datetime)
    expired_at = datetime.now(timezone.utc) - timedelta(hours=2)
    expired_at_naive = expired_at.replace(tzinfo=None)  # DB returns naive

    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ("tok", "client1", "demo", expired_at_naive)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.load_access_token("expired-token")

    assert result is None


@pytest.mark.asyncio
async def test_load_access_token_valid():
    """load_access_token returns AccessToken for a valid unexpired token."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    future_at = datetime.now(timezone.utc) + timedelta(hours=1)
    future_at_naive = future_at.replace(tzinfo=None)  # DB returns naive datetime

    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = ("mytoken", "client1", "demo professional", future_at_naive)
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.load_access_token("mytoken")

    assert result is not None
    assert result.token == "mytoken"
    assert result.client_id == "client1"
    assert "demo" in result.scopes
    assert "professional" in result.scopes


# ── get_client ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_client_not_found():
    """get_client returns None for unknown client_id."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.get_client("unknown-client")

    assert result is None


@pytest.mark.asyncio
async def test_get_client_found():
    """get_client returns OAuthClientInformationFull for a known client."""
    from src.oauth_provider import SFPermitsAuthProvider
    from mcp.shared.auth import OAuthClientInformationFull

    provider = SFPermitsAuthProvider()
    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (
                "client-123",
                "secret-abc",
                ["https://example.com/callback"],
                "Test App",
                "demo",
            )
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.get_client("client-123")

    assert result is not None
    assert result.client_id == "client-123"
    assert result.client_secret == "secret-abc"
    # redirect_uris contains AnyUrl objects; compare via string representation
    assert any("example.com/callback" in str(u) for u in result.redirect_uris)


# ── register_client ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_client_executes_insert():
    """register_client calls INSERT with correct fields."""
    from src.oauth_provider import SFPermitsAuthProvider
    from mcp.shared.auth import OAuthClientInformationFull

    provider = SFPermitsAuthProvider()
    client_info = OAuthClientInformationFull(
        client_id="new-client",
        client_secret="new-secret",
        redirect_uris=["https://app.example.com/cb"],
        client_name="New App",
        scope="demo",
    )

    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                await provider.register_client(client_info)

    # Verify that execute was called (INSERT happened)
    assert mock_cursor.execute.called
    call_args = mock_cursor.execute.call_args[0]
    assert "INSERT INTO mcp_oauth_clients" in call_args[0]
    assert "new-client" in call_args[1]


# ── authorize ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authorize_returns_redirect_url():
    """authorize returns a URL containing the code and state."""
    from src.oauth_provider import SFPermitsAuthProvider
    from mcp.shared.auth import OAuthClientInformationFull
    from mcp.server.auth.provider import AuthorizationParams

    provider = SFPermitsAuthProvider()
    client = OAuthClientInformationFull(
        client_id="client-xyz",
        redirect_uris=["https://app.example.com/cb"],
    )
    params = AuthorizationParams(
        state="mystate",
        scopes=["demo"],
        code_challenge="challenge123",
        redirect_uri="https://app.example.com/cb",
        redirect_uri_provided_explicitly=True,
    )

    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                redirect = await provider.authorize(client, params)

    assert "code=" in redirect
    assert "state=mystate" in redirect
    assert redirect.startswith("https://app.example.com/cb")


# ── DuckDB backend short-circuits ────────────────────────────────

@pytest.mark.asyncio
async def test_load_access_token_duckdb_returns_none():
    """In DuckDB mode, load_access_token returns None without DB call."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    with patch("src.oauth_provider.BACKEND", "duckdb"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            result = await provider.load_access_token("any-token")
            # get_connection should NOT be called in duckdb mode
            mock_gc.assert_not_called()

    assert result is None


@pytest.mark.asyncio
async def test_get_client_duckdb_returns_none():
    """In DuckDB mode, get_client returns None without DB call."""
    from src.oauth_provider import SFPermitsAuthProvider

    provider = SFPermitsAuthProvider()
    with patch("src.oauth_provider.BACKEND", "duckdb"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            result = await provider.get_client("any-client")
            mock_gc.assert_not_called()

    assert result is None


# ── load_authorization_code expiry ───────────────────────────────

@pytest.mark.asyncio
async def test_load_authorization_code_expired():
    """load_authorization_code returns None for an expired code."""
    from src.oauth_provider import SFPermitsAuthProvider
    from mcp.shared.auth import OAuthClientInformationFull

    provider = SFPermitsAuthProvider()
    client = OAuthClientInformationFull(
        client_id="client-abc",
        redirect_uris=["https://example.com/cb"],
    )
    expired_at = datetime.now(timezone.utc) - timedelta(minutes=15)

    with patch("src.oauth_provider.BACKEND", "postgres"):
        with patch("src.oauth_provider.get_connection") as mock_gc:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (
                "code123", "client-abc", "demo", "challenge", "https://example.com/cb", expired_at
            )
            mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
            mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
            mock_gc.return_value = mock_conn
            with patch.object(mock_conn, "close"):
                result = await provider.load_authorization_code(client, "code123")

    assert result is None
