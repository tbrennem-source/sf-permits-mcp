# QA Results: Sprint 61D — Permit Change Email Notifications

**Session:** sprint61d-notifications
**Date:** 2026-02-25
**Agent:** Agent D (worktree-agent-a2655534)
**Script:** qa-drop/sprint61d-notifications-qa.md

---

## CLI QA Results

| Step | Description | Result |
|------|-------------|--------|
| 1 | Module imports cleanly | PASS |
| 2 | MAX_INDIVIDUAL_EMAILS == 10 | PASS |
| 3 | Unsubscribe token deterministic, 32 chars, unique per user | PASS |
| 4 | Dev-mode send (no SMTP_HOST) returns True | PASS |
| 5 | Empty change list returns zero stats | PASS |
| 6 | pytest 36/36 tests pass | PASS |
| 7 | Migration registry has 13 entries, sprint61d_notify_columns is last | PASS |
| 8 | Schema includes notify_permit_changes and notify_email columns | PASS |
| 9 | /account/notify-permit-changes route registered in Flask app | PASS |
| 10a | _row_to_user maps notify columns from 19-field row | PASS |
| 10b | _row_to_user returns safe defaults for pre-migration 17-field row | PASS |
| 11 | Template files exist with required content (account, unsubscribe, table) | PASS |

**Total CLI: 12/12 PASS**

---

## Browser QA Steps (DeskRelay HANDOFF)

The following visual checks require a running dev server and an authenticated session. Escalate to DeskCC/DeskRelay:

| Check | Description | Verification Method |
|-------|-------------|---------------------|
| B1 | Account page shows notification checkbox in Email Preferences | Navigate to /account, scroll to Email Preferences |
| B2 | Checkbox toggle persists after Save (HTMX response) | Check/uncheck + save + reload |
| B3 | Digest threshold: >10 changes uses digest path | Verified by unit test test_send_digest_for_large_batch |
| B4 | Unsubscribe link in notification email points to /account | View email template or send test email |

---

## Regression Check

Full test suite (excluding network tests): **2943 passed, 0 failed**, 20 skipped (pre-existing SODA network timeout exclusion on test_tools.py).

4 tests were updated to reflect new migration count (12→13) and new last migration name (neighborhood_backfill→sprint61d_notify_columns). These are valid maintenance updates, not regressions.

---

## Notes

- All functionality is in dev mode (SMTP_HOST not set locally). Production behavior requires SMTP env vars on Railway.
- Notification call in nightly_changes.py is wrapped in try/except — SMTP failures are non-fatal.
- The nested worktree context (sprint-58 > agent-a2655534) required careful absolute path management during build.
