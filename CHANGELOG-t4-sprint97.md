
## Sprint 97 — Agent 4C: /demo/guided self-guided walkthrough

**Branch:** worktree-agent-ad1e33c8
**Commit:** bf94307

### Added
- `GET /demo/guided` — new public route registered on `misc` Blueprint (`web/routes_misc.py`)
- `web/templates/demo_guided.html` — 6-section self-guided stakeholder walkthrough page using full Obsidian design token system
  - Section 1: Hero ("See what sfpermits.ai does")
  - Section 2: Gantt / station tracker explanation with link to `/tools/station-predictor`
  - Section 3: Pre-filled search block (`/search?q=487+Noe+St`)
  - Section 4: 4 intelligence tool cards (stuck-permit, what-if, revision-risk, cost-of-delay) with demo query params
  - Section 5: Amy professional workflow bullets (morning triage, reviewer lookup, intervention playbooks)
  - Section 6: MCP/AI connect block with Learn more link to `/methodology`
- `tests/test_demo_guided.py` — 20 passing tests covering all 6 sections, tool link params, auth behavior, template base

### Design Token Compliance
- Score: 5/5 — clean (zero violations per `design_lint.py`)
- No inline colors outside DESIGN_TOKENS.md palette
- Font roles correct: `--sans` for prose/headings, `--mono` for data values and CTAs
- Uses `glass-card` and `ghost-cta` token components throughout
