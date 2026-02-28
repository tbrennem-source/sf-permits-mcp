## Sprint QS10 — T3 Agent 3D: Share Mechanic for Intelligence Tool Pages

### Added
- `web/templates/components/share_button.html` — reusable share button component (Jinja2 include)
- `web/static/js/share.js` — Web Share API on mobile, clipboard copy on desktop, textarea execCommand fallback for older browsers
- `web/static/css/share.css` — share button styles using only DESIGN_TOKENS.md CSS custom properties (5/5 lint score)
- `web/templates/tools/entity_network.html` — new Entity Network tool page (full tool UI with share button)
- `web/templates/tools/revision_risk.html` — new Revision Risk tool page (full tool UI with share button)
- `web/routes_search.py` — added `/tools/entity-network` and `/tools/revision-risk` routes
- `web/routes_api.py` — added `/api/share` POST endpoint (placeholder for future shareable-link persistence)
- `tests/test_share_mechanic.py` — 30 tests covering component existence, CSS token compliance, all 6 tool page inclusions, and API endpoints (30/30 passing)
- `docs/DESIGN_COMPONENT_LOG.md` — logged share-container + share-btn as new component

### Modified
- `web/templates/tools/station_predictor.html` — added share button include + share.js/share.css links
- `web/templates/tools/stuck_permit.html` — added share button include + share.js/share.css links
- `web/templates/tools/what_if.html` — added share button include + share.js/share.css links
- `web/templates/tools/cost_of_delay.html` — added share button include + share.js/share.css links

### Test results
- 30/30 new tests pass
- 3,919 passing / 4 skipped in full suite (no regressions)
- Design lint: 5/5 for all agent-owned files
