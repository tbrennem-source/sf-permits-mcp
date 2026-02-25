# Sprint 55 — DeskRelay: Staging → Promotion → Prod

## Context

Sprint 55 completed the following in the sf-permits-mcp repo:
- 7 new SODA datasets ingested (electrical, plumbing, street use, dev pipeline, affordable housing, housing production, dwelling completions)
- 3 reference tables seeded (ref_zoning_routing, ref_permit_forms, ref_agency_triggers)
- MCP tools enriched: permit_lookup shows planning records + boiler permits, property_lookup uses local tax_rolls fallback, predict_permits is zoning-aware
- Morning brief gains planning_context, compliance_calendar, data_quality sections
- Nightly pipeline expanded to monitor planning record and boiler permit changes
- 1964 tests passing (up from 1820)

## Setup

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
```

## Rules

- NO code changes. QA artifacts only.
- If a check fails, document it. Do NOT attempt fixes.
- Save all screenshots to the paths specified below.
- Write final results to the path specified in Part 4.

---

## Part 1: Staging Checks

**Target:** https://sfpermits-ai-staging-production.up.railway.app

Screenshots to: `qa-results/screenshots/sprint55-deskrelay-staging/`

### 1.1 Health endpoint

```bash
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool
```

**PASS:** `"status": "ok"`, `tables` object present, no error fields
**FAIL:** status != ok, tables missing, or connection refused

### 1.2 Landing page loads

Navigate to: https://sfpermits-ai-staging-production.up.railway.app

Screenshot: `sprint55-staging-landing.png`

**PASS:** Page loads without error; search bar is visible; no "Application Error" banner
**FAIL:** 500 error page, blank page, or "Application Error"

### 1.3 Permit search returns electrical/plumbing permits

Search for: `75 robin hood dr`

Screenshot: `sprint55-staging-search-results.png`

**PASS:** Results page loads; permits displayed with permit types visible; page does not error
**FAIL:** Search returns no results, 500 error, or page is blank

### 1.4 Property detail page with planning section

Click on any permit from the search results to open the detail view.

Screenshot: `sprint55-staging-permit-detail.png`

**PASS:** Detail page loads; permit fields (address, type, status) visible; no traceback in page
**FAIL:** 500 error, blank page, or missing permit fields

### 1.5 Property lookup with zoning context

Navigate to property lookup using block/lot (or use the MCP tool UI if available).

Screenshot: `sprint55-staging-property-lookup.png`

**PASS:** Property lookup returns data including zoning or assessed value information; no error
**FAIL:** Empty response, error page, or "no data found" for a known parcel

### 1.6 New tables visible in health response

```bash
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | \
  python3 -c "
import sys, json
h = json.load(sys.stdin)
tables = h.get('tables', {})
new_tables = ['street_use_permits', 'development_pipeline', 'affordable_housing',
              'housing_production', 'dwelling_completions',
              'ref_zoning_routing', 'ref_permit_forms', 'ref_agency_triggers']
for t in new_tables:
    row_count = tables.get(t, {}).get('row_count', 'MISSING')
    print(f'{t}: {row_count}')
"
```

**PASS:** All 8 new tables present in health response with row_count values (0 or more)
**FAIL:** Any table absent from response with key "MISSING"

### 1.7 Cron endpoints reject unauthenticated requests

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://sfpermits-ai-staging-production.up.railway.app/cron/ingest-electrical

curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://sfpermits-ai-staging-production.up.railway.app/cron/seed-references

curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://sfpermits-ai-staging-production.up.railway.app/cron/ingest-street-use
```

**PASS:** All 3 return `403`
**FAIL:** Any returns 200 or 500

---

## Part 2: Promotion Ceremony

**Only proceed if ALL Part 1 checks PASS.**

If any Part 1 check FAILED, stop here. Write results to `qa-results/sprint55-deskrelay-results.md` with BLOCKED status and the specific failure. Do not promote.

### Promotion command (exact — do not modify)

```bash
git checkout prod && git merge main && git push origin prod
```

### Wait for prod deploy

Wait **120 seconds** after the push for Railway to build and deploy the production service.

You can monitor deployment status at:
```
https://railway.app/project/sfpermits-ai/deployments
```

### Post-promotion steps

Run migrations and seed reference tables on production:

```bash
export CRON_SECRET="$(railway variable list --service sfpermits-ai | grep CRON_SECRET | awk '{print $3}')"
export PROD_URL="https://sfpermits-ai-production.up.railway.app"

# 1. Run migrations
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/migrate" | python3 -m json.tool

# 2. Seed reference tables
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/seed-references" | python3 -m json.tool

# 3. Trigger electrical ingest (large dataset — may take several minutes)
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-electrical" | python3 -m json.tool

# 4. Trigger plumbing ingest
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-plumbing" | python3 -m json.tool

# 5. Trigger development pipeline ingest
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-development-pipeline" | python3 -m json.tool

# 6. Trigger affordable housing ingest
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-affordable-housing" | python3 -m json.tool

# 7. Trigger housing production ingest
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-housing-production" | python3 -m json.tool

# 8. Trigger dwelling completions ingest
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  "$PROD_URL/cron/ingest-dwelling-completions" | python3 -m json.tool

# NOTE: /cron/ingest-street-use ingests ~1.2M rows and will take several minutes.
# Run this separately or schedule for nightly cron rather than during DeskRelay.
# Only run if you have 10+ minutes available:
# curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" "$PROD_URL/cron/ingest-street-use" | python3 -m json.tool
```

**PASS for each command:** Returns JSON with `ok: true` or row counts; no error fields
**FAIL for any command:** Returns 4xx, 5xx, or error in JSON body

---

## Part 3: Prod Checks

**Target:** https://sfpermits-ai-production.up.railway.app

Screenshots to: `qa-results/screenshots/sprint55-deskrelay-prod/`

### 3.1 Health endpoint

```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```

**PASS:** `"status": "ok"`, tables present
**FAIL:** Error, tables missing, or connection refused

### 3.2 Landing page loads

Navigate to: https://sfpermits-ai-production.up.railway.app

Screenshot: `sprint55-prod-landing.png`

**PASS:** Page loads without error; search bar visible; no "Application Error"
**FAIL:** 500 error, blank page, or "Application Error"

### 3.3 Permit search returns results

Search for: `75 robin hood dr`

Screenshot: `sprint55-prod-search-results.png`

**PASS:** Results load; permit types visible; no errors
**FAIL:** Search errors, blank results when parcel should have data, 500 error

### 3.4 New tables present in prod health

```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | \
  python3 -c "
import sys, json
h = json.load(sys.stdin)
tables = h.get('tables', {})
new_tables = ['street_use_permits', 'development_pipeline', 'affordable_housing',
              'housing_production', 'dwelling_completions',
              'ref_zoning_routing', 'ref_permit_forms', 'ref_agency_triggers']
for t in new_tables:
    row_count = tables.get(t, {}).get('row_count', 'MISSING')
    print(f'{t}: {row_count}')
"
```

**PASS:** All 8 tables present; ref tables show seeded row counts (29/28/38)
**FAIL:** Any table absent or ref tables show 0 rows after seed step

### 3.5 Cross-reference check passes

```bash
curl -s -X POST \
  -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/cross-ref-check | python3 -m json.tool
```

**PASS:** Response shows match rates; all rates > 5%
**FAIL:** Error response, or any match rate reported as 0%

### 3.6 Signal pipeline is live

```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | \
  python3 -c "
import sys, json
h = json.load(sys.stdin)
ph = h.get('property_health_count', h.get('signal_pipeline', 'not_present'))
print('property_health:', ph)
"
```

**PASS:** property_health count > 0 or signal pipeline reported as active
**FAIL:** Count is 0 or key not present after signals have been seeded

### 3.7 Prod cron endpoints reject unauthenticated requests

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://sfpermits-ai-production.up.railway.app/cron/ingest-electrical

curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://sfpermits-ai-production.up.railway.app/cron/seed-references
```

**PASS:** Both return `403`
**FAIL:** Either returns 200 or 500

---

## Part 4: Close

Results to: `qa-results/sprint55-deskrelay-results.md`

Write a results file with the following structure:

```markdown
# Sprint 55 — DeskRelay Results
Date: [date]

## Staging Checks
| Check | Result | Notes |
|-------|--------|-------|
| 1.1 Health endpoint | PASS/FAIL | |
| 1.2 Landing page | PASS/FAIL | |
| 1.3 Permit search | PASS/FAIL | |
| 1.4 Permit detail | PASS/FAIL | |
| 1.5 Property lookup | PASS/FAIL | |
| 1.6 New tables in health | PASS/FAIL | |
| 1.7 Cron auth rejection | PASS/FAIL | |

## Promotion
| Step | Result | Notes |
|------|--------|-------|
| git merge + push | PASS/FAIL | |
| Migration | PASS/FAIL | |
| Seed references | PASS/FAIL | |
| Electrical ingest | PASS/FAIL | |
| Plumbing ingest | PASS/FAIL | |
| Dev pipeline ingest | PASS/FAIL | |
| Affordable housing ingest | PASS/FAIL | |
| Housing production ingest | PASS/FAIL | |
| Dwelling completions ingest | PASS/FAIL | |

## Prod Checks
| Check | Result | Notes |
|-------|--------|-------|
| 3.1 Health endpoint | PASS/FAIL | |
| 3.2 Landing page | PASS/FAIL | |
| 3.3 Permit search | PASS/FAIL | |
| 3.4 New tables in health | PASS/FAIL | |
| 3.5 Cross-ref check | PASS/FAIL | |
| 3.6 Signal pipeline | PASS/FAIL | |
| 3.7 Cron auth rejection | PASS/FAIL | |

## Summary
Overall: PASS / FAIL / PARTIAL
Open issues: [list any FAILs with notes]
```

Lightweight CHECKCHAT:
1. `git add qa-results/sprint55-deskrelay-results.md qa-results/screenshots/`
2. `git commit -m "qa: Sprint 55 DeskRelay results"`
3. `git push origin main`
4. Update Chief brain state with session summary via `chief_add_note`
5. Note any follow-ups as new tasks via `chief_add_task`
