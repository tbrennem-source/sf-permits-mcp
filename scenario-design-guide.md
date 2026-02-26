# Scenario Design Guide — sfpermits.ai

_Last reviewed: Sprint 68-A (2026-02-26)_
_Total scenarios: 73_
_Prior review: Session 50 (25 scenarios) — all preserved below_

This is the canonical behavioral specification for sfpermits.ai. Every scenario describes a user-visible outcome, not implementation details.

**Format rules:**
- User persona (expediter, homeowner, architect, admin)
- Starting state (what's true before the action)
- Goal (what the user is trying to accomplish)
- Expected outcome (success criteria — no routes, no CSS, no implementation details)
- Edge cases (boundary conditions)

---

## SEVERITY / PORTFOLIO HEALTH (9 scenarios)

### SCENARIO 1: Hold signal produces AT_RISK regardless of other permit signals
**User:** expediter
**Starting state:** Property has multiple active permits, 1 expired permit (OTC, zero inspections), AND an active hold at a routing station on a different permit
**Goal:** Property health correctly reflects the hold as the primary risk signal
**Expected outcome:**
- Permit-level: The held permit shows `at_risk` with signal `hold` ("Hold at PLMB station, 47d")
- Permit-level: The expired OTC permit shows `slower` with signal `expired_otc`
- Property-level: Tier is `at_risk` (driven by the hold signal). Expired OTC does NOT compound because `slower` signals don't escalate.
- Morning brief card shows AT RISK with "Hold at PLMB station (47d)" as primary reason
**Edge cases:**
1. Hold + open complaint (no NOV): Property stays `at_risk` (complaint = `slower`, doesn't compound).
2. Hold + NOV: Property escalates to `high_risk` — two independent AT_RISK signal types.
3. Hold on critical-path permit vs parallel permit: Same tier at permit level.
**Status:** APPROVED (Session 50)

---

### SCENARIO 2a: Open complaint does NOT escalate property to AT_RISK
**User:** expediter
**Starting state:** Property has 1 expired OTC permit (zero inspections) + open complaint (no NOV) + 3 active permits with recent activity
**Goal:** Property health reflects the complaint as informational, not alarm
**Expected outcome:**
- Complaint adds signal `complaint` (severity: `slower`).
- Tier: `slower` — NOT `at_risk`. Complaint alone never triggers AT_RISK.
**Edge case:** Property has complaint + expired non-OTC permit with zero inspections — both informational. Tier: `behind`, not `at_risk`.
**Status:** APPROVED (Session 50)

---

### SCENARIO 2b: NOV escalates property to AT_RISK, not downgraded by active site
**User:** expediter
**Starting state:** Property has 1 expired OTC permit + NOV issued + multiple active permits with recent activity
**Goal:** NOV drives property to AT_RISK despite active-site context
**Expected outcome:**
- NOV adds signal `nov` (severity: `at_risk`).
- Tier: `at_risk` — active-site downgrade logic does NOT fire because NOV is a confirmed legal finding.
**Edge case:** NOV + hold on different permit escalates to `high_risk`.
**Status:** APPROVED (Session 50)

---

### SCENARIO 3: Expired permit severity determined by inspection evidence and permit type
**User:** expediter
**Starting state:** Property has 1 expired permit, no other active permits, no enforcement
**Goal:** Severity accurately reflects risk based on data signals

| Sub-case | Permit details | Signal | Tier |
|---|---|---|---|
| 3a | Expired + 4+ real inspections + no final | `expired_uninspected` | `at_risk` |
| 3b | Expired + 1-3 real inspections | `expired_minor_activity` | `behind` |
| 3c | Expired + zero inspections + OTC type | `expired_otc` | `slower` |
| 3d | Expired + zero inspections + non-OTC type | `expired_inconclusive` | `behind` |
| 3e | Stale issued 2yr+ zero inspections | `stale_no_activity` | `slower` |
| 3f | Stale issued 2yr+ has real inspections | `stale_with_activity` | `at_risk` |

**"Real inspections"** = result is PASSED, FAILED, or DISAPPROVED (not N/A).
**Status:** APPROVED (Session 50)

---

### SCENARIO 4: Expired permit at active site — contextualizes, doesn't alarm
**User:** expediter
**Starting state:** Property has 1 expired OTC permit (zero inspections) + 5 active permits + activity within 90 days
**Goal:** Expired permit doesn't create noise on an active construction site
**Expected outcome:** Tier: `slower` — not `at_risk`, not `behind`. Expired permit shown as footnote, not headline.
**Edge case:** Expired non-OTC permit with 5 real inspections and no final → `at_risk` regardless of site activity.
**Status:** APPROVED (Session 50)

---

### SCENARIO 5: Stale zombie permit does not alarm
**User:** expediter
**Starting state:** Property has 1 permit issued in 2015, status "issued", zero inspections, OTC type. 1 active permit filed 2024.
**Goal:** The 10-year-old zombie permit doesn't distract from current active work
**Expected outcome:** Zombie → `slower` (`stale_no_activity`). Active permit → `on_track`. Property tier: `slower`.
**Edge case:** Same zombie but with 3 real inspection records from 2016 → `stale_with_activity` (`at_risk`).
**Status:** APPROVED (Session 50)

---

### SCENARIO 26: Expired seismic permit scores CRITICAL
**User:** expediter
**Starting state:** Property has a seismic retrofit permit, status=issued, filed 4 years ago, issued 13+ months ago ($50k), zero inspections
**Goal:** Severity model identifies this as a critical-risk permit
**Expected outcome:** Severity score >= 80 (CRITICAL tier). Top driver is expiration_proximity or inspection_activity. Explanation mentions the expired permit.
**Edge cases:** $50k permits have 360-day Table B validity; $200k+ have 1080 days. A $200k seismic issued 13 months ago would NOT be expired — tier would be lower.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 27: Fresh low-cost filing scores GREEN
**User:** homeowner
**Starting state:** Homeowner just filed a $5k window replacement permit 5 days ago
**Goal:** Severity model confirms permit is on track
**Expected outcome:** Severity score < 20 (GREEN tier). All dimensions score near zero. Morning brief shows "on_track" health.
**Edge cases:** Filed permits get zero inspection penalty (inspections not expected yet).
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 28: High-risk compound detection
**User:** expediter
**Starting state:** Property has permits with Issued Comments hold AND open Notice of Violation
**Goal:** System correctly identifies convergent risk
**Expected outcome:** Property tier is HIGH_RISK (not just AT_RISK). Signal table shows both independent risk signals. Recommended actions include "Immediate review" and note about multiple independent risk factors.
**Edge cases:** Two at_risk signals from the SAME compounding type = AT_RISK not HIGH_RISK. hold_stalled (behind) does NOT compound.
**Status:** APPROVED (Sprint 68-A)

---

## ADMIN OPS (6 scenarios)

### SCENARIO 6: Admin Ops tab timeout recovery
**User:** admin
**Starting state:** Logged in as admin, database under heavy load or slow
**Goal:** View any Admin Ops tab and get either content or a clear error within 30 seconds
**Expected outcome:** Tab loads data OR shows "timed out" fallback with retry link. Never shows infinite spinner past 30s.
**Edge cases:** Server-side timeout (25s) fires before client-side timeout (30s) — both paths produce user-visible message.
**Status:** APPROVED (Session 50)

---

### SCENARIO 7: Admin Ops tabs load within 5 seconds
**User:** admin
**Starting state:** Logged in as admin, on Admin Ops page
**Goal:** Every tab loads in under 5 seconds, even at scale
**Expected outcome:** Any tab click → content renders in <5s. Tab switching mid-load → previous request canceled, new tab wins, no orphaned spinners. Active state tracks most-recently-clicked tab.
**Edge case:** If cache is stale, show last-cached data with timestamp rather than running a live slow query.
**Status:** APPROVED (Session 50)

---

### SCENARIO 8: Hash routing aliases for Admin Ops
**User:** admin
**Starting state:** Not on Admin Ops page
**Goal:** Navigate directly to a specific tab via URL hash
**Expected outcome:** Friendly hash aliases work (#luck → Sources, #dq → Data Quality, #watch → Regulatory Watch, #pipeline → Pipeline Health). Unknown hashes fall back to Data Quality.
**Status:** APPROVED (Session 50)

---

### SCENARIO 9: Admin Ops initial tab loads on first visit without double-click
**User:** admin
**Starting state:** Not on Admin Ops page; navigating for first time in session
**Goal:** Navigate to Admin Ops and see default tab content load automatically
**Expected outcome:** Default tab content appears without clicking any tab button. Tab button shows active state. URL hash updates.
**Status:** APPROVED (Session 50)

---

### SCENARIO 10: Admin dropdown submenu reachable on hover
**User:** admin
**Starting state:** Logged in as admin, on any page with top nav bar
**Goal:** Hover over "Admin" and move cursor down to click a submenu item
**Expected outcome:** Submenu appears on hover and remains visible as cursor moves from trigger to submenu items. Submenu disappears only when cursor leaves both trigger and menu.
**Status:** APPROVED (Session 50)

---

### SCENARIO 11: DQ cache serves instant results; refresh populates fresh data
**User:** admin
**Starting state:** DQ cache populated by nightly cron or previous manual refresh
**Goal:** See check results instantly, then trigger manual refresh
**Expected outcome:** DQ tab loads in <1s from cache, showing "Last refreshed" timestamp and all check cards. Clicking "Refresh" runs checks and replaces content. If cache empty, shows "No cached results yet" with instructions.
**Edge cases:** Check timeout during refresh is caught and skipped — remaining checks still run.
**Status:** APPROVED (Session 50)

---

## DATA QUALITY (2 scenarios)

### SCENARIO 12: DQ tab shows bulk index health diagnostic
**User:** admin
**Starting state:** DQ cache populated, on Data Quality tab
**Goal:** Verify that critical PostgreSQL indexes exist on bulk tables
**Expected outcome:** Index tags shown — green for existing, red for missing. At least 6 key indexes checked.
**Edge cases:** On DuckDB (local dev) returns empty list, bar doesn't render.
**Status:** APPROVED (Session 50)

---

### SCENARIO 13: DQ checks degrade gracefully when individual checks error
**User:** admin
**Starting state:** DQ cache populated, some checks failing
**Goal:** See results even when some checks have errors
**Expected outcome:** Tab loads fully. Passing checks green, failing checks show red with error message. Summary line counts correctly. Tab never crashes because one check errored.
**Status:** APPROVED (Session 50)

---

## INTENT ROUTER (3 scenarios)

### SCENARIO 14: Pasted email routes to AI draft response
**User:** expediter
**Starting state:** On homepage, received email from homeowner about permits
**Goal:** Paste email into search box and get AI-drafted reply
**Expected outcome:** AI generates contextual response using knowledge base. Does NOT trigger complaint search, address lookup, or project analysis even if email contains those keywords.
**Edge cases:** Single-line greeting without substance ("Hi Amy") falls through to general_question. "draft:" prefix always triggers.
**Status:** APPROVED (Session 50)

---

### SCENARIO 15: Multi-line email with signature detected
**User:** expediter
**Starting state:** Received forwarded email with sign-off ("— Karen", "Best regards,", "Sent from my iPhone")
**Goal:** Paste full email thread into search box for AI analysis
**Expected outcome:** Routes to draft_response even without explicit greeting, based on signature detection + multi-line structure.
**Edge cases:** Single dash "- Karen" matches but "-Karen" (no space) does not.
**Status:** APPROVED (Session 50)

---

### SCENARIO 16: Exact street name matching prevents false positives
**User:** expediter
**Starting state:** User searches "146 Lake" (LAKE ST exists, BLAKE ST also exists)
**Goal:** See permits only for LAKE ST, not substring matches
**Expected outcome:** Results contain only LAKE ST permits; no BLAKE, LAKE MERCED HILL, or other partial matches.
**Edge cases:** Space-variant names (VAN NESS vs VANNESS) still match.
**Status:** APPROVED (Session 50)

---

## PLAN ANALYSIS UX (8 scenarios)

### SCENARIO 17: Badge count matches permit table count
**User:** expediter
**Starting state:** User searches address with permits across multiple parcels/historical lots
**Goal:** Understand permit count at a glance
**Expected outcome:** PERMITS badge total matches count shown in permit results table.
**Status:** APPROVED (Session 50)

---

### SCENARIO 18: Feedback screenshot on content-heavy page
**User:** homeowner
**Starting state:** Viewing permit results page with 10+ permits
**Goal:** Report bug with visual screenshot
**Expected outcome:** Screenshot captures within 5MB limit, attaches to feedback form, submits successfully.
**Edge cases:** CDN load failure shows fallback message; JPEG quality degrades if first pass exceeds 5MB.
**Status:** APPROVED (Session 50)

---

### SCENARIO 19: Undo accidental delete within grace period
**User:** expediter
**Starting state:** Has a completed analysis on history page
**Goal:** Accidentally delete, then undo before 30s grace period
**Expected outcome:** Toast with "Undo" button appears; clicking within 30s restores job.
**Edge cases:** Bulk delete returns multiple IDs for undo; restore fails gracefully if already purged.
**Status:** APPROVED (Session 50)

---

### SCENARIO 20: Retry failed analysis with prefilled metadata
**User:** expediter
**Starting state:** Failed or stale analysis card visible
**Goal:** Retry without re-entering metadata
**Expected outcome:** "Retry" opens upload form with address, permit number, submission stage, project description pre-filled. File must still be re-uploaded.
**Edge cases:** No address/permit stored → fields empty (not "null").
**Status:** APPROVED (Session 50)

---

### SCENARIO 21: Filter persistence across page reloads
**User:** expediter
**Starting state:** On analysis history page with many jobs
**Goal:** Set filter, share URL, have same view load
**Expected outcome:** Filter chip updates URL params; reload restores filter; shared URL loads filtered view.
**Edge cases:** Multiple filters (status + mode) both persist; clearing "All" removes params.
**Status:** APPROVED (Session 50)

---

### SCENARIO 22: Compare page shows human-readable labels
**User:** expediter
**Starting state:** On comparison page for two versions of same plan set
**Goal:** Understand results without knowing internal terminology
**Expected outcome:** Columns say "Original" / "Resubmittal"; type chips use human names; EPR checks show human names with raw ID as secondary.
**Status:** APPROVED (Session 50)

---

### SCENARIO 23: Project notes visible for pre-existing jobs in grouped view
**User:** expediter
**Starting state:** Existing jobs from before version_group column was added; grouped view enabled
**Goal:** Open notes panel for a project group and save a note
**Expected outcome:** Notes toggle appears on every group. Textarea opens, typing/saving works, char counter updates live (e.g., "42 / 4,000"), saved confirmation appears.
**Edge cases:** Groups keyed by normalized address/filename when version_group is NULL. Single-job groups also show notes.
**Status:** APPROVED (Session 50)

---

### SCENARIO 24: Project notes persist across grouped view reloads
**User:** expediter
**Starting state:** Notes saved on a project group
**Goal:** Reload and verify notes persist
**Expected outcome:** Notes text reappears. Preview truncation (first 60 chars) in button label. Character count correct.
**Status:** APPROVED (Session 50)

---

## MORNING BRIEF (7 scenarios)

### SCENARIO 25: What Changed shows specific permit details
**User:** expediter
**Starting state:** Watched property had a permit status update, nightly change detection logged it
**Goal:** See what changed on the morning brief
**Expected outcome:** Card shows permit number, permit type, and current status badge instead of generic "Activity Xd ago".
**Edge cases:** Query failure falls back to generic activity card. Multiple changed permits → one card per permit.
**Status:** APPROVED (Session 50)

---

### SCENARIO 52: Addenda staleness detected in morning brief
**User:** expediter | admin
**Starting state:** Addenda data is >3 days old (SODA outage or stale import)
**Goal:** User sees data freshness warning on morning brief
**Expected outcome:** Morning brief shows a pipeline health warning indicating addenda data is stale, with the last known data date. Warning banner appears above the "What Changed" section.
**Edge cases:** data_as_of can be None if addenda table is empty; check runs inside try/except so failures don't crash the brief.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 53: Morning brief shows planning context for watched parcels
**User:** expediter | admin
**Starting state:** User has watch items for parcels; planning_records table has CUA or variance records for those block/lots
**Goal:** See active planning entitlements alongside building permit activity
**Expected outcome:** Brief includes a planning context section showing record_type, record_status, assigned_planner for each watched parcel with planning records. Parcels without planning records omitted.
**Edge cases:** Planning records with NULL block/lot cannot be joined to watch items.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 54: Compliance calendar surfaces expiring boiler permits
**User:** expediter | admin
**Starting state:** Boiler permits have expiration dates within 90 days of today; user watches those parcels
**Goal:** Morning brief proactively surfaces upcoming renewals
**Expected outcome:** Compliance calendar section lists property address, permit number, expiration date, and days remaining. Sorted by soonest first.
**Edge cases:** Boiler permits lack block/lot — requires address matching; parcels without expiring boilers not shown.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 55: Street-use activity near watched address
**User:** expediter | homeowner
**Starting state:** User watches an address on a named street; active street-use permits exist on that street
**Goal:** See nearby street-use activity (scaffolding, crane, utility work)
**Expected outcome:** Brief includes street-use section listing permit type, applicant, and date. Deduplicates on permit_number.
**Edge cases:** Case-insensitive matching; users with no address watches get empty list.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 56: Station path prediction in morning brief
**User:** expediter
**Starting state:** User has a watched permit currently in BLDG review
**Goal:** Know what station comes next and how long it will take
**Expected outcome:** Brief shows predicted next station with estimated days remaining.
**Edge cases:** Permit at a rare station with no transition data; cycle prevention in prediction path.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 57: Change velocity breakdown
**User:** expediter
**Starting state:** Nightly detected 10 permit changes (5 status_change, 3 new_permit, 2 cost_revision)
**Goal:** See a breakdown of what types of changes occurred
**Expected outcome:** Brief contains change velocity data showing counts by change type (e.g., "5 status changes, 3 new permits, 2 cost revisions").
**Edge cases:** Empty dict if no changes or table doesn't exist.
**Status:** APPROVED (Sprint 68-A)

---

## SECURITY (7 scenarios)

### SCENARIO 30: run_query blocks SQL injection attempts
**User:** admin (or attacker)
**Starting state:** MCP tool invoked with malicious SQL
**Goal:** Prevent any write operations through run_query
**Expected outcome:** INSERT/UPDATE/DELETE/DROP/ALTER/TRUNCATE all rejected with clear error. Comment-disguised writes also rejected. Column names containing keywords (e.g., `deleted_at`) do NOT trigger false positives.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 31: read_source blocks directory traversal
**User:** admin (or attacker)
**Starting state:** MCP tool invoked with path traversal attempt
**Goal:** Prevent reading files outside the repository
**Expected outcome:** Absolute paths rejected. Relative traversal rejected. Symlink traversal that resolves outside repo rejected.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 32: Kill switch blocks AI endpoints and returns 503
**User:** expediter | homeowner
**Starting state:** Admin has activated the kill switch
**Goal:** User submits a question via AI endpoint
**Expected outcome:** HTTP 503 returned explaining AI features temporarily unavailable. Basic permit search and lookup still work. Kill switch does NOT block non-AI features.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 33: Cost auto-triggers kill switch when daily spend exceeds threshold
**User:** system (automated)
**Starting state:** Daily spend threshold set; spend about to exceed it
**Goal:** Automatic cost protection
**Expected outcome:** Kill switch activates when threshold crossed. Subsequent AI requests return 503. Admin sees kill switch active on dashboard.
**Edge cases:** Kill switch only auto-activates once per day.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 34: CSP header blocks injected external script
**User:** admin (or attacker attempting XSS)
**Starting state:** Production response includes Content-Security-Policy header
**Goal:** External script injection blocked by CSP
**Expected outcome:** CSP header present on every response. Browser blocks any injected external script. Frame-ancestors blocks clickjacking.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 35: Bot user agent blocked from app routes
**User:** scraper/bot
**Starting state:** Request arrives with automated User-Agent
**Goal:** Block automated scraping while allowing monitoring
**Expected outcome:** Bot receives 403 on app routes. Health and cron endpoints remain accessible. curl is NOT blocked. Empty UA is NOT blocked.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 36: Daily request limit prevents anonymous abuse
**User:** anonymous visitor
**Starting state:** Anonymous user makes 50+ requests in a single day
**Goal:** Prevent excessive resource consumption
**Expected outcome:** After 50 requests/day, user receives 429. Authenticated users get 200/day. Client tracking endpoint exempt. Cache prevents DB query on every request.
**Edge cases:** Fails open on DB error; test mode skips limit.
**Status:** APPROVED (Sprint 68-A)

---

## AUTH & ACCESS (7 scenarios)

### SCENARIO 37: Anonymous user discovers site via landing page
**User:** homeowner
**Starting state:** No account, visits sfpermits.ai for the first time
**Goal:** Understand what the tool offers and search for an address
**Expected outcome:** Landing page renders with hero, search box, feature cards, and stats. Search box submits and returns public permit results.
**Edge cases:** Empty query redirects home; rate limiting applies.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 38: Anonymous user searches and sees public results
**User:** homeowner
**Starting state:** On landing page, not logged in
**Goal:** Look up permit history for an address
**Expected outcome:** Public results show basic permit data with locked premium feature cards and sign-up CTAs.
**Edge cases:** Intent classifier may route query as general knowledge question; no-results case shows helpful message.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 39: Authenticated user bypasses landing page
**User:** expediter | homeowner | architect
**Starting state:** Logged in with a session
**Goal:** Access the full app dashboard
**Expected outcome:** Home page serves full app instead of landing page; all premium features visible.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 40: Login required for premium features
**User:** homeowner
**Starting state:** No account, tries to visit premium content (brief, portfolio, consultants, analyses)
**Goal:** Access premium content without logging in
**Expected outcome:** Redirected to login. After signing up and logging in, can access the feature. Health, search, and report pages remain public.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 41: Unauthenticated visitor sees gated navigation
**User:** homeowner (not logged in)
**Starting state:** Visitor arrives at landing page
**Goal:** See which features exist while being guided toward signup
**Expected outcome:** Nav shows Search normally; Brief/Portfolio/Projects/Analyses greyed with "Sign up" badges linking to login. After login, badges disappear. Admin features hidden entirely for non-admin.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 42: Staging banner on staging environment
**User:** expediter | admin
**Starting state:** App deployed to staging with ENVIRONMENT=staging
**Goal:** Distinguish staging from production visually
**Expected outcome:** Yellow banner reading "STAGING ENVIRONMENT" visible at top of every page. Banner NOT present on production.
**Edge cases:** Default when ENVIRONMENT not set is "production" (no banner).
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 43: Test-login endpoint not exposed on production
**User:** any unauthenticated user
**Starting state:** App running in production (TESTING env var not set)
**Goal:** Attempt to access test-login
**Expected outcome:** HTTP 404. No information about the endpoint or secret disclosed.
**Edge cases:** Empty string and "false" also return 404.
**Status:** APPROVED (Sprint 68-A)

---

## ONBOARDING & GROWTH (9 scenarios)

### SCENARIO 44: Homeowner gets instant permit preview without signing up
**User:** homeowner
**Starting state:** Unauthenticated user on landing page with a remodel project
**Goal:** Understand permits needed and timeline before signing up
**Expected outcome:** User fills in project description, sees review path (OTC vs in-house) and timeline estimate. Additional cards (fees, documents, risk) shown locked with signup CTA. No login required for the preview.
**Edge cases:** Empty description redirects home; rate limit applies.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 45: Kitchen remodel sees layout decision fork
**User:** homeowner
**Starting state:** Describes a kitchen remodel on the preview page
**Goal:** Understand how fixture layout choice affects permit path
**Expected outcome:** Page shows side-by-side fork: "Keep existing layout → OTC, ~3-4 weeks" vs "Change layout → In-house, ~3-6 months". Decision tied to whether plumbing/gas lines move.
**Edge cases:** Non-kitchen projects do not show the fork.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 46: New user sees welcome banner on first login
**User:** homeowner | expediter
**Starting state:** Just verified magic link for the first time, no watches yet
**Goal:** Understand where to start
**Expected outcome:** Dismissable welcome banner appears suggesting to search an address or describe a project. Disappears permanently on dismiss. Users with existing watches don't see it.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 47: Share analysis with team via email
**User:** expediter | architect
**Starting state:** Completed a 5-tool permit analysis; authenticated
**Goal:** Share results with 2-3 colleagues
**Expected outcome:** Email sent to each recipient with project summary and link to shared analysis page. Max 5 recipients enforced. Unauthenticated user cannot trigger share.
**Edge cases:** Invalid email rejected; SMTP not configured → dev mode logs links.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 48: Shared analysis page visible without login
**User:** homeowner (recipient, no account)
**Starting state:** Received share email, clicked "View Full Analysis" link
**Goal:** View analysis results shared by a colleague
**Expected outcome:** Full 5-tool analysis results render in tab layout. CTA at bottom offers free signup via shared_link referral path. View count increments on each load.
**Edge cases:** Invalid analysis ID returns 404; analysis by anonymous user still renders.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 49: Organic visitor requests beta access
**User:** homeowner (no invite code)
**Starting state:** Arrives at login with no invite code and no shared link
**Goal:** Get access to sfpermits.ai
**Expected outcome:** Redirected to beta request form; fills out email, name, reason; receives confirmation. Admin sees request in queue. Tim approves, user receives magic link.
**Edge cases:** Rate limit after 3 requests/hour; honeypot field silently discards bot submissions; duplicate email reuses existing request.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 50: Shared-link signup grants immediate access
**User:** homeowner (shared_link recipient)
**Starting state:** Views shared analysis page; clicks signup CTA; no invite code
**Goal:** Create account and access platform immediately
**Expected outcome:** No invite code required; account created with referral_source='shared_link'; after magic link verification, redirected back to original shared analysis.
**Edge cases:** analysis_id missing from session → no redirect; existing users still get magic link.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 51: Admin approves beta request and sends magic link
**User:** admin
**Starting state:** Pending beta requests visible at admin panel
**Goal:** Review and approve a qualified requester
**Expected outcome:** "Approve + Send Link" creates user with beta_approved_at timestamp; magic link sent; request removed from pending queue. Denying updates status without creating user.
**Edge cases:** Approving same request twice is safe (re-sends link).
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 73: ADU landing page shows pre-computed permit stats
**User:** homeowner
**Starting state:** Searching for ADU information (e.g., via search engine)
**Goal:** Learn what's involved in building an ADU in SF
**Expected outcome:** Dedicated page shows current ADU permit count, median processing time, common ADU types, and CTA to run full analysis. Stats are cached.
**Status:** APPROVED (Sprint 68-A)

---

## PERMIT PREDICTION (3 scenarios)

### SCENARIO 58: predict_permits uses DB forms and zoning routing
**User:** expediter | architect
**Starting state:** Reference tables seeded (forms, triggers, zoning routing); user submits project description
**Goal:** Get accurate permit form and review path prediction
**Expected outcome:** Prediction returns correct form (e.g., "Form 1/2" for new construction) sourced from database. When DB is empty, gracefully falls back to hardcoded logic. If property is in a historic district, zoning context section shows "Historic District: Yes".
**Edge cases:** Unknown project types return no DB rows and trigger fallback; zoning lookup requires address → block/lot → tax_rolls chain.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 59: Restaurant project triggers all required agencies
**User:** expediter | architect
**Starting state:** Reference trigger tables seeded; user describes restaurant change-of-use project
**Goal:** See all routing agencies for a restaurant project
**Expected outcome:** Result includes DBI, Planning, SFFD, DPH, and conditionally DBI Mechanical/Electrical, SFPUC, DPW/BSM. All backed by queryable trigger table entries.
**Edge cases:** Restaurant keyword appears in triggers for 5 different agencies; DPH must approve before permit issuance.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 60: Historic district flag surfaced in permit prediction
**User:** architect
**Starting state:** Property in a zoning code with historic_district=True
**Goal:** Understand historic preservation requirements for exterior work
**Expected outcome:** Zoning Context section shows "Historic District: Yes" with note about Article 10/11. Properties without historic designation don't show the flag.
**Edge cases:** Zoning lookup chain (address → block/lot → tax_rolls → ref_zoning_routing) — any step failing gracefully suppresses the section.
**Status:** APPROVED (Sprint 68-A)

---

## ANALYSIS UX (4 scenarios)

### SCENARIO 61: Methodology card reveals calculation details
**User:** architect | expediter
**Starting state:** Viewing a completed 5-tool analysis
**Goal:** Understand where each number came from
**Expected outcome:** Each tool section has a collapsible "How we calculated this" card showing formula steps, data sources, sample size, confidence, and coverage gaps. Cards collapsed by default. Toggle preference persists in browser storage. Shared analysis pages show methodology cards collapsed without toggle.
**Edge cases:** When methodology data is None (old analysis), no card renders.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 62: Coverage disclaimers clarify data limitations
**User:** expediter | architect
**Starting state:** Viewing tool output from any analysis tool
**Goal:** Know what data limitations apply to each result
**Expected outcome:** Each tool output includes a "Data Coverage" section listing specific gaps (e.g., "Planning fees not included", "Limited data for this combination").
**Edge cases:** estimate_timeline disclaimer triggers when sample < 20; predict_permits shows "Zoning-specific routing unavailable" when no address provided.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 63: Cost of delay informs budget planning
**User:** homeowner
**Starting state:** User renting during renovation, paying monthly carrying cost
**Goal:** Understand financial impact of permit delays
**Expected outcome:** Timeline section shows carrying cost scenarios (typical and conservative estimates) and delay risk.
**Edge cases:** Zero carrying cost (field empty) → no cost section shown; no timeline data available → section absent.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 64: Similar projects validate timeline estimate
**User:** homeowner
**Starting state:** Submitted project for analysis
**Goal:** See how project compares to completed similar projects
**Expected outcome:** "Similar Projects" section shows 3-5 completed permits with actual timelines.
**Edge cases:** No similar projects found (rare neighborhood + type combo); progressive widening falls back to district-level match.
**Status:** APPROVED (Sprint 68-A)

---

## ENTITY NETWORK (2 scenarios)

### SCENARIO 65: Entity resolution consolidates trade contractors
**User:** expediter | architect
**Starting state:** An electrical contractor appears on both building and electrical permits with same license but different formatting
**Goal:** Search and see a single consolidated entity
**Expected outcome:** Entity has contact_count > 1, source_datasets includes both permit types, license_number normalized.
**Edge cases:** Leading zeros on CSLB numbers; cross-source matching requires same normalized name.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 66: Multi-role entity shows all observed roles
**User:** expediter
**Starting state:** A professional appears as "contractor" on electrical permits and "consultant" on building permits
**Goal:** See all roles this person has held
**Expected outcome:** Entity type shows most common role; roles field lists all observed roles. Useful for cross-discipline recommendations.
**Edge cases:** Single-role entities have NULL roles field.
**Status:** APPROVED (Sprint 68-A)

---

## DATA & INGEST (1 scenario)

### SCENARIO 67: Trade permits surface in search results
**User:** expediter
**Starting state:** Electrical and plumbing permits ingested into permits table
**Goal:** Search for trade permits at a known address
**Expected outcome:** Trade permits appear in the same search results as building permits. Permit_type_definition differentiates the trade type. No special filter required.
**Edge cases:** Same table as building permits — no schema distinction.
**Status:** APPROVED (Sprint 68-A)

---

## PROJECTS (2 scenarios)

### SCENARIO 68: Project auto-created and deduped on analysis
**User:** expediter | architect
**Starting state:** User runs an analysis with a street address and block/lot for the first time
**Goal:** Analysis automatically linked to a project
**Expected outcome:** A project appears in project list with the analysis address as name. Second analysis on the same parcel links to existing project (dedup by block/lot). Second user added as member.
**Edge cases:** Analysis with no address/block/lot → no project created; address-only analyses create separate projects.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 69: Non-member cannot access project detail page
**User:** expediter (not a project member)
**Starting state:** Navigates directly to a project page they're not a member of
**Goal:** Access control prevents unauthorized viewing
**Expected outcome:** 403 response. Members and admins can access. Anonymous users redirected to login. Missing project returns 404.
**Status:** APPROVED (Sprint 68-A)

---

## EMAIL NOTIFICATIONS (2 scenarios)

### SCENARIO 70: Permit change email notifications
**User:** expediter
**Starting state:** User has opted in to notifications, watches permits, nightly detects status changes
**Goal:** Be notified when watched permits change
**Expected outcome:** User receives one email per change (up to 10). With 11+ changes, receives a single digest email instead. Each email contains permit address, old→new status, date, and unsubscribe link.
**Edge cases:** SMTP failure logged but pipeline continues; dev mode skips sending.
**Status:** APPROVED (Sprint 68-A)

---

### SCENARIO 71: One-click unsubscribe from notification email
**User:** expediter
**Starting state:** Received a permit change notification email
**Goal:** Quickly opt out without logging in
**Expected outcome:** Email footer contains signed link. Clicking sets notifications to off. Token is user-specific and deterministic. Invalid token silently ignored.
**Status:** APPROVED (Sprint 68-A)

---

## MOBILE (1 scenario)

### SCENARIO 72: Mobile landing page without horizontal scroll
**User:** homeowner (mobile)
**Starting state:** Opens sfpermits.ai on iPhone SE (375px viewport)
**Goal:** Search for a permit address on phone
**Expected outcome:** No horizontal overflow. Nav badges scrollable. Search box stacks correctly below 480px. All touch targets >= 44px.
**Edge cases:** iOS Safari auto-zooms if input font-size < 16px — minimum 16px on all inputs.
**Status:** APPROVED (Sprint 68-A)

---

## PROPERTY RESEARCH (1 scenario)

### SCENARIO 29: Property health lookup by block/lot
**User:** expediter | architect
**Starting state:** Signal pipeline has run; property_health table populated
**Goal:** Look up health status of a specific parcel
**Expected outcome:** Returns tier label (HIGH RISK/AT RISK/BEHIND/SLOWER/ON TRACK), signal count, individual signal table, and recommended actions. Property with no signals returns explanation about nightly pipeline. DB unavailable returns graceful error.
**Status:** APPROVED (Sprint 68-A)
