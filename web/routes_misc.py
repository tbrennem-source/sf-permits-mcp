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
