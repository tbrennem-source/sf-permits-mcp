## SUGGESTED SCENARIO: security audit runs without crashing when tools are missing
**Source:** scripts/security_audit.py — run_bandit / run_pip_audit graceful degradation
**User:** admin
**Starting state:** CI environment where bandit and/or pip-audit are not installed
**Goal:** Run the security audit script and get a usable report even when tools are absent
**Expected outcome:** Script completes (exit 0), report clearly marks missing tools as SKIPPED, no stack trace or unhandled exception
**Edge cases seen in code:** tool not on PATH returns rc=-1 from run_command; check_tool_available guards both scanners independently
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: security audit exits 1 on HIGH severity bandit finding
**Source:** scripts/security_audit.py — main() exit code logic
**User:** admin
**Starting state:** Codebase has a bandit HIGH severity issue (e.g., subprocess shell=True)
**Goal:** CI job fails and draws attention to the finding
**Expected outcome:** Script exits with code 1; report contains "FAIL" status; HIGH issue details present with filename, line number, test ID
**Edge cases seen in code:** bandit exits 1 even when only LOW issues found — exit code alone cannot distinguish severity; script re-parses JSON counts
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: security audit produces artifact on every run including failures
**Source:** .github/workflows/security.yml — continue-on-error + upload-artifact with if: always()
**User:** admin
**Starting state:** Security audit finds HIGH issues (audit step returns exit 1)
**Goal:** Review the detailed report even when the CI job is marked failed
**Expected outcome:** GitHub Actions artifact "security-audit-report-<run_id>" is uploaded and available for download; report contains full issue details
**Edge cases seen in code:** continue-on-error on audit step + explicit fail step pattern ensures report upload always runs before job marks failed
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: weekly security scan runs on Sunday without manual trigger
**Source:** .github/workflows/security.yml — schedule cron trigger
**User:** admin
**Starting state:** No new commits; cron fires on schedule
**Goal:** Catch newly disclosed vulnerabilities in dependencies between development cycles
**Expected outcome:** Workflow runs at 06:00 UTC Sunday, both bandit and pip-audit execute against current installed packages, report artifact is stored for 90 days
**CC confidence:** medium
**Status:** PENDING REVIEW
