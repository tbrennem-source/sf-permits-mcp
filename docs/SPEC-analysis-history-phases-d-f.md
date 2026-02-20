# Spec: Analysis History — Phases D-F (Deferred Features)

> **Status**: Spec'd, not yet implemented
> **Prerequisite**: Phases A-C deployed in Session 40 (2026-02-20)
> **Origin**: Three-role review (Amy/UI/Data Analytics) in Session 40 planning

## What's Already Built (Phases A-C)

| Feature | Status |
|---------|--------|
| Inline upload form on history page | ✅ Deployed |
| Duration fix (`started_at` not `created_at`) | ✅ Deployed |
| Live elapsed timer for processing jobs | ✅ Deployed |
| Bulk select mode + checkboxes + floating action bar | ✅ Deployed |
| Bulk delete endpoint (`POST /api/plan-jobs/bulk-delete`) | ✅ Deployed |
| Sort controls (5 options: newest/oldest/address/filename/status) | ✅ Deployed |
| Project grouping with address + filename normalization | ✅ Deployed |
| Accordion grouped view with version badges | ✅ Deployed |
| "1 of N scans" badge in flat view | ✅ Deployed |
| Group/flat toggle in view options bar | ✅ Deployed |

### Known Minor Gaps from Phases A-C
1. **Undo toast is informational only** — deletes immediately, shows "Deleted X" after. Plan called for 10s undo window or soft-delete. True undo needs `is_archived` (Phase D).
2. **No localStorage for group preference** — resets on page reload (URL param only).
3. **Sort UX is toggle-links, not a dropdown selector** — functional but minimal.

---

## Phase D — Close Project + Document Fingerprinting (P2, ~12 hrs)

### D1: Close Project (was "Archive")

**Amy's mental model**: "active projects" vs "closed projects." She doesn't think in terms of "archive" — she thinks "this project is done, get it out of my face."

**Database**:
- Add `is_archived BOOLEAN DEFAULT FALSE` column to `plan_analysis_jobs` (auto-migrate)

**Backend** (`web/plan_jobs.py`):
- `close_project(job_ids: list[str], user_id: int)` — sets `is_archived=TRUE` for all jobs in list
- `reopen_project(job_ids: list[str], user_id: int)` — sets `is_archived=FALSE`
- Update `get_user_jobs()` — filter `WHERE is_archived = FALSE` by default; accept `include_archived` param
- Update `cleanup_old_jobs()` — skip jobs that belong to a version_group where any member is < 30 days old

**Endpoints** (`web/app.py`):
- `POST /api/plan-jobs/bulk-close` — close multiple jobs (or entire project group)
- `POST /api/plan-jobs/{job_id}/close` — close single job
- `POST /api/plan-jobs/{job_id}/reopen` — reopen

**Template**:
- "Closed" filter chip in filter bar (toggles to show closed items with greyed-out cards)
- "Close Project" button in group header (closes ALL analyses in group)
- "Close" button per card in action area
- "Reopen" button on closed items
- Bulk action toolbar: add "Close Selected" next to "Delete Selected"

**Interaction with bulk delete**: With soft-delete (close) available, the undo toast gap from Phase B is resolved — "Close" is the safe default, "Delete" is the permanent action.

---

### D2: Document Fingerprinting (Same Doc, Different Filename)

**Problem**: User renames `PrelimPermitSet11.14.pdf` to `PrelimPermitSet11.14-v2.pdf` or `Webster_resubmittal.pdf`. We need to recognize it's the same project.

**Three-layer identity matching** (strongest → weakest):

| Layer | Signal | Confidence | Exists? |
|-------|--------|------------|---------|
| 1. Content hash | SHA-256 of PDF bytes | Exact = same file | ❌ New |
| 2. Structural fingerprint | Page count + dimensions + sheet numbers | High — same set even if annotations changed | ❌ New |
| 3. Metadata match | `property_address` OR `permit_number` OR normalized filename | Medium — same project, maybe different version | ✅ Already built (Phase C grouping) |

**Database**:
- Add `pdf_hash TEXT` column — SHA-256 computed at upload time
- Add `structural_fingerprint TEXT` column — computed after async processing

**Two-phase linking**:
1. **At upload** (`create_job()`): Compute SHA-256 hash. Query for exact hash match. Also check address/permit/filename (Layer 3, already exists). → Tentative grouping.
2. **After processing** (`plan_worker.py`): Extract sheet numbers + page dimensions. Compute structural fingerprint. Use **overlap scoring** (not exact match): if 10 of 12 sheets match a previous analysis → 83% structural match → same project. **Threshold: 60%+**. → Confirm or reassign grouping.

**Why overlap scoring, not exact match**: Common case is architect adds 2 sheets to a 12-page set. Now it's 14 pages with different sheet count. Exact structural match fails. Overlap catches it.

**Files**:
- `web/app.py` — `pdf_hash` and `structural_fingerprint` column migrations
- `web/plan_jobs.py` — hash computation in `create_job()`, `find_related_jobs()` with 3-layer matching
- `web/plan_worker.py` — structural fingerprint computation after page extraction
- `web/app.py` (grouping) — incorporate fingerprint matches into `group_jobs_by_project()`

---

## Phase E — Version Chain + Comparison Page (P2, ~8-12 hrs)

### E1: Version Chain Data Model

**New columns on `plan_analysis_jobs`**:
- `version_group TEXT` — shared ID for all related analyses (generated from first upload, propagated to matches)
- `version_number INTEGER` — auto-incremented within group (1, 2, 3...)
- `parent_job_id TEXT` — optional explicit link to previous version

**Functions** (`web/plan_jobs.py`):
- `assign_version_group(job_id, group_id)` — link a job to an existing version group
- `get_version_chain(version_group)` — return ordered list of all jobs in chain
- Auto-assign on fingerprint match (Phase D2)

**Revision extraction**: Vision prompts already detect revision triangles (△) and revision blocks in title blocks. Extend `src/vision/prompts.py` to explicitly extract revision number/date from title blocks → store as metadata.

### E2: Comparison Page

**Route**: `GET /account/analyses/compare?a=<job_id>&b=<job_id>`

**Priority order for comparison features**:

| Priority | Tab | What | Method | Amy Value |
|----------|-----|------|--------|-----------|
| 🔴 P0 | **Summary** | Comment resolution count + EPR changes | Compare annotation lists by text similarity | "12 of 32 comments resolved" — **Amy's deliverable to Vince** |
| 🔴 P0 | **Comments** | Per-comment resolution table | v1 comment → status (resolved/new/unchanged) → v2 response | The actual table Amy emails to architects |
| 🟡 P1 | **Sheets** | Sheet list diff | Compare extracted sheet lists | "Sheet S1.0 added, A0.1 removed" |
| P2 | **Visual** | Side-by-side page gallery | Existing plan_analysis_images infrastructure | Flip between versions visually |
| P3 | **EPR Detail** | Per-check status change | Compare metadata_results arrays | "EPR-012 went FAIL → PASS" |

**Data model**: Don't diff raw `report_md` strings — store structured `comparison_json` once when both analyses complete. Contains:
- `comment_resolutions`: list of {v1_comment, status, v2_match}
- `epr_changes`: list of {check_id, v1_status, v2_status}
- `sheet_diff`: {added: [], removed: [], unchanged: []}

Compute once at render time (or on-demand), cache in a new `comparison_json JSONB` column. Renders instantly without re-computation.

**Template**: `web/templates/analysis_compare.html` — tab-based layout (not two-column — too wide for long reports):
- Tab navigation at top
- Each tab is focused and scannable
- "Compare with previous" button on v2+ cards in grouped view

**UX in grouped view header**:
- Summary line: "✅ 8 comments resolved, ⚠️ 4 new comments, 📄 2 sheets added"
- "Compare latest two" quick action

---

## Phase F — Stats Banner + Project Notes + Visual Comparison (P3, ~6 hrs)

### F1: Stats Banner
Small stats bar at top of history page:
- "12 analyses this month | Avg processing: 2m 14s | 3 projects tracked"
- Helps Amy set client expectations
- Optionally show AI cost per analysis from `vision_usage_json` (for paid product planning)

### F2: Project Notes
Amy wants to add notes to a project group: "Sent to architect Feb 15, waiting on fire rating revisions."
- New `project_notes TEXT` column or separate `project_notes` table keyed by `version_group`
- Simple free-text input per project group in grouped view
- Notes visible in accordion header (truncated) and full when expanded

### F3: Visual Comparison (Tab 4)
Side-by-side rendered pages from existing `plan_analysis_images` infrastructure:
- Page selector (dropdown or thumbnail strip)
- Sync scroll between v1 and v2
- Toggle: side-by-side vs overlay with opacity slider

### F4: Revision Extraction from Title Blocks
Enhance `src/vision/prompts.py` to explicitly extract:
- Revision number (e.g., "Rev 2")
- Revision date
- Revision description (if present in revision block)
Store as structured metadata in job record. Display in version chain timeline.

---

## Build Order Summary

| Phase | Features | Est. | Depends On |
|-------|----------|------|------------|
| **D** | Close Project + Document Fingerprinting | 12 hrs | Phases A-C (done) |
| **E** | Version Chain + Comparison (comments + sheets) | 8-12 hrs | Phase D (fingerprinting) |
| **F** | Stats Banner + Project Notes + Visual Compare + Revision Extraction | 6 hrs | Phase E (version chain) |

## Verification Checklist

**Phase D**:
- [ ] "Close Project" on a group → all analyses hidden from default view
- [ ] "Closed" filter chip → shows closed projects with "Reopen" option
- [ ] Upload same PDF with different filename → auto-linked via SHA-256 match
- [ ] Upload revised PDF (2 new sheets added) → 83% sheet overlap → auto-linked
- [ ] `cleanup_old_jobs()` skips version groups with any member < 30 days old

**Phase E**:
- [ ] "Compare with previous" on v2 card → comparison page opens
- [ ] Summary tab: "✅ 8 comments resolved, ⚠️ 4 new, 📄 2 sheets added"
- [ ] Comments tab: table showing each v1 comment + resolution status
- [ ] Sheets tab: added/removed/unchanged sheet lists

**Phase F**:
- [ ] Stats banner shows monthly count, avg processing time, project count
- [ ] Project notes editable in grouped view
- [ ] Visual comparison: side-by-side page gallery with page selector
