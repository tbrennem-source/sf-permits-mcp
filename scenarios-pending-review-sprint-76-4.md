## SUGGESTED SCENARIO: admin navigates ops dashboard across tabs
**Source:** admin_ops.html Obsidian migration (Sprint 76-4)
**User:** admin
**Starting state:** Admin is logged in, visits /admin/ops
**Goal:** Check pipeline health, then look at feedback, then check user activity — all in one session
**Expected outcome:** Tab navigation loads each panel without a full page reload; hash in URL updates to reflect current tab; back/forward navigation restores correct tab
**Edge cases seen in code:** Hash aliases (luck, dq, watch, intelligence) allow bookmarking with friendly names; 30s HTMX timeout shows error if server is slow
**CC confidence:** high
**Status:** PENDING REVIEW
