# Sprint 56 — DeskRelay: Staging → Promotion → Prod

## Context
Sprint 56 implements the Chang Family viral loop: homeowner → describe project → teaser → signup → full analysis → email to architect → architect auto-registered via shared link. Also: plumbing inspections shared table, 3 review metrics tables, 4 tier1 knowledge files, ref table wiring. 6 parallel agents, 2,304 tests passing, 320+ new tests.

## Setup
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

## Rules
- NO code changes. QA artifacts only.
- If a check fails, document it. Do NOT attempt fixes.

---

## Part 1: Staging Checks
Target: https://sfpermits-ai-staging-production.up.railway.app

### Health
1. [ ] Health endpoint returns 200 with `status: ok`
2. [ ] New tables exist: `permit_issuance_metrics`, `permit_review_metrics`, `planning_review_metrics`, `analysis_sessions`, `beta_requests`
3. [ ] `inspections` table has `source` column (row count unchanged or higher)

### Homeowner Funnel (Sprint 56E)
4. [ ] Landing page shows "Planning a project?" card with textarea and neighborhood dropdown
5. [ ] Landing page shows "Got a violation?" card with link to search
6. [ ] Submit "kitchen remodel" to /analyze-preview → shows preview with OTC/In-House fork comparison
7. [ ] Preview shows locked cards (fees, docs, risk) with signup CTA
8. [ ] Search with `?context=violation` shows violations/complaints first in results
9. [ ] Brief page shows empty state with CTA when no watches
10. [ ] Portfolio page shows empty state with CTA when empty

### Shareable Analysis (Sprint 56D)
11. [ ] Run analysis (POST /analyze with project description) → share bar appears below results
12. [ ] "Copy share link" copies a URL like /analysis/<uuid>
13. [ ] Visit /analysis/<uuid> without login → page loads with tab layout and "Try sfpermits.ai" CTA
14. [ ] Visit /analysis/nonexistent-id → 404 page (not 500)
15. [ ] "Email to your team" opens modal with email input

### Three-Tier Signup (Sprint 56D)
16. [ ] /beta-request page renders with email, name, reason fields; honeypot field hidden
17. [ ] Submit beta request → confirmation message appears
18. [ ] Login page accepts `?referral_source=shared_link` param without errors
19. [ ] /admin/beta-requests (as admin) shows beta request queue

### Data Pipeline (Sprint 56C, 56F)
20. [ ] Run `/cron/migrate-schema` with CRON_SECRET → new tables created (may need to run migrations)
21. [ ] Run `/cron/ingest-plumbing-inspections` → rows appear in inspections table
22. [ ] Run `/cron/ingest-permit-issuance-metrics` → rows appear
23. [ ] Run `/cron/ingest-permit-review-metrics` → rows appear
24. [ ] Run `/cron/ingest-planning-review-metrics` → rows appear

### Auth Smoke Test
25. [ ] CRON_SECRET auth works (hit /cron/status with bearer token → 200)

Screenshots to: qa-results/screenshots/sprint56-deskrelay-staging/

---

## Part 2: Promotion Ceremony
(Only if all staging checks PASS)

```bash
git checkout prod && git merge main && git push origin prod
```

Wait 120s for prod deploy.

Post-promotion commands:
```bash
SECRET="f6564fc90fcd615e7192789d51bd83806216951a16d1ee8ac15975413a437758"
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/migrate-schema
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/seed-references
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/signals
```

---

## Part 3: Prod Checks
Target: https://sfpermits-ai-production.up.railway.app

26. [ ] Health endpoint returns 200 with all new tables
27. [ ] Landing page loads with homeowner funnel sections
28. [ ] /analyze-preview works (kitchen remodel → fork comparison)
29. [ ] "Got a violation?" CTA routes correctly
30. [ ] Search for "75 robin hood dr" returns results
31. [ ] Click a permit → detail page loads
32. [ ] /analysis/<valid-id> loads (may need to create one first)

Screenshots to: qa-results/screenshots/sprint56-deskrelay-prod/

---

## Part 4: Close
Results to: qa-results/sprint56-deskrelay-results.md
Lightweight CHECKCHAT: commit QA artifacts, push, update Chief.
