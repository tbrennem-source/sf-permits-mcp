# Anthropic MCP Connector Directory — Submission Package

> Pre-filled responses for the Anthropic connector directory submission form.
> Last updated: 2026-02-28

---

## Submission Fields

### Server Name
```
sfpermits — San Francisco Permit Intelligence
```

### Server URL
```
https://sfpermits-mcp-api-production.up.railway.app/mcp
```

### Short Description (≤ 160 chars)
```
AI-powered San Francisco building permit intelligence. Track permits, predict timelines, assess revision risk, find contractors, and estimate fees.
```

### Long Description
```
AI-powered San Francisco building permit intelligence. Track permits through review stations, diagnose stuck permits, predict timelines, assess revision risk, find contractors, and estimate fees. Built on 18M+ public government records updated nightly from 22 city data sources.

34 tools organized across 7 categories:
- Search & Lookup: search permits, look up properties and businesses, search entities and addenda routing records
- Analytics: permit statistics, inspections, complaints, violations, severity scoring, property health
- Intelligence: estimate timelines and fees, predict required permits, assess revision risk, get contractor recommendations, generate document checklists
- Advanced: diagnose stuck permits, run what-if simulations, calculate delay costs, predict next review stations
- Plan Analysis: validate PDF plan sets against DBI EPR requirements, AI vision analysis of architectural drawings
- Network: entity relationship networks, anomaly detection, similar project discovery
- System: read-only SQL queries, schema introspection, source code access, test inventory

All permit data sourced from the San Francisco Open Data Portal (data.sfgov.org) — public government records, updated nightly. The service is built for permit expediters, architects, contractors, and property owners navigating San Francisco's complex permitting system.
```

### Documentation URL
```
https://sfpermits.ai/docs
```

### Privacy Policy URL
```
https://sfpermits.ai/privacy
```

### Terms of Service URL
```
https://sfpermits.ai/terms
```

### Category
```
Government / Real Estate / Construction
```

### Authentication Method
```
OAuth 2.1 with PKCE, dynamic client registration (RFC 7591)
```

### Test Account
See `docs/MCP_TESTING.md` for test credentials, example tool calls, and expected responses.

### Example Prompts (5)
1. "What permits are currently open at 123 Main Street in San Francisco?"
2. "How long will a $500K kitchen remodel permit take in Noe Valley, and what are the fees?"
3. "My permit 202301015555 has been at SFFD review for 6 weeks — what's wrong and what should I do?"
4. "Find the top architects for historic building work in Pacific Heights"
5. "What permits do I need to convert my garage to an ADU in SF?"

### Tool Count
```
34
```

### Data Sources
```
San Francisco Open Data Portal (data.sfgov.org) — 22 SODA datasets, 13.3M+ records including:
- SF Building Permits (1.1M+ records)
- DBI Inspections (671K+ records)
- DBI Complaints
- DBI Notices of Violation
- Registered Business Locations
- Assessor/Recorder parcel data
- Plan review addenda routing (3.9M+ records)
```

### Update Frequency
```
Nightly — automated pipeline pulls from SODA API and refreshes local database
```

### Rate Limits
```
Demo (unauthenticated): 10 calls/day
Professional (OAuth): 1,000 calls/day
Unlimited (admin): unrestricted
```

---

## Technical Details (for reviewer reference)

### MCP Protocol
- Transport: Streamable HTTP (SSE-based)
- Protocol version: 2024-11-05
- Authentication: OAuth 2.1 + PKCE + dynamic client registration
- Package: `mcp[cli]>=1.26.0` (Anthropic's official package)

### Endpoints
| Endpoint | Purpose |
|---|---|
| `GET /health` | Health check, returns tool count and DB status |
| `GET /.well-known/oauth-authorization-server` | OAuth discovery metadata |
| `POST /register` | Dynamic client registration |
| `GET /authorize` | OAuth authorization page |
| `POST /token` | Token exchange |
| `GET /mcp` / `POST /mcp` | MCP protocol (SSE + POST) |

### Infrastructure
- Hosting: Railway (sfpermits-mcp-api service)
- Database: PostgreSQL + pgvector (internal Railway network)
- Runtime: Python 3.11, FastMCP + Flask
- Dockerfile: `Dockerfile.mcp`

### Health Check
```bash
curl https://sfpermits-mcp-api-production.up.railway.app/health
```

Expected response:
```json
{
  "status": "ok",
  "tools": 34,
  "db": "connected"
}
```

---

## Readiness Checklist

Run `scripts/qa_directory_readiness.py` to verify all items before submission:

- [ ] MCP server responds at the server URL
- [ ] OAuth discovery endpoint returns valid JSON
- [ ] Dynamic client registration works
- [ ] OAuth flow completes (register → authorize → token)
- [ ] Authenticated tool call succeeds
- [ ] Unauthenticated tool call fails (401)
- [ ] Rate limiting returns 429 after threshold
- [ ] /docs page accessible (200)
- [ ] /privacy page accessible (200)
- [ ] /terms page accessible (200)
- [ ] Health endpoint returns correct tool count
- [ ] No tool response exposes stack traces

---

## Contact

- Operator: Tim Brenneman
- Email: tim@sfpermits.ai
- Website: https://sfpermits.ai
