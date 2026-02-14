"""Tool: predict_permits — Predict required permits, forms, routing, and review path."""

import json
from src.tools.knowledge_base import get_knowledge_base

# Project type keywords mapped from semantic index concepts
# These map to special_project_types in the decision tree
PROJECT_TYPE_KEYWORDS = {
    "restaurant": ["restaurant", "food service", "commercial kitchen", "grease trap",
                    "hood", "ventilation", "dining", "food facility", "grease interceptor",
                    "type i hood", "kitchen hood"],
    "adu": ["adu", "accessory dwelling", "in-law", "granny flat", "garage conversion",
            "in-law unit", "secondary unit"],
    "seismic": ["seismic", "earthquake", "retrofit", "soft story", "foundation bolting",
                "brace and bolt", "anchor bolt", "seismic upgrade", "seismic retrofit",
                "seismic strengthening"],
    "commercial_ti": ["tenant improvement", "office buildout", "commercial alteration",
                      "ti", "buildout", "commercial interior", "office remodel",
                      "commercial renovation"],
    "adaptive_reuse": ["adaptive reuse", "conversion", "warehouse to residential",
                       "commercial to residential", "office to residential"],
    "solar": ["solar", "photovoltaic", "pv", "clean energy", "battery storage",
              "ev charging", "energy storage"],
    "demolition": ["demolition", "demolish", "tear down", "raze"],
    "change_of_use": ["change of use", "change of occupancy", "change occupancy",
                      "retail to", "office to", "residential to"],
    "historic": ["historic", "landmark", "preservation", "heritage",
                 "article 10", "article 11", "conservation district"],
    "new_construction": ["new construction", "new building", "ground up",
                         "build new", "new structure"],
}


def _extract_project_types(description: str, scope_override: list[str] | None) -> list[str]:
    """Extract project type categories from description text."""
    if scope_override:
        return scope_override

    desc_lower = description.lower()
    matched = []
    for ptype, keywords in PROJECT_TYPE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            matched.append(ptype)

    # Default to general alteration if nothing matched
    if not matched:
        matched.append("general_alteration")
    return matched


def _determine_form(project_types: list[str], kb) -> dict:
    """Determine which permit form is needed."""
    dt = kb.decision_tree.get("steps", {}).get("step_2_which_form", {})
    logic = dt.get("decision_logic", [])

    if "new_construction" in project_types:
        return {"form": "Form 1/2", "reason": "New construction", "notes": "Mark Form 1 (non-wood) or Form 2 (wood frame)"}
    if "demolition" in project_types:
        return {"form": "Form 6", "reason": "Demolition", "notes": "May be paired with Form 1/2 for replacement construction"}
    # Most alterations use Form 3/8
    return {"form": "Form 3/8", "reason": "Alterations/repairs to existing building",
            "notes": "Mark Form 3 for in-house review, Form 8 for OTC-eligible projects"}


def _determine_review_path(project_types: list[str], estimated_cost: float | None, kb) -> dict:
    """Determine OTC vs in-house review path."""
    otc = kb.otc_criteria

    # Projects that are always in-house
    always_inhouse = [
        "new_construction", "demolition", "change_of_use", "adu",
        "adaptive_reuse", "historic",
    ]
    for pt in project_types:
        if pt in always_inhouse:
            return {
                "path": "in_house",
                "reason": f"'{pt}' projects require in-house review",
                "confidence": "high",
            }

    # Check the not-OTC list
    not_otc = otc.get("not_otc_requires_inhouse", {}).get("projects", [])
    not_otc_lower = [p.lower() if isinstance(p, str) else p.get("description", "").lower() for p in not_otc]

    # Restaurant to full restaurant is always in-house
    if "restaurant" in project_types and "change_of_use" in project_types:
        return {"path": "in_house", "reason": "Restaurant change of use requires in-house review", "confidence": "high"}

    # Simple residential scope might be OTC
    if "general_alteration" in project_types or "commercial_ti" in project_types:
        if estimated_cost and estimated_cost < 50000:
            return {
                "path": "likely_otc",
                "reason": "Small scope alteration may qualify for OTC — verify with DBI",
                "confidence": "medium",
            }
        return {
            "path": "likely_in_house",
            "reason": "Scope likely exceeds OTC one-hour review threshold",
            "confidence": "medium",
        }

    if "seismic" in project_types:
        # Voluntary brace-and-bolt can be OTC
        return {
            "path": "depends",
            "reason": "Voluntary brace/bolt (S-09) is OTC; mandatory/extensive seismic retrofit is in-house",
            "confidence": "medium",
        }

    if "solar" in project_types:
        return {
            "path": "likely_otc",
            "reason": "Solar/PV installations are typically OTC with plans; qualifies for priority processing",
            "confidence": "medium",
        }

    return {"path": "likely_in_house", "reason": "Default to in-house for unclassified scope", "confidence": "low"}


def _determine_agency_routing(project_types: list[str], kb) -> list[dict]:
    """Determine which agencies must review the permit."""
    agencies = []

    # Almost everything goes to BLDG
    agencies.append({"agency": "DBI (Building)", "required": True, "reason": "All permitted work"})

    # Planning triggers
    planning_triggers = ["change_of_use", "new_construction", "demolition", "adu",
                         "adaptive_reuse", "historic", "restaurant"]
    if any(pt in project_types for pt in planning_triggers):
        agencies.append({"agency": "Planning", "required": True,
                         "reason": "Change of use, new construction, demolition, exterior changes, or historic resource"})

    # SFFD triggers
    fire_triggers = ["restaurant", "new_construction", "change_of_use", "historic"]
    if any(pt in project_types for pt in fire_triggers):
        agencies.append({"agency": "SFFD (Fire)", "required": True,
                         "reason": "Fire code review — restaurant hood/suppression, new construction, or occupancy change"})

    # DPH triggers (food service)
    if "restaurant" in project_types:
        agencies.append({"agency": "DPH (Public Health)", "required": True,
                         "reason": "Health permit for food service establishment"})

    # MECH/MECH-E for commercial work
    if any(pt in project_types for pt in ["commercial_ti", "restaurant", "new_construction"]):
        agencies.append({"agency": "DBI Mechanical/Electrical", "required": True,
                         "reason": "HVAC, electrical, or commercial kitchen systems"})

    # PUC for new plumbing
    if any(pt in project_types for pt in ["restaurant", "adu", "new_construction"]):
        agencies.append({"agency": "SFPUC", "conditional": True,
                         "reason": "New plumbing fixtures or water service"})

    # BSM for exterior/ROW work
    if any(pt in project_types for pt in ["new_construction", "restaurant", "demolition"]):
        agencies.append({"agency": "DPW/BSM", "conditional": True,
                         "reason": "Work in or adjacent to public right-of-way"})

    return agencies


def _determine_special_requirements(project_types: list[str], kb) -> list[dict]:
    """Determine special requirements based on project type."""
    reqs = []

    if "restaurant" in project_types:
        reqs.extend([
            {"requirement": "Planning zoning verification", "details": "Confirm restaurant use is permitted at site"},
            {"requirement": "DPH health permit application", "details": "Food preparation workflow diagram + equipment schedule"},
            {"requirement": "Type I hood fire suppression", "details": "Automatic suppression system for grease-producing equipment"},
            {"requirement": "Grease interceptor sizing", "details": "Grease trap calculations per plumbing code"},
            {"requirement": "ADA compliance", "details": "Path of travel and restroom upgrades per CBC Chapter 11B"},
        ])

    if "adu" in project_types:
        reqs.extend([
            {"requirement": "ADU pre-approval application", "details": "Separate ADU application process for detached ADUs"},
            {"requirement": "Fire separation", "details": "Fire separation between ADU and primary dwelling"},
            {"requirement": "Separate utility connections", "details": "May need separate water/electric meters"},
        ])

    if "seismic" in project_types:
        reqs.extend([
            {"requirement": "Structural engineering report", "details": "Licensed structural engineer evaluation"},
            {"requirement": "Priority processing eligibility", "details": "Voluntary/mandatory seismic upgrades per AB-004"},
        ])

    if "historic" in project_types:
        reqs.extend([
            {"requirement": "Historic preservation review", "details": "Certificate of Appropriateness from HPC (Article 10) or Permit to Alter (Article 11)"},
            {"requirement": "Secretary of Interior Standards", "details": "All work must comply with SOI Standards for Treatment of Historic Properties"},
        ])

    if "change_of_use" in project_types:
        reqs.extend([
            {"requirement": "Section 311 notification", "details": "30-day neighborhood notification period (cannot go OTC during notification)"},
        ])

    if "new_construction" in project_types:
        reqs.extend([
            {"requirement": "Fire flow study", "details": "SFFD fire flow analysis for new construction"},
            {"requirement": "Stormwater management plan", "details": "Required if 5,000+ sq ft impervious surfaces"},
            {"requirement": "Geotechnical report", "details": "May be required depending on site conditions"},
        ])

    return reqs


async def predict_permits(
    project_description: str,
    address: str | None = None,
    estimated_cost: float | None = None,
    square_footage: float | None = None,
    scope_keywords: list[str] | None = None,
) -> str:
    """Predict required permits, forms, review path, and agency routing for a project.

    Walks the SF permit decision tree based on project description to predict:
    - Required permit types and forms
    - OTC vs in-house review path
    - Which city agencies must review
    - Special requirements and triggers
    - Confidence levels for each prediction

    Args:
        project_description: Natural language description of the project
        address: Optional street address for property context
        estimated_cost: Optional construction cost estimate
        square_footage: Optional project area in square feet
        scope_keywords: Optional explicit project type keywords to override auto-extraction

    Returns:
        Formatted prediction with permits, routing, requirements, and confidence.
    """
    kb = get_knowledge_base()

    # Extract project types from description
    project_types = _extract_project_types(project_description, scope_keywords)

    # Also match semantic index concepts for richer context
    concepts = kb.match_concepts(project_description)

    # Walk decision tree
    form = _determine_form(project_types, kb)
    review_path = _determine_review_path(project_types, estimated_cost, kb)
    agency_routing = _determine_agency_routing(project_types, kb)
    special_requirements = _determine_special_requirements(project_types, kb)

    # Build result
    result = {
        "project_description": project_description,
        "detected_project_types": project_types,
        "matched_concepts": concepts[:10],
        "permits_needed": {
            "building_permit": True,
            "form": form,
            "electrical_permit": any(pt in project_types for pt in ["restaurant", "commercial_ti", "new_construction", "adu"]),
            "plumbing_permit": any(pt in project_types for pt in ["restaurant", "adu", "new_construction"]),
            "planning_approval": "Planning" in [a["agency"] for a in agency_routing],
        },
        "review_path": review_path,
        "agency_routing": agency_routing,
        "special_requirements": special_requirements,
        "confidence_summary": {
            "overall": review_path.get("confidence", "medium"),
            "form_selection": kb.get_step_confidence(2),
            "review_path": kb.get_step_confidence(3),
            "agency_routing": kb.get_step_confidence(4),
            "documents": kb.get_step_confidence(5),
        },
        "gaps": [],
    }

    # Note any gaps
    if not estimated_cost:
        result["gaps"].append("No cost estimate provided — OTC eligibility and fee estimates less accurate")
    if not address:
        result["gaps"].append("No address provided — cannot check zoning, historic status, or neighborhood-specific rules")
    if "general_alteration" in project_types:
        result["gaps"].append("Could not classify specific project type — predictions are generalized")

    # Format output
    lines = ["# Permit Prediction\n"]
    lines.append(f"**Project:** {project_description}")
    if address:
        lines.append(f"**Address:** {address}")
    if estimated_cost:
        lines.append(f"**Estimated Cost:** ${estimated_cost:,.0f}")
    if square_footage:
        lines.append(f"**Square Footage:** {square_footage:,.0f}")
    lines.append(f"\n**Detected Project Types:** {', '.join(project_types)}")
    if concepts:
        lines.append(f"**Matched Concepts:** {', '.join(concepts[:10])}")

    lines.append(f"\n## Permit Form\n")
    lines.append(f"**Form:** {form['form']}")
    lines.append(f"**Reason:** {form['reason']}")
    lines.append(f"**Notes:** {form['notes']}")

    lines.append(f"\n## Review Path\n")
    lines.append(f"**Path:** {review_path['path']}")
    lines.append(f"**Reason:** {review_path['reason']}")
    lines.append(f"**Confidence:** {review_path['confidence']}")

    lines.append(f"\n## Agency Routing\n")
    for a in agency_routing:
        status = "Required" if a.get("required") else "Conditional"
        lines.append(f"- **{a['agency']}** ({status}): {a['reason']}")

    if special_requirements:
        lines.append(f"\n## Special Requirements\n")
        for r in special_requirements:
            lines.append(f"- **{r['requirement']}:** {r['details']}")

    lines.append(f"\n## Confidence Summary\n")
    for k, v in result["confidence_summary"].items():
        lines.append(f"- {k}: {v}")

    if result["gaps"]:
        lines.append(f"\n## Gaps / Caveats\n")
        for g in result["gaps"]:
            lines.append(f"- {g}")

    return "\n".join(lines)
