# QS9 Visual QA Scores

Scored by T0 overnight orchestrator from staging screenshots.
Auth pages skipped (TEST_LOGIN_SECRET not passed through to visual_qa.py correctly).

| Page | Desktop | Mobile | Issues |
|------|---------|--------|--------|
| / (landing) | 4/5 | 4/5 | Below-fold content area is empty black — by design (content loads on scroll), but large void on screenshot |
| /search | 4/5 | 4/5 | Clean layout, suggested searches render well, mono font for data |
| /auth/login | 5/5 | — | Clean form, staging banner visible, magic link flow clear |
| /beta-request | 5/5 | — | Clean form, ghost CTA, footer nav present |
| /report (error state) | 4/5 | — | Error state is clean — "No data found" with back link. Normal for test parcel. |
| /brief | — | — | Skipped (auth required, not captured) |
| /portfolio | — | — | Skipped (auth required, not captured) |
| /admin | — | — | Skipped (auth required, not captured) |
| /methodology | — | — | Not in screenshot set |
| /demo | — | — | Not in screenshot set |

**Average score (scored pages): 4.3/5**

**Pages <= 2.0: NONE**

**Notes:**
- No broken layouts, off-brand elements, or rendering issues
- All pages use obsidian dark theme consistently
- Mono font used correctly for data labels/values
- Staging banner renders correctly on auth pages
- Auth pages need manual spot-check in DeskRelay (TEST_LOGIN_SECRET didn't propagate to visual_qa.py env)
