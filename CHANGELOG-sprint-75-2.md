# Sprint 75-2 CHANGELOG — Beta Approval Email + Onboarding

## Features

### Beta Approval Welcome Email (`web/auth.py`)
- **New function:** `send_beta_welcome_email(email, magic_link)` — sends a branded HTML email with a one-click sign-in CTA button when admin approves a beta request
- Inline CSS following Obsidian brand colors (`#22D3EE` cyan, `#131825` surface, `#E8ECF4` text)
- Fallback to plain SMTP magic link email if welcome send fails
- Dev mode: logs to console when SMTP not configured (returns `True`)

### Beta Approved Email Template (`web/templates/emails/beta_approved.html`)
- New HTML email template for beta approval notification
- Inline CSS for email client compatibility (no external sheets)
- Dark theme with Obsidian brand colors
- Three numbered "what happens next" steps
- Magic link CTA button + fallback URL text

### Admin Approval Wired (`web/routes_admin.py`)
- `admin_approve_beta()` now calls `send_beta_welcome_email()` instead of plain `send_magic_link()`
- Generates full `BASE_URL + /auth/verify/<token>` URL for the email
- Falls back to `send_magic_link()` if welcome email fails
- Flash message updated: "Approved and sent welcome email to..."

### `onboarding_complete` Column
- **`scripts/release.py`:** `ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_complete BOOLEAN DEFAULT FALSE` (Sprint 75-2 section)
- **`src/db.py` `init_user_schema`:** DuckDB equivalent via `ALTER TABLE` in the existing migration loop

### User Schema Updated (`web/auth.py`)
- `get_user_by_email()` and `get_user_by_id()` both select `COALESCE(onboarding_complete, FALSE)` (column index 19)
- `_row_to_user()` returns `"onboarding_complete"` key in user dict

### `/welcome` Onboarding Route (`web/routes_misc.py`)
- **New route:** `GET /welcome` — 3-step onboarding page for new beta users
- Requires authentication (`@login_required`)
- Redirects to `/` (dashboard) if `user.onboarding_complete` is already True
- Obsidian design: `obs-container`, `glass-card` step cards, progress dots

### Welcome Template (`web/templates/welcome.html`)
- Obsidian design: `head_obsidian.html` include, `body.obsidian`, `obs-container`
- 3-step `glass-card` grid: Search, Property Report, Watchlist
- Progress dots (3 dots with connectors)
- CTA footer card with "Start searching now" button
- Skip link fires `fetch('/onboarding/dismiss')` before navigating away
- Responsive: 3-column desktop, 1-column mobile

### `/onboarding/dismiss` Enhanced (`web/routes_auth.py`)
- Now persists `onboarding_complete = TRUE` in DB when user is authenticated
- Session flag logic preserved for backward compatibility with HTMX banner dismiss

## Tests (`tests/test_sprint_75_2.py`)
- 18 tests, all passing
- SMTP mock tests, dev mode, failure handling
- Column existence and `_row_to_user` field tests
- Route accessibility, redirect guard, dismiss endpoint
