"""Tool: diagnose_stuck_permit — Stuck Permit Intervention Playbook.

Diagnoses why a permit is stalled and generates a ranked intervention playbook
with specific action steps based on which station is holding the permit and
how long it has been dwell there relative to historical baselines.

Checks for:
  - Dwell time vs p50/p75/p90 baseline per station (from station_velocity_v2)
  - No inspector assigned (station stalled with no activity)
  - Comments issued, no resubmission (revision backlog)
  - Inter-agency holds (SFFD, HEALTH/DPH, Planning, DPW)
  - Multiple revision cycles (addenda_number >= 2)
  - 30+ day inactivity blackout

Produced format: markdown playbook with severity header, per-station diagnosis,
ranked interventions, and agency contact info.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from src.db import BACKEND, get_connection
from src.severity import PermitInput, score_permit, classify_description

logger = logging.getLogger(__name__)

# Placeholder helper — consistent with existing tools
_PH = "%s" if BACKEND == "postgres" else "?"


# ---------------------------------------------------------------------------
# Inter-agency station classification
# ---------------------------------------------------------------------------

# Stations that route to inter-agency partners — require direct agency contact
INTER_AGENCY_STATIONS: dict[str, str] = {
    # Fire
    "SFFD": "SF Fire Department",
    "SFFD-HQ": "SF Fire Department (Headquarters)",
    # Health / DPH
    "HEALTH": "SF Department of Public Health",
    "HEALTH-FD": "SF Department of Public Health (Food)",
    "HEALTH-HM": "SF Department of Public Health (Hazmat)",
    "HEALTH-MH": "SF Department of Public Health (Mental Health)",
    # Planning
    "CP-ZOC": "SF Planning Department",
    "CP-ENV": "SF Planning (Environmental)",
    "PLAN": "SF Planning Department",
    "PLANNING": "SF Planning Department",
    # Public Works / DPW
    "DPW-BSM": "SF Public Works (Bureau of Street-Use & Mapping)",
    "DPW-BUF": "SF Public Works (Bureau of Urban Forestry)",
    # PUC
    "SFPUC": "SF Public Utilities Commission",
    "SFPUC-PRG": "SF Public Utilities Commission (Groundwater)",
    # Historic Preservation
    "HIS": "Historic Preservation Commission",
    # Accessible Business Entrance
    "ABE": "Accessible Business Entrance Program",
}

# BLDG plan-check stations — handled by DBI customer service
BLDG_STATIONS = {"BLDG", "BLDG-E", "BLDG-P", "BLDG-M", "BLDG-S", "BLDG-A"}


# ---------------------------------------------------------------------------
# Agency contact info
# ---------------------------------------------------------------------------

AGENCY_CONTACTS: dict[str, dict] = {
    "DBI": {
        "name": "SF Department of Building Inspection",
        "phone": "(415) 558-6000",
        "url": "https://sfdbi.org",
        "notes": "Customer service counter: 49 South Van Ness Ave, M-F 8am-4pm",
    },
    "SFFD": {
        "name": "SF Fire Department — Permit Division",
        "phone": "(415) 558-3300",
        "url": "https://sf.gov/departments/fire-department",
        "notes": "Plan check: 698 2nd St, 3rd Floor",
    },
    "HEALTH": {
        "name": "SF Department of Public Health — Environmental Health",
        "phone": "(415) 252-3800",
        "url": "https://www.sfcdcp.org/environmental-health.html",
        "notes": "For food facility permits: (415) 252-3984",
    },
    "PLANNING": {
        "name": "SF Planning Department",
        "phone": "(415) 558-6378",
        "url": "https://sfplanning.org",
        "notes": "Permit Counter: 49 South Van Ness Ave, M-Th 8am-5pm",
    },
    "DPW": {
        "name": "SF Public Works",
        "phone": "(415) 554-6920",
        "url": "https://sfpublicworks.org",
        "notes": "Street-use permits: (415) 695-2020",
    },
    "HIS": {
        "name": "SF Historic Preservation Commission",
        "phone": "(415) 558-6206",
        "url": "https://sfplanning.org/historic-preservation",
        "notes": "Part of Planning Department — same counter at 49 South Van Ness",
    },
}


def _get_agency_key(station: str) -> str:
    """Map a station code to an agency contact key."""
    s = station.upper()
    if s.startswith("SFFD"):
        return "SFFD"
    if s.startswith("HEALTH"):
        return "HEALTH"
    if s in ("CP-ZOC", "CP-ENV", "PLAN", "PLANNING"):
        return "PLANNING"
    if s.startswith("DPW"):
        return "DPW"
    if s == "HIS":
        return "HIS"
    return "DBI"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _exec(conn, sql: str, params=None):
    """Execute SQL and return all rows — handles both DuckDB and Postgres."""
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


def _exec_one(conn, sql: str, params=None):
    """Execute SQL and return first row or None."""
    rows = _exec(conn, sql, params)
    return rows[0] if rows else None


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def _fetch_permit(conn, permit_number: str) -> dict | None:
    """Fetch permit row from permits table."""
    sql = f"""
        SELECT permit_number, permit_type, permit_type_definition, status,
               status_date, description, filed_date, issued_date, approved_date,
               completed_date, estimated_cost, revised_cost, street_number,
               street_name, street_suffix, zipcode, neighborhood
        FROM permits
        WHERE permit_number = {_PH}
    """
    row = _exec_one(conn, sql, [permit_number])
    if not row:
        return None
    keys = [
        "permit_number", "permit_type", "permit_type_definition", "status",
        "status_date", "description", "filed_date", "issued_date", "approved_date",
        "completed_date", "estimated_cost", "revised_cost", "street_number",
        "street_name", "street_suffix", "zipcode", "neighborhood",
    ]
    return dict(zip(keys, row))


def _fetch_active_stations(conn, permit_number: str) -> list[dict]:
    """Fetch current active routing stations from addenda table.

    Active = arrived but not finished (finish_date IS NULL), or most recent
    routing entry per station if all have finish_dates (still under review).

    Returns list of dicts with: station, addenda_number, arrive, finish_date,
    review_results, comments.
    """
    # Get all routing rows for this permit, most recent per station
    sql = f"""
        SELECT station, addenda_number, arrive, finish_date,
               review_results
        FROM addenda
        WHERE application_number = {_PH}
          AND station IS NOT NULL
        ORDER BY arrive DESC NULLS LAST, addenda_number DESC
    """
    rows = _exec(conn, sql, [permit_number])

    if not rows:
        return []

    # Convert to dicts
    all_entries = []
    for row in rows:
        all_entries.append({
            "station": row[0],
            "addenda_number": row[1],
            "arrive": row[2],
            "finish_date": row[3],
            "review_results": row[4],
        })

    # Find active (finish_date IS NULL) stations first
    active = [e for e in all_entries if e["finish_date"] is None]

    # If no active stations, take the most recently arrived per station
    if not active:
        seen = set()
        for entry in all_entries:
            if entry["station"] not in seen:
                seen.add(entry["station"])
                active.append(entry)

    return active


def _fetch_revision_count(conn, permit_number: str) -> int:
    """Count revision cycles (addenda_number >= 1 routing entries)."""
    sql = f"""
        SELECT COUNT(DISTINCT addenda_number)
        FROM addenda
        WHERE application_number = {_PH}
          AND addenda_number >= 1
    """
    row = _exec_one(conn, sql, [permit_number])
    return int(row[0]) if row and row[0] else 0


def _fetch_velocity(conn, station: str, metric_type: str = "initial") -> dict | None:
    """Fetch pre-computed station velocity baselines from station_velocity_v2.

    Tries 'current' period first, falls back to 'baseline', then 'all'.
    """
    for period in ("current", "baseline", "all"):
        sql = f"""
            SELECT p50_days, p75_days, p90_days, sample_count
            FROM station_velocity_v2
            WHERE station = {_PH}
              AND metric_type = {_PH}
              AND period = {_PH}
        """
        try:
            row = _exec_one(conn, sql, [station, metric_type, period])
            if row and row[3] and row[3] >= 10:
                return {
                    "p50_days": float(row[0]) if row[0] is not None else None,
                    "p75_days": float(row[1]) if row[1] is not None else None,
                    "p90_days": float(row[2]) if row[2] is not None else None,
                    "sample_count": int(row[3]),
                    "period": period,
                }
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Dwell time calculation
# ---------------------------------------------------------------------------

def _parse_date(val) -> date | None:
    """Parse a date from string, date, or datetime."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        return date.fromisoformat(str(val).strip()[:10])
    except (ValueError, TypeError):
        return None


def _calc_dwell_days(arrive_val, today: date) -> int | None:
    """Calculate days since permit arrived at a station."""
    arrive = _parse_date(arrive_val)
    if arrive is None:
        return None
    return (today - arrive).days


# ---------------------------------------------------------------------------
# Diagnosis logic
# ---------------------------------------------------------------------------

def _diagnose_station(
    station_entry: dict,
    velocity: dict | None,
    today: date,
) -> dict:
    """Diagnose a single station entry.

    Returns a dict with:
        station, dwell_days, status, flags, recommendation
    """
    station = station_entry["station"]
    dwell_days = _calc_dwell_days(station_entry.get("arrive"), today)
    review_results = station_entry.get("review_results") or ""
    addenda_number = station_entry.get("addenda_number") or 0

    flags = []
    status = "normal"
    recommendation = None

    # --- Dwell vs baseline ---
    if dwell_days is not None and velocity:
        p75 = velocity.get("p75_days")
        p90 = velocity.get("p90_days")
        p50 = velocity.get("p50_days")

        if p90 is not None and dwell_days > p90:
            status = "critically_stalled"
            flags.append(f"dwell {dwell_days}d > p90 ({p90:.0f}d baseline)")
        elif p75 is not None and dwell_days > p75:
            status = "stalled"
            flags.append(f"dwell {dwell_days}d > p75 ({p75:.0f}d baseline)")
        elif p50 is not None:
            flags.append(f"dwell {dwell_days}d (p50={p50:.0f}d baseline)")
    elif dwell_days is not None:
        if dwell_days > 90:
            status = "critically_stalled"
            flags.append(f"dwell {dwell_days}d (no baseline — very long wait)")
        elif dwell_days > 45:
            status = "stalled"
            flags.append(f"dwell {dwell_days}d (no baseline — extended wait)")

    # --- Comment-issued, no resubmission ---
    if review_results and "comment" in review_results.lower():
        flags.append("comments issued — resubmission needed")
        status = max(status, "stalled", key=lambda s: {"normal": 0, "stalled": 1, "critically_stalled": 2}.get(s, 0))

    # --- Revision cycle ---
    if addenda_number >= 2:
        flags.append(f"revision cycle {addenda_number} (multiple rounds)")

    # --- 30+ day inactivity ---
    if dwell_days is not None and dwell_days >= 30 and not flags:
        flags.append(f"{dwell_days}d with no recorded activity")

    # --- Build recommendation ---
    is_inter_agency = station.upper() in INTER_AGENCY_STATIONS
    is_bldg = station.upper() in BLDG_STATIONS or station.upper().startswith("BLDG")

    if review_results and "comment" in review_results.lower():
        recommendation = "Revise plans to address plan check comments and resubmit via EPR (Electronic Plan Review)"
    elif is_inter_agency:
        agency_name = INTER_AGENCY_STATIONS.get(station.upper(), station)
        recommendation = f"Contact {agency_name} directly to inquire about permit status"
    elif is_bldg:
        recommendation = "Contact DBI plan check counter to inquire about permit status (49 South Van Ness)"
    elif dwell_days is not None and dwell_days >= 30:
        recommendation = "File a status inquiry with DBI Customer Service — (415) 558-6000"
    else:
        recommendation = "Monitor permit routing — dwell is within normal range"

    return {
        "station": station,
        "dwell_days": dwell_days,
        "status": status,
        "flags": flags,
        "recommendation": recommendation,
        "is_inter_agency": is_inter_agency,
        "is_bldg": is_bldg,
        "review_results": review_results,
        "addenda_number": addenda_number,
    }


def _severity_label(status: str) -> str:
    mapping = {
        "critically_stalled": "CRITICAL",
        "stalled": "STALLED",
        "normal": "NORMAL",
    }
    return mapping.get(status, "UNKNOWN")


def _overall_status(diagnoses: list[dict]) -> str:
    """Compute overall worst-case status across all stations."""
    if any(d["status"] == "critically_stalled" for d in diagnoses):
        return "critically_stalled"
    if any(d["status"] == "stalled" for d in diagnoses):
        return "stalled"
    return "normal"


# ---------------------------------------------------------------------------
# Markdown formatting
# ---------------------------------------------------------------------------

def _format_address(permit: dict) -> str:
    """Format permit address from permit dict."""
    parts = [
        str(permit.get("street_number") or "").strip(),
        str(permit.get("street_name") or "").strip(),
        str(permit.get("street_suffix") or "").strip(),
    ]
    addr = " ".join(p for p in parts if p)
    if permit.get("zipcode"):
        addr = f"{addr}, SF {permit['zipcode']}"
    return addr or "Address unknown"


def _format_playbook(
    permit: dict,
    diagnoses: list[dict],
    severity_result,
    revision_count: int,
    today: date,
) -> str:
    """Format the full intervention playbook as markdown."""
    lines = []

    # --- Header ---
    permit_number = permit.get("permit_number", "Unknown")
    status = (permit.get("status") or "").title()
    description = (permit.get("description") or "No description")
    address = _format_address(permit)

    overall = _overall_status(diagnoses)
    severity_emoji = {
        "critically_stalled": "CRITICAL",
        "stalled": "STALLED",
        "normal": "OK",
    }.get(overall, "UNKNOWN")

    lines.append(f"# Stuck Permit Playbook: {permit_number}")
    lines.append("")
    lines.append(f"**Address:** {address}")
    lines.append(f"**Description:** {description}")
    lines.append(f"**Permit Status:** {status}")
    lines.append(f"**Severity Score:** {severity_result.score}/100 ({severity_result.tier})")
    lines.append(f"**Routing Status:** {severity_emoji}")
    if revision_count > 0:
        lines.append(f"**Revision Cycles:** {revision_count} (resubmission required)")
    lines.append("")

    # --- Filed / issued dates ---
    filed = _parse_date(permit.get("filed_date"))
    issued = _parse_date(permit.get("issued_date"))
    if filed:
        days_filed = (today - filed).days
        lines.append(f"**Filed:** {filed.isoformat()} ({days_filed} days ago)")
    if issued:
        days_issued = (today - issued).days
        lines.append(f"**Issued:** {issued.isoformat()} ({days_issued} days ago)")
    if filed or issued:
        lines.append("")

    # --- Station Diagnosis ---
    lines.append("## Station Diagnosis")
    lines.append("")

    if not diagnoses:
        lines.append("No active routing stations found in addenda data.")
        lines.append("This permit may not have entered the plan check queue yet, or data is unavailable.")
        lines.append("")
    else:
        for diag in sorted(diagnoses, key=lambda d: {"critically_stalled": 0, "stalled": 1, "normal": 2}.get(d["status"], 3)):
            station_label = f"**{diag['station']}**"
            if diag["station"].upper() in INTER_AGENCY_STATIONS:
                agency = INTER_AGENCY_STATIONS[diag["station"].upper()]
                station_label = f"**{diag['station']}** ({agency})"

            dwell_str = f"{diag['dwell_days']}d" if diag["dwell_days"] is not None else "unknown dwell"
            status_label = _severity_label(diag["status"])
            lines.append(f"### {station_label} — [{status_label}] — {dwell_str}")
            lines.append("")

            if diag["flags"]:
                for flag in diag["flags"]:
                    lines.append(f"- {flag}")
                lines.append("")

            if diag["review_results"]:
                lines.append(f"**Review Result:** {diag['review_results']}")
                lines.append("")

    # --- Intervention Steps (ranked) ---
    lines.append("## Intervention Steps")
    lines.append("")

    # Collect ranked interventions: critically_stalled first, then stalled, then normal
    interventions = []

    # Priority 1: Comment-issued resubmission
    comment_stations = [d for d in diagnoses if d["review_results"] and "comment" in d["review_results"].lower()]
    if comment_stations:
        station_list = ", ".join(d["station"] for d in comment_stations)
        interventions.append({
            "priority": 1,
            "action": f"Revise plans to address comments at {station_list} and resubmit via EPR (Electronic Plan Review)",
            "contact": None,
            "urgency": "IMMEDIATE",
        })

    # Priority 2: Critically stalled inter-agency
    for diag in diagnoses:
        if diag["status"] == "critically_stalled" and diag["is_inter_agency"]:
            agency_key = _get_agency_key(diag["station"])
            contact = AGENCY_CONTACTS.get(agency_key)
            interventions.append({
                "priority": 2,
                "action": f"Contact {INTER_AGENCY_STATIONS.get(diag['station'].upper(), diag['station'])} directly — permit has been waiting {diag['dwell_days']}d (critically past p90 baseline)",
                "contact": contact,
                "urgency": "HIGH",
            })

    # Priority 3: Critically stalled BLDG
    for diag in diagnoses:
        if diag["status"] == "critically_stalled" and diag["is_bldg"]:
            interventions.append({
                "priority": 3,
                "action": f"Contact DBI plan check counter — {diag['station']} has held permit for {diag['dwell_days']}d (critically past p90 baseline)",
                "contact": AGENCY_CONTACTS["DBI"],
                "urgency": "HIGH",
            })

    # Priority 4: Stalled inter-agency
    for diag in diagnoses:
        if diag["status"] == "stalled" and diag["is_inter_agency"]:
            agency_key = _get_agency_key(diag["station"])
            contact = AGENCY_CONTACTS.get(agency_key)
            interventions.append({
                "priority": 4,
                "action": f"Contact {INTER_AGENCY_STATIONS.get(diag['station'].upper(), diag['station'])} — {diag['dwell_days']}d dwell exceeds p75 baseline",
                "contact": contact,
                "urgency": "MEDIUM",
            })

    # Priority 5: Stalled BLDG
    for diag in diagnoses:
        if diag["status"] == "stalled" and diag["is_bldg"]:
            interventions.append({
                "priority": 5,
                "action": f"Contact DBI plan check — {diag['station']} has held permit for {diag['dwell_days']}d (past p75 baseline)",
                "contact": AGENCY_CONTACTS["DBI"],
                "urgency": "MEDIUM",
            })

    # Priority 6: Multiple revision cycles
    if revision_count >= 2:
        interventions.append({
            "priority": 6,
            "action": f"Review all plan check comments carefully — {revision_count} revision cycles indicate recurring issues. Consider consulting with a licensed architect or expediter.",
            "contact": None,
            "urgency": "MEDIUM",
        })

    # Priority 7: General 30d+ inactivity
    long_inactive = [d for d in diagnoses if d["dwell_days"] is not None and d["dwell_days"] >= 30 and d["status"] == "normal"]
    if long_inactive:
        interventions.append({
            "priority": 7,
            "action": f"File a status inquiry with DBI Customer Service — no recorded activity for 30+ days",
            "contact": AGENCY_CONTACTS["DBI"],
            "urgency": "LOW",
        })

    if not interventions:
        lines.append("No urgent interventions required at this time. Monitor permit routing.")
        lines.append("")
    else:
        urgency_order = {"IMMEDIATE": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        interventions.sort(key=lambda x: (urgency_order.get(x["urgency"], 9), x["priority"]))

        for i, step in enumerate(interventions, 1):
            urgency_tag = f"[{step['urgency']}]"
            lines.append(f"{i}. {urgency_tag} {step['action']}")
            if step.get("contact"):
                c = step["contact"]
                lines.append(f"   - {c['name']}")
                if c.get("phone"):
                    lines.append(f"   - Phone: {c['phone']}")
                if c.get("url"):
                    lines.append(f"   - Web: {c['url']}")
                if c.get("notes"):
                    lines.append(f"   - Notes: {c['notes']}")
            lines.append("")

    # --- Additional context ---
    if revision_count > 0:
        lines.append("## Revision History")
        lines.append("")
        lines.append(f"This permit has gone through **{revision_count}** revision cycle(s).")
        if revision_count >= 3:
            lines.append("Multiple revision cycles suggest persistent plan check issues. Consider an expediter or licensed architect for review.")
        lines.append("")

    # --- Footer note ---
    lines.append("---")
    lines.append(f"*Playbook generated {today.isoformat()}. Station dwell baselines from historical addenda data.*")
    lines.append("*For EPR (Electronic Plan Review): https://dbiweb02.sfgov.org/dbipts/*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main async tool function
# ---------------------------------------------------------------------------

async def diagnose_stuck_permit(permit_number: str) -> str:
    """Diagnose why a permit is stuck and return a ranked intervention playbook.

    Args:
        permit_number: The SF permit number (e.g. "202401234567").

    Returns:
        Markdown-formatted intervention playbook with:
        - Severity score and routing status summary
        - Per-station diagnosis (dwell vs historical baselines)
        - Ranked intervention steps with contact information
        - Revision history if applicable
    """
    permit_number = permit_number.strip()
    today = date.today()

    conn = None
    try:
        conn = get_connection()
        # 1. Fetch permit data
        permit = _fetch_permit(conn, permit_number)
        if not permit:
            return (
                f"# Permit Not Found: {permit_number}\n\n"
                f"No permit found with number `{permit_number}` in the database.\n\n"
                f"Verify the permit number at: https://dbiweb02.sfgov.org/dbipts/"
            )

        # 2. Fetch active routing stations from addenda
        active_stations = _fetch_active_stations(conn, permit_number)

        # 3. Fetch revision count
        revision_count = _fetch_revision_count(conn, permit_number)

        # 4. Score permit severity (uses pure Python, no DB needed)
        perm_input = PermitInput.from_dict(permit)
        severity_result = score_permit(perm_input, today=today)

        # 5. Diagnose each active station
        diagnoses = []
        for station_entry in active_stations:
            station = station_entry.get("station", "")
            if not station:
                continue

            # Determine metric_type from addenda_number
            addenda_num = station_entry.get("addenda_number") or 0
            metric_type = "revision" if addenda_num >= 1 else "initial"

            # Fetch velocity baseline for this station
            velocity = _fetch_velocity(conn, station, metric_type=metric_type)

            diagnosis = _diagnose_station(station_entry, velocity, today)
            diagnoses.append(diagnosis)

        # 6. Format playbook
        playbook = _format_playbook(permit, diagnoses, severity_result, revision_count, today)
        return playbook

    except Exception as e:
        logger.exception("diagnose_stuck_permit(%s) failed", permit_number)
        return (
            f"# Error Diagnosing Permit {permit_number}\n\n"
            f"An error occurred while fetching permit data: {e}\n\n"
            f"Please verify the permit number and try again."
        )
    finally:
        if conn is not None:
            conn.close()
