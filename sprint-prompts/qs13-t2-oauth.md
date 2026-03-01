> EXECUTE IMMEDIATELY. You are a build terminal in a quad sprint. Read the tasks below and execute them sequentially. Do NOT summarize or ask for confirmation — execute now.

# QS13 T2 — OAuth 2.1 + MCP Server Hardening (Sprint 99)

You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
CRITICAL: NEVER run git checkout main or git merge. Commit to YOUR branch only.

## Read First
- CLAUDE.md (project rules, especially MCP server section)
- src/mcp_http.py (current MCP server — 165 lines, Starlette via FastMCP)
- src/server.py lines 1-100 (tool registration pattern, 30+ tools here vs 27 in mcp_http.py)
- src/db.py lines 1-50 (database connection pattern)

## Key Architecture Facts
- MCP server uses `mcp[cli]>=1.26.0` (NOT standalone fastmcp)
- Framework: Starlette via FastMCP
- `mcp.server.auth` module ships complete OAuth 2.1: OAuthAuthorizationServerProvider protocol, auto-created routes, BearerAuthMiddleware
- FastMCP constructor accepts: `auth_server_provider=`, `token_verifier=`, `auth=AuthSettings(...)`
- Current state: BearerTokenMiddleware stopgap exists (from pre-sprint security fix). OAuth replaces it.
- Database: PostgreSQL via `DATABASE_URL` env var (same pgvector-db as web app)
- Container: `Dockerfile.mcp`, Python 3.11, runs `python -m src.mcp_http`

## DuckDB/Postgres Gotchas
- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use autocommit for DDL

## Agent 2A: OAuth 2.1 Server Implementation

### Provider Implementation
Create `src/oauth_provider.py` implementing `OAuthAuthorizationServerProvider` protocol from `mcp.server.auth.provider`:

8 async methods:
1. `get_client(client_id)` → lookup in `mcp_oauth_clients` table
2. `register_client(client_info)` → insert into `mcp_oauth_clients`, return OAuthClientInformationFull
3. `authorize(client, params)` → generate auth code, store in `mcp_oauth_codes`, return redirect URL with consent
4. `load_authorization_code(client, code)` → lookup in `mcp_oauth_codes`
5. `exchange_authorization_code(client, auth_code)` → swap code for access_token + refresh_token, store in `mcp_oauth_tokens`
6. `load_refresh_token(client, token)` → lookup in `mcp_oauth_tokens`
7. `exchange_refresh_token(client, token, scopes)` → rotate tokens
8. `load_access_token(token)` → verify bearer token, return AccessToken with scope info
9. `revoke_token(token)` → delete from `mcp_oauth_tokens`

### Token Model
Create `src/oauth_models.py`:
- Token generation: `secrets.token_urlsafe(32)` for all tokens
- Access token expiry: 1 hour
- Refresh token expiry: 30 days
- Auth code expiry: 10 minutes
- Scopes: `demo` (10 calls/day), `professional` (1000 calls/day), `unlimited`

### Database Tables
Add to `src/db.py` in a NEW section (do NOT modify existing beta_requests section — T1 owns that):

```sql
CREATE TABLE IF NOT EXISTS mcp_oauth_clients (
    client_id TEXT PRIMARY KEY,
    client_secret TEXT,
    redirect_uris TEXT[] NOT NULL DEFAULT '{}',
    client_name TEXT,
    scope TEXT DEFAULT 'demo',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_oauth_codes (
    code TEXT PRIMARY KEY,
    client_id TEXT NOT NULL REFERENCES mcp_oauth_clients(client_id),
    redirect_uri TEXT NOT NULL,
    scope TEXT DEFAULT 'demo',
    code_challenge TEXT,
    code_challenge_method TEXT DEFAULT 'S256',
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mcp_oauth_tokens (
    token TEXT PRIMARY KEY,
    token_type TEXT NOT NULL CHECK (token_type IN ('access', 'refresh')),
    client_id TEXT NOT NULL REFERENCES mcp_oauth_clients(client_id),
    scope TEXT DEFAULT 'demo',
    expires_at TIMESTAMP NOT NULL,
    refresh_token TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Add startup migration function that creates these tables (pattern: `CREATE TABLE IF NOT EXISTS`). Call it from `mcp_http.py` at startup.

### Consent Screen
Create a minimal HTML consent page served by the OAuth authorize endpoint:
- "sfpermits.ai wants to provide your AI assistant with San Francisco permit intelligence tools."
- Show requested scopes
- "Approve" button that completes the auth flow
- Obsidian dark theme (inline CSS, no template engine — this is Starlette, not Flask)

### Wire into FastMCP
In `src/mcp_http.py`:
- Remove the `BearerTokenMiddleware` class and related code (stopgap replaced by OAuth)
- Import `OAuthAuthorizationServerProvider` implementation from `src/oauth_provider`
- Import `AuthSettings` from `mcp.server.auth.settings`
- Add to FastMCP constructor:
```python
from src.oauth_provider import SFPermitsAuthProvider
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

provider = SFPermitsAuthProvider()

mcp = FastMCP(
    "SF Permits",
    auth_server_provider=provider,
    auth=AuthSettings(
        issuer_url="https://sfpermits-mcp-api-production.up.railway.app",
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=["demo", "professional", "unlimited"],
        ),
        revocation_options=RevocationOptions(enabled=True),
    ),
    # ... existing params
)
```
- Initialize DB tables at module load (call migration function)

### Files Owned
- NEW `src/oauth_provider.py`
- NEW `src/oauth_models.py`
- `src/mcp_http.py` (replace bearer token with OAuth)
- `src/db.py` (OAuth tables — NEW section at end, do NOT touch beta_requests section)

### Tests
Write tests in `tests/test_oauth.py`:
- Provider creates client via register_client
- Provider generates auth code via authorize
- Provider exchanges code for tokens
- Access token expires after 1 hour
- Invalid token returns None from load_access_token
- PKCE challenge verification works
- Token revocation works

---

## Agent 2B: Per-Token Rate Limiting + Response Size

### Rate Limiter
Create `src/mcp_rate_limiter.py`:
- In-memory rate limiting (dict of {token: {count, reset_time}})
- Tiers based on token scope:
  - No token / anonymous: 5 calls/day (by IP — extract from request)
  - `demo` scope: 10 calls/day
  - `professional` scope: 1,000 calls/day
  - `unlimited` scope: no limit
- Reset at midnight UTC
- Return `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` headers
- On exceeded: 429 response with message "Rate limit exceeded. Upgrade at https://sfpermits.ai/docs for more calls."

### Response Size Enforcement
Add response size check after each tool call:
- Estimate token count: `len(response_text) / 4` (rough approximation)
- If > 20,000 tokens: truncate with `\n\n[Response truncated. Use more specific filters to narrow results.]`
- This covers Anthropic's 25K token limit with buffer

### Integration with mcp_http.py
The rate limiter needs to hook into the request/response cycle. Options:
- If `mcp[cli]` provides middleware hooks, use them
- Otherwise, wrap each tool function with a rate-check decorator
- The access token info is available from the auth middleware context

Add rate limit headers to MCP responses via custom middleware or response wrapper.

### Files Owned
- NEW `src/mcp_rate_limiter.py`
- `src/mcp_http.py` (rate limit middleware integration — coordinate with 2A's OAuth changes)

### Tests
Write tests in `tests/test_mcp_rate_limit.py`:
- Demo scope: 10 calls allowed, 11th returns 429
- Anonymous: 5 calls allowed
- Professional: 1000 calls allowed
- Rate limit resets after window
- Response truncation at 20K tokens
- Rate limit headers present in response

---

## Agent 2C: Tool Description Audit + Missing Tools + Test Account

### Tool Description Audit
Review ALL tool docstrings in `src/tools/*.py` against Anthropic requirements:
- Each must say WHAT it does, WHEN to use it, WHAT it returns
- No overpromising
- Narrow, unambiguous language
- Fix any that are too vague or too verbose

### Tool Annotations
Add `readOnlyHint: True` to all tool registrations. Check if FastMCP's `mcp.tool()` accepts an `annotations` parameter, or if annotations are set via the tool function's metadata.

### Add 7 Missing Tools to mcp_http.py
These exist in `src/server.py` but are NOT in `src/mcp_http.py`:
1. `permit_severity` from `src/tools/permit_severity.py`
2. `property_health` from `src/tools/property_health.py`
3. `similar_projects` from `src/tools/similar_projects.py`
4. `predict_next_stations` from `src/tools/predict_next_stations.py`
5. `diagnose_stuck_permit` from `src/tools/diagnose_stuck_permit.py`
6. `simulate_what_if` from `src/tools/simulate_what_if.py`
7. `calculate_delay_cost` from `src/tools/calculate_delay_cost.py`

Import each and register with `mcp.tool()`. Update the tool count in health endpoint and instructions string.

### Security Hardening
- `run_query`: Add table allowlist. Only allow SELECT from permit-related tables: `permits`, `contacts`, `entities`, `relationships`, `inspections`, `timeline_stats`, `station_velocity_v2`, `complaints`, `violations`, `addenda_routing`. Block: `users`, `auth_tokens`, `feedback`, `watch_items`, `plan_analysis_sessions`, `plan_analysis_images`, `plan_analysis_jobs`, `beta_requests`, `mcp_oauth_clients`, `mcp_oauth_codes`, `mcp_oauth_tokens`, `pg_*`, `information_schema.*`.
- `read_source`: Remove `sprint-prompts/` and `CLAUDE.md` from Dockerfile.mcp readable paths. Add a path denylist in the tool: reject any path starting with `sprint-prompts/` or matching `CLAUDE.md`.
- `list_feedback`: Add a check that the caller has `professional` or `unlimited` scope (or is admin). Return "Insufficient permissions" for `demo` scope.

### Update Dockerfile.mcp
Remove lines that expose internal files:
```dockerfile
# REMOVE these lines:
COPY sprint-prompts/ /app/sprint-prompts/
COPY CLAUDE.md /app/CLAUDE.md
```

### Test Account
Create `scripts/create_qa_account.py`:
- Registers an OAuth client for Anthropic QA: `anthropic-qa-client`
- Pre-creates demo scope token
- Documents the client_id and a test token value
- Outputs setup instructions

Create `docs/MCP_TESTING.md`:
- How to connect as a QA reviewer
- 5 example prompts that demonstrate core functionality:
  1. "Look up permits at 487 Noe St" → permit_lookup
  2. "Is permit 202412237330 stuck?" → diagnose_stuck_permit
  3. "What's the timeline for an alteration permit in the Mission?" → estimate_timeline
  4. "Compare a $45K kitchen remodel vs a $185K full renovation" → simulate_what_if
  5. "Who are the top contractors in Noe Valley?" → recommend_consultants
- Expected response format for each

### Files Owned
- `src/server.py` (tool descriptions only — do NOT change tool registration pattern)
- `src/mcp_http.py` (7 new tool imports + registrations, tool count update)
- `src/tools/project_intel.py` (run_query table allowlist, read_source path denylist)
- `src/tools/list_feedback.py` (scope check)
- `Dockerfile.mcp` (remove sprint-prompts and CLAUDE.md COPY lines)
- NEW `scripts/create_qa_account.py`
- NEW `docs/MCP_TESTING.md`

### Tests
Write tests in `tests/test_tool_audit.py`:
- All 34 tool docstrings contain "Args:" and "Returns:"
- run_query blocks SELECT from users table
- run_query allows SELECT from permits table
- read_source blocks CLAUDE.md
- read_source blocks sprint-prompts/
- list_feedback returns error for demo scope

---

## Build Order
1. Agent 2A first (creates OAuth tables + provider, modifies mcp_http.py constructor)
2. Agent 2B + Agent 2C in parallel (2B adds rate limit middleware, 2C adds tools + security)

## T2 Merge Validation
- OAuth discovery: GET `/.well-known/oauth-authorization-server` returns metadata
- Dynamic registration: POST `/register` creates client
- Auth flow: GET `/authorize` → POST `/token` → receive access_token
- Authenticated tool call succeeds with valid token
- Unauthenticated tool call fails with 401
- Rate limiting enforces demo tier (10/day)
- All 34 tools registered (check health endpoint tool count)
- run_query blocks user tables
- Full test suite passes

## Commit + Push
```bash
git add -A && git commit -m "feat(qs13-t2): OAuth 2.1 + rate limiting + tool audit + security hardening"
git push origin HEAD
```
