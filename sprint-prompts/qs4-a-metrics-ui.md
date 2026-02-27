<!-- LAUNCH: Paste into any CC terminal (fresh or reused):
     "Read sprint-prompts/qs4-a-metrics-ui.md and execute it" -->

# Quad Sprint 4 — Session A: Metrics UI + Data Surfacing

You are a build agent following **Black Box Protocol v1.3**.

## Agent Rules
```
WORKTREE BRANCH: Name your worktree qs4-a
DESCOPE RULE: If a task can't be completed, mark BLOCKED with reason. Do NOT silently reduce scope.
EARLY COMMIT RULE: First commit within 10 minutes. Subsequent every 30 minutes.
SAFETY TAG: git tag pre-qs4-a before any code changes.
MERGE RULE: Do NOT merge your branch to main. Commit to worktree branch only. The orchestrator (Tab 0) merges all branches.
CONFLICT RULE: Do NOT run `git checkout <branch> -- <file>` on shared files. If you encounter a conflict, stop and report it.
APPEND FILES: Write scenarios to `scenarios-pending-review-qs4-a.md` (not the shared file). Write changelog to `CHANGELOG-qs4-a.md`.
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
   Use EnterWorktree with name `qs4-a`

If worktree exists: `git worktree remove .claude/worktrees/qs4-a --force 2>/dev/null; true`

4. **Safety tag:** `git tag pre-qs4-a`

---

## PHASE 1: READ

Read these files before writing any code:
1. `CLAUDE.md` — project structure, deployment, rules
2. `src/db.py` lines 1287-1384 — metrics table schemas (permit_issuance_metrics, permit_review_metrics, planning_review_metrics)
3. `src/ingest.py` lines 2184-2283 — existing metrics ingest functions (defined but NOT called from run_ingestion)
4. `src/ingest.py` lines 2289-2372 — `run_ingestion()` main pipeline (where to add metrics calls)
5. `web/routes_cron.py` — existing cron endpoints for metrics (search for `ingest-permit-issuance`)
6. `web/routes_admin.py` — where to add metrics dashboard route
7. `src/station_velocity_v2.py` — current station velocity query patterns (no caching)
8. `web/templates/admin_ops.html` — existing admin template pattern for reference
9. `scenario-design-guide.md` — for scenario-keyed QA

**Architecture notes:**
- Templates are SELF-CONTAINED (no base.html, no Jinja inheritance, inline Obsidian CSS vars)
- All 3 metrics tables already have data on prod: permit_issuance_metrics (138K rows), permit_review_metrics (439K rows), planning_review_metrics (69K rows)
- Metrics are ingested via separate cron endpoints but NOT from `run_ingestion()` main pipeline
- Station velocity queries 3.9M addenda rows per call — needs caching
- `permit_review_metrics` has columns: station, department, met_cal_sla, bpa, review_days, assigned_days
- `permit_issuance_metrics` has columns: bpa, permit_type, otc_ih, issued_year, issued_month

---

## PHASE 2: BUILD

### Task A-1: Metrics Dashboard Route + Template (~60 min)
**Files:** `web/routes_admin.py` (append), `web/templates/admin_metrics.html` (NEW)

**Add `/admin/metrics` route to `web/routes_admin.py`:**
- Requires login + admin
- Queries all 3 metrics tables for summary data
- Renders `admin_metrics.html`

**Create `web/templates/admin_metrics.html`:**
- Self-contained template with inline Obsidian CSS vars (match admin_ops.html pattern)
- Include `fragments/nav.html`
- Three sections:

**Section 1: Permit Issuance Trends**
```sql
SELECT issued_year, issued_month, permit_type, otc_ih, COUNT(*) as count
FROM permit_issuance_metrics
WHERE issued_year >= EXTRACT(YEAR FROM CURRENT_DATE) - 2
GROUP BY issued_year, issued_month, permit_type, otc_ih
ORDER BY issued_year DESC, issued_month DESC
```
- Display as a table: Year | Month | Type | OTC/In-House | Count
- Add totals row per year

**Section 2: Station SLA Compliance**
```sql
SELECT station, department,
       COUNT(*) as total,
       SUM(CASE WHEN met_cal_sla = 'Y' THEN 1 ELSE 0 END) as met_sla,
       ROUND(AVG(review_days)::numeric, 1) as avg_days
FROM permit_review_metrics
WHERE station IS NOT NULL
GROUP BY station, department
ORDER BY total DESC
LIMIT 30
```
- Display as table with SLA % column (met_sla/total * 100)
- Color code: green >= 80%, amber 60-79%, red < 60%

**Section 3: Planning Velocity**
```sql
SELECT project_stage, metric_outcome, COUNT(*) as count,
       ROUND(AVG(metric_value)::numeric, 1) as avg_value
FROM planning_review_metrics
GROUP BY project_stage, metric_outcome
ORDER BY count DESC
```
- Display as grouped table

### Task A-2: Add Metrics to Nightly Pipeline (~15 min)
**Files:** `src/ingest.py` (append 3 calls)

Add to `run_ingestion()` at ~line 2361 (after dwelling_completions):
```python
# Metrics datasets (refresh alongside main pipeline)
await ingest_permit_issuance_metrics()
await ingest_permit_review_metrics()
await ingest_planning_review_metrics()
```

### Task A-3: Station Velocity Caching (~45 min)
**Files:** `src/station_velocity_v2.py` (add caching), `scripts/release.py` (DDL), `web/routes_cron.py` (refresh endpoint)

**Add `station_velocity_cache` table DDL to `scripts/release.py`:**
```sql
CREATE TABLE IF NOT EXISTS station_velocity_cache (
    station TEXT NOT NULL,
    permit_type TEXT NOT NULL,
    p25_days REAL,
    p50_days REAL,
    p75_days REAL,
    sample_count INTEGER,
    refreshed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (station, permit_type)
);
```

**Add caching to `station_velocity_v2.py`:**
- `_get_cached_velocity(station, permit_type)` — check cache first (< 24h old)
- `_refresh_velocity_cache()` — recalculate all stations, upsert into cache
- Fallback to live query if cache miss

**Add `POST /cron/refresh-velocity-cache` to `web/routes_cron.py`:**
- CRON_SECRET auth
- Calls `_refresh_velocity_cache()`
- Returns count of stations cached

### ~~Task A-4: Extract Street-Use Contacts~~ — DESCOPED TO QS5
**Reason:** Entity resolution changes are high-risk for a beta launch sprint. 1.2M records touching the 5-step resolution cascade could introduce regressions in consultant recommendations, entity network, and property reports. Defer to QS5 when we can test thoroughly.

---

## PHASE 3: TEST

```bash
source /Users/timbrenneman/AIprojects/sf-permits-mcp/.venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

Write `tests/test_qs4_a_metrics.py`:
- /admin/metrics returns 200 for admin user
- /admin/metrics returns 403 for non-admin
- /admin/metrics returns 302 for anonymous
- Issuance trends query returns data structure with year/month/type keys
- Station SLA query returns station/department/met_sla keys
- Planning velocity query returns stage/outcome keys
- Station velocity cache table created successfully
- _get_cached_velocity returns None on cache miss
- _get_cached_velocity returns data on cache hit
- _refresh_velocity_cache populates cache table
- Stale cache (> 24h) triggers live query fallback
- POST /cron/refresh-velocity-cache requires CRON_SECRET
- POST /cron/refresh-velocity-cache returns station count
- Metrics ingest functions are called in run_ingestion

**Target: 20+ tests**

Run pytest after EACH task.

---

## PHASE 4: SCENARIOS

Append 3 scenarios to `scenarios-pending-review-qs4-a.md` (per-agent file):
1. "Admin views station SLA compliance and identifies bottleneck departments"
2. "Station velocity query returns cached results in under 100ms"
3. "Nightly pipeline includes metrics refresh alongside permit data"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/qs4-a-metrics-qa.md`:

```
1. [NEW] GET /admin/metrics renders 3 sections (issuance, SLA, planning) — PASS/FAIL
2. [NEW] Station SLA table shows color-coded percentages — PASS/FAIL
3. [NEW] GET /admin/metrics requires admin auth — PASS/FAIL
4. [NEW] POST /cron/refresh-velocity-cache populates cache — PASS/FAIL
5. [NEW] Station velocity query uses cache when available — PASS/FAIL
6. [NEW] run_ingestion includes 3 metrics calls — PASS/FAIL
7. [NEW] Screenshot /admin/metrics at 1440px — PASS/FAIL
```

Save screenshots to `qa-results/screenshots/qs4-a/`
Write results to `qa-results/qs4-a-results.md`

---

## PHASE 5.5: VISUAL REVIEW

Score these pages 1-5:
- /admin/metrics at 1440px
- /admin/metrics at 375px (mobile)

---

## PHASE 6: CHECKCHAT

### 1. VERIFY
- All QA FAILs fixed or BLOCKED
- pytest passing, no regressions

### 2. DOCUMENT
- Write `CHANGELOG-qs4-a.md` with session entry

### 3. CAPTURE
- 3 scenarios in `scenarios-pending-review-qs4-a.md`

### 4. SHIP
- Commit with: "feat: Metrics UI + data surfacing (QS4-A)"
- Report: files created, test count, QA results

### 5. PREP NEXT
- Note: velocity cache needs adding to nightly cron schedule

### 6. BLOCKED ITEMS REPORT

### 7. TELEMETRY
```
## TELEMETRY
| Metric | Estimated | Actual |
|--------|-----------|--------|
| Wall clock time | 2-3 hours | [first commit to CHECKCHAT] |
| New tests | 25+ | [count] |
| Tasks completed | 3 | [N of 3] |
| Tasks descoped | — | [count + reasons] |
| Tasks blocked | — | [count + reasons] |
| Longest task | — | [task name, duration] |
| QA checks | 7 | [pass/fail/skip] |
| Visual Review avg | — | [score] |
| Scenarios proposed | 3 | [count] |
```

### Visual QA Checklist
- [ ] Metrics dashboard: are the tables readable and well-organized?
- [ ] SLA color coding: does green/amber/red communicate intuitively?
- [ ] Mobile: usable on phone or is admin-only desktop-first acceptable?

---

## File Ownership (Session A ONLY)
**Own:**
- `web/routes_admin.py` (append metrics route)
- `web/templates/admin_metrics.html` (NEW)
- `src/ingest.py` (append 3 metrics calls + street-use extraction)
- `src/station_velocity_v2.py` (add caching layer)
- `scripts/release.py` (append velocity cache DDL)
- `web/routes_cron.py` (append velocity refresh endpoint)
- `tests/test_qs4_a_metrics.py` (NEW)
- `CHANGELOG-qs4-a.md` (NEW — per-agent)
- `scenarios-pending-review-qs4-a.md` (NEW — per-agent)

**Do NOT touch:**
- `web/app.py` (Session B + D)
- `src/db.py` (Session B)
- `web/security.py` (Session D)
- `web/templates/index.html` (Session C)
- `web/templates/brief.html` (Session C)
- `web/routes_misc.py` (Session B)
- `web/static/design-system.css` (Session C)
- `web/helpers.py` (Session D owns PostHog verification)
