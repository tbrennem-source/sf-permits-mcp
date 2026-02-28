## SUGGESTED SCENARIO: SODA API circuit breaker opens after repeated failures
**Source:** src/soda_client.py — CircuitBreaker integration with SODAClient.query()
**User:** homeowner | expediter
**Starting state:** SODA API is returning 503 errors or timing out on every request
**Goal:** User searches for permit data; app should not hang or surface raw errors
**Expected outcome:** After the failure threshold is reached, all SODA queries return empty results immediately without making network calls. The UI degrades gracefully (shows no results) rather than returning error pages or stalling.
**Edge cases seen in code:** 4xx errors (e.g., bad dataset ID) do NOT trip the circuit — only 5xx and network errors count as failures
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: SODA circuit breaker auto-recovers after cooldown
**Source:** src/soda_client.py — CircuitBreaker.is_open() half-open transition
**User:** expediter
**Starting state:** Circuit breaker was opened due to SODA API failures; recovery_timeout seconds have passed
**Goal:** Resume normal permit data queries without manual restart
**Expected outcome:** The next query after the cooldown window acts as a probe. If it succeeds, the circuit closes and normal queries resume. If it fails, the circuit reopens and the cooldown restarts.
**Edge cases seen in code:** Half-open state allows exactly one probe — not multiple concurrent probes
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Circuit breaker thresholds configurable per deployment
**Source:** src/soda_client.py — SODA_CB_THRESHOLD and SODA_CB_TIMEOUT env vars
**User:** admin
**Starting state:** Default thresholds (5 failures, 60s cooldown) are too aggressive for a slow network environment
**Goal:** Operator adjusts circuit breaker sensitivity without code changes
**Expected outcome:** Setting SODA_CB_THRESHOLD=3 and SODA_CB_TIMEOUT=120 in Railway env vars changes behavior at app startup — lower failure tolerance, longer cooldown
**Edge cases seen in code:** Values are parsed as int() at client instantiation, not lazily — restart required for changes to take effect
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: 4xx SODA errors do not trigger circuit breaker
**Source:** src/soda_client.py — HTTPStatusError handling in query()
**User:** expediter
**Starting state:** A tool passes an invalid dataset ID or malformed SoQL query to the SODA client
**Goal:** Bad queries surface as errors without poisoning the circuit breaker for healthy queries
**Expected outcome:** HTTPStatusError is raised to the caller as before; failure_count stays at 0; subsequent queries to valid endpoints succeed normally
**CC confidence:** high
**Status:** PENDING REVIEW
