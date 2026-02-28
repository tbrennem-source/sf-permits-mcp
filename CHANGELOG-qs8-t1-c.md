# CHANGELOG — QS8-T1-C: SODA Circuit Breaker

## [QS8-T1-C] — 2026-02-27

### Added

#### `src/soda_client.py`
- New `CircuitBreaker` class with three states: `closed` (normal), `open` (failing), `half-open` (probing after cooldown)
- `CircuitBreaker.is_open()` — returns True when requests should be short-circuited; automatically transitions `open → half-open` after `recovery_timeout` seconds
- `CircuitBreaker.record_success()` — resets breaker to closed, clears failure count
- `CircuitBreaker.record_failure()` — increments failure count; opens circuit at threshold; re-opens from half-open state if probe fails
- `SODAClient.circuit_breaker` instance — one circuit breaker per client, initialized from env vars at startup
- `SODA_CB_THRESHOLD` env var — failure count before opening (default: 5)
- `SODA_CB_TIMEOUT` env var — seconds before half-open recovery probe (default: 60)
- `SODAClient.query()` integration:
  - Short-circuits with `return []` when circuit is open (graceful degradation)
  - Calls `record_success()` on successful HTTP 2xx response
  - Calls `record_failure()` on `httpx.TimeoutException`, `httpx.NetworkError`, and HTTP 5xx responses
  - 4xx errors (caller bugs) do NOT increment failure count
- Structured logging for circuit state transitions (open/closed/half-open)

#### `tests/test_sprint_79_4.py`
- 19 tests covering:
  - `test_circuit_breaker_starts_closed`
  - `test_opens_exactly_at_threshold`
  - `test_failure_count_increments`
  - `test_default_threshold_is_five`
  - `test_transitions_to_half_open_after_timeout`
  - `test_stays_open_before_timeout`
  - `test_half_open_resets_to_closed_on_success`
  - `test_half_open_reopens_on_failure`
  - `test_success_resets_failure_count`
  - `test_success_on_closed_is_noop`
  - `test_returns_empty_list_when_open`
  - `test_no_http_call_when_circuit_open`
  - `test_records_success_on_200_response`
  - `test_records_failure_on_timeout`
  - `test_circuit_opens_after_repeated_timeouts`
  - `test_records_failure_on_5xx`
  - `test_4xx_does_not_trip_circuit`
  - `test_default_threshold_from_env`
  - `test_default_values_without_env`
