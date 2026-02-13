"""Client for Socrata Open Data API (SODA) 2.1 — data.sfgov.org"""

import httpx
import os
from typing import Any


class SODAClient:
    """Async client for Socrata Open Data API (SODA) 2.1.

    Wraps SoQL queries against data.sfgov.org endpoints.
    Supports app token auth for higher rate limits.
    """

    BASE_URL = "https://data.sfgov.org/resource"

    def __init__(self):
        self.app_token = os.environ.get("SODA_APP_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

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
            List of result dictionaries.

        Raises:
            httpx.HTTPStatusError: On API errors (4xx, 5xx)
        """
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

        response = await self.client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

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
