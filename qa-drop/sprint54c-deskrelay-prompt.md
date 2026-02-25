# Sprint 54C — DeskRelay: Staging → Promotion → Prod

## Context
Sprint 54C added 4 new SODA datasets (boiler permits, fire permits, planning records, tax rolls) with ~1.15M new records. Data is on staging. This prompt verifies staging, promotes to prod, ingests on prod, then verifies prod.

---

## Part 1: Staging Visual Checks

### Check 1: Health endpoint shows new tables
- Navigate to: https://sfpermits-ai-staging-production.up.railway.app/health
- Verify JSON contains `boiler_permits`, `fire_permits`, `planning_records`, `tax_rolls`
- All counts should be > 0
- Screenshot

### Check 2: Landing page loads normally (no regression)
- Navigate to: https://sfpermits-ai-staging-production.up.railway.app/
- Verify page loads without errors
- Screenshot

---

## Part 2: Promotion Ceremony

After staging checks pass:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout prod && git merge main && git push origin prod
```

Wait ~3 min for prod deploy.

---

## Part 3: Prod Migration + Ingest

```bash
CRON="f6564fc90fcd615e7192789d51bd83806216951a16d1ee8ac15975413a437758"

# 1. Run schema migrations
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/migrate

# 2. Ingest all 4 datasets (run sequentially — each takes 1-4 min)
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-boiler
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-fire
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-planning
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-tax-rolls
```

---

## Part 4: Prod Visual Checks

### Check 3: Health endpoint shows new tables with data
- Navigate to: https://sfpermits-ai-production.up.railway.app/health
- Verify `boiler_permits`, `fire_permits`, `planning_records`, `tax_rolls` all > 0
- Counts should match staging (~151K, ~84K, ~282K, ~636K)
- Screenshot

### Check 4: Cross-ref check returns reasonable match rates
- Run: `POST /cron/cross-ref-check` with CRON_SECRET
- Verify planning→permits >5%, boiler→permits >5%, tax→permits >5%

### Check 5: Landing page loads normally
- Navigate to: https://sfpermits-ai-production.up.railway.app/
- Verify no errors
- Screenshot

### Check 6: Existing features work (spot check)
- Navigate to a property report or permit lookup page
- Verify no regressions in existing UI
- Screenshot
