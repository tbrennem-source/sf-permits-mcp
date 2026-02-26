# QA: QS3-D Analytics + Revenue Polish

## Setup
```
cd /Users/timbrenneman/AIprojects/sf-permits-mcp/.claude/worktrees/qs3-d
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
```

## Tests

1. **posthog import safe without API key** — `python -c "from web.helpers import posthog_track; posthog_track('test')"` exits cleanly — PASS/FAIL
2. **landing.html source contains async PostHog script** — `grep -c 'posthog.init' web/templates/landing.html` returns >= 1 — PASS/FAIL
3. **landing.html source contains `<link rel="manifest">`** — `grep -c 'rel="manifest"' web/templates/landing.html` returns >= 1 — PASS/FAIL
4. **index.html source contains `<link rel="manifest">`** — `grep -c 'rel="manifest"' web/templates/index.html` returns >= 1 — PASS/FAIL
5. **GET /static/manifest.json returns valid JSON** — start Flask, GET /static/manifest.json, parse as JSON, has "name" key — PASS/FAIL
6. **api_usage CREATE TABLE in release.py** — `grep -c 'CREATE TABLE IF NOT EXISTS api_usage' scripts/release.py` returns >= 1 — PASS/FAIL
7. **/sitemap.xml does not contain /demo** — start Flask, GET /sitemap.xml, assert "/demo" not in body — PASS/FAIL
8. **docs/charis-invite.md contains friends-gridcare** — `grep -c 'friends-gridcare' docs/charis-invite.md` returns >= 1 — PASS/FAIL
9. **Screenshot landing page at 1440px** — Playwright, viewport 1440x900, screenshot, no layout breakage — PASS/FAIL
