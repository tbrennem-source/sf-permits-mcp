"""Client for Socrata Open Data API (SODA) 2.1 — data.sfgov.org"""

import httpx
import logging
import os
import time
from typing import Any


logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Simple circuit breaker for the SODA API client.

    States:
        closed   — normal operation; requests pass through
        open     — too many failures; requests short-circuit immediately
        half-open — recovery_timeout elapsed; one probe allowed through

    Thresholds are configurable via environment variables:
        SODA_CB_THRESHOLD  — consecutive failures before opening (default 5)
        SODA_CB_TIMEOUT    — seconds before transitioning open → half-open (default 60)
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.state: str = "closed"  # closed | open | half-open

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def is_open(self) -> bool:
        """Return True if requests should be short-circuited.

        Handles the open → half-open transition automatically: once
        recovery_timeout seconds have elapsed since the last failure,
        the breaker moves to half-open and allows one probe through.
        """
        if self.state == "closed":
            return False

        if self.state == "open":
            if self.last_failure_time is not None:
                elapsed = time.monotonic() - self.last_failure_time
                if elapsed >= self.recovery_timeout:
                    self.state = "half-open"
                    logger.info(
                        "SODA circuit breaker → half-open (%.0fs since last failure, probing)",
                        elapsed,
                    )
                    return False  # allow the probe request through
            return True

        # half-open: allow the probe through
        return False

    def record_success(self) -> None:
        """Record a successful request. Resets the breaker to closed."""
        if self.state != "closed":
            logger.info(
                "SODA circuit breaker → closed (success after %d failures)",
                self.failure_count,
            )
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"

    def record_failure(self) -> None:
        """Record a failed request. Opens the circuit once threshold is hit."""
        self.failure_count += 1
        self.last_failure_time = time.monotonic()

        if self.state == "half-open":
            # Probe failed — go back to open
            self.state = "open"
            logger.warning(
                "SODA circuit breaker → open (probe failed, cooldown %ds)",
                self.recovery_timeout,
            )
            return

        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(
                "SODA circuit breaker → open (%d/%d failures, cooldown %ds)",
                self.failure_count,
                self.failure_threshold,
                self.recovery_timeout,
            )


class SODAClient:
    """Async client for Socrata Open Data API (SODA) 2.1.

    Wraps SoQL queries against data.sfgov.org endpoints.
    Supports app token auth for higher rate limits.

    A circuit breaker protects downstream callers from cascading failures
    when the SODA API is unavailable.  Thresholds are controlled by:
        SODA_CB_THRESHOLD  — failures before opening (default 5)
        SODA_CB_TIMEOUT    — seconds before attempting recovery (default 60)
    """

    BASE_URL = "https://data.sfgov.org/resource"

    def __init__(self):
        self.app_token = os.environ.get("SODA_APP_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=int(os.environ.get("SODA_CB_THRESHOLD", "5")),
            recovery_timeout=int(os.environ.get("SODA_CB_TIMEOUT", "60")),
        )

    async def query(
        self,
        endpoint_id: str,
        select: str | None = None,
        where: str | None = None,
        order: str | None = None,
        group: str | None = None,
        having: str | None = None,
        q: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Execute a SoQL query against a SODA endpoint.

        Args:
            endpoint_id: The 9-char dataset identifier (e.g., 'i98e-djp9')
            select: SoQL $select clause (columns, aggregations)
            where: SoQL $where clause (filter conditions)
            order: SoQL $order clause (sort)
            group: SoQL $group clause (aggregation grouping)
            having: SoQL $having clause (post-aggregation filter)
            q: Full-text search query ($q parameter)
            limit: Max records to return (default 100, SODA max 50,000)
            offset: Pagination offset

        Returns:
            List of result dictionaries, or an empty list when the circuit
            breaker is open (graceful degradation).

        Raises:
            httpx.HTTPStatusError: On API errors (4xx, 5xx)
        """
        if self.circuit_breaker.is_open():
            logger.info(
                "SODA circuit breaker open — skipping query for endpoint %s",
                endpoint_id,
            )
            return []

        url = f"{self.BASE_URL}/{endpoint_id}.json"
        params: dict[str, Any] = {"$limit": limit, "$offset": offset}

        if select:
            params["$select"] = select
        if where:
            params["$where"] = where
        if order:
            params["$order"] = order
        if group:
            params["$group"] = group
        if having:
            params["$having"] = having
        if q:
            params["$q"] = q

        headers = {}
        if self.app_token:
            headers["X-App-Token"] = self.app_token

        try:
            response = await self.client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
            self.circuit_breaker.record_success()
            return result
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning(
                "SODA network error for %s: %s — recording failure",
                endpoint_id,
                exc,
            )
            self.circuit_breaker.record_failure()
            raise
        except httpx.HTTPStatusError as exc:
            # 5xx errors count as failures; 4xx are caller errors and don't
            if exc.response.status_code >= 500:
                logger.warning(
                    "SODA 5xx error %d for %s — recording failure",
                    exc.response.status_code,
                    endpoint_id,
                )
                self.circuit_breaker.record_failure()
            raise

    async def count(self, endpoint_id: str, where: str | None = None) -> int:
        """Get record count for a dataset, optionally filtered.

        Args:
            endpoint_id: The dataset identifier
            where: Optional SoQL filter

        Returns:
            Total record count
        """
        result = await self.query(
            endpoint_id,
            select="count(*) as count",
            where=where,
        )
        return int(result[0]["count"]) if result else 0

    async def schema(self, endpoint_id: str) -> list[str]:
        """Get field names by fetching one record.

        Args:
            endpoint_id: The dataset identifier

        Returns:
            List of field names
        """
        result = await self.query(endpoint_id, limit=1)
        return list(result[0].keys()) if result else []

    async def close(self):
        """Close the underlying HTTP client."""
        await self.client.aclose()
