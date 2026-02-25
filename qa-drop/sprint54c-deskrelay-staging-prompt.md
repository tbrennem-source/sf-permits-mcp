# Sprint 54C — DeskRelay Staging Verification

## Context
Sprint 54C added 4 new SODA datasets (boiler permits, fire permits, planning records, tax rolls) with ~1.15M new records. Data is on staging. This prompt verifies staging then promotes to prod.

## Visual Checks (staging)

### Check 1: Health endpoint shows new tables
- Navigate to: https://sfpermits-ai-staging-production.up.railway.app/health
- Verify JSON contains `boiler_permits`, `fire_permits`, `planning_records`, `tax_rolls`
- All counts should be > 0
- Screenshot

### Check 2: Landing page loads normally (no regression)
- Navigate to: https://sfpermits-ai-staging-production.up.railway.app/
- Verify page loads without errors
- Screenshot

## Promotion Ceremony (after checks pass)

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout prod && git merge main && git push origin prod
```

## Post-Promotion (prod)

After prod deploys (~3 min):

1. Run migrations on prod:
```bash
CRON="f6564fc90fcd615e7192789d51bd83806216951a16d1ee8ac15975413a437758"
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/migrate
```

2. Ingest all 4 datasets on prod:
```bash
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-boiler
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-fire
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-planning
curl -s -X POST -H "Authorization: Bearer $CRON" https://sfpermits-ai-production.up.railway.app/cron/ingest-tax-rolls
```

3. Verify prod health shows new table counts

Then proceed to `sprint54c-deskrelay-prod-prompt.md`.
