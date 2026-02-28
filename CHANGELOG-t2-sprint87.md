## QS10 T2-A — Admin Persona Impersonation (2026-02-28)

### Added
- `web/admin_personas.py` — 7 QA personas (anonymous new, anonymous returning, free auth, beta empty, beta active, power user, admin reset) with `get_persona()` and `apply_persona()` helpers
- `POST /admin/impersonate` endpoint in `web/routes_admin.py` — admin-only; injects persona state into Flask session; returns HTMX status snippet
- `GET /admin/reset-impersonation` endpoint in `web/routes_admin.py` — admin-only escape hatch; clears all impersonation session keys and redirects
- Persona panel in `web/templates/fragments/feedback_widget.html` — visible only to admins; dropdown lists all 7 personas; Apply button uses HTMX; Reset link clears state; active persona shown in session-aware status line
- `tests/test_admin_impersonation.py` — 6 tests covering auth gate, persona application, unknown persona error, reset flow, required key validation, and session state isolation

### Design
- Design lint score: 5/5 (no violations)
- All CSS uses token variables only (no inline hex)
- Font roles: `--mono` for labels and status, token components `form-input`, `action-btn`, `ghost-cta`
