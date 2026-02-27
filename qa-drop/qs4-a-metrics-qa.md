# QA Script: QS4-A Metrics UI + Data Surfacing

## Pre-flight
- Start local dev server
- Log in as admin user

## Checks

1. [NEW] GET /admin/metrics renders 3 sections (issuance, SLA, planning) — PASS/FAIL
2. [NEW] Station SLA table shows color-coded percentages (green/amber/red) — PASS/FAIL
3. [NEW] GET /admin/metrics requires admin auth (302 for anon, 403 for non-admin) — PASS/FAIL
4. [NEW] POST /cron/velocity-refresh with valid CRON_SECRET returns 200 — PASS/FAIL
5. [NEW] Station velocity cache query returns cached data — PASS/FAIL
6. [NEW] run_ingestion source includes 3 metrics calls — PASS/FAIL
7. [NEW] Screenshot /admin/metrics at 1440px — PASS/FAIL
