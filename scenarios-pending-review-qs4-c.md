## SUGGESTED SCENARIO: Consistent Obsidian design from landing through dashboard
**Source:** QS4-C Obsidian design migration (index.html + brief.html)
**User:** expediter | homeowner | architect
**Starting state:** User is on the landing page (not logged in)
**Goal:** Experience a visually consistent design when transitioning from landing page through login to the authenticated dashboard
**Expected outcome:** Landing page, index/search page, and morning brief all share the same color palette (deep navy backgrounds, cyan accents, IBM Plex Sans body text, JetBrains Mono headings), with no jarring visual shifts between pages
**Edge cases seen in code:** Nav fragment uses legacy alias vars that must resolve to Obsidian tokens; body.obsidian class must be present for design-system.css to activate
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Morning brief health indicators use signal colors
**Source:** QS4-C Obsidian design migration (brief.html signal colors)
**User:** expediter
**Starting state:** User has watched properties with varying health statuses (on_track, slower, behind, at_risk)
**Goal:** Quickly scan the morning brief and identify which properties need attention based on color coding
**Expected outcome:** Health indicators use signal-green for on_track, signal-amber for slower/behind, and signal-red for at_risk, matching the Obsidian design system's signal color palette used on the landing page
**Edge cases seen in code:** Health status classes (.health-on_track, .health-slower, etc.) use var(--success), var(--warning), var(--error) which now alias to signal colors via head_obsidian.html
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Google Fonts loaded once via shared fragment
**Source:** QS4-C head_obsidian.html shared fragment
**User:** all
**Starting state:** Any Obsidian-migrated page is loaded
**Goal:** Page loads efficiently without duplicate font requests
**Expected outcome:** Google Fonts (IBM Plex Sans, JetBrains Mono) are loaded via a single shared fragment (head_obsidian.html) included by all migrated templates, rather than each template having its own font link — reducing duplicate network requests and ensuring font consistency
**Edge cases seen in code:** design-system.css also has an @import for Google Fonts; the fragment uses preconnect hints for faster loading
**CC confidence:** medium
**Status:** PENDING REVIEW
