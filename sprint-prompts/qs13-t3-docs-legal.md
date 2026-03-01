> EXECUTE IMMEDIATELY. You are a build terminal in a quad sprint. Read the tasks below and execute them sequentially. Do NOT summarize or ask for confirmation — execute now.

# QS13 T3 — Docs + Legal + Directory Package (Sprint 100)

You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
If you modify any file in web/templates/ or web/static/, read docs/DESIGN_TOKENS.md first.
Use ONLY token components and CSS custom properties. Log new components to docs/DESIGN_COMPONENT_LOG.md.
CRITICAL: NEVER run git checkout main or git merge. Commit to YOUR branch only.

## Read First
- CLAUDE.md (project rules)
- docs/DESIGN_TOKENS.md (for template styling)
- src/server.py (all tool registrations + docstrings)
- src/mcp_http.py (MCP server structure — will have OAuth after T2)
- web/routes_misc.py (where new routes go)
- web/templates/methodology.html (existing content page for style reference)

## Agent 3A: /docs API Documentation Page

### Tool Introspection
Create `web/docs_generator.py`:
- Function that reads tool metadata from the MCP server (or directly from tool function docstrings)
- Organize tools into 7 categories:
  - **Search & Lookup** (7): search_permits, permit_lookup, get_permit_details, search_businesses, property_lookup, search_entity, search_addenda
  - **Analytics** (3): permit_stats, search_inspections, search_complaints
  - **Intelligence** (7): estimate_timeline, estimate_fees, predict_permits, revision_risk, recommend_consultants, required_documents, search_violations
  - **Advanced** (4): diagnose_stuck_permit, simulate_what_if, calculate_delay_cost, predict_next_stations
  - **Plan Analysis** (2): validate_plans, analyze_plans
  - **Network** (3): entity_network, network_anomalies, similar_projects
  - **System** (4): run_query, schema_info, read_source, list_tests
- For each tool, extract: name, description, parameters (name, type, required, description), return type

### Template
Create `web/templates/docs.html`:
- Obsidian dark theme
- Hero: "sfpermits.ai API — San Francisco Permit Intelligence"
- Quick start section: "Connect via Claude.ai" (3 steps)
  1. Go to Settings → Integrations → Add custom connector
  2. Enter URL: `https://sfpermits-mcp-api-production.up.railway.app/mcp`
  3. Authorize via OAuth (auto-prompted)
- Tool catalog: 7 category sections, each with tool cards
- Each tool card: name, description, parameters table, example query
- Rate limits section: tier table (demo 10/day, professional 1000/day, unlimited)
- Authentication section: OAuth 2.1 flow description
- Links to /privacy and /terms

### Route
Add to `web/routes_misc.py`:
- `GET /docs` → renders `docs.html` with tool data from `docs_generator.py`
- No auth required (public page)

### Files Owned
- NEW `web/docs_generator.py`
- NEW `web/templates/docs.html`
- `web/routes_misc.py` (new /docs route — append at end, do NOT modify existing routes)

### Tests
Write tests in `tests/test_docs_page.py`:
- /docs returns 200
- /docs contains all 7 category names
- /docs lists at least 30 tools
- docs_generator returns dict with expected structure

---

## Agent 3B: Privacy Policy + Terms Pages

### Privacy Policy
Create `web/templates/privacy.html`:
- Obsidian dark theme, clean typography
- Last updated date
- Sections:
  - **What We Collect**: permit search queries, email addresses (beta signups), usage analytics (PostHog), uploaded PDFs (plan analysis — processed in memory, not stored)
  - **How We Use It**: service delivery, search improvement, analytics, beta access management
  - **What We Don't Do**: sell data, share PII with third parties, store uploaded plans permanently
  - **Data Sources**: all permit data from public SF government sources (data.sfgov.org), updated nightly
  - **Third Parties**: PostHog (analytics), Railway (hosting), Anthropic (AI processing via Claude API), SendGrid (email)
  - **Data Retention**: search queries logged 90 days for service improvement, email addresses kept until account deletion
  - **Your Rights**: request data deletion by emailing tim@sfpermits.ai, unsubscribe from emails via link in footer
  - **MCP Server**: when connected via Claude.ai, tool calls are processed by our server and responses returned to your Claude conversation. We log tool call metadata (endpoint, timestamp) but not conversation content.
  - **Cookies**: session cookie (authentication), PostHog analytics cookie (optional)
  - **Contact**: tim@sfpermits.ai

### Terms of Service
Create `web/templates/terms.html`:
- Obsidian dark theme
- Sections:
  - **Beta Status**: sfpermits.ai is in beta. Features may change. Data accuracy is best-effort.
  - **Data Accuracy**: we aggregate public government data from data.sfgov.org. This is NOT legal advice. Permit timelines are estimates based on historical data. Always verify with DBI directly for critical decisions.
  - **Acceptable Use**: do not scrape, do not use for automated bulk queries, do not attempt to access other users' data
  - **Rate Limits**: enforced per account tier. Exceeding limits results in temporary throttling, not account termination.
  - **Account Termination**: we may suspend accounts that violate acceptable use. Email tim@sfpermits.ai to appeal.
  - **Intellectual Property**: permit data is public record. Our analysis, intelligence tools, and presentation are proprietary.
  - **Limitation of Liability**: standard beta limitation — no warranties, use at your own risk
  - **Changes**: we'll email registered users about significant changes to terms

### Routes
Add to `web/routes_misc.py`:
- `GET /privacy` → renders `privacy.html`
- `GET /terms` → renders `terms.html`
- No auth required (public pages)

### Files Owned
- NEW `web/templates/privacy.html`
- NEW `web/templates/terms.html`
- `web/routes_misc.py` (new routes — append at end)

### Tests
Write tests in `tests/test_legal_pages.py`:
- /privacy returns 200
- /privacy contains "Privacy" in title
- /terms returns 200
- /terms contains "Terms" in title
- Both pages are accessible without login

---

## Agent 3C: Directory Submission Package + Readiness QA

### Submission Document
Create `docs/DIRECTORY_SUBMISSION.md`:
- Pre-filled responses for every Anthropic connector directory form field:
  - **Server Name**: sfpermits — San Francisco Permit Intelligence
  - **Server URL**: `https://sfpermits-mcp-api-production.up.railway.app/mcp`
  - **Description**: "AI-powered San Francisco building permit intelligence. Track permits through review stations, diagnose stuck permits, predict timelines, assess revision risk, find contractors, and estimate fees. Built on 18M+ public government records updated nightly from 22 city data sources."
  - **Documentation URL**: `https://sfpermits.ai/docs`
  - **Privacy Policy URL**: `https://sfpermits.ai/privacy`
  - **Terms URL**: `https://sfpermits.ai/terms`
  - **Category**: Government / Real Estate / Construction
  - **Authentication**: OAuth 2.1 with PKCE, dynamic client registration
  - **Test Account**: reference docs/MCP_TESTING.md (created by T2 Agent 2C)
  - **Example Prompts**: 5 prompts from MCP_TESTING.md
  - **Tool Count**: 34
  - **Data Sources**: San Francisco Open Data (data.sfgov.org) — 22 SODA datasets, 13.3M records
  - **Update Frequency**: Nightly
  - **Rate Limits**: Demo (10/day), Professional (1000/day)

### Readiness QA Script
Create `scripts/qa_directory_readiness.py`:
Automated checklist that verifies:
1. MCP server responds at URL
2. `/.well-known/oauth-authorization-server` returns valid JSON
3. Dynamic client registration works (POST /register)
4. OAuth flow completes (register → authorize → token)
5. Authenticated tool call succeeds
6. Unauthenticated tool call fails (401)
7. Rate limiting returns 429 after threshold
8. All tools respond (call each with minimal params, check for non-error response)
9. No tool response exceeds 25K tokens
10. /docs page accessible (200)
11. /privacy page accessible (200)
12. /terms page accessible (200)
13. Health endpoint returns tool count matching actual registrations
14. Error messages are user-friendly (no stack traces)

Output: PASS/FAIL checklist with details for any failures.

Note: This script tests the LIVE deployed server, not local. It needs to run after T1+T2+T3 are deployed. Include a `--local` flag for testing against localhost:8001.

### Files Owned
- NEW `docs/DIRECTORY_SUBMISSION.md`
- NEW `scripts/qa_directory_readiness.py`

### Tests
Write tests in `tests/test_directory_package.py`:
- DIRECTORY_SUBMISSION.md exists and contains required fields
- qa_directory_readiness.py is importable
- MCP_TESTING.md exists (created by T2)

---

## Build Order
1. Agent 3A + Agent 3B in parallel (independent templates + routes)
2. Agent 3C after both (needs /docs and /privacy to exist for readiness checks)

## T3 Merge Validation
- /docs renders with 34 tools across 7 categories
- /privacy and /terms render with content
- DIRECTORY_SUBMISSION.md has all fields
- Full test suite passes

## Commit + Push
```bash
git add -A && git commit -m "feat(qs13-t3): /docs API page + privacy/terms + directory submission package"
git push origin HEAD
```
