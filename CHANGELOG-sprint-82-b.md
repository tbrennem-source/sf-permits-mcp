## Sprint 82-B — Admin System Health Panel

### Added
- **`/admin/health` endpoint** (web/routes_admin.py): New HTMX fragment endpoint returning a 3-card system health panel. Admin-only (403 for non-admins). Uses `get_pool_health()` from `src/db.py`, `get_soda_cb_status()` from `src/soda_client.py`, and direct `page_cache` table queries.
- **`fragments/admin_health.html`** (web/templates/fragments/admin_health.html): New fragment template with:
  - **Pool card**: connections in use / available / max with a fill bar (color shifts amber at 70%, red at 90%); healthy/unhealthy status row
  - **Circuit Breaker card**: SODA CB state dot (green=closed, amber=half-open, red=open) + failure count; DB per-category CB status
  - **Cache card**: page_cache total rows, active (non-invalidated) count, oldest entry age
  - HTMX `hx-trigger="every 30s"` auto-refresh on outer div
  - Design token compliant: `--mono`/`--sans` split, token colors only, token spacing. Lint score: **5/5**
- **"System Health" tab** in admin ops hub (web/templates/admin_ops.html): New `syshealth` tab added to the tab bar; routes through existing `_render_ops_tab` dispatcher.
- **`get_soda_cb_status()`** (src/soda_client.py): New function returning SODA circuit breaker state from a module-level `_soda_circuit_breaker` singleton. Enables observability without instantiating a throw-away SODAClient.

### Tests
- **`tests/test_admin_health.py`**: 7 new tests
  - `test_admin_health_requires_auth` — unauthenticated gets 302 or 403
  - `test_admin_health_non_admin_forbidden` — regular user gets 403
  - `test_admin_health_admin_ok` — admin gets 200
  - `test_admin_health_shows_pool_stats` — pool card content present
  - `test_admin_health_shows_cache_count` — cache card content present
  - `test_admin_health_shows_circuit_breaker` — CB card content present
  - `test_admin_health_tab_in_ops` — System Health tab present in ops hub HTML
