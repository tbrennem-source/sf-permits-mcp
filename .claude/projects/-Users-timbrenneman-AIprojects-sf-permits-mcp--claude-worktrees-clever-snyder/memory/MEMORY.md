# Memory

## User Preferences

- **Always update docs on commit**: When committing changes to the repo, update all relevant project documentation and status docs before or alongside the commit. See [docs-checklist.md](docs-checklist.md) for the full list.
- **QA checklist after commit**: After committing, always present the user with a concise QA test list covering user-facing behavior, edge cases, and things automated tests can't cover (visual, UX, mobile, cross-browser).
- **Pytest path**: Use `/Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/pytest` (system python doesn't have pytest)

## Project Conventions

- All inline styles, no static CSS files — Flask has no `static/` folder
- DuckDB (dev) + PostgreSQL (prod) dual-mode — all DB functions must handle both
- Railway deploy with ephemeral filesystem — no persistent file storage
- html2canvas loaded lazily, not on page load
