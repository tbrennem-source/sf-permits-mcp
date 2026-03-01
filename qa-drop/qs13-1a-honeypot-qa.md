# QA Script: QS13-1A — Honeypot Middleware + Capture Routes + Scope Guard

**Session:** QS13 Agent 1A
**Branch:** worktree-agent-a083ce57
**Date:** 2026-02-28

---

## Pre-flight

- [ ] `source .venv/bin/activate`
- [ ] `pytest tests/test_honeypot.py -v` — all 18 tests PASS

---

## 1. HONEYPOT_MODE middleware

### 1.1 Redirect behavior (HONEYPOT_MODE=1)

Run app with `HONEYPOT_MODE=1` set in env or use test client:

- [ ] `GET /search` → 302 redirect to `/join-beta?ref=search`
  **PASS**: Location header contains `/join-beta`
  **FAIL**: Returns 200 or redirects elsewhere

- [ ] `GET /methodology` → 302 redirect to `/join-beta?ref=methodology`
  **PASS**: Location header contains `/join-beta`
  **FAIL**: Returns 200

- [ ] `GET /` (landing) → 200, NOT redirected
  **PASS**: Status 200, no `/join-beta` in Location
  **FAIL**: Redirected

- [ ] `GET /join-beta` → 200, NOT redirected
  **PASS**: Status 200
  **FAIL**: Redirect loop

- [ ] `GET /health` → 200 or 204, NOT redirected
  **PASS**: No `/join-beta` redirect
  **FAIL**: Redirected

- [ ] `GET /admin/` → not redirected to `/join-beta` (may redirect to login)
  **PASS**: Location does not contain `/join-beta`
  **FAIL**: Redirected to `/join-beta`

### 1.2 Normal mode (HONEYPOT_MODE=0)

- [ ] `GET /search` → normal response (200 or search page), no `/join-beta` redirect
  **PASS**: No `/join-beta` in Location
  **FAIL**: Redirected

---

## 2. /join-beta GET

- [ ] Navigate to `/join-beta` — form renders with email, name, role select, address fields
  **PASS**: Form visible with all 4 fields
  **FAIL**: Error or blank page

- [ ] Navigate to `/join-beta?ref=search` — form renders, ref hidden field present
  **PASS**: `<input name="ref" value="search">` in source
  **FAIL**: Field missing

---

## 3. /join-beta POST — spam guard

- [ ] POST with `website=http://spam.com` (honeypot filled) → 200 empty response, no redirect
  **PASS**: Status 200, no DB insert for bot's email
  **FAIL**: Redirected to thanks or error

---

## 4. /join-beta POST — happy path

- [ ] POST `email=test@example.com, name=Test, role=homeowner` → redirects to `/join-beta/thanks`
  **PASS**: 302 to `/join-beta/thanks`
  **FAIL**: Error or no redirect

- [ ] POST with empty/invalid email `email=notanemail` → 200 with error message
  **PASS**: Error text visible
  **FAIL**: Redirect or silent

---

## 5. /join-beta/thanks

- [ ] Navigate to `/join-beta/thanks` — shows queue position
  **PASS**: "on the list" text visible
  **FAIL**: Error or blank

---

## 6. Intent scope guard

```python
from src.tools.intent_router import classify

# Should NOT be out_of_scope
assert classify("remodel kitchen permit").intent != "out_of_scope"
assert classify("123 Main St").intent != "out_of_scope"
assert classify("hello").intent != "out_of_scope"
assert classify("check my plans").intent == "validate_plans"

# Should be out_of_scope
assert classify("weather forecast in Oakland California").intent == "out_of_scope"
assert classify("how do I get a dog license in san francisco").intent == "out_of_scope"
```

- [ ] All assertions pass
  **PASS**: All correct
  **FAIL**: Any assertion fails

---

## 7. DESIGN TOKEN COMPLIANCE

- [ ] Run: `python scripts/design_lint.py --files web/templates/join_beta.html web/templates/join_beta_thanks.html --quiet`
- [ ] Score: 5/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: --mono for labels, --sans for body text
- [ ] Components: custom (not token), but token CSS vars used throughout

---

## Edge Cases

- [ ] POST with rate limit exceeded (3+ attempts from same IP) → 200 with error message
  **PASS**: Rate limit error displayed
  **FAIL**: Request accepted

- [ ] HONEYPOT_MODE=1 with `/cron/status` → not redirected (cron exempt)
  **PASS**: Passes through
  **FAIL**: Redirected
