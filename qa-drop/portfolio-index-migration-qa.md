# QA Script — Portfolio + Index Obsidian Design Token Migration

**Feature:** Migrate portfolio.html, project_detail.html, index.html to obsidian design tokens
**Scope:** Presentation-only migration — no Jinja logic changes, no new routes, no JS behavior changes
**Files changed:** `web/templates/portfolio.html`, `web/templates/project_detail.html`, `web/templates/index.html`

---

## DESIGN TOKEN COMPLIANCE

- [ ] Run: `python scripts/design_lint.py --files web/templates/portfolio.html web/templates/project_detail.html --quiet`
  - PASS: Both files score 5/5 (0 violations)
  - FAIL: Any violation in portfolio.html or project_detail.html

- [ ] Run: `python scripts/design_lint.py --files web/templates/index.html --quiet`
  - PASS: Score is 1/5 with violations in 64 lines
  - NOTE: All violations are false positives (HTML entity codes + font-display/font-body naming mismatch)
  - FAIL: Any NEW real hex colors (non-entity, non-variable) found in index.html

- [ ] Spot-check index.html for old blue accent `rgba(79, 143, 247, ...)`:
  - PASS: No matches found (`grep "79, 143, 247" web/templates/index.html` returns empty)
  - FAIL: Any match found

- [ ] Spot-check for hardcoded `#1a1d27` staging banner color:
  - PASS: No match (`grep "#1a1d27" web/templates/index.html` returns empty)
  - FAIL: Any match found

---

## TEMPLATE STRUCTURE — portfolio.html

1. Start the app: `python -m web.app &` (or use a running dev server)

2. Visit /portfolio as an authenticated user
   - PASS: Page loads without 500 error
   - PASS: Page has `<body class="obsidian">` in HTML source
   - PASS: Glass-card containers visible for property list
   - PASS: Summary stats at top show stat-number/stat-label classes
   - PASS: Empty state shows "No watched properties yet" with a CTA button
   - FAIL: Server error, missing template syntax, white page

3. Check filter chips
   - PASS: Status filter buttons render (All / Active / Attention / Stale)
   - PASS: Filter chips use CSS variables (no raw hex in inline styles)

---

## TEMPLATE STRUCTURE — project_detail.html

1. Visit /project/<id> as an authenticated user (owner or admin)
   - PASS: Page loads without 500 error
   - PASS: Members section shows with role badges (Owner, Admin, Member)
   - PASS: Invite form visible for owner/admin
   - PASS: Analyses section shows (or "No analyses linked" empty state)
   - FAIL: Server error, missing role badge rendering

2. Visit /project/<id> as a regular member (not owner/admin)
   - PASS: Invite form NOT shown
   - FAIL: Invite form shown to non-admin

---

## TEMPLATE STRUCTURE — index.html

1. Visit / as an authenticated user
   - PASS: Page loads without 500 error
   - PASS: Search form renders with input fields
   - PASS: Personalization section renders (priorities, experience level chips)
   - PASS: Load more / result pagination works
   - FAIL: Server error, broken form layout

2. Check staging banner (if STAGING env set)
   - PASS: No hardcoded dark background color visible; uses obsidian token colors
   - FAIL: Jarring color mismatch compared to obsidian dark theme

---

## VISUAL SPOT-CHECKS (for human DeskRelay)

- [ ] portfolio.html: property cards use dark glass-card style (no white boxes, no blue accents)
- [ ] portfolio.html: status indicators use dot colors (green/amber/red dots, not badges)
- [ ] project_detail.html: role badges are color-coded (cyan for Owner, blue for Admin, dim for Member)
- [ ] index.html: search form accent color is cyan (#22d3ee range), not old blue (#4f8ff7)
- [ ] All three pages: consistent dark obsidian background, no sections with off-brand light backgrounds
