# DeskRelay Visual QA Results — Sprint 59

**Date:** 2026-02-25
**Production URL:** https://sfpermits-ai-production.up.railway.app
**Screenshots:** qa-results/screenshots/sprint59-deskrelay/

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1 | Public Search no-results | PASS | Dark theme intact, search bar prominent, guidance card shows "Please provide a permit number, address, or parcel" message, 3 locked premium cards (Property Report, Watch & Get Alerts, AI Project Analysis) visible with "Sign up free to unlock" CTAs — no guidance card with example links but the instructional message is present |
| 2 | Public Search with results | PASS | Query "614 6th Ave" retained in search bar; "Did you mean:" suggestions rendered with permit counts per street variation (06th/26th/36th/46th); 3 locked premium cards displayed below; consistent dark card styling |
| 3 | Public Search mobile 375px | PASS | No horizontal overflow; search input and Search button stack vertically at full width — clean stacking; results card and locked premium cards all fit within 375px; readable on mobile |
| 4 | Login page | PASS | Centered card on dark background; branded "sfpermits.ai" logo; email input with placeholder "you@example.com"; invite code field; "Send magic link" CTA button in brand blue; "Back to search" link present |
| 5 | Health page JSON | PASS | status:"ok", backend:"postgres", db_connected:true, 54 tables visible — all key services confirmed healthy; addenda:3,799,948 rows confirms Sprint 58 data load intact |
| 6 | Landing page desktop | PASS | Hero headline "San Francisco Building Permit Intelligence" prominent; search bar full-width with Search button; dark theme (bg rgb(15,17,23)); feature cards grid (Address Lookup, Property Reports, Morning Brief, Plan Analysis, Entity Network, Fee & Timeline Estimates) visible; stat counters (1.1M+, 3.9M+, 671K+, 1M+) in footer area |
| 7 | Landing page mobile 375px | PASS | No horizontal overflow; hero headline stacks cleanly; search bar full width; feature cards stack single-column; all content readable; footer stats visible at bottom |

**Summary:** 7 PASS / 0 FAIL out of 7 checks

## Visual Observations

**Strengths:**
- Dark theme is consistent across all pages (rgb(15,17,23) background)
- Brand blue (#3B82F6 range) used consistently for CTAs and logo accent
- Premium locked cards have a uniform visual treatment — title, description, blurred data preview, "Sign up free to unlock" CTA
- Mobile layout stacks cleanly with no overflow on any tested page
- Login page is focused and uncluttered — centered card pattern matches overall dark aesthetic

**Minor Notes (informational, not blocking):**
- Check 1 (no-results): The guidance message reads "Please provide a permit number, address (street number + street name), or parcel (block + lot)" — this is a useful instructional message but does not include example links/queries. If a richer "Try searching for..." guidance card was intended in Sprint 59, it is not currently visible.
- Check 2 (search with results): The "Did you mean:" suggestions with permit counts is a good disambiguation UX — visually clean and readable.
- Check 5 (health): `cron_log: 0` noted — cron log table appears empty on production. Not a blocker but worth monitoring.

## Screenshots

- Check 1: `qa-results/screenshots/sprint59-deskrelay/1-search-no-results.png`
- Check 2: `qa-results/screenshots/sprint59-deskrelay/2-search-with-results.png`
- Check 3: `qa-results/screenshots/sprint59-deskrelay/3-search-mobile.png`
- Check 4: `qa-results/screenshots/sprint59-deskrelay/4-login-page.png`
- Check 5: `qa-results/screenshots/sprint59-deskrelay/5-health-page.png`
- Check 6: `qa-results/screenshots/sprint59-deskrelay/6-landing-desktop.png`
- Check 7: `qa-results/screenshots/sprint59-deskrelay/7-landing-mobile.png`
