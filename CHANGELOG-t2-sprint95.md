# CHANGELOG — T2 Sprint 95 (Tool UX Polish)

## Agent: T2 — entity_network, revision_risk, what_if, cost_of_delay polish

### Critical Fix: revision_risk.html — missing style block
The revision_risk.html template was rendering broken because the entire `<style nonce="{{ csp_nonce }}">` opening tag was absent. CSS was floating as bare text after the `<link>` tag, causing the page to render with all CSS as visible text. Fixed by rewriting the template with a proper `<head>` structure.

### revision_risk.html — full UX rebuild
- **Redesigned input**: Changed from `permit-number-input` (permit number lookup) to `permit-type` select + optional neighborhood/project_type/review_path fields — matching the actual `revision_risk()` MCP tool signature
- **?permit_type= pre-fill**: URL param auto-fills select and triggers analysis
- **Two-column layout**: Sticky left form, right results panel (matches cost_of_delay.html pattern)
- **Loading skeleton**: 3-row skeleton while analysis is in flight
- **Empty state**: Centered state with demo link (?permit_type=alterations&neighborhood=Mission)
- **SVG risk gauge**: Half-circle arc SVG with stroke-dasharray animation; arc color = red (HIGH) / amber (MODERATE) / green (LOW); percentage label inside arc; risk level text and explanatory sub-text
- **Risk extraction**: JS parses markdown for `**HIGH**`, `**MODERATE**`, `**LOW**` keywords + percentage fallback
- **Graceful 404**: If /api/revision-risk returns 404, shows helpful message suggesting What-If Simulator
- **Lint**: 5/5 — zero token violations

### entity_network.html — UX improvements
- **?address= pre-fill**: Reads `?address=` or `?q=` URL params, auto-populates input, auto-runs analysis with 400ms delay
- **Loading skeleton**: Separate loading-area div with skeleton rows (was previously hidden inside results)
- **Empty state**: Dedicated `empty-state` div with icon, title, description, and demo link (?address=Smith+Construction)
- **Network graph visualization**: Parsed from markdown response — center node badge, connection rows with dot indicators, shared permit counts, entity types; hidden until results arrive
- **Network stats row**: 3 stat cards (Connected entities, Relationships, Hops) above connections
- **Proper loading state management**: setLoading() controls all elements (skeleton, empty state, spinner, button)
- **Lint**: 5/5 — zero token violations

### what_if.html — verified complete
- Demo pre-fill (?demo=kitchen-vs-full) works correctly with auto-run
- Loading skeleton present with 4 skeleton rows
- Empty state guides user with demo suggestion
- Comparison table has `.diff-better` (--signal-green) and `.diff-worse` (--signal-red) column indicators
- No changes needed

### cost_of_delay.html — verified complete
- Demo pre-fill (?demo=restaurant-15k) works correctly with auto-run
- Loading skeleton with 4 rows
- Empty state with demo suggestion
- Percentile table with row-likely highlight
- No changes needed

### Tests
- Created `tests/test_tool_ux_remaining.py`: 82 new tests covering entity_network and revision_risk templates and routes
  - Style block presence and nonce compliance
  - URL param pre-fill assertions
  - Loading state, empty state, demo link checks
  - SVG gauge elements, risk level text
  - Network graph elements, connection rows, stat cards
  - Token compliance (no hardcoded hex, --mono/--sans usage)
  - CSRF, admin scripts, feedback widget
- Updated `tests/test_tools_new.py`: 7 assertions updated to match new designs (entity-network results id, revision-risk form inputs)

### Lint
```
Token lint: 5/5 (0 violations across 2 files)
```
