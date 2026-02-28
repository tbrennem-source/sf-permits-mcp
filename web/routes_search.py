"""Search & lookup routes — /lookup, /lookup/intel-preview, and /ask endpoints.

Extracted from web/app.py during Sprint 64 Blueprint refactor.
Sprint 69-S2: Added intelligence preview endpoint and intel gathering.
"""

import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from flask import Blueprint, g, redirect, render_template, request

from src.tools.intent_router import classify as classify_intent
from src.tools.knowledge_base import get_knowledge_base
from src.tools.permit_lookup import permit_lookup
from src.tools.search_complaints import search_complaints
from src.tools.search_entity import search_entity
from src.tools.search_violations import search_violations

from web.helpers import (
    NEIGHBORHOODS,
    _is_no_results,
    _rate_limited_ai,
    _resolve_block_lot,
    md_to_html,
    run_async,
    parse_search_query,
    build_empty_result_guidance,
)
from web.tier_gate import has_tier

bp = Blueprint("search", __name__)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Intelligence gathering for property preview (Sprint 69-S2)
# ---------------------------------------------------------------------------

def _gather_intel(block: str, lot: str) -> dict:
    """Gather property intelligence data from local DB + SODA.

    Returns a dict with routing progress, complaint/violation counts,
    top entities, and a has_intelligence flag. Never raises — returns
    degraded data on any error.
    """
    intel = {
        "routing": [],
        "complaints_count": 0,
        "violations_count": 0,
        "top_entities": [],
        "has_intelligence": False,
        "timeout": False,
    }

    start = time.monotonic()
    deadline = 2.0  # seconds

    try:
        from src.db import get_connection, BACKEND
        _ph = "%s" if BACKEND == "postgres" else "?"

        conn = get_connection()
        try:
            # 1. Routing progress for active permits at this parcel
            active_sql = f"""
                SELECT permit_number, status, permit_type, description
                FROM permits
                WHERE block = {_ph} AND lot = {_ph}
                  AND status IN ('issued', 'filed', 'approved', 'plancheck')
                ORDER BY filed_date DESC
                LIMIT 10
            """
            if BACKEND == "postgres":
                with conn.cursor() as cur:
                    cur.execute(active_sql, [block, lot])
                    active_permits = cur.fetchall()
            else:
                active_permits = conn.execute(active_sql, [block, lot]).fetchall()

            for ap in active_permits:
                pnum = ap[0]
                if time.monotonic() - start > deadline:
                    intel["timeout"] = True
                    break

                # Count routing stations for this permit
                routing_sql = f"""
                    SELECT station, review_results
                    FROM addenda
                    WHERE application_number = {_ph}
                    ORDER BY step
                """
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(routing_sql, [pnum])
                        stations = cur.fetchall()
                else:
                    stations = conn.execute(routing_sql, [pnum]).fetchall()

                if stations:
                    cleared = sum(1 for s in stations if s[1] and s[1].strip().lower() not in ('', 'pending', 'in review'))
                    total = len(stations)
                    current = next((s[0] for s in stations if not s[1] or s[1].strip().lower() in ('', 'pending', 'in review')), None)
                    intel["routing"].append({
                        "permit_number": pnum,
                        "status": ap[1],
                        "permit_type": ap[2],
                        "description": (ap[3] or "")[:100],
                        "stations_cleared": cleared,
                        "stations_total": total,
                        "current_station": current or "Complete",
                    })

            # 2. Top entities (architect, contractor, owner) from contacts
            if time.monotonic() - start <= deadline:
                entity_sql = f"""
                    SELECT
                        COALESCE(applicant_name, ''),
                        COALESCE(contractor_name, ''),
                        COALESCE(engineer_name, '')
                    FROM contacts
                    WHERE block = {_ph} AND lot = {_ph}
                    LIMIT 50
                """
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(entity_sql, [block, lot])
                        contact_rows = cur.fetchall()
                else:
                    contact_rows = conn.execute(entity_sql, [block, lot]).fetchall()

                # Count entity appearances
                entity_counts = {}
                for row in contact_rows:
                    for i, role in enumerate(["Applicant", "Contractor", "Engineer"]):
                        name = row[i].strip() if row[i] else ""
                        if name and name.upper() not in ("N/A", "NA", "NONE", ""):
                            key = (name, role)
                            entity_counts[key] = entity_counts.get(key, 0) + 1

                # Top 3 by frequency
                sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)
                intel["top_entities"] = [
                    {"name": k[0], "role": k[1], "permit_count": v}
                    for (k, v) in sorted_entities[:3]
                ]

            # 3. Complaint + violation counts via SODA (or skip if near timeout)
            if time.monotonic() - start <= deadline - 0.5:
                try:
                    complaints_md = run_async(search_complaints(block=block, lot=lot, limit=1))
                    if complaints_md and "found" in complaints_md.lower():
                        import re as _re
                        m = _re.search(r'Found\s+\*?\*?(\d+)', complaints_md)
                        if m:
                            intel["complaints_count"] = int(m.group(1))
                except Exception:
                    pass

            if time.monotonic() - start <= deadline - 0.5:
                try:
                    violations_md = run_async(search_violations(block=block, lot=lot, limit=1))
                    if violations_md and "found" in violations_md.lower():
                        import re as _re
                        m = _re.search(r'Found\s+\*?\*?(\d+)', violations_md)
                        if m:
                            intel["violations_count"] = int(m.group(1))
                except Exception:
                    pass

            intel["has_intelligence"] = bool(
                intel["routing"] or intel["top_entities"]
                or intel["complaints_count"] or intel["violations_count"]
            )

        finally:
            conn.close()

    except Exception as e:
        logger.warning("Intel gathering failed for %s/%s: %s", block, lot, e)

    if time.monotonic() - start > deadline:
        intel["timeout"] = True

    return intel


# ---------------------------------------------------------------------------
# HTMX endpoint: intelligence preview panel (Sprint 69-S2)
# ---------------------------------------------------------------------------

@bp.route("/lookup/intel-preview", methods=["POST"])
def lookup_intel_preview():
    """HTMX fragment: intelligence preview panel for a property."""
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None
    street_number = request.form.get("street_number", "").strip() or None
    street_name = request.form.get("street_name", "").strip() or None

    # Resolve block/lot from address if needed
    if not block or not lot:
        if street_number and street_name:
            bl = _resolve_block_lot(street_number, street_name)
            if bl:
                block, lot = bl[0], bl[1]

    if not block or not lot:
        return '<div class="intel-empty">No property data available.</div>'

    intel = _gather_intel(block, lot)

    if intel.get("timeout") and not intel.get("has_intelligence"):
        # Return a spinner that auto-retries every 2 seconds
        return (
            '<div class="intel-loading" '
            'hx-post="/lookup/intel-preview" '
            'hx-trigger="revealed delay:1s" '
            f'hx-vals=\'{{"block": "{block}", "lot": "{lot}"}}\' '
            'hx-swap="outerHTML">'
            '<div class="intel-spinner"></div>'
            '<p>Loading property intelligence...</p>'
            '</div>'
        )

    return render_template(
        "fragments/intel_preview.html",
        intel=intel,
        block=block,
        lot=lot,
    )


# ---------------------------------------------------------------------------
# Permit lookup — /lookup endpoint
# ---------------------------------------------------------------------------

@bp.route("/lookup", methods=["POST"])
def lookup():
    """Look up permits by number, address, or block/lot."""
    lookup_mode = request.form.get("lookup_mode", "number")
    permit_number = request.form.get("permit_number", "").strip() or None
    street_number = request.form.get("street_number", "").strip() or None
    street_name = request.form.get("street_name", "").strip() or None
    block = request.form.get("block", "").strip() or None
    lot = request.form.get("lot", "").strip() or None

    # Validate based on selected mode
    if lookup_mode == "number" and not permit_number:
        return '<div class="error">Please enter a permit number.</div>', 400
    if lookup_mode == "address" and (not street_number or not street_name):
        return '<div class="error">Please enter both street number and street name.</div>', 400
    if lookup_mode == "parcel" and (not block or not lot):
        return '<div class="error">Please enter both block and lot numbers.</div>', 400

    try:
        result_md = run_async(permit_lookup(
            permit_number=permit_number if lookup_mode == "number" else None,
            street_number=street_number if lookup_mode == "address" else None,
            street_name=street_name if lookup_mode == "address" else None,
            block=block if lookup_mode == "parcel" else None,
            lot=lot if lookup_mode == "parcel" else None,
        ))
        result_html = md_to_html(result_md)
    except Exception as e:
        result_html = f'<div class="error">Lookup error: {e}</div>'

    # Resolve report URL for property report link
    report_url = None
    try:
        if lookup_mode == "parcel" and block and lot:
            report_url = f"/report/{block}/{lot}"
        elif lookup_mode == "address" and street_number and street_name:
            bl = _resolve_block_lot(street_number, street_name)
            if bl:
                report_url = f"/report/{bl[0]}/{bl[1]}"
    except Exception:
        pass

    # Extract street address for action buttons
    street_address = None
    permit_type = None

    if lookup_mode == "address" and street_number and street_name:
        street_address = f"{street_number} {street_name}"
    elif lookup_mode == "parcel" and block and lot:
        street_address = f"Block {block}, Lot {lot}"

    # Resolve block/lot for intel preview HTMX call
    resolved_block = block
    resolved_lot = lot
    if lookup_mode == "address" and street_number and street_name:
        try:
            bl = _resolve_block_lot(street_number, street_name)
            if bl:
                resolved_block, resolved_lot = bl[0], bl[1]
        except Exception:
            pass

    return render_template(
        "lookup_results.html",
        result=result_html,
        report_url=report_url,
        street_address=street_address,
        permit_type=permit_type,
        block=resolved_block,
        lot=resolved_lot,
    )


# ---------------------------------------------------------------------------
# Conversational search box — /ask endpoint
# ---------------------------------------------------------------------------

@bp.route("/ask", methods=["POST"])
@_rate_limited_ai
def ask():
    """Classify a free-text query and route to the appropriate handler."""
    query = request.form.get("q", "").strip() or request.form.get("query", "").strip()
    if not query:
        return '<div class="error">Please type a question or search term.</div>', 400

    # Quick-action modifier (re-generate with overlay instructions)
    modifier = request.form.get("modifier", "").strip() or None

    # If modifier is set, skip classification — go straight to draft_response
    if modifier:
        _user_mod = g.get("user")
        if _user_mod and not has_tier(_user_mod, 'beta'):
            teaser_html = render_template(
                "fragments/tier_gate_teaser_inline.html",
                required_tier='beta',
                current_tier=_user_mod.get('subscription_tier', 'free'),
                user=_user_mod,
            )
            return teaser_html, 200
        return _ask_draft_response(query, {"query": query}, modifier=modifier)

    # Smart Analyze button: analyze=1 is always posted by the button,
    # so route to analyze_project regardless of description content.
    if request.form.get("analyze") == "1":
        return _ask_analyze_prefill(query, {})

    # Classify intent
    result = classify_intent(query, [n for n in NEIGHBORHOODS if n])
    intent = result.intent
    entities = result.entities

    # --- NLP enhancement: if intent router missed an address in a natural
    # language query, use parse_search_query to extract street/neighborhood.
    # Merge extracted fields into entities so the right handler is triggered.
    if intent not in ("lookup_permit", "search_complaint", "search_parcel", "validate_plans"):
        nlp = parse_search_query(query)
        if nlp.get("street_number") and nlp.get("street_name"):
            if intent not in ("search_address",):
                # Upgrade intent to address search when NLP found an address
                intent = "search_address"
            if not entities.get("street_number"):
                entities["street_number"] = nlp["street_number"]
            if not entities.get("street_name"):
                entities["street_name"] = nlp["street_name"]
        # Merge neighborhood into analyze_project entities if not already present
        if nlp.get("neighborhood") and intent == "analyze_project":
            if not entities.get("neighborhood"):
                entities["neighborhood"] = nlp["neighborhood"]

    # Allow explicit draft mode override via form field
    if request.form.get("draft") == "1" and intent not in (
        "lookup_permit", "search_complaint", "search_address",
        "search_parcel", "search_person", "validate_plans",
    ):
        intent = "draft_response"
        entities = {"query": query}

    # Tier gate: AI synthesis intents require beta or higher.
    # Data lookup intents (permit, address, complaint, parcel, person) pass through freely.
    _AI_INTENTS = {"draft_response", "analyze_project", "general_question"}
    _effective_intent = intent if intent in (
        "lookup_permit", "search_complaint", "search_address",
        "search_parcel", "search_person", "validate_plans",
    ) else "ai_synthesis"
    if _effective_intent == "ai_synthesis":
        user = g.get("user")
        if user and not has_tier(user, 'beta'):
            teaser_html = render_template(
                "fragments/tier_gate_teaser_inline.html",
                required_tier='beta',
                current_tier=user.get('subscription_tier', 'free'),
                user=user,
            )
            return teaser_html, 200

    try:
        if intent == "lookup_permit":
            return _ask_permit_lookup(query, entities)
        elif intent == "search_complaint":
            return _ask_complaint_search(query, entities)
        elif intent == "search_address":
            return _ask_address_search(query, entities)
        elif intent == "search_parcel":
            return _ask_parcel_search(query, entities)
        elif intent == "search_person":
            return _ask_person_search(query, entities)
        elif intent == "analyze_project":
            return _ask_analyze_prefill(query, entities)
        elif intent == "validate_plans":
            return _ask_validate_reveal(query)
        elif intent == "draft_response":
            return _ask_draft_response(query, entities)
        else:
            return _ask_general_question(query, entities)
    except Exception as e:
        logging.error("Error in /ask handler for intent=%s: %s", intent, e)
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html=f'<div class="error">Something went wrong: {e}</div>',
        )


# ---------------------------------------------------------------------------
# Helper functions for /ask sub-handlers
# ---------------------------------------------------------------------------

def _watch_context(watch_data: dict) -> dict:
    """Build template context for watch button (check existing watch status)."""
    ctx = {"watch_data": watch_data}
    if g.user:
        from web.auth import check_watch
        # Exclude watch_type and label from kwargs — they're positional or not DB fields
        kw = {k: v for k, v in watch_data.items() if k not in ("watch_type", "label")}
        existing = check_watch(g.user["user_id"], watch_data["watch_type"], **kw)
        if existing:
            ctx["existing_watch_id"] = existing["watch_id"]
    return ctx


def _get_severity_for_permit(permit_number: str) -> dict | None:
    """Query severity_cache for a permit, compute + store if missing.

    Returns dict with 'score', 'tier', 'drivers' keys, or None on failure.
    Failures are swallowed — severity never breaks search.
    """
    try:
        import json as _json
        from src.db import get_connection, BACKEND, query as db_query

        # Check cache first
        _ph = "%s" if BACKEND == "postgres" else "?"
        cached = db_query(
            f"SELECT score, tier, drivers FROM severity_cache WHERE permit_number = {_ph}",
            (permit_number,),
        )
        if cached:
            drivers_raw = cached[0][2]
            drivers = _json.loads(drivers_raw) if drivers_raw else {}
            return {"score": cached[0][0], "tier": cached[0][1], "drivers": drivers}

        # Cache miss — fetch permit data and compute
        permit_rows = db_query(
            f"SELECT permit_number, status, permit_type_definition, description, "
            f"filed_date, issued_date, completed_date, status_date, "
            f"estimated_cost, revised_cost "
            f"FROM permits WHERE permit_number = {_ph}",
            (permit_number,),
        )
        if not permit_rows:
            return None

        row = permit_rows[0]
        # Count inspections for this permit
        insp_rows = db_query(
            f"SELECT COUNT(*) FROM inspections WHERE reference_number = {_ph}",
            (permit_number,),
        )
        insp_count = insp_rows[0][0] if insp_rows else 0

        from src.severity import PermitInput, score_permit
        permit_input = PermitInput.from_dict(
            {
                "permit_number": row[0],
                "status": row[1] or "",
                "permit_type_definition": row[2] or "",
                "description": row[3] or "",
                "filed_date": row[4],
                "issued_date": row[5],
                "completed_date": row[6],
                "status_date": row[7],
                "estimated_cost": row[8],
                "revised_cost": row[9],
            },
            inspection_count=insp_count,
        )
        result = score_permit(permit_input)
        drivers_json = _json.dumps({
            dim: vals["score"] for dim, vals in result.dimensions.items()
        })

        # Upsert into cache
        try:
            conn = get_connection()
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO severity_cache (permit_number, score, tier, drivers) "
                            "VALUES (%s, %s, %s, %s) "
                            "ON CONFLICT (permit_number) DO UPDATE "
                            "SET score=EXCLUDED.score, tier=EXCLUDED.tier, "
                            "    drivers=EXCLUDED.drivers, computed_at=NOW()",
                            (permit_number, result.score, result.tier, drivers_json),
                        )
                        conn.commit()
                else:
                    conn.execute(
                        "INSERT OR REPLACE INTO severity_cache "
                        "(permit_number, score, tier, drivers) VALUES (?, ?, ?, ?)",
                        [permit_number, result.score, result.tier, drivers_json],
                    )
            finally:
                conn.close()
        except Exception as cache_err:
            logging.debug("severity_cache upsert failed: %s", cache_err)

        return {
            "score": result.score,
            "tier": result.tier,
            "drivers": result.dimensions,
        }
    except Exception as e:
        logging.debug("_get_severity_for_permit failed for %s: %s", permit_number, e)
        return None


def _ask_permit_lookup(query: str, entities: dict) -> str:
    """Handle permit number lookup."""
    permit_num = entities.get("permit_number")
    try:
        result_md = run_async(permit_lookup(permit_number=permit_num))
    except Exception as e:
        logging.warning("permit_lookup failed for permit %s: %s", permit_num, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "permit",
        "permit_number": permit_num,
        "label": f"Permit #{permit_num}",
    }
    # Enrich with severity data (cache hit or compute on-demand)
    severity = None
    if permit_num:
        severity = _get_severity_for_permit(permit_num)
    return render_template(
        "search_results.html",
        query_echo=f"Permit #{permit_num}",
        result_html=md_to_html(result_md),
        severity_score=severity["score"] if severity else None,
        severity_tier=severity["tier"] if severity else None,
        **_watch_context(watch_data),
    )


def _ask_complaint_search(query: str, entities: dict) -> str:
    """Handle complaint/violation/enforcement search."""
    complaint_number = entities.get("complaint_number")
    street_number = entities.get("street_number")
    street_name = entities.get("street_name")
    block = entities.get("block")
    lot = entities.get("lot")

    # Build full address string for display and filtering
    if street_number and street_name:
        full_address = f"{street_number} {street_name}"
    elif street_name:
        full_address = street_name
    else:
        full_address = None

    # Run both complaints and violations searches in parallel via the same
    # run_async helper. Build combined results.
    parts = []

    # Search complaints
    try:
        complaints_md = run_async(search_complaints(
            complaint_number=complaint_number,
            address=street_name,
            street_number=street_number,
            block=block,
            lot=lot,
        ))
        parts.append("## Complaints\n\n" + complaints_md)
    except Exception as e:
        logging.warning("search_complaints failed: %s", e)

    # Search violations
    try:
        violations_md = run_async(search_violations(
            complaint_number=complaint_number,
            address=street_name,
            street_number=street_number,
            block=block,
            lot=lot,
        ))
        parts.append("## Violations (NOVs)\n\n" + violations_md)
    except Exception as e:
        logging.warning("search_violations failed: %s", e)

    if not parts:
        return _ask_general_question(query, entities)

    combined_md = "\n\n---\n\n".join(parts)

    # Build label for display
    if complaint_number:
        label = f"Complaint #{complaint_number}"
    elif full_address:
        label = f"Complaints at {full_address}"
    elif block and lot:
        label = f"Complaints at Block {block}, Lot {lot}"
    else:
        label = "Complaint search"

    # Build watch data for address or parcel
    watch_data = {}
    if block and lot:
        watch_data = {
            "watch_type": "parcel",
            "block": block,
            "lot": lot,
            "label": f"Block {block}, Lot {lot}",
        }
    elif street_name:
        watch_data = {
            "watch_type": "address",
            "street_name": street_name,
            "label": f"Near {full_address or street_name}",
        }

    ctx = {}
    if watch_data:
        ctx = _watch_context(watch_data)

    report_url = f"/report/{block}/{lot}" if block and lot else None
    street_address = full_address or (f"Block {block}, Lot {lot}" if block and lot else None)

    return render_template(
        "search_results.html",
        query_echo=label,
        result_html=md_to_html(combined_md),
        report_url=report_url,
        street_address=street_address,
        show_quick_actions=False,
        **ctx,
    )


def _get_primary_permit_context(street_number: str, street_name: str) -> dict | None:
    """Get the most recent permit at an address for Analyze button pre-fill."""
    try:
        from src.db import query
        ctx_base = street_name.split()[0] if street_name else ""
        ctx_nospace = ctx_base.replace(' ', '')
        rows = query(
            "SELECT description, permit_type_definition, estimated_cost, "
            "       revised_cost, proposed_use, adu, neighborhood "
            "FROM permits "
            "WHERE street_number = %s "
            "  AND ("
            "    UPPER(street_name) = UPPER(%s)"
            "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
            "  ) "
            "ORDER BY filed_date DESC LIMIT 1",
            (street_number, ctx_base, ctx_nospace),
        )
        if not rows:
            return None
        desc, ptd, cost, revised_cost, proposed_use, adu, neighborhood = rows[0]
        effective_cost = revised_cost or cost
        # Build a short human label for the button
        label_parts = []
        if ptd:
            short = ptd.replace("Additions Alterations or Repairs", "Additions + Repairs")
            short = short.replace("New Construction Wood Frame", "New Construction")
            label_parts.append(short[:35])
        if effective_cost:
            label_parts.append(
                f"${effective_cost/1000:.0f}K" if effective_cost < 1_000_000
                else f"${effective_cost/1_000_000:.1f}M"
            )
        label = " · ".join(label_parts) if label_parts else "Active Permit"
        return {
            "description": (desc or ptd or "")[:200],
            "estimated_cost": effective_cost,
            "neighborhood": neighborhood,
            "label": label,
        }
    except Exception as e:
        logging.debug("_get_primary_permit_context failed: %s", e)
        return None


def _get_open_violation_counts(block: str, lot: str) -> dict | None:
    """Count open violations + complaints at a parcel. Returns None if tables empty."""
    try:
        from src.db import query
        # Check table is populated first — return None if ingest not yet done
        check = query("SELECT COUNT(*) FROM violations LIMIT 1", ())
        if not check or check[0][0] == 0:
            return None
        v_rows = query(
            "SELECT COUNT(*) FROM violations "
            "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
            (block, lot),
        )
        c_rows = query(
            "SELECT COUNT(*) FROM complaints "
            "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
            (block, lot),
        )
        open_v = v_rows[0][0] if v_rows else 0
        open_c = c_rows[0][0] if c_rows else 0
        return {"open_violations": open_v, "open_complaints": open_c, "total": open_v + open_c}
    except Exception as e:
        logging.debug("_get_open_violation_counts failed: %s", e)
        return None


def _get_active_businesses(street_number: str, street_name: str) -> list:
    """Get active registered businesses at this address. Returns [] if table empty."""
    try:
        from src.db import query
        check = query("SELECT COUNT(*) FROM businesses LIMIT 1", ())
        if not check or check[0][0] == 0:
            return []
        rows = query(
            "SELECT dba_name, ownership_name, dba_start_date, "
            "       parking_tax, transient_occupancy_tax "
            "FROM businesses "
            "WHERE full_business_address ILIKE %s "
            "  AND location_end_date IS NULL "
            "ORDER BY dba_start_date DESC LIMIT 5",
            (f"%{street_number}%{street_name.split()[0]}%",),
        )
        results = []
        for dba, ownership, start, parking, tot in rows:
            name = (dba or ownership or "").strip()
            if not name:
                continue
            since = str(start or "")[:4] or "?"
            type_flag = None
            if parking == "Y":
                type_flag = "\U0001f17f\ufe0f Parking"
            elif tot == "Y":
                type_flag = "\U0001f3e8 Short-term rental"
            results.append({"name": name, "since": since, "type_flag": type_flag})
        return results
    except Exception as e:
        logging.debug("_get_active_businesses failed: %s", e)
        return []


def _get_address_intel(
    block: str | None = None,
    lot: str | None = None,
    street_number: str | None = None,
    street_name: str | None = None,
) -> dict:
    """Assemble property intelligence panel data.

    Each section is independently fault-tolerant — one failure
    doesn't prevent the others from returning data.
    """
    from src.db import query as db_query

    result = {
        "open_violations": None,
        "open_complaints": None,
        "enforcement_total": None,
        "business_count": 0,
        "active_businesses": [],
        "total_permits": None,
        "active_permits": None,
        "latest_permit_type": None,
        # Routing progress for primary active permit
        "routing_total": None,
        "routing_complete": None,
        "routing_latest_station": None,
        "routing_latest_date": None,
        "routing_latest_result": None,
    }

    # -- Section 1: Violations (needs block + lot) --
    open_v = 0
    if block and lot:
        try:
            v_rows = db_query(
                "SELECT COUNT(*) FROM violations "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            open_v = v_rows[0][0] if v_rows else 0
            result["open_violations"] = open_v
        except Exception as e:
            logging.debug("_get_address_intel violations failed: %s", e)

    # -- Section 2: Complaints (needs block + lot) --
    open_c = 0
    if block and lot:
        try:
            c_rows = db_query(
                "SELECT COUNT(*) FROM complaints "
                "WHERE block = %s AND lot = %s AND LOWER(status) = 'open'",
                (block, lot),
            )
            open_c = c_rows[0][0] if c_rows else 0
            result["open_complaints"] = open_c
        except Exception as e:
            logging.debug("_get_address_intel complaints failed: %s", e)

    if result["open_violations"] is not None or result["open_complaints"] is not None:
        result["enforcement_total"] = (result["open_violations"] or 0) + (result["open_complaints"] or 0)

    # -- Section 3: Businesses (needs street address) --
    if street_number and street_name:
        try:
            biz_rows = db_query(
                "SELECT dba_name, ownership_name, dba_start_date, "
                "       parking_tax, transient_occupancy_tax "
                "FROM businesses "
                "WHERE full_business_address ILIKE %s "
                "  AND location_end_date IS NULL "
                "ORDER BY dba_start_date DESC LIMIT 5",
                (f"%{street_number}%{street_name.split()[0]}%",),
            )
            for dba, ownership, start, parking, tot in biz_rows:
                name = (dba or ownership or "").strip()
                if not name:
                    continue
                since = str(start or "")[:4] or "?"
                type_flag = None
                if parking == "Y":
                    type_flag = "\U0001f17f\ufe0f Parking"
                elif tot == "Y":
                    type_flag = "\U0001f3e8 Short-term rental"
                result["active_businesses"].append(
                    {"name": name, "since": since, "type_flag": type_flag}
                )
            result["business_count"] = len(result["active_businesses"])
        except Exception as e:
            logging.debug("_get_address_intel businesses failed: %s", e)

    # -- Section 4: Permit stats (works with address OR block+lot) --
    try:
        if street_number and street_name:
            # Exact match on street name (no substring matching)
            base_name = street_name.split()[0] if street_name else ""
            nospace_name = base_name.replace(' ', '')
            count_rows = db_query(
                "SELECT COUNT(*), "
                "       COUNT(*) FILTER (WHERE UPPER(status) IN "
                "           ('ISSUED', 'FILED', 'PLANCHECK', 'REINSTATED')) "
                "FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  )",
                (street_number, base_name, nospace_name),
            )
        elif block and lot:
            count_rows = db_query(
                "SELECT COUNT(*), "
                "       COUNT(*) FILTER (WHERE UPPER(status) IN "
                "           ('ISSUED', 'FILED', 'PLANCHECK', 'REINSTATED')) "
                "FROM permits "
                "WHERE block = %s AND lot = %s",
                (block, lot),
            )
        else:
            count_rows = None

        if count_rows and count_rows[0]:
            result["total_permits"] = count_rows[0][0]
            result["active_permits"] = count_rows[0][1]
    except Exception as e:
        logging.debug("_get_address_intel permit counts failed: %s", e)

    try:
        if street_number and street_name:
            base_name2 = street_name.split()[0] if street_name else ""
            nospace_name2 = base_name2.replace(' ', '')
            latest_rows = db_query(
                "SELECT permit_type_definition FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "ORDER BY filed_date DESC LIMIT 1",
                (street_number, base_name2, nospace_name2),
            )
        elif block and lot:
            latest_rows = db_query(
                "SELECT permit_type_definition FROM permits "
                "WHERE block = %s AND lot = %s "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
        else:
            latest_rows = None

        if latest_rows and latest_rows[0]:
            ptd = latest_rows[0][0] or ""
            ptd = ptd.replace("Additions Alterations or Repairs", "Additions + Repairs")
            ptd = ptd.replace("New Construction Wood Frame", "New Construction")
            result["latest_permit_type"] = ptd[:40] if ptd else None
    except Exception as e:
        logging.debug("_get_address_intel latest permit failed: %s", e)

    # -- Section 5: Routing progress for primary active permit --
    try:
        # Find the most recently filed active permit at this address
        primary_pnum = None
        if street_number and street_name:
            rp_base = street_name.split()[0] if street_name else ""
            rp_nospace = rp_base.replace(' ', '')
            pn_rows = db_query(
                "SELECT permit_number FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "  AND UPPER(status) IN ('FILED', 'PLANCHECK') "
                "ORDER BY filed_date DESC LIMIT 1",
                (street_number, rp_base, rp_nospace),
            )
        elif block and lot:
            pn_rows = db_query(
                "SELECT permit_number FROM permits "
                "WHERE block = %s AND lot = %s "
                "  AND UPPER(status) IN ('FILED', 'PLANCHECK') "
                "ORDER BY filed_date DESC LIMIT 1",
                (block, lot),
            )
        else:
            pn_rows = None

        if pn_rows and pn_rows[0]:
            primary_pnum = pn_rows[0][0]

        if primary_pnum:
            # Get the latest addenda_number for this permit
            latest_rev = db_query(
                "SELECT MAX(addenda_number) FROM addenda "
                "WHERE application_number = %s",
                (primary_pnum,),
            )
            rev_num = latest_rev[0][0] if latest_rev and latest_rev[0][0] is not None else None

            if rev_num is not None:
                # Count total steps and completed steps for this revision
                routing_rows = db_query(
                    "SELECT COUNT(*), "
                    "       COUNT(*) FILTER (WHERE finish_date IS NOT NULL) "
                    "FROM addenda "
                    "WHERE application_number = %s AND addenda_number = %s",
                    (primary_pnum, rev_num),
                )
                if routing_rows and routing_rows[0]:
                    result["routing_total"] = routing_rows[0][0]
                    result["routing_complete"] = routing_rows[0][1]

                # Get the most recent completed step
                latest_step = db_query(
                    "SELECT station, finish_date, review_results "
                    "FROM addenda "
                    "WHERE application_number = %s AND addenda_number = %s "
                    "  AND finish_date IS NOT NULL "
                    "ORDER BY finish_date DESC LIMIT 1",
                    (primary_pnum, rev_num),
                )
                if latest_step and latest_step[0]:
                    result["routing_latest_station"] = latest_step[0][0]
                    fd = latest_step[0][1]
                    result["routing_latest_date"] = str(fd)[:10] if fd else None
                    result["routing_latest_result"] = latest_step[0][2]
    except Exception as e:
        logging.debug("_get_address_intel routing progress failed: %s", e)

    return result


def _ask_address_search(query: str, entities: dict) -> str:
    """Handle address-based permit search."""
    street_number = entities.get("street_number")
    street_name = entities.get("street_name")
    try:
        result_md = run_async(permit_lookup(
            street_number=street_number,
            street_name=street_name,
        ))
    except Exception as e:
        logging.warning("permit_lookup failed for address %s %s: %s",
                        street_number, street_name, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "address",
        "street_number": street_number,
        "street_name": street_name,
        "label": f"{street_number} {street_name}",
    }
    # Primary address prompt: show if logged in and no primary address set yet
    show_primary_prompt = bool(g.user and not g.user.get("primary_street_number"))
    # Resolve block/lot for property report link
    report_url = None
    try:
        from src.db import query as db_query
        from src.tools.permit_lookup import _strip_suffix
        bl = _resolve_block_lot(street_number, street_name)
        # Fallback: if _resolve_block_lot failed but permits exist, try a
        # broader query (just street_number + block/lot NOT NULL)
        if not bl:
            base_name, _sfx = _strip_suffix(street_name)
            fb_nospace = base_name.replace(' ', '')
            rows = db_query(
                "SELECT block, lot FROM permits "
                "WHERE street_number = %s "
                "  AND ("
                "    UPPER(street_name) = UPPER(%s)"
                "    OR REPLACE(UPPER(COALESCE(street_name, '')), ' ', '') = UPPER(%s)"
                "  ) "
                "  AND block IS NOT NULL AND lot IS NOT NULL "
                "LIMIT 1",
                (street_number, base_name, fb_nospace),
            )
            if rows:
                bl = (rows[0][0], rows[0][1])
                logging.info("_resolve_block_lot fallback matched: %s %s -> %s/%s",
                             street_number, street_name, bl[0], bl[1])
        if bl:
            report_url = f"/report/{bl[0]}/{bl[1]}"
    except Exception as e:
        logging.warning("Block/lot resolution failed for %s %s: %s",
                        street_number, street_name, e)
    # Detect no-results to show helpful next-step CTAs
    no_results = _is_no_results(result_md)
    street_address = f"{street_number} {street_name}" if street_number and street_name else None
    # Enrich Quick Actions with live context
    project_context = None
    address_intel = None
    if not no_results:
        project_context = _get_primary_permit_context(street_number, street_name)
        address_intel = _get_address_intel(
            block=bl[0] if bl else None,
            lot=bl[1] if bl else None,
            street_number=street_number,
            street_name=street_name,
        )
        # Sync badge count with MCP tool's actual permit count (which
        # includes parcel merge + historical lot discovery)
        if address_intel:
            import re
            _m = re.search(r'Found \*\*(\d+)\*\* permits', result_md)
            if _m:
                address_intel["total_permits"] = int(_m.group(1))
    # Extract for backward compat with Quick Actions buttons
    violation_counts = None
    active_businesses = []
    if address_intel:
        if address_intel["enforcement_total"] is not None:
            violation_counts = {
                "open_violations": address_intel["open_violations"] or 0,
                "open_complaints": address_intel["open_complaints"] or 0,
                "total": address_intel["enforcement_total"],
            }
        active_businesses = address_intel["active_businesses"]
    return render_template(
        "search_results.html",
        query_echo=f"{street_number} {street_name}",
        result_html=md_to_html(result_md),
        show_primary_prompt=show_primary_prompt,
        prompt_street_number=street_number,
        prompt_street_name=street_name,
        report_url=report_url,
        street_address=street_address,
        no_results=no_results,
        no_results_address=f"{street_number} {street_name}" if no_results else None,
        project_context=project_context,
        violation_counts=violation_counts,
        active_businesses=active_businesses,
        address_intel=address_intel,
        show_quick_actions=True,
        **_watch_context(watch_data),
    )


def _ask_parcel_search(query: str, entities: dict) -> str:
    """Handle block/lot parcel search."""
    block = entities.get("block")
    lot = entities.get("lot")
    try:
        result_md = run_async(permit_lookup(block=block, lot=lot))
    except Exception as e:
        logging.warning("permit_lookup failed for parcel %s/%s: %s", block, lot, e)
        return _ask_general_question(query, entities)
    watch_data = {
        "watch_type": "parcel",
        "block": block,
        "lot": lot,
        "label": f"Block {block}, Lot {lot}",
    }
    report_url = f"/report/{block}/{lot}" if block and lot else None
    street_address = f"Block {block}, Lot {lot}" if block and lot else None
    # Property intel — block/lot only, no street address for business lookup
    address_intel = None
    violation_counts = None
    if block and lot:
        address_intel = _get_address_intel(block=block, lot=lot)
        # Sync badge count with MCP tool's actual permit count
        if address_intel:
            import re
            _m = re.search(r'Found \*\*(\d+)\*\* permits', result_md)
            if _m:
                address_intel["total_permits"] = int(_m.group(1))
        if address_intel and address_intel["enforcement_total"] is not None:
            violation_counts = {
                "open_violations": address_intel["open_violations"] or 0,
                "open_complaints": address_intel["open_complaints"] or 0,
                "total": address_intel["enforcement_total"],
            }
    return render_template(
        "search_results.html",
        query_echo=f"Block {block}, Lot {lot}",
        result_html=md_to_html(result_md),
        report_url=report_url,
        street_address=street_address,
        project_context=None,
        violation_counts=violation_counts,
        active_businesses=[],
        address_intel=address_intel,
        show_quick_actions=True,
        **_watch_context(watch_data),
    )


def _ask_person_search(query: str, entities: dict) -> str:
    """Handle person/company name search."""
    name = entities.get("person_name", "")
    role = entities.get("role")
    try:
        result_md = run_async(search_entity(name=name, entity_type=role))
    except Exception as e:
        logging.warning("search_entity failed for %s: %s", name, e)
        return _ask_general_question(query, entities)
    # For person searches, we can't easily get entity_id without a DB lookup,
    # so we watch by name (general_question fallback — entity watching is best
    # done from the detailed entity page in a future iteration)
    watch_data = {
        "watch_type": "entity",
        "label": f"{name}" + (f" ({role})" if role else ""),
    }
    return render_template(
        "search_results.html",
        query_echo=f"Search: {name}" + (f" ({role})" if role else ""),
        result_html=md_to_html(result_md),
        **_watch_context(watch_data),
    )


def _ask_analyze_prefill(query: str, entities: dict) -> str:
    """Pre-fill the analyze form and reveal it."""
    # Accept real permit fields posted directly from the smart Analyze button
    cost_raw = request.form.get("estimated_cost", "")
    neighborhood_raw = request.form.get("neighborhood", "")
    address_raw = request.form.get("address", "")
    prefill_data = {
        "description": entities.get("description", query),
        "estimated_cost": float(cost_raw) if cost_raw else entities.get("estimated_cost"),
        "square_footage": entities.get("square_footage"),
        "neighborhood": neighborhood_raw or entities.get("neighborhood"),
        "address": address_raw or entities.get("address"),
    }
    # Remove None/empty values for cleaner JSON
    prefill_data = {k: v for k, v in prefill_data.items() if v}
    return render_template(
        "search_prefill.html",
        prefill_json=json.dumps(prefill_data),
    )


def _ask_validate_reveal(query: str) -> str:
    """Reveal the validation section."""
    return render_template("search_reveal.html", section="validate")


def _ask_draft_response(query: str, entities: dict, modifier: str | None = None) -> str:
    """Generate an AI-synthesized response to a conversational question.

    Uses RAG retrieval for context, then sends to Claude for a natural,
    helpful response. Falls back to raw RAG display if AI is unavailable.

    Args:
        modifier: Optional quick-action modifier (get_meeting, cite_sources, shorter, more_detail)
    """
    effective_query = entities.get("query", query)

    # Try RAG-augmented retrieval for context
    rag_results = _try_rag_retrieval(effective_query)
    if not rag_results:
        return _ask_general_question(query, entities)

    role = _get_user_response_role()

    # Assemble context from RAG results
    seen_sources = set()
    context_parts = []
    references = []
    source_details = []

    for r in rag_results:
        source_file = r.get("source_file", "")
        source_section = r.get("source_section", "")
        source_key = f"{source_file}:{source_section}"
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        content = r.get("content", "")
        label = _build_source_label(source_file, source_section)
        context_parts.append(f"[{label}]\n{content}")
        if label and label not in references:
            references.append(label)
        source_details.append({
            "source_label": label,
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })

    if not context_parts:
        return _ask_general_question(query, entities)

    # Synthesize with Claude
    ai_response = _synthesize_with_ai(
        effective_query, "\n\n---\n\n".join(context_parts), role, modifier=modifier
    )

    if ai_response:
        return render_template(
            "draft_response.html",
            query=query,
            ai_response_html=md_to_html(ai_response),
            references=references[:5],
            source_details=source_details,
            role=role,
            is_expert=_is_expert_user(),
        )

    # Fallback: show raw RAG results if AI synthesis fails
    cleaned_results = []
    for r in rag_results:
        sf = r.get("source_file", "")
        ss = r.get("source_section", "")
        sk = f"{sf}:{ss}"
        content = _clean_chunk_content(r.get("content", ""), sf)
        label = _build_source_label(sf, ss)
        cleaned_results.append({
            "content_html": md_to_html(content),
            "source_label": label,
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })
    return render_template(
        "draft_response.html",
        query=query,
        results=cleaned_results,
        references=references[:5],
        role=role,
        is_expert=_is_expert_user(),
    )


def _synthesize_with_ai(
    query: str, rag_context: str, role: str, modifier: str | None = None,
) -> str | None:
    """Call Claude to synthesize a conversational response from RAG context.

    Returns the AI-generated markdown response, or None if unavailable.
    Injects user's voice_style preferences if set.

    Args:
        modifier: Optional quick-action modifier that overrides default guidelines.
            Supported: get_meeting, cite_sources, shorter, more_detail
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    if role == "professional":
        tone = (
            "You are Amy, an expert SF permit expeditor. Respond professionally "
            "but warmly, as if advising a colleague. Be specific about code "
            "sections, required forms, and practical next steps."
        )
    elif role == "homeowner":
        tone = (
            "You are Amy, a friendly SF permit expert helping a homeowner. "
            "Explain things simply and clearly, avoiding jargon. Focus on "
            "what they need to do and what to expect."
        )
    else:
        tone = (
            "You are Amy, an SF building permit expert. Provide a clear, "
            "helpful response. Include specific code references and practical "
            "guidance where relevant."
        )

    # Inject user's voice & style preferences (macro instructions)
    voice_style = ""
    try:
        if g.user and g.user.get("voice_style"):
            voice_style = g.user["voice_style"]
    except RuntimeError:
        pass  # Outside request context

    style_block = ""
    if voice_style:
        style_block = (
            f"\n\nIMPORTANT — The user has set these style preferences. "
            f"Follow them closely:\n{voice_style}\n"
        )

    # Quick-action modifier overrides
    modifier_instructions = ""
    if modifier == "get_meeting":
        modifier_instructions = (
            "\n\nOVERRIDE: Keep the response brief (2-3 sentences max). "
            "Give one concrete helpful fact, then warmly suggest scheduling "
            "a call to discuss in detail. End with something like 'Would you "
            "like to set up a quick call to walk through this?'\n"
        )
    elif modifier == "shorter":
        modifier_instructions = (
            "\n\nOVERRIDE: Maximum 100 words. Be direct and concise. "
            "No pleasantries, just the key facts and one next step.\n"
        )
    elif modifier == "more_detail":
        modifier_instructions = (
            "\n\nOVERRIDE: Provide a thorough 400-600 word response with full details, "
            "timelines, fees, and step-by-step guidance. Include specific code section "
            "references for every claim. Use these rules for citations:\n"
            "- SF Planning Code sections: format as markdown links, e.g. "
            "[Planning Code \u00a7207](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/0-0-0-1)\n"
            "- SF Building Code (SFBC) sections: format as markdown links, e.g. "
            "[SFBC \u00a73301](https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-1)\n"
            "- CBC, Title 24, ASCE 7: use inline citations only, e.g. (CBC \u00a7706.1) \u2014 no links, these are paywalled.\n"
            "Be comprehensive and cite sources inline throughout, not just at the end.\n"
        )

    system_prompt = (
        f"{tone}{style_block}{modifier_instructions}\n\n"
        "Use the following knowledge base context to answer the question. "
        "If the context doesn't fully answer the question, say what you know "
        "and note what you're less certain about.\n\n"
        "Guidelines:\n"
        "- Start with a brief, direct summary (2-3 sentences) answering their core question\n"
        "- Then provide relevant details and next steps\n"
        "- Cite specific code sections (CBC, Planning Code, SFBC) when applicable\n"
        "- Keep the response concise \u2014 aim for 200-400 words\n"
        "- Use markdown formatting (bold, bullets, headers) for readability\n"
        "- End with a clear next-step recommendation\n"
        "- Do NOT say 'Based on the context provided' or reference the retrieval system\n"
    )

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Knowledge base context:\n{rag_context}\n\n"
                        f"---\n\nQuestion from user:\n{query}"
                    ),
                }
            ],
        )
        if response.content and response.content[0].type == "text":
            # SESSION B: log cost
            try:
                from web.cost_tracking import log_api_call, ensure_schema
                ensure_schema()
                user_id = g.user["user_id"] if (hasattr(g, "user") and g.user) else None
                log_api_call(
                    endpoint="/ask",
                    model="claude-sonnet-4-20250514",
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    user_id=user_id,
                )
            except Exception:
                pass
            return response.content[0].text
        return None
    except Exception as e:
        logging.warning("AI synthesis failed: %s", e)
        return None


def _ask_general_question(query: str, entities: dict) -> str:
    """Answer a general question using RAG retrieval (with keyword fallback)."""
    effective_query = entities.get("query", query)

    # Try RAG-augmented retrieval first
    rag_results = _try_rag_retrieval(effective_query)
    if rag_results:
        # Try AI synthesis first, fall back to raw display
        role = _get_user_response_role()
        context_parts = []
        references = []
        source_details = []
        seen = set()
        for r in rag_results:
            sf = r.get("source_file", "")
            ss = r.get("source_section", "")
            sk = f"{sf}:{ss}"
            if sk in seen:
                continue
            seen.add(sk)
            label = _build_source_label(sf, ss)
            context_parts.append(f"[{label}]\n{r.get('content', '')}")
            if label and label not in references:
                references.append(label)
            source_details.append({
                "source_label": label,
                "score": r.get("final_score", 0),
                "source_tier": r.get("source_tier", ""),
            })
        ai_response = _synthesize_with_ai(effective_query, "\n\n---\n\n".join(context_parts), role)
        if ai_response:
            return render_template(
                "draft_response.html",
                query=query,
                ai_response_html=md_to_html(ai_response),
                references=references[:5],
                source_details=source_details,
                role=role,
                is_expert=_is_expert_user(),
            )
        # Fall back to raw RAG display
        return _render_rag_results(query, rag_results)

    # Fallback: keyword-only matching from KnowledgeBase
    kb = get_knowledge_base()
    scored = kb.match_concepts_scored(effective_query)

    if not scored:
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html=(
                '<div class="info">I don\'t have a specific answer for that yet. '
                'Try searching by permit number, address, or describing your project.</div>'
            ),
        )

    # Build an answer from the top matched concepts
    parts = []
    concepts = kb.semantic_index.get("concepts", {})
    for concept_name, score in scored[:3]:
        concept = concepts.get(concept_name, {})
        desc = concept.get("description", "")
        if desc:
            parts.append(f"**{concept_name.replace('_', ' ').title()}**: {desc}")

    result_html = md_to_html("\n\n".join(parts)) if parts else (
        '<div class="info">No matching knowledge found for that query.</div>'
    )
    return render_template(
        "search_results.html",
        query_echo=query,
        result_html=result_html,
    )


# ---------------------------------------------------------------------------
# RAG helpers
# ---------------------------------------------------------------------------

def _try_rag_retrieval(query: str) -> list[dict] | None:
    """Attempt RAG retrieval. Returns results or None if unavailable."""
    try:
        from src.rag.retrieval import retrieve
        results = retrieve(query, top_k=5)
        # Filter out keyword-only fallback results (those have similarity=0)
        real_results = [r for r in results if r.get("similarity", 0) > 0]
        return real_results if real_results else None
    except Exception as e:
        logging.debug("RAG retrieval unavailable: %s", e)
        return None


def _clean_chunk_content(content: str, source_file: str = "") -> str:
    """Clean raw RAG chunk content for human-readable display.

    Handles tier1 JSON-style key:value content, tier2 raw text,
    and expert notes.
    """
    lines = content.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Strip [filename] prefixes like "[epr-requirements]"
        stripped = re.sub(r'^\[[\w\-\.]+\]\s*', '', stripped)
        # Convert "key: value" (YAML-style) to bold key
        m = re.match(r'^(\w[\w_\s]{1,30}?):\s+(.+)$', stripped)
        if m:
            key = m.group(1).replace("_", " ").strip().title()
            val = m.group(2).strip()
            # Special handling for quote fields
            if key.lower() == "quote":
                cleaned.append(f'> "{val}"')
            else:
                cleaned.append(f"**{key}**: {val}")
        elif stripped.startswith("- ") or stripped.startswith("* "):
            cleaned.append(stripped)
        elif stripped.startswith('"') and stripped.endswith('"'):
            cleaned.append(f"> {stripped}")
        else:
            cleaned.append(stripped)
    return "\n\n".join(cleaned)


def _get_user_response_role() -> str:
    """Determine response role based on current user."""
    if not g.user:
        return "general"
    if g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant"):
        return "professional"
    return "homeowner"


def _is_expert_user() -> bool:
    """Check if current user can add expert notes."""
    return bool(
        g.user
        and (g.user.get("is_admin") or g.user.get("role") in ("admin", "consultant"))
    )


def _build_source_label(source_file: str, source_section: str) -> str:
    """Build a readable source label from file/section names."""
    label = source_file.replace(".json", "").replace(".txt", "")
    label = label.replace("-", " ").replace("_", " ").title()
    if source_section and source_section not in source_file:
        section = source_section.replace("_", " ").replace("-", " ").title()
        label = f"{label} \u203a {section}"
    return label


def _render_rag_results(query: str, results: list[dict]) -> str:
    """Render RAG retrieval results as a clean knowledge answer card."""
    seen_sources = set()
    cleaned_results = []

    for r in results:
        source_file = r.get("source_file", "")
        source_section = r.get("source_section", "")
        source_key = f"{source_file}:{source_section}"
        if source_key in seen_sources:
            continue
        seen_sources.add(source_key)

        content = _clean_chunk_content(r.get("content", ""), source_file)
        cleaned_results.append({
            "content_html": md_to_html(content),
            "source_label": _build_source_label(source_file, source_section),
            "score": r.get("final_score", 0),
            "source_tier": r.get("source_tier", ""),
        })

    if not cleaned_results:
        return render_template(
            "search_results.html",
            query_echo=query,
            result_html='<div class="info">No matching knowledge found.</div>',
        )

    return render_template(
        "knowledge_answer.html",
        query=query,
        results=cleaned_results,
        is_expert=_is_expert_user(),
    )

# ---------------------------------------------------------------------------
# Station Predictor — /tools/station-predictor (Sprint QS10-T3-3A)
# ---------------------------------------------------------------------------

@bp.route("/tools/station-predictor")
def tools_station_predictor():
    """Station Predictor: predicted next review stations for a permit."""
    if not g.user:
        return redirect("/auth/login")
    return render_template("tools/station_predictor.html")


# ---------------------------------------------------------------------------
# Stuck Permit Analyzer — /tools/stuck-permit (Sprint QS10-T3-3B)
# ---------------------------------------------------------------------------

@bp.route("/tools/stuck-permit")
def tools_stuck_permit():
    """Stuck Permit Analyzer: diagnose delays and get intervention playbook."""
    if not g.user:
        return redirect("/auth/login")
    return render_template("tools/stuck_permit.html")
