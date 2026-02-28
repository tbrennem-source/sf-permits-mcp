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

---

# CHANGELOG — T2 Sprint 87

## 2B: Accept/Reject/Note log in admin feedback widget (QS10 T2-B)

### Added
- `POST /admin/qa-decision` endpoint in `web/routes_admin.py` — admin-only route that records Tim's visual QA verdict (accept/reject/note) for a pending review item
- qa-review-panel in `web/templates/fragments/feedback_widget.html` — admin-only section inside the feedback modal with pending badge, context display, note textarea, and three verdict buttons (Accept/Note/Reject) wired to HTMX
- `window.qaLoadItem(item)` global JS function to populate the panel's hidden fields from a pending review item
- `qa-results/review-decisions.json` — empty JSON array; append-only storage for all Tim verdicts (training data)
- Atomic write helper `_atomic_write_json` (tmp + rename) to prevent partial writes
- Pending entry removal from `qa-results/pending-reviews.json` on matching page + dimension + sprint
- `docs/DESIGN_COMPONENT_LOG.md` — logged `qa-review-panel` component (QS10 T2-B)

### Tests
- `tests/test_accept_reject_log.py` — 6 tests, all passing
  - Auth gate (403 for non-admins)
  - Accept writes review-decisions.json with correct fields
  - Reject appends to existing file
  - Invalid verdict returns 400
  - Missing file handled gracefully
  - Matching pending-reviews.json entry removed on decision

### Design
- Design lint score: 5/5 (no violations)
- No new CSS classes; uses only token classes (`action-btn`, `form-input`) and CSS custom properties
