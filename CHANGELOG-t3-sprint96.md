# QS12 T3 Sprint Changelog

## Agent 3A: Tool Page Public Access
- Removed auth redirect (`if not g.user: return redirect("/auth/login")`) from 4 routes in `web/routes_search.py`: `/tools/station-predictor`, `/tools/stuck-permit`, `/tools/what-if`, `/tools/cost-of-delay`
- Added anonymous soft CTA to 4 tool templates (`station_predictor.html`, `stuck_permit.html`, `what_if.html`, `cost_of_delay.html`) — gated with `{% if not g.user %}`, links to `/beta/join`, uses design token classes (`ghost-cta`, `--obsidian-mid`, `--glass-border`, `--text-tertiary`)
- Updated 9 existing tests across 4 test files that asserted 301/302 redirects for anonymous users — changed to assert 200 (`test_station_predictor_ui.py`, `test_stuck_permit_ui.py`, `test_what_if_ui.py`, `test_cost_of_delay_ui.py`, `test_tools_polish_a.py`, `test_tools_polish_b.py`)
- Created `tests/test_tool_public_access.py` with 24 tests covering: 6 routes × 200 for anonymous users, no redirect assertions, content rendering, soft CTA presence, anon gating, and authed user regression
- Design lint: 5/5 (zero violations across 4 changed templates)
