# SF Permits MCP — QA Testing Guide

## Connection

**MCP URL**: `https://sfpermits-mcp-api-production.up.railway.app/mcp`

### Claude.ai Setup
1. Go to Settings > Integrations > Add MCP Server
2. Paste the MCP URL above
3. Complete the OAuth flow when prompted
4. Select scope: `demo` (10 calls/day) or `professional` (1,000 calls/day)

### OAuth Flow
1. **Discovery**: `GET /.well-known/oauth-authorization-server` — returns server metadata
2. **Register**: `POST /register` with client metadata — returns client_id + client_secret
3. **Authorize**: `GET /authorize?client_id=...&redirect_uri=...&code_challenge=...` — consent screen
4. **Token**: `POST /token` with code — returns access_token + refresh_token

## 5 Core Test Prompts

### 1. Property Permit Lookup
> "Look up permits at 487 Noe St, San Francisco"

**Expected tool**: `permit_lookup`
**Expected output**: List of permits at that address with permit numbers, types, status, costs

---

### 2. Stuck Permit Diagnosis
> "Is permit 202412237330 stuck? What's causing the delay?"

**Expected tool**: `diagnose_stuck_permit`
**Expected output**: Current station, days at station vs historical baseline, delay classification, recommended actions

---

### 3. Timeline Estimate
> "What's the typical timeline for an alteration permit in the Mission district?"

**Expected tool**: `estimate_timeline`
**Expected output**: P50/P75/P90 day ranges, station velocity breakdown, OTC vs in-house comparison

---

### 4. What-If Simulation
> "Compare a $45K kitchen remodel vs a $185K full renovation — which takes longer to permit?"

**Expected tool**: `simulate_what_if`
**Expected output**: Side-by-side timeline and fee comparison, permit path differences, recommendation

---

### 5. Consultant Recommendations
> "Who are the top contractors in Noe Valley for kitchen remodels?"

**Expected tool**: `recommend_consultants`
**Expected output**: Ranked list of contractors with permit counts, success rates, contact info

## Rate Limits

| Scope | Calls/Day | Use Case |
|-------|-----------|----------|
| `demo` | 10 | Evaluation, QA testing |
| `professional` | 1,000 | Daily expediter workflow |
| `unlimited` | — | Internal/admin use |

## Health Check

```bash
curl https://sfpermits-mcp-api-production.up.railway.app/health
```

Expected: `{"status": "healthy", "server": "SF Permits MCP", "tools": 34}`

## QA Account Setup

Run `python scripts/create_qa_account.py` with DATABASE_URL set to register the `anthropic-qa-client`.
