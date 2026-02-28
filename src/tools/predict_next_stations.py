"""Tool: predict_next_stations — What's Next station predictor for SF permits.

Predicts what review stations a permit will visit next using:
1. The permit's current station (from addenda routing records)
2. Historical transition probabilities from similar permits
3. Velocity estimates (p50/p75) from station_velocity_v2

QS8-T2-A: New tool — What's Next station predictor.

Note: src/tools/station_predictor.py contains a lower-level transition matrix
refresh module (cron utility). This module provides the MCP-facing async tool.
"""

import logging
from datetime import date, timedelta

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

# Human-readable station labels
STATION_LABELS = {
    "BLDG": "Building Inspection",
    "CP-ZOC": "Planning (Zoning)",
    "SFFD": "Fire Department",
    "SFFD-HQ": "Fire Dept HQ",
    "HEALTH": "Health Dept",
    "HEALTH-FD": "Health (Food)",
    "HEALTH-HM": "Health (Hazmat)",
    "HEALTH-MH": "Health (Mental Health)",
    "HIS": "Historic Preservation",
    "DPW-BSM": "DPW (Bureau of Street Mgmt)",
    "DPW-BUF": "DPW (Bureau of Urban Forestry)",
    "SFPUC": "SF Public Utilities",
    "SFPUC-PRG": "SF PUC (PRG)",
    "PW-DAC": "DPW (Accessibility)",
    "PLANCK": "Planning (CK)",
    "PLAN": "Planning",
    "ELECT": "Electrical",
    "PLMB": "Plumbing",
    "MECH": "Mechanical",
    "PERMIT-CTR": "Permit Center",
}

# Stations that indicate review is complete
COMPLETE_STATUSES = {"complete", "issued", "approved", "cancelled", "withdrawn"}

# Minimum sample size for a transition edge to be considered
MIN_TRANSITION_SAMPLES = 5

# Days without activity to consider a permit stalled at a station
STALL_THRESHOLD_DAYS = 60

# Data lookback window for building transition matrix (days)
TRANSITION_LOOKBACK_DAYS = 3 * 365


def _ph() -> str:
    """Return the correct placeholder for the current DB backend."""
    return "%s" if BACKEND == "postgres" else "?"


def _label(station: str) -> str:
    """Return human-readable label for a station code."""
    return STATION_LABELS.get(station, station)


def _format_days(d: float | None) -> str:
    """Format a day count as a human-readable string."""
    if d is None:
        return "—"
    if d < 1:
        return "<1 day"
    if d < 7:
        return f"{d:.0f} days"
    if d < 30:
        weeks = d / 7
        return f"{weeks:.0f} wk"
    months = d / 30
    return f"{months:.1f} mo"


# ── DB query helpers ────────────────────────────────────────────────


def _get_permit_info(conn, permit_number: str) -> dict | None:
    """Fetch basic permit metadata: type, neighborhood, status, dates."""
    ph = _ph()
    sql = f"""
        SELECT permit_number, permit_type_definition, neighborhood,
               status, filed_date, issued_date, completed_date
        FROM permits
        WHERE permit_number = {ph}
        LIMIT 1
    """
    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, [permit_number])
                row = cur.fetchone()
        else:
            row = conn.execute(sql, [permit_number]).fetchone()
    except Exception:
        logger.warning("_get_permit_info: query failed for %s", permit_number, exc_info=True)
        return None

    if not row:
        return None

    return {
        "permit_number": row[0],
        "permit_type": row[1] or "Unknown",
        "neighborhood": row[2],
        "status": row[3],
        "filed_date": str(row[4]) if row[4] else None,
        "issued_date": str(row[5]) if row[5] else None,
        "completed_date": str(row[6]) if row[6] else None,
    }


def _get_station_history(conn, permit_number: str) -> list[dict]:
    """Fetch this permit's addenda routing history, deduped, ordered by arrive.

    Deduplication: for each (station, addenda_number) pair, keep the record
    with the latest finish_date (handles reassignment dupes in SODA data).
    """
    ph = _ph()

    if BACKEND == "postgres":
        sql = """
            WITH ranked AS (
                SELECT station, arrive, finish_date, review_results, addenda_number,
                       ROW_NUMBER() OVER (
                           PARTITION BY station, addenda_number
                           ORDER BY finish_date DESC NULLS LAST
                       ) AS rn
                FROM addenda
                WHERE application_number = %s
                  AND station IS NOT NULL
            )
            SELECT station, arrive, finish_date, review_results, addenda_number
            FROM ranked
            WHERE rn = 1
            ORDER BY arrive ASC NULLS LAST, addenda_number ASC
        """
        params: list = [permit_number]
    else:
        sql = """
            WITH ranked AS (
                SELECT station, arrive, finish_date, review_results, addenda_number,
                       ROW_NUMBER() OVER (
                           PARTITION BY station, addenda_number
                           ORDER BY finish_date DESC NULLS LAST
                       ) AS rn
                FROM addenda
                WHERE application_number = ?
                  AND station IS NOT NULL
            )
            SELECT station, arrive, finish_date, review_results, addenda_number
            FROM ranked
            WHERE rn = 1
            ORDER BY arrive ASC NULLS LAST, addenda_number ASC
        """
        params = [permit_number]

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
        else:
            rows = conn.execute(sql, params).fetchall()
    except Exception:
        logger.warning("_get_station_history: query failed for %s", permit_number, exc_info=True)
        return []

    return [
        {
            "station": row[0],
            "arrive": str(row[1]) if row[1] else None,
            "finish_date": str(row[2]) if row[2] else None,
            "review_results": row[3],
            "addenda_number": row[4],
        }
        for row in rows
    ]


def _find_current_station(history: list[dict]) -> dict | None:
    """Return the most recently arrived station that hasn't finished yet.

    Returns None when all stations have finish_dates (permit fully routed).
    """
    unfinished = [h for h in history if h["arrive"] and not h["finish_date"]]
    if not unfinished:
        return None
    return max(unfinished, key=lambda x: x["arrive"] or "")


def _compute_dwell_days(station_rec: dict) -> int | None:
    """Return number of days this permit has been at the given station."""
    arrive = station_rec.get("arrive")
    if not arrive:
        return None
    try:
        arrive_date = date.fromisoformat(str(arrive)[:10])
        return (date.today() - arrive_date).days
    except Exception:
        return None


def _build_transition_matrix(
    conn,
    permit_type: str,
    neighborhood: str | None = None,
) -> dict[str, dict[str, int]]:
    """Build station transition count matrix from historical similar permits.

    Algorithm:
    1. Find similar permits (same type, optionally same neighborhood)
    2. For each permit, get ordered station sequence from addenda
    3. For each consecutive pair (A → B), increment transitions[A][B]
    4. Exclude "Not Applicable" / "Administrative" pass-throughs
    5. Deduplicate consecutive identical stations

    Returns: {from_station: {to_station: count}}
    """
    ph = _ph()
    cutoff = (date.today() - timedelta(days=TRANSITION_LOOKBACK_DAYS)).isoformat()

    # Step 1: Find similar permits
    if neighborhood:
        if BACKEND == "postgres":
            permits_sql = """
                SELECT permit_number FROM permits
                WHERE permit_type_definition = %s
                  AND neighborhood = %s
                  AND filed_date >= %s
                LIMIT 5000
            """
            permits_params: list = [permit_type, neighborhood, cutoff]
        else:
            permits_sql = """
                SELECT permit_number FROM permits
                WHERE permit_type_definition = ?
                  AND neighborhood = ?
                  AND filed_date::DATE >= ?
                LIMIT 5000
            """
            permits_params = [permit_type, neighborhood, cutoff]
    else:
        if BACKEND == "postgres":
            permits_sql = """
                SELECT permit_number FROM permits
                WHERE permit_type_definition = %s
                  AND filed_date >= %s
                LIMIT 5000
            """
            permits_params = [permit_type, cutoff]
        else:
            permits_sql = """
                SELECT permit_number FROM permits
                WHERE permit_type_definition = ?
                  AND filed_date::DATE >= ?
                LIMIT 5000
            """
            permits_params = [permit_type, cutoff]

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(permits_sql, permits_params)
                permit_rows = cur.fetchall()
        else:
            permit_rows = conn.execute(permits_sql, permits_params).fetchall()
    except Exception:
        logger.warning("_build_transition_matrix: permits query failed", exc_info=True)
        return {}

    if not permit_rows:
        return {}

    permit_numbers = [r[0] for r in permit_rows]

    # Step 2: Get ordered station sequences for all similar permits
    if BACKEND == "postgres":
        addenda_sql = """
            WITH ranked AS (
                SELECT application_number, station, arrive,
                       ROW_NUMBER() OVER (
                           PARTITION BY application_number, station, addenda_number
                           ORDER BY finish_date DESC NULLS LAST
                       ) AS rn
                FROM addenda
                WHERE application_number = ANY(%s)
                  AND station IS NOT NULL
                  AND arrive IS NOT NULL
                  AND (review_results IS NULL
                       OR review_results NOT IN ('Not Applicable', 'Administrative'))
            )
            SELECT application_number, station, arrive
            FROM ranked
            WHERE rn = 1
            ORDER BY application_number, arrive ASC
        """
        addenda_params: list = [permit_numbers]
    else:
        placeholders = ", ".join(["?"] * len(permit_numbers))
        addenda_sql = f"""
            WITH ranked AS (
                SELECT application_number, station, arrive,
                       ROW_NUMBER() OVER (
                           PARTITION BY application_number, station, addenda_number
                           ORDER BY finish_date DESC NULLS LAST
                       ) AS rn
                FROM addenda
                WHERE application_number IN ({placeholders})
                  AND station IS NOT NULL
                  AND arrive IS NOT NULL
                  AND (review_results IS NULL
                       OR review_results NOT IN ('Not Applicable', 'Administrative'))
            )
            SELECT application_number, station, arrive
            FROM ranked
            WHERE rn = 1
            ORDER BY application_number, arrive ASC
        """
        addenda_params = permit_numbers

    try:
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(addenda_sql, addenda_params)
                addenda_rows = cur.fetchall()
        else:
            addenda_rows = conn.execute(addenda_sql, addenda_params).fetchall()
    except Exception:
        logger.warning("_build_transition_matrix: addenda query failed", exc_info=True)
        return {}

    # Step 3: Build sequences per permit
    sequences: dict[str, list[str]] = {}
    for row in addenda_rows:
        app_num, station = row[0], row[1]
        if app_num not in sequences:
            sequences[app_num] = []
        sequences[app_num].append(station)

    # Step 4: Count transitions
    transitions: dict[str, dict[str, int]] = {}
    for seq in sequences.values():
        # Deduplicate consecutive identical stations
        deduped: list[str] = []
        for s in seq:
            if not deduped or deduped[-1] != s:
                deduped.append(s)

        for i in range(len(deduped) - 1):
            from_s = deduped[i]
            to_s = deduped[i + 1]
            if from_s not in transitions:
                transitions[from_s] = {}
            transitions[from_s][to_s] = transitions[from_s].get(to_s, 0) + 1

    return transitions


def _lookup_station_velocity(conn, station: str) -> dict | None:
    """Look up station velocity from station_velocity_v2 table.

    Prefers 'current' (rolling 90d) period, falls back to 'baseline' then 'all'.
    Returns None if station not found or table doesn't exist.
    """
    ph = _ph()
    for period in ("current", "baseline", "all"):
        sql = f"""
            SELECT p25_days, p50_days, p75_days, p90_days, sample_count, period
            FROM station_velocity_v2
            WHERE station = {ph}
              AND metric_type = 'initial'
              AND period = {ph}
            LIMIT 1
        """
        try:
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(sql, [station, period])
                    row = cur.fetchone()
            else:
                row = conn.execute(sql, [station, period]).fetchone()
        except Exception:
            return None  # Table doesn't exist

        if row:
            return {
                "p25_days": float(row[0]) if row[0] is not None else None,
                "p50_days": float(row[1]) if row[1] is not None else None,
                "p75_days": float(row[2]) if row[2] is not None else None,
                "p90_days": float(row[3]) if row[3] is not None else None,
                "sample_count": row[4],
                "period": row[5],
            }
    return None


def _compute_top_predictions(
    current_station: str,
    transitions: dict[str, dict[str, int]],
    conn,
    top_n: int = 3,
) -> list[dict]:
    """Compute top-N predicted next stations with probabilities and velocity data.

    Filters edges with fewer than MIN_TRANSITION_SAMPLES transitions.
    Probabilities are computed as count / total_outbound_count.

    Returns sorted list of prediction dicts.
    """
    outbound = transitions.get(current_station, {})
    # Filter to meaningful transitions
    outbound = {k: v for k, v in outbound.items() if v >= MIN_TRANSITION_SAMPLES}
    if not outbound:
        return []

    total = sum(outbound.values())
    predictions = []

    for station, count in sorted(outbound.items(), key=lambda x: -x[1]):
        prob = count / total
        velocity = _lookup_station_velocity(conn, station)
        predictions.append({
            "station": station,
            "label": _label(station),
            "probability": prob,
            "sample_count": count,
            "total_outbound": total,
            "p25_days": velocity["p25_days"] if velocity else None,
            "p50_days": velocity["p50_days"] if velocity else None,
            "p75_days": velocity["p75_days"] if velocity else None,
            "p90_days": velocity["p90_days"] if velocity else None,
            "velocity_period": velocity["period"] if velocity else None,
        })

    return predictions[:top_n]


# ── Formatting ──────────────────────────────────────────────────────


def _format_output(
    permit_number: str,
    permit_info: dict | None,
    history: list[dict],
    current: dict | None,
    predictions: list[dict],
    transitions: dict[str, dict[str, int]],
    neighborhood_filtered: bool,
) -> str:
    """Render the prediction result as a markdown string."""
    lines: list[str] = []

    lines.append(f"# What's Next: Permit {permit_number}")
    lines.append("")

    if permit_info:
        ptype = permit_info.get("permit_type", "Unknown")
        nhood = permit_info.get("neighborhood") or "—"
        status = permit_info.get("status") or "—"
        lines.append(
            f"**Type:** {ptype}  |  **Neighborhood:** {nhood}  |  **Status:** {status}"
        )
        lines.append("")

    # No addenda data
    if not history:
        lines.append("No routing data available for this permit.")
        lines.append("")
        lines.append(
            "*This permit may not have entered plan review yet, "
            "or addenda records are not available.*"
        )
        return "\n".join(lines)

    # Station visit summary
    finished = [h for h in history if h["finish_date"]]
    distinct = len(set(h["station"] for h in history))
    lines.append(f"**Stations visited:** {len(finished)} completed, {distinct} total")
    lines.append("")

    # Current station status
    lines.append("## Current Station")
    lines.append("")

    if current is None:
        all_done = all(h["finish_date"] for h in history)
        if all_done:
            lines.append(
                "All tracked review stations have finished. "
                "The permit may be awaiting issuance or final approval."
            )
            last_finish = max(
                (h["finish_date"] for h in history if h["finish_date"]), default=None
            )
            if last_finish:
                lines.append(f"**Last activity:** {last_finish[:10]}")
        else:
            lines.append("No active station found. Routing may be between stations.")
        lines.append("")
    else:
        station_code = current["station"]
        dwell = _compute_dwell_days(current)
        is_stalled = dwell is not None and dwell > STALL_THRESHOLD_DAYS

        stall_tag = " — STALLED" if is_stalled else ""
        lines.append(f"**{_label(station_code)}** (`{station_code}`){stall_tag}")

        if current.get("arrive"):
            lines.append(f"- Arrived: {current['arrive'][:10]}")
        if dwell is not None:
            lines.append(f"- Days at this station: **{dwell} days**")
            if is_stalled:
                lines.append(
                    f"  - *Over {STALL_THRESHOLD_DAYS} days with no finish recorded — "
                    f"consider following up with DBI.*"
                )
        lines.append("")

    # Predictions
    lines.append("## Predicted Next Stations")
    lines.append("")

    if not predictions:
        if current:
            sc = current["station"]
            if sc not in transitions:
                lines.append(f"No historical transition data found for station `{sc}`.")
            else:
                lines.append(
                    f"No transitions from `{sc}` met the minimum sample threshold "
                    f"({MIN_TRANSITION_SAMPLES} permits)."
                )
        else:
            lines.append("Cannot predict next stations — no active station found.")
        lines.append("")
        lines.append(
            "*Prediction requires an active routing record and sufficient historical data.*"
        )
        return "\n".join(lines)

    scope_label = (
        f"permits in {permit_info.get('neighborhood')}" if neighborhood_filtered and permit_info
        else "all similar permit types"
    )
    lines.append(f"*Based on historical routing patterns from {scope_label}*")
    lines.append("")
    lines.append("| Station | Probability | Typical (p50) | Range (p25–p75) |")
    lines.append("|---------|-------------|--------------|-----------------|")

    for pred in predictions:
        prob_pct = f"{pred['probability'] * 100:.0f}%"
        duration = _format_days(pred["p50_days"])
        p25 = _format_days(pred["p25_days"])
        p75 = _format_days(pred["p75_days"])
        range_str = (
            f"{p25}–{p75}"
            if pred["p25_days"] is not None and pred["p75_days"] is not None
            else "—"
        )
        label_col = f"{pred['label']} (`{pred['station']}`)"
        lines.append(f"| {label_col} | {prob_pct} | {duration} | {range_str} |")

    lines.append("")

    # All-clear estimate
    lines.append("## All-Clear Estimate")
    lines.append("")

    total_p50 = sum(p["p50_days"] for p in predictions if p["p50_days"] is not None)
    if total_p50 > 0:
        lines.append(f"**Estimated remaining time:** {_format_days(total_p50)}")
        lines.append("")
        lines.append(
            "*Sequential sum of p50 (median) durations for predicted stations. "
            "Actual time depends on submission completeness and reviewer workload.*"
        )
    else:
        lines.append(
            "*Velocity data not available — cannot estimate remaining time.*"
        )

    lines.append("")

    # Confidence
    n_samples = max((p["total_outbound"] for p in predictions), default=0)
    confidence = "High" if n_samples >= 100 else ("Medium" if n_samples >= 30 else "Low")
    lines.append(
        f"**Prediction confidence:** {confidence} "
        f"({n_samples:,} similar permits in transition data)"
    )

    return "\n".join(lines)


# ── Public async tool ───────────────────────────────────────────────


async def predict_next_stations(permit_number: str) -> str:
    """Predict the next review stations for an active SF permit.

    Uses the permit's current station (from addenda routing records) combined with
    a Markov-style transition probability matrix built from similar permit types
    to predict the most likely next 3 stations. Each predicted station is enriched
    with velocity estimates (p50/p75 days) from station_velocity_v2.

    Args:
        permit_number: SF permit application number (e.g. "202201234567").

    Returns:
        Markdown string with:
        - Current station name, arrival date, and dwell time (stall warning if >60d)
        - Top 3 predicted next stations with probability and estimated duration
        - Total estimated remaining time (sum of p50s)
        - Prediction confidence indicator

    Edge cases:
        - Permit not found → error message with correction guidance
        - No addenda data → "No routing data available"
        - All stations finished → "This permit has completed all review stations"
        - No transition data → explains why prediction isn't possible
    """
    conn = None
    try:
        conn = get_connection()
        # 1. Permit info
        permit_info = _get_permit_info(conn, permit_number)
        if not permit_info:
            return (
                f"# Permit Not Found\n\n"
                f"No permit found with number `{permit_number}`.\n\n"
                "Verify the permit number and try again. "
                "SF permit numbers typically look like `202201234567`."
            )

        # 2. Already-complete short-circuit
        status = (permit_info.get("status") or "").lower()
        if status in COMPLETE_STATUSES:
            lines = [
                f"# What's Next: Permit {permit_number}",
                "",
                f"**Type:** {permit_info.get('permit_type', 'Unknown')}  |  "
                f"**Neighborhood:** {permit_info.get('neighborhood') or '—'}  |  "
                f"**Status:** {permit_info.get('status', '—')}",
                "",
                "This permit has completed all review stations.",
            ]
            if permit_info.get("issued_date"):
                lines.append(f"**Issued:** {permit_info['issued_date']}")
            if permit_info.get("completed_date"):
                lines.append(f"**Completed:** {permit_info['completed_date']}")
            return "\n".join(lines)

        # 3. Station history for this permit
        history = _get_station_history(conn, permit_number)
        if not history:
            return (
                f"# What's Next: Permit {permit_number}\n\n"
                f"**Type:** {permit_info.get('permit_type', 'Unknown')}\n\n"
                "No routing data available for this permit.\n\n"
                "*This permit may not have entered plan review yet, "
                "or addenda records are not available in the database.*"
            )

        # 4. Find current station
        current = _find_current_station(history)

        # 5. Build transition matrix — try neighborhood first, fall back to type-only
        permit_type = permit_info.get("permit_type", "")
        neighborhood = permit_info.get("neighborhood")
        transitions: dict[str, dict[str, int]] = {}
        neighborhood_filtered = False

        if neighborhood:
            transitions = _build_transition_matrix(conn, permit_type, neighborhood)
            if transitions:
                neighborhood_filtered = True

        if not transitions:
            transitions = _build_transition_matrix(conn, permit_type, None)

        # 6. Compute top predictions from current station
        predictions: list[dict] = []
        if current:
            predictions = _compute_top_predictions(current["station"], transitions, conn)

        # 7. Render output
        return _format_output(
            permit_number=permit_number,
            permit_info=permit_info,
            history=history,
            current=current,
            predictions=predictions,
            transitions=transitions,
            neighborhood_filtered=neighborhood_filtered,
        )

    except Exception:
        logger.error(
            "predict_next_stations: unexpected error for %s", permit_number, exc_info=True
        )
        return (
            f"# Error\n\n"
            f"An unexpected error occurred while predicting next stations for "
            f"permit `{permit_number}`. Please try again or check the server logs."
        )
    finally:
        if conn is not None:
            conn.close()
