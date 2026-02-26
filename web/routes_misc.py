"""Miscellaneous routes: brief, dashboard, beta-request, SEO pages.

Blueprint: misc (no url_prefix)
"""

import logging
from datetime import datetime

from flask import (
    Blueprint, render_template, request, g, Response, jsonify,
)

from web.helpers import login_required

bp = Blueprint("misc", __name__)


# ---------------------------------------------------------------------------
# Morning Brief
# ---------------------------------------------------------------------------

@bp.route("/brief")
@login_required
def brief():
    """Morning brief dashboard — what changed, permit health, inspections."""
    from web.brief import get_morning_brief
    from web.auth import get_primary_address
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1
    primary_addr = get_primary_address(g.user["user_id"])
    brief_data = get_morning_brief(g.user["user_id"], lookback_days,
                                   primary_address=primary_addr)
    return render_template("brief.html", user=g.user, brief=brief_data,
                           active_page="brief")


# ---------------------------------------------------------------------------
# Velocity / Bottleneck Dashboard
# ---------------------------------------------------------------------------

@bp.route("/dashboard/bottlenecks")
@login_required
def velocity_dashboard():
    """DBI approval pipeline bottleneck heatmap."""
    from web.velocity_dashboard import get_dashboard_data
    user_id = g.user["user_id"] if g.user else None
    data = get_dashboard_data(user_id=user_id)
    try:
        from web.station_velocity import get_station_congestion
        data["congestion"] = get_station_congestion()
    except Exception:
        data["congestion"] = {}
    return render_template(
        "velocity_dashboard.html",
        data=data,
        active_page="bottlenecks",
    )


@bp.route("/dashboard/bottlenecks/station/<path:station>")
@login_required
def velocity_station_detail(station: str):
    """JSON endpoint: reviewer stats for a single station (heatmap drill-down)."""
    from web.velocity_dashboard import get_reviewer_stats
    station = station.upper().strip()
    reviewers = get_reviewer_stats(station)
    return jsonify({"station": station, "reviewers": reviewers})


# ---------------------------------------------------------------------------
# Beta request (organic signup)
# ---------------------------------------------------------------------------

@bp.route("/beta-request", methods=["GET", "POST"])
def beta_request():
    """Organic signup — 'Request beta access' form.

    GET: Show the form (with optional prefill_email from query string).
    POST: Accept submission, validate honeypot, apply rate limit, create beta request.
    """
    from web.auth import (
        is_beta_rate_limited, record_beta_request_ip,
        create_beta_request as _create_req,
        send_beta_confirmation_email,
    )

    if request.method == "GET":
        prefill_email = request.args.get("email", "").strip()
        return render_template("beta_request.html", prefill_email=prefill_email)

    # POST — process submission
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()

    # Rate limiting
    if is_beta_rate_limited(ip):
        return render_template(
            "beta_request.html",
            message="Too many requests from your IP. Please try again later.",
            message_type="error",
        ), 429

    # Honeypot check
    honeypot = request.form.get("website", "").strip()
    if honeypot:
        # Bot — silently succeed (don't reveal the check)
        logging.warning("beta_request honeypot triggered from IP %s", ip)
        return render_template(
            "beta_request.html",
            submitted=True,
            message="Thank you! We'll be in touch soon.",
        )

    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip() or None
    reason = request.form.get("reason", "").strip() or None

    if not email or "@" not in email:
        return render_template(
            "beta_request.html",
            message="Please enter a valid email address.",
            message_type="error",
        ), 400

    if not reason:
        return render_template(
            "beta_request.html",
            message="Please tell us what brings you to sfpermits.ai.",
            message_type="error",
        ), 400

    record_beta_request_ip(ip)

    try:
        result = _create_req(email=email, name=name, reason=reason, ip=ip)
        send_beta_confirmation_email(email)
    except Exception as e:
        logging.exception("beta_request creation failed")
        return render_template(
            "beta_request.html",
            message="Something went wrong. Please try again.",
            message_type="error",
        ), 500

    return render_template(
        "beta_request.html",
        submitted=True,
        message="Thank you! We'll review your request and send you a sign-in link if approved.",
    )


# ---------------------------------------------------------------------------
# SEO pages: ADU landing, sitemap
# ---------------------------------------------------------------------------

_adu_stats_cache: dict = {}


def _get_adu_stats() -> dict:
    """Return cached ADU permit stats. Queries DB once and caches for 24h."""
    import time as _time

    now = _time.time()
    if _adu_stats_cache and _adu_stats_cache.get("computed_at", 0) > now - 86400:
        return _adu_stats_cache

    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        try:
            # Count ADU permits issued in 2024/2025 using description keyword search
            if BACKEND == "postgres":
                like_op = "ILIKE"
            else:
                like_op = "LIKE"

            # Count ADUs (case-insensitive keyword match on description)
            row_2025 = conn.execute(
                f"SELECT COUNT(*) FROM permits WHERE status = 'issued' "
                f"AND issued_date >= '2025-01-01' "
                f"AND (LOWER(description) LIKE '%accessory dwelling%' "
                f"  OR LOWER(description) LIKE '% adu %' "
                f"  OR LOWER(description) LIKE '%adu:'  "
                f"  OR LOWER(description) LIKE 'adu %' "
                f"  OR LOWER(description) LIKE '%jr. adu%' "
                f"  OR LOWER(description) LIKE '%jadu%')"
            ).fetchone()

            count_2025 = row_2025[0] if row_2025 else 0

            # Median days to issuance for ADU permits (all time for better stats)
            med_row = conn.execute(
                "SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY "
                "DATEDIFF('day', filed_date::DATE, issued_date::DATE)) "
                "FROM permits WHERE status = 'issued' "
                "AND issued_date IS NOT NULL AND filed_date IS NOT NULL "
                "AND (LOWER(description) LIKE '%accessory dwelling%' "
                "  OR LOWER(description) LIKE '% adu %' "
                "  OR LOWER(description) LIKE '%jadu%')"
            ).fetchone()

            median_days = int(med_row[0]) if med_row and med_row[0] else None
        except Exception:
            # DuckDB may not support PERCENTILE_CONT — try simpler query
            try:
                row_2025 = conn.execute(
                    "SELECT COUNT(*) FROM permits WHERE status = 'issued' "
                    "AND issued_date >= '2025-01-01' "
                    "AND (lower(description) LIKE '%accessory dwelling%' "
                    "  OR lower(description) LIKE '% adu %' "
                    "  OR lower(description) LIKE '%jadu%')"
                ).fetchone()
                count_2025 = row_2025[0] if row_2025 else 0
                median_days = None
            except Exception:
                count_2025 = 0
                median_days = None
        finally:
            conn.close()
    except Exception:
        count_2025 = 0
        median_days = None

    import time as _time
    _adu_stats_cache.clear()
    _adu_stats_cache.update({
        "issued_2025": count_2025,
        "median_days": median_days,
        "computed_at": _time.time(),
    })
    return _adu_stats_cache


@bp.route("/sitemap.xml")
def sitemap():
    """Static sitemap — crawl-budget-safe, no dynamic permit URLs."""
    static_pages = [
        "/",
        "/search",
        "/adu",
        "/beta-request",
        "/analyze-preview",
        "/methodology",
        "/about-data",
    ]
    base = "https://sfpermits.ai"
    now = datetime.now().strftime("%Y-%m-%d")

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path in static_pages:
        lines.append("  <url>")
        lines.append(f"    <loc>{base}{path}</loc>")
        lines.append(f"    <lastmod>{now}</lastmod>")
        lines.append("    <changefreq>weekly</changefreq>")
        lines.append("  </url>")
    lines.append("</urlset>")

    xml = "\n".join(lines)
    return Response(xml, mimetype="application/xml")


@bp.route("/adu")
def adu_landing():
    """ADU landing page with pre-computed stats (24h cache)."""
    stats = _get_adu_stats()
    return render_template("adu_landing.html", stats=stats)


# ---------------------------------------------------------------------------
# Content pages: methodology, about-data, demo
# ---------------------------------------------------------------------------

@bp.route("/methodology")
def methodology():
    """Deep-dive page showing how sfpermits.ai calculates everything."""
    return render_template("methodology.html")


@bp.route("/about-data")
def about_data():
    """Full data inventory — datasets, pipeline, knowledge base, QA."""
    return render_template("about_data.html")


# Demo address config: a known-rich parcel with permits, routing, violations
_DEMO_ADDRESS = {"street_number": "1455", "street_name": "MARKET", "block": "3507", "lot": "004"}
_demo_cache: dict = {}


def _get_demo_data() -> dict:
    """Pre-query all intelligence layers for the demo address. Cached 1 hour."""
    import time as _time

    now = _time.time()
    if _demo_cache and _demo_cache.get("computed_at", 0) > now - 3600:
        return _demo_cache

    addr = _DEMO_ADDRESS
    data: dict = {
        "demo_address": f"{addr['street_number']} {addr['street_name']} ST",
        "block": addr["block"],
        "lot": addr["lot"],
        "neighborhood": "South of Market",
        "permits": [],
        "routing": [],
        "timeline": None,
        "entities": [],
        "complaints": [],
        "violations": [],
    }

    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        ph = "%s" if BACKEND == "postgres" else "?"
        try:
            # Permits
            rows = conn.execute(
                f"SELECT permit_number, permit_type_definition, status, "
                f"filed_date, estimated_cost, description "
                f"FROM permits WHERE block = {ph} AND lot = {ph} "
                f"ORDER BY filed_date DESC NULLS LAST LIMIT 20",
                (addr["block"], addr["lot"]),
            ).fetchall() if BACKEND == "duckdb" else []

            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT permit_number, permit_type_definition, status, "
                        "filed_date, estimated_cost, description "
                        "FROM permits WHERE block = %s AND lot = %s "
                        "ORDER BY filed_date DESC NULLS LAST LIMIT 20",
                        (addr["block"], addr["lot"]),
                    )
                    rows = cur.fetchall()

            for r in rows:
                cost = r[4]
                cost_display = f"${cost:,.0f}" if cost and cost > 0 else "N/A"
                desc = (r[5] or "")[:80]
                filed = str(r[3])[:10] if r[3] else "N/A"
                data["permits"].append({
                    "permit_number": r[0],
                    "permit_type": (r[1] or "")[:30],
                    "status": (r[2] or "unknown").lower(),
                    "filed_date": filed,
                    "cost_display": cost_display,
                    "description_short": desc,
                })

            # Complaints
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT complaint_number, status, description "
                            "FROM complaints WHERE block = %s AND lot = %s "
                            "ORDER BY date_filed DESC NULLS LAST LIMIT 5",
                            (addr["block"], addr["lot"]),
                        )
                        for r in cur.fetchall():
                            data["complaints"].append({
                                "description_short": (r[2] or "")[:80],
                                "status": r[1] or "unknown",
                            })
                else:
                    for r in conn.execute(
                        "SELECT complaint_number, status, description "
                        "FROM complaints WHERE block = ? AND lot = ? "
                        "ORDER BY date_filed DESC NULLS LAST LIMIT 5",
                        (addr["block"], addr["lot"]),
                    ).fetchall():
                        data["complaints"].append({
                            "description_short": (r[2] or "")[:80],
                            "status": r[1] or "unknown",
                        })
            except Exception:
                pass

            # Violations
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT nov_number, status, description "
                            "FROM violations WHERE block = %s AND lot = %s "
                            "ORDER BY date_filed DESC NULLS LAST LIMIT 5",
                            (addr["block"], addr["lot"]),
                        )
                        for r in cur.fetchall():
                            data["violations"].append({
                                "description_short": (r[2] or "")[:80],
                                "status": r[1] or "unknown",
                            })
                else:
                    for r in conn.execute(
                        "SELECT nov_number, status, description "
                        "FROM violations WHERE block = ? AND lot = ? "
                        "ORDER BY date_filed DESC NULLS LAST LIMIT 5",
                        (addr["block"], addr["lot"]),
                    ).fetchall():
                        data["violations"].append({
                            "description_short": (r[2] or "")[:80],
                            "status": r[1] or "unknown",
                        })
            except Exception:
                pass

            # Entities (from contacts on permits at this address)
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT DISTINCT c.name, c.role, e.permit_count "
                            "FROM contacts c "
                            "JOIN entities e ON c.entity_id = e.entity_id "
                            "WHERE c.permit_number IN ("
                            "  SELECT permit_number FROM permits WHERE block = %s AND lot = %s"
                            ") "
                            "AND c.name IS NOT NULL "
                            "ORDER BY e.permit_count DESC LIMIT 10",
                            (addr["block"], addr["lot"]),
                        )
                        for r in cur.fetchall():
                            data["entities"].append({
                                "name": r[0],
                                "role": r[1] or "unknown",
                                "permit_count": r[2] or 0,
                            })
                else:
                    for r in conn.execute(
                        "SELECT DISTINCT c.name, c.role, e.permit_count "
                        "FROM contacts c "
                        "JOIN entities e ON c.entity_id = e.entity_id "
                        "WHERE c.permit_number IN ("
                        "  SELECT permit_number FROM permits WHERE block = ? AND lot = ?"
                        ") "
                        "AND c.name IS NOT NULL "
                        "ORDER BY e.permit_count DESC LIMIT 10",
                        (addr["block"], addr["lot"]),
                    ).fetchall():
                        data["entities"].append({
                            "name": r[0],
                            "role": r[1] or "unknown",
                            "permit_count": r[2] or 0,
                        })
            except Exception:
                pass

            # Routing progress (latest permit with routing data)
            try:
                latest_permit = data["permits"][0]["permit_number"] if data["permits"] else None
                if latest_permit and BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT station, review_result "
                            "FROM addenda WHERE permit_number = %s "
                            "AND station IS NOT NULL "
                            "ORDER BY finish_date DESC NULLS LAST LIMIT 8",
                            (latest_permit,),
                        )
                        for r in cur.fetchall():
                            result = (r[1] or "pending").lower()
                            if "approved" in result:
                                bar_class = "complete"
                                pct = 100
                            elif "comment" in result or "hold" in result:
                                bar_class = "in-progress"
                                pct = 60
                            else:
                                bar_class = "pending"
                                pct = 10
                            data["routing"].append({
                                "station": r[0],
                                "result": r[1] or "Pending",
                                "bar_class": bar_class,
                                "pct": pct,
                            })
            except Exception:
                pass

        finally:
            conn.close()
    except Exception as e:
        logging.warning("Demo data query failed: %s", e)

    # Timeline estimate (hardcoded example for demo reliability)
    if not data.get("timeline"):
        data["timeline"] = {
            "p25": 28, "p50": 45, "p75": 78, "p90": 120,
            "p25_pct": 23, "p50_pct": 38, "p75_pct": 65, "p90_pct": 100,
            "sample_size": "1,100,000+",
            "confidence": "high",
        }

    _demo_cache.clear()
    _demo_cache.update(data)
    _demo_cache["computed_at"] = _time.time()
    return _demo_cache


@bp.route("/demo")
def demo():
    """Pre-loaded property intelligence demo for Zoom presentations."""
    data = dict(_get_demo_data())  # copy to avoid mutating cache
    data["density_max"] = request.args.get("density") == "max"
    return render_template("demo.html", **data)
