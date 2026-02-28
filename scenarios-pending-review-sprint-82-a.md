## SUGGESTED SCENARIO: MCP client discovers all 34 tools
**Source:** src/server.py — Phase 9 tool registration
**User:** expediter
**Starting state:** MCP client connects to the SF Permits MCP server
**Goal:** Client wants to discover all available tools including the 4 new intelligence tools
**Expected outcome:** Client receives a tool list containing predict_next_stations, diagnose_stuck_permit, simulate_what_if, and calculate_delay_cost alongside the existing 30 tools (34 total)
**Edge cases seen in code:** Server must import all 4 tools without error on startup; any missing dependency causes the entire server to fail to load
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Intelligence tool returns formatted markdown via MCP
**Source:** src/server.py — simulate_what_if and calculate_delay_cost registration
**User:** expediter
**Starting state:** MCP client has connected and discovered tools; user provides a project description with two variations
**Goal:** User calls simulate_what_if to compare scoping options before filing a permit application
**Expected outcome:** Tool returns a markdown comparison table with timeline, fee, review path, and revision risk columns for each variation — consumable by Claude in a planning conversation
**Edge cases seen in code:** Simulator calls predict_permits, estimate_timeline, estimate_fees, revision_risk internally — any sub-tool failure degrades gracefully to "N/A" in the table
**CC confidence:** medium
**Status:** PENDING REVIEW
