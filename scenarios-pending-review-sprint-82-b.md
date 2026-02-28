## SUGGESTED SCENARIO: Admin views DB pool utilization in real-time

**Source:** web/routes_admin.py — /admin/health endpoint (Sprint 82-B)
**User:** admin
**Starting state:** Admin is logged in; production app is under moderate load with several active DB connections
**Goal:** Admin wants to assess whether the DB connection pool is under pressure without querying infrastructure directly
**Expected outcome:** Admin sees a pool card showing connections in use vs. available vs. max, with a fill bar reflecting current utilization. Card highlights visually when utilization is ≥ 70%. Panel auto-refreshes every 30 seconds without manual reload.
**Edge cases seen in code:** Pool is None (app just started or DuckDB mode) — card renders with 0/0 without crashing. Pool is exhausted (in_use == max) — bar fills to 100%, card shows danger border.
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Admin sees SODA circuit breaker state change

**Source:** src/soda_client.py — _soda_circuit_breaker singleton + web/routes_admin.py (Sprint 82-B)
**User:** admin
**Starting state:** SODA API has started returning errors; circuit breaker has accumulated failures and transitioned to "open" state
**Goal:** Admin wants to know if the external SODA data API is degraded so they can inform users or take action
**Expected outcome:** System Health panel shows the SODA circuit breaker card with a red dot and "OPEN" state label. After the recovery timeout elapses, state changes to "HALF-OPEN" (amber dot), then back to "CLOSED" (green dot) on the next successful probe. The 30-second auto-refresh picks up the state change without page reload.
**Edge cases seen in code:** CircuitBreaker is per-module singleton — state persists across requests within a process; workers may have divergent state.
**CC confidence:** medium
**Status:** PENDING REVIEW
