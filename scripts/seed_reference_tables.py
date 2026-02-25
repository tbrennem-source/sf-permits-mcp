"""Seed reference tables for predict_permits.

Populates three tables from tier1 knowledge-base JSON files and the
hardcoded rules extracted from predict_permits.py:

  ref_zoning_routing   — zoning code → agency routing flags
  ref_permit_forms     — project type → required permit form
  ref_agency_triggers  — trigger keyword → agency routing

All INSERTs are idempotent (ON CONFLICT DO UPDATE / INSERT OR REPLACE).

Usage:
    python -m scripts.seed_reference_tables
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Seed data — extracted from predict_permits.py hardcoded logic and tier1 JSON
# ---------------------------------------------------------------------------

# ref_zoning_routing seed rows
# Derived from SF Planning Code zoning categories and G-20 routing rules.
# Key SF zoning codes and their routing implications.
ZONING_ROUTING_ROWS = [
    # Residential – House Districts
    ("RH-1",    "Residential House - One Family",          False, False, False, False, "40-X",  "Single-family detached; minimal planning triggers for interior work"),
    ("RH-1(D)", "Residential House - One Family (Detached)", False, False, False, False, "40-X", "Detached single-family; hillside rules may apply"),
    ("RH-1(S)", "Residential House - One Family (Small)",   False, False, False, False, "40-X", "Small lot single-family"),
    ("RH-2",    "Residential House - Two Family",           False, False, False, False, "40-X",  "Two-family; Planning triggered by unit add/remove"),
    ("RH-3",    "Residential House - Three Family",         False, False, False, False, "40-X",  "Three-family; unit changes trigger Planning"),
    # Residential – Mixed Districts
    ("RM-1",    "Residential Mixed - Low Density",          False, False, False, False, "40-X",  "Low-density mixed residential"),
    ("RM-2",    "Residential Mixed - Moderate Density",     False, False, False, False, "65-A",  "Moderate-density mixed residential"),
    ("RM-3",    "Residential Mixed - Medium Density",       False, False, False, False, "65-A",  "Medium-density mixed residential"),
    ("RM-4",    "Residential Mixed - High Density",         True,  False, False, False, "65-A",  "High-density; Planning review likely for most work"),
    # Residential – Commercial Combination
    ("RC-4",    "Residential Commercial - High Density",    True,  True,  False, False, "65-A",  "High-density residential/commercial mix; fire review for commercial floors"),
    # Neighborhood Commercial
    ("NC-1",    "Neighborhood Commercial - Cluster",        True,  False, False, False, "25-X",  "Small neighborhood cluster; Planning for change of use"),
    ("NC-2",    "Neighborhood Commercial - Small Scale",    True,  False, False, False, "40-X",  "Small-scale NC; Planning for exterior changes"),
    ("NC-3",    "Neighborhood Commercial - Moderate Scale", True,  True,  False, False, "40-X",  "Moderate-scale NC; SFFD for new occupancies"),
    ("NCD",     "Neighborhood Commercial District",         True,  False, False, False, "40-X",  "General NCD designation"),
    # Commercial (Downtown)
    ("C-2",     "Community Business District",              True,  True,  True,  False, "65-X",  "Community business; DPH for food; SFFD for new commercial"),
    ("C-3-G",   "Downtown General Commercial",              True,  True,  True,  False, "130-F", "Downtown commercial; all agencies for TI work"),
    ("C-3-O",   "Downtown Office District",                 True,  True,  False, False, "350-F", "Downtown office; Planning + SFFD for any new construction"),
    ("C-3-O(SD)","Downtown Office Special Development",     True,  True,  False, False, "350-F", "Downtown office special development"),
    # Mixed-Use
    ("MUG",     "Mixed Use General",                        True,  False, False, False, "58-X",  "General mixed-use; Planning for ground-floor commercial changes"),
    ("MUR",     "Mixed Use Residential",                    True,  False, False, False, "40-X",  "Residential-oriented mixed use"),
    ("MUO",     "Mixed Use Office",                         True,  True,  False, False, "65-X",  "Office-oriented mixed use; SFFD for new construction"),
    # Industrial / PDR
    ("PDR-1-G", "Production Distribution Repair - General", True,  True,  False, False, "68-X",  "PDR general; Planning + SFFD for change from industrial to other uses"),
    ("PDR-1-B", "Production Distribution Repair - Buffer",  True,  False, False, False, "68-X",  "PDR buffer zone"),
    ("PDR-2",   "Production Distribution Repair",           True,  True,  False, False, "68-X",  "Heavy PDR; SFFD for any new construction"),
    # Special / Historic
    ("P",       "Public",                                   True,  True,  False, False, "None",  "Public use; all projects require Planning coordination"),
    ("OS",      "Open Space",                               True,  False, False, False, "None",  "Open space; Planning for any development"),
    ("SPD",     "Special Planning District",                True,  False, False, False, "Varies","Special planning district; always Planning"),
    # Historic Preservation Special Use Districts (examples)
    ("HCD",     "Historic Conservation District",           True,  False, False, True,  "Varies","Historic Conservation District; all exterior work triggers Planning"),
    ("NV",      "Noe Valley NCT",                           True,  False, False, False, "40-X",  "Noe Valley neighborhood commercial transit"),
    ("UMU",     "Urban Mixed Use",                          True,  True,  False, False, "58-X",  "Urban mixed use; SFFD for new construction"),
]

# ref_permit_forms seed rows: (project_type, permit_form, review_path, notes)
PERMIT_FORMS_ROWS = [
    # New Construction / Demolition
    ("new_construction",   "Form 1/2",  "in_house", "Form 1 for non-wood; Form 2 for wood-frame construction"),
    ("demolition",         "Form 6",    "in_house", "May pair with Form 1/2 for replacement construction"),
    # Common Alterations — OTC eligible
    ("kitchen_remodel",    "Form 3/8",  "otc",      "In-kind (no layout change) → Form 8 no plans; with layout change → Form 3 OTC with plans"),
    ("bathroom_remodel",   "Form 3/8",  "otc",      "In-kind → Form 8; with layout change → Form 3 OTC with plans"),
    ("re_roofing",         "Form 3/8",  "otc",      "No plans required; Form 8 OTC"),
    ("window_replacement", "Form 3/8",  "otc",      "In-kind same size/location → Form 8 online only"),
    ("door_replacement",   "Form 3/8",  "otc",      "In-kind → Form 8 OTC"),
    ("deck_repair",        "Form 3/8",  "otc",      "Less than 50% repair → Form 8 no plans; more than 50% → Form 3 with plans"),
    ("deck_construction",  "Form 3/8",  "otc",      "Decks under 20 ft above grade meeting setbacks → Form 3 OTC with plans"),
    ("fence",              "Form 3/8",  "otc",      "Over 6 ft side/rear or over 3 ft front → Form 3 OTC with plans"),
    ("solar",              "Form 3/8",  "likely_otc","Solar/PV installations; Form 3 or Form 8 with plans; priority processing"),
    ("sign",               "Form 3/8",  "otc",      "Sign permits eligible for OTC with plans"),
    ("accessibility",      "Form 3/8",  "otc",      "ADA/accessibility barrier removal → OTC; Form 3 with plans"),
    ("seismic",            "Form 3/8",  "depends",  "Voluntary brace-and-bolt (S-09) → Form 8 OTC; mandatory soft-story/engineered → in-house"),
    ("mechanical",         "Form 3/8",  "otc",      "New mechanical equipment inside/outside → OTC with plans"),
    # General Alterations
    ("general_alteration", "Form 3/8",  "likely_in_house", "Mark Form 3 for in-house or Form 8 for OTC-eligible projects"),
    ("residential_interior","Form 3/8", "otc",      "Changing floor plans or removing walls → OTC with plans"),
    ("exterior_work",      "Form 3/8",  "otc",      "Facade changes, siding changes, new windows → OTC with plans"),
    # In-house Required
    ("adu",                "Form 3/8",  "in_house", "ADU or unit legalization — always in-house (IH-12)"),
    ("change_of_use",      "Form 3/8",  "in_house", "Change of use → in-house; Form depends on project scope"),
    ("restaurant",         "Form 3/8",  "in_house", "Restaurant TI or change of use → in-house; DPH + SFFD routing required"),
    ("adaptive_reuse",     "Form 3/8",  "in_house", "Adaptive reuse → in-house review"),
    ("historic",           "Form 3/8",  "in_house", "Historic resource exterior work → in-house"),
    ("commercial_ti",      "Form 3/8",  "likely_in_house", "Commercial TI — single-story non-structural may be OTC; otherwise in-house"),
    # Site Permit / Large Projects
    ("site_permit",        "Form 1/2",  "in_house", "Site permit for large/phased projects; addenda follow separate routing"),
    ("foundation_work",    "Form 3/8",  "in_house", "Foundation replacement or seismic upgrade → in-house (IH-03, IH-08)"),
    ("excavation",         "Form 3/8",  "in_house", "Below-grade footprint expansion → in-house (IH-05)"),
    ("unit_addition",      "Form 3/8",  "in_house", "Adding or removing units → in-house (IH-11)"),
    ("housing",            "Form 3/8",  "in_house", "Housing projects → in-house (IH-15)"),
]

# ref_agency_triggers seed rows: (trigger_keyword, agency, reason, adds_weeks)
AGENCY_TRIGGERS_ROWS = [
    # DBI (Building) — always required
    ("all_permitted_work",  "DBI (Building)",             "All permitted work requires DBI plan review",                                   0),
    # Planning Department triggers
    ("change_of_use",       "Planning",                   "Change of occupancy/use requires Planning zoning review",                       2),
    ("new_construction",    "Planning",                   "New buildings require Planning review (G-20 Rule D)",                           4),
    ("demolition",          "Planning",                   "Demolition requires Planning environmental/preservation review",                 3),
    ("adu",                 "Planning",                   "ADU/unit legalization requires Planning zoning compliance review",               2),
    ("adaptive_reuse",      "Planning",                   "Adaptive reuse requires Planning approval",                                     4),
    ("historic",            "Planning",                   "Historic resource triggers Planning Preservation review (Article 10/11)",        6),
    ("restaurant",          "Planning",                   "Restaurant change of use or new food service triggers Planning",                 2),
    ("unit_addition",       "Planning",                   "Adding/removing units requires Planning zoning review",                         3),
    ("exterior_work",       "Planning",                   "Exterior changes visible from street may trigger Planning discretionary review", 1),
    ("site_permit",         "Planning",                   "Site permit — Planning is first station (G-20 Rule D)",                         4),
    ("housing",             "Planning",                   "Housing projects require Planning review",                                       4),
    ("sign",                "Planning",                   "Signs in some districts require Planning sign review",                          1),
    # SFFD triggers
    ("restaurant",          "SFFD (Fire)",                "Restaurant hood/suppression systems require SFFD fire code review",              2),
    ("new_construction",    "SFFD (Fire)",                "New construction triggers SFFD fire code review",                               3),
    ("change_of_use",       "SFFD (Fire)",                "Occupancy change may require SFFD fire sprinkler/egress review",                2),
    ("historic",            "SFFD (Fire)",                "Historic buildings may require SFFD fire suppression upgrade review",            2),
    ("adu",                 "SFFD (Fire)",                "ADU may require SFFD fire separation review",                                   1),
    # DPH (Public Health) triggers
    ("restaurant",          "DPH (Public Health)",        "Food service requires DPH health permit; parallel review with DBI; must approve before permit issuance", 3),
    ("food_facility",       "DPH (Public Health)",        "Any food facility construction requires DPH plan check (G-20 Rule C)",          3),
    ("cannabis",            "DPH (Public Health)",        "Medical cannabis dispensing facility — route DPH before Planning (G-20 Rule C)", 3),
    # DBI Mechanical/Electrical
    ("commercial_ti",       "DBI Mechanical/Electrical",  "Commercial TI with HVAC, electrical, or kitchen systems",                       1),
    ("restaurant",          "DBI Mechanical/Electrical",  "Restaurant requires MECH review for hood exhaust, makeup air, kitchen systems", 2),
    ("new_construction",    "DBI Mechanical/Electrical",  "New construction requires mechanical and electrical plan review",               2),
    ("adu",                 "DBI Mechanical/Electrical",  "ADU with new HVAC or electrical service may require MECH-E review",            1),
    # SFPUC triggers
    ("restaurant",          "SFPUC",                      "New plumbing fixtures, grease interceptor, or water service changes",           1),
    ("adu",                 "SFPUC",                      "New plumbing for ADU bathroom/kitchen",                                         1),
    ("new_construction",    "SFPUC",                      "New water service connection requires PUC review",                              2),
    # DPW/BSM (Bureau of Street-Use and Mapping)
    ("new_construction",    "DPW/BSM",                    "Work adjacent to public right-of-way during new construction",                  1),
    ("demolition",          "DPW/BSM",                    "Demolition debris removal and sidewalk use permit",                             1),
    ("restaurant",          "DPW/BSM",                    "Outdoor dining or sidewalk work for restaurant",                               1),
    ("excavation",          "DPW/BSM",                    "Excavation near public ROW requires BSM review",                               2),
    # PW-DAC (Office of Disability Access Coordinator)
    ("accessibility",       "PW-DAC (DPW Disability Access)", "Accessibility projects may require DAC sign-off",                           1),
    ("change_of_use",       "PW-DAC (DPW Disability Access)", "Change of use triggers accessibility compliance review",                    1),
    # OCII (Redevelopment Areas)
    ("ocii_area",           "OCII",                       "Projects in former Redevelopment Agency areas require OCII routing (G-20 //)",   2),
]


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _get_backend() -> str:
    """Return 'postgres' or 'duckdb'."""
    return "postgres" if os.environ.get("DATABASE_URL") else "duckdb"


def _get_connection():
    from src.db import get_connection
    return get_connection()


def _upsert_zoning_routing(conn, backend: str, rows: list) -> int:
    """Upsert all zoning routing rows. Returns count of rows inserted/updated."""
    count = 0
    for row in rows:
        (zoning_code, zoning_category, planning, fire, health,
         historic, height_limit, notes) = row

        if backend == "postgres":
            sql = """
                INSERT INTO ref_zoning_routing
                    (zoning_code, zoning_category, planning_review_required,
                     fire_review_required, health_review_required,
                     historic_district, height_limit, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (zoning_code) DO UPDATE SET
                    zoning_category = EXCLUDED.zoning_category,
                    planning_review_required = EXCLUDED.planning_review_required,
                    fire_review_required = EXCLUDED.fire_review_required,
                    health_review_required = EXCLUDED.health_review_required,
                    historic_district = EXCLUDED.historic_district,
                    height_limit = EXCLUDED.height_limit,
                    notes = EXCLUDED.notes
            """
            with conn.cursor() as cur:
                cur.execute(sql, (zoning_code, zoning_category, planning, fire,
                                  health, historic, height_limit, notes))
        else:
            # DuckDB: INSERT OR REPLACE
            sql = """
                INSERT OR REPLACE INTO ref_zoning_routing
                    (zoning_code, zoning_category, planning_review_required,
                     fire_review_required, health_review_required,
                     historic_district, height_limit, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            conn.execute(sql, [zoning_code, zoning_category, planning, fire,
                                health, historic, height_limit, notes])
        count += 1
    return count


def _upsert_permit_forms(conn, backend: str, rows: list) -> int:
    """Upsert all permit forms rows. Returns count of rows inserted/updated."""
    # Truncate + re-insert for simplicity (these are static reference rows)
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ref_permit_forms")
            for i, row in enumerate(rows, start=1):
                project_type, permit_form, review_path, notes = row
                cur.execute(
                    "INSERT INTO ref_permit_forms (id, project_type, permit_form, review_path, notes) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "project_type=EXCLUDED.project_type, permit_form=EXCLUDED.permit_form, "
                    "review_path=EXCLUDED.review_path, notes=EXCLUDED.notes",
                    (i, project_type, permit_form, review_path, notes),
                )
    else:
        conn.execute("DELETE FROM ref_permit_forms")
        for i, row in enumerate(rows, start=1):
            project_type, permit_form, review_path, notes = row
            conn.execute(
                "INSERT OR REPLACE INTO ref_permit_forms (id, project_type, permit_form, review_path, notes) "
                "VALUES (?, ?, ?, ?, ?)",
                [i, project_type, permit_form, review_path, notes],
            )
    return len(rows)


def _upsert_agency_triggers(conn, backend: str, rows: list) -> int:
    """Upsert all agency trigger rows. Returns count of rows inserted/updated."""
    if backend == "postgres":
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ref_agency_triggers")
            for i, row in enumerate(rows, start=1):
                trigger_keyword, agency, reason, adds_weeks = row
                cur.execute(
                    "INSERT INTO ref_agency_triggers (id, trigger_keyword, agency, reason, adds_weeks) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "trigger_keyword=EXCLUDED.trigger_keyword, agency=EXCLUDED.agency, "
                    "reason=EXCLUDED.reason, adds_weeks=EXCLUDED.adds_weeks",
                    (i, trigger_keyword, agency, reason, adds_weeks),
                )
    else:
        conn.execute("DELETE FROM ref_agency_triggers")
        for i, row in enumerate(rows, start=1):
            trigger_keyword, agency, reason, adds_weeks = row
            conn.execute(
                "INSERT OR REPLACE INTO ref_agency_triggers (id, trigger_keyword, agency, reason, adds_weeks) "
                "VALUES (?, ?, ?, ?, ?)",
                [i, trigger_keyword, agency, reason, adds_weeks],
            )
    return len(rows)


# ---------------------------------------------------------------------------
# Main seed function
# ---------------------------------------------------------------------------

def seed_reference_tables(conn=None) -> dict[str, Any]:
    """Seed all three reference tables.

    Args:
        conn: Optional existing connection. If None, creates one internally.

    Returns:
        dict with row counts for each table and success flag.
    """
    from src.db import get_connection, BACKEND as _BACKEND
    backend = _BACKEND

    close = conn is None
    if conn is None:
        conn = get_connection()

    try:
        zoning_count = _upsert_zoning_routing(conn, backend, ZONING_ROUTING_ROWS)
        forms_count = _upsert_permit_forms(conn, backend, PERMIT_FORMS_ROWS)
        triggers_count = _upsert_agency_triggers(conn, backend, AGENCY_TRIGGERS_ROWS)

        if backend == "postgres":
            conn.commit()

        logger.info(
            "Seeded reference tables: zoning=%d, forms=%d, triggers=%d",
            zoning_count, forms_count, triggers_count,
        )
        return {
            "ok": True,
            "ref_zoning_routing": zoning_count,
            "ref_permit_forms": forms_count,
            "ref_agency_triggers": triggers_count,
        }
    except Exception as exc:
        if backend == "postgres":
            try:
                conn.rollback()
            except Exception:
                pass
        logger.exception("seed_reference_tables failed: %s", exc)
        return {"ok": False, "error": str(exc)}
    finally:
        if close:
            conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    result = seed_reference_tables()
    if result.get("ok"):
        print(
            f"OK — zoning_routing={result['ref_zoning_routing']} rows, "
            f"permit_forms={result['ref_permit_forms']} rows, "
            f"agency_triggers={result['ref_agency_triggers']} rows"
        )
        sys.exit(0)
    else:
        print(f"FAILED: {result.get('error')}", file=sys.stderr)
        sys.exit(1)
