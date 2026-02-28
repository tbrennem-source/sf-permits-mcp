"""Tool: cost_of_delay — Calculate financial cost of permit processing delays.

Combines timeline estimates (p50/p75/p90) with carrying costs and revision
risk to show the full economic impact of permit delays. Helps owners and
expediters quantify the ROI of faster permitting strategies.

QS8-T2-D
"""

import logging
from typing import Optional

# Module-level sentinel for estimate_timeline — allows test patching.
# The real function is loaded lazily on first call to avoid startup cost.
estimate_timeline = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permit type to OTC eligibility mapping
# ---------------------------------------------------------------------------
OTC_ELIGIBLE_TYPES = {
    "otc",
    "no_plans",
    "general_alteration",
    "bathroom_remodel",
    "kitchen_remodel",
    "seismic",
    "plumbing",
    "electrical",
}

# Revision probability by permit type (from revision_risk REVISION_TRIGGERS patterns
# and typical SF DBI correction rates)
REVISION_PROBABILITY = {
    "restaurant": 0.38,
    "commercial_ti": 0.35,
    "change_of_use": 0.40,
    "new_construction": 0.30,
    "adu": 0.28,
    "adaptive_reuse": 0.35,
    "seismic": 0.18,
    "general_alteration": 0.15,
    "kitchen_remodel": 0.12,
    "bathroom_remodel": 0.12,
    "alterations": 0.20,
    "otc": 0.05,
    "no_plans": 0.05,
}

DEFAULT_REVISION_PROBABILITY = 0.20

# Average revision delay in days by permit type
REVISION_DELAY_DAYS = {
    "restaurant": 75,
    "commercial_ti": 60,
    "change_of_use": 70,
    "new_construction": 90,
    "adu": 60,
    "adaptive_reuse": 70,
    "seismic": 45,
    "general_alteration": 30,
    "kitchen_remodel": 21,
    "bathroom_remodel": 21,
    "alterations": 45,
    "otc": 14,
    "no_plans": 14,
}

DEFAULT_REVISION_DELAY_DAYS = 45

# Mitigation strategies by project type
MITIGATION_STRATEGIES = {
    "restaurant": [
        "Pre-consultation with DPH before filing",
        "Submit complete equipment schedule at first submittal (DPH #1 correction item)",
        "Engage architect experienced with SF DBI restaurant permits",
        "Consider expedited plan check ($500-$1,500 additional fee)",
    ],
    "commercial_ti": [
        "CASp inspection pre-filing — reduces ADA correction rate from ~38% to ~10%",
        "Submit DA-02 accessibility checklist with initial application",
        "Use Title-24 compliance consultant — #1 correction category (~45% of commercial)",
        "Pre-application DBI counter consultation",
    ],
    "new_construction": [
        "File for early start (foundation permit) while full permits process",
        "Geotechnical report ready before filing",
        "Pre-application meeting with Planning",
        "Engage licensed professional experienced with SF Building Code",
    ],
    "adu": [
        "Confirm ADU pre-approval through SF Planning",
        "Use SF ADU permit application template checklist",
        "Consider ADU pre-approved plan program if eligible",
        "Verify setbacks with Planning before designing",
    ],
    "general": [
        "Complete Title-24 energy compliance documentation before submission",
        "Include a Back Check page in all plan sets",
        "Use DBI completeness checklist before submitting",
        "Consider pre-application consultation with plan reviewer",
    ],
}


def _get_permit_type_label(permit_type: str) -> str:
    """Return a human-readable label for the permit type."""
    labels = {
        "restaurant": "Restaurant/Food Service",
        "commercial_ti": "Commercial Tenant Improvement",
        "change_of_use": "Change of Use",
        "new_construction": "New Construction",
        "adu": "Accessory Dwelling Unit (ADU)",
        "adaptive_reuse": "Adaptive Reuse",
        "seismic": "Seismic Retrofit",
        "general_alteration": "General Alteration",
        "kitchen_remodel": "Kitchen Remodel",
        "bathroom_remodel": "Bathroom Remodel",
        "alterations": "Alterations",
        "otc": "Over-the-Counter (OTC)",
        "no_plans": "No Plans Required",
    }
    return labels.get(permit_type, permit_type.replace("_", " ").title())


def _format_currency(amount: float) -> str:
    """Format a dollar amount with K/M suffix for readability."""
    if amount >= 1_000_000:
        return f"${amount / 1_000_000:.2f}M"
    elif amount >= 10_000:
        return f"${amount / 1_000:.1f}K"
    else:
        return f"${amount:,.0f}"


def _get_revision_info(permit_type: str) -> tuple[float, int]:
    """Return (revision_probability, revision_delay_days) for a permit type."""
    prob = REVISION_PROBABILITY.get(permit_type, DEFAULT_REVISION_PROBABILITY)
    delay = REVISION_DELAY_DAYS.get(permit_type, DEFAULT_REVISION_DELAY_DAYS)
    return prob, delay


def _get_timeline_estimates(permit_type: str) -> dict:
    """Get p25/p50/p90 timeline estimates.

    Attempts to call estimate_timeline tool. Falls back to hard-coded
    typical SF DBI processing times if the tool or DB is unavailable.
    """
    # Hard-coded fallback timelines in days (based on SF DBI historical patterns)
    # These are calibrated to match estimate_timeline outputs for common types
    FALLBACK_TIMELINES = {
        "restaurant": {"p25": 45, "p50": 75, "p90": 150},
        "commercial_ti": {"p25": 30, "p50": 60, "p90": 120},
        "change_of_use": {"p25": 60, "p50": 90, "p90": 180},
        "new_construction": {"p25": 90, "p50": 150, "p90": 300},
        "adu": {"p25": 45, "p50": 90, "p90": 180},
        "adaptive_reuse": {"p25": 60, "p50": 120, "p90": 240},
        "seismic": {"p25": 21, "p50": 45, "p90": 90},
        "general_alteration": {"p25": 14, "p50": 30, "p90": 75},
        "kitchen_remodel": {"p25": 10, "p50": 21, "p90": 60},
        "bathroom_remodel": {"p25": 10, "p50": 21, "p90": 60},
        "alterations": {"p25": 21, "p50": 45, "p90": 120},
        "otc": {"p25": 1, "p50": 3, "p90": 14},
        "no_plans": {"p25": 1, "p50": 3, "p90": 10},
    }
    default = {"p25": 21, "p50": 45, "p90": 120}
    return FALLBACK_TIMELINES.get(permit_type, default)


def daily_delay_cost(monthly_carrying_cost: float) -> str:
    """Return a one-liner showing the daily cost of permit delay.

    Args:
        monthly_carrying_cost: Total monthly carrying cost in dollars
            (mortgage/rent, insurance, opportunity cost, etc.)

    Returns:
        One-line formatted string.
    """
    if monthly_carrying_cost <= 0:
        return "Invalid monthly carrying cost — must be greater than zero."

    daily = monthly_carrying_cost / 30.44  # average days per month
    return f"Every day of permit delay costs you {_format_currency(daily)}/day"


async def calculate_delay_cost(
    permit_type: str,
    monthly_carrying_cost: float,
    neighborhood: Optional[str] = None,
    triggers: Optional[list] = None,
) -> str:
    """Calculate financial cost of permit processing delays.

    Shows the full economic impact across best/likely/worst-case timelines
    including carrying costs and revision risk. Helps quantify the ROI of
    expediting strategies.

    Args:
        permit_type: Type of permit (e.g., 'restaurant', 'adu', 'new_construction',
                     'commercial_ti', 'alterations', 'otc')
        monthly_carrying_cost: Total monthly carrying cost in dollars
            (mortgage/rent payments, insurance, opportunity cost of capital,
            lost revenue from delay, etc.)
        neighborhood: Optional SF neighborhood for context (no data effect currently)
        triggers: Optional list of delay trigger flags (e.g., ['planning_review',
                  'historic', 'dph_review']) — used to escalate timeline estimates

    Returns:
        Formatted markdown string with cost breakdown table and mitigation advice.
    """
    if monthly_carrying_cost <= 0:
        return "## Error\n\nMonthly carrying cost must be greater than zero."

    # ── Step 1: Get timeline estimates ─────────────────────────────
    timelines = _get_timeline_estimates(permit_type)
    db_available = False

    # Resolve estimate_timeline: check module attribute first (allows test patching),
    # then fall back to a fresh import. Never cache — patching resets the attribute.
    import sys as _sys
    _this_module = _sys.modules[__name__]
    _etl_fn = getattr(_this_module, "estimate_timeline", None)
    if _etl_fn is None:
        try:
            from src.tools.estimate_timeline import estimate_timeline as _imported_etl
            _etl_fn = _imported_etl
        except Exception:
            _etl_fn = None

    try:
        if _etl_fn is None:
            raise RuntimeError("estimate_timeline not available")
        result_str = await _etl_fn(
            permit_type=permit_type,
            neighborhood=neighborhood,
            triggers=triggers or [],
            return_structured=False,
        )
        # Parse p50/p90 from the returned markdown if possible
        import re
        p50_match = re.search(r'p50[^\d]*(\d+)\s*day', result_str, re.IGNORECASE)
        p90_match = re.search(r'p90[^\d]*(\d+)\s*day', result_str, re.IGNORECASE)
        p25_match = re.search(r'p25[^\d]*(\d+)\s*day', result_str, re.IGNORECASE)
        if p50_match:
            timelines["p50"] = int(p50_match.group(1))
            db_available = True
        if p90_match:
            timelines["p90"] = int(p90_match.group(1))
        if p25_match:
            timelines["p25"] = int(p25_match.group(1))
    except Exception as e:
        logger.debug("estimate_timeline unavailable, using fallback: %s", e)

    # Apply trigger escalations to timeline estimates
    trigger_days_added = 0
    trigger_notes = []
    TRIGGER_DELAYS = {
        "planning_review": (14, "+2-6 weeks: Planning Department review"),
        "dph_review": (21, "+2-4 weeks: DPH health permit review"),
        "fire_review": (10, "+1-3 weeks: Fire Department plan review"),
        "historic": (42, "+4-12 weeks: Historic preservation review (HPC)"),
        "ceqa": (180, "+3-12 months: CEQA environmental review"),
        "multi_agency": (10, "+1-2 weeks per additional agency"),
        "conditional_use": (90, "+3+ months: Planning Commission CU hearing"),
        "change_of_use": (30, "+30 days minimum: Section 311 notification"),
    }
    if triggers:
        for trigger in triggers:
            if trigger in TRIGGER_DELAYS:
                days, note = TRIGGER_DELAYS[trigger]
                trigger_days_added += days
                trigger_notes.append(note)

    if trigger_days_added > 0 and not db_available:
        # Only escalate if we used fallback (live data would already reflect triggers)
        timelines["p50"] = timelines["p50"] + trigger_days_added
        timelines["p90"] = timelines["p90"] + trigger_days_added
        timelines["p25"] = timelines["p25"] + (trigger_days_added // 2)

    # ── Step 2: Get revision risk ───────────────────────────────────
    revision_prob, revision_delay = _get_revision_info(permit_type)

    # ── Step 3: Calculate costs per scenario ───────────────────────
    daily_cost = monthly_carrying_cost / 30.44

    def scenario_costs(timeline_days: int) -> dict:
        carrying = daily_cost * timeline_days
        # Expected revision cost = P(revision) * revision_delay * daily_cost
        revision_cost = revision_prob * revision_delay * daily_cost
        total = carrying + revision_cost
        return {
            "timeline_days": timeline_days,
            "carrying_cost": carrying,
            "revision_cost": revision_cost,
            "total": total,
        }

    best = scenario_costs(timelines["p25"])
    likely = scenario_costs(timelines["p50"])
    worst = scenario_costs(timelines["p90"])

    # Break-even analysis: how much is one day of expediting worth?
    break_even_per_day = daily_cost * (1 + revision_prob)

    # ── Step 4: Format output ───────────────────────────────────────
    permit_label = _get_permit_type_label(permit_type)
    lines = [f"# Cost of Delay — {permit_label}\n"]

    if neighborhood:
        lines.append(f"**Neighborhood:** {neighborhood}")
    lines.append(f"**Monthly Carrying Cost:** {_format_currency(monthly_carrying_cost)}")
    lines.append(f"**Daily Rate:** {_format_currency(daily_cost)}/day")
    lines.append(f"**Revision Probability:** {revision_prob:.0%} (avg delay if revised: {revision_delay}d)\n")

    if trigger_notes:
        lines.append("**Active Delay Triggers:**")
        for note in trigger_notes:
            lines.append(f"- {note}")
        lines.append("")

    # Cost table
    lines.append("## Financial Exposure by Scenario\n")
    lines.append("| Scenario | Timeline | Carrying Cost | Revision Risk Cost | Total |")
    lines.append("|----------|----------|---------------|-------------------|-------|")
    lines.append(
        f"| Best (p25) | {best['timeline_days']}d | "
        f"{_format_currency(best['carrying_cost'])} | "
        f"{_format_currency(best['revision_cost'])} | "
        f"**{_format_currency(best['total'])}** |"
    )
    lines.append(
        f"| Likely (p50) | {likely['timeline_days']}d | "
        f"{_format_currency(likely['carrying_cost'])} | "
        f"{_format_currency(likely['revision_cost'])} | "
        f"**{_format_currency(likely['total'])}** |"
    )
    lines.append(
        f"| Worst (p90) | {worst['timeline_days']}d | "
        f"{_format_currency(worst['carrying_cost'])} | "
        f"{_format_currency(worst['revision_cost'])} | "
        f"**{_format_currency(worst['total'])}** |"
    )

    # Break-even analysis
    lines.append(f"\n## Break-Even Analysis\n")
    lines.append(
        f"Permit delays cost **{_format_currency(break_even_per_day)}/day** "
        f"(carrying + expected revision risk)."
    )
    lines.append(
        f"Any expediting service or premium that saves time is worth up to "
        f"**{_format_currency(break_even_per_day)}/day** — including the cost of:"
    )
    lines.append("- Pre-application meetings")
    lines.append("- Expedited plan check fee")
    lines.append("- CASp specialist for ADA compliance")
    lines.append("- Licensed professional with SF DBI track record")

    # Gap between best and worst (the "risk premium")
    risk_gap = worst["total"] - best["total"]
    lines.append(
        f"\n**Risk premium (worst vs. best case):** {_format_currency(risk_gap)} "
        f"over {worst['timeline_days'] - best['timeline_days']} additional days"
    )

    # OTC eligibility note
    is_otc_eligible = permit_type in OTC_ELIGIBLE_TYPES
    if is_otc_eligible:
        lines.append(
            f"\n> **OTC Eligible:** This permit type may qualify for Over-the-Counter "
            f"processing (same-day to 3 days). If eligible, total exposure could be "
            f"as low as {_format_currency(daily_cost * 3)}."
        )

    # Mitigation strategies
    strategies = MITIGATION_STRATEGIES.get(permit_type, MITIGATION_STRATEGIES["general"])
    lines.append(f"\n## Mitigation Strategies\n")
    for s in strategies:
        lines.append(f"- {s}")

    # Data source note
    lines.append(f"\n## Methodology\n")
    if db_available:
        lines.append("- Timelines from SF DBI historical permit data (station-sum velocity model)")
    else:
        lines.append(f"- Timelines: SF DBI historical averages for {permit_label}")
    lines.append(f"- Revision probability: {revision_prob:.0%} based on SF permit correction patterns")
    lines.append(f"- Revision cost = P(revision) × avg_revision_delay × daily_carrying_cost")
    lines.append(f"- Carrying cost = timeline_days × (monthly_cost / 30.44 days/month)")

    if not db_available:
        lines.append(
            "\n*Note: Live permit database unavailable — timelines from SF DBI historical averages. "
            "For project-specific timeline data, run `estimate_timeline` directly.*"
        )

    lines.append(f"\n{daily_delay_cost(monthly_carrying_cost)}")

    return "\n".join(lines)
