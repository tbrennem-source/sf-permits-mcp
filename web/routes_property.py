"""Property-related routes: consultants, reports, portfolio.

Blueprint: property (no url_prefix)
"""

import logging
import os

from flask import (
    Blueprint, render_template, request, redirect, abort, g, Response,
    jsonify,
)

from web.helpers import (
    login_required, _is_rate_limited, _resolve_block_lot, NEIGHBORHOODS,
)
from web.tier_gate import has_tier

bp = Blueprint("property", __name__)


# ---------------------------------------------------------------------------
# Permit Prep (QS3-A)
# ---------------------------------------------------------------------------

@bp.route("/prep/<permit_number>")
@login_required
def permit_prep(permit_number):
    """Permit Prep checklist page.

    If checklist exists for this user+permit, render it.
    Otherwise auto-create one.
    """
    from web.permit_prep import get_checklist, create_checklist

    user_id = g.user["user_id"]
    checklist = get_checklist(permit_number, user_id)

    if not checklist:
        try:
            create_checklist(permit_number, user_id)
            checklist = get_checklist(permit_number, user_id)
        except Exception as e:
            logging.error("Failed to create prep checklist: %s", e)
            return render_template(
                "permit_prep.html",
                checklist=None,
                error=f"Failed to generate checklist: {e}",
                progress={"total": 0, "addressed": 0, "remaining": 0, "percent": 0},
            ), 500

    if not checklist:
        abort(500)

    return render_template(
        "permit_prep.html",
        checklist=checklist,
        progress=checklist["progress"],
    )


# ---------------------------------------------------------------------------
# Rate limit constants
# ---------------------------------------------------------------------------
RATE_LIMIT_MAX_REPORT = 10  # /report views per window
RATE_LIMIT_MAX_SHARE = 3    # /report share emails per window


# ---------------------------------------------------------------------------
# Consultants
# ---------------------------------------------------------------------------

@bp.route("/consultants")
@login_required
def consultants_page():
    """Consultant recommendation dashboard.

    Accepts optional query params from property report "Find a consultant" link:
      ?block=XXXX&lot=YYY&signal=recommended
    When present, pre-fills the form and auto-submits.
    """
    from src.db import query as db_query

    prefill = None
    block = request.args.get("block", "").strip()
    lot = request.args.get("lot", "").strip()
    signal = request.args.get("signal", "").strip()

    if block and lot:
        # Look up address and neighborhood from permits table
        addr = ""
        neighborhood = ""
        try:
            row = db_query(
                "SELECT street_number, street_name, neighborhood "
                "FROM permits WHERE block = %s AND lot = %s "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
            if row:
                addr = f"{row[0][0] or ''} {row[0][1] or ''}".strip()
                neighborhood = row[0][2] or ""
        except Exception:
            pass

        # Check if property has active complaints (for checkbox prefill)
        has_complaint = False
        try:
            c_row = db_query(
                "SELECT COUNT(*) FROM complaints "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            has_complaint = bool(c_row and c_row[0][0] > 0)
        except Exception:
            pass

        prefill = {
            "block": block,
            "lot": lot,
            "address": addr,
            "neighborhood": neighborhood,
            "signal": signal,
            "has_complaint": has_complaint,
        }

    return render_template("consultants.html",
                           neighborhoods=NEIGHBORHOODS,
                           prefill=prefill)


@bp.route("/consultants/search", methods=["POST"])
@login_required
def consultants_search():
    """Search for consultants and return HTMX fragment with results."""
    from src.tools.recommend_consultants import recommend_consultants, ScoredConsultant

    address = request.form.get("address", "").strip() or None
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None
    neighborhood = request.form.get("neighborhood", "").strip() or None
    permit_type = request.form.get("permit_type", "").strip() or None
    has_complaint = request.form.get("has_active_complaint") == "on"
    needs_planning = request.form.get("needs_planning") == "on"
    sort_by = request.form.get("sort_by", "score").strip()

    try:
        # recommend_consultants is async, returns markdown string
        # But for the dashboard we want structured data — call the internal
        # scoring logic directly
        from src.tools.recommend_consultants import (
            _query_consultants, _query_relationships,
            _load_registry, _get_registered_names,
        )
        from src.db import get_connection, BACKEND
        from datetime import date

        conn = get_connection()
        try:
            consultants_raw = _query_consultants(conn, min_permits=20)
            if not consultants_raw:
                return render_template(
                    "consultants.html",
                    neighborhoods=NEIGHBORHOODS,
                    error="No consultants found with sufficient activity.",
                )

            max_permits = max(e["permit_count"] for e in consultants_raw)
            registered_names = _get_registered_names()
            registry = _load_registry()

            # Check which consultants have worked at this address (block/lot)
            address_match_ids: set[int] = set()
            if block and lot:
                try:
                    from src.db import query as db_query
                    ph = "%s" if BACKEND == "postgres" else "?"
                    addr_rows = db_query(
                        f"SELECT DISTINCT e.entity_id "
                        f"FROM contacts c JOIN entities e ON c.entity_id = e.entity_id "
                        f"WHERE c.block = {ph} AND c.lot = {ph} "
                        f"AND e.entity_type = 'consultant'",
                        (block, lot),
                    )
                    address_match_ids = {r[0] for r in addr_rows} if addr_rows else set()
                except Exception:
                    pass

            scored = []

            for exp in consultants_raw:
                s = ScoredConsultant(
                    entity_id=exp["entity_id"],
                    name=exp["canonical_name"],
                    firm=exp["canonical_firm"] or "",
                    permit_count=exp["permit_count"],
                )

                # Volume score (0-25)
                volume_score = (exp["permit_count"] / max_permits) * 25 if max_permits > 0 else 0
                s.breakdown["volume"] = round(volume_score, 1)
                s.score += volume_score

                # Get relationships
                rels = _query_relationships(conn, exp["entity_id"])

                total_rel_permits = 0
                residential_permits = 0
                all_neighborhoods = set()
                latest_date = ""
                network_partners = 0

                for r in rels:
                    shared = r["shared_permits"]
                    total_rel_permits += shared
                    ptypes = (r["permit_types"] or "").lower()
                    if "a" in ptypes.split(",") or "additions" in ptypes:
                        residential_permits += shared
                    if r["neighborhoods"]:
                        for n in r["neighborhoods"].split(","):
                            n = n.strip()
                            if n:
                                all_neighborhoods.add(n)
                    if r["date_range_end"] and r["date_range_end"] > latest_date:
                        latest_date = r["date_range_end"]
                    if shared >= 3:
                        network_partners += 1

                s.neighborhoods = sorted(all_neighborhoods)
                s.date_range_end = latest_date
                s.network_size = network_partners

                # Specialization (0-25)
                if total_rel_permits > 0:
                    spec_score = (residential_permits / total_rel_permits) * 25
                else:
                    spec_score = 12.5
                s.breakdown["specialization"] = round(spec_score, 1)
                s.score += spec_score

                # Neighborhood (0-20)
                hood_match = False
                if neighborhood:
                    target_lower = neighborhood.lower()
                    hood_match = any(
                        target_lower in n.lower() or n.lower() in target_lower
                        for n in all_neighborhoods
                    )
                    hood_score = 20 if hood_match else 0
                else:
                    hood_score = 10
                s.breakdown["neighborhood"] = round(hood_score, 1)
                s.score += hood_score

                # Recency (0-15)
                recency_score = 0
                if latest_date:
                    try:
                        end_date = date.fromisoformat(latest_date[:10])
                        months_ago = (date.today() - end_date).days / 30
                        if months_ago <= 6:
                            recency_score = 15
                        elif months_ago <= 12:
                            recency_score = 10
                        elif months_ago <= 24:
                            recency_score = 5
                    except (ValueError, TypeError):
                        pass
                s.breakdown["recency"] = round(recency_score, 1)
                s.score += recency_score

                # Network (0-15)
                if network_partners >= 10:
                    network_score = 15
                elif network_partners >= 5:
                    network_score = 10
                elif network_partners >= 2:
                    network_score = 5
                else:
                    network_score = 0
                s.breakdown["network"] = round(network_score, 1)
                s.score += network_score

                # Bonuses
                if has_complaint and exp["permit_count"] >= 50 and len(all_neighborhoods) >= 3:
                    s.breakdown["complaint_bonus"] = 10
                    s.score += 10
                if needs_planning and network_partners >= 5:
                    s.breakdown["planning_bonus"] = 10
                    s.score += 10

                name_lower = exp["canonical_name"].lower()
                if name_lower in registered_names:
                    s.is_registered = True
                    s.breakdown["ethics_bonus"] = 5
                    s.score += 5
                    for c in registry.get("consultants", []):
                        if c.get("name", "").strip().lower() == name_lower:
                            s.contact_info = {
                                "email": c.get("email", ""),
                                "phone": c.get("phone", ""),
                            }
                            break

                # Address match bonus (+5) + badge
                if exp["entity_id"] in address_match_ids:
                    s.score += 5
                    s.breakdown["address_match"] = 5

                # Build smart badges list (stored as tuples: label, css_class)
                badges = []
                if exp["entity_id"] in address_match_ids:
                    badges.append(("Worked at this address", "badge-address"))
                if s.is_registered:
                    badges.append(("Ethics Registered", "badge-ethics"))
                if hood_match and neighborhood:
                    badges.append(("Neighborhood match", "badge-hood"))
                if exp["permit_count"] >= 100:
                    badges.append(("High volume", "badge-volume"))
                if network_partners >= 10:
                    badges.append(("Strong network", "badge-network"))
                if recency_score == 15:
                    badges.append(("Recently active", "badge-recent"))
                # Store badges on the dataclass via dynamic attr
                s.badges = badges  # type: ignore[attr-defined]

                scored.append(s)
        finally:
            conn.close()

        # Sort by user-selected criterion
        if sort_by == "permits":
            scored.sort(key=lambda x: x.permit_count, reverse=True)
        elif sort_by == "recency":
            scored.sort(key=lambda x: x.date_range_end or "", reverse=True)
        elif sort_by == "network":
            scored.sort(key=lambda x: x.network_size, reverse=True)
        else:  # default: score
            scored.sort(key=lambda x: x.score, reverse=True)

        top = scored[:10]

        return render_template(
            "consultants.html",
            neighborhoods=NEIGHBORHOODS,
            results=top,
            sort_by=sort_by,
        )

    except Exception as e:
        logging.error("Consultant search failed: %s", e)
        return render_template(
            "consultants.html",
            neighborhoods=NEIGHBORHOODS,
            error=f"Search failed: {e}",
        )


# Legacy route redirects (backward compatibility)
@bp.route("/expediters")
def expediters_redirect():
    return redirect("/consultants" + ("?" + request.query_string.decode() if request.query_string else ""), 301)

@bp.route("/expediters/search", methods=["POST"])
def expediters_search_redirect():
    return redirect("/consultants/search", 308)


# ---------------------------------------------------------------------------
# Property report
# ---------------------------------------------------------------------------

@bp.route("/report/<block>/<lot>")
def property_report(block, lot):
    """Comprehensive property report — public (no login required).

    Owner Mode: If the logged-in user's primary address matches the
    report address (or ?owner=1 is set), the report includes a
    Remediation Roadmap and extended consultant scoring.
    """
    from web.report import get_property_report
    from web.owner_mode import detect_owner
    from src.report_links import ReportLinks

    ip = request.remote_addr or "unknown"
    if _is_rate_limited(ip, RATE_LIMIT_MAX_REPORT):
        abort(429)

    block = block.strip()
    lot = lot.strip()
    if not block or not lot:
        abort(400)

    user = getattr(g, "user", None)
    explicit_toggle = request.args.get("owner", "").lower() in ("1", "true", "yes")

    try:
        # First pass without owner mode to get the address
        report = get_property_report(block, lot)

        # Detect owner from address match or explicit toggle
        is_owner = detect_owner(user, report.get("address", ""), explicit_toggle)

        # If owner detected, regenerate with Owner Mode extensions
        if is_owner:
            report = get_property_report(block, lot, is_owner=True)
    except Exception as e:
        logging.exception("Report generation failed for %s/%s", block, lot)
        return render_template(
            "report.html",
            report=None,
            error=f"Could not generate report: {e}",
            user=user,
            is_owner=False,
            links=ReportLinks,
        ), 500

    is_owner = report.get("is_owner", False)

    if not report.get("permits") and not report.get("complaints") and not report.get("property_profile"):
        return render_template(
            "report.html",
            report=report,
            error=f"No data found for Block {block}, Lot {lot}.",
            user=user,
            is_owner=is_owner,
            links=ReportLinks,
        ), 404

    return render_template(
        "report.html",
        report=report,
        user=user,
        is_owner=is_owner,
        links=ReportLinks,
    )


@bp.route("/report/<block>/<lot>/share", methods=["POST"])
@login_required
def property_report_share(block, lot):
    """Email a property report to a specified address."""
    from web.report import get_property_report
    from src.report_links import ReportLinks
    import smtplib
    from email.message import EmailMessage

    ip = request.remote_addr or "unknown"
    if _is_rate_limited(ip, RATE_LIMIT_MAX_SHARE):
        return "<div class='flash error'>Rate limited — please try again in a minute.</div>", 429

    to_email = request.form.get("email", "").strip()
    if not to_email or "@" not in to_email:
        return "<div class='flash error'>Please enter a valid email address.</div>", 400

    personal_message = request.form.get("message", "").strip()[:500]

    block = block.strip()
    lot = lot.strip()

    try:
        report = get_property_report(block, lot)
    except Exception as e:
        logging.exception("Report generation failed for share: %s/%s", block, lot)
        return f"<div class='flash error'>Failed to generate report: {e}</div>", 500

    base_url = os.environ.get("BASE_URL", "http://localhost:5001")
    report_url = f"{base_url}/report/{block}/{lot}"

    is_owner = report.get("is_owner", False)
    sender_name = g.user.get("display_name") or g.user.get("email", "Someone")

    try:
        html_body = render_template(
            "report_email.html",
            report=report,
            report_url=report_url,
            base_url=base_url,
            is_owner=is_owner,
            links=ReportLinks,
            sender_name=sender_name,
            personal_message=personal_message,
        )
    except Exception as e:
        logging.exception("Report email render failed")
        return f"<div class='flash error'>Failed to render email: {e}</div>", 500

    # Send via SMTP (reuse brief email SMTP config)
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_from = os.environ.get("SMTP_FROM", "noreply@sfpermits.ai")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    address = report.get("address", f"Block {block}, Lot {lot}")
    subject = f"Property Report — {address} — sfpermits.ai"

    if not smtp_host:
        logging.info("SMTP not configured — would send report to %s (%d chars)", to_email, len(html_body))
        return "<div class='flash success'>Report sent (dev mode — no SMTP configured).</div>"

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"SF Permits AI <{smtp_from}>"
        msg["To"] = to_email
        plain_text = f"Property Report for {address}\n\n"
        if personal_message:
            plain_text += f"{sender_name} says: {personal_message}\n\n"
        plain_text += f"View the full report: {report_url}\n\n"
        plain_text += "--\nsfpermits.ai - San Francisco Building Permit Intelligence"
        msg.set_content(plain_text)
        msg.add_alternative(html_body, subtype="html")

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_pass or "")
            server.send_message(msg)

        logging.info("Report email sent to %s for %s/%s", to_email, block, lot)
        return "<div class='flash success'>Report sent! Check your inbox.</div>"
    except Exception as e:
        logging.exception("Failed to send report email to %s", to_email)
        return f"<div class='flash error'>Failed to send email: {e}</div>", 500


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------

@bp.route("/portfolio")
@login_required
def portfolio():
    """Portfolio dashboard — property card grid with health indicators."""
    from web.portfolio import get_portfolio

    # Tier gate: free users see upgrade teaser instead of full portfolio
    if not has_tier(g.user, 'beta'):
        return render_template(
            "portfolio.html",
            tier_locked=True,
            required_tier='beta',
            current_tier=g.user.get('subscription_tier', 'free'),
            user=g.user,
            properties=[],
            summary={},
            filter_by='all',
            sort_by='recent',
        ), 200

    filter_by = request.args.get("filter", "all")
    sort_by = request.args.get("sort", "recent")

    data = get_portfolio(g.user["user_id"])
    properties = data["properties"]

    # Apply filters
    if filter_by == "action_needed":
        properties = [p for p in properties if p["worst_health"] in ("behind", "at_risk")]
    elif filter_by == "in_review":
        properties = [p for p in properties if any(pm["status"] == "filed" for pm in p["permits"])]
    elif filter_by == "active":
        properties = [p for p in properties if p["active_count"] > 0]

    # Apply sort
    health_order = {"at_risk": 0, "behind": 1, "slower": 2, "on_track": 3}
    if sort_by == "cost_desc":
        properties.sort(key=lambda p: p["total_cost"] or 0, reverse=True)
    elif sort_by == "stale":
        properties.sort(key=lambda p: p["latest_activity"] or "")
    elif sort_by == "health":
        properties.sort(key=lambda p: health_order.get(p["worst_health"], 4))
    else:
        properties.sort(key=lambda p: p["latest_activity"] or "", reverse=True)

    return render_template("portfolio.html",
                           tier_locked=False,
                           properties=properties,
                           summary=data["summary"],
                           filter_by=filter_by,
                           sort_by=sort_by)


@bp.route("/portfolio/timeline/<block>/<lot>")
def portfolio_timeline(block, lot):
    """HTMX: load inspection timeline for a property."""
    from web.portfolio import get_inspection_timeline
    timeline = get_inspection_timeline(block, lot)
    return render_template("fragments/inspection_timeline.html", timeline=timeline)


@bp.route("/portfolio/discover", methods=["POST"])
@login_required
def portfolio_discover():
    """HTMX: search for consultant's permits by name/firm."""
    from web.portfolio import discover_portfolio

    name = request.form.get("name", "").strip()
    firm = request.form.get("firm", "").strip()

    if not name and not firm:
        return '<div style="color: var(--text-muted);">Enter a name or firm to search.</div>'

    discovery = discover_portfolio(name, firm or None)
    return render_template("fragments/discover_results.html", discovery=discovery)


@bp.route("/portfolio/import", methods=["POST"])
@login_required
def portfolio_import():
    """HTMX: bulk-create watches from discovery results."""
    from web.portfolio import bulk_add_watches

    selected = request.form.getlist("selected")
    addresses = []
    for idx in selected:
        addresses.append({
            "street_number": request.form.get(f"snum_{idx}", ""),
            "street_name": request.form.get(f"sname_{idx}", ""),
            "block": request.form.get(f"block_{idx}", ""),
            "lot": request.form.get(f"lot_{idx}", ""),
        })

    count = bulk_add_watches(g.user["user_id"], addresses)
    return render_template("fragments/import_confirmation.html", count=count)
