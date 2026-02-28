<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs3-a-permit-prep.md and execute it" -->

# Quad Sprint 3 — Session A: Permit Prep Phase 1

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs3-a
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs3-a before any code changes.
```

## SETUP — Session Bootstrap

1. **Navigate to main repo root:**
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main:**
   ```
   git checkout main && git pull origin main
   ```
3. **Create worktree:**
   Use EnterWorktree with name `qs3-a`

If worktree exists: `git worktree remove .claude/worktrees/qs3-a --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs3-a`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `web/routes_api.py` — where you'll add prep API endpoints
3. `web/routes_property.py` — where you'll add /prep route
4. `web/routes_auth.py` — where you'll add /account/prep
5. `web/brief.py` — morning brief data assembly (you'll add prep summary)
6. `web/helpers.py` — decorators, run_async, shared utilities
7. `src/tools/predict_permits.py` — permit prediction (seeds checklists)
8. `src/tools/required_documents.py` — document checklist generation (seeds checklists)
9. `web/templates/search_results_public.html` — where you'll add Prep button
10. `web/templates/fragments/intel_preview.html` — where you'll add Prep link
11. `web/templates/fragments/nav.html` — where you'll add nav item
12. `scripts/release.py` — where you'll add DDL
13. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes from pre-flight audit:**
- Templates are SELF-CONTAINED (no base.html, no Jinja inheritance, inline Obsidian CSS vars)
- All route files exist from Blueprint refactor
- NOTHING exists for Permit Prep — no tables, no routes, no templates, no module. Full build.
- Feature flag coordination: Session D creates PostHog flag `permit_prep_enabled`. Your templates should check `permit_prep_enabled` as a template variable (default: True if variable not set). Do NOT import PostHog.

---

## PHASE 2: BUILD

### Task A-1: Data Model + API (~90 min)
**Files:** `web/permit_prep.py` (NEW), `web/routes_api.py` (append), `scripts/release.py` (append DDL)

**Create `web/permit_prep.py`:**

```python
# Core functions:
def create_checklist(permit_number, user_id, conn):
    """Generate checklist from predict_permits + required_documents output."""
    # 1. Look up permit type and description from permits table
    # 2. Call predict_permits to get required forms and review path
    # 3. Call required_documents to get document list
    # 4. Insert prep_checklists row
    # 5. Insert prep_items rows (one per document)
    # 6. Return checklist_id

def get_checklist(permit_number, user_id, conn):
    """Return checklist with all items for a permit."""

def update_item_status(item_id, new_status, user_id, conn):
    """Update a single item's status. Validate ownership."""

def get_user_checklists(user_id, conn):
    """Return all checklists for a user with progress summary."""

def preview_checklist(permit_number, conn):
    """Generate predicted checklist without saving — for Preview Mode."""
```

**Add DDL to `scripts/release.py`** (append after existing DDL):
```sql
CREATE TABLE IF NOT EXISTS prep_checklists (
    checklist_id SERIAL PRIMARY KEY,
    permit_number TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_prep_checklists_user ON prep_checklists(user_id);
CREATE INDEX IF NOT EXISTS idx_prep_checklists_permit ON prep_checklists(permit_number);

CREATE TABLE IF NOT EXISTS prep_items (
    item_id SERIAL PRIMARY KEY,
    checklist_id INTEGER NOT NULL REFERENCES prep_checklists(checklist_id),
    document_name TEXT NOT NULL,
    category TEXT NOT NULL,  -- plans, forms, supplemental, agency
    status TEXT NOT NULL DEFAULT 'required',  -- required, submitted, verified, waived, n_a
    source TEXT NOT NULL DEFAULT 'predicted',  -- predicted, manual
    notes TEXT,
    due_date TEXT
);
CREATE INDEX IF NOT EXISTS idx_prep_items_checklist ON prep_items(checklist_id);
```

**Add API endpoints to `web/routes_api.py`:**
- `POST /api/prep/create` — requires auth, creates checklist
- `GET /api/prep/<permit_number>` — requires auth, returns checklist JSON
- `PATCH /api/prep/item/<item_id>` — requires auth, updates item status (HTMX-friendly: return updated item fragment)
- `GET /api/prep/preview/<permit_number>` — requires auth, returns preview without saving

### Task A-2: Permit Prep UI (~60 min)
**Files:** `web/templates/permit_prep.html` (NEW), `web/templates/fragments/prep_checklist.html` (NEW), `web/templates/fragments/prep_progress.html` (NEW), `web/routes_property.py` (append), `web/static/style.css` (prep styles)

**Create `/prep/<permit_number>` route in `web/routes_property.py`:**
- Requires login
- If checklist exists for this user+permit, render it
- If no checklist exists, auto-create one (POST to /api/prep/create internally)
- Render `permit_prep.html`

**Create `web/templates/permit_prep.html`:**
- Self-contained template with inline Obsidian CSS vars (same pattern as other templates)
- Google Fonts import (JetBrains Mono + IBM Plex Sans)
- Header with logo + nav
- Progress bar at top: "7 of 12 items addressed" with colored fill
- Categorized sections: Required Plans, Application Forms, Supplemental Documents, Agency-Specific
- Each item: document name, status toggle (radio buttons: Required/Submitted/Verified), source badge, notes field
- Status toggles use HTMX: `hx-patch="/api/prep/item/{item_id}"` with `hx-swap="outerHTML"` to update item in-place
- "What's still needed" summary card (list of required items not yet submitted)
- Print button: `window.print()` with print stylesheet
- Mobile: single column, large tap targets (48px), full-width items

**Create HTMX fragments:**
- `prep_checklist.html` — renders a single category section (used for HTMX partial updates)
- `prep_progress.html` — renders just the progress bar (used after item status change)

**Add print styles to `web/static/style.css`:**
```css
@media print {
    .prep-page { background: white; color: black; }
    .prep-page .nav, .prep-page .header { display: none; }
    .prep-page .status-toggle { border: 1px solid #ccc; }
}
```

### Task A-3: Integration Points (~45 min)
**Files:** `web/templates/search_results_public.html` (add button), `web/templates/fragments/intel_preview.html` (add link), `web/brief.py` (prep summary), `web/templates/fragments/nav.html` (nav item), `web/templates/account_prep.html` (NEW), `web/routes_auth.py` (append)

**Search results + intel preview:** Add a "Prep Checklist" button/link next to each permit in search results. Links to `/prep/<permit_number>`. For anonymous users, links to login with redirect back to /prep.

**Morning brief:** In `web/brief.py`, add a `_get_prep_summary(user_id, conn)` function:
- Query prep_checklists for this user
- Count items by status per checklist
- Return: list of {permit_number, total_items, completed_items, missing_required}
- Include in brief data as `prep_summary`

**Nav:** Add "Permit Prep" to authenticated nav in `web/templates/fragments/nav.html`. Link to `/account/prep`.

**Account prep dashboard:** Create `web/templates/account_prep.html`:
- Lists all user's active checklists with progress bars
- Links to individual /prep/<permit_number> pages
- "Start new checklist" button (search for permit)

**Route:** Add `/account/prep` to `web/routes_auth.py`, requires login.

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write `tests/test_qs3_a_permit_prep.py`:
- prep_checklists DDL creates table (mock DB)
- create_checklist returns checklist_id with items
- get_checklist returns items grouped by category
- update_item_status changes status correctly
- update_item_status rejects invalid status values
- update_item_status rejects wrong user (ownership check)
- preview_checklist returns items without saving to DB
- get_user_checklists returns summary with progress
- POST /api/prep/create returns 201 with checklist_id (auth required)
- POST /api/prep/create returns 401 for anonymous
- GET /api/prep/<permit> returns JSON with items
- PATCH /api/prep/item/<id> returns updated item HTML
- GET /api/prep/preview/<permit> returns preview JSON
- /prep/<permit> renders with categories and progress bar
- /prep/<permit> requires authentication
- /account/prep renders checklist list
- Search results contain "Prep Checklist" link
- Nav contains "Permit Prep" for authenticated users
- Brief includes prep_summary data
- Print stylesheet exists for prep page

**Target: 40+ tests**

Run pytest after EACH task (A-1, A-2, A-3).

---

## PHASE 4: SCENARIOS

Read `scenario-design-guide.md`. No existing scenarios for Permit Prep — all are NEW.

Append 5 scenarios to `scenarios-pending-review.md`:
1. "User creates Permit Prep checklist for an existing permit and sees categorized document requirements"
2. "User toggles document status from Required to Submitted and progress bar updates"
3. "Preview Mode shows predicted checklist for a permit without saving"
4. "Morning brief shows permits with incomplete checklists"
5. "Anonymous user clicking Prep Checklist is redirected to login then back to /prep"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs3-a-permit-prep-qa.md`:

```
Scenarios covered: [none — all new, pending review]

1. [NEW] POST /api/prep/create with valid permit — 201 response — PASS/FAIL
2. [NEW] GET /prep/<permit_number> renders checklist with 4 categories — PASS/FAIL
3. [NEW] PATCH /api/prep/item/<id> toggles status, HTMX returns fragment — PASS/FAIL
4. [NEW] Progress bar shows correct count after status change — PASS/FAIL
5. [NEW] Screenshot /prep at 375px — no horizontal scroll, touch targets ≥48px — PASS/FAIL
6. [NEW] Screenshot /prep at 768px — PASS/FAIL
7. [NEW] Screenshot /prep at 1440px — PASS/FAIL
8. [NEW] Print stylesheet removes nav and header — PASS/FAIL
9. [NEW] Authenticated nav shows "Permit Prep" link — PASS/FAIL
10. [NEW] Anonymous GET /prep redirects to login — PASS/FAIL
11. [NEW] /account/prep lists active checklists with progress — PASS/FAIL
```

Save screenshots to `qa-results/screenshots/qs3-a/`
Write results to `qa-results/qs3-a-results.md`

Run QA. Fix FAILs. Loop until PASS or BLOCKED.

---

## PHASE 5.5: VISUAL REVIEW

Score these pages 1-5 (1=broken, 2=poor, 3=acceptable, 4=good, 5=impressive):
- /prep/<permit_number> at 375px, 768px, 1440px
- /account/prep at 1440px

Use `scripts/visual_qa.py` if available, or send screenshots to Vision.
≥3.0 average = PASS. ≤2.0 on any page = ESCALATE to DeskRelay.

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions
- Re-read scenario-design-guide.md — confirm no existing scenarios contradicted

### 2. DOCUMENT
- Update CHANGELOG.md with QS3-A entry
- Update STATUS.md if accessible

### 3. CAPTURE
- 5 scenarios appended to scenarios-pending-review.md

### 4. SHIP
- Commit with: "feat: Permit Prep Phase 1 — data model, UI, integration points"
- Report: files created, test count, QA results

### 5. PREP NEXT
- Note: Session D will create PostHog feature flag `permit_prep_enabled`
- Note: Manifest link tag needs adding to permit_prep.html if not done

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 3-4 hours | [first commit to CHECKCHAT] |
| New tests | 40+ | [count] |
| Total tests | ~3,470 | [pytest output] |
| Tasks completed | 3 | [N of 3] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task name, duration] |
| QA checks | 11 | [pass/fail/skip] |
| Visual Review avg | — | [score or N/A] |
| Scenarios proposed | 5 | [count] |
```

### DeskRelay HANDOFF
- [ ] Permit Prep page: does the categorized checklist feel professional?
- [ ] Status toggles: are they intuitive? Do colors communicate state clearly?
- [ ] Progress bar: does it update smoothly via HTMX?
- [ ] Mobile: usable at a permit counter on a phone?
- [ ] Print view: clean enough to hand to a plan checker?

---

## File Ownership (Session A ONLY)
**Own:**
- `web/permit_prep.py` (NEW)
- `web/templates/permit_prep.html` (NEW)
- `web/templates/fragments/prep_checklist.html` (NEW)
- `web/templates/fragments/prep_progress.html` (NEW)
- `web/templates/account_prep.html` (NEW)
- `web/routes_api.py` (append prep endpoints)
- `web/routes_property.py` (append /prep route)
- `web/routes_auth.py` (append /account/prep)
- `web/brief.py` (append prep summary)
- `web/templates/search_results_public.html` (add Prep button)
- `web/templates/fragments/intel_preview.html` (add Prep link)
- `web/templates/fragments/nav.html` (add nav item)
- `web/static/style.css` (prep + print styles)
- `scripts/release.py` (append prep DDL)
- `tests/test_qs3_a_permit_prep.py` (NEW)

**Do NOT touch:**
- `src/tools/permit_lookup.py` (Session B)
- `src/db.py` (Session B)
- `web/routes_cron.py` (Session B)
- `web/app.py` (Sessions B + D)
- `tests/e2e/` (Session C)
- `web/templates/landing.html` (Session D)
- `web/templates/index.html` (Session D)
- `web/helpers.py` (Session D)
- `web/routes_misc.py` (Session D)
