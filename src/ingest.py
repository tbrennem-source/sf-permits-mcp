"""Ingestion pipeline: fetch SF permit data from SODA API into local DuckDB.

Usage:
    python -m src.ingest              # Full ingestion (all datasets)
    python -m src.ingest --contacts   # Only contact datasets
    python -m src.ingest --permits    # Only building permits
    python -m src.ingest --inspections # Only building inspections
"""

import asyncio
import time
import sys
import os
from datetime import datetime, timezone

from src.soda_client import SODAClient
from src.db import get_connection, init_schema

# Dataset configs
DATASETS = {
    "building_contacts": {
        "endpoint_id": "3pee-9qhc",
        "name": "Building Permits Contacts",
        "source": "building",
    },
    "electrical_contacts": {
        "endpoint_id": "fdm7-jqqf",
        "name": "Electrical Permits Contacts",
        "source": "electrical",
    },
    "plumbing_contacts": {
        "endpoint_id": "k6kv-9kix",
        "name": "Plumbing Permits Contacts",
        "source": "plumbing",
    },
    "building_permits": {
        "endpoint_id": "i98e-djp9",
        "name": "Building Permits",
    },
    "building_inspections": {
        "endpoint_id": "vckc-dh2h",
        "name": "Building Inspections",
    },
    "plumbing_inspections": {
        "endpoint_id": "fuas-yurr",
        "name": "Plumbing Inspections",
    },
    "addenda": {
        "endpoint_id": "87xy-gk8d",
        "name": "Building Permit Addenda with Routing",
    },
    "violations": {
        "endpoint_id": "nbtm-fbw5",
        "name": "Notices of Violation",
    },
    "complaints": {
        "endpoint_id": "gm2e-bten",
        "name": "DBI Complaints",
    },
    "businesses": {
        "endpoint_id": "g8m3-pdis",
        "name": "Registered Business Locations",
    },
    "electrical_permits": {
        "endpoint_id": "ftty-kx6y",
        "name": "Electrical Permits",
    },
    "plumbing_permits": {
        "endpoint_id": "a6aw-rudh",
        "name": "Plumbing Permits",
    },
    "boiler_permits": {
        "endpoint_id": "5dp4-gtxk",
        "name": "Boiler Permits",
    },
    "fire_permits": {
        "endpoint_id": "893e-xam6",
        "name": "Fire Permits",
    },
    "planning_projects": {
        "endpoint_id": "qvu5-m3a2",
        "name": "Planning Projects",
    },
    "planning_non_projects": {
        "endpoint_id": "y673-d69b",
        "name": "Planning Non-Projects",
    },
    "tax_rolls": {
        "endpoint_id": "wv5m-vpq2",
        "name": "Tax Rolls (Secured Property)",
    },
    "street_use_permits": {
        "endpoint_id": "b6tj-gt35",
        "name": "Street-Use Permits",
    },
    "development_pipeline": {
        "endpoint_id": "6jgi-cpb4",
        "name": "SF Development Pipeline",
    },
    "affordable_housing": {
        "endpoint_id": "aaxw-2cb8",
        "name": "Affordable Housing Pipeline",
    },
    "housing_production": {
        "endpoint_id": "xdht-4php",
        "name": "Housing Production",
    },
    "dwelling_completions": {
        "endpoint_id": "j67f-aayr",
        "name": "Dwelling Unit Completions",
    },
}

PAGE_SIZE = 10_000

# Role normalization map for building contacts
ROLE_MAP = {
    "contractor": "contractor",
    "authorized agent-others": "agent",
    "architect": "architect",
    "engineer": "engineer",
    "lessee": "owner",
    "payor": "other",
    "pmt consultant/expediter": "consultant",
    "designer": "designer",
    "project contact": "other",
    "attorney": "other",
    "subcontractor": "contractor",
}

# Contact type normalization for electrical contacts
ELECTRICAL_ROLE_MAP = {
    "Contractor": "contractor",
    "contractor": "contractor",
    "Owner": "owner",
    "owner": "owner",
    "Others": "other",
    "others": "other",
}


def _normalize_role(role: str | None, source: str) -> str:
    """Normalize role/contact_type to canonical type."""
    if not role:
        if source == "plumbing":
            return "contractor"  # All plumbing contacts are implicitly contractors
        return "other"
    role_lower = role.lower().strip()
    if source == "building":
        return ROLE_MAP.get(role_lower, "other")
    elif source == "electrical":
        return ELECTRICAL_ROLE_MAP.get(role, ELECTRICAL_ROLE_MAP.get(role_lower, "other"))
    elif source == "plumbing":
        return "contractor"
    return "other"


def _normalize_building_contact(record: dict, row_id: int) -> tuple:
    """Normalize a building contacts record to unified schema."""
    first_name = (record.get("first_name") or "").strip()
    last_name = (record.get("last_name") or "").strip()
    name_parts = [first_name, last_name]
    name = " ".join(p for p in name_parts if p).strip() or None

    return (
        row_id,
        "building",
        record.get("permit_number", ""),
        _normalize_role(record.get("role"), "building"),
        name,
        first_name or None,
        last_name or None,
        (record.get("firm_name") or "").strip() or None,
        (record.get("pts_agent_id") or "").strip() or None,
        (record.get("license1") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        None,  # phone not in building contacts
        (record.get("agent_address") or "").strip() or None,
        (record.get("city") or "").strip() or None,
        (record.get("state") or "").strip() or None,
        (record.get("agent_zipcode") or "").strip() or None,
        record.get("is_applicant"),
        record.get("from_date"),
        None,  # entity_id (populated later)
        record.get("data_as_of"),
    )


def _normalize_electrical_contact(record: dict, row_id: int) -> tuple:
    """Normalize an electrical contacts record to unified schema."""
    company = (record.get("company_name") or "").strip() or None
    address_parts = [
        record.get("street_number", ""),
        record.get("street", ""),
        record.get("street_suffix", ""),
    ]
    address = " ".join(p for p in address_parts if (p or "").strip()).strip() or None

    return (
        row_id,
        "electrical",
        record.get("permit_number", ""),
        _normalize_role(record.get("contact_type"), "electrical"),
        company,  # company_name used as name
        None,  # no first_name
        None,  # no last_name
        company,  # company_name serves as firm_name too
        None,  # no pts_agent_id
        (record.get("license_number") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        (record.get("phone") or "").strip() or None,
        address,
        None,  # no city field
        (record.get("state") or "").strip() or None,
        (record.get("zipcode") or "").strip() or None,
        record.get("is_applicant"),
        None,  # no from_date
        None,  # entity_id
        record.get("data_as_of"),
    )


def _normalize_plumbing_contact(record: dict, row_id: int) -> tuple:
    """Normalize a plumbing contacts record to unified schema."""
    firm = (record.get("firm_name") or "").strip() or None

    return (
        row_id,
        "plumbing",
        record.get("permit_number", ""),
        "contractor",  # all plumbing contacts are contractors
        firm,  # firm_name used as name
        None,  # no first_name
        None,  # no last_name
        firm,
        None,  # no pts_agent_id
        (record.get("license_number") or "").strip() or None,
        (record.get("sf_business_license_number") or "").strip() or None,
        (record.get("phone") or "").strip() or None,
        (record.get("address") or "").strip() or None,
        (record.get("city") or "").strip() or None,
        (record.get("state") or "").strip() or None,
        (record.get("zipcode") or "").strip() or None,
        record.get("is_applicant"),
        None,  # no from_date
        None,  # entity_id
        record.get("data_as_of"),
    )


def _normalize_permit(record: dict) -> tuple:
    """Normalize a building permit record."""
    cost = None
    raw_cost = record.get("estimated_cost")
    if raw_cost:
        try:
            cost = float(raw_cost)
        except (ValueError, TypeError):
            pass

    revised_cost = None
    raw_revised = record.get("revised_cost")
    if raw_revised:
        try:
            revised_cost = float(raw_revised)
        except (ValueError, TypeError):
            pass

    existing_units = None
    raw_eu = record.get("existing_units")
    if raw_eu:
        try:
            existing_units = int(float(raw_eu))
        except (ValueError, TypeError):
            pass

    proposed_units = None
    raw_pu = record.get("proposed_units")
    if raw_pu:
        try:
            proposed_units = int(float(raw_pu))
        except (ValueError, TypeError):
            pass

    return (
        record.get("permit_number", ""),
        record.get("permit_type"),
        record.get("permit_type_definition"),
        record.get("status"),
        record.get("status_date"),
        record.get("description"),
        record.get("filed_date"),
        record.get("issued_date"),
        record.get("approved_date"),
        record.get("completed_date"),
        cost,
        revised_cost,
        record.get("existing_use"),
        record.get("proposed_use"),
        existing_units,
        proposed_units,
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zipcode"),
        record.get("neighborhoods_analysis_boundaries"),
        record.get("supervisor_district"),
        record.get("block"),
        record.get("lot"),
        record.get("adu"),
        record.get("data_as_of"),
    )


def _normalize_electrical_permit(record: dict) -> tuple:
    """Normalize an electrical permit record to the shared permits table schema.

    Electrical permits (ftty-kx6y) have a reduced field set compared to building
    permits.  Missing fields (cost, use, units, neighborhood, adu, etc.) are set
    to NULL so the record fits the existing permits table without schema changes.

    Field name differences vs building permits:
      - application_creation_date  (no equivalent in permits table — dropped)
      - zip_code                   → zipcode
    """
    return (
        record.get("permit_number", ""),
        "electrical",               # permit_type
        "Electrical Permit",        # permit_type_definition (human-readable constant)
        record.get("status"),
        None,                       # status_date (not in electrical dataset)
        record.get("description"),
        record.get("filed_date"),
        record.get("issued_date"),
        None,                       # approved_date (not in electrical dataset)
        record.get("completed_date"),
        None,                       # estimated_cost
        None,                       # revised_cost
        None,                       # existing_use
        None,                       # proposed_use
        None,                       # existing_units
        None,                       # proposed_units
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zip_code"),     # electrical uses zip_code (not zipcode)
        None,                       # neighborhood (not in electrical dataset)
        None,                       # supervisor_district (not in electrical dataset)
        record.get("block"),
        record.get("lot"),
        None,                       # adu (not in electrical dataset)
        record.get("data_as_of"),
    )


def _normalize_plumbing_permit(record: dict) -> tuple:
    """Normalize a plumbing permit record to the shared permits table schema.

    Plumbing permits (a6aw-rudh) have a reduced field set compared to building
    permits.  Missing fields are set to NULL.

    Field name differences vs building permits:
      - application_date  (no equivalent in permits table — dropped)
      - parcel_number     (not in permits table — dropped)
      - unit              (not in permits table — dropped)
    """
    return (
        record.get("permit_number", ""),
        "plumbing",                 # permit_type
        "Plumbing Permit",          # permit_type_definition (human-readable constant)
        record.get("status"),
        None,                       # status_date (not in plumbing dataset)
        record.get("description"),
        record.get("filed_date"),
        record.get("issued_date"),
        None,                       # approved_date (not in plumbing dataset)
        record.get("completed_date"),
        None,                       # estimated_cost
        None,                       # revised_cost
        None,                       # existing_use
        None,                       # proposed_use
        None,                       # existing_units
        None,                       # proposed_units
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zipcode"),
        None,                       # neighborhood (not in plumbing dataset)
        None,                       # supervisor_district (not in plumbing dataset)
        record.get("block"),
        record.get("lot"),
        None,                       # adu (not in plumbing dataset)
        record.get("data_as_of"),
    )


def _normalize_addenda(record: dict, row_id: int) -> tuple:
    """Normalize a building permit addenda routing record."""
    addenda_number = None
    raw_an = record.get("addenda_number")
    if raw_an:
        try:
            addenda_number = int(float(raw_an))
        except (ValueError, TypeError):
            pass

    step = None
    raw_step = record.get("step")
    if raw_step:
        try:
            step = int(float(raw_step))
        except (ValueError, TypeError):
            pass

    return (
        row_id,
        record.get("primary_key"),
        record.get("application_number", ""),
        addenda_number,
        step,
        (record.get("station") or "").strip() or None,
        record.get("arrive"),
        record.get("assign_date"),
        record.get("start_date"),
        record.get("finish_date"),
        record.get("approved_date"),
        (record.get("plan_checked_by") or "").strip() or None,
        (record.get("review_results") or "").strip() or None,
        (record.get("hold_description") or "").strip() or None,
        (record.get("addenda_status") or "").strip() or None,
        (record.get("department") or "").strip() or None,
        (record.get("title") or "").strip() or None,
        record.get("data_as_of"),
    )


def _normalize_inspection(record: dict, row_id: int, source: str = "building") -> tuple:
    """Normalize a building or plumbing inspection record.

    Args:
        record: Raw SODA record dict.
        row_id: Integer primary key.
        source: 'building' or 'plumbing' — identifies the inspection dataset.
    """
    return (
        row_id,
        record.get("reference_number"),
        record.get("reference_number_type"),
        (record.get("inspector") or "").strip() or None,
        record.get("scheduled_date"),
        record.get("result"),
        record.get("inspection_description"),
        record.get("block"),
        record.get("lot"),
        record.get("street_number"),
        record.get("avs_street_name"),
        record.get("avs_street_sfx"),
        record.get("analysis_neighborhood"),
        record.get("supervisor_district"),
        record.get("zip_code"),
        record.get("data_as_of"),
        source,
    )


def normalize_plumbing_inspection(record: dict, row_id: int) -> tuple:
    """Normalize a plumbing inspection record (fuas-yurr) to inspections schema.

    Plumbing inspections share field names with building inspections (vckc-dh2h):
    reference_number, reference_number_type, inspector, scheduled_date,
    block, lot, avs_street_name, avs_street_sfx, analysis_neighborhood,
    supervisor_district, zip_code.

    Note: plumbing inspections have no 'result' field in the SODA dataset.
    """
    return _normalize_inspection(record, row_id, source="plumbing")


def _normalize_violation(record: dict, row_id: int) -> tuple:
    """Normalize a notice of violation record."""
    return (
        row_id,
        record.get("complaint_number"),
        record.get("item_sequence_number"),
        record.get("date_filed"),
        record.get("block"),
        record.get("lot"),
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("unit"),
        record.get("status"),
        record.get("receiving_division"),
        record.get("assigned_division"),
        record.get("nov_category_description"),
        record.get("item"),
        record.get("nov_item_description"),
        record.get("neighborhoods_analysis_boundaries"),
        record.get("supervisor_district"),
        record.get("zipcode"),
        record.get("data_as_of"),
    )


def _normalize_complaint(record: dict, row_id: int) -> tuple:
    """Normalize a DBI complaint record."""
    return (
        row_id,
        record.get("complaint_number"),
        record.get("date_filed"),
        record.get("date_abated"),
        record.get("block"),
        record.get("lot"),
        record.get("parcel_number"),
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("unit"),
        record.get("zip_code"),
        record.get("complaint_description"),
        record.get("status"),
        record.get("nov_type"),
        record.get("receiving_division"),
        record.get("assigned_division"),
        record.get("data_as_of"),
    )


def _normalize_business(record: dict, row_id: int) -> tuple:
    """Normalize a registered business location record."""
    return (
        row_id,
        record.get("certificate_number"),
        record.get("ttxid"),
        (record.get("ownership_name") or "").strip() or None,
        (record.get("dba_name") or "").strip() or None,
        (record.get("full_business_address") or "").strip() or None,
        record.get("city"),
        record.get("state"),
        record.get("business_zip"),
        record.get("dba_start_date"),
        record.get("dba_end_date"),
        record.get("location_start_date"),
        record.get("location_end_date"),
        record.get("parking_tax"),
        record.get("transient_occupancy_tax"),
        record.get("data_as_of"),
    )


def _normalize_boiler_permit(record: dict) -> tuple:
    """Normalize a boiler permit record."""
    return (
        record.get("permit_number", ""),
        record.get("block"),
        record.get("lot"),
        record.get("status"),
        record.get("boiler_type"),
        record.get("boiler_serial_number"),
        record.get("model"),
        record.get("description"),
        record.get("application_date"),
        record.get("expiration_date"),
        record.get("street_number"),
        record.get("street_name"),
        record.get("street_suffix"),
        record.get("zip_code"),
        record.get("neighborhood"),
        record.get("supervisor_district"),
        record.get("data_as_of"),
    )


def _normalize_fire_permit(record: dict) -> tuple:
    """Normalize a fire permit record."""
    def _parse_fee(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    return (
        record.get("permit_number", ""),
        record.get("permit_type"),
        record.get("permit_type_description"),
        record.get("permit_status"),
        record.get("permit_address"),
        record.get("permit_holder"),
        record.get("dba_name"),
        record.get("application_date"),
        record.get("date_approved"),
        record.get("expiration_date"),
        _parse_fee(record.get("permit_fee")),
        _parse_fee(record.get("posting_fee")),
        _parse_fee(record.get("referral_fee")),
        record.get("conditions"),
        record.get("battalion"),
        record.get("fire_prevention_district"),
        record.get("night_assembly_permit"),
        record.get("data_as_of"),
    )


def _normalize_planning_project(record: dict) -> tuple:
    """Normalize a planning project record (is_project=True)."""
    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    return (
        record.get("record_id", ""),
        record.get("record_type"),
        record.get("record_status"),
        record.get("block"),
        record.get("lot"),
        record.get("address"),
        record.get("project_name"),
        record.get("description"),
        record.get("applicant"),
        record.get("applicant_org"),
        record.get("assigned_planner"),
        record.get("open_date"),
        record.get("environmental_doc_type"),
        True,  # is_project
        _parse_int(record.get("units_existing")),
        _parse_int(record.get("units_proposed")),
        _parse_float(record.get("units_net")),
        _parse_int(record.get("affordable_units")),
        record.get("child_id"),
        None,  # parent_id (projects don't have this)
        record.get("data_as_of"),
    )


def _normalize_planning_non_project(record: dict) -> tuple:
    """Normalize a planning non-project record (is_project=False)."""
    return (
        record.get("record_id", ""),
        record.get("record_type"),
        record.get("record_status"),
        record.get("block"),
        record.get("lot"),
        record.get("address"),
        None,  # project_name
        record.get("description"),
        record.get("applicant"),
        None,  # applicant_org
        record.get("assigned_planner"),
        record.get("open_date"),
        None,  # environmental_doc_type
        False,  # is_project
        None,  # units_existing
        None,  # units_proposed
        None,  # units_net
        None,  # affordable_units
        None,  # child_id
        record.get("parent_id"),
        record.get("data_as_of"),
    )


def _normalize_tax_roll(record: dict) -> tuple:
    """Normalize a tax roll record."""
    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    return (
        record.get("block"),
        record.get("lot"),
        record.get("closed_roll_year"),
        record.get("property_location"),
        record.get("parcel_number"),
        record.get("zoning_code"),
        record.get("use_code"),
        record.get("use_definition"),
        record.get("property_class_code"),
        record.get("property_class_code_definition"),
        _parse_float(record.get("number_of_stories")),
        _parse_int(record.get("number_of_units")),
        _parse_int(record.get("number_of_rooms")),
        _parse_int(record.get("number_of_bedrooms")),
        _parse_float(record.get("number_of_bathrooms")),
        _parse_float(record.get("lot_area")),
        _parse_float(record.get("property_area")),
        _parse_float(record.get("assessed_land_value")),
        _parse_float(record.get("assessed_improvement_value")),
        _parse_float(record.get("assessed_personal_property")),
        _parse_float(record.get("assessed_fixtures")),
        record.get("current_sales_date"),
        record.get("neighborhood"),
        record.get("supervisor_district"),
        record.get("data_as_of"),
    )


def _normalize_street_use_permit(record: dict) -> tuple:
    """Normalize a street-use permit record.

    SODA endpoint b6tj-gt35. Key field differences vs building permits:
      - streetname (not street_name)
      - agentphone (not agent_phone)
      - planchecker (not plan_checker)
      - permit_zipcode (different name)
      - analysis_neighborhood → neighborhood
      - unique_identifier as primary key (permit_number may be duplicate across CNN)
    """
    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    return (
        record.get("unique_identifier") or record.get("permit_number", ""),
        record.get("permit_type"),
        record.get("permit_purpose"),
        record.get("status"),
        record.get("agent"),
        record.get("agentphone"),
        record.get("contact"),
        record.get("streetname"),
        record.get("cross_street_1"),
        record.get("cross_street_2"),
        record.get("planchecker"),
        record.get("approved_date"),
        record.get("expiration_date"),
        record.get("analysis_neighborhood"),
        record.get("supervisor_district"),
        _parse_float(record.get("latitude")),
        _parse_float(record.get("longitude")),
        record.get("cnn"),
        record.get("data_as_of"),
    )


def _normalize_development_pipeline(record: dict) -> tuple:
    """Normalize a development pipeline record.

    SODA endpoint 6jgi-cpb4. Key fields:
      - blklot → block_lot (combined)
      - nameaddr → name_address
      - nhood37 → neighborhood
      - pipeline_affordable_units → affordable_units
    """
    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    # Use bpa_no as primary key when available, else case_no, else generated
    record_id = record.get("bpa_no") or record.get("case_no") or record.get("blklot", "")

    return (
        record_id,
        record.get("bpa_no"),
        record.get("case_no"),
        record.get("nameaddr"),
        record.get("current_status"),
        record.get("description_dbi"),
        record.get("description_planning"),
        record.get("contact"),
        record.get("sponsor"),
        record.get("planner"),
        _parse_int(record.get("proposed_units")),
        _parse_int(record.get("existing_units")),
        _parse_int(record.get("net_pipeline_units")),
        _parse_int(record.get("pipeline_affordable_units")),
        record.get("zoning_district"),
        record.get("height_district"),
        record.get("nhood37"),
        record.get("planning_district"),
        record.get("approved_date_planning"),
        record.get("blklot"),
        _parse_float(record.get("latitude")),
        _parse_float(record.get("longitude")),
        record.get("data_as_of"),
    )


def _normalize_affordable_housing(record: dict) -> tuple:
    """Normalize an affordable housing pipeline record.

    SODA endpoint aaxw-2cb8. Key fields:
      - city_analysis_neighborhood → neighborhood
      - mohcd_affordable_units → affordable_units
      - project_status (not construction_status alone)
    """
    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    def _parse_float(val):
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    return (
        record.get("project_id", ""),
        record.get("project_name"),
        record.get("project_lead_sponsor"),
        record.get("planning_case_number"),
        record.get("plannning_approval_address"),
        _parse_int(record.get("total_project_units")),
        _parse_int(record.get("mohcd_affordable_units")),
        _parse_float(record.get("affordable_percent")),
        record.get("construction_status"),
        record.get("housing_tenure"),
        record.get("general_housing_program"),
        record.get("supervisor_district"),
        record.get("city_analysis_neighborhood"),
        _parse_float(record.get("latitude")),
        _parse_float(record.get("longitude")),
        record.get("data_as_of"),
    )


def _normalize_housing_production(record: dict, row_id: int) -> tuple:
    """Normalize a housing production record.

    SODA endpoint xdht-4php. Key fields:
      - blocklot → block_lot
      - analysis_neighborhood → neighborhood
    """
    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    return (
        row_id,
        record.get("bpa"),
        record.get("address"),
        record.get("blocklot"),
        record.get("description"),
        record.get("permit_type"),
        record.get("issued_date"),
        record.get("first_completion_date"),
        record.get("latest_completion_date"),
        _parse_int(record.get("proposed_units") or record.get("pts_proposed_units")),
        _parse_int(record.get("net_units")),
        _parse_int(record.get("net_units_completed")),
        _parse_int(record.get("market_rate")),
        _parse_int(record.get("affordable_units")),
        record.get("zoning_district"),
        record.get("analysis_neighborhood"),
        record.get("supervisor_district"),
        record.get("data_as_of"),
    )


def _normalize_dwelling_completion(record: dict, row_id: int) -> tuple:
    """Normalize a dwelling unit completion record.

    SODA endpoint j67f-aayr. Simple schema.
    """
    def _parse_int(val):
        if val is None:
            return None
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None

    return (
        row_id,
        record.get("building_address"),
        record.get("building_permit_application"),
        record.get("date_issued"),
        record.get("document_type"),
        _parse_int(record.get("number_of_units_certified")),
        record.get("data_as_of"),
    )


async def _fetch_all_pages(
    client: SODAClient,
    endpoint_id: str,
    dataset_name: str,
    order: str = ":id",
    where: str | None = None,
    page_size: int | None = None,
) -> list[dict]:
    """Fetch all records from a SODA endpoint with pagination."""
    all_records = []
    offset = 0
    start = time.time()
    fetch_size = page_size or PAGE_SIZE

    # Get total count first
    total = await client.count(endpoint_id, where=where)
    print(f"  {dataset_name}: {total:,} total records to fetch")

    max_retries = 3
    while True:
        page = None
        for attempt in range(max_retries):
            try:
                page = await client.query(
                    endpoint_id=endpoint_id,
                    where=where,
                    limit=fetch_size,
                    offset=offset,
                    order=order,
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retry {attempt + 1}/{max_retries} after error: {e}. Waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    raise
        if not page:
            break

        all_records.extend(page)
        offset += len(page)
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        print(
            f"  Fetched {offset:,}/{total:,} records "
            f"({offset * 100 // total}%) — "
            f"{rate:,.0f} records/sec — "
            f"{elapsed:.1f}s elapsed",
            flush=True,
        )

        if len(page) < fetch_size:
            break

    elapsed = time.time() - start
    print(f"  Done: {len(all_records):,} records in {elapsed:.1f}s")
    return all_records


async def ingest_contacts(conn, client: SODAClient) -> int:
    """Ingest all three contact datasets into unified contacts table."""
    print("\n=== Ingesting Contact Datasets ===")

    # Clear existing contacts
    conn.execute("DELETE FROM contacts")

    row_id = 0
    total = 0

    # Building contacts
    print("\n[1/3] Building Permits Contacts (3pee-9qhc)")
    records = await _fetch_all_pages(
        client, "3pee-9qhc", "Building Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_building_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} building contact records")

    # Update ingest log
    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "3pee-9qhc",
            "Building Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    # Electrical contacts
    print("\n[2/3] Electrical Permits Contacts (fdm7-jqqf)")
    records = await _fetch_all_pages(
        client, "fdm7-jqqf", "Electrical Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_electrical_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} electrical contact records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "fdm7-jqqf",
            "Electrical Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    # Plumbing contacts
    print("\n[3/3] Plumbing Permits Contacts (k6kv-9kix)")
    records = await _fetch_all_pages(
        client, "k6kv-9kix", "Plumbing Contacts"
    )
    batch = []
    for r in records:
        row_id += 1
        batch.append(_normalize_plumbing_contact(r, row_id))
    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} plumbing contact records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "k6kv-9kix",
            "Plumbing Permits Contacts",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )

    # Extract contacts from addenda and businesses (if those tables are populated)
    addenda_contacts = _extract_addenda_contacts(conn, row_id)
    row_id += addenda_contacts
    total += addenda_contacts

    business_contacts = _extract_business_contacts(conn, row_id)
    total += business_contacts

    print(f"\n  Total contacts loaded: {total:,}")
    return total


async def ingest_permits(conn, client: SODAClient) -> int:
    """Ingest building permits into permits table."""
    print("\n=== Ingesting Building Permits ===")

    conn.execute("DELETE FROM permits")

    records = await _fetch_all_pages(
        client, "i98e-djp9", "Building Permits"
    )

    batch = [_normalize_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "i98e-djp9",
            "Building Permits",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_electrical_permits(conn, client: SODAClient) -> int:
    """Ingest electrical permits (ftty-kx6y) into the shared permits table.

    Electrical permit records are inserted alongside building permits.  The
    permits table uses permit_number as PRIMARY KEY with INSERT OR REPLACE so
    re-ingestion is safe.  Fields not present in the electrical dataset are
    stored as NULL.
    """
    print("\n=== Ingesting Electrical Permits ===")

    records = await _fetch_all_pages(client, "ftty-kx6y", "Electrical Permits")

    batch = [_normalize_electrical_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} electrical permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "ftty-kx6y",
            "Electrical Permits",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_plumbing_permits(conn, client: SODAClient) -> int:
    """Ingest plumbing permits (a6aw-rudh) into the shared permits table.

    Plumbing permit records are inserted alongside building permits.  The
    permits table uses permit_number as PRIMARY KEY with INSERT OR REPLACE so
    re-ingestion is safe.  Fields not present in the plumbing dataset are
    stored as NULL.
    """
    print("\n=== Ingesting Plumbing Permits ===")

    records = await _fetch_all_pages(client, "a6aw-rudh", "Plumbing Permits")

    batch = [_normalize_plumbing_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} plumbing permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "a6aw-rudh",
            "Plumbing Permits",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_inspections(conn, client: SODAClient) -> int:
    """Ingest building inspections into inspections table (source='building')."""
    print("\n=== Ingesting Building Inspections ===")

    conn.execute("DELETE FROM inspections WHERE source = 'building' OR source IS NULL")

    records = await _fetch_all_pages(
        client, "vckc-dh2h", "Building Inspections"
    )

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_inspection(r, i, source="building"))
    if batch:
        conn.executemany(
            "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} inspection records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "vckc-dh2h",
            "Building Inspections",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


async def ingest_plumbing_inspections(conn, client: SODAClient) -> int:
    """Ingest plumbing inspections (fuas-yurr) into the shared inspections table.

    Uses source='plumbing' to distinguish from building inspections.
    Replaces all plumbing rows on each run (same pattern as building inspections).
    """
    print("\n=== Ingesting Plumbing Inspections ===")

    conn.execute("DELETE FROM inspections WHERE source = 'plumbing'")

    records = await _fetch_all_pages(
        client, "fuas-yurr", "Plumbing Inspections"
    )

    # Start IDs after any existing building inspection rows to avoid collision
    try:
        max_id_row = conn.execute("SELECT COALESCE(MAX(id), 0) FROM inspections").fetchone()
        start_id = (max_id_row[0] if max_id_row else 0) + 1
    except Exception:
        start_id = 1

    batch = []
    for i, r in enumerate(records, start_id):
        batch.append(normalize_plumbing_inspection(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} plumbing inspection records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [
            "fuas-yurr",
            "Plumbing Inspections",
            datetime.now(timezone.utc).isoformat(),
            len(records),
            len(records),
        ],
    )
    return len(batch)


ADDENDA_PAGE_SIZE = 50_000  # Larger page for 3.9M addenda dataset
ADDENDA_BATCH_FLUSH = 100_000  # Flush to DB every 100K rows


async def ingest_addenda(conn, client: SODAClient) -> int:
    """Ingest building permit addenda + routing into addenda table.

    Uses larger page size and periodic batch flushing for the ~3.9M row dataset.
    """
    print("\n=== Ingesting Building Permit Addenda + Routing ===")
    conn.execute("DELETE FROM addenda")

    endpoint_id = "87xy-gk8d"
    total_count = await client.count(endpoint_id)
    print(f"  Building Permit Addenda: {total_count:,} total records to fetch")

    row_id = 0
    total = 0
    offset = 0
    start = time.time()
    max_retries = 3
    batch = []

    while True:
        page = None
        for attempt in range(max_retries):
            try:
                page = await client.query(
                    endpoint_id=endpoint_id,
                    limit=ADDENDA_PAGE_SIZE,
                    offset=offset,
                    order=":id",
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retry {attempt + 1}/{max_retries}: {e}. Waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    raise
        if not page:
            break

        for r in page:
            row_id += 1
            batch.append(_normalize_addenda(r, row_id))

        offset += len(page)
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        pct = offset * 100 // total_count if total_count else 0
        print(
            f"  Fetched {offset:,}/{total_count:,} ({pct}%) — "
            f"{rate:,.0f} rec/s — {elapsed:.1f}s",
            flush=True,
        )

        # Flush batch to DB periodically to limit memory
        if len(batch) >= ADDENDA_BATCH_FLUSH:
            conn.executemany(
                "INSERT INTO addenda VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            total += len(batch)
            batch = []

        if len(page) < ADDENDA_PAGE_SIZE:
            break

    # Flush remaining
    if batch:
        conn.executemany(
            "INSERT INTO addenda VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        [endpoint_id, "Building Permit Addenda + Routing", datetime.now(timezone.utc).isoformat(), total, total],
    )
    elapsed = time.time() - start
    print(f"  Loaded {total:,} addenda records in {elapsed:.1f}s")
    return total


async def ingest_violations(conn, client: SODAClient) -> int:
    """Ingest notices of violation into violations table."""
    print("\n=== Ingesting Notices of Violation ===")
    conn.execute("DELETE FROM violations")

    records = await _fetch_all_pages(client, "nbtm-fbw5", "Notices of Violation")

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_violation(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO violations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} violation records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["nbtm-fbw5", "Notices of Violation", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_complaints(conn, client: SODAClient) -> int:
    """Ingest DBI complaints into complaints table."""
    print("\n=== Ingesting DBI Complaints ===")
    conn.execute("DELETE FROM complaints")

    records = await _fetch_all_pages(client, "gm2e-bten", "DBI Complaints")

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_complaint(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO complaints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} complaint records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["gm2e-bten", "DBI Complaints", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_businesses(conn, client: SODAClient) -> int:
    """Ingest active registered business locations into businesses table."""
    print("\n=== Ingesting Registered Business Locations (active only) ===")
    conn.execute("DELETE FROM businesses")

    records = await _fetch_all_pages(
        client, "g8m3-pdis", "Registered Business Locations",
        where="location_end_date IS NULL",
    )

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_business(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO businesses VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} business records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["g8m3-pdis", "Registered Business Locations", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_boiler_permits(conn, client: SODAClient) -> int:
    """Ingest boiler permits into boiler_permits table."""
    print("\n=== Ingesting Boiler Permits ===")
    conn.execute("DELETE FROM boiler_permits")

    records = await _fetch_all_pages(client, "5dp4-gtxk", "Boiler Permits")

    batch = [_normalize_boiler_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO boiler_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} boiler permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["5dp4-gtxk", "Boiler Permits", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_fire_permits(conn, client: SODAClient) -> int:
    """Ingest fire permits into fire_permits table."""
    print("\n=== Ingesting Fire Permits ===")
    conn.execute("DELETE FROM fire_permits")

    records = await _fetch_all_pages(client, "893e-xam6", "Fire Permits")

    batch = [_normalize_fire_permit(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO fire_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} fire permit records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["893e-xam6", "Fire Permits", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_planning_records(conn, client: SODAClient) -> int:
    """Ingest planning records (projects + non-projects) into planning_records table."""
    print("\n=== Ingesting Planning Records ===")
    conn.execute("DELETE FROM planning_records")

    total = 0

    # Projects
    print("\n[1/2] Planning Projects (qvu5-m3a2)")
    projects = await _fetch_all_pages(client, "qvu5-m3a2", "Planning Projects")
    batch = [_normalize_planning_project(r) for r in projects]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO planning_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} planning project records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["qvu5-m3a2", "Planning Projects", datetime.now(timezone.utc).isoformat(), len(projects), len(projects)],
    )

    # Non-projects
    print("\n[2/2] Planning Non-Projects (y673-d69b)")
    non_projects = await _fetch_all_pages(client, "y673-d69b", "Planning Non-Projects")
    batch = [_normalize_planning_non_project(r) for r in non_projects]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO planning_records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)
        print(f"  Loaded {len(batch):,} planning non-project records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["y673-d69b", "Planning Non-Projects", datetime.now(timezone.utc).isoformat(), len(non_projects), len(non_projects)],
    )

    print(f"\n  Total planning records loaded: {total:,}")
    return total


TAX_ROLL_YEAR_FILTER = "closed_roll_year >= '2022'"
TAX_ROLL_BATCH_FLUSH = 50_000  # Flush to DB every 50K rows to limit memory
STREET_USE_BATCH_FLUSH = 50_000  # Street-use permits ~1.2M rows — flush periodically


async def ingest_tax_rolls(conn, client: SODAClient) -> int:
    """Ingest tax rolls (latest 3 years) into tax_rolls table.

    Uses streaming pagination with periodic batch flushes to avoid OOM
    on memory-constrained Railway containers (~600K rows).
    """
    print("\n=== Ingesting Tax Rolls (3-year filter) ===")
    conn.execute("DELETE FROM tax_rolls")

    endpoint_id = "wv5m-vpq2"
    total_count = await client.count(endpoint_id, where=TAX_ROLL_YEAR_FILTER)
    print(f"  Tax Rolls: {total_count:,} total records to fetch")

    total = 0
    offset = 0
    start = time.time()
    max_retries = 3
    batch = []

    while True:
        page = None
        for attempt in range(max_retries):
            try:
                page = await client.query(
                    endpoint_id=endpoint_id,
                    where=TAX_ROLL_YEAR_FILTER,
                    limit=PAGE_SIZE,
                    offset=offset,
                    order=":id",
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retry {attempt + 1}/{max_retries}: {e}. Waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    raise
        if not page:
            break

        for r in page:
            batch.append(_normalize_tax_roll(r))

        offset += len(page)
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        pct = offset * 100 // total_count if total_count else 0
        print(
            f"  Fetched {offset:,}/{total_count:,} ({pct}%) — "
            f"{rate:,.0f} rec/s — {elapsed:.1f}s",
            flush=True,
        )

        # Flush batch to DB periodically to limit memory
        if len(batch) >= TAX_ROLL_BATCH_FLUSH:
            conn.executemany(
                "INSERT OR REPLACE INTO tax_rolls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            total += len(batch)
            batch = []

        if len(page) < PAGE_SIZE:
            break

    # Flush remaining
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO tax_rolls VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["wv5m-vpq2", "Tax Rolls", datetime.now(timezone.utc).isoformat(), total, total],
    )
    elapsed = time.time() - start
    print(f"  Loaded {total:,} tax roll records in {elapsed:.1f}s")
    return total


def _extract_addenda_contacts(conn, start_row_id: int) -> int:
    """Extract plan_checked_by from addenda as contacts for entity resolution."""
    print("\n  Extracting addenda contacts (plan_checked_by)...")

    # Get distinct (application_number, plan_checked_by) pairs
    try:
        records = conn.execute("""
            SELECT DISTINCT application_number, plan_checked_by
            FROM addenda
            WHERE plan_checked_by IS NOT NULL
              AND TRIM(plan_checked_by) != ''
        """).fetchall()
    except Exception:
        # addenda table may not exist or be empty
        return 0

    batch = []
    row_id = start_row_id
    for app_num, checker in records:
        row_id += 1
        batch.append((
            row_id, "addenda", app_num, "plan_checker", checker,
            None, None, None,  # first_name, last_name, firm_name
            None, None, None,  # pts_agent_id, license, biz_license
            None,  # phone
            None, None, None, None,  # address, city, state, zip
            None, None,  # is_applicant, from_date
            None,  # entity_id
            None,  # data_as_of
        ))

    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} addenda contact records")

    return len(batch)


def _extract_business_contacts(conn, start_row_id: int) -> int:
    """Extract ownership_name and dba_name from businesses as contacts."""
    print("\n  Extracting business contacts (ownership_name, dba_name)...")

    try:
        records = conn.execute("""
            SELECT certificate_number, ownership_name, dba_name
            FROM businesses
            WHERE ownership_name IS NOT NULL OR dba_name IS NOT NULL
        """).fetchall()
    except Exception:
        # businesses table may not exist or be empty
        return 0

    batch = []
    row_id = start_row_id
    seen = set()  # Avoid duplicate (cert_number, name) pairs

    for cert_num, owner, dba in records:
        permit_ref = cert_num or ""

        if owner and (permit_ref, owner) not in seen:
            seen.add((permit_ref, owner))
            row_id += 1
            batch.append((
                row_id, "business", permit_ref, "owner", owner,
                None, None, None,  # first_name, last_name, firm_name
                None, None, None,  # pts_agent_id, license, biz_license
                None,  # phone
                None, None, None, None,  # address, city, state, zip
                None, None,  # is_applicant, from_date
                None,  # entity_id
                None,  # data_as_of
            ))

        if dba and dba != owner and (permit_ref, dba) not in seen:
            seen.add((permit_ref, dba))
            row_id += 1
            batch.append((
                row_id, "business", permit_ref, "dba", dba,
                None, None, None,
                None, None, None,
                None,
                None, None, None, None,
                None, None,
                None,
                None,
            ))

    if batch:
        conn.executemany(
            "INSERT INTO contacts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} business contact records")

    return len(batch)


async def ingest_street_use_permits(conn, client: SODAClient) -> int:
    """Ingest street-use permits (~1.2M records) into street_use_permits table.

    Uses streaming pagination with periodic batch flushes to avoid OOM
    on memory-constrained Railway containers.
    """
    print("\n=== Ingesting Street-Use Permits ===")
    conn.execute("DELETE FROM street_use_permits")

    endpoint_id = "b6tj-gt35"
    total_count = await client.count(endpoint_id)
    print(f"  Street-Use Permits: {total_count:,} total records to fetch")

    total = 0
    offset = 0
    start = time.time()
    max_retries = 3
    batch = []

    while True:
        page = None
        for attempt in range(max_retries):
            try:
                page = await client.query(
                    endpoint_id=endpoint_id,
                    limit=PAGE_SIZE,
                    offset=offset,
                    order=":id",
                )
                break
            except Exception as e:
                if attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    print(f"  Retry {attempt + 1}/{max_retries}: {e}. Waiting {wait}s...", flush=True)
                    await asyncio.sleep(wait)
                else:
                    raise
        if not page:
            break

        for r in page:
            batch.append(_normalize_street_use_permit(r))

        offset += len(page)
        elapsed = time.time() - start
        rate = offset / elapsed if elapsed > 0 else 0
        pct = offset * 100 // total_count if total_count else 0
        print(
            f"  Fetched {offset:,}/{total_count:,} ({pct}%) — "
            f"{rate:,.0f} rec/s — {elapsed:.1f}s",
            flush=True,
        )

        # Flush batch to DB periodically to limit memory
        if len(batch) >= STREET_USE_BATCH_FLUSH:
            conn.executemany(
                "INSERT OR REPLACE INTO street_use_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                batch,
            )
            conn.commit()  # Commit each batch so partial data survives timeouts
            total += len(batch)
            batch = []

        if len(page) < PAGE_SIZE:
            break

    # Flush remaining
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO street_use_permits VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        total += len(batch)

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["b6tj-gt35", "Street-Use Permits", datetime.now(timezone.utc).isoformat(), total, total],
    )
    elapsed = time.time() - start
    print(f"  Loaded {total:,} street-use permit records in {elapsed:.1f}s")
    return total


async def ingest_development_pipeline(conn, client: SODAClient) -> int:
    """Ingest SF Development Pipeline (~2K records) into development_pipeline table."""
    print("\n=== Ingesting SF Development Pipeline ===")
    conn.execute("DELETE FROM development_pipeline")

    records = await _fetch_all_pages(client, "6jgi-cpb4", "SF Development Pipeline")

    batch = [_normalize_development_pipeline(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO development_pipeline VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} development pipeline records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["6jgi-cpb4", "SF Development Pipeline", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_affordable_housing(conn, client: SODAClient) -> int:
    """Ingest Affordable Housing Pipeline (~194 records) into affordable_housing table."""
    print("\n=== Ingesting Affordable Housing Pipeline ===")
    conn.execute("DELETE FROM affordable_housing")

    records = await _fetch_all_pages(client, "aaxw-2cb8", "Affordable Housing Pipeline")

    batch = [_normalize_affordable_housing(r) for r in records]
    if batch:
        conn.executemany(
            "INSERT OR REPLACE INTO affordable_housing VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} affordable housing records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["aaxw-2cb8", "Affordable Housing Pipeline", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_housing_production(conn, client: SODAClient) -> int:
    """Ingest Housing Production (~5.8K records) into housing_production table."""
    print("\n=== Ingesting Housing Production ===")
    conn.execute("DELETE FROM housing_production")

    records = await _fetch_all_pages(client, "xdht-4php", "Housing Production")

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_housing_production(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO housing_production VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} housing production records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["xdht-4php", "Housing Production", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def ingest_dwelling_completions(conn, client: SODAClient) -> int:
    """Ingest Dwelling Unit Completions (~2.4K records) into dwelling_completions table."""
    print("\n=== Ingesting Dwelling Unit Completions ===")
    conn.execute("DELETE FROM dwelling_completions")

    records = await _fetch_all_pages(client, "j67f-aayr", "Dwelling Unit Completions")

    batch = []
    for i, r in enumerate(records, 1):
        batch.append(_normalize_dwelling_completion(r, i))
    if batch:
        conn.executemany(
            "INSERT INTO dwelling_completions VALUES (?, ?, ?, ?, ?, ?, ?)",
            batch,
        )
        print(f"  Loaded {len(batch):,} dwelling completion records")

    conn.execute(
        "INSERT OR REPLACE INTO ingest_log VALUES (?, ?, ?, ?, ?)",
        ["j67f-aayr", "Dwelling Unit Completions", datetime.now(timezone.utc).isoformat(), len(records), len(records)],
    )
    return len(batch)


async def run_ingestion(
    contacts: bool = True,
    permits: bool = True,
    inspections: bool = True,
    plumbing_inspections: bool = True,
    addenda: bool = True,
    violations: bool = True,
    complaints: bool = True,
    businesses: bool = True,
    electrical_permits: bool = True,
    plumbing_permits: bool = True,
    boiler: bool = True,
    fire: bool = True,
    planning: bool = True,
    tax_rolls: bool = True,
    street_use: bool = True,
    development_pipeline: bool = True,
    affordable_housing: bool = True,
    housing_production: bool = True,
    dwelling_completions: bool = True,
    db_path: str | None = None,
) -> dict:
    """Run the full ingestion pipeline.

    Returns dict with counts of records ingested per dataset.
    """
    start = time.time()
    conn = get_connection(db_path)
    init_schema(conn)

    client = SODAClient()
    results = {}

    try:
        # Ingest new datasets first so contact extraction can read them
        if addenda:
            results["addenda"] = await ingest_addenda(conn, client)
        if violations:
            results["violations"] = await ingest_violations(conn, client)
        if complaints:
            results["complaints"] = await ingest_complaints(conn, client)
        if businesses:
            results["businesses"] = await ingest_businesses(conn, client)
        if contacts:
            results["contacts"] = await ingest_contacts(conn, client)
        if permits:
            results["permits"] = await ingest_permits(conn, client)
        if electrical_permits:
            results["electrical_permits"] = await ingest_electrical_permits(conn, client)
        if plumbing_permits:
            results["plumbing_permits"] = await ingest_plumbing_permits(conn, client)
        if inspections:
            results["inspections"] = await ingest_inspections(conn, client)
        if plumbing_inspections:
            results["plumbing_inspections"] = await ingest_plumbing_inspections(conn, client)
        if boiler:
            results["boiler_permits"] = await ingest_boiler_permits(conn, client)
        if fire:
            results["fire_permits"] = await ingest_fire_permits(conn, client)
        if planning:
            results["planning_records"] = await ingest_planning_records(conn, client)
        if tax_rolls:
            results["tax_rolls"] = await ingest_tax_rolls(conn, client)
        if street_use:
            results["street_use_permits"] = await ingest_street_use_permits(conn, client)
        if development_pipeline:
            results["development_pipeline"] = await ingest_development_pipeline(conn, client)
        if affordable_housing:
            results["affordable_housing"] = await ingest_affordable_housing(conn, client)
        if housing_production:
            results["housing_production"] = await ingest_housing_production(conn, client)
        if dwelling_completions:
            results["dwelling_completions"] = await ingest_dwelling_completions(conn, client)
    finally:
        await client.close()

    elapsed = time.time() - start
    total = sum(results.values())
    print(f"\n{'=' * 60}")
    print(f"Ingestion complete: {total:,} total records in {elapsed:.1f}s")
    for k, v in results.items():
        print(f"  {k}: {v:,}")
    print(f"{'=' * 60}")

    conn.close()
    return results


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ingest SF permit data into DuckDB")
    parser.add_argument("--contacts", action="store_true", help="Only ingest contacts")
    parser.add_argument("--permits", action="store_true", help="Only ingest permits")
    parser.add_argument("--inspections", action="store_true", help="Only ingest inspections")
    parser.add_argument("--addenda", action="store_true", help="Only ingest addenda routing")
    parser.add_argument("--violations", action="store_true", help="Only ingest violations")
    parser.add_argument("--complaints", action="store_true", help="Only ingest complaints")
    parser.add_argument("--businesses", action="store_true", help="Only ingest businesses")
    parser.add_argument("--electrical-permits", action="store_true", help="Only ingest electrical permits")
    parser.add_argument("--plumbing-permits", action="store_true", help="Only ingest plumbing permits")
    parser.add_argument("--boiler", action="store_true", help="Only ingest boiler permits")
    parser.add_argument("--fire", action="store_true", help="Only ingest fire permits")
    parser.add_argument("--planning", action="store_true", help="Only ingest planning records")
    parser.add_argument("--tax-rolls", action="store_true", help="Only ingest tax rolls")
    parser.add_argument("--street-use", action="store_true", help="Only ingest street-use permits")
    parser.add_argument("--development-pipeline", action="store_true", help="Only ingest SF development pipeline")
    parser.add_argument("--affordable-housing", action="store_true", help="Only ingest affordable housing pipeline")
    parser.add_argument("--housing-production", action="store_true", help="Only ingest housing production")
    parser.add_argument("--dwelling-completions", action="store_true", help="Only ingest dwelling unit completions")
    parser.add_argument("--db", type=str, help="Custom database path")
    args = parser.parse_args()

    # If no specific flag, ingest everything
    do_all = not (args.contacts or args.permits or args.inspections
                  or args.addenda or args.violations or args.complaints
                  or args.businesses or args.electrical_permits or args.plumbing_permits
                  or args.boiler or args.fire
                  or args.planning or args.tax_rolls
                  or args.street_use or args.development_pipeline
                  or args.affordable_housing or args.housing_production
                  or args.dwelling_completions)

    asyncio.run(
        run_ingestion(
            contacts=do_all or args.contacts,
            permits=do_all or args.permits,
            inspections=do_all or args.inspections,
            addenda=do_all or args.addenda,
            violations=do_all or args.violations,
            complaints=do_all or args.complaints,
            businesses=do_all or args.businesses,
            electrical_permits=do_all or args.electrical_permits,
            plumbing_permits=do_all or args.plumbing_permits,
            boiler=do_all or args.boiler,
            fire=do_all or args.fire,
            planning=do_all or args.planning,
            tax_rolls=do_all or args.tax_rolls,
            street_use=do_all or args.street_use,
            development_pipeline=do_all or args.development_pipeline,
            affordable_housing=do_all or args.affordable_housing,
            housing_production=do_all or args.housing_production,
            dwelling_completions=do_all or args.dwelling_completions,
            db_path=args.db,
        )
    )


if __name__ == "__main__":
    main()
