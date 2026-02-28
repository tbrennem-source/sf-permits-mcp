# QS10 T1: Visual QA Phase A — QA Pipeline Extensions

**Sprint:** QS10
**Terminal:** T1 — Visual QA Phase A
**Theme:** Extend existing QA scripts with structural diff, computed CSS checks, and vision gate
**Agents:** 3 (1A, 1B, 1C — run in parallel)
**Chief Task:** #378

---

## Terminal Overview

T1 extends three existing scripts. No new routes, no web/ changes, no templates.

| Agent | Script Owned | What Gets Added |
|---|---|---|
| 1A | `scripts/visual_qa.py` | `--structural` mode (DOM fingerprint, no pixel diff) |
| 1B | `scripts/design_lint.py` | `--live` mode (Playwright computed CSS + axe-core contrast) |
| 1C | `scripts/vision_score.py` | `--changed` flag + per-dimension scores; new `scripts/qa_gate.py` |

**File ownership is strict. Agents must NOT touch files outside their matrix.**

---

## Agent Rules (read before launching)

Every agent MUST follow these rules:

1. **Worktree**: You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run `git checkout main`. Do NOT run `git merge`. Your CWD is your isolated copy.
2. **No descoping**: If something is hard, attempt it. Do not skip it. Do not write "SKIP" in QA results. Flag actual blockers in CHECKQUAD.
3. **Early commit**: Commit after each major milestone (after tests pass, not just at the end). Use `git add -p` to stage only your owned files.
4. **Merge is T1's job**: Agents commit to their worktree branch. T1 merges all branches. Agents MUST NOT merge to main.
5. **Conflict prevention**: Only touch files in your ownership matrix. If you realize you need to touch a shared file, stop and note it in your CHECKQUAD output.
6. **Test command**: `source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short`
7. **Scenario file**: Append suggested scenarios to `scenarios-t1-sprint86.md` (create if missing, do NOT touch `scenarios-pending-review.md` directly).
8. **Changelog file**: Append your changes to `CHANGELOG-t1-sprint86.md` (create if missing).

---

## DuckDB / Postgres Gotchas

These scripts do not touch the DB directly, but if any test fixtures or helpers do:

- `INSERT OR REPLACE` → `ON CONFLICT DO UPDATE SET ...`
- `?` placeholders → `%s`
- `conn.execute()` → `cursor.execute()`
- Postgres transactions abort on any error — use `conn.autocommit = True` for DDL
- `duckdb.connect()` in tests must use a temp path, not the real DB file

---

## Agent 1A Prompt — Structural Diff (MODIFY scripts/visual_qa.py)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Add --structural mode to scripts/visual_qa.py

### Context
visual_qa.py is 1,023 lines. It has:
- PAGES list (21 pages with auth levels)
- VIEWPORTS dict (mobile/tablet/desktop)
- Playwright-based screenshot + pixel diff pipeline
- --capture-goldens, --update-goldens, --journeys, --guided flags
- _login_via_test_secret() for auth
- run_visual_qa() for page matrix
- run_journeys() for interactive flows
- main() CLI with argparse

### What to Add: --structural mode

Structural mode takes a DOM fingerprint of each page instead of a pixel diff.
It answers: "did the layout skeleton change?" — not "did pixels shift?"

**Fingerprint spec (per page):**
- CSS classes on <body> element (sorted list)
- CSS classes on the first detected grid/flex container (body > div, main, .obs-container, .obs-container-wide — first match)
- Count of elements with each class: .glass-card, .obs-table, nav, footer, .ghost-cta, form, .status-dot
- Presence of hx-get, hx-post, hx-target, hx-swap attributes (boolean each)
- Viewport overflow: document.documentElement.scrollWidth > window.innerWidth (boolean)
- Centering check: main content container offsetLeft > 20 (boolean — true = centered)

**What is NOT compared:** text content, data counts, timestamps, dynamic values.

**New CLI flags:**
- `--structural` — enables structural mode (mutually exclusive with pixel diff)
- `--structural-baseline` — capture fingerprints as baselines (saves to qa-results/structural-baselines/)
- `--structural-check` — compare fingerprints against baselines (default when --structural given without --structural-baseline)
- `--structural-changed-only` — only fingerprint pages whose templates appear in `git diff --name-only HEAD~1`
  - Map template names to page slugs using a TEMPLATE_TO_SLUG dict you define
  - Pages with no matching changed template are skipped

**Output format:**
- JSON report per page: `{"slug": ..., "pass": bool, "baseline": {...}, "current": {...}, "diffs": [...]}`
- Summary markdown written to `qa-results/qs10-structural-results.md`
- Baseline JSON files saved to `qa-results/structural-baselines/<slug>-<viewport>.json`

**Implementation approach:**
1. Add `run_structural_qa()` function (parallel to `run_visual_qa()`)
2. Add `capture_structural_baseline()` and `check_structural()` sub-functions
3. Add `get_page_fingerprint(page)` that runs JS via `page.evaluate()` to collect the fingerprint
4. Extend `main()` CLI with the new flags — keep existing flags working unchanged
5. Write results to `qa-results/qs10-structural-results.md`

### FILES YOU OWN
- MODIFY: scripts/visual_qa.py
- CREATE: qa-results/structural-baselines/ (directory — create via mkdir in code)
- CREATE: tests/test_visual_regression.py

### FILES YOU MUST NOT TOUCH
- web/app.py, src/server.py, web/routes_*.py
- scripts/design_lint.py (Agent 1B owns this)
- scripts/vision_score.py, scripts/qa_gate.py (Agent 1C owns these)
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_visual_regression.py)
Write pytest tests that do NOT require Playwright or a live server:
- Test `get_page_fingerprint` logic by mocking `page.evaluate()` return values
- Test structural diff comparison: given two fingerprints, verify diffs are detected correctly
- Test `--structural-changed-only` template-to-slug mapping: given a list of changed file paths, verify correct page slugs are selected
- Test that baseline save/load round-trips correctly (write to tmp_path, reload, compare)
- At least 8 tests total. All must pass with: source .venv/bin/activate && pytest tests/test_visual_regression.py -v

### Steps
1. Read scripts/visual_qa.py in full (1,023 lines) — understand existing patterns before adding
2. Add the structural mode implementation
3. Write tests/test_visual_regression.py
4. Run: source .venv/bin/activate && pytest tests/test_visual_regression.py -v
5. Run: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
   Fix any regressions. ALL existing tests must still pass.
6. Commit: git add scripts/visual_qa.py tests/test_visual_regression.py && git commit -m "feat(visual-qa): add --structural mode — DOM fingerprint diff"
7. Append to scenarios-t1-sprint86.md (create if missing) — 2-3 suggested scenarios for structural diff behavior
8. Append to CHANGELOG-t1-sprint86.md (create if missing) — one bullet per change

### CHECKQUAD output
Write a brief session summary to stdout when done:
- Files modified
- Tests added / passing
- Any blockers
```

---

## Agent 1B Prompt — Design Token Lint Live Mode (MODIFY scripts/design_lint.py)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Add --live flag to scripts/design_lint.py

### Context
design_lint.py is 404 lines. It has:
- 6 static checks: check_hex_colors, check_font_families, check_inline_styles,
  check_tertiary_misuse, check_missing_csrf, check_rgba_colors
- ALLOWED_HEX set, ALLOWED_RGBA_PATTERNS list, TOKEN_CLASSES set
- lint_file() runs all checks on a single file
- score() maps violations to 1-5
- format_report() writes markdown
- main() CLI with --files, --changed, --output, --quiet flags
- Default mode: static analysis of HTML/CSS source files (no browser)

### What to Add: --live flag

`--live` launches Playwright headless Chromium and checks computed CSS on rendered pages.
Existing static checks (--files, --changed, no flag) are UNCHANGED.

**New checks in --live mode:**

1. **Computed color compliance**: For each CSS custom property in ALLOWED_TOKENS_VARS
   (a new dict you define mapping var name → expected hex), check `getComputedStyle(el).color`
   and `getComputedStyle(el).backgroundColor` on representative elements.
   Flag if computed color is more than ±2 RGB per channel from expected.

2. **Computed font compliance**: Check `getComputedStyle(el).fontFamily` on:
   - `.obs-table` elements → must resolve to monospace (contains "mono", "Courier", "Consolas", or similar)
   - `p, .insight__body` elements → must resolve to sans-serif (contains "sans", "Inter", "system-ui", or similar)
   Flag violations as medium severity.

3. **axe-core WCAG AA contrast**: Inject axe-core via CDN (`page.add_script_tag(url=...)`),
   run `axe.run({runOnly: ['color-contrast']})`, collect violations.
   Report each violation as high severity with the element selector and contrast ratio.
   Use axe-core CDN: `https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js`

4. **Viewport overflow check**: `document.documentElement.scrollWidth > window.innerWidth`
   Report as medium severity if true (horizontal scroll = layout breakage).

**Pages to check in --live mode:**
Use the same PAGES list pattern as visual_qa.py. For --live, only check public pages
(auth="public") to avoid needing TEST_LOGIN_SECRET as a hard dependency.
If TEST_LOGIN_SECRET env var is set, also check auth pages.

**--live flag behavior:**
- Requires --url argument (base URL, e.g. https://staging.example.com)
- Runs static checks first (existing behavior), then appends live results
- Combined score considers both static and live violations
- Output goes to qa-results/design-lint-live-results.md (separate from static output)

**Implementation approach:**
1. Add `run_live_checks(base_url, pages, test_secret)` function
2. Add `check_computed_colors(page, url)`, `check_computed_fonts(page, url)`,
   `check_axe_contrast(page, url)`, `check_viewport_overflow(page, url)` sub-functions
3. Extend `main()` — add `--live` and `--url` args; keep all existing args working
4. Import playwright inside the function (conditional import — only needed for --live)

### Read first
Read docs/DESIGN_TOKENS.md to understand the token palette and variable names before
defining ALLOWED_TOKENS_VARS. Map at minimum: --accent, --signal-green, --signal-amber,
--signal-red, --bg-primary, --text-primary, --text-secondary.

### FILES YOU OWN
- MODIFY: scripts/design_lint.py
- CREATE: tests/test_design_token_lint.py
- READ ONLY: docs/DESIGN_TOKENS.md

### FILES YOU MUST NOT TOUCH
- scripts/visual_qa.py (Agent 1A owns this)
- scripts/vision_score.py, scripts/qa_gate.py (Agent 1C owns these)
- web/app.py, src/server.py, web/routes_*.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_design_token_lint.py)
Write pytest tests that do NOT require Playwright or a live server:
- Test all 6 existing checks still produce correct violations on fixture HTML strings
- Test the new ALLOWED_TOKENS_VARS dict is populated (at least 5 entries)
- Test computed color compliance logic: given a mocked computed color value,
  verify the ±2 RGB tolerance check works correctly
- Test axe violation parsing: given a mock axe result dict, verify violations are
  extracted and formatted as high-severity lint violations correctly
- Test viewport overflow flagging: given scrollWidth > innerWidth, verify medium violation produced
- At least 10 tests total. All must pass.

### Steps
1. Read docs/DESIGN_TOKENS.md (to understand token vars before coding)
2. Read scripts/design_lint.py in full (404 lines)
3. Add --live mode implementation
4. Write tests/test_design_token_lint.py
5. Run: source .venv/bin/activate && pytest tests/test_design_token_lint.py -v
6. Run: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
   Fix any regressions. ALL existing tests must still pass.
7. Commit: git add scripts/design_lint.py tests/test_design_token_lint.py && git commit -m "feat(design-lint): add --live mode — computed CSS + axe-core contrast checks"
8. Append to scenarios-t1-sprint86.md (create if missing) — 2-3 suggested scenarios
9. Append to CHANGELOG-t1-sprint86.md (create if missing) — one bullet per change

### CHECKQUAD output
Write a brief session summary to stdout when done:
- Files modified
- Tests added / passing
- Any blockers
```

---

## Agent 1C Prompt — Vision Scoring + Merge Gate (MODIFY scripts/vision_score.py + CREATE scripts/qa_gate.py)

```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

## YOUR TASK: Extend scripts/vision_score.py and create scripts/qa_gate.py

### Context — vision_score.py (106 lines)
vision_score.py currently:
- Sends screenshots to Claude Vision (claude-sonnet-4-5-20250929) with an 8-dimension rubric
- Returns JSON: {"score": N, "checks": {centering, nav, cards, typography, spacing,
  search_bar, recent_items, action_links}, "summary": "..."}
- When run as __main__: scores screenshots in qa-results/screenshots/dashboard-loop/
- score_screenshot(image_path, label) is the main function

### Part 1: Extend vision_score.py with --changed flag

Add a CLI mode to vision_score.py that:
1. Runs `git diff --name-only HEAD~1 -- web/templates/ web/static/` to find changed files
2. Maps changed template filenames to page slugs using a TEMPLATE_TO_PAGE dict
   (build this by cross-referencing the PAGES list pattern from visual_qa.py —
   define it inline in vision_score.py, covering all 21 pages)
3. Takes a screenshot of each matched page using Playwright headless Chromium
   (use TEST_LOGIN_SECRET env var for auth, same pattern as visual_qa.py's _login_via_test_secret)
4. Scores each screenshot with score_screenshot()
5. Returns per-dimension scores (not just overall) — the existing rubric already has 8 checks;
   expose them in the output
6. Pages scoring < 3.0 overall: append to qa-results/pending-reviews.json
   Format: {"page": slug, "url": ..., "score": N, "checks": {...}, "screenshot": ..., "timestamp": ...}
   If the file exists, append to the list; if not, create it.
7. Print a summary table: page | score | dimensions passing | action

**New CLI flags for vision_score.py:**
- `--changed` — run against git-changed pages (requires --url)
- `--url` — base URL (e.g. https://sfpermits-ai-staging-production.up.railway.app)
- `--sprint` — sprint label for screenshot filenames (e.g. qs10)
- `--output` — path for per-run JSON results (default: qa-results/vision-scores-latest.json)

Keep existing __main__ behavior working (no flags = scores dashboard-loop screenshots).

### Part 2: Create scripts/qa_gate.py

qa_gate.py is a merge gate script. It orchestrates the other two scripts and exits non-zero on failure.

**What it does:**
1. Runs: `python scripts/visual_qa.py --structural --structural-check --url <url> --sprint <sprint>`
   Parses the output JSON for pass/fail. Fails if any page fails structural check.
2. Runs: `python scripts/design_lint.py --live --url <url> --changed --quiet`
   Parses the score from stdout ("Token lint: N/5"). Fails if score <= 2.
3. Collects results from both, writes a summary to qa-results/qa-gate-results.md
4. Exits 0 if both pass, exits 1 if either fails (with clear error messages to stderr)

**CLI for qa_gate.py:**
```
python scripts/qa_gate.py --url https://... --sprint qs10
```
Optional: `--skip-structural`, `--skip-lint` to bypass individual checks during development.

**qa-results/pending-reviews.json schema:**
```json
[
  {
    "page": "landing",
    "url": "https://...",
    "score": 2.5,
    "checks": {"centering": {"pass": true, "fix": null}, ...},
    "screenshot": "qa-results/screenshots/qs10/landing-desktop.png",
    "timestamp": "2026-02-28T12:00:00Z"
  }
]
```
Initialize as empty list [] if file does not exist.

### FILES YOU OWN
- MODIFY: scripts/vision_score.py
- CREATE: scripts/qa_gate.py
- CREATE: qa-results/pending-reviews.json (initialize as [])
- CREATE: tests/test_vision_qa.py

### FILES YOU MUST NOT TOUCH
- scripts/visual_qa.py (Agent 1A owns this)
- scripts/design_lint.py (Agent 1B owns this)
- web/app.py, src/server.py, web/routes_*.py
- CLAUDE.md, CHANGELOG.md, scenarios-pending-review.md

### Tests (tests/test_vision_qa.py)
Write pytest tests that do NOT require Playwright or the Anthropic API:
- Test TEMPLATE_TO_PAGE dict: verify all 21 page slugs from PAGES are covered
- Test pending-reviews.json append logic: given a mock result with score < 3.0,
  verify it is appended; given score >= 3.0, verify it is not appended
- Test pending-reviews.json initialization: if file doesn't exist, verify [] is written first
- Test qa_gate.py subprocess invocation logic (mock subprocess.run, verify args passed correctly)
- Test qa_gate.py exit code: mock both checks passing → exit 0; one failing → exit 1
- Test per-dimension score extraction from Vision API response JSON
- At least 10 tests total. All must pass.

### Steps
1. Read scripts/vision_score.py in full (106 lines)
2. Add --changed flag and per-dimension output to vision_score.py
3. Create scripts/qa_gate.py
4. Initialize qa-results/pending-reviews.json as []
5. Write tests/test_vision_qa.py
6. Run: source .venv/bin/activate && pytest tests/test_vision_qa.py -v
7. Run: source .venv/bin/activate && pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
   Fix any regressions. ALL existing tests must still pass.
8. Commit:
   git add scripts/vision_score.py scripts/qa_gate.py qa-results/pending-reviews.json tests/test_vision_qa.py
   git commit -m "feat(vision-qa): add --changed flag, per-dimension scores, qa_gate.py merge gate"
9. Append to scenarios-t1-sprint86.md (create if missing) — 2-3 suggested scenarios
10. Append to CHANGELOG-t1-sprint86.md (create if missing) — one bullet per change

### CHECKQUAD output
Write a brief session summary to stdout when done:
- Files modified / created
- Tests added / passing
- Any blockers
```

---

## Spawn All 3 Agents

Paste this into a fresh CC terminal (T1). The terminal spawns all 3 agents in parallel via Task tool.

```python
# Run these Task calls in parallel (all 3 at once)

Task(
    subagent_type="general-purpose",
    model="sonnet",
    isolation="worktree",
    prompt="<Agent 1A prompt from above>"
)

Task(
    subagent_type="general-purpose",
    model="sonnet",
    isolation="worktree",
    prompt="<Agent 1B prompt from above>"
)

Task(
    subagent_type="general-purpose",
    model="sonnet",
    isolation="worktree",
    prompt="<Agent 1C prompt from above>"
)
```

Expected runtime: 20-30 minutes for all 3 agents.

---

## Post-Agent: Merge and Push

After all 3 agents complete, T1 runs the merge ceremony from the **main repo root**.

```bash
# Step 0: Escape any worktree CWD
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git status  # confirm on main branch

# Step 1: Identify agent branches
git worktree list
# Note the branch names for all 3 worktrees (e.g. claude/sharp-xyz, claude/brave-abc, claude/quiet-def)

# Step 2: Merge in dependency order — 1A first (visual_qa.py), then 1B, then 1C
git merge claude/<1A-branch> --no-ff -m "merge: agent-1A structural diff mode"
git merge claude/<1B-branch> --no-ff -m "merge: agent-1B design lint --live mode"
git merge claude/<1C-branch> --no-ff -m "merge: agent-1C vision --changed + qa_gate.py"

# If conflicts arise (should not happen with clean file ownership):
# git checkout HEAD -- <conflicted-file>  # keep main version
# git add <conflicted-file> && git merge --continue

# Step 3: Consolidate per-terminal output files
# Concatenate scenario and changelog files from agents into the terminal files
cat scenarios-t1-sprint86.md  # review, then append to scenarios-pending-review.md manually
cat CHANGELOG-t1-sprint86.md  # review, then incorporate into CHANGELOG.md

# Step 4: Run full test suite ONCE
source .venv/bin/activate
pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/e2e --tb=short
# ALL tests must pass. If failures: bisect by reverting last merge, re-testing.

# Step 5: Run design lint on changed files
python scripts/design_lint.py --changed --quiet
# T1 only touches scripts/ and tests/ — no templates changed. Score should be N/A or 5/5.

# Step 6: Push to main
git push origin main

# Step 7: Confirm
git log --oneline -5
echo "T1 push complete"
```

---

## CHECKQUAD (T1 Session Close)

T1 uses CHECKQUAD (lighter than CHECKCHAT — delegates documentation and shipping to T0).

### Step 0: Escape CWD

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git status  # must be on main, clean
```

### Step 1: MERGE

Merge all agent branches. Run tests once. Push to main. (See Post-Agent section above.)

### Step 2: ARTIFACT

Write `qa-results/t1-sprint86-session.md` with:
- Agent outcomes (1A/1B/1C): PASS / PARTIAL / BLOCKED
- Files modified (list)
- New tests added (count per agent)
- Test suite result (N passed, N failed)
- Design lint score
- Any blockers (BLOCKED-FIXABLE or BLOCKED-EXTERNAL with classification)

### Step 3: CAPTURE

- Verify `scenarios-t1-sprint86.md` exists with entries from all 3 agents
- Verify `CHANGELOG-t1-sprint86.md` exists with entries from all 3 agents
- Do NOT touch `scenarios-pending-review.md` or `CHANGELOG.md` directly — T0 consolidates

### Step 4: HYGIENE CHECK

```bash
# Verify no stale worktrees
git worktree list
git worktree prune

# Verify no uncommitted changes on main
git status

# Verify push succeeded
git log --oneline -3
```

### Step 5: SIGNAL DONE

Output this exact block so T0 can parse it:

```
T1 DONE
Agents: 1A=<PASS|PARTIAL|BLOCKED>, 1B=<PASS|PARTIAL|BLOCKED>, 1C=<PASS|PARTIAL|BLOCKED>
Tests: <N> new tests, <N> passing, <N> failing
Files: scripts/visual_qa.py, scripts/design_lint.py, scripts/vision_score.py, scripts/qa_gate.py, tests/test_visual_regression.py, tests/test_design_token_lint.py, tests/test_vision_qa.py, qa-results/pending-reviews.json
Lint: <N>/5
Branch: pushed to main at <commit hash>
Blockers: <NONE | description with BLOCKED-FIXABLE or BLOCKED-EXTERNAL classification>
```

---

## File Ownership Matrix (reference)

| File | Agent | Action |
|---|---|---|
| `scripts/visual_qa.py` | 1A | MODIFY |
| `qa-results/structural-baselines/` | 1A | CREATE |
| `tests/test_visual_regression.py` | 1A | CREATE |
| `scripts/design_lint.py` | 1B | MODIFY |
| `tests/test_design_token_lint.py` | 1B | CREATE |
| `docs/DESIGN_TOKENS.md` | 1B | READ ONLY |
| `scripts/vision_score.py` | 1C | MODIFY |
| `scripts/qa_gate.py` | 1C | CREATE |
| `qa-results/pending-reviews.json` | 1C | CREATE |
| `tests/test_vision_qa.py` | 1C | CREATE |
| `scenarios-t1-sprint86.md` | All (append) | PER-AGENT OUTPUT |
| `CHANGELOG-t1-sprint86.md` | All (append) | PER-AGENT OUTPUT |

**DO NOT TOUCH (any agent):**
- `web/app.py`
- `src/server.py`
- `web/routes_*.py`
- `CLAUDE.md`
- `CHANGELOG.md` (use `CHANGELOG-t1-sprint86.md` instead)
- `scenarios-pending-review.md` (use `scenarios-t1-sprint86.md` instead)
