"""OAuth 2.1 constants and helpers for SF Permits MCP server."""

import secrets

# Token expiry durations
ACCESS_TOKEN_EXPIRY_SECONDS = 3600       # 1 hour
REFRESH_TOKEN_EXPIRY_SECONDS = 2592000   # 30 days
AUTH_CODE_EXPIRY_SECONDS = 600           # 10 minutes

# Valid OAuth scopes
VALID_SCOPES = ["demo", "professional", "unlimited"]

# Rate limits per scope (requests per minute, None = unlimited)
SCOPE_RATE_LIMITS = {
    "demo": 10,
    "professional": 1000,
    "unlimited": None,   # no limit
    None: 5,             # anonymous
}


def generate_token() -> str:
    """Generate a cryptographically secure token string.

    Returns a URL-safe base64-encoded string with 32 bytes of randomness.
    Length is 43 characters (32 bytes → 43 chars in urlsafe base64 without padding).
    """
    return secrets.token_urlsafe(32)
