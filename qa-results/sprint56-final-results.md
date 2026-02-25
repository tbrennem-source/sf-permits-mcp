# Sprint 56 Final QA Results — 2026-02-25 20:38 UTC

**URL:** https://sfpermits-ai-staging-production.up.railway.app
**Summary:** 15 PASS / 0 FAIL / 0 SKIP

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Health: status=ok, 54 tables, inspections > 1M, total rows > 18.7M | PASS | status=ok, tables=54, inspections=1,070,674, total_rows=18,792,473 |
| 2 | Health: permit/planning review metrics > 0 | PASS | permit_issuance_metrics=138,244, permit_review_metrics=439,403, planning_review_metrics=69,191 |
| 3 | Health: analysis_sessions and beta_requests tables exist | PASS | analysis_sessions present=True (rows=0), beta_requests present=True (rows=0) |
| 4 | Landing: 'Planning a project?' textarea visible | PASS | textarea_visible=True, textarea_count=1 |
| 5 | Landing: 'Got a violation?' CTA visible | PASS | violation_cta_found=True |
| 6 | POST /analyze-preview kitchen remodel returns 200 with permit content | PASS | status=200, response_len=18993, has_permit_content=True |
| 7 | GET /search?q=market+street&context=violation loads OK | PASS | title='market street — sfpermits.ai', is_error=False, page_len=11671 |
| 8 | GET /beta-request form with email, name, reason fields | PASS | has_email=True, has_name=True, has_reason=True, is_404=False |
| 9 | GET /analysis/nonexistent-id returns 404 not 500 | PASS | status=404, is_500=False |
| 10 | GET /auth/login login page loads | PASS | has_form=True, is_500=False, title='Sign in — sfpermits.ai' |
| 11 | GET /auth/login?referral_source=shared_link loads without error | PASS | is_500=False, title='Sign in — sfpermits.ai', page_len=4717 |
| 12 | GET / landing page loads | PASS | title='sfpermits.ai — San Francisco Building Permit Intelligence', is_blank=False, is_500=False, page_len=18935 |
| 13 | Search '75 robin hood' results appear (or graceful no-results) | PASS | is_500=False, has_results=True, title='75 robin hood — sfpermits.ai' |
| 14 | Property result accessible without 500 (unauthenticated sees locked card) | PASS | unauthenticated view: has_locked_card=True, has_result_content=True, no_500=True |
| 15 | GET /brief redirects to login when unauthenticated | PASS | status=302, location='/auth/login' |

Screenshots: qa-results/screenshots/sprint56-final/

## Raw Health JSON

```json
{
  "status": "ok",
  "backend": "postgres",
  "has_db_url": true,
  "tables": {
    "activity_log": 522,
    "addenda": 3920710,
    "addenda_changes": 1504,
    "affordable_housing": 194,
    "analysis_sessions": 0,
    "api_daily_summary": 0,
    "api_usage": 3,
    "auth_tokens": 6,
    "beta_requests": 0,
    "boiler_permits": 151919,
    "businesses": 126585,
    "complaints": 325977,
    "contacts": 1847052,
    "cron_log": 20,
    "development_pipeline": 2055,
    "dq_cache": 1,
    "dwelling_completions": 2389,
    "entities": 1014670,
    "feedback": 4,
    "fire_permits": 83975,
    "housing_production": 5798,
    "ingest_log": 21,
    "inspections": 1070674,
    "knowledge_chunks": 2685,
    "permit_changes": 1075,
    "permit_issuance_metrics": 138244,
    "permit_review_metrics": 439403,
    "permit_signals": 313739,
    "permits": 1985343,
    "plan_analysis_images": 365,
    "plan_analysis_jobs": 11,
    "plan_analysis_sessions": 35,
    "planning_records": 282169,
    "planning_review_metrics": 69191,
    "points_ledger": 2,
    "project_notes": 0,
    "property_health": 0,
    "property_signals": 0,
    "ref_agency_triggers": 35,
    "ref_permit_forms": 29,
    "ref_zoning_routing": 30,
    "regulatory_watch": 3,
    "relationships": 576323,
    "reviewer_interactions": 3695735,
    "signal_types": 13,
    "station_velocity": 245,
    "station_velocity_v2": 254,
    "street_use_permits": 1206125,
    "tax_rolls": 636410,
    "timeline_stats": 381962,
    "users": 6,
    "violations": 508906,
    "voice_calibrations": 15,
    "watch_items": 41
  },
  "db_connected": true
}
```