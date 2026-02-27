# Changelog — Sprint 74-3: Security Audit Tooling

## Added

### scripts/security_audit.py
- New security audit script that runs bandit (static analysis) and pip-audit (dependency vulnerability scan)
- Parses JSON output from both tools; counts issues by severity (HIGH/MEDIUM/LOW)
- Generates combined markdown report written to `qa-results/security-audit-latest.md`
- Exits 0 when no HIGH severity issues; exits 1 when HIGH issues are found
- Graceful degradation: if bandit or pip-audit is not installed, prints a warning and skips that check rather than crashing
- Handles subprocess timeouts, missing tools (FileNotFoundError), and malformed JSON gracefully
- Severity inference for pip-audit output: RCE/critical keywords in description trigger HIGH classification

### .bandit
- New bandit configuration file at project root
- Excludes `tests/`, `.venv/`, `build/`, `dist/`, `.git/` from static analysis
- Skips B101 (assert_used) — assert statements are acceptable in test code and debug paths
- Targets `src/` and `web/` directories

### .github/workflows/security.yml
- New GitHub Actions workflow for automated security scanning
- Triggers: push to `main` + weekly cron schedule (Sunday 06:00 UTC)
- Installs both `bandit` and `pip-audit` before running
- Uses `continue-on-error: true` on the audit step so the report artifact is always uploaded
- Uploads `qa-results/security-audit-latest.md` as an artifact with 90-day retention
- Separate "Fail job if HIGH issues found" step after upload — ensures artifact is always available for review even when CI fails

### tests/test_sprint_74_3.py
- 29 tests covering all three new files
- `TestSecurityAuditImport`: module importability, file existence
- `TestRunCommand`: successful command, missing tool handling
- `TestRunBanditMocked`: HIGH/MEDIUM/LOW counting, no-issues path, not-installed path, invalid JSON error handling
- `TestRunPipAuditMocked`: vulnerability parsing, no-vulns path, not-installed path
- `TestBuildReport`: markdown output structure, PASS/FAIL status, SKIPPED tools, section headers
- `TestMainExitCode`: exit 0 on clean run, exit 1 on HIGH issue
- `TestBanditConfig`: file existence, B101 skip, tests exclusion, section header
- `TestSecurityWorkflow`: YAML validity, cron schedule, push trigger, continue-on-error, artifact upload, tool installation
- Note: PyYAML parses `on:` as boolean `True` — cron/push trigger tests use raw text matching to avoid this YAML quirk
