# QA Results: Security Audit Tooling (Sprint 74-3)

**Date:** 2026-02-27
**Agent:** 74-3
**Script:** qa-drop/security-audit-qa.md

---

| Step | Check | Result | Notes |
|------|-------|--------|-------|
| 1 | File existence: scripts/security_audit.py | PASS | File exists |
| 1 | File existence: .bandit | PASS | File exists |
| 1 | File existence: .github/workflows/security.yml | PASS | File exists |
| 2 | pytest tests/test_sprint_74_3.py | PASS | 29 passed, 0 failed |
| 3 | Module import (main, run_bandit, run_pip_audit, build_report) | PASS | All 4 functions present |
| 4 | Graceful degradation — tools not on PATH | PASS | Script exits 0, SKIPPED in output for both tools |
| 5 | Report file created and well-formed | PASS | qa-results/security-audit-latest.md created with proper headers |
| 6 | .bandit config has [bandit], B101 skip, tests exclusion | PASS | All 3 present |
| 7 | .github/workflows/security.yml valid YAML | PASS | Parses successfully |
| 8 | Workflow has cron 0 6 * * 0 and push to main | PASS | Both triggers present |
| 9 | Exit code 1 on mocked HIGH issue | PASS | Verified via pytest TestMainExitCode::test_main_returns_1_on_high_issue |
| 10 | Invalid JSON from bandit handled gracefully | PASS | Verified via pytest TestRunBanditMocked::test_bandit_invalid_json_sets_error |

**Overall: PASS — 12/12 checks passed**

## Regression check

Pre-existing failures (not caused by Sprint 74-3):
- tests/test_permit_lookup.py::test_permit_lookup_address_suggestions — DuckDB fixture issue (pre-existing)
- tests/test_reference_tables.py::TestCronEndpointAuth::test_cron_seed_references_blocked_on_web_worker — 403 vs 404 (pre-existing)

Sprint 74-3 tests: 29 passed, 0 failed.
