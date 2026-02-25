# Sprint 56 — DeskRelay: Staging → Promotion → Prod

## Context
Sprint 56 implements the Chang Family viral loop: homeowner → describe project → teaser → signup → full analysis → email to architect → architect auto-registered via shared link. Also: plumbing inspections shared table, 3 review metrics tables, 4 tier1 knowledge files, ref table wiring. 6 parallel agents, 2,304 tests passing, 320+ new tests.

**termCC already verified:** 15/15 staging QA PASS (health, funnel, analysis, beta request, search). Schema migrated. All 4 new datasets ingested. PgConnWrapper cursor bug found and fixed. Plumbing inspections persisting (1.07M total).

**What DeskRelay needs to verify:** Visual rendering, end-to-end user flows, and prod promotion.

## Setup
cd /Users/timbrenneman/AIprojects/sf-permits-mcp

## Rules
- NO code changes. QA artifacts only.
- If a check fails, document it. Do NOT attempt fixes.

---

## Part 1: Staging Visual Checks
Target: https://sfpermits-ai-staging-production.up.railway.app

### Health (already verified by termCC — quick reconfirm)
1. [ ] `curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool` → status=ok, 54 tables, inspections > 1M

### Homeowner Funnel (Sprint 56E) — VISUAL
2. [ ] Landing page: "Planning a project?" card renders cleanly — textarea + neighborhood dropdown visible
3. [ ] Landing page: "Got a violation?" card renders with distinct styling alongside project card
4. [ ] Mobile (375px viewport): both cards stack to single column, text readable
5. [ ] Submit "kitchen remodel in the Mission" to /analyze-preview → preview page renders with review path + timeline
6. [ ] Preview: kitchen/bath fork shows side-by-side comparison (OTC vs In-House)
7. [ ] Preview: locked cards (fees, docs, risk) show gradient fade with signup CTA
8. [ ] Search with `?context=violation`: GET /search?q=market+street&context=violation → page loads, check for violation context banner or reordering

### Shareable Analysis (Sprint 56D) — VISUAL
9. [ ] Run analysis: go to landing, enter "bathroom remodel, keep existing layout" in textarea, submit → full analysis loads
10. [ ] Share bar visible below results: "Email to your team", "Copy share link", "Copy all" buttons
11. [ ] Click "Copy share link" → clipboard gets URL like /analysis/<uuid>
12. [ ] Open the shared URL in incognito/new tab (no login) → public analysis page renders with tab layout
13. [ ] Public analysis page: "Try sfpermits.ai free" CTA visible at bottom
14. [ ] Visit /analysis/fake-nonexistent-id → 404 page (not 500 crash)

### Three-Tier Signup (Sprint 56D) — VISUAL
15. [ ] GET /beta-request → form renders with email, name, "What brings you to sfpermits.ai?" textarea
16. [ ] Honeypot field (`website`) is NOT visible to users (inspect DOM — should be display:none)
17. [ ] Submit beta request with valid email → confirmation message
18. [ ] GET /auth/login?referral_source=shared_link&analysis_id=test → login page loads normally
19. [ ] As admin (POST /auth/test-login): GET /admin/beta-requests → queue page loads with Approve/Deny buttons

### Onboarding + Empty States (Sprint 56E) — VISUAL
20. [ ] After first login: welcome banner appears (dismissable)
21. [ ] GET /brief (no watches) → empty state: "No morning brief yet" with search CTA
22. [ ] GET /portfolio (empty) → empty state: "Your portfolio is empty" with search CTA

Screenshots to: qa-results/screenshots/sprint56-deskrelay-staging/

---

## Part 2: Promotion Ceremony
(Only if all staging checks PASS)

```bash
git checkout prod && git merge main && git push origin prod
```

Wait 120s for prod deploy. Then verify deploy succeeded:
```bash
railway service link sfpermits-ai && railway deployment list | head -3
```

Post-promotion commands:
```bash
SECRET="f6564fc90fcd615e7192789d51bd83806216951a16d1ee8ac15975413a437758"

# Schema migration (creates new tables)
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/migrate-schema

# Seed reference tables
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/seed-references

# Ingest new datasets (run in order, smallest first)
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/ingest-planning-review-metrics
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/ingest-permit-issuance-metrics
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/ingest-permit-review-metrics
curl -s -X POST -H "Authorization: Bearer $SECRET" https://sfpermits-ai-production.up.railway.app/cron/ingest-plumbing-inspections
```

NOTE: Each ingest takes 10s-3min. Wait for each to return before starting the next.

---

## Part 3: Prod Checks
Target: https://sfpermits-ai-production.up.railway.app

23. [ ] Health endpoint: status=ok, 54 tables, inspections > 1M
24. [ ] Landing page: "Planning a project?" + "Got a violation?" both visible
25. [ ] /analyze-preview with "kitchen remodel" → preview with fork comparison
26. [ ] /beta-request → form loads
27. [ ] /analysis/nonexistent → 404
28. [ ] Search "75 robin hood dr" → results appear
29. [ ] Click through to property report → page loads
30. [ ] /auth/login → login page loads

Screenshots to: qa-results/screenshots/sprint56-deskrelay-prod/

---

## Part 4: Close
Results to: qa-results/sprint56-deskrelay-results.md (staging + prod results in one file)
Lightweight CHECKCHAT: commit QA artifacts, push, update Chief.
