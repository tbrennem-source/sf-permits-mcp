# Sprint 57 — termRelay: Visual QA + Staging → Promotion → Prod

## Context
Sprint 57.0 implements data foundation improvements: entity resolution for electrical/plumbing contacts, velocity refresh with trade permit exclusion, neighborhood backfill via self-join, multi-role entity tracking, and license normalization.

**This sprint replaces DeskRelay with automated visual QA.** All visual checks run via `scripts/visual_qa.py` using headless Playwright — no manual browser verification needed.

## Prerequisites
```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
source .venv/bin/activate

# Set auth for staging (required for auth/admin page screenshots)
export TESTING=true
export TEST_LOGIN_SECRET=$(railway variables --json | python3 -c "import sys,json; print(json.load(sys.stdin)['TEST_LOGIN_SECRET'])")
```

## Rules
- NO code changes except visual_qa.py bug fixes if a step mechanically fails
- All results go to `qa-results/`
- If staging is down/deploying, wait and retry — do not skip

---

## Part 0: Fix Staging (if needed)
Target: https://sfpermits-ai-staging-production.up.railway.app

Staging may be unhealthy due to zombie DB transactions or stale deploys after Sprint 57.0 merge.

**Step 0a — Check health:**
```bash
curl -s --max-time 15 https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool
```

**If staging is DOWN or returning errors:**

Option 1 — Force rebuild via empty commit:
```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git commit --allow-empty -m "chore: trigger staging rebuild"
git push origin main
# Wait ~120s for Railway to rebuild
```

Option 2 — Kill zombie transactions (if health returns but tables show errors):
```bash
CRON_SECRET=$(railway service link sfpermits-ai-staging && railway variables --json | python3 -c "import sys,json; print(json.load(sys.stdin)['CRON_SECRET'])")
curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-staging-production.up.railway.app/cron/migrate
```

**Do not proceed to Part 1 until staging health returns status=ok.**

---

## Part 1: Staging Health
Target: https://sfpermits-ai-staging-production.up.railway.app

1. [ ] Health check passes:
```bash
curl -s https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool
```
PASS criteria: status=ok, tables >= 54

2. [ ] Test login works:
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d "{\"email\":\"test-admin@sfpermits.ai\",\"secret\":\"$TEST_LOGIN_SECRET\"}" \
  https://sfpermits-ai-staging-production.up.railway.app/auth/test-login
```
PASS criteria: HTTP 200

---

## Part 2: Staging Visual QA (Golden Capture)
Capture golden baselines for all 21 pages x 3 viewports.

3. [ ] Run visual QA with golden capture:
```bash
python scripts/visual_qa.py \
  --url https://sfpermits-ai-staging-production.up.railway.app \
  --sprint sprint57-staging \
  --capture-goldens
```
PASS criteria: 0 FAIL, all pages captured (63 total = 21 pages x 3 viewports)

If pages fail with timeout: retry individually with `--pages <slugs>` flag.
If auth pages show "skipped": verify TEST_LOGIN_SECRET is set, retry.

4. [ ] Review filmstrips — quick visual scan:
- Open `qa-results/filmstrips/sprint57-staging-desktop.png`
- Open `qa-results/filmstrips/sprint57-staging-mobile.png`
- Open `qa-results/filmstrips/sprint57-staging-tablet.png`

PASS criteria: No blank pages, no error pages, no obvious layout breaks visible in filmstrip.

5. [ ] Run UX evaluation (spawn qa-ux-designer agent):
Point it at `qa-results/goldens/` and `qa-results/filmstrips/sprint57-staging-*.png`.
Agent writes results to `qa-results/sprint57-staging-ux-evaluation.md`.
PASS criteria: No page scores below 2.0. Flag items for follow-up but don't block promotion.

---

## Part 3: Promotion Ceremony
(Only proceed if Part 2 has 0 FAIL on visual QA)

```bash
git checkout prod && git merge main && git push origin prod
```

Wait ~120s for Railway to deploy. Verify:
```bash
curl -s --max-time 30 https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```

6. [ ] Prod deploy succeeded: status=ok

### Post-promotion (if Sprint 57 adds schema/data changes):
```bash
CRON_SECRET=$(railway service link sfpermits-ai && railway variables --json | python3 -c "import sys,json; print(json.load(sys.stdin)['CRON_SECRET'])")

# Schema migration
curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/migrate-schema

# Seed references
curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" \
  https://sfpermits-ai-production.up.railway.app/cron/seed-references
```

---

## Part 4: Prod Visual QA
Target: https://sfpermits-ai-production.up.railway.app

7. [ ] Health check:
```bash
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
```
PASS criteria: status=ok

8. [ ] Set prod auth (if available — prod may not have TESTING=true):
```bash
# Only if prod has TESTING enabled:
export TEST_LOGIN_SECRET=$(railway service link sfpermits-ai && railway variables --json | python3 -c "import sys,json; print(json.load(sys.stdin).get('TEST_LOGIN_SECRET',''))")
```

9. [ ] Run visual QA against prod:
```bash
python scripts/visual_qa.py \
  --url https://sfpermits-ai-production.up.railway.app \
  --sprint sprint57-prod \
  --capture-goldens
```
PASS criteria: 0 FAIL on public pages. Auth/admin pages may be skipped if prod doesn't have TESTING.

10. [ ] Review prod filmstrips for obvious issues.

---

## Part 5: Staging vs Prod Divergence Check
Compare staging and prod screenshots for unexpected differences.

11. [ ] Run divergence comparison:
```bash
# Use staging goldens as baseline, compare prod screenshots against them
python scripts/visual_qa.py \
  --url https://sfpermits-ai-production.up.railway.app \
  --sprint sprint57-divergence
```
This compares prod screenshots against the staging goldens captured in Part 2.

PASS criteria: Public pages show < 1% diff (same code, same data = identical rendering).
Expected divergence: staging banner present on staging but not prod — that's OK.
Unexpected divergence: layout differences, missing elements, broken pages — FAIL.

12. [ ] Document divergences:
- Expected: staging environment banner, any data differences
- Unexpected: any layout/rendering differences → create Chief task

---

## Part 6: CHECKCHAT
Results file: `qa-results/sprint57-termrelay-results.md`

### Structure:
```markdown
# Sprint 57 termRelay Results

## Staging Visual QA
- Total: X PASS / Y FAIL / Z NEW
- Filmstrips reviewed: [PASS/FAIL]
- UX evaluation: [summary + flagged items]

## Promotion
- Merge main → prod: [timestamp]
- Deploy status: [OK/FAIL]
- Post-promotion commands: [ran/skipped]

## Prod Visual QA
- Total: X PASS / Y FAIL / Z NEW
- Public pages: [all OK / issues]

## Staging ↔ Prod Divergence
- Expected divergences: [list]
- Unexpected divergences: [list or "none"]

## Follow-up Tasks
- [any new Chief tasks created]
```

Commit QA artifacts, push to main, update Chief with session note.
