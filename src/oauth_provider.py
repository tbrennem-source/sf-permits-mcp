"""OAuth 2.1 Authorization Server Provider for SF Permits MCP server.

Implements OAuthAuthorizationServerProvider using PostgreSQL for token/client storage.
Falls back gracefully when no DATABASE_URL is set (DuckDB mode — OAuth not supported).
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    AuthorizationCode,
    AuthorizationParams,
    AccessToken,
    RefreshToken,
    OAuthToken,
)
from mcp.shared.auth import OAuthClientInformationFull

from src.db import get_connection, BACKEND
from src.oauth_models import (
    ACCESS_TOKEN_EXPIRY_SECONDS,
    REFRESH_TOKEN_EXPIRY_SECONDS,
    AUTH_CODE_EXPIRY_SECONDS,
    generate_token,
)

logger = logging.getLogger(__name__)


class SFPermitsAuthProvider(OAuthAuthorizationServerProvider):
    """PostgreSQL-backed OAuth 2.1 authorization server.

    Stores clients, auth codes, and tokens in the mcp_oauth_* tables.
    All methods are async-safe and use connection pool borrowing.
    """

    # ── Client management ────────────────────────────────────────────

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        """Look up a registered client by client_id."""
        if BACKEND != "postgres":
            logger.debug("OAuth get_client: DuckDB backend — returning None")
            return None

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT client_id, client_secret, redirect_uris, client_name, scope "
                    "FROM mcp_oauth_clients WHERE client_id = %s",
                    (client_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                cid, secret, redirect_uris, client_name, scope = row
                return OAuthClientInformationFull(
                    client_id=cid,
                    client_secret=secret,
                    redirect_uris=redirect_uris or [],
                    client_name=client_name,
                    scope=scope or "demo",
                )
        finally:
            conn.close()

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Persist a newly registered OAuth client."""
        if BACKEND != "postgres":
            logger.warning("OAuth register_client: DuckDB backend — ignoring")
            return

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mcp_oauth_clients
                        (client_id, client_secret, redirect_uris, client_name, scope)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (client_id) DO UPDATE SET
                        client_secret = EXCLUDED.client_secret,
                        redirect_uris = EXCLUDED.redirect_uris,
                        client_name   = EXCLUDED.client_name,
                        scope         = EXCLUDED.scope
                    """,
                    (
                        client_info.client_id,
                        client_info.client_secret,
                        list(client_info.redirect_uris),
                        client_info.client_name,
                        client_info.scope or "demo",
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    # ── Authorization code flow ──────────────────────────────────────

    async def authorize(
        self,
        client: OAuthClientInformationFull,
        params: AuthorizationParams,
    ) -> str:
        """Generate an authorization code and return the redirect URL.

        Stores the code in mcp_oauth_codes and returns a redirect URI with
        the code (and state) appended as query parameters.
        """
        code = generate_token()
        redirect_uri = str(params.redirect_uri) if params.redirect_uri else ""
        scope_str = " ".join(params.scopes) if params.scopes else "demo"
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=AUTH_CODE_EXPIRY_SECONDS)

        if BACKEND == "postgres":
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO mcp_oauth_codes
                            (code, client_id, redirect_uri, scope,
                             code_challenge, code_challenge_method, expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            code,
                            client.client_id,
                            redirect_uri,
                            scope_str,
                            params.code_challenge,
                            "S256",
                            expires_at,
                        ),
                    )
                conn.commit()
            finally:
                conn.close()
        else:
            logger.warning("OAuth authorize: DuckDB backend — code not persisted")

        # Build redirect URL with code (and optional state)
        sep = "&" if "?" in redirect_uri else "?"
        redirect = f"{redirect_uri}{sep}code={code}"
        if params.state:
            redirect += f"&state={params.state}"
        return redirect

    async def load_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: str,
    ) -> Optional[AuthorizationCode]:
        """Load an authorization code from storage."""
        if BACKEND != "postgres":
            return None

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT code, client_id, scope, code_challenge,
                           redirect_uri, expires_at
                    FROM mcp_oauth_codes
                    WHERE code = %s AND client_id = %s
                    """,
                    (authorization_code, client.client_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                code, cid, scope, challenge, redirect_uri, expires_at = row

                # Normalise timezone info
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) > expires_at:
                    logger.debug("OAuth: authorization code expired")
                    return None

                scopes = scope.split() if scope else ["demo"]
                return AuthorizationCode(
                    code=code,
                    client_id=cid,
                    scopes=scopes,
                    expires_at=expires_at.timestamp(),
                    code_challenge=challenge,
                    redirect_uri=redirect_uri,
                    redirect_uri_provided_explicitly=bool(redirect_uri),
                )
        finally:
            conn.close()

    async def exchange_authorization_code(
        self,
        client: OAuthClientInformationFull,
        authorization_code: AuthorizationCode,
    ) -> OAuthToken:
        """Exchange an auth code for access + refresh tokens."""
        access_token = generate_token()
        refresh_token = generate_token()
        now = datetime.now(timezone.utc)
        access_expires = now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)
        scope_str = " ".join(authorization_code.scopes) if authorization_code.scopes else "demo"

        if BACKEND == "postgres":
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    # Delete the used code
                    cur.execute(
                        "DELETE FROM mcp_oauth_codes WHERE code = %s",
                        (authorization_code.code,),
                    )

                    # Insert access token
                    cur.execute(
                        """
                        INSERT INTO mcp_oauth_tokens
                            (token, token_type, client_id, scope, expires_at, refresh_token)
                        VALUES (%s, 'access', %s, %s, %s, %s)
                        """,
                        (access_token, client.client_id, scope_str, access_expires, refresh_token),
                    )

                    # Insert refresh token
                    cur.execute(
                        """
                        INSERT INTO mcp_oauth_tokens
                            (token, token_type, client_id, scope, expires_at)
                        VALUES (%s, 'refresh', %s, %s, %s)
                        """,
                        (refresh_token, client.client_id, scope_str, refresh_expires),
                    )

                conn.commit()
            finally:
                conn.close()

        return OAuthToken(
            access_token=access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
            scope=scope_str,
            refresh_token=refresh_token,
        )

    # ── Refresh token flow ───────────────────────────────────────────

    async def load_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: str,
    ) -> Optional[RefreshToken]:
        """Load a refresh token from storage."""
        if BACKEND != "postgres":
            return None

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT token, client_id, scope, expires_at
                    FROM mcp_oauth_tokens
                    WHERE token = %s AND token_type = 'refresh' AND client_id = %s
                    """,
                    (refresh_token, client.client_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                token, cid, scope, expires_at = row
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) > expires_at:
                    logger.debug("OAuth: refresh token expired")
                    return None

                scopes = scope.split() if scope else ["demo"]
                return RefreshToken(
                    token=token,
                    client_id=cid,
                    scopes=scopes,
                    expires_at=int(expires_at.timestamp()),
                )
        finally:
            conn.close()

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list,
    ) -> OAuthToken:
        """Rotate tokens: invalidate old refresh token, issue new access + refresh."""
        new_access = generate_token()
        new_refresh = generate_token()
        now = datetime.now(timezone.utc)
        access_expires = now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS)
        refresh_expires = now + timedelta(seconds=REFRESH_TOKEN_EXPIRY_SECONDS)

        # Use requested scopes if provided, otherwise keep existing
        effective_scopes = scopes if scopes else refresh_token.scopes
        scope_str = " ".join(effective_scopes) if effective_scopes else "demo"

        if BACKEND == "postgres":
            conn = get_connection()
            try:
                with conn.cursor() as cur:
                    # Delete old refresh token
                    cur.execute(
                        "DELETE FROM mcp_oauth_tokens WHERE token = %s",
                        (refresh_token.token,),
                    )

                    # Also delete any access tokens linked to this refresh token
                    cur.execute(
                        "DELETE FROM mcp_oauth_tokens WHERE refresh_token = %s",
                        (refresh_token.token,),
                    )

                    # Insert new access token
                    cur.execute(
                        """
                        INSERT INTO mcp_oauth_tokens
                            (token, token_type, client_id, scope, expires_at, refresh_token)
                        VALUES (%s, 'access', %s, %s, %s, %s)
                        """,
                        (new_access, client.client_id, scope_str, access_expires, new_refresh),
                    )

                    # Insert new refresh token
                    cur.execute(
                        """
                        INSERT INTO mcp_oauth_tokens
                            (token, token_type, client_id, scope, expires_at)
                        VALUES (%s, 'refresh', %s, %s, %s)
                        """,
                        (new_refresh, client.client_id, scope_str, refresh_expires),
                    )

                conn.commit()
            finally:
                conn.close()

        return OAuthToken(
            access_token=new_access,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
            scope=scope_str,
            refresh_token=new_refresh,
        )

    # ── Token validation & revocation ────────────────────────────────

    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        """Load and validate an access token."""
        if BACKEND != "postgres":
            return None

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT token, client_id, scope, expires_at
                    FROM mcp_oauth_tokens
                    WHERE token = %s AND token_type = 'access'
                    """,
                    (token,),
                )
                row = cur.fetchone()
                if row is None:
                    return None

                tok, cid, scope, expires_at = row
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)

                if datetime.now(timezone.utc) > expires_at:
                    logger.debug("OAuth: access token expired")
                    return None

                scopes = scope.split() if scope else ["demo"]
                return AccessToken(
                    token=tok,
                    client_id=cid,
                    scopes=scopes,
                    expires_at=int(expires_at.timestamp()),
                )
        finally:
            conn.close()

    async def revoke_token(
        self,
        token,
    ) -> None:
        """Revoke an access or refresh token (and its pair)."""
        if BACKEND != "postgres":
            return

        # token can be AccessToken or RefreshToken pydantic model
        token_str = token.token if hasattr(token, "token") else str(token)

        conn = get_connection()
        try:
            with conn.cursor() as cur:
                # Find the token to determine its type
                cur.execute(
                    "SELECT token_type, refresh_token FROM mcp_oauth_tokens WHERE token = %s",
                    (token_str,),
                )
                row = cur.fetchone()
                if row is None:
                    return  # Already revoked or never existed

                token_type, linked_refresh = row

                # Delete the token itself
                cur.execute(
                    "DELETE FROM mcp_oauth_tokens WHERE token = %s",
                    (token_str,),
                )

                if token_type == "access" and linked_refresh:
                    # Also revoke the paired refresh token
                    cur.execute(
                        "DELETE FROM mcp_oauth_tokens WHERE token = %s",
                        (linked_refresh,),
                    )
                elif token_type == "refresh":
                    # Also revoke any access tokens linked to this refresh
                    cur.execute(
                        "DELETE FROM mcp_oauth_tokens WHERE refresh_token = %s",
                        (token_str,),
                    )

            conn.commit()
        finally:
            conn.close()
