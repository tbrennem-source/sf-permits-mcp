#!/usr/bin/env python3
"""Generate system_predictions.md — run 5 Amy stress-test scenarios through all 5 tools."""

import asyncio
import sys
import os
from datetime import date

# Ensure the project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.predict_permits import predict_permits
from src.tools.estimate_fees import estimate_fees
from src.tools.estimate_timeline import estimate_timeline
from src.tools.required_documents import required_documents
from src.tools.revision_risk import revision_risk


SCENARIOS = [
    {
        "id": "A",
        "title": "Residential Kitchen Remodel (Noe Valley, $85K)",
        "predict": {
            "project_description": "Gut renovation of residential kitchen in Noe Valley, removing a non-bearing wall, relocating gas line, new electrical panel. Budget $85K.",
            "estimated_cost": 85000,
        },
        "fees": {
            "permit_type": "alterations",
            "estimated_construction_cost": 85000,
            "neighborhood": "Noe Valley",
        },
        "timeline": {
            "permit_type": "alterations",
            "neighborhood": "Noe Valley",
            "estimated_cost": 85000,
        },
        "docs": {
            "permit_forms": ["Form 3/8"],
            "review_path": "in_house",
            "agency_routing": ["DBI (Building)", "DBI Mechanical/Electrical"],
            "project_type": "general_alteration",
        },
        "risk": {
            "permit_type": "alterations",
            "neighborhood": "Noe Valley",
            "project_type": "general_alteration",
            "review_path": "in_house",
        },
    },
    {
        "id": "B",
        "title": "ADU Over Garage (Sunset, $180K)",
        "predict": {
            "project_description": "Convert existing detached garage to ADU with kitchenette and bathroom in the Sunset District. 450 sq ft, new plumbing/electrical, $180K budget.",
            "estimated_cost": 180000,
            "square_footage": 450,
        },
        "fees": {
            "permit_type": "alterations",
            "estimated_construction_cost": 180000,
            "square_footage": 450,
            "neighborhood": "Sunset/Parkside",
            "project_type": "adu",
        },
        "timeline": {
            "permit_type": "alterations",
            "neighborhood": "Sunset/Parkside",
            "estimated_cost": 180000,
        },
        "docs": {
            "permit_forms": ["Form 3/8"],
            "review_path": "in_house",
            "agency_routing": ["DBI (Building)", "Planning", "DBI Mechanical/Electrical"],
            "project_type": "adu",
            "triggers": ["adu", "new_plumbing", "new_electrical"],
        },
        "risk": {
            "permit_type": "alterations",
            "neighborhood": "Sunset/Parkside",
            "project_type": "adu",
            "review_path": "in_house",
        },
    },
    {
        "id": "C",
        "title": "Commercial Tenant Improvement (Financial District, $350K)",
        "predict": {
            "project_description": "Office tenant improvement in Financial District, 3,500 sq ft. New walls, HVAC modifications, lighting, ADA-compliant restrooms. Budget $350K.",
            "estimated_cost": 350000,
            "square_footage": 3500,
        },
        "fees": {
            "permit_type": "alterations",
            "estimated_construction_cost": 350000,
            "square_footage": 3500,
            "neighborhood": "Financial District/South Beach",
            "project_type": "commercial_ti",
        },
        "timeline": {
            "permit_type": "alterations",
            "neighborhood": "Financial District/South Beach",
            "estimated_cost": 350000,
        },
        "docs": {
            "permit_forms": ["Form 3/8"],
            "review_path": "in_house",
            "agency_routing": ["DBI (Building)", "Planning", "DBI Mechanical/Electrical", "DPW (Public Works)"],
            "project_type": "commercial_ti",
            "triggers": ["ada_path_of_travel", "hvac", "title24"],
        },
        "risk": {
            "permit_type": "alterations",
            "neighborhood": "Financial District/South Beach",
            "project_type": "commercial_ti",
            "review_path": "in_house",
        },
    },
    {
        "id": "D",
        "title": "Restaurant Conversion (Mission, $250K)",
        "predict": {
            "project_description": "Convert vacant retail space to restaurant with Type I hood, grease interceptor, 49 seats, full commercial kitchen. Mission District, $250K budget.",
            "estimated_cost": 250000,
        },
        "fees": {
            "permit_type": "alterations",
            "estimated_construction_cost": 250000,
            "neighborhood": "Mission",
            "project_type": "restaurant",
        },
        "timeline": {
            "permit_type": "alterations",
            "neighborhood": "Mission",
            "estimated_cost": 250000,
        },
        "docs": {
            "permit_forms": ["Form 3/8"],
            "review_path": "in_house",
            "agency_routing": ["DBI (Building)", "Planning", "DPH (Public Health)", "SFFD (Fire)", "DBI Mechanical/Electrical"],
            "project_type": "restaurant",
            "triggers": ["dph_food_facility", "fire_suppression", "grease_interceptor", "change_of_use", "title24"],
        },
        "risk": {
            "permit_type": "alterations",
            "neighborhood": "Mission",
            "project_type": "restaurant",
            "review_path": "in_house",
        },
    },
    {
        "id": "E",
        "title": "Historic Building Renovation (Pacific Heights, $2.5M)",
        "predict": {
            "project_description": "Major renovation of Article 10 landmark building in Pacific Heights. Seismic retrofit, new MEP systems, ADA compliance, restore historic facade. 8,000 sq ft, $2.5M budget.",
            "estimated_cost": 2500000,
            "square_footage": 8000,
        },
        "fees": {
            "permit_type": "alterations",
            "estimated_construction_cost": 2500000,
            "square_footage": 8000,
            "neighborhood": "Pacific Heights",
            "project_type": "historic",
        },
        "timeline": {
            "permit_type": "alterations",
            "neighborhood": "Pacific Heights",
            "estimated_cost": 2500000,
        },
        "docs": {
            "permit_forms": ["Form 3/8"],
            "review_path": "in_house",
            "agency_routing": ["DBI (Building)", "Planning", "SFFD (Fire)", "DPW (Public Works)"],
            "project_type": "historic",
            "triggers": ["historic_preservation", "seismic_retrofit", "ada_path_of_travel", "title24"],
        },
        "risk": {
            "permit_type": "alterations",
            "neighborhood": "Pacific Heights",
            "project_type": "historic",
            "review_path": "in_house",
        },
    },
]


async def run_scenario(scenario: dict) -> str:
    """Run all 5 tools for a scenario and return formatted markdown."""
    sid = scenario["id"]
    title = scenario["title"]
    lines = [f"## Scenario {sid}: {title}", ""]

    # 1. Predict Permits
    lines.append("### Predicted Permits")
    lines.append("")
    try:
        result = await predict_permits(**scenario["predict"])
        lines.append(result)
    except Exception as e:
        lines.append(f"**ERROR:** {e}")
    lines.append("")

    # 2. Estimated Fees
    lines.append("### Estimated Fees")
    lines.append("")
    try:
        result = await estimate_fees(**scenario["fees"])
        lines.append(result)
    except Exception as e:
        lines.append(f"**ERROR:** {e}")
    lines.append("")

    # 3. Estimated Timeline
    lines.append("### Estimated Timeline")
    lines.append("")
    try:
        result = await estimate_timeline(**scenario["timeline"])
        lines.append(result)
    except Exception as e:
        lines.append(f"**ERROR:** {e}")
    lines.append("")

    # 4. Required Documents
    lines.append("### Required Documents")
    lines.append("")
    try:
        result = await required_documents(**scenario["docs"])
        lines.append(result)
    except Exception as e:
        lines.append(f"**ERROR:** {e}")
    lines.append("")

    # 5. Revision Risk
    lines.append("### Revision Risk")
    lines.append("")
    try:
        result = await revision_risk(**scenario["risk"])
        lines.append(result)
    except Exception as e:
        lines.append(f"**ERROR:** {e}")
    lines.append("")

    return "\n".join(lines)


async def main():
    header = f"""# System Predictions — Amy Stress Test

Generated: {date.today()}
Tools: predict_permits, estimate_fees, estimate_timeline, required_documents, revision_risk
Source citations: Enabled (17-source registry with clickable links)

---

"""
    parts = [header]
    for scenario in SCENARIOS:
        print(f"Running scenario {scenario['id']}: {scenario['title']}...")
        result = await run_scenario(scenario)
        parts.append(result)
        parts.append("---\n\n")

    output = "\n".join(parts)

    outpath = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data", "knowledge", "system_predictions.md",
    )
    with open(outpath, "w") as f:
        f.write(output)
    print(f"\nWritten to {outpath} ({len(output):,} chars)")


if __name__ == "__main__":
    asyncio.run(main())
