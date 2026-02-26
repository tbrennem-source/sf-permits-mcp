# QA Script: Sprint 61D — Permit Change Email Notifications

**Feature:** Permit change email notification system (individual + digest)
**Session:** sprint61d-notifications
**Date:** 2026-02-25

---

## CLI / Unit QA Steps

### 1. Module imports cleanly
```bash
cd /path/to/repo && source .venv/bin/activate
python -c "from web.email_notifications import send_permit_notifications, MAX_INDIVIDUAL_EMAILS, generate_unsubscribe_token; print('OK')"
```
PASS: prints "OK"
FAIL: ImportError or missing symbol

### 2. MAX_INDIVIDUAL_EMAILS is 10
```bash
python -c "from web.email_notifications import MAX_INDIVIDUAL_EMAILS; assert MAX_INDIVIDUAL_EMAILS == 10, MAX_INDIVIDUAL_EMAILS; print('OK')"
```
PASS: prints "OK"
FAIL: assertion error or wrong value

### 3. Unsubscribe token is deterministic and 32 chars
```bash
python -c "
from web.email_notifications import generate_unsubscribe_token
t1 = generate_unsubscribe_token(1, 'user@example.com')
t2 = generate_unsubscribe_token(1, 'user@example.com')
assert t1 == t2, 'not deterministic'
assert len(t1) == 32, f'wrong length: {len(t1)}'
t3 = generate_unsubscribe_token(2, 'user@example.com')
assert t1 != t3, 'different users should differ'
print('OK')
"
```
PASS: prints "OK"
FAIL: assertion failure

### 4. Dev-mode email send (no SMTP_HOST) returns True
```bash
python -c "
from unittest.mock import patch
from web.email_notifications import _send_email_sync
with patch('web.email_notifications.SMTP_HOST', None):
    result = _send_email_sync('test@example.com', 'Subject', '<p>body</p>')
assert result is True, result
print('OK')
"
```
PASS: prints "OK"
FAIL: returns False or raises

### 5. send_permit_notifications with empty list returns zero stats
```bash
python -c "
from web.email_notifications import send_permit_notifications
stats = send_permit_notifications([])
assert stats['emails_sent'] == 0
assert stats['users_notified'] == 0
print('OK')
"
```
PASS: prints "OK"
FAIL: non-zero stats or exception

### 6. pytest suite — Sprint 61D tests all pass
```bash
python -m pytest tests/test_sprint61d_notifications.py -v --tb=short
```
PASS: 36 passed, 0 failed
FAIL: any failures

### 7. Migration registry includes sprint61d_notify_columns
```bash
python -c "
from scripts.run_prod_migrations import MIGRATIONS
names = [m.name for m in MIGRATIONS]
assert 'sprint61d_notify_columns' in names, names
assert names[-1] == 'sprint61d_notify_columns', f'not last: {names[-1]}'
print('OK — 13 migrations, sprint61d_notify_columns is last')
"
```
PASS: prints the OK line
FAIL: assertion error

### 8. Schema includes notify columns in init_user_schema
```bash
python -c "
from src.db import init_user_schema
import inspect
src = inspect.getsource(init_user_schema)
assert 'notify_permit_changes' in src
assert 'notify_email' in src
print('OK')
"
```
PASS: prints "OK"
FAIL: assertion error

### 9. notify_permit_changes route is registered in Flask app
```bash
python -c "
from web.app import app
rules = {r.rule for r in app.url_map.iter_rules()}
assert '/account/notify-permit-changes' in rules, rules
print('OK')
"
```
PASS: prints "OK"
FAIL: route missing

### 10. _row_to_user handles notify columns
```bash
python -c "
from web.auth import _row_to_user
# Row with notify columns (19 fields)
row = (1, 'u@e.com', 'Alice', 'consultant', 'Acme', None,
       True, False, True, 'daily', None, '123', 'Main St',
       'free', None, 'invited', None, True, 'alt@e.com')
user = _row_to_user(row)
assert user['notify_permit_changes'] is True
assert user['notify_email'] == 'alt@e.com'
print('OK notify columns')
# Row without notify columns (17 fields — pre-migration)
row_old = (1, 'u@e.com', 'Alice', 'consultant', 'Acme', None,
           True, False, True, 'daily', None, '123', 'Main St',
           'free', None, 'invited', None)
user_old = _row_to_user(row_old)
assert user_old['notify_permit_changes'] is False
assert user_old['notify_email'] is None
print('OK pre-migration fallback')
"
```
PASS: both OK lines printed
FAIL: KeyError or wrong values

### 11. Template files exist and contain required content
```bash
python -c "
import os
base = os.path.join(os.path.dirname(os.path.abspath('.')), 'web', 'templates')
# Check from repo root
import subprocess
result = subprocess.run(
    ['python', '-c', '''
import os
base = \"web/templates\"
for fn, checks in [
    (\"notification_email.html\", [\"account\", \"unsubscribe\"]),
    (\"notification_digest_email.html\", [\"account\", \"unsubscribe\", \"<table\", \"Permit\", \"Address\", \"Change\"]),
]:
    path = os.path.join(base, fn)
    assert os.path.exists(path), f\"Missing: {path}\"
    content = open(path).read().lower()
    for check in checks:
        assert check.lower() in content, f\"{fn} missing: {check}\"
print(\"OK\")
'''],
    capture_output=True, text=True
)
print(result.stdout or result.stderr)
"
```
PASS: prints "OK"
FAIL: missing file or missing required content

---

## Browser / UI QA Steps (DeskRelay)

These require a running dev server. Start with:
```bash
source .venv/bin/activate && python -m web.app &
```

### B1. Account page shows notification checkbox
- Navigate to /account (must be logged in)
- Scroll to "Email Preferences" section
PASS: Checkbox labeled "Email me when watched permits change status" is visible
FAIL: Checkbox is absent

### B2. Notification checkbox persists toggle
- Check/uncheck the "Email me when watched permits change status" checkbox
- Click Save
- Reload page
PASS: Checkbox state persisted (HTMX response shows On/Off status)
FAIL: State not saved, error shown

### B3. Digest threshold: >10 changes routes to digest
- (Unit-test verified, no live trigger without DB data)
- PASS via test_send_digest_for_large_batch unit test

### B4. Unsubscribe link in email template points to /account
- Open web/templates/notification_email.html in browser or text editor
PASS: href references "/account" or unsubscribe route
FAIL: No account reference found

---

## Edge Cases Verified by Unit Tests

- Empty change list → no emails, zero stats (test_send_notifications_empty_changes)
- No opted-in users → no emails (test_send_notifications_no_opted_in_users)
- SMTP returns False → error counted, pipeline continues (test_smtp_failure_does_not_crash)
- SMTP raises exception → error counted, pipeline continues (test_smtp_exception_does_not_crash)
- change with block=None/lot=None → skipped (test_group_changes_skips_no_block_lot)
- Pre-migration row (17 fields) → notify_permit_changes=False, notify_email=None (test_notify_field_defaults_when_missing)
