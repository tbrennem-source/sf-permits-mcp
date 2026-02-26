"""Station path predictor — transition probabilities from addenda routing data.

Computes P(next_station | current_station) using LEAD() window function
over the addenda table. Predicts remaining routing path for active permits.
"""
import logging
from src.db import get_connection, execute_write, query, BACKEND

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


def ensure_station_transitions_table() -> None:
    """Create station_transitions table if it doesn't exist."""
    if BACKEND == "postgres":
        execute_write("""
            CREATE TABLE IF NOT EXISTS station_transitions (
                from_station VARCHAR(30),
                to_station VARCHAR(30),
                probability FLOAT,
                transition_count INTEGER,
                sample_permits INTEGER,
                permit_type_bucket TEXT DEFAULT 'all',
                updated_at TIMESTAMP DEFAULT NOW(),
                PRIMARY KEY (from_station, to_station, permit_type_bucket)
            )
        """)
    # DuckDB: handled in-memory during refresh


def refresh_station_transitions() -> dict:
    """Compute station transition probabilities from addenda data.

    Algorithm:
    1. For each permit, order stations by step/arrive
    2. Use LEAD() window function to find next station
    3. Count transitions and compute probabilities

    Returns dict with stats for logging.
    """
    ensure_station_transitions_table()

    if BACKEND != "postgres":
        logger.info("Station transitions refresh skipped (DuckDB)")
        return {"transitions": 0}

    # The SQL uses LEAD() to compute next-station for each routing step
    # Filter: post-2018, non-null stations, finished reviews only
    sql = """
        WITH ordered_steps AS (
            SELECT
                application_number,
                station,
                LEAD(station) OVER (
                    PARTITION BY application_number
                    ORDER BY step, arrive
                ) AS next_station
            FROM addenda
            WHERE station IS NOT NULL
              AND finish_date IS NOT NULL
              AND CAST(finish_date AS DATE) >= '2018-01-01'
        ),
        transition_counts AS (
            SELECT
                station AS from_station,
                next_station AS to_station,
                COUNT(*) AS transition_count,
                COUNT(DISTINCT application_number) AS sample_permits
            FROM ordered_steps
            WHERE next_station IS NOT NULL
            GROUP BY station, next_station
            HAVING COUNT(*) >= 5
        ),
        station_totals AS (
            SELECT from_station, SUM(transition_count) AS total
            FROM transition_counts
            GROUP BY from_station
        )
        INSERT INTO station_transitions
            (from_station, to_station, probability, transition_count, sample_permits, permit_type_bucket, updated_at)
        SELECT
            tc.from_station,
            tc.to_station,
            ROUND(tc.transition_count::NUMERIC / st.total, 4) AS probability,
            tc.transition_count,
            tc.sample_permits,
            'all',
            NOW()
        FROM transition_counts tc
        JOIN station_totals st ON tc.from_station = st.from_station
        ON CONFLICT (from_station, to_station, permit_type_bucket) DO UPDATE SET
            probability = EXCLUDED.probability,
            transition_count = EXCLUDED.transition_count,
            sample_permits = EXCLUDED.sample_permits,
            updated_at = NOW()
    """

    try:
        execute_write(sql)
        rows = query("SELECT COUNT(*) FROM station_transitions")
        count = rows[0][0] if rows else 0
        return {"transitions": count}
    except Exception as e:
        logger.exception("refresh_station_transitions failed")
        return {"transitions": 0, "error": str(e)}


def predict_remaining_path(
    current_station: str,
    max_steps: int = 10,
    min_probability: float = 0.1,
) -> list[dict]:
    """Predict remaining routing path from current station.

    Uses greedy most-probable-path: at each station, take the highest-probability
    next station. Stop at terminal stations (PERMIT-CTR, etc.) or when P < min_probability.

    Enriches each predicted station with p50/p75 from station_velocity_v2.

    Returns list of dicts:
    [
        {"station": "SFFD", "probability": 0.85, "p50_days": 4, "p75_days": 8},
        {"station": "PERMIT-CTR", "probability": 0.92, "p50_days": 1, "p75_days": 2},
    ]
    """
    ph = _ph()
    terminal_stations = {"PERMIT-CTR", "ISSUED", "COMPLETE"}
    path = []
    visited = {current_station}
    station = current_station

    for _ in range(max_steps):
        # Get most probable next station
        try:
            rows = query(
                f"SELECT to_station, probability FROM station_transitions "
                f"WHERE from_station = {ph} AND permit_type_bucket = 'all' "
                f"ORDER BY probability DESC LIMIT 1",
                (station,),
            )
        except Exception:
            break

        if not rows:
            break

        next_station = rows[0][0]
        prob = float(rows[0][1])

        if prob < min_probability:
            break
        if next_station in visited:
            break

        # Get velocity for this station
        p50_days = None
        p75_days = None
        try:
            vel_rows = query(
                f"SELECT p50_days, p75_days FROM station_velocity_v2 "
                f"WHERE station = {ph} AND metric_type = 'initial' "
                f"AND period IN ('current', 'baseline') "
                f"ORDER BY CASE period WHEN 'current' THEN 0 ELSE 1 END "
                f"LIMIT 1",
                (next_station,),
            )
            if vel_rows:
                p50_days = float(vel_rows[0][0]) if vel_rows[0][0] else None
                p75_days = float(vel_rows[0][1]) if vel_rows[0][1] else None
        except Exception:
            pass

        path.append({
            "station": next_station,
            "probability": prob,
            "p50_days": p50_days,
            "p75_days": p75_days,
        })

        visited.add(next_station)
        station = next_station

        if next_station in terminal_stations:
            break

    return path


def predict_total_remaining_days(current_station: str) -> dict | None:
    """Get total estimated remaining days from current station to completion.

    Returns dict with p50 and p75 total remaining days, or None.
    """
    path = predict_remaining_path(current_station)
    if not path:
        return None

    total_p50 = sum(s["p50_days"] or 0 for s in path)
    total_p75 = sum(s["p75_days"] or 0 for s in path)

    return {
        "remaining_stations": len(path),
        "p50_remaining_days": round(total_p50),
        "p75_remaining_days": round(total_p75),
        "path": path,
        "next_station": path[0]["station"] if path else None,
        "next_p50_days": path[0]["p50_days"] if path else None,
    }
