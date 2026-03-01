"""Synchronous intelligence wrappers for Flask routes.

These wrap the async MCP tool functions into sync calls with structured
dict returns. Used by analyze(), report, brief, and API endpoints.
All wrappers: try/except -> None/[] on failure, 3s timeout, warning logged.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Currency parsing helper
# ---------------------------------------------------------------------------

def _parse_currency_str(value: str) -> float:
    """Parse a currency string like '$10,068', '$21.2K', '$1.5M' into a float.

    Handles:
      - Comma-separated: '10,068'
      - K suffix: '21.2K' -> 21200
      - M suffix: '1.5M' -> 1500000
    """
    s = value.strip().replace(',', '').replace('$', '')
    if s.upper().endswith('K'):
        return float(s[:-1]) * 1_000
    if s.upper().endswith('M'):
        return float(s[:-1]) * 1_000_000
    return float(s)


# ---------------------------------------------------------------------------
# Timeout helper
# ---------------------------------------------------------------------------

async def _with_timeout(coro, seconds: float = 3.0):
    """Wrap a coroutine with asyncio.wait_for timeout."""
    return await asyncio.wait_for(coro, timeout=seconds)


# ---------------------------------------------------------------------------
# Stuck permit diagnosis
# ---------------------------------------------------------------------------

def get_stuck_diagnosis_sync(permit_number: str) -> dict | None:
    """Get stuck permit diagnosis as a structured dict.

    Returns:
        {
            "severity": "HIGH",         # str: severity label (from tier or routing status)
            "severity_score": 72,       # int: 0-100 score
            "stuck_stations": [         # list of stuck station dicts
                {
                    "station": "CP-ZOC",
                    "days": 45,
                    "baseline_p50": 12,
                    "status": "STALLED",
                }
            ],
            "interventions": [          # ranked intervention steps
                {"step": 1, "action": "Contact plan checker", "contact": "..."}
            ],
            "permit_number": "202301015555",
            "markdown": "..."           # raw markdown for fallback rendering
        }
        or None on failure/timeout.
    """
    try:
        from src.tools.stuck_permit import diagnose_stuck_permit
        from web.helpers import run_async

        raw_markdown = run_async(_with_timeout(diagnose_stuck_permit(permit_number), seconds=3.0))
        return _parse_stuck_diagnosis(raw_markdown, permit_number)
    except asyncio.TimeoutError:
        logger.warning("Stuck diagnosis timed out for %s", permit_number)
        return None
    except Exception as e:
        logger.warning("Stuck diagnosis failed for %s: %s", permit_number, e)
        return None


def _parse_stuck_diagnosis(markdown: str, permit_number: str) -> dict | None:
    """Parse diagnose_stuck_permit markdown output into a structured dict.

    The markdown format is:
        # Stuck Permit Playbook: {permit_number}
        **Severity Score:** {score}/100 ({tier})
        **Routing Status:** {CRITICAL|STALLED|OK|UNKNOWN}
        ## Station Diagnosis
        ### **{STATION}** — [{STATUS}] — {N}d
        ## Intervention Steps
        {N}. [{URGENCY}] {action}
    """
    if not markdown:
        return None

    result: dict = {
        "permit_number": permit_number,
        "severity": "UNKNOWN",
        "severity_score": 0,
        "stuck_stations": [],
        "interventions": [],
        "markdown": markdown,
    }

    # Parse "Permit Not Found" or error responses — return minimal dict
    if "Permit Not Found" in markdown or "Error Diagnosing Permit" in markdown:
        return result

    # --- Severity score ---
    # Matches: **Severity Score:** 72/100 (HIGH)
    score_m = re.search(r'\*\*Severity Score:\*\*\s*(\d+)/100\s*\(([^)]+)\)', markdown)
    if score_m:
        try:
            result["severity_score"] = int(score_m.group(1))
        except (ValueError, TypeError):
            pass
        result["severity"] = score_m.group(2).strip()

    # --- Routing status (CRITICAL / STALLED / OK / UNKNOWN) ---
    # Matches: **Routing Status:** STALLED
    routing_m = re.search(r'\*\*Routing Status:\*\*\s*(\w+)', markdown)
    if routing_m:
        routing_status = routing_m.group(1).strip()
        # Map routing status to severity if score not available
        if result["severity"] == "UNKNOWN":
            result["severity"] = routing_status

    # --- Station Diagnosis section ---
    # Stations appear as: ### **CP-ZOC** — [STALLED] — 45d
    # or: ### **BLDG** (SF Department of Building Inspection) — [CRITICAL] — 90d
    station_pattern = re.compile(
        r'###\s+\*\*([A-Z0-9\-]+)\*\*(?:[^—]*)?—\s+\[([A-Z]+)\]\s+—\s+(\d+)d',
        re.MULTILINE,
    )
    for sm in station_pattern.finditer(markdown):
        station_name = sm.group(1).strip()
        station_status = sm.group(2).strip()
        try:
            dwell_days = int(sm.group(3))
        except (ValueError, TypeError):
            dwell_days = 0

        # Try to find p50 baseline from the flags text near this station
        # Flags look like: "dwell 45d (p50=12d baseline)" or "dwell 45d > p75 (30d baseline)"
        station_block_start = sm.end()
        # Find the next station heading or end of section
        next_section = re.search(r'\n##', markdown[station_block_start:])
        station_block = markdown[station_block_start: station_block_start + (next_section.start() if next_section else 500)]

        p50 = None
        p50_m = re.search(r'p50[=\s]*(\d+(?:\.\d+)?)d', station_block)
        if p50_m:
            try:
                p50 = float(p50_m.group(1))
            except (ValueError, TypeError):
                pass

        result["stuck_stations"].append({
            "station": station_name,
            "days": dwell_days,
            "baseline_p50": p50,
            "status": station_status,
        })

    # --- Intervention Steps section ---
    # Lines look like: "1. [HIGH] Contact DBI plan check counter..."
    # or: "2. [IMMEDIATE] Revise plans to address comments..."
    intervention_pattern = re.compile(
        r'^(\d+)\.\s+\[([A-Z]+)\]\s+(.+?)$',
        re.MULTILINE,
    )

    # Find the Intervention Steps section
    intervention_section_m = re.search(r'## Intervention Steps\n', markdown)
    intervention_text = markdown[intervention_section_m.end():] if intervention_section_m else markdown

    for im in intervention_pattern.finditer(intervention_text):
        step_num = int(im.group(1))
        urgency = im.group(2).strip()
        action_text = im.group(3).strip()

        # Try to find contact info in the lines immediately following
        # Contact lines look like: "   - SF Fire Department", "   - Phone: (415) 558-3300"
        block_start = im.end()
        # Capture up to 6 lines following the intervention line
        block = intervention_text[block_start: block_start + 400]
        contact_lines = []
        for line in block.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- ') and stripped != '- ':
                contact_lines.append(stripped[2:])
            elif stripped == '':
                continue
            elif re.match(r'^\d+\.', stripped):
                break
            elif stripped.startswith('#'):
                break

        contact_str = '; '.join(contact_lines) if contact_lines else None

        result["interventions"].append({
            "step": step_num,
            "urgency": urgency,
            "action": action_text,
            "contact": contact_str,
        })

        # Stop after Revision History or footer section
        if '## Revision History' in intervention_text[block_start:block_start + 50]:
            break

    return result


# ---------------------------------------------------------------------------
# Delay cost analysis
# ---------------------------------------------------------------------------

def get_delay_cost_sync(
    permit_type: str,
    monthly_cost: float,
    neighborhood: str | None = None,
) -> dict | None:
    """Get delay cost analysis as a structured dict.

    Returns:
        {
            "daily_cost": 166.67,       # float
            "weekly_cost": 1166.67,     # float
            "monthly_cost": 5000.0,     # float (input)
            "scenarios": [              # best/likely/worst
                {"label": "Best case", "months": 2, "total_cost": 10000},
                {"label": "Likely", "months": 4, "total_cost": 20000},
                {"label": "Worst case", "months": 8, "total_cost": 40000},
            ],
            "mitigation": ["strategy1", "strategy2"],
            "revision_risk": 0.12,      # float 0-1, probability
            "markdown": "..."           # raw markdown
        }
        or None on failure/timeout.
    """
    try:
        from src.tools.cost_of_delay import calculate_delay_cost
        from web.helpers import run_async

        raw_markdown = run_async(
            _with_timeout(
                calculate_delay_cost(
                    permit_type=permit_type,
                    monthly_carrying_cost=monthly_cost,
                    neighborhood=neighborhood,
                ),
                seconds=3.0,
            )
        )
        return _parse_delay_cost(raw_markdown, monthly_cost)
    except asyncio.TimeoutError:
        logger.warning("Delay cost timed out for permit_type=%s", permit_type)
        return None
    except Exception as e:
        logger.warning("Delay cost failed for permit_type=%s: %s", permit_type, e)
        return None


def _parse_delay_cost(markdown: str, monthly_cost: float) -> dict | None:
    """Parse calculate_delay_cost markdown output into a structured dict.

    The markdown format includes:
        **Daily Rate:** $166.67/day
        **Revision Probability:** 12%
        | Best (p25)   | 60d  | $9,868  | $200  | **$10,068** |
        | Likely (p50) | 120d | $19,737 | $200  | **$19,937** |
        | Worst (p90)  | 240d | $39,474 | $200  | **$39,674** |
        ## Mitigation Strategies
        - Pre-application meeting with DBI
        - ...
    """
    if not markdown or "Error" in markdown[:50]:
        return None

    daily_cost = monthly_cost / 30.44

    result: dict = {
        "daily_cost": round(daily_cost, 2),
        "weekly_cost": round(daily_cost * 7, 2),
        "monthly_cost": monthly_cost,
        "scenarios": [],
        "mitigation": [],
        "revision_risk": 0.0,
        "markdown": markdown,
    }

    # --- Daily rate (may override computed value if markdown has one) ---
    daily_m = re.search(r'\*\*Daily Rate:\*\*\s*\$([0-9,.KkMm]+)/day', markdown)
    if daily_m:
        try:
            result["daily_cost"] = _parse_currency_str(daily_m.group(1))
            result["weekly_cost"] = round(result["daily_cost"] * 7, 2)
        except (ValueError, TypeError):
            pass

    # --- Revision probability ---
    # Matches: **Revision Probability:** 12% (avg delay if revised: 30d)
    rev_m = re.search(r'\*\*Revision Probability:\*\*\s*(\d+)%', markdown)
    if rev_m:
        try:
            result["revision_risk"] = int(rev_m.group(1)) / 100.0
        except (ValueError, TypeError):
            pass

    # --- Scenarios from cost table ---
    # Row format: | Best (p25) | 60d | $9,868 | $200 | **$10,068** |
    # or:         | Likely (p50) | 120d | ... | **$21.2K** |
    scenario_pattern = re.compile(
        r'\|\s*(Best|Likely|Worst)[^|]*\|\s*(\d+)d\s*\|[^|]+\|[^|]+\|\s*\*\*\$([0-9,.KkMm]+)\*\*\s*\|',
        re.IGNORECASE,
    )
    label_map = {
        "best": "Best case",
        "likely": "Likely",
        "worst": "Worst case",
    }
    for sm in scenario_pattern.finditer(markdown):
        raw_label = sm.group(1).lower()
        label = label_map.get(raw_label, sm.group(1))
        try:
            days = int(sm.group(2))
            months = round(days / 30.44, 1)
            total_cost = _parse_currency_str(sm.group(3))
        except (ValueError, TypeError):
            continue

        result["scenarios"].append({
            "label": label,
            "months": months,
            "days": days,
            "total_cost": total_cost,
        })

    # --- Mitigation strategies ---
    # Section: ## Mitigation Strategies\n- strategy1\n- strategy2
    mit_section_m = re.search(r'## Mitigation Strategies\n', markdown)
    if mit_section_m:
        mit_text = markdown[mit_section_m.end():]
        for line in mit_text.split('\n'):
            stripped = line.strip()
            if stripped.startswith('- '):
                strategy = stripped[2:].strip()
                if strategy:
                    result["mitigation"].append(strategy)
            elif stripped.startswith('#') or stripped.startswith('---'):
                break

    return result


# ---------------------------------------------------------------------------
# Similar projects
# ---------------------------------------------------------------------------

def get_similar_projects_sync(
    permit_type: str,
    neighborhood: str | None = None,
    cost: float | None = None,
) -> list[dict]:
    """Get similar completed projects as structured dicts.

    Returns:
        [
            {
                "permit_number": "202201234567",
                "description": "Kitchen remodel...",
                "neighborhood": "Mission",
                "duration_days": 120,
                "routing_path": ["PERMIT-CTR", "BLDG", "CP-ZOC"],
                "estimated_cost": 85000,
            },
            ...
        ]
        or [] on failure/timeout.
    """
    try:
        from src.tools.similar_projects import similar_projects
        from web.helpers import run_async

        # Use return_structured=True to get (str, dict) tuple when available
        raw = run_async(
            _with_timeout(
                similar_projects(
                    permit_type=permit_type,
                    neighborhood=neighborhood,
                    estimated_cost=cost,
                    return_structured=True,
                ),
                seconds=3.0,
            )
        )

        # similar_projects returns (markdown_str, methodology_dict) when return_structured=True
        # or just a markdown str when structured data isn't available
        if isinstance(raw, tuple) and len(raw) == 2:
            markdown_str, methodology = raw
            # methodology dict uses "projects" key (Sprint 58 contract)
            structured = methodology.get("projects", []) if isinstance(methodology, dict) else []
            if structured:
                return _normalize_similar_projects(structured)
            # Fall back to parsing markdown
            return _parse_similar_projects_markdown(markdown_str)
        elif isinstance(raw, str):
            return _parse_similar_projects_markdown(raw)
        else:
            return []

    except asyncio.TimeoutError:
        logger.warning("Similar projects timed out for permit_type=%s", permit_type)
        return []
    except Exception as e:
        logger.warning("Similar projects failed for permit_type=%s: %s", permit_type, e)
        return []


def _normalize_similar_projects(matches: list[dict]) -> list[dict]:
    """Normalize structured match dicts from similar_projects into the contract shape."""
    results = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        # Map DB dict fields to contract interface
        duration_days = m.get("days_to_issuance") or m.get("days_to_completion")
        results.append({
            "permit_number": m.get("permit_number", ""),
            "description": m.get("permit_type_definition", ""),
            "neighborhood": m.get("neighborhood"),
            "duration_days": duration_days,
            "routing_path": m.get("routing_path", []),
            "estimated_cost": m.get("estimated_cost"),
            # Preserve extras for callers that want full data
            "address": m.get("address"),
            "filed_date": m.get("filed_date"),
            "issued_date": m.get("issued_date"),
            "completed_date": m.get("completed_date"),
        })
    return results


def _parse_similar_projects_markdown(markdown: str) -> list[dict]:
    """Parse similar_projects markdown output into structured dicts.

    Markdown format per project:
        ## 1. 123 Mission St
        **Permit:** 202201234567 . **Type:** ALTERATIONS
        **Neighborhood:** Mission
        **Cost:** $85,000
        **Days to Issuance:** 120
        **Route:** PERMIT-CTR -> BLDG -> CP-ZOC
    """
    if not markdown or "No similar completed projects found" in markdown:
        return []

    results = []

    # Split on project headings: ## 1. Address or ## 2. ...
    # Find each numbered section
    project_pattern = re.compile(r'^## \d+\. (.+?)$', re.MULTILINE)
    sections = list(project_pattern.finditer(markdown))

    for i, section_m in enumerate(sections):
        # Get this section's text
        start = section_m.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(markdown)
        block = markdown[start:end]

        project: dict = {
            "permit_number": "",
            "description": "",
            "neighborhood": None,
            "duration_days": None,
            "routing_path": [],
            "estimated_cost": None,
            "address": section_m.group(1).strip(),
        }

        # Permit number and type
        perm_m = re.search(r'\*\*Permit:\*\*\s*(\S+).*?\*\*Type:\*\*\s*(.+?)(?:\n|$)', block, re.IGNORECASE)
        if perm_m:
            project["permit_number"] = perm_m.group(1).strip(' ·')
            project["description"] = perm_m.group(2).strip()

        # Neighborhood
        hood_m = re.search(r'\*\*Neighborhood:\*\*\s*(.+?)(?:\n|$)', block)
        if hood_m:
            project["neighborhood"] = hood_m.group(1).strip()

        # Cost
        cost_m = re.search(r'\*\*Cost:\*\*\s*\$([0-9,]+)', block)
        if cost_m:
            try:
                project["estimated_cost"] = float(cost_m.group(1).replace(',', ''))
            except (ValueError, TypeError):
                pass

        # Duration — prefer "Days to Issuance"
        issuance_m = re.search(r'\*\*Days to Issuance:\*\*\s*(\d+)', block)
        if issuance_m:
            try:
                project["duration_days"] = int(issuance_m.group(1))
            except (ValueError, TypeError):
                pass
        else:
            completion_m = re.search(r'\*\*Days to Completion:\*\*\s*(\d+)', block)
            if completion_m:
                try:
                    project["duration_days"] = int(completion_m.group(1))
                except (ValueError, TypeError):
                    pass

        # Routing path
        route_m = re.search(r'\*\*Route:\*\*\s*(.+?)(?:\n|$)', block)
        if route_m:
            raw_route = route_m.group(1).strip()
            # Routes are separated by " -> " or " → "
            stations = re.split(r'\s*(?:->|→)\s*', raw_route)
            project["routing_path"] = [s.strip() for s in stations if s.strip()]

        if project["permit_number"]:
            results.append(project)

    return results
