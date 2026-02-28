# CSRF Comprehensive Audit — Fix Log

## Date: 2026-02-27

## Summary

Comprehensive audit and fix of all POST request vectors for CSRF protection.
The CSRF middleware (`web/security.py`) aborts 403 on any POST without a valid token.
Prior work fixed: regular HTML POST forms and HTMX hx-post via global `htmx:configRequest`
listener in `head_obsidian.html`. This audit covers all remaining vectors.

---

## Findings & Fixes

### 1. Standalone pages with hx-post but no CSRF meta tag / htmx:configRequest listener

These pages use HTMX but do not include `head_obsidian.html`, so hx-post calls
had no mechanism to add X-CSRFToken to requests.

**Fixed — added `<meta name="csrf-token">` + `htmx:configRequest` listener:**

| File | hx-post endpoints |
|------|-------------------|
| `web/templates/report.html` | `/report/{block}/{lot}/share` |
| `web/templates/search_results_public.html` | `/lookup/intel-preview` |
| `web/templates/voice_calibration.html` | `/account/voice-calibration/save`, `/reset` |
| `web/templates/consultants.html` | `/consultants/search` |
| `web/templates/plan_processing_page.html` | hosts `analyze_plans_processing.html` + `feedback_widget.html` |
| `web/templates/plan_results_page.html` | hosts `analyze_plans_results.html` + `feedback_widget.html` |
| `web/templates/analysis_history.html` | multiple hx-post targets |

### 2. JavaScript fetch() POST calls missing X-CSRFToken header

fetch() calls bypass the HTMX `htmx:configRequest` listener entirely.
Each required explicit header injection.

**Fixed — added `'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''`:**

| File | Endpoint |
|------|----------|
| `web/templates/analysis_history.html` | `/api/plan-jobs/bulk-delete` |
| `web/templates/analysis_history.html` | `/api/plan-jobs/{id}/restore` |
| `web/templates/analysis_compare.html` | `/api/project-notes/{vg}` |
| `web/templates/analyze_plans_results.html` | `/plan-analysis/{id}/email` |
| `web/templates/analysis_shared.html` | `/project/{id}/join` |
| `web/templates/draft_response.html` | `/feedback/draft-edit`, `/feedback/draft-good` |
| `web/templates/fragments/account_settings.html` | `/watch/edit` |
| `web/templates/fragments/analysis_grouping.html` | `/api/project-notes/{vg}` |
| `web/templates/fragments/watch_button.html` | `/watch/remove` (upgraded from cookie to meta tag) |
| `web/templates/project_detail.html` | `/project/{id}/invite` |
| `web/templates/results.html` | `/analysis/{id}/share` |
| `web/templates/welcome.html` | `/onboarding/dismiss` |
| `web/static/admin-feedback.js` | `/api/qa-feedback` (2 calls) |
| `web/static/admin-tour.js` | `/api/qa-feedback` |
| `web/static/activity-tracker.js` | `/api/activity/track` |
| `web/templates/admin_pipeline.html` | `/cron/pipeline-health` (was building headers var but not including token) |

### 3. analysis_compare.html — added csrf-token meta tag

`analysis_compare.html` is a standalone page with no HTMX and no `head_obsidian`.
It only has fetch() POST calls. Added `<meta name="csrf-token">` tag.

### 4. security.py — added /api/activity/track to CSRF skip list

`activity-tracker.js` uses `navigator.sendBeacon()` as primary transport (reliability).
`sendBeacon` cannot set custom headers, so it cannot send X-CSRFToken.
The fetch() fallback was fixed to include the header, but sendBeacon is the primary path.

Added `/api/activity/track` to `_CSRF_SKIP_PREFIXES` alongside `/api/qa-feedback`
which was already exempt.

Note: `/api/qa-feedback` and `/api/activity/track` are telemetry/analytics endpoints
with no state-changing side effects — CSRF exemption is appropriate.

---

## Verification Results

```
1. POST forms missing csrf_token hidden input:
   PASS — all POST forms have csrf_token

2. Standalone pages with hx-post but no CSRF setup:
   PASS — all standalone hx-post pages have CSRF setup

3. fetch() POST calls potentially missing X-CSRFToken:
   PASS — all fetch() POST calls have X-CSRFToken
```

## Test Results

- 564 passed, 1 failed (pre-existing: `test_db_pool.py::TestPoolConfig::test_pool_minconn_maxconn` — pool config mismatch, unrelated to CSRF)
- 0 regressions introduced

---

## Pattern Reference

### HTMX hx-post (covered by htmx:configRequest listener)
```html
<meta name="csrf-token" content="{{ csrf_token }}">
<script nonce="{{ csp_nonce }}">
    document.addEventListener('htmx:configRequest', function(e) {
        var token = document.querySelector('meta[name="csrf-token"]');
        if (token) e.detail.headers['X-CSRFToken'] = token.getAttribute('content');
    });
</script>
```

### fetch() POST (must be explicit per call)
```js
fetch('/some/endpoint', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
    },
    body: JSON.stringify(data)
})
```

### HTML POST form (hidden input)
```html
<form method="post" action="/some/endpoint">
    <input type="hidden" name="csrf_token" value="{{ csrf_token }}">
    ...
</form>
```
