# QS7 Terminal 4: Tests + Hardening + Docs

> Paste this into CC Terminal 4. It spawns 4 agents via Task tool.
> **Merge order: Terminal 4 merges LAST** (after Terminals 1+2+3).
> Tests are written against interface specs — they validate T1-T3's work.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
source .venv/bin/activate
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --timeout=30 2>&1 | tail -3
```

## File Ownership (Terminal 4 ONLY touches these)

| Agent | Files |
|---|---|
| 4A | `scripts/component_goldens.py` (NEW) |
| 4B | `tests/test_page_cache.py` (NEW), `tests/test_brief_cache.py` (NEW) |
| 4C | `tests/test_design_lint_integration.py` (NEW), `tests/test_prod_gate.py` (NEW) |
| 4D | `docs/BLACKBOX_PROTOCOL.md`, `scenarios-pending-review-qs7-4d.md` (per-agent isolation), `docs/DESIGN_MIGRATION.md` |

**No production code.** Terminal 4 writes tests, scripts, and docs. If a test fails after merge, it means T1-T3 didn't match the spec — the test is correct, the implementation needs a fix.

## Launch All 4 Agents (FOREGROUND, parallel)

---

### Agent 4A: Component Golden Test Script

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Build scripts/component_goldens.py (Task #354)

### Read First
- docs/DESIGN_TOKENS.md (full file — you need every component's HTML)
- web/static/mockups/obsidian-tokens.css (reference CSS)
- scripts/design_lint.py (reference for script patterns in this project)
- scripts/visual_qa.py (reference for Playwright patterns)

### Build

Create `scripts/component_goldens.py` that:

1. Generates a minimal HTML page for each token component using the HTML from DESIGN_TOKENS.md
2. Loads obsidian.css (or falls back to the mockup CSS)
3. Renders each component in isolation using Playwright headless Chromium
4. Screenshots each component at desktop width (1280px)
5. Stores as golden baselines in `qa-results/component-goldens/`
6. In diff mode (--diff), compares current render against stored goldens using pixel comparison

**Component list (26):**
glass-card, search-input, ghost-cta, action-btn, status-dot (3 colors), chip, data-row, stat-counter, progress-bar, dropdown, section-divider, skeleton (3 variants), obs-table, form-input, form-check, form-toggle, form-select, form-upload, toast (3 variants), modal, insight (4 colors), expandable, risk-flag, action-prompt, tabs, load-more

**Usage:**
```bash
python scripts/component_goldens.py --capture   # Generate golden baselines
python scripts/component_goldens.py --diff       # Compare against goldens
python scripts/component_goldens.py --component glass-card  # Single component
```

**Structure:**
```python
COMPONENTS = {
    "glass-card": {
        "html": '<div class="glass-card"><h3>Card Title</h3><p>Content</p></div>',
        "width": 400,
        "height": 200,
    },
    # ... for each of the 26 components
}
```

For each component, use the exact HTML snippet from DESIGN_TOKENS.md. Set a dark background (#0a0a0f) on the body so components render on the correct background.

**Diff mode:** Use simple pixel comparison. If >2% of pixels differ, flag as CHANGED. Output a markdown report listing UNCHANGED / CHANGED / NEW for each component.

### Test
```bash
source .venv/bin/activate
python scripts/component_goldens.py --capture --component glass-card
# Should produce qa-results/component-goldens/glass-card.png
```

### Commit
`feat: component golden test script — 26 components, capture + diff modes`
""")
```

---

### Agent 4B: Page Cache + Brief Cache Tests

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Write tests for the page_cache infrastructure (Task #349)

### Read First
- web/helpers.py (the cache utility — Agent 1A is building get_cached_or_compute and invalidate_cache)
- web/routes_misc.py (the /brief route — Agent 1B is adding cache integration)
- web/routes_cron.py (Agent 1C is adding /cron/compute-caches)
- tests/ (browse existing test patterns — look at conftest.py, test_routes*.py)

### Build

**Create tests/test_page_cache.py:**

Test the cache utility functions (write against the spec, not the implementation):

```python
def test_cache_miss_computes_and_stores():
    # First call with empty cache should call compute_fn
    # Second call should return cached result without calling compute_fn

def test_cache_hit_returns_cached():
    # Pre-populate cache, verify compute_fn not called

def test_cache_ttl_expiry():
    # Set TTL to 0, verify cache miss on second call

def test_invalidate_cache_marks_stale():
    # Populate cache, invalidate, verify next read triggers compute

def test_invalidate_cache_pattern():
    # Populate "brief:user1:1" and "brief:user2:1"
    # Invalidate "brief:user1:%"
    # Verify user1 invalidated, user2 still cached

def test_cache_stores_json_serializable():
    # Verify dicts with dates, numbers, nested structures round-trip correctly

def test_cache_metadata_fields():
    # Verify _cached=True and _cached_at set on cache hits
```

**Create tests/test_brief_cache.py:**

Test the /brief route's cache integration:

```python
def test_brief_serves_from_cache(client, logged_in_user):
    # Hit /brief twice, verify second request is faster (or mock to verify compute called once)

def test_brief_refresh_invalidates_cache(client, logged_in_user):
    # POST /brief/refresh, then GET /brief — should recompute

def test_brief_refresh_rate_limited(client, logged_in_user):
    # POST /brief/refresh twice quickly — second should return 429

def test_cron_compute_caches(client, monkeypatch):
    # POST /cron/compute-caches with valid auth
    # Verify response includes computed count
    monkeypatch.setenv("CRON_WORKER", "1")
```

Use the existing test patterns from the codebase — check conftest.py for fixtures (client, logged_in_user, monkeypatch patterns).

**IMPORTANT:** These tests should work against both DuckDB (local) and the test patterns in the existing suite. Use `monkeypatch.setenv("TESTING", "1")` if needed. Use `monkeypatch.setenv("CRON_WORKER", "1")` for cron endpoint tests.

### Test
```bash
source .venv/bin/activate
pytest tests/test_page_cache.py tests/test_brief_cache.py -v --tb=short 2>&1 | tail -20
# These will FAIL until Terminal 1's code is merged — that's expected.
# The tests define the correct behavior. Terminal 1's code must make them pass.
```

### Commit
`test: page_cache utility + brief cache integration tests`
""")
```

---

### Agent 4C: Design Lint + Prod Gate Tests

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Write tests for design_lint.py and prod_gate.py

### Read First
- scripts/design_lint.py (the token lint script)
- scripts/prod_gate.py (the prod gate with weighted scoring)
- tests/ (existing test patterns)

### Build

**Create tests/test_design_lint_integration.py:**

```python
import tempfile, os

def test_clean_template_scores_5():
    # Write a minimal template using only token classes/colors
    # Run lint on it, verify score 5

def test_non_token_hex_detected():
    # Write a template with #ff0000 (not in palette)
    # Verify violation detected with correct line number

def test_non_token_font_detected():
    # Write a template with font-family: Arial
    # Verify high severity violation

def test_tertiary_on_interactive_detected():
    # Write a template with <a> using --text-tertiary
    # Verify violation detected

def test_inline_style_color_detected():
    # Write a template with style="color: red"
    # Verify violation detected

def test_token_vars_allowed():
    # Write a template using var(--accent), var(--text-primary)
    # Verify NO violations

def test_svg_hex_not_flagged():
    # Write a template with SVG stroke="#fff"
    # Verify NOT flagged (SVGs are allowed)

def test_changed_mode_no_templates():
    # Run --changed when no templates changed
    # Verify clean output
```

**Create tests/test_prod_gate.py:**

```python
def test_weighted_scoring_perfect():
    # All categories raw 5 → effective 5

def test_weighted_scoring_design_dampened():
    # Design raw 2, everything else 5 → effective 3 (not 2)

def test_weighted_scoring_safety_not_dampened():
    # Safety raw 2, everything else 5 → effective 2 (HOLD)

def test_weighted_scoring_floor():
    # Design raw 2 → effective max(3.2, 2.0) = 3.2 → rounds to 3

def test_hard_hold_overrides_score():
    # Auth bypass with all other scores at 5 → still HOLD

def test_hotfix_ratchet_first_time():
    # Score 3 → PROMOTE, writes HOTFIX_REQUIRED.md

def test_hotfix_ratchet_second_time():
    # Score 3 with existing HOTFIX_REQUIRED.md → HOLD

def test_hotfix_cleanup_on_improvement():
    # Score 5 with existing HOTFIX_REQUIRED.md → file deleted
```

Test the scoring math by importing the functions directly and passing mock data, not by running the full script.

### Test
```bash
source .venv/bin/activate
pytest tests/test_design_lint_integration.py tests/test_prod_gate.py -v --tb=short 2>&1 | tail -20
```

### Commit
`test: design lint + prod gate weighted scoring tests`
""")
```

---

### Agent 4D: Docs + Scenario Drain

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Update Black Box Protocol docs + drain pending scenarios

### Read First
- docs/BLACKBOX_PROTOCOL.md (or BLACKBOX_PROTOCOL.md in repo root — find it)
- CLAUDE.md section "12. Session Protocols"
- docs/DESIGN_MIGRATION.md
- scenarios-pending-review.md (93 pending scenarios)
- scenario-design-guide.md (approved scenarios — understand the format)

### Build

**1. Update BLACKBOX_PROTOCOL.md:**

In the Stage 1 (termCC) section, update the visual review step:

OLD: Visual QA via scripts/visual_qa.py (21 pages × 3 viewports)
NEW:
- **Phase 6.5a (mechanical — every sprint):** `python scripts/design_lint.py --changed --quiet` — <5 seconds, no browser. Reports token compliance score 1-5.
- **Phase 6.5b (visual — only for changed templates):** Targeted Playwright screenshots of modified templates only. Compare against component goldens if available.
- **Phase 6.5c (full sweep — every 5 sprints):** `python scripts/visual_qa.py` full 21×3 mode for regression baseline.

In the post-merge section, add:
- `python scripts/prod_gate.py --quiet` — unified promotion gate, determines PROMOTE or HOLD

**2. Update docs/DESIGN_MIGRATION.md:**

Add a status section tracking which templates have been migrated:

| Template | Violations (pre) | Violations (post) | Sprint | Agent |
|----------|------------------|--------------------|--------|-------|
| landing.html | 15 | — | QS7 | 2B |
| search_results_public.html | 25 | — | QS7 | 2B |
| results.html | 54 | — | QS7 | 2C |
| report.html | 46 | — | QS7 | 3B |
| brief.html | 35 | — | QS7 | 3A |
| portfolio.html | 18 | — | QS7 | 3C |
| index.html | (tbd) | — | QS7 | 3C |
| auth_login.html | (tbd) | — | QS7 | 3D |
| error.html | (tbd) | — | QS7 | 2D |

The "post" column gets filled after the sprint when lint scores are verified.

**3. Drain 25 pending scenarios:**

Read scenarios-pending-review.md. For each scenario, categorize it:
- If it matches an existing scenario in scenario-design-guide.md → mark as DUPLICATE, remove
- If it's clearly valid → leave as PENDING REVIEW (Tim approves)
- If it's too implementation-specific (references routes, CSS classes, specific UI elements) → rewrite to be outcome-focused per the scenario durability spectrum

Write your categorization to `scenarios-pending-review-qs7-4d.md` (per-agent file to avoid merge conflicts with the main file). Include:
- KEPT: N scenarios (valid, left as pending)
- DUPLICATES: N scenarios (removed, listed with the scenario they duplicate)
- REWRITTEN: N scenarios (made more durable, show before/after)

Target: process 25 of the 93 pending scenarios.

### Commit
`docs: update Black Box Protocol for design lint + drain 25 scenarios`
""")
```

---

## Post-Agent: Merge

After all 4 agents complete, **wait for Terminals 1+2+3 to merge first**, then:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull  # Pick up Terminal 1+2+3 merges

git merge <agent-4a-branch>  # Component goldens script
git merge <agent-4b-branch>  # Cache tests
git merge <agent-4c-branch>  # Lint + gate tests
git merge <agent-4d-branch>  # Docs + scenarios

# Run ALL tests (validates T1-T3 against T4's test specs):
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --timeout=30
# Fix any failures (likely interface mismatches between spec and implementation)

# Run prod gate:
python scripts/prod_gate.py --skip-tests --quiet
# (skip-tests because we just ran them manually)

git push origin main
```

## Final: Cross-Terminal Report

After all 4 terminals merged:

```
QS7 COMPLETE — Beta Readiness Sprint
============================================

Terminal 1 (Speed):
  1A page_cache infrastructure: [PASS/FAIL]
  1B /brief cache integration:  [PASS/FAIL]
  1C cron pre-compute:          [PASS/FAIL]
  1D cache headers + gate v2:   [PASS/FAIL]

Terminal 2 (Public Templates):
  2A obsidian.css:              [PASS/FAIL] lint: [N/5]
  2B landing + search:          [PASS/FAIL] lint: [N/5]
  2C results + content:         [PASS/FAIL] lint: [N/5]
  2D nav + errors:              [PASS/FAIL] lint: [N/5]

Terminal 3 (Auth Templates):
  3A brief + cache UI:          [PASS/FAIL] lint: [N/5]
  3B property report:           [PASS/FAIL] lint: [N/5]
  3C portfolio + index:         [PASS/FAIL] lint: [N/5]
  3D auth + toast + fragments:  [PASS/FAIL] lint: [N/5]

Terminal 4 (Testing):
  4A component goldens:         [PASS/FAIL]
  4B cache tests:               [N passed / M failed]
  4C lint + gate tests:         [N passed / M failed]
  4D docs + scenarios:          [N scenarios processed]

Tests: [total passed / failed]
Prod gate: [PROMOTE/HOLD] ([N/5])
Design lint (core 6): [N/5]
```
