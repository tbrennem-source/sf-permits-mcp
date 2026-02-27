## SUGGESTED SCENARIO: Demo page shows severity tier for active permits
**Source:** web/routes_misc.py _get_demo_data() + web/templates/demo.html severity badges
**User:** expediter
**Starting state:** User navigates to /demo as an anonymous visitor
**Goal:** Understand at a glance whether the demo property has high-risk active permits
**Expected outcome:** A severity badge (CRITICAL/HIGH/MEDIUM/LOW/GREEN) appears on the hero section and inline with each active permit in the permit table; color distinguishes risk level
**Edge cases seen in code:** If DB is unavailable, severity_tier is None and the banner is simply not rendered — no error displayed
**CC confidence:** high
**Status:** PENDING REVIEW
