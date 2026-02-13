# SF Permits MCP Server

MCP server that exposes San Francisco public permitting data to Claude. Built with [FastMCP](https://github.com/jlowin/fastmcp) and the [Socrata SODA API](https://dev.socrata.com/).

Phase 1 of a larger project that will add fraud detection (social network analysis of permit actors) and permit facilitation.

## Tools

| Tool | Description |
|------|-------------|
| `search_permits` | Search building permits by neighborhood, type, status, cost, date, address, or description |
| `get_permit_details` | Get full details for a specific permit by permit number |
| `permit_stats` | Aggregate statistics grouped by neighborhood, type, status, month, or year |
| `search_businesses` | Search registered business locations in SF |
| `property_lookup` | Look up property assessments by address or block/lot |

## Data Sources

All data from [DataSF](https://data.sfgov.org/) (San Francisco Open Data) via the Socrata SODA API. 22 datasets cataloged covering:

- **Permits**: Building (1.3M), Plumbing (513K), Electrical (344K), Boiler (152K), Street-Use (1.2M)
- **Contacts**: Building Permits Contacts (1M records, 11 actor types), Electrical Contacts (340K), Plumbing Contacts (503K)
- **Violations**: Building Inspections (671K), DBI Complaints (326K), Notices of Violation (509K)
- **Enrichment**: Business Locations (354K), Property Tax Rolls (3.7M), Development Pipeline, Housing Production

See [`datasets/CATALOG.md`](datasets/CATALOG.md) for the full catalog and [`docs/contact-data-report.md`](docs/contact-data-report.md) for the contact/actor data analysis.

## Setup

```bash
# Clone
git clone https://github.com/tbrennem-source/sf-permits-mcp.git
cd sf-permits-mcp

# Install dependencies
pip install -e ".[dev]"

# Optional: set SODA app token for higher rate limits
export SODA_APP_TOKEN="your_token_here"

# Run the MCP server
python -m src.server
```

## Architecture

```
Claude (claude.ai / Claude Code)
    ↓ MCP tool call
SF Permits MCP Server (FastMCP)
    ↓ HTTP GET (SoQL)
data.sfgov.org SODA API
    ↓ JSON response
MCP Server formats + returns
    ↓ structured results
Claude renders for user
```

### Key Files

```
src/
├── server.py           # FastMCP entry point, tool registration
├── soda_client.py      # Async SODA API client (httpx)
├── formatters.py       # Response formatting for Claude consumption
└── tools/
    ├── search_permits.py
    ├── get_permit_details.py
    ├── permit_stats.py
    ├── search_businesses.py
    └── property_lookup.py
```

## Tests

```bash
# Run integration tests (hits live API)
pytest tests/ -v
```

## Performance

Benchmarks run against the live SODA API (see [`benchmarks/RESULTS.md`](benchmarks/RESULTS.md)):

- **Single lookups**: ~500ms
- **Filtered searches**: ~600-720ms
- **Aggregations**: ~600ms warm cache, 10-14s cold cache on large datasets
- **Full-text search**: ~600ms-1.4s (most datasets)

The API is sufficient for interactive use. Aggregation results should be cached for production.

## Project Phases

- [x] **Phase 1**: MCP server + dataset catalog + benchmarks ← *you are here*
- [ ] **Phase 2**: Local storage decision, contacts data ingestion
- [ ] **Phase 3**: Fraud detection prototype (social network analysis using Mehri model)
- [ ] **Phase 4**: Predictive analytics, Railway deployment

## Decisions

See [`docs/DECISIONS.md`](docs/DECISIONS.md) for architecture decisions including:
- Why we built from scratch vs. forking existing Socrata MCP servers
- Custom SODA client vs. sodapy
- NIXPACKS deployment strategy
