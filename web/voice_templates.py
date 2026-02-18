"""Voice calibration scenario templates.

Each scenario is defined by (audience, situation) and includes:
- key: unique identifier (audience_situation)
- audience/situation labels and descriptions
- template_text: a generic "textbook" response that Amy will rewrite
- context_hint: a one-liner describing the scenario

Templates are deliberately bland and formal so the expert's rewrites
create a clear style signal. The bigger the diff, the more we learn.
"""

from __future__ import annotations

AUDIENCES = [
    {
        "key": "homeowner",
        "label": "Homeowner",
        "description": "Someone who doesn't know permits, needs hand-holding",
    },
    {
        "key": "contractor",
        "label": "Contractor",
        "description": "Knows the trade, wants quick code references",
    },
    {
        "key": "architect",
        "label": "Architect / Engineer",
        "description": "Technical peer, wants specifics",
    },
    {
        "key": "city_official",
        "label": "City Official / Plan Checker",
        "description": "Formal, show expertise",
    },
    {
        "key": "colleague",
        "label": "Another Expeditor",
        "description": "Shorthand OK, insider language",
    },
    {
        "key": "realtor_attorney",
        "label": "Real Estate Agent / Attorney",
        "description": "Liability-aware, timeline-focused",
    },
    {
        "key": "property_manager",
        "label": "Property Manager",
        "description": "Repeat customer, ongoing relationship",
    },
]

SITUATIONS = [
    {
        "key": "good_news",
        "label": "Good News",
        "description": "Permit approved, inspection passed, etc.",
    },
    {
        "key": "bad_news",
        "label": "Bad News / Correction",
        "description": "Plan checker flagged issues, permit denied, etc.",
    },
    {
        "key": "process_explanation",
        "label": "Explaining a Process",
        "description": "How ADU permits work, what to expect, etc.",
    },
    {
        "key": "urgent",
        "label": "Urgent / Time-Sensitive",
        "description": "Permit expiring, deadline approaching, etc.",
    },
    {
        "key": "follow_up",
        "label": "Follow-up / Check-in",
        "description": "Status update, gentle reminder",
    },
    {
        "key": "first_contact",
        "label": "First Contact / Intro",
        "description": "First response to someone new",
    },
    {
        "key": "needs_more_info",
        "label": "Need More Info / Suggest Meeting",
        "description": "Can't fully answer — give a nugget, offer a call",
    },
    {
        "key": "prospect_hook",
        "label": "Prospect (Not Yet Client)",
        "description": "Give value, seed the conversation, suggest engagement",
    },
]

# Lookup dicts
AUDIENCE_MAP = {a["key"]: a for a in AUDIENCES}
SITUATION_MAP = {s["key"]: s for s in SITUATIONS}


# ---------------------------------------------------------------------------
# Scenario templates — ~15 highest-value combinations
# ---------------------------------------------------------------------------

SCENARIOS: list[dict] = [
    # ── Homeowner × all 8 situations ──────────────────────────────
    {
        "key": "homeowner_good_news",
        "audience": "homeowner",
        "situation": "good_news",
        "context_hint": "A homeowner's permit was just approved.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "I am pleased to inform you that your building permit application "
            "has been approved by the Department of Building Inspection. "
            "The permit is now ready for issuance.\n\n"
            "To collect your permit, please visit DBI at 49 South Van Ness "
            "Avenue during business hours. You will need to bring a valid "
            "photo ID and payment for any remaining fees.\n\n"
            "Please note that the permit is valid for the timeframe specified "
            "in the approval documents. Work must commence within the specified "
            "period to avoid expiration.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_bad_news",
        "audience": "homeowner",
        "situation": "bad_news",
        "context_hint": "A plan checker flagged issues on a homeowner's remodel plans.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "After review, the plan checker has identified several items that "
            "need to be addressed before your permit can be approved. The "
            "correction notice is attached.\n\n"
            "The main items requiring attention are:\n"
            "1. [Specific correction item]\n"
            "2. [Specific correction item]\n\n"
            "Please have your architect or engineer revise the plans accordingly "
            "and resubmit for review. The resubmission process typically takes "
            "2-4 weeks for re-review.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_process_explanation",
        "audience": "homeowner",
        "situation": "process_explanation",
        "context_hint": "A homeowner asks how the ADU permit process works in SF.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "Thank you for your inquiry regarding the ADU permit process in "
            "San Francisco. Below is an overview of the steps involved.\n\n"
            "Step 1: Determine eligibility under Planning Code Section 207(c)(4).\n"
            "Step 2: Prepare architectural drawings per DBI requirements.\n"
            "Step 3: Submit application to DBI with all required documents.\n"
            "Step 4: Plan review (typically 8-16 weeks).\n"
            "Step 5: Address any plan check corrections.\n"
            "Step 6: Permit issuance and construction.\n"
            "Step 7: Final inspections.\n\n"
            "Fees typically range from $15,000 to $30,000 depending on scope. "
            "The total timeline from application to permit issuance is "
            "approximately 6-12 months.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_urgent",
        "audience": "homeowner",
        "situation": "urgent",
        "context_hint": "A homeowner's permit is about to expire.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "This is to inform you that your building permit is approaching "
            "its expiration date. Per San Francisco Building Code, permits "
            "expire if work has not commenced within the specified period.\n\n"
            "To avoid expiration, you must either:\n"
            "1. Begin construction and schedule your first inspection, or\n"
            "2. File for a permit extension before the expiration date.\n\n"
            "Extension applications require a written request and may involve "
            "additional fees. Please act promptly to preserve your permit.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_follow_up",
        "audience": "homeowner",
        "situation": "follow_up",
        "context_hint": "Checking in with a homeowner about their permit status.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "I am writing to provide an update on the status of your permit "
            "application. As of the latest check, your application is currently "
            "in plan review.\n\n"
            "The estimated timeline for completion of review is [X] weeks. "
            "I will notify you as soon as there is a status change or if any "
            "additional information is required.\n\n"
            "Please do not hesitate to reach out if you have any questions.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_first_contact",
        "audience": "homeowner",
        "situation": "first_contact",
        "context_hint": "First response to a homeowner who submitted a question.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "Thank you for reaching out regarding your project. I would be "
            "happy to assist you with your permit needs.\n\n"
            "Based on your description, it appears you will need a building "
            "permit for this type of work. The general process involves "
            "submitting architectural plans to the Department of Building "
            "Inspection for review.\n\n"
            "I have prepared some initial guidance below based on the "
            "information you provided. Please review and let me know if "
            "you have any questions.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_needs_more_info",
        "audience": "homeowner",
        "situation": "needs_more_info",
        "context_hint": "A homeowner asks a complex question that needs more discussion.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "Thank you for your question. This is a great topic and there are "
            "several factors that come into play depending on your specific "
            "situation.\n\n"
            "Based on what you've described, the key consideration is "
            "[one relevant code or process point]. This often determines "
            "the overall approach and timeline.\n\n"
            "However, to give you accurate guidance, I would need to know "
            "more about your specific property and project scope. I'd recommend "
            "we schedule a brief call to discuss the details.\n\n"
            "Would you be available for a 15-minute phone call this week? "
            "Please let me know what times work for you.\n\n"
            "Best regards"
        ),
    },
    {
        "key": "homeowner_prospect_hook",
        "audience": "homeowner",
        "situation": "prospect_hook",
        "context_hint": "A prospective homeowner client asks about permits — give value, suggest engagement.",
        "template_text": (
            "Dear Homeowner,\n\n"
            "Thank you for your inquiry. You're asking the right questions, "
            "and I can provide some helpful context.\n\n"
            "For the type of project you're describing, San Francisco requires "
            "a building permit per CBC Section [X]. The typical timeline is "
            "[Y] months and fees run approximately $[Z].\n\n"
            "One important thing to know: [one specific, helpful fact that "
            "demonstrates expertise].\n\n"
            "Every property in SF has unique considerations — zoning, historical "
            "status, setbacks — that can significantly affect the permit path. "
            "I'd love to take a quick look at your specific situation.\n\n"
            "Would you like to set up a brief call? I can review your property "
            "details and give you a clearer picture of what to expect.\n\n"
            "Best regards"
        ),
    },

    # ── Contractor × 3 key situations ─────────────────────────────
    {
        "key": "contractor_bad_news",
        "audience": "contractor",
        "situation": "bad_news",
        "context_hint": "Plan check corrections came back on a contractor's project.",
        "template_text": (
            "Hi,\n\n"
            "The plan check corrections are in. Main items:\n\n"
            "1. Fire separation between units does not meet CBC 706.1 requirements\n"
            "2. Structural calcs need PE stamp per SFBC 107A.1\n"
            "3. Energy compliance docs (CF1R) missing from set\n\n"
            "Please coordinate with the project engineer to address items 1-2 "
            "and submit revised plans with all corrections marked. "
            "Resubmission turnaround is typically 2-3 weeks.\n\n"
            "Let me know if you need the full correction letter.\n\n"
            "Regards"
        ),
    },
    {
        "key": "contractor_process_explanation",
        "audience": "contractor",
        "situation": "process_explanation",
        "context_hint": "A contractor asks about the tenant improvement permit process.",
        "template_text": (
            "Hi,\n\n"
            "For a commercial tenant improvement in SF, the permit process "
            "is as follows:\n\n"
            "1. Submit plans to DBI with completed application (form 8)\n"
            "2. Routing: plans go to Planning, Fire, DPH as applicable\n"
            "3. Plan review: 4-8 weeks for standard TI, 8-16 for change of use\n"
            "4. Corrections if needed (1-2 rounds typical)\n"
            "5. Permit issuance — bring contractor license info\n\n"
            "Fees are based on project valuation. For a standard TI under $100K, "
            "expect approximately $5,000-8,000 in city fees.\n\n"
            "Key items that slow things down: missing energy compliance, "
            "incomplete ADA path of travel, fire sprinkler scope changes.\n\n"
            "Regards"
        ),
    },
    {
        "key": "contractor_needs_more_info",
        "audience": "contractor",
        "situation": "needs_more_info",
        "context_hint": "A contractor asks about a complex scope — need to discuss specifics.",
        "template_text": (
            "Hi,\n\n"
            "Good question. The answer depends on a few factors specific to "
            "your project — particularly the occupancy classification and "
            "whether this triggers a change of use.\n\n"
            "Quick reference: CBC Table 508.4 governs the separation "
            "requirements, but the Planning Code overlay may add restrictions "
            "depending on the zoning district.\n\n"
            "I'd want to review the specific address and scope before giving "
            "you a definitive answer. Can we jump on a quick call to go "
            "through the details?\n\n"
            "Regards"
        ),
    },

    # ── Architect × 2 key situations ──────────────────────────────
    {
        "key": "architect_bad_news",
        "audience": "architect",
        "situation": "bad_news",
        "context_hint": "Relaying plan check corrections to the project architect.",
        "template_text": (
            "Hi,\n\n"
            "The plan checker has returned corrections on the [project] set. "
            "The correction letter is attached. Key items:\n\n"
            "1. Sheet A2.1: Fire-rated assembly detail does not reference "
            "a listed system per CBC 703.2\n"
            "2. Sheet S1: Structural calculations incomplete — need lateral "
            "analysis per ASCE 7-22 Chapter 12\n"
            "3. Energy: CEC Title 24 compliance forms (CF1R-ENV-01) not "
            "included in the submission\n"
            "4. Accessibility: path of travel from public way to unit entry "
            "not shown per CBC Chapter 11B\n\n"
            "Please revise and resubmit. Standard re-review turnaround is "
            "2-3 weeks. Let me know if you have questions on any items.\n\n"
            "Regards"
        ),
    },
    {
        "key": "architect_process_explanation",
        "audience": "architect",
        "situation": "process_explanation",
        "context_hint": "An architect asks about the plan review routing process.",
        "template_text": (
            "Hi,\n\n"
            "For this project type, the routing through DBI is:\n\n"
            "1. Central Permit Bureau (intake, fee assessment)\n"
            "2. Planning Department (zoning compliance, 311 notification if applicable)\n"
            "3. DBI Plan Review (building code, structural, accessibility)\n"
            "4. Fire Department (if sprinkler/fire alarm scope included)\n"
            "5. DPH (if food service, ventilation, or hazmat involved)\n\n"
            "Total review timeline: 8-16 weeks first pass, depending on "
            "project complexity and current backlog.\n\n"
            "Tips for faster review: include a code analysis sheet (A0.0), "
            "cross-reference CBC sections on applicable details, and submit "
            "energy docs with the initial set rather than deferred.\n\n"
            "Regards"
        ),
    },

    # ── Generic × prospect_hook (any audience) ────────────────────
    {
        "key": "general_prospect_hook",
        "audience": "general",
        "situation": "prospect_hook",
        "context_hint": "A potential client of unknown type asks a general question — give value, build rapport.",
        "template_text": (
            "Hi,\n\n"
            "Thanks for reaching out. That's a common question and I can "
            "share some quick guidance.\n\n"
            "For the type of work you're describing, San Francisco typically "
            "requires [relevant permit type]. The key code section is [X], "
            "and the timeline usually runs [Y] months.\n\n"
            "One thing most people don't know: [one useful insider tip]. "
            "This can save significant time and money if handled correctly "
            "from the start.\n\n"
            "Every project has unique factors that affect the permit path. "
            "I'd be happy to take a closer look at your specific situation "
            "if you'd like to chat — no commitment needed.\n\n"
            "Best regards"
        ),
    },

    # ── Generic × needs_more_info (any audience) ──────────────────
    {
        "key": "general_needs_more_info",
        "audience": "general",
        "situation": "needs_more_info",
        "context_hint": "Complex question from anyone — give a nugget, suggest a conversation.",
        "template_text": (
            "Hi,\n\n"
            "Great question. The short answer is that it depends on a few "
            "specifics about your property and project scope.\n\n"
            "Here's what I can tell you right now: [one concrete, helpful "
            "fact with a code reference]. This is the main factor that will "
            "drive the timeline and approach.\n\n"
            "To give you a complete answer, I'd need to review [what info "
            "is missing — address, scope, existing conditions]. Would you "
            "be available for a brief call? I can usually sort this out in "
            "about 10-15 minutes.\n\n"
            "Best regards"
        ),
    },
]

# Quick lookup by scenario key
SCENARIO_MAP: dict[str, dict] = {s["key"]: s for s in SCENARIOS}

# Group scenarios by audience for the admin UI
def get_scenarios_by_audience() -> dict[str, list[dict]]:
    """Return scenarios grouped by audience key, maintaining order."""
    grouped: dict[str, list[dict]] = {}
    for s in SCENARIOS:
        audience = s["audience"]
        if audience not in grouped:
            grouped[audience] = []
        grouped[audience].append(s)
    return grouped
