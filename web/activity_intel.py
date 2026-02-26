"""Activity Intelligence — analytics queries for admin ops.

Analyzes activity_log data to surface user behavior patterns:
bounce rates, feature funnels, query refinement, feedback correlation,
and time-to-first-action metrics.
"""
from __future__ import annotations
import logging
from src.db import BACKEND, query

logger = logging.getLogger(__name__)


def _interval(n: int, unit: str) -> str:
    """Return a SQL INTERVAL literal for the current backend.

    unit must be 'hours', 'days', or 'minutes'.
    """
    if BACKEND == "postgres":
        return f"INTERVAL '{n} {unit}'"
    # DuckDB: INTERVAL N HOUR / DAY / MINUTE
    unit_map = {"hours": "HOUR", "days": "DAY", "minutes": "MINUTE"}
    return f"INTERVAL {n} {unit_map.get(unit, unit.upper())}"


def get_bounce_rate(hours: int = 168) -> dict:
    """Searches with no follow-up action within 60 seconds.

    A 'bounce' = a search/public_search action where the same user/ip_hash
    has no subsequent action within 60 seconds.

    Returns: {total_searches, bounced, bounce_rate, hours}
    """
    try:
        time_filter = f"created_at > CURRENT_TIMESTAMP - {_interval(hours, 'hours')}"
        if BACKEND == "postgres":
            sql = f"""
                SELECT
                    COUNT(*) AS total_searches,
                    SUM(CASE WHEN follow_up = 0 THEN 1 ELSE 0 END) AS bounced
                FROM (
                    SELECT
                        s.log_id,
                        COALESCE(
                            (SELECT COUNT(*)
                             FROM activity_log f
                             WHERE (
                                 (s.user_id IS NOT NULL AND f.user_id = s.user_id)
                                 OR (s.user_id IS NULL AND s.ip_hash IS NOT NULL AND f.ip_hash = s.ip_hash)
                             )
                             AND f.log_id != s.log_id
                             AND f.created_at > s.created_at
                             AND f.created_at <= s.created_at + INTERVAL '60 seconds'
                            ), 0
                        ) AS follow_up
                    FROM activity_log s
                    WHERE s.action IN ('search', 'public_search')
                    AND s.{time_filter}
                ) sub
            """
        else:
            sql = f"""
                SELECT
                    COUNT(*) AS total_searches,
                    SUM(CASE WHEN follow_up = 0 THEN 1 ELSE 0 END) AS bounced
                FROM (
                    SELECT
                        s.log_id,
                        COALESCE(
                            (SELECT COUNT(*)
                             FROM activity_log f
                             WHERE (
                                 (s.user_id IS NOT NULL AND f.user_id = s.user_id)
                                 OR (s.user_id IS NULL AND s.ip_hash IS NOT NULL AND f.ip_hash = s.ip_hash)
                             )
                             AND f.log_id != s.log_id
                             AND f.created_at > s.created_at
                             AND f.created_at <= s.created_at + INTERVAL 60 SECOND
                            ), 0
                        ) AS follow_up
                    FROM activity_log s
                    WHERE s.action IN ('search', 'public_search')
                    AND s.{time_filter}
                ) sub
            """
        rows = query(sql)
        if rows:
            total = int(rows[0][0] or 0)
            bounced = int(rows[0][1] or 0)
        else:
            total, bounced = 0, 0
        rate = round(bounced / total * 100, 1) if total > 0 else 0.0
        return {
            "total_searches": total,
            "bounced": bounced,
            "bounce_rate": rate,
            "hours": hours,
        }
    except Exception:
        logger.debug("get_bounce_rate failed", exc_info=True)
        return {"total_searches": 0, "bounced": 0, "bounce_rate": 0.0, "hours": hours}


def get_feature_funnel(days: int = 7) -> dict:
    """Search to detail to analyze to ask conversion funnel.

    Counts unique users/ip_hashes at each stage:
    - search: 'search' or 'public_search' actions
    - detail: 'lookup' action
    - analyze: 'analyze' or 'analyze_plans' action
    - ask: any action with path '/ask'

    Returns: {stages: [{name, count, pct_of_search}], days}
    """
    try:
        time_filter = f"created_at > CURRENT_TIMESTAMP - {_interval(days, 'days')}"

        def _uid_expr(action_filter: str) -> str:
            return (
                f"SELECT COUNT(DISTINCT COALESCE(CAST(user_id AS TEXT), ip_hash)) "
                f"FROM activity_log WHERE {action_filter} AND {time_filter}"
            )

        search_sql = _uid_expr("action IN ('search', 'public_search')")
        detail_sql = _uid_expr("action = 'lookup'")
        analyze_sql = _uid_expr("action IN ('analyze', 'analyze_plans')")
        ask_sql = _uid_expr("path = '/ask' OR path LIKE '/ask%'")

        search_count = int((query(search_sql) or [[0]])[0][0] or 0)
        detail_count = int((query(detail_sql) or [[0]])[0][0] or 0)
        analyze_count = int((query(analyze_sql) or [[0]])[0][0] or 0)
        ask_count = int((query(ask_sql) or [[0]])[0][0] or 0)

        def _pct(n: int) -> float:
            return round(n / search_count * 100, 1) if search_count > 0 else 0.0

        stages = [
            {"name": "Search", "count": search_count, "pct_of_search": 100.0 if search_count > 0 else 0.0},
            {"name": "Detail", "count": detail_count, "pct_of_search": _pct(detail_count)},
            {"name": "Analyze", "count": analyze_count, "pct_of_search": _pct(analyze_count)},
            {"name": "Ask", "count": ask_count, "pct_of_search": _pct(ask_count)},
        ]
        return {"stages": stages, "days": days}
    except Exception:
        logger.debug("get_feature_funnel failed", exc_info=True)
        empty_stages = [
            {"name": n, "count": 0, "pct_of_search": 0.0}
            for n in ("Search", "Detail", "Analyze", "Ask")
        ]
        return {"stages": empty_stages, "days": days}


def get_query_refinements(hours: int = 168) -> dict:
    """Same user refining search 2+ times within 5 minutes.

    Looks for consecutive search actions by the same user_id or ip_hash
    within 5 minutes. Groups by the query text in detail->query.

    Returns: {refinement_sessions, avg_refinements_per_session,
              top_refined_queries: [{query, count}], hours}
    """
    try:
        time_filter = f"a.created_at > CURRENT_TIMESTAMP - {_interval(hours, 'hours')}"

        if BACKEND == "postgres":
            # Use JSON operator for Postgres
            sql = f"""
                SELECT
                    COALESCE(CAST(a.user_id AS TEXT), a.ip_hash) AS uid,
                    a.detail::json->>'query' AS qtext,
                    COUNT(*) AS cnt
                FROM activity_log a
                WHERE a.action IN ('search', 'public_search')
                AND {time_filter}
                AND (a.user_id IS NOT NULL OR a.ip_hash IS NOT NULL)
                GROUP BY uid, qtext
                HAVING COUNT(*) >= 2
                ORDER BY cnt DESC
                LIMIT 20
            """
        else:
            # DuckDB: json_extract_string
            sql = f"""
                SELECT
                    COALESCE(CAST(a.user_id AS VARCHAR), a.ip_hash) AS uid,
                    json_extract_string(a.detail, '$.query') AS qtext,
                    COUNT(*) AS cnt
                FROM activity_log a
                WHERE a.action IN ('search', 'public_search')
                AND {time_filter}
                AND (a.user_id IS NOT NULL OR a.ip_hash IS NOT NULL)
                GROUP BY uid, qtext
                HAVING COUNT(*) >= 2
                ORDER BY cnt DESC
                LIMIT 20
            """
        rows = query(sql)

        refinement_sessions = len(rows)
        avg_refinements = (
            round(sum(r[2] for r in rows) / refinement_sessions, 1)
            if refinement_sessions > 0
            else 0.0
        )
        # Aggregate by query text
        query_counts: dict[str, int] = {}
        for row in rows:
            qtext = row[1] or "(no query)"
            query_counts[qtext] = query_counts.get(qtext, 0) + int(row[2])
        top_refined = sorted(
            [{"query": q, "count": c} for q, c in query_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:10]

        return {
            "refinement_sessions": refinement_sessions,
            "avg_refinements_per_session": avg_refinements,
            "top_refined_queries": top_refined,
            "hours": hours,
        }
    except Exception:
        logger.debug("get_query_refinements failed", exc_info=True)
        return {
            "refinement_sessions": 0,
            "avg_refinements_per_session": 0.0,
            "top_refined_queries": [],
            "hours": hours,
        }


def get_feedback_by_page(days: int = 30) -> dict:
    """Feedback-to-visit ratio per path.

    Joins feedback table (has page_url) with activity_log visit counts.

    Returns: {pages: [{path, visits, feedback_count, ratio}], days}
    """
    try:
        time_filter_act = f"al.created_at > CURRENT_TIMESTAMP - {_interval(days, 'days')}"
        time_filter_fb = f"fb.created_at > CURRENT_TIMESTAMP - {_interval(days, 'days')}"

        # Get visit counts per path from activity_log
        visit_sql = f"""
            SELECT al.path, COUNT(*) AS visits
            FROM activity_log al
            WHERE {time_filter_act}
            AND al.path IS NOT NULL
            GROUP BY al.path
            ORDER BY visits DESC
            LIMIT 50
        """
        visit_rows = query(visit_sql)
        visit_map = {r[0]: int(r[1]) for r in visit_rows}

        # Get feedback counts per page_url
        fb_sql = f"""
            SELECT fb.page_url, COUNT(*) AS fb_count
            FROM feedback fb
            WHERE {time_filter_fb}
            AND fb.page_url IS NOT NULL
            GROUP BY fb.page_url
        """
        fb_rows = query(fb_sql)
        fb_map: dict[str, int] = {}
        for r in fb_rows:
            # Normalize URL to path: strip scheme+host
            url = str(r[0])
            # e.g. "https://host/path?q=x" -> "/path"
            if "://" in url:
                url = "/" + url.split("/", 3)[-1].split("?")[0]
            fb_map[url] = fb_map.get(url, 0) + int(r[1])

        # Combine: start with paths that have feedback
        all_paths = set(visit_map.keys()) | set(fb_map.keys())
        pages = []
        for path in all_paths:
            visits = visit_map.get(path, 0)
            fb_count = fb_map.get(path, 0)
            ratio = round(fb_count / visits * 100, 2) if visits > 0 else 0.0
            if fb_count > 0 or visits > 0:
                pages.append({
                    "path": path,
                    "visits": visits,
                    "feedback_count": fb_count,
                    "ratio": ratio,
                })
        pages.sort(key=lambda x: x["feedback_count"], reverse=True)

        return {"pages": pages[:20], "days": days}
    except Exception:
        logger.debug("get_feedback_by_page failed", exc_info=True)
        return {"pages": [], "days": days}


def get_time_to_first_action(days: int = 7) -> dict:
    """Average seconds from first page view to first meaningful action.

    For each unique user/ip_hash, find their first activity_log entry
    and their first 'search' or 'analyze' action. Compute the gap.

    Returns: {avg_seconds, median_seconds, sample_size, days}
    """
    try:
        time_filter = f"created_at > CURRENT_TIMESTAMP - {_interval(days, 'days')}"

        if BACKEND == "postgres":
            sql = f"""
                WITH sessions AS (
                    SELECT
                        COALESCE(CAST(user_id AS TEXT), ip_hash) AS uid,
                        MIN(created_at) AS first_seen,
                        MIN(CASE WHEN action IN ('search', 'analyze', 'analyze_plans')
                            THEN created_at END) AS first_action
                    FROM activity_log
                    WHERE {time_filter}
                    AND (user_id IS NOT NULL OR ip_hash IS NOT NULL)
                    GROUP BY uid
                )
                SELECT
                    AVG(EXTRACT(EPOCH FROM (first_action - first_seen))) AS avg_sec,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY
                        EXTRACT(EPOCH FROM (first_action - first_seen))) AS median_sec,
                    COUNT(*) AS sample_size
                FROM sessions
                WHERE first_action IS NOT NULL
                AND first_action > first_seen
            """
        else:
            sql = f"""
                WITH sessions AS (
                    SELECT
                        COALESCE(CAST(user_id AS VARCHAR), ip_hash) AS uid,
                        MIN(created_at) AS first_seen,
                        MIN(CASE WHEN action IN ('search', 'analyze', 'analyze_plans')
                            THEN created_at END) AS first_action
                    FROM activity_log
                    WHERE {time_filter}
                    AND (user_id IS NOT NULL OR ip_hash IS NOT NULL)
                    GROUP BY uid
                )
                SELECT
                    AVG(epoch(first_action) - epoch(first_seen)) AS avg_sec,
                    MEDIAN(epoch(first_action) - epoch(first_seen)) AS median_sec,
                    COUNT(*) AS sample_size
                FROM sessions
                WHERE first_action IS NOT NULL
                AND first_action > first_seen
            """
        rows = query(sql)
        if rows and rows[0][0] is not None:
            avg_sec = round(float(rows[0][0]), 1)
            median_sec = round(float(rows[0][1]), 1) if rows[0][1] is not None else 0.0
            sample_size = int(rows[0][2] or 0)
        else:
            avg_sec, median_sec, sample_size = 0.0, 0.0, 0

        return {
            "avg_seconds": avg_sec,
            "median_seconds": median_sec,
            "sample_size": sample_size,
            "days": days,
        }
    except Exception:
        logger.debug("get_time_to_first_action failed", exc_info=True)
        return {
            "avg_seconds": 0.0,
            "median_seconds": 0.0,
            "sample_size": 0,
            "days": days,
        }
