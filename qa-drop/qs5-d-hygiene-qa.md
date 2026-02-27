# QS5-D Task Hygiene Diagnostic Sweep — QA Script

## Prerequisites
- Chief MCP server accessible
- Access to sf-permits-mcp codebase

## Checks

1. [NEW] All 12 Chief items investigated — PASS
   - Item 1 (addenda refresh #127): Investigated, closed
   - Item 2 (inspections PK #112): Investigated, closed
   - Item 3 (safety tagging #159): Investigated, closed
   - Item 4 (cost tracking #143): Investigated, updated (not wired)
   - Item 5 (Playwright suite #220): Investigated, closed
   - Item 6 (test personas #222): Investigated, closed
   - Item 7 (CRON_SECRET 403 #179): Investigated, closed
   - Item 8 (DQ checks #178): Investigated, new task created (#342)
   - Item 9 (property_signals #261): Investigated, kept open
   - Item 10 (orphaned tests #207): Investigated, closed
   - Item 11 (slow tests #210): Investigated, kept open
   - Item 12 (nightly CI #209): Investigated, closed

2. [NEW] chief_add_note called with summary — PASS
   - Full investigation summary note added to Chief brain state

3. [NEW] Stale tasks closed or updated — PASS
   - 8 tasks closed: #127, #112, #159, #179, #220, #222, #207, #209
   - 2 tasks kept open with justification: #261, #210
   - 1 task updated: #143 (noted DDL exists but middleware not wired)
   - 1 new task created: #342 (verify DQ checks on prod/staging)

4. [NEW] CHANGELOG-qs5-d.md documents findings — PASS (see below)
