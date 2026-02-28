"""Tool: what_if_simulator — Compare how project variations change timeline, fees, and revision risk.

Takes a base project description and a list of variations (e.g., "Add bathroom", "Use ADU path"),
runs predict_permits / estimate_timeline / estimate_fees / revision_risk on each, and returns
a side-by-side comparison table.

Designed to help expeditors and homeowners quickly answer "what changes if I scope up / down?"
before committing to a full permit application.
"""

import asyncio
import logging
import re
from typing import Any

# Import sub-tools at module level so they can be patched in tests.
from src.tools.predict_permits import predict_permits
from src.tools.estimate_timeline import estimate_timeline
from src.tools.estimate_fees import estimate_fees
from src.tools.revision_risk import revision_risk

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers: parse headline values from tool markdown output
# ---------------------------------------------------------------------------

_CURRENCY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")
_DAYS_RE = re.compile(r"(\d+)\s*(?:–|-)\s*(\d+)\s*(?:business\s+)?days?", re.IGNORECASE)
_DAYS_SINGLE_RE = re.compile(r"(\d+)\s+(?:business\s+)?days?", re.IGNORECASE)
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)%")
_RISK_RE = re.compile(r"\*\*Risk Level:\*\*\s*(HIGH|MODERATE|LOW)", re.IGNORECASE)
_REVIEW_PATH_RE = re.compile(
    r"(?:Review Path|review_path)[:\s]+[*`]*(OTC|Over-the-Counter|In-house|In[_\s]House)[*`]*",
    re.IGNORECASE,
)
_PERMIT_TYPE_RE = re.compile(
    r"(?:Permit Type|permit_type)[:\s]+[*`]*([^\n*`]+)[*`]*",
    re.IGNORECASE,
)
_P50_RE = re.compile(r"[Pp]50[^:\n]*:\s*(\d+)\s+days?", re.IGNORECASE)
_TOTAL_FEE_RE = re.compile(
    r"\|\s*\*\*Total DBI Fees\*\*\s*\|\s*\*\*\$([\d,]+(?:\.\d+)?)\*\*",
    re.IGNORECASE,
)
_CONFIDENCE_RE = re.compile(r"\*\*Confidence:\*\*\s*(\w+)", re.IGNORECASE)


def _extract_permits(md: str) -> str:
    """Extract a short permit-type summary from predict_permits markdown."""
    # Look for "Required Permits" section header then first bullet
    match = re.search(r"## Required Permits?\n+(.*?)(?:\n\n|\n##|$)", md, re.DOTALL)
    if match:
        chunk = match.group(1).strip()
        # Take first 2 lines as summary
        lines = [l.lstrip("- *•").strip() for l in chunk.splitlines() if l.strip()]
        return "; ".join(lines[:2]) or "N/A"

    # Fall back: look for "**Permit Form:**" or "**Primary Permit:**"
    for pattern in [
        r"\*\*Permit Form:\*\*\s*([^\n]+)",
        r"\*\*Primary Permit:\*\*\s*([^\n]+)",
        r"\*\*Permit Type:\*\*\s*([^\n]+)",
    ]:
        m = re.search(pattern, md, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    return "N/A"


def _extract_review_path(md: str) -> str:
    """Extract OTC or In-house review path from predict_permits markdown."""
    m = _REVIEW_PATH_RE.search(md)
    if m:
        raw = m.group(1).strip()
        if re.search(r"otc|over.the.counter", raw, re.IGNORECASE):
            return "OTC"
        return "In-house"

    # Also check for "**Review Path:**"
    m2 = re.search(r"\*\*Review Path:\*\*\s*([^\n]+)", md, re.IGNORECASE)
    if m2:
        raw = m2.group(1).strip()
        if re.search(r"otc|over.the.counter", raw, re.IGNORECASE):
            return "OTC"
        if re.search(r"in.house|in_house", raw, re.IGNORECASE):
            return "In-house"
        return raw[:30]

    return "N/A"


def _extract_p50(md: str) -> str:
    """Extract p50 timeline from estimate_timeline markdown."""
    m = _P50_RE.search(md)
    if m:
        return f"{m.group(1)} days"

    # Fall back to a range pattern like "60–90 business days"
    m2 = _DAYS_RE.search(md)
    if m2:
        return f"{m2.group(1)}–{m2.group(2)} days"

    # Single day value near "median" or "typical"
    for pattern in [
        r"Median[^:\n]*:\s*(\d+)\s+days?",
        r"Typical[^:\n]*:\s*(\d+)\s+days?",
        r"(\d+)\s+business\s+days",
    ]:
        m3 = re.search(pattern, md, re.IGNORECASE)
        if m3:
            return f"{m3.group(1)} days"

    return "N/A"


def _extract_p75(md: str) -> str:
    """Extract p75 timeline from estimate_timeline markdown."""
    m = re.search(r"[Pp]75[^:\n]*:\s*(\d+)\s+days?", md, re.IGNORECASE)
    if m:
        return f"{m.group(1)} days"
    return "N/A"


def _extract_total_fee(md: str) -> str:
    """Extract Total DBI Fee from estimate_fees markdown."""
    # Try the bold table cell pattern first
    m = _TOTAL_FEE_RE.search(md)
    if m:
        return f"${m.group(1)}"

    # Fallback: scan for "Fee Estimate" section and look for the first large dollar amount
    m2 = _CURRENCY_RE.search(md)
    if m2:
        return f"${m2.group(1)}"

    return "N/A"


def _extract_revision_risk(md: str) -> str:
    """Extract revision risk level + rate from revision_risk markdown."""
    risk_m = _RISK_RE.search(md)
    rate_m = re.search(r"Revision Rate:\*\*\s*([\d.]+%)", md, re.IGNORECASE)

    if risk_m and rate_m:
        return f"{risk_m.group(1)} ({rate_m.group(1)})"
    if risk_m:
        return risk_m.group(1)
    if rate_m:
        return rate_m.group(1)

    # LUCK-based fallback text
    if "15-20%" in md or "15–20%" in md:
        return "MODERATE (15–20% est.)"
    return "N/A"


# ---------------------------------------------------------------------------
# Per-scenario evaluation
# ---------------------------------------------------------------------------

async def _evaluate_scenario(
    label: str,
    description: str,
) -> dict[str, str]:
    """Run all four sub-tools for one scenario and return extracted headline values.

    Returns a dict with keys:
        label, description, permits, review_path, timeline_p50, timeline_p75,
        fees, revision_risk, notes
    """
    result: dict[str, str] = {
        "label": label,
        "description": description,
        "permits": "N/A",
        "review_path": "N/A",
        "timeline_p50": "N/A",
        "timeline_p75": "N/A",
        "fees": "N/A",
        "revision_risk": "N/A",
        "notes": "",
    }

    # --- Parse cost from description ---
    cost: float | None = None
    cost_m = re.search(r"\$([\d,]+)(?:K|k)?", description)
    if cost_m:
        raw = cost_m.group(1).replace(",", "")
        multiplier = 1000 if re.search(r"\$[\d,]+K", description, re.IGNORECASE) else 1
        try:
            cost = float(raw) * multiplier
        except ValueError:
            cost = None

    # Also handle "80K" / "80k" without dollar sign
    if cost is None:
        cost_k = re.search(r"(\d+)\s*[Kk]\b", description)
        if cost_k:
            try:
                cost = float(cost_k.group(1)) * 1000
            except ValueError:
                pass

    # --- 1. predict_permits ---
    predict_md = ""
    try:
        predict_result = await predict_permits(
            project_description=description,
            estimated_cost=cost,
        )
        if isinstance(predict_result, tuple):
            predict_md = predict_result[0]
        else:
            predict_md = str(predict_result)
        result["permits"] = _extract_permits(predict_md)
        result["review_path"] = _extract_review_path(predict_md)
    except Exception as e:
        logger.warning("predict_permits failed for scenario '%s': %s", label, e)
        result["notes"] += f"predict_permits error; "

    # --- 2. estimate_timeline ---
    timeline_md = ""
    try:
        # Infer permit_type from predict output or default to "alterations"
        permit_type_for_timeline = "alterations"
        if re.search(r"new.construction|ground.up", description, re.IGNORECASE):
            permit_type_for_timeline = "new_construction"
        elif re.search(r"otc|over.the.counter", predict_md, re.IGNORECASE):
            permit_type_for_timeline = "otc"

        review_path_for_timeline = None
        rp = result["review_path"]
        if rp == "OTC":
            review_path_for_timeline = "otc"
        elif rp == "In-house":
            review_path_for_timeline = "in_house"

        timeline_result = await estimate_timeline(
            permit_type=permit_type_for_timeline,
            review_path=review_path_for_timeline,
            estimated_cost=cost,
        )
        if isinstance(timeline_result, tuple):
            timeline_md = timeline_result[0]
        else:
            timeline_md = str(timeline_result)
        result["timeline_p50"] = _extract_p50(timeline_md)
        result["timeline_p75"] = _extract_p75(timeline_md)
    except Exception as e:
        logger.warning("estimate_timeline failed for scenario '%s': %s", label, e)
        result["notes"] += f"estimate_timeline error; "

    # --- 3. estimate_fees ---
    fees_md = ""
    try:
        # Infer fee category
        fee_category = "alterations"
        if re.search(r"new.construction|ground.up", description, re.IGNORECASE):
            fee_category = "new_construction"

        fee_cost = cost if cost else 50000.0

        fees_result = await estimate_fees(
            permit_type=fee_category,
            estimated_construction_cost=fee_cost,
        )
        if isinstance(fees_result, tuple):
            fees_md = fees_result[0]
        else:
            fees_md = str(fees_result)
        result["fees"] = _extract_total_fee(fees_md)
    except Exception as e:
        logger.warning("estimate_fees failed for scenario '%s': %s", label, e)
        result["notes"] += f"estimate_fees error; "

    # --- 4. revision_risk ---
    try:
        # Infer permit_type for revision risk
        rr_permit_type = "alterations"
        if re.search(r"new.construction|ground.up", description, re.IGNORECASE):
            rr_permit_type = "new_construction"

        rr_result = await revision_risk(
            permit_type=rr_permit_type,
        )
        if isinstance(rr_result, tuple):
            rr_md = rr_result[0]
        else:
            rr_md = str(rr_result)
        result["revision_risk"] = _extract_revision_risk(rr_md)
    except Exception as e:
        logger.warning("revision_risk failed for scenario '%s': %s", label, e)
        result["notes"] += f"revision_risk error; "

    result["notes"] = result["notes"].rstrip("; ")
    return result


# ---------------------------------------------------------------------------
# Main public function
# ---------------------------------------------------------------------------

async def simulate_what_if(
    base_description: str,
    variations: list[dict[str, str]],
) -> str:
    """Compare how project variations change timeline, fees, and revision risk.

    Runs predict_permits, estimate_timeline, estimate_fees, and revision_risk for
    each scenario (base + each variation) and formats the results as a comparison
    table. Each sub-tool call is awaited; errors in individual tools yield "N/A"
    rather than propagating.

    Args:
        base_description: Natural-language description of the base project,
            e.g. "Kitchen remodel in the Mission, $80K".
        variations: List of dicts, each with required "label" (short name) and
            "description" (natural-language scope), e.g.:
            [{"label": "Add bathroom", "description": "Kitchen + bathroom, $120K"}]

    Returns:
        Formatted markdown string with a comparison table and per-scenario notes.
    """
    if not base_description or not base_description.strip():
        return "# What-If Simulator Error\n\nbase_description is required."

    # Build the full list: base scenario first, then variations
    scenarios: list[dict[str, str]] = [
        {"label": "Base", "description": base_description},
    ]
    for v in variations or []:
        label = str(v.get("label", "Variation")).strip() or "Variation"
        description = str(v.get("description", base_description)).strip() or base_description
        scenarios.append({"label": label, "description": description})

    # Evaluate all scenarios in parallel
    tasks = [
        _evaluate_scenario(s["label"], s["description"])
        for s in scenarios
    ]
    results: list[dict[str, str]] = await asyncio.gather(*tasks)

    # ---------------------------------------------------------------------------
    # Format comparison table
    # ---------------------------------------------------------------------------
    lines: list[str] = [
        "# What-If Permit Simulator\n",
        f"**Base project:** {base_description}\n",
        f"**Scenarios evaluated:** {len(results)} (1 base + {len(results) - 1} variation(s))\n",
        "---\n",
        "## Comparison Table\n",
    ]

    # Table header
    lines.append("| Scenario | Description | Permits | Review Path | Timeline (p50) | Timeline (p75) | Est. DBI Fees | Revision Risk |")
    lines.append("|---|---|---|---|---|---|---|---|")

    # Table rows
    for r in results:
        label = r["label"]
        description = r["description"]
        # Truncate long descriptions for readability
        if len(description) > 60:
            description = description[:57] + "..."
        permits = r["permits"]
        if len(permits) > 40:
            permits = permits[:37] + "..."
        row = (
            f"| **{label}** "
            f"| {description} "
            f"| {permits} "
            f"| {r['review_path']} "
            f"| {r['timeline_p50']} "
            f"| {r['timeline_p75']} "
            f"| {r['fees']} "
            f"| {r['revision_risk']} |"
        )
        lines.append(row)

    lines.append("\n---\n")

    # ---------------------------------------------------------------------------
    # Delta summary: compare each variation to base
    # ---------------------------------------------------------------------------
    if len(results) > 1:
        lines.append("## Delta vs. Base\n")
        base = results[0]
        for var in results[1:]:
            lines.append(f"### {var['label']}\n")

            # Review path change
            if var["review_path"] != base["review_path"] and var["review_path"] != "N/A" and base["review_path"] != "N/A":
                lines.append(
                    f"- **Review path:** {base['review_path']} → {var['review_path']} "
                    f"({'significant change — may add weeks' if var['review_path'] == 'In-house' else 'may shorten timeline'})"
                )

            # Timeline change
            if var["timeline_p50"] != base["timeline_p50"] and var["timeline_p50"] != "N/A" and base["timeline_p50"] != "N/A":
                lines.append(f"- **Timeline (p50):** {base['timeline_p50']} → {var['timeline_p50']}")

            # Fee change
            if var["fees"] != base["fees"] and var["fees"] != "N/A" and base["fees"] != "N/A":
                lines.append(f"- **Fees:** {base['fees']} → {var['fees']}")

            # Revision risk change
            if var["revision_risk"] != base["revision_risk"] and var["revision_risk"] != "N/A" and base["revision_risk"] != "N/A":
                lines.append(f"- **Revision risk:** {base['revision_risk']} → {var['revision_risk']}")

            if not any([
                var["review_path"] != base["review_path"],
                var["timeline_p50"] != base["timeline_p50"],
                var["fees"] != base["fees"],
                var["revision_risk"] != base["revision_risk"],
            ]):
                lines.append("- No significant headline differences detected vs. base scenario")

            lines.append("")

    # ---------------------------------------------------------------------------
    # Per-scenario notes (errors, data gaps)
    # ---------------------------------------------------------------------------
    notes_present = [r for r in results if r.get("notes")]
    if notes_present:
        lines.append("## Data Notes\n")
        for r in notes_present:
            lines.append(f"- **{r['label']}:** {r['notes']}")
        lines.append("")

    # ---------------------------------------------------------------------------
    # Footer
    # ---------------------------------------------------------------------------
    lines.append("---\n")
    lines.append("## About This Simulation\n")
    lines.append(
        "Each scenario is independently evaluated using: "
        "`predict_permits` (permit types + review path), "
        "`estimate_timeline` (historical p50/p75 processing times), "
        "`estimate_fees` (DBI Table 1A-A fee schedule), and "
        "`revision_risk` (correction probability from 1.1M+ permit records)."
    )
    lines.append("")
    lines.append(
        "**Limitations:** Headline values are extracted from markdown outputs and may not "
        "capture all nuance. Use the individual tools for full breakdowns. "
        "Timeline and fee estimates depend on data availability in the local permit database."
    )
    lines.append("")
    lines.append("*Generated by what_if_simulator v1.0 (QS8)*")

    return "\n".join(lines)
