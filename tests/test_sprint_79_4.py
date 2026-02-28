"""Tests for SODA API circuit breaker (QS8-T1-C).

Covers:
    - CircuitBreaker state transitions (closed → open → half-open → closed)
    - SODAClient returns empty list when circuit is open
    - SODAClient resets breaker on success
    - Configurable thresholds via env vars
"""

import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.soda_client import CircuitBreaker, SODAClient


# ---------------------------------------------------------------------------
# CircuitBreaker unit tests
# ---------------------------------------------------------------------------


class TestCircuitBreakerStartsClosed:
    def test_circuit_breaker_starts_closed(self):
        cb = CircuitBreaker()
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.is_open() is False


class TestCircuitBreakerOpensAfterThreshold:
    def test_opens_exactly_at_threshold(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
        # 2 failures — still closed
        cb.record_failure()
        cb.record_failure()
        assert cb.state == "closed"
        assert cb.is_open() is False
        # 3rd failure — opens
        cb.record_failure()
        assert cb.state == "open"
        assert cb.is_open() is True

    def test_failure_count_increments(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        for i in range(4):
            cb.record_failure()
        assert cb.failure_count == 4
        assert cb.state == "closed"

    def test_default_threshold_is_five(self):
        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        for _ in range(4):
            cb.record_failure()
        assert cb.state == "closed"
        cb.record_failure()
        assert cb.state == "open"


class TestCircuitBreakerRecoveryAfterTimeout:
    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        assert cb.state == "open"
        # Simulate timeout elapsed by setting last_failure_time in the past
        cb.last_failure_time = time.monotonic() - 61
        assert cb.is_open() is False  # allows probe through
        assert cb.state == "half-open"

    def test_stays_open_before_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        assert cb.state == "open"
        # No time has elapsed
        assert cb.is_open() is True
        assert cb.state == "open"

    def test_half_open_resets_to_closed_on_success(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        cb.last_failure_time = time.monotonic() - 61
        cb.is_open()  # trigger half-open transition
        assert cb.state == "half-open"
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0
        assert cb.is_open() is False

    def test_half_open_reopens_on_failure(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=60)
        cb.record_failure()
        cb.last_failure_time = time.monotonic() - 61
        cb.is_open()  # trigger half-open
        assert cb.state == "half-open"
        cb.record_failure()  # probe failed
        assert cb.state == "open"
        assert cb.is_open() is True


class TestCircuitBreakerSuccessResets:
    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"

    def test_success_on_closed_is_noop(self):
        cb = CircuitBreaker()
        cb.record_success()
        assert cb.state == "closed"
        assert cb.failure_count == 0


# ---------------------------------------------------------------------------
# SODAClient + circuit breaker integration tests
# ---------------------------------------------------------------------------


class TestSODAClientReturnsEmptyWhenCircuitOpen:
    def test_returns_empty_list_when_open(self):
        client = SODAClient()
        # Force the circuit open
        client.circuit_breaker.state = "open"
        client.circuit_breaker.last_failure_time = time.monotonic()

        result = asyncio.run(client.query("test-123"))
        assert result == []

    def test_no_http_call_when_circuit_open(self):
        client = SODAClient()
        client.circuit_breaker.state = "open"
        client.circuit_breaker.last_failure_time = time.monotonic()

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            asyncio.run(client.query("test-123"))
            mock_get.assert_not_called()


class TestSODAClientResetsOnSuccess:
    def test_records_success_on_200_response(self):
        client = SODAClient()
        # Plant a failure so we can verify it gets reset
        client.circuit_breaker.record_failure()
        client.circuit_breaker.record_failure()
        assert client.circuit_breaker.failure_count == 2

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value=[{"permit_number": "A123"}])

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            result = asyncio.run(client.query("i98e-djp9"))

        assert result == [{"permit_number": "A123"}]
        assert client.circuit_breaker.state == "closed"
        assert client.circuit_breaker.failure_count == 0

    def test_records_failure_on_timeout(self):
        client = SODAClient()
        assert client.circuit_breaker.failure_count == 0

        with patch.object(
            client.client,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            with pytest.raises(httpx.TimeoutException):
                asyncio.run(client.query("i98e-djp9"))

        assert client.circuit_breaker.failure_count == 1

    def test_circuit_opens_after_repeated_timeouts(self):
        client = SODAClient()
        client.circuit_breaker.failure_threshold = 3

        with patch.object(
            client.client,
            "get",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("timed out"),
        ):
            for _ in range(3):
                try:
                    asyncio.run(client.query("i98e-djp9"))
                except httpx.TimeoutException:
                    pass

        assert client.circuit_breaker.state == "open"

    def test_records_failure_on_5xx(self):
        client = SODAClient()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 503
        error = httpx.HTTPStatusError(
            "503 Service Unavailable",
            request=mock_request,
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=error)

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(client.query("i98e-djp9"))

        assert client.circuit_breaker.failure_count == 1

    def test_4xx_does_not_trip_circuit(self):
        client = SODAClient()

        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 404
        error = httpx.HTTPStatusError(
            "404 Not Found",
            request=mock_request,
            response=mock_response,
        )
        mock_response.raise_for_status = MagicMock(side_effect=error)

        with patch.object(client.client, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                asyncio.run(client.query("i98e-djp9"))

        # 4xx should NOT increment failure count
        assert client.circuit_breaker.failure_count == 0
        assert client.circuit_breaker.state == "closed"


class TestSODAClientConfigurableThresholds:
    def test_default_threshold_from_env(self, monkeypatch):
        monkeypatch.setenv("SODA_CB_THRESHOLD", "3")
        monkeypatch.setenv("SODA_CB_TIMEOUT", "30")
        client = SODAClient()
        assert client.circuit_breaker.failure_threshold == 3
        assert client.circuit_breaker.recovery_timeout == 30

    def test_default_values_without_env(self, monkeypatch):
        monkeypatch.delenv("SODA_CB_THRESHOLD", raising=False)
        monkeypatch.delenv("SODA_CB_TIMEOUT", raising=False)
        client = SODAClient()
        assert client.circuit_breaker.failure_threshold == 5
        assert client.circuit_breaker.recovery_timeout == 60
