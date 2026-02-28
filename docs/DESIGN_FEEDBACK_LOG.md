# Design Feedback Log

> Running log of Tim's design feedback during build sessions.
> Agents: read this before touching any template. Learn from past mistakes.

## Session: 2026-02-27 — Landing Page Rebuild

### Mistake 1: Wrong mockup file
**What happened:** Agent built from `web/static/landing-v5.html` (7K, early prototype) instead of `web/static/mockups/landing.html` (54K, approved design).
**Cost:** 2+ hours wasted building the wrong thing.
**Rule:** Always check `web/static/mockups/` FIRST. If a mockup exists there, it IS the spec.

### Mistake 2: Invented content instead of reading design docs
**What happened:** Agent wireframed landing page content from scratch, re-presented design decisions Tim had already approved.
**Tim's feedback:** "I already fucking approved all this, did you not read the design docs?"
**Rule:** Read ALL design docs before proposing content. DESIGN_CANON, DESIGN_PRINCIPALS, DESIGN_TOKENS, design-spec.md, Chief DESIGN_SYSTEM.md, and the mockups. Do not re-derive what's already documented.

### Mistake 3: Sub-row links changed to dropdowns
**What happened:** Agent changed "Do I need a permit?" / "How long will it take?" / "Is my permit stuck?" from anchor links (#cap-permits scroll) to hover dropdown triggers.
**Tim's feedback:** "Do I need a permit line should not be dropdowns. Click goes to the identical section below the fold."
**Rule:** Sub row = anchor links to below-fold sections. Context row = hover dropdowns. They are DIFFERENT interaction patterns on DIFFERENT rows.

### Mistake 4: "See how it works" not clickable
**Tim's feedback:** "Flashing but no action when clicked. Possible mixed messages to users."
**Fix:** Changed from decorative `<div>` to clickable `<a href="#cap-permits">`. If something looks clickable, it must be clickable.

### Mistake 5: No navigation mapping for dropdown items
**What happened:** Agent didn't know where dropdown item clicks should navigate in production (mockup just fills input, doesn't navigate).
**Tim's feedback:** "Won't know until I click it."
**Resolution:** Dropdown items submit the search form to `/search?q={value}`. Capability inputs wrapped in `<form action="/search">`. Demo CTA goes to `/demo`. Footer links to real routes.

### Mistake 6: Search results page still old design
**Observation:** Landing page submits to `/search`, which renders `search_results_public.html` — still the old white-header design with filled gradient buttons.
**Status:** Rebuilding from `web/static/mockups/search-results.html`.

### General Rules (from this session)
- **Build from mockups, not from imagination.** The mockup IS the spec.
- **QA against mockup files, not agent judgment.** Screenshot new page vs mockup at same viewport.
- **Every clickable thing needs a destination.** If the mockup has `href="#"`, figure out the real route before building.
- **Tim's design process is: mockup → approved → build exactly that.** No interpretation, no "improvements", no alternative proposals unless asked.
- **The Pre-Sprint Design Brief (CLAUDE.md) is mandatory.** Check mockups, check docs, confirm with Tim.
- **When Tim says "read the docs" — he means ALL of them:** CANON, PRINCIPALS, TOKENS, design-spec.md, Chief DESIGN_SYSTEM.md, mockups dir, memory file. Missing one costs hours.

### Pages with approved mockups (as of 2026-02-27)
| Mockup | Template | Status |
|--------|----------|--------|
| `mockups/landing.html` | `landing.html` | Rebuilt, pushed to staging |
| `mockups/search-results.html` | `search_results_public.html` | Rebuilt, pushed to staging |
| `mockups/auth-login.html` | `auth_login.html` | Not started |
| `mockups/portfolio.html` | `portfolio.html` | Not started |
| `mockups/property-intel.html` | `report.html` | Not started |
| `mockups/ai-consultation.html` | (new or search results) | Not started |
| `mockups/ai-consultation-otc.html` | (new) | Not started |
| `mockups/project-timeline.html` | (new or velocity) | Not started |
