# c.ai Prompt: V5 UI Architecture Session

Copy everything below the line into a new c.ai conversation.

---

# sfpermits.ai — V5 UI Architecture

I have a working prototype for my landing page (I'll paste the HTML). Now I need your help figuring out how to integrate ALL of the app's functionality into this design language. I need UI architecture advice — where does everything go? How do the pages connect? What's the navigation model?

## The prototype

Here's my v5 landing page prototype. It establishes the visual language: dark Obsidian theme, JetBrains Mono + IBM Plex Sans, glass-card containers, progressive disclosure search with 3 user states.

```html
[PASTE THE FULL landing-v5.html CONTENT HERE — all 744 lines]
```

## All functionality that needs to fit

Here's every feature the app has, organized by user journey:

### Anonymous visitor
- **Landing page** (the prototype above) — hero, search, stats, capabilities, demo
- **Public search results** — address lookup with permit history, entity network preview, routing progress
- **Demo page** — curated property intelligence for 1455 Market St, no auth needed
- **Content pages** — /methodology (3000 words), /about-data (data inventory), /adu (ADU stats)
- **Beta request** — signup form for waitlist
- **Login** — magic link email (no passwords)

### Authenticated user (after login)
- **Dashboard** — the HOME after login. Currently: search bar + recent items + action links. Needs: watched property summary, severity badges, portfolio health, quick stats
- **Search + results** — same as public but with richer data, watch button, routing details
- **Morning brief** — daily digest: permit changes, new filings, health signals, inspections, compliance calendar, street activity, plan review status. Dense data page.
- **Portfolio** — all watched properties in one view, health tiers, change timeline
- **Property report** — deep dive: permit history, complaints, violations, risk assessment, consultant signal, nearby activity, routing progress
- **Plan analysis** — upload architectural drawings, AI vision checks EPR compliance, returns annotated results with gallery
- **Permit prep** — checklist for a specific permit: required documents, status tracking
- **Account settings** — email preferences, brief frequency, primary address, voice calibration
- **Watch list management** — add/remove/tag properties, set notification preferences
- **Projects** — team collaboration spaces (block/lot scoped)
- **Consultant/expediter search** — find professionals by neighborhood, permit type, track record
- **Bottlenecks dashboard** — station congestion data, which review stations are slow

### Admin
- **Ops hub** — tabbed dashboard: pipeline health, data quality, user activity, feedback, LUCK sources, regulatory watch
- **Metrics** — permit issuance trends, SLA compliance, planning velocity
- **Costs** — API usage tracking, daily spend, kill switch
- **Beta requests** — approve/deny waitlist signups
- **QA replays** — video recordings of browser QA sessions with PASS/FAIL results
- **Activity log** — user actions with timestamps
- **Voice calibration** — tune AI response style per scenario

### Data flowing into the UI
- 1.1M permits with status, costs, dates, contacts
- 671K inspections
- 576K entity relationship edges
- 3.9M addenda routing records
- Severity scores per permit (CRITICAL/HIGH/MEDIUM/LOW/GREEN)
- Health tiers per property (on_track/at_risk/high_risk)
- Parcel summary cache (permit counts, tax value, zoning per block/lot)
- Station velocity estimates (p50 days per review station)

## What I need from you

1. **Navigation architecture** — The prototype has NO nav (just the search). Once logged in, the user needs access to: Dashboard, Brief, Portfolio, Projects, Analyses, Permit Prep, Consultants, Account, Admin. That's 9 items. How do we handle this without the cramped badge row I have now? Show me options.

2. **Page hierarchy** — Which pages are top-level nav items vs. nested/contextual? For example, is "Property Report" its own nav item, or is it reached through search results? Is "Permit Prep" a standalone page or a tab within Property Report?

3. **Dashboard layout** — The prototype search is the whole page. For authenticated users, what goes BELOW the search? How do we show: watched properties (could be 3 or 90), severity alerts, recent activity, quick actions — without making it feel cluttered?

4. **Dense data pages** — Morning Brief and Property Report are data-dense. How do we present tables, stats, timelines, risk badges in the Obsidian visual language without losing information density?

5. **Progressive disclosure model** — The prototype uses 3 states (new/returning/power) for search. Should the whole app use progressive disclosure? Hide complexity from new users, reveal it as they use more features?

6. **Mobile architecture** — At 375px, what's the nav model? Hamburger? Bottom tab bar? Slide-out drawer? How do dense pages like Morning Brief work on mobile?

Start with navigation architecture (#1) — that's the backbone everything else hangs on. Show me as an artifact.
