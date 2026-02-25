# Sprint 54 QA Script
## Session: sprint54 | Date: 2026-02-24

### Prerequisites
- Deploy to staging complete (push to main triggers Railway build)
- TESTING=1 and TEST_LOGIN_SECRET configured on staging

---

### QA-1: /cron/migrate endpoint (Amendment C)
1. `curl -s -X POST -H "Authorization: Bearer $CRON_SECRET" https://sfpermits-ai-production.up.railway.app/cron/migrate | python3 -m json.tool`
2. **PASS** if response contains `"ok": true` and lists all 8 migrations
3. **FAIL** if 403 or any migration has `"ok": false`

### QA-2: Test-login admin sync (Amendment D)
1. POST to `/auth/test-login` with `{"secret": "$TEST_LOGIN_SECRET", "email": "test-admin@sfpermits.ai"}`
2. Verify response contains `"is_admin": true`
3. POST again with `{"secret": "$TEST_LOGIN_SECRET", "email": "homeowner@test.example.com"}`
4. Verify response contains `"is_admin": false`
5. **PASS** if admin status matches email pattern for both
6. **FAIL** if admin status is wrong for either

### QA-3: Report archival (Amendment G)
1. Verify `reports/sprint53/SWARM-REPORT.md` exists
2. Verify `reports/sprint53/CHECKCHAT-A.md` through `CHECKCHAT-D.md` exist
3. Verify `reports/sprint53b/SPRINT-53B-REPORT.md` exists
4. Verify `reports/sprint53b/CHECKCHAT-53B.md` exists
5. Verify `reports/sprint53b/DIAGNOSTIC-53B.md` exists
6. Verify old locations (repo root) no longer have these files
7. **PASS** if all files moved correctly
8. **FAIL** if any file missing or duplicated

### QA-4: Route manifest (Q1)
1. Run `python scripts/discover_routes.py`
2. Verify `siteaudit_manifest.json` is valid JSON
3. Verify `total_routes` >= 100
4. Verify `auth_summary` has all 4 keys (public, auth, admin, cron)
5. Verify user_journeys has 4 entries
6. **PASS** if all checks pass
7. **FAIL** if manifest is invalid or missing data

### QA-5: Agent definitions (Q2)
1. Verify 15 new files in `.claude/agents/`
2. Verify 5 qa-*.md files exist
3. Verify 6 persona-*.md files exist (4 active + 2 stubs)
4. Verify 4 deskrelay-*.md files exist
5. Verify 0 session-*.md files remain
6. **PASS** if file count matches
7. **FAIL** if any missing or old files remain

### QA-6: Signal pipeline Postgres compatibility (Q3)
1. Run `python -m pytest tests/test_signals_pipeline.py -v`
2. Verify all 25 tests pass
3. Check that `src/signals/pipeline.py` imports BACKEND
4. Check that `src/signals/detector.py` imports BACKEND
5. **PASS** if tests pass and imports present
6. **FAIL** if any test fails

### QA-7: Data ingest expansion (Q4)
1. Run `python -m pytest tests/test_ingest_electrical_plumbing.py -v`
2. Verify all 32 tests pass
3. Check `src/ingest.py` DATASETS dict has `electrical_permits` and `plumbing_permits`
4. **PASS** if tests pass and datasets configured
5. **FAIL** if any test fails

### QA-8: Staging health check
1. `curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool`
2. **PASS** if response returns JSON with status info
3. **FAIL** if 500 or unreachable

### QA-9: Full test suite
1. `python -m pytest tests/ -q --ignore=tests/test_tools.py`
2. **PASS** if 1770+ tests pass with 0 failures
3. **FAIL** if any non-network test fails

### QA-10: prod branch exists
1. `git branch -a | grep prod`
2. **PASS** if `remotes/origin/prod` exists
3. **FAIL** if missing
