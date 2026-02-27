# CHANGELOG — QS4-D (Security + Beta Launch Polish)

## 2026-02-26 — QS4-D

### Added
- **CSP-Report-Only header updated** with external CDN sources (unpkg, jsdelivr, Google Fonts, PostHog) — monitors violations without breaking pages
- **CSRF protection middleware** — lightweight implementation in `web/security.py`, no flask-wtf dependency
  - Validates `csrf_token` form field or `X-CSRFToken` header on POST/PUT/PATCH/DELETE
  - Skips GET/HEAD/OPTIONS, cron endpoints, `/api/csp-report`, `/auth/test-login`, Bearer-auth requests
  - Disabled in TESTING mode
  - `init_security(app)` registered after blueprint registration
- **CSRF tokens added to templates**: `auth_login.html`, `account.html`, `consultants.html`, `account_settings.html`, `account_admin.html`, `feedback_widget.html`
- **HTMX CSRF support**: `hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'` on body tags in `account.html` and `consultants.html`
- **PostHog verification**: server-side tracking confirmed working, client-side JS already present in landing/index
- **28 new tests** in `tests/test_qs4_d_security.py`
- **3 scenarios** appended to `scenarios-pending-review-qs4-d.md`

### Technical Notes
- CSP-Report-Only includes `'unsafe-inline'` as fallback alongside nonces — when violations reach zero, swap to enforced
- CSRF token is 64 hex chars (32 bytes), stored in Flask session, persists across requests
- The `/api/csp-report` endpoint was already implemented pre-QS4
