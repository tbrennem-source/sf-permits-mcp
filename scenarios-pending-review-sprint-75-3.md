## SUGGESTED SCENARIO: Account page renders with Obsidian dark theme

**Source:** web/templates/account.html Obsidian migration
**User:** expediter | homeowner | architect
**Starting state:** User is authenticated and navigates to their account page
**Goal:** View account settings, watched addresses, and plan analyses in the Obsidian dark theme
**Expected outcome:** Page loads with dark background, JetBrains Mono headings, IBM Plex Sans body text, card sections clearly separated, no white/light background visible
**Edge cases seen in code:** Admin users see tab bar with Settings/Admin tabs; non-admins see settings directly without tab bar. Both paths must render correctly under Obsidian.
**CC confidence:** high
**Status:** PENDING REVIEW
