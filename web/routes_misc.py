"""Miscellaneous routes: brief, dashboard, beta-request, SEO pages.

Blueprint: misc (no url_prefix)
"""

import logging
import time
from datetime import datetime

from flask import (
    Blueprint, render_template, request, g, Response, jsonify,
    redirect, url_for, session,
)

from web.helpers import login_required
from web.tier_gate import has_tier

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
    from web.helpers import get_cached_or_compute
    lookback = request.args.get("lookback", "1")
    try:
        lookback_days = max(1, min(int(lookback), 90))
    except ValueError:
        lookback_days = 1
    # Tier gate: free users see upgrade teaser instead of full brief content
    tier_locked = not has_tier(g.user, 'beta')

    primary_addr = get_primary_address(g.user["user_id"])
    cache_key = f"brief:{g.user['user_id']}:{lookback_days}"
    brief_data = get_cached_or_compute(
        cache_key,
        lambda: get_morning_brief(g.user["user_id"], lookback_days, primary_address=primary_addr),
        ttl_minutes=30
    )
    # Add cache metadata for template
    brief_data['cached_at'] = brief_data.get('_cached_at')
    brief_data['can_refresh'] = True
    return render_template("brief.html", user=g.user, brief=brief_data,
                           active_page="brief",
                           tier_locked=tier_locked,
                           required_tier='beta',
                           current_tier=g.user.get('subscription_tier', 'free'))


@bp.route("/brief/refresh", methods=["POST"])
@login_required
def brief_refresh():
    """Force-invalidate the brief cache for this user (rate-limited to once per 5 min)."""
    from web.helpers import invalidate_cache
    user_id = g.user["user_id"]
    # Rate limit: check if last refresh was < 5 min ago
    last_refresh = session.get("last_brief_refresh", 0)
    if time.time() - last_refresh < 300:
        return "Rate limited — try again in a few minutes", 429
    invalidate_cache(f"brief:{user_id}:%")
    session["last_brief_refresh"] = time.time()
    return redirect(url_for("misc.brief"))


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
        "/demo",
        "/join-beta",
        "/docs",
        "/privacy",
        "/terms",
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


_DEMO_CACHE_TTL = 900  # 15 minutes


def _get_demo_data() -> dict:
    """Pre-query all intelligence layers for the demo address. Cached 15 minutes."""
    import time as _time

    now = _time.time()
    if _demo_cache and _demo_cache.get("computed_at", 0) > now - _DEMO_CACHE_TTL:
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
        "severity_tier": None,
        "severity_score": None,
        "permit_count": None,
        "open_permit_count": None,
        "complaint_count": None,
        "violation_count": None,
    }

    try:
        from src.db import get_connection, BACKEND
        conn = get_connection()
        ph = "%s" if BACKEND == "postgres" else "?"
        try:
            # ── Task 75-4-1: Check parcel_summary for real cached data ──────
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT neighborhood, permit_count, open_permit_count, "
                            "complaint_count, violation_count, health_tier "
                            "FROM parcel_summary WHERE block = %s AND lot = %s",
                            (addr["block"], addr["lot"]),
                        )
                        ps_row = cur.fetchone()
                else:
                    ps_row = conn.execute(
                        "SELECT neighborhood, permit_count, open_permit_count, "
                        "complaint_count, violation_count, health_tier "
                        "FROM parcel_summary WHERE block = ? AND lot = ?",
                        (addr["block"], addr["lot"]),
                    ).fetchone()

                if ps_row:
                    if ps_row[0]:
                        data["neighborhood"] = ps_row[0]
                    if ps_row[1] is not None:
                        data["permit_count"] = ps_row[1]
                    if ps_row[2] is not None:
                        data["open_permit_count"] = ps_row[2]
                    if ps_row[3] is not None:
                        data["complaint_count"] = ps_row[3]
                    if ps_row[4] is not None:
                        data["violation_count"] = ps_row[4]
                    if ps_row[5]:
                        data["severity_tier"] = ps_row[5]
            except Exception:
                pass  # Fallback to hardcoded values below

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
                    "permit_type_definition": r[1] or "",
                    "description": r[5] or "",
                    "estimated_cost": cost,
                })

            # ── Task 75-4-2: Score active permits with severity model ──────
            try:
                from src.severity import score_permit, PermitInput
                active_statuses = {"issued", "filed", "approved"}
                active_permits = [
                    p for p in data["permits"]
                    if p.get("status", "").lower() in active_statuses
                ]
                if active_permits:
                    scored = []
                    for p in active_permits:
                        pi = PermitInput.from_dict({
                            "permit_number": p["permit_number"],
                            "status": p["status"],
                            "permit_type_definition": p.get("permit_type_definition", ""),
                            "description": p.get("description", ""),
                            "filed_date": p.get("filed_date"),
                            "estimated_cost": p.get("estimated_cost") or 0.0,
                        })
                        result = score_permit(pi)
                        scored.append((result.score, result.tier, p["permit_number"]))
                    # Highest score among active permits drives the overall tier
                    scored.sort(key=lambda x: x[0], reverse=True)
                    top_score, top_tier, _ = scored[0]
                    # Only override if parcel_summary didn't provide a tier
                    if not data.get("severity_tier"):
                        data["severity_tier"] = top_tier
                    data["severity_score"] = top_score
                    # Annotate each permit with its tier
                    score_map = {pnum: (sc, tr) for sc, tr, pnum in scored}
                    for p in data["permits"]:
                        if p["permit_number"] in score_map:
                            p["severity_score"], p["severity_tier"] = score_map[p["permit_number"]]
                        else:
                            p["severity_score"] = None
                            p["severity_tier"] = None
            except Exception as sev_err:
                logging.debug("Demo severity scoring skipped: %s", sev_err)

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


@bp.route("/welcome")
@login_required
def welcome():
    """3-step onboarding page shown to new beta users after first login.

    Walks through: (1) address search, (2) property report, (3) watchlist.
    Redirects to dashboard if user has already completed onboarding.
    """
    user = g.user
    # If already completed, redirect to dashboard
    if user.get("onboarding_complete"):
        return redirect(url_for("index"))
    return render_template("welcome.html", user=user, active_page="welcome")


@bp.route("/demo")
def demo():
    """Pre-loaded property intelligence demo for Zoom presentations."""
    data = dict(_get_demo_data())  # copy to avoid mutating cache
    data["density_max"] = request.args.get("density") == "max"
    return render_template("demo.html", **data)


@bp.route("/demo/guided")
def demo_guided():
    """Self-guided walkthrough page for stakeholder demos."""
    return render_template("demo_guided.html")


# ---------------------------------------------------------------------------
# API Documentation + Legal pages (no auth required)
# ---------------------------------------------------------------------------

@bp.route("/docs")
def api_docs():
    """Public API documentation page — 34 tools across 7 categories."""
    from web.docs_generator import get_tool_catalog
    catalog = get_tool_catalog()
    return render_template("docs.html", catalog=catalog)


@bp.route("/privacy")
def privacy():
    """Privacy policy page."""
    return render_template("privacy.html")


@bp.route("/terms")
def terms():
    """Terms of service page."""
    return render_template("terms.html")


# QS13: Honeypot capture page — /join-beta
# ---------------------------------------------------------------------------

_BETA_REQUEST_BUCKETS: dict = {}  # ip -> list of timestamps


@bp.route("/join-beta", methods=["GET"])
def join_beta():
    """Honeypot capture page: waitlist signup shown to non-authenticated users.

    In HONEYPOT_MODE=1, the middleware redirects most paths here so that
    organic traffic lands on a waitlist form instead of a login wall.
    """
    ref = request.args.get("ref", "")
    q = request.args.get("q", "")
    return render_template("join_beta.html", ref=ref, q=q)


@bp.route("/join-beta", methods=["POST"])
def join_beta_post():
    """Process the /join-beta waitlist form submission."""
    import os as _os
    import time as _time

    # Honeypot spam check — bots fill the hidden 'website' field
    website = request.form.get("website", "").strip()
    if website:
        # Silent drop — don't reveal the honeypot
        logging.warning("join_beta honeypot triggered from IP %s", request.remote_addr)
        return "", 200

    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    interest_address = request.form.get("interest_address", "").strip()
    mcp_interest = bool(request.form.get("mcp_interest"))
    ref = request.form.get("ref", "").strip()

    if not email or "@" not in email:
        return render_template("join_beta.html", ref=ref, q="",
                               error="Please enter a valid email address.")

    # Rate limit: 3 signups per hour per IP
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    ip = ip.split(",")[0].strip()
    now = _time.time()
    _BETA_REQUEST_BUCKETS.setdefault(ip, [])
    _BETA_REQUEST_BUCKETS[ip] = [t for t in _BETA_REQUEST_BUCKETS[ip] if now - t < 3600]
    if len(_BETA_REQUEST_BUCKETS[ip]) >= 3:
        return render_template("join_beta.html", ref=ref, q="",
                               error="Too many requests. Please try again later.")
    _BETA_REQUEST_BUCKETS[ip].append(now)

    # Write to DB
    try:
        from src.db import execute_write
        execute_write(
            """
            INSERT INTO beta_requests
                (email, name, role, interest_address, mcp_interest, referrer, ip, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', NOW())
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                role = EXCLUDED.role,
                interest_address = EXCLUDED.interest_address,
                mcp_interest = EXCLUDED.mcp_interest,
                referrer = EXCLUDED.referrer,
                ip = EXCLUDED.ip
            """,
            (
                email,
                name or None,
                role or None,
                interest_address or None,
                mcp_interest,
                ref or None,
                ip,
            ),
        )
    except Exception as e:
        logging.error("join_beta DB error: %s", e)

    # Send confirmation email
    try:
        from web.auth import send_beta_confirmation_email
        send_beta_confirmation_email(email)
    except Exception as e:
        logging.warning("join_beta confirmation email failed: %s", e)

    # Send admin alert
    try:
        admin_email = _os.environ.get("ADMIN_EMAIL", "").strip()
        if admin_email:
            from web.auth import SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASS
            if SMTP_HOST:
                import smtplib
                from email.message import EmailMessage
                msg = EmailMessage()
                msg["Subject"] = f"New beta signup: {email}"
                msg["From"] = f"SF Permits AI <{SMTP_FROM}>"
                msg["To"] = admin_email
                msg.set_content(
                    f"Email: {email}\nName: {name}\nRole: {role}\n"
                    f"Ref: {ref}\nAddress: {interest_address}\n"
                    f"MCP Interest: {'Yes' if mcp_interest else 'No'}\nIP: {ip}"
                )
                with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as srv:
                    srv.starttls()
                    if SMTP_USER:
                        srv.login(SMTP_USER, SMTP_PASS or "")
                    srv.send_message(msg)
    except Exception as e:
        logging.warning("join_beta admin alert failed: %s", e)

    return redirect("/join-beta/thanks")


@bp.route("/join-beta/thanks", methods=["GET"])
def join_beta_thanks():
    """Post-signup thank-you page with queue position."""
    queue_position = 0
    try:
        from src.db import query_one
        row = query_one(
            "SELECT COUNT(*) FROM beta_requests WHERE status = %s",
            ("pending",),
        )
        queue_position = row[0] if row else 0
    except Exception:
        pass
    return render_template("join_beta_thanks.html", queue_position=queue_position)
