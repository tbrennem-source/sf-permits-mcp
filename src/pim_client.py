"""PIM ArcGIS REST API client for SF Planning parcel data.

Queries the SF Planning Information Map (PIM) ArcGIS service for authoritative
zoning, historic district, height limits, and special use data per parcel.

API: https://sfplanninggis.org/arcgisext/rest/services/PIM/MapServer/0/query
No authentication required. 5-second timeout.

Usage:
    from src.pim_client import query_pim_cached
    data = await query_pim_cached("3512", "001")
    # data = {"ZONING_CODE": "RH-2", "HISTORIC_DISTRICT": None, ...} or None
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# PIM ArcGIS endpoint
PIM_BASE_URL = "https://sfplanninggis.org/arcgisext/rest/services/PIM/MapServer/0/query"
PIM_TIMEOUT = 5  # seconds

# Cache TTL: 30 days
PIM_CACHE_TTL_DAYS = 30

# Fields we extract from PIM response
PIM_FIELDS = [
    "ZONING_CODE",
    "ZONING_CATEGORY",
    "HISTORIC_DISTRICT",
    "HEIGHT_DIST",
    "SPECIAL_USE_DIST",
    "LANDMARK",
]


def _ensure_pim_cache_table(conn, backend: str) -> None:
    """Create pim_cache table if it doesn't exist. Idempotent."""
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pim_cache (
                    block TEXT NOT NULL,
                    lot TEXT NOT NULL,
                    response_json JSONB,
                    fetched_at TIMESTAMPTZ DEFAULT NOW(),
                    PRIMARY KEY (block, lot)
                )
            """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_pim_cache_fetched ON pim_cache (fetched_at)"
            )
        conn.commit()
    else:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pim_cache (
                block TEXT NOT NULL,
                lot TEXT NOT NULL,
                response_json TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (block, lot)
            )
        """)
        conn.commit()


def _get_cached(block: str, lot: str, conn, backend: str) -> Optional[dict]:
    """Return cached PIM data if present and not expired. Returns None if miss."""
    try:
        _ensure_pim_cache_table(conn, backend)
        ph = "%s" if backend == "postgres" else "?"
        if backend == "postgres":
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT response_json, fetched_at FROM pim_cache"
                    f" WHERE block = {ph} AND lot = {ph}",
                    [block, lot],
                )
                row = cur.fetchone()
        else:
            row = conn.execute(
                f"SELECT response_json, fetched_at FROM pim_cache"
                f" WHERE block = {ph} AND lot = {ph}",
                [block, lot],
            ).fetchone()

        if not row:
            return None

        response_json, fetched_at = row

        # Check TTL
        if fetched_at:
            if isinstance(fetched_at, str):
                # DuckDB returns strings
                try:
                    fetched_at = datetime.fromisoformat(fetched_at)
                except ValueError:
                    fetched_at = None
            if fetched_at:
                if fetched_at.tzinfo is None:
                    fetched_at = fetched_at.replace(tzinfo=timezone.utc)
                age = datetime.now(tz=timezone.utc) - fetched_at
                if age > timedelta(days=PIM_CACHE_TTL_DAYS):
                    logger.debug("PIM cache expired for %s/%s (age=%s)", block, lot, age)
                    return None

        if response_json is None:
            return {}  # Cached empty result (API returned no features)

        if isinstance(response_json, dict):
            return response_json
        if isinstance(response_json, str):
            return json.loads(response_json)
        return None
    except Exception as exc:
        logger.debug("PIM cache read failed for %s/%s: %s", block, lot, exc)
        return None


def _write_cache(block: str, lot: str, data: Optional[dict], conn, backend: str) -> None:
    """Write PIM data to cache. data=None means no features returned by API."""
    try:
        _ensure_pim_cache_table(conn, backend)
        ph = "%s" if backend == "postgres" else "?"
        json_val = json.dumps(data) if data is not None else None

        if backend == "postgres":
            with conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO pim_cache (block, lot, response_json, fetched_at)"
                    f" VALUES ({ph}, {ph}, {ph}, NOW())"
                    f" ON CONFLICT (block, lot)"
                    f" DO UPDATE SET response_json = EXCLUDED.response_json,"
                    f"               fetched_at = NOW()",
                    [block, lot, json_val],
                )
            conn.commit()
        else:
            conn.execute(
                f"INSERT OR REPLACE INTO pim_cache (block, lot, response_json, fetched_at)"
                f" VALUES ({ph}, {ph}, {ph}, CURRENT_TIMESTAMP)",
                [block, lot, json_val],
            )
            conn.commit()
    except Exception as exc:
        logger.debug("PIM cache write failed for %s/%s: %s", block, lot, exc)


async def _fetch_pim_api(block: str, lot: str) -> Optional[dict]:
    """Fetch parcel data from PIM ArcGIS REST API.

    Returns dict of extracted fields or None on error/timeout.
    Returns {} if API succeeded but no features found for this parcel.
    """
    import httpx

    params = {
        "where": f"BLOCK_NUM='{block}' AND LOT_NUM='{lot}'",
        "outFields": "*",
        "f": "json",
    }

    try:
        async with httpx.AsyncClient(timeout=PIM_TIMEOUT) as client:
            resp = await client.get(PIM_BASE_URL, params=params)
            resp.raise_for_status()
            payload = resp.json()

        features = payload.get("features", [])
        if not features:
            logger.debug("PIM returned no features for block=%s lot=%s", block, lot)
            return {}  # Cache miss result, but API responded successfully

        attrs = features[0].get("attributes", {})
        # Extract only the fields we care about; normalize None/empty strings
        result = {}
        for field in PIM_FIELDS:
            val = attrs.get(field)
            if val == "" or val == "N/A":
                val = None
            result[field] = val

        logger.debug(
            "PIM API response for %s/%s: ZONING=%s HISTORIC=%s",
            block, lot,
            result.get("ZONING_CODE"),
            result.get("HISTORIC_DISTRICT"),
        )
        return result

    except httpx.TimeoutException:
        logger.warning("PIM API timeout for block=%s lot=%s (%.1fs)", block, lot, PIM_TIMEOUT)
        return None
    except httpx.HTTPError as exc:
        logger.warning("PIM API HTTP error for %s/%s: %s", block, lot, exc)
        return None
    except Exception as exc:
        logger.warning("PIM API unexpected error for %s/%s: %s", block, lot, exc)
        return None


async def query_pim_cached(block: str, lot: str) -> Optional[dict]:
    """Query PIM for parcel data, using DB cache with 30-day TTL.

    Returns:
        dict with PIM fields (ZONING_CODE, ZONING_CATEGORY, HISTORIC_DISTRICT,
        HEIGHT_DIST, SPECIAL_USE_DIST, LANDMARK) — some may be None.
        Returns {} if API responded but found no parcel.
        Returns None if PIM is unavailable (timeout/error) AND no cache exists.

    This function NEVER raises — all errors are caught and logged.
    Callers should treat None as "PIM unavailable, use fallback".
    """
    if not block or not lot:
        return None

    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        try:
            # 1. Check cache first
            cached = _get_cached(block, lot, conn, BACKEND)
            if cached is not None:
                logger.debug("PIM cache hit for %s/%s", block, lot)
                return cached if cached else None  # {} → None (no features)

            # 2. Cache miss — fetch from API
            logger.debug("PIM cache miss for %s/%s — querying API", block, lot)
            api_result = await _fetch_pim_api(block, lot)

            if api_result is None:
                # API failed — don't cache, return None so caller falls back
                return None

            # 3. Write to cache (including empty results so we don't re-query dead parcels)
            _write_cache(block, lot, api_result if api_result else None, conn, BACKEND)

            return api_result if api_result else None

        finally:
            conn.close()

    except Exception as exc:
        logger.warning("PIM query_pim_cached failed for %s/%s: %s", block, lot, exc)
        return None


def get_pim_coverage_gap_note(zoning_code: str) -> str:
    """Return a coverage gap note for zoning codes not in ref_zoning_routing."""
    return (
        f"Zoning routing not available for code {zoning_code!r}. "
        f"General routing rules applied."
    )
