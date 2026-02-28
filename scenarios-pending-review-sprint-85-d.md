## SUGGESTED SCENARIO: New developer reads README and finds accurate project stats
**Source:** README.md update (Sprint 85-D docs consolidation)
**User:** architect | expediter
**Starting state:** Developer opens README.md on a fresh checkout to understand project scope
**Goal:** Quickly understand how many tools exist, how many tests pass, and what phases are complete
**Expected outcome:** README accurately states 34 tools, 4357+ tests, and all phases 1-8 complete; no stale numbers from earlier sprints
**Edge cases seen in code:** README previously showed 21 tools and outdated test counts; stale docs cause developer confusion about what's actually shipped
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Architecture doc describes all 34 tools with one-line summaries
**Source:** docs/ARCHITECTURE.md update (Sprint 85-D docs consolidation)
**User:** architect | expediter
**Starting state:** Developer opens ARCHITECTURE.md to understand which tool to use for a given task
**Goal:** Find the right MCP tool by scanning the tool inventory
**Expected outcome:** ARCHITECTURE.md lists all 34 tools with file paths and one-line descriptions; Phase 8 tools (predict_next_stations, diagnose_stuck_permit, simulate_what_if, calculate_delay_cost) are clearly described with their algorithms and data sources
**Edge cases seen in code:** Architecture doc previously showed 21 tools and was missing Phase 6-8 tools entirely
**CC confidence:** high
**Status:** PENDING REVIEW
