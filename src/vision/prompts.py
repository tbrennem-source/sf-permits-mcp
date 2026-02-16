"""Vision prompts for EPR compliance checks on architectural drawings.

Each prompt is designed for a specific EPR check or set of checks.
All prompts request structured JSON output for reliable parsing.
"""

SYSTEM_PROMPT_EPR = (
    "You are analyzing San Francisco building permit plan set PDFs for "
    "Electronic Plan Review (EPR) compliance. You are looking at individual "
    "pages of architectural/engineering drawings.\n\n"
    "Title blocks are usually in the bottom-right corner or along the right edge.\n"
    "Sheet numbers follow discipline prefixes: G (General), A (Architectural), "
    "S (Structural), M (Mechanical), E (Electrical), P (Plumbing), T (Title-24).\n"
    "Format is typically: PREFIX + NUMBER.NUMBER (e.g., A1.0, S2.1).\n\n"
    "Respond with structured JSON only. No markdown fences, no explanations "
    "outside the JSON."
)


# EPR-011: Cover sheet page count vs actual
PROMPT_COVER_PAGE_COUNT = (
    "Look at this cover sheet of an architectural plan set.\n\n"
    "Find the total sheet count or page count listed on this cover. It might appear in:\n"
    "- A sheet index/schedule table\n"
    "- Text like 'X SHEETS' or 'TOTAL SHEETS: X' or 'Page X of Y'\n"
    "- The sheet index listing individual sheet numbers\n\n"
    "Return JSON:\n"
    '{"found_count": true, "stated_count": 16, '
    '"sheet_index_entries": ["G0.0", "A1.0", "A1.1"], '
    '"location_description": "Sheet index table in upper right"}'
)


# EPR-012: 8.5"x11" blank area on cover for DBI stamping
PROMPT_COVER_BLANK_AREA = (
    "Look at this cover sheet of an architectural plan set.\n\n"
    "DBI requires an 8.5\" x 11\" blank/empty area on the cover sheet for permit "
    "stamping. This is typically a large white/empty rectangle, often in the "
    "upper-right or upper portion.\n\n"
    "Assess whether there is a sufficiently large blank area (approximately "
    "8.5\"x11\" — roughly 1/4 of an Arch D sheet) that is free of text, "
    "graphics, or drawing content.\n\n"
    "Return JSON:\n"
    '{"has_blank_area": true, "estimated_size": "approximately 8.5x11 inches", '
    '"location": "upper-right", "confidence": "high", "notes": ""}'
)


# EPR-013/014/015/016/018: Title block content on a drawing sheet
PROMPT_TITLE_BLOCK = (
    "Look at this architectural drawing sheet.\n\n"
    "Find the title block (usually bottom-right corner or right edge) and extract:\n"
    "1. Project address — the street address of the project\n"
    "2. Sheet number — like A1.0, S2.1, G0.0, etc.\n"
    "3. Sheet name/description — like 'FLOOR PLAN', 'ELEVATIONS', etc.\n"
    "4. Firm name or logo\n"
    "5. Professional stamp/signature — look for a circular/rectangular professional\n"
    "   engineer or architect stamp, registration numbers, signature marks\n\n"
    "Also assess:\n"
    "6. Is there a blank area approximately 2\"x2\" in or near the title block "
    "for reviewer stamps?\n\n"
    "Return JSON:\n"
    '{"project_address": "123 Main St, San Francisco", '
    '"sheet_number": "A1.0", "sheet_name": "FLOOR PLAN", '
    '"firm_name": "Smith Architecture", '
    '"has_professional_stamp": true, "has_signature": true, '
    '"has_2x2_blank": true, "blank_area_location": "bottom-right corner", '
    '"confidence": "high"}'
)


# EPR-022: Dense hatching patterns
PROMPT_DENSE_HATCHING = (
    "Look at this architectural drawing sheet.\n\n"
    "Assess whether this sheet contains dense cross-hatching or fill patterns "
    "that could cause rendering issues in Bluebeam Studio (the PDF review tool "
    "used by SF DBI plan reviewers).\n\n"
    "Dense hatching = tightly spaced repeating lines, crosshatch patterns, or "
    "heavy material fills that cover large areas of the drawing.\n\n"
    "Return JSON:\n"
    '{"has_dense_hatching": false, "severity": "none", '
    '"affected_areas": "", "recommendation": ""}'
)


# Full extraction for analyze_plans tool
PROMPT_FULL_EXTRACTION = (
    "Analyze this architectural drawing sheet thoroughly.\n\n"
    "Extract ALL visible information:\n\n"
    "1. **Title Block** (usually bottom-right):\n"
    "   - Project address, sheet number, sheet name\n"
    "   - Firm/company name, professional stamp (PE/RA number, state)\n"
    "   - Signature present (yes/no), date, scale, revision info\n\n"
    "2. **Drawing Content**:\n"
    "   - What type of drawing? (floor plan, elevation, section, detail, cover, etc.)\n"
    "   - Key dimensions or areas called out\n"
    "   - Occupancy labels (Group A, B, R, etc.)\n"
    "   - Code references (CBC, NFPA, etc.)\n"
    "   - Construction type indicators\n\n"
    "3. **Scope Indicators**:\n"
    "   - New work vs existing (dashed = existing, solid = new)\n"
    "   - Demolition notation\n"
    "   - Scope of work description if present\n\n"
    "Return JSON:\n"
    '{"page_type": "floor_plan", '
    '"title_block": {"project_address": null, "sheet_number": null, '
    '"sheet_name": null, "firm_name": null, '
    '"professional_stamp": {"present": false, "type": null, "number": null, "state": null}, '
    '"signature_present": false, "date": null, "scale": null, "revision": null}, '
    '"drawing_content": {"drawing_type": null, "key_dimensions": [], '
    '"occupancy_labels": [], "code_references": [], "construction_type": null}, '
    '"scope_indicators": {"has_new_work": false, "has_demolition": false, '
    '"scope_description": null}}'
)
