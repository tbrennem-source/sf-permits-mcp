"""Tool metadata catalog for the /docs API documentation page.

Organizes all 34 MCP tools into 7 categories with descriptions,
parameters, and example queries for the public-facing docs page.
"""

from typing import Any

TOOL_CATEGORIES: list[dict[str, Any]] = [
    {
        "id": "search-lookup",
        "name": "Search & Lookup",
        "description": "Search permits, properties, businesses, and entities across 18M+ government records.",
        "tools": [
            {
                "name": "search_permits",
                "description": "Search SF building permits with filters for neighborhood, type, status, cost, date, address, and description keywords.",
                "parameters": [
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Filter by neighborhood (e.g., 'Mission', 'SoMa')"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Filter by type (e.g., 'new construction', 'alterations')"},
                    {"name": "status", "type": "string", "required": False, "description": "Filter by status (e.g., 'issued', 'filed', 'complete')"},
                    {"name": "min_cost", "type": "number", "required": False, "description": "Minimum estimated cost"},
                    {"name": "max_cost", "type": "number", "required": False, "description": "Maximum estimated cost"},
                    {"name": "date_from", "type": "string", "required": False, "description": "Filed after this date (YYYY-MM-DD)"},
                    {"name": "date_to", "type": "string", "required": False, "description": "Filed before this date (YYYY-MM-DD)"},
                    {"name": "address", "type": "string", "required": False, "description": "Search by street name"},
                    {"name": "description_search", "type": "string", "required": False, "description": "Full-text search in permit description"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 20, max 200)"},
                ],
                "example": "Show me all new construction permits filed in the Mission in 2024",
            },
            {
                "name": "permit_lookup",
                "description": "Look up SF permits by number, address, or parcel. Shows full details and related permits.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Exact permit number (e.g., '202301015555')"},
                    {"name": "street_number", "type": "string", "required": False, "description": "Street number for address search"},
                    {"name": "street_name", "type": "string", "required": False, "description": "Street name for address search"},
                    {"name": "block", "type": "string", "required": False, "description": "SF assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "SF assessor lot number"},
                ],
                "example": "Look up permit 202301015555",
            },
            {
                "name": "get_permit_details",
                "description": "Get full details for a specific SF building permit by permit number.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": True, "description": "The permit number to retrieve"},
                ],
                "example": "Get full details for permit 202212106789",
            },
            {
                "name": "search_businesses",
                "description": "Search registered business locations in San Francisco by name or address.",
                "parameters": [
                    {"name": "business_name", "type": "string", "required": False, "description": "Search by DBA or ownership name"},
                    {"name": "address", "type": "string", "required": False, "description": "Search by street address"},
                    {"name": "zip_code", "type": "string", "required": False, "description": "Filter by zip code"},
                    {"name": "active_only", "type": "boolean", "required": False, "description": "Only show active businesses (default True)"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 20)"},
                ],
                "example": "Find businesses named 'Golden Gate' in zip code 94103",
            },
            {
                "name": "property_lookup",
                "description": "Look up property information for a San Francisco parcel including assessed value and zoning.",
                "parameters": [
                    {"name": "address", "type": "string", "required": False, "description": "Street address to search"},
                    {"name": "block", "type": "string", "required": False, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "Assessor lot number"},
                    {"name": "tax_year", "type": "string", "required": False, "description": "Tax roll year (e.g., '2024')"},
                ],
                "example": "What is the assessed value and zoning of 123 Main St SF?",
            },
            {
                "name": "search_entity",
                "description": "Search for a person or company across all permit contact data. Returns portfolio summary and network connections.",
                "parameters": [
                    {"name": "name", "type": "string", "required": True, "description": "Name to search for (person or company)"},
                    {"name": "entity_type", "type": "string", "required": False, "description": "Filter by type: contractor, architect, engineer, owner, agent"},
                ],
                "example": "Find all permits associated with contractor John Smith Construction",
            },
            {
                "name": "search_addenda",
                "description": "Search 3.9M+ plan review routing records by permit, station, reviewer, department, or date range.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Filter by permit number"},
                    {"name": "station", "type": "string", "required": False, "description": "Review station (e.g., 'BLDG', 'SFFD-HQ', 'CP-ZOC')"},
                    {"name": "reviewer", "type": "string", "required": False, "description": "Plan checker name (LAST FIRST format)"},
                    {"name": "department", "type": "string", "required": False, "description": "Department code (DBI, CPC, PUC, DPW, SFFD)"},
                    {"name": "review_result", "type": "string", "required": False, "description": "Filter by outcome (Approved, Issued Comments)"},
                    {"name": "date_from", "type": "string", "required": False, "description": "Filter by finish_date start (YYYY-MM-DD)"},
                    {"name": "date_to", "type": "string", "required": False, "description": "Filter by finish_date end (YYYY-MM-DD)"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 50)"},
                ],
                "example": "Show routing history for permit 202301015555",
            },
        ],
    },
    {
        "id": "analytics",
        "name": "Analytics",
        "description": "Aggregate statistics, inspection records, complaints, violations, and severity scoring.",
        "tools": [
            {
                "name": "permit_stats",
                "description": "Get aggregate statistics on SF building permits grouped by neighborhood, type, status, month, or year.",
                "parameters": [
                    {"name": "group_by", "type": "string", "required": False, "description": "Aggregation dimension: neighborhood, type, status, month, year"},
                    {"name": "date_from", "type": "string", "required": False, "description": "Start date filter (YYYY-MM-DD)"},
                    {"name": "date_to", "type": "string", "required": False, "description": "End date filter (YYYY-MM-DD)"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Filter to specific neighborhood"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Filter to specific permit type"},
                ],
                "example": "How many permits were filed in each SF neighborhood in 2024?",
            },
            {
                "name": "search_inspections",
                "description": "Search DBI building inspection records by permit, address, inspector, result, or date.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Filter by permit number"},
                    {"name": "address", "type": "string", "required": False, "description": "Search by street name"},
                    {"name": "block", "type": "string", "required": False, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "Assessor lot number"},
                    {"name": "inspector", "type": "string", "required": False, "description": "Inspector name (partial match)"},
                    {"name": "result", "type": "string", "required": False, "description": "Inspection result (approved, disapproved)"},
                    {"name": "date_from", "type": "string", "required": False, "description": "Scheduled after this date"},
                    {"name": "date_to", "type": "string", "required": False, "description": "Scheduled before this date"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 50)"},
                ],
                "example": "Show all failed inspections at 100 Van Ness Ave in 2024",
            },
            {
                "name": "search_complaints",
                "description": "Search DBI building complaints filed against properties by address, status, or description.",
                "parameters": [
                    {"name": "address", "type": "string", "required": False, "description": "Search by street name"},
                    {"name": "street_number", "type": "string", "required": False, "description": "Street number"},
                    {"name": "block", "type": "string", "required": False, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "Assessor lot number"},
                    {"name": "status", "type": "string", "required": False, "description": "Complaint status (open, abated, closed)"},
                    {"name": "description_search", "type": "string", "required": False, "description": "Full-text search in complaint description"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 20)"},
                ],
                "example": "Are there any open complaints at 500 Market Street?",
            },
            {
                "name": "permit_severity",
                "description": "Score a permit's complexity and risk level based on type, cost, scope, and historical patterns.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Permit number to score"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Permit type if number unknown"},
                    {"name": "estimated_cost", "type": "number", "required": False, "description": "Estimated construction cost"},
                    {"name": "description", "type": "string", "required": False, "description": "Permit description"},
                ],
                "example": "How complex is this $2M commercial tenant improvement permit?",
            },
            {
                "name": "property_health",
                "description": "Aggregate health signal for a property — permits, complaints, violations, inspection pass rates.",
                "parameters": [
                    {"name": "block", "type": "string", "required": True, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": True, "description": "Assessor lot number"},
                ],
                "example": "What is the overall health status of block 3507 lot 004?",
            },
        ],
    },
    {
        "id": "intelligence",
        "name": "Intelligence",
        "description": "AI-powered permit guidance: timelines, fees, predictions, revision risk, and contractor recommendations.",
        "tools": [
            {
                "name": "estimate_timeline",
                "description": "Estimate permit processing timeline using historical data and station velocity models (p25/p50/p75/p90 percentiles).",
                "parameters": [
                    {"name": "permit_type", "type": "string", "required": True, "description": "Type: alterations, new_construction, demolition, otc"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "SF neighborhood name"},
                    {"name": "review_path", "type": "string", "required": False, "description": "otc or in_house"},
                    {"name": "estimated_cost", "type": "number", "required": False, "description": "Construction cost for bracket matching"},
                    {"name": "triggers", "type": "array", "required": False, "description": "Delay factors (e.g., change_of_use, historic)"},
                    {"name": "monthly_carrying_cost", "type": "number", "required": False, "description": "Monthly cost to compute delay financial impact"},
                ],
                "example": "How long will a $500K kitchen remodel permit take in Noe Valley?",
            },
            {
                "name": "estimate_fees",
                "description": "Estimate permit fees using the DBI fee schedule plus historical data for statistical context.",
                "parameters": [
                    {"name": "permit_type", "type": "string", "required": True, "description": "alterations, new_construction, or no_plans"},
                    {"name": "estimated_construction_cost", "type": "number", "required": True, "description": "Project valuation in dollars"},
                    {"name": "square_footage", "type": "number", "required": False, "description": "Optional project area for per-sqft analysis"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Optional SF neighborhood"},
                    {"name": "project_type", "type": "string", "required": False, "description": "Specific type (e.g., restaurant, adu)"},
                ],
                "example": "What are the permit fees for a $1.2M new construction in the Mission?",
            },
            {
                "name": "predict_permits",
                "description": "Predict required permits, forms, review path, and agency routing for a project description.",
                "parameters": [
                    {"name": "project_description", "type": "string", "required": True, "description": "Natural language description of the project"},
                    {"name": "address", "type": "string", "required": False, "description": "Optional street address for property context"},
                    {"name": "estimated_cost", "type": "number", "required": False, "description": "Optional construction cost estimate"},
                    {"name": "square_footage", "type": "number", "required": False, "description": "Optional project area in square feet"},
                ],
                "example": "What permits do I need to convert a garage to an ADU in SF?",
            },
            {
                "name": "revision_risk",
                "description": "Estimate revision probability and timeline impact from historical permit patterns.",
                "parameters": [
                    {"name": "permit_type", "type": "string", "required": True, "description": "Type of permit"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Optional SF neighborhood name"},
                    {"name": "project_type", "type": "string", "required": False, "description": "Specific type (e.g., restaurant, adu, seismic)"},
                    {"name": "review_path", "type": "string", "required": False, "description": "otc or in_house"},
                ],
                "example": "How likely are revisions for a restaurant conversion in SoMa?",
            },
            {
                "name": "recommend_consultants",
                "description": "Recommend top land use consultants, contractors, or architects for a project based on scoring criteria.",
                "parameters": [
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Target neighborhood for matching"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Type of permit"},
                    {"name": "entity_type", "type": "string", "required": False, "description": "consultant, contractor, architect, engineer, electrician, plumber"},
                    {"name": "address", "type": "string", "required": False, "description": "Property street name"},
                    {"name": "block", "type": "string", "required": False, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "Assessor lot number"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Number of recommendations (default 5)"},
                ],
                "example": "Who are the top architects for historic building work in Pacific Heights?",
            },
            {
                "name": "required_documents",
                "description": "Generate a document checklist for permit submission based on form type, review path, and agency routing.",
                "parameters": [
                    {"name": "permit_forms", "type": "array", "required": True, "description": "Required forms (e.g., ['Form 3/8'])"},
                    {"name": "review_path", "type": "string", "required": True, "description": "otc or in_house"},
                    {"name": "agency_routing", "type": "array", "required": False, "description": "Agencies reviewing (e.g., Planning, SFFD, DPH)"},
                    {"name": "project_type", "type": "string", "required": False, "description": "Specific type (restaurant, adu, seismic)"},
                    {"name": "triggers", "type": "array", "required": False, "description": "Additional triggers (change_of_use, ada, historic)"},
                ],
                "example": "What documents do I need for an in-house review restaurant permit?",
            },
            {
                "name": "search_violations",
                "description": "Search DBI Notices of Violation issued against properties by address, status, or category.",
                "parameters": [
                    {"name": "address", "type": "string", "required": False, "description": "Search by street name"},
                    {"name": "street_number", "type": "string", "required": False, "description": "Street number"},
                    {"name": "block", "type": "string", "required": False, "description": "Assessor block number"},
                    {"name": "lot", "type": "string", "required": False, "description": "Assessor lot number"},
                    {"name": "status", "type": "string", "required": False, "description": "NOV status (open, closed, complied)"},
                    {"name": "category", "type": "string", "required": False, "description": "NOV category (building, electrical, plumbing)"},
                    {"name": "description_search", "type": "string", "required": False, "description": "Full-text search in violation description"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 20)"},
                ],
                "example": "Show open violations at 500 Market Street",
            },
        ],
    },
    {
        "id": "advanced",
        "name": "Advanced",
        "description": "Diagnose stuck permits, run what-if simulations, calculate delay costs, and predict next review stations.",
        "tools": [
            {
                "name": "diagnose_stuck_permit",
                "description": "Diagnose why a permit is stuck in review and recommend actions to move it forward.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": True, "description": "The stuck permit number to diagnose"},
                ],
                "example": "My permit 202301015555 has been at SFFD for 6 weeks — what's wrong?",
            },
            {
                "name": "simulate_what_if",
                "description": "Simulate how project changes affect timeline and fees (e.g., adding ADU, changing scope).",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Base permit to simulate against"},
                    {"name": "scenario", "type": "string", "required": True, "description": "Description of the change to simulate"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "SF neighborhood"},
                ],
                "example": "What happens to my timeline if I add a rooftop deck to my renovation?",
            },
            {
                "name": "calculate_delay_cost",
                "description": "Calculate the financial impact of permit delays given monthly carrying costs.",
                "parameters": [
                    {"name": "monthly_carrying_cost", "type": "number", "required": True, "description": "Monthly cost (rent, mortgage, storage, etc.)"},
                    {"name": "expected_delay_days", "type": "number", "required": False, "description": "Expected delay in days"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Permit type for delay estimation"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "SF neighborhood"},
                ],
                "example": "My $8K/month rent starts in 60 days — what does a permit delay cost me?",
            },
            {
                "name": "predict_next_stations",
                "description": "Predict which review stations a permit will hit next based on current routing status.",
                "parameters": [
                    {"name": "permit_number", "type": "string", "required": False, "description": "Permit number to analyze"},
                    {"name": "current_station", "type": "string", "required": False, "description": "Current station if permit number unknown"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Permit type"},
                    {"name": "project_description", "type": "string", "required": False, "description": "Project description for routing prediction"},
                ],
                "example": "What stations will my permit hit after SFFD approval?",
            },
        ],
    },
    {
        "id": "plan-analysis",
        "name": "Plan Analysis",
        "description": "AI-powered PDF plan set validation and analysis for DBI Electronic Plan Review (EPR) compliance.",
        "tools": [
            {
                "name": "validate_plans",
                "description": "Validate a PDF plan set against SF DBI EPR requirements (file size, encryption, dimensions, fonts).",
                "parameters": [
                    {"name": "pdf_bytes", "type": "string", "required": True, "description": "Raw bytes or base64-encoded PDF"},
                    {"name": "filename", "type": "string", "required": False, "description": "Original filename for naming convention check"},
                    {"name": "is_site_permit_addendum", "type": "boolean", "required": False, "description": "Use 350MB limit instead of 250MB"},
                    {"name": "enable_vision", "type": "boolean", "required": False, "description": "Run Claude Vision checks on sampled pages"},
                ],
                "example": "Check if my PDF plan set meets DBI EPR requirements before submission",
            },
            {
                "name": "analyze_plans",
                "description": "Full AI vision analysis of a plan set: title blocks, stamps, EPR compliance, sheet index, and recommendations.",
                "parameters": [
                    {"name": "pdf_bytes", "type": "string", "required": True, "description": "Raw bytes or base64-encoded PDF"},
                    {"name": "filename", "type": "string", "required": False, "description": "Original filename"},
                    {"name": "project_description", "type": "string", "required": False, "description": "Project description for completeness assessment"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Permit type (alterations, new_construction)"},
                    {"name": "property_address", "type": "string", "required": False, "description": "Project address for address verification"},
                    {"name": "submission_stage", "type": "string", "required": False, "description": "preliminary, permit, or resubmittal"},
                ],
                "example": "Analyze my architectural plans for a kitchen remodel — are they ready to submit?",
            },
        ],
    },
    {
        "id": "network",
        "name": "Network",
        "description": "Entity relationship networks, anomaly detection, and similar project discovery.",
        "tools": [
            {
                "name": "entity_network",
                "description": "Get the relationship network around a contractor, architect, or owner — who they work with and how often.",
                "parameters": [
                    {"name": "entity_id", "type": "string", "required": True, "description": "Entity ID from search_entity results"},
                    {"name": "hops", "type": "integer", "required": False, "description": "Relationship hops to traverse (1-3, default 1)"},
                ],
                "example": "Who does architect Jane Smith typically work with?",
            },
            {
                "name": "network_anomalies",
                "description": "Scan for anomalous patterns in the permit network — unusual concentrations, relationships, or timing.",
                "parameters": [
                    {"name": "min_permits", "type": "integer", "required": False, "description": "Minimum permit count to consider an entity (default 10)"},
                ],
                "example": "Are there any unusual patterns in SF permit contractor relationships?",
            },
            {
                "name": "similar_projects",
                "description": "Find similar completed projects to benchmark timelines, costs, and outcomes for planning.",
                "parameters": [
                    {"name": "project_description", "type": "string", "required": True, "description": "Description of your project"},
                    {"name": "neighborhood", "type": "string", "required": False, "description": "Target neighborhood"},
                    {"name": "permit_type", "type": "string", "required": False, "description": "Type of permit"},
                    {"name": "estimated_cost", "type": "number", "required": False, "description": "Estimated project cost"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 5)"},
                ],
                "example": "Find similar kitchen remodel permits in Noe Valley around $150K",
            },
        ],
    },
    {
        "id": "system",
        "name": "System",
        "description": "Direct database queries, source code access, schema introspection, and test inventory for power users.",
        "tools": [
            {
                "name": "run_query",
                "description": "Run a read-only SQL query against the production database for custom analytical queries.",
                "parameters": [
                    {"name": "sql", "type": "string", "required": True, "description": "SELECT query only (INSERT/UPDATE/DELETE rejected)"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max rows returned (default 100, max 1000)"},
                ],
                "example": "SELECT neighborhood, COUNT(*) FROM permits WHERE status='issued' GROUP BY 1 ORDER BY 2 DESC LIMIT 10",
            },
            {
                "name": "schema_info",
                "description": "Get database schema information — all tables with row counts, or detailed column info for a specific table.",
                "parameters": [
                    {"name": "table", "type": "string", "required": False, "description": "Specific table to inspect (omit to list all tables)"},
                ],
                "example": "What columns does the permits table have?",
            },
            {
                "name": "read_source",
                "description": "Read a source file from the sf-permits-mcp repository for debugging or understanding implementation.",
                "parameters": [
                    {"name": "path", "type": "string", "required": True, "description": "Relative path from repo root (e.g., 'web/brief.py')"},
                    {"name": "line_start", "type": "integer", "required": False, "description": "Optional start line (1-indexed)"},
                    {"name": "line_end", "type": "integer", "required": False, "description": "Optional end line"},
                ],
                "example": "Show me the source code for the timeline estimation tool",
            },
            {
                "name": "list_tests",
                "description": "List test files and test functions in the repository, with optional pattern filtering.",
                "parameters": [
                    {"name": "pattern", "type": "string", "required": False, "description": "Optional filter (e.g., 'severity', 'brief')"},
                    {"name": "show_status", "type": "boolean", "required": False, "description": "Run pytest collect-only for detailed counts"},
                ],
                "example": "What tests exist for the timeline estimation feature?",
            },
            {
                "name": "search_source",
                "description": "Search the codebase for a pattern using ripgrep — find implementations, usages, and definitions.",
                "parameters": [
                    {"name": "pattern", "type": "string", "required": True, "description": "Search string or regex"},
                    {"name": "file_pattern", "type": "string", "required": False, "description": "Glob for file types (default *.py)"},
                    {"name": "max_results", "type": "integer", "required": False, "description": "Cap on matches (default 20)"},
                ],
                "example": "Find all uses of the station_velocity function",
            },
            {
                "name": "list_feedback",
                "description": "Query user feedback submitted to sfpermits.ai — bugs, suggestions, questions from the feedback queue.",
                "parameters": [
                    {"name": "status", "type": "string", "required": False, "description": "Filter by status: new, reviewed, resolved, wontfix"},
                    {"name": "feedback_type", "type": "string", "required": False, "description": "Filter by type: bug, suggestion, question"},
                    {"name": "days_back", "type": "integer", "required": False, "description": "Only return items from the last N days"},
                    {"name": "limit", "type": "integer", "required": False, "description": "Max results (default 50)"},
                ],
                "example": "What bug reports came in this week?",
            },
        ],
    },
]


def get_tool_catalog() -> dict:
    """Return the full tool catalog organized by category.

    Returns:
        dict with:
        - categories: list of category dicts with tools
        - total_tools: int count of all tools
        - total_categories: int count of categories
    """
    total = sum(len(cat["tools"]) for cat in TOOL_CATEGORIES)
    return {
        "categories": TOOL_CATEGORIES,
        "total_tools": total,
        "total_categories": len(TOOL_CATEGORIES),
    }
