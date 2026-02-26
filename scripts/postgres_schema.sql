-- sfpermits.ai PostgreSQL schema
-- Mirrors DuckDB tables 1:1 (Option A: migrate what we have)
-- Run against Railway Postgres after creating the database.

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- Core tables (migrated from DuckDB)
-- ============================================================

-- Permits (1.1M records)
CREATE TABLE IF NOT EXISTS permits (
    permit_number   TEXT PRIMARY KEY,
    permit_type     TEXT,
    permit_type_definition TEXT,
    status          TEXT,
    status_date     TEXT,       -- kept as TEXT to match DuckDB (mixed formats)
    description     TEXT,
    filed_date      TEXT,
    issued_date     TEXT,
    approved_date   TEXT,
    completed_date  TEXT,
    estimated_cost  DOUBLE PRECISION,
    revised_cost    DOUBLE PRECISION,
    existing_use    TEXT,
    proposed_use    TEXT,
    existing_units  INTEGER,
    proposed_units  INTEGER,
    street_number   TEXT,
    street_name     TEXT,
    street_suffix   TEXT,
    zipcode         TEXT,
    neighborhood    TEXT,
    supervisor_district TEXT,
    block           TEXT,
    lot             TEXT,
    adu             TEXT,
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_permits_neighborhood ON permits(neighborhood);
CREATE INDEX IF NOT EXISTS idx_permits_type ON permits(permit_type_definition);
CREATE INDEX IF NOT EXISTS idx_permits_status ON permits(status);
CREATE INDEX IF NOT EXISTS idx_permits_filed ON permits(filed_date);
CREATE INDEX IF NOT EXISTS idx_permits_cost ON permits(estimated_cost);
CREATE INDEX IF NOT EXISTS idx_permits_block_lot ON permits(block, lot);
CREATE INDEX IF NOT EXISTS idx_permits_street ON permits(street_number, street_name);

-- Contacts (1.8M records)
CREATE TABLE IF NOT EXISTS contacts (
    id              INTEGER PRIMARY KEY,
    source          TEXT,
    permit_number   TEXT,
    role            TEXT,
    name            TEXT,
    first_name      TEXT,
    last_name       TEXT,
    firm_name       TEXT,
    pts_agent_id    TEXT,
    license_number  TEXT,
    sf_business_license TEXT,
    phone           TEXT,
    address         TEXT,
    city            TEXT,
    state           TEXT,
    zipcode         TEXT,
    is_applicant    TEXT,
    from_date       TEXT,
    entity_id       INTEGER,
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_contacts_permit ON contacts(permit_number);
CREATE INDEX IF NOT EXISTS idx_contacts_entity ON contacts(entity_id);
CREATE INDEX IF NOT EXISTS idx_contacts_role ON contacts(role);
CREATE INDEX IF NOT EXISTS idx_contacts_name ON contacts(name);
CREATE INDEX IF NOT EXISTS idx_contacts_pts_agent ON contacts(pts_agent_id);
CREATE INDEX IF NOT EXISTS idx_contacts_license ON contacts(license_number);
-- Trigram indexes for fuzzy search
CREATE INDEX IF NOT EXISTS idx_contacts_name_trgm ON contacts USING gin(name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_contacts_firm_trgm ON contacts USING gin(firm_name gin_trgm_ops);

-- Entities (1M resolved records)
CREATE TABLE IF NOT EXISTS entities (
    entity_id       INTEGER PRIMARY KEY,
    canonical_name  TEXT,
    canonical_firm  TEXT,
    entity_type     TEXT,
    pts_agent_id    TEXT,
    license_number  TEXT,
    sf_business_license TEXT,
    resolution_method TEXT,
    resolution_confidence TEXT,
    contact_count   INTEGER,
    permit_count    INTEGER,
    source_datasets TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(canonical_name);
CREATE INDEX IF NOT EXISTS idx_entities_license ON entities(license_number);
CREATE INDEX IF NOT EXISTS idx_entities_pts ON entities(pts_agent_id);
-- Trigram index for fuzzy entity search (team lookup)
CREATE INDEX IF NOT EXISTS idx_entities_name_trgm ON entities USING gin(canonical_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_entities_firm_trgm ON entities USING gin(canonical_firm gin_trgm_ops);

-- Relationships (576K co-occurrence edges)
CREATE TABLE IF NOT EXISTS relationships (
    entity_id_a     INTEGER,
    entity_id_b     INTEGER,
    shared_permits  INTEGER,
    permit_numbers  TEXT,
    permit_types    TEXT,
    date_range_start TEXT,
    date_range_end  TEXT,
    total_estimated_cost DOUBLE PRECISION,
    neighborhoods   TEXT,
    PRIMARY KEY (entity_id_a, entity_id_b)
);

CREATE INDEX IF NOT EXISTS idx_rel_a ON relationships(entity_id_a);
CREATE INDEX IF NOT EXISTS idx_rel_b ON relationships(entity_id_b);

-- Inspections (671K records)
CREATE TABLE IF NOT EXISTS inspections (
    id              INTEGER PRIMARY KEY,
    reference_number TEXT,
    reference_number_type TEXT,
    inspector       TEXT,
    scheduled_date  TEXT,
    result          TEXT,
    inspection_description TEXT,
    block           TEXT,
    lot             TEXT,
    street_number   TEXT,
    street_name     TEXT,
    street_suffix   TEXT,
    neighborhood    TEXT,
    supervisor_district TEXT,
    zipcode         TEXT,
    data_as_of      TEXT,
    source          TEXT DEFAULT 'building'
);

-- Migration: add source column to existing inspections table
ALTER TABLE inspections ADD COLUMN IF NOT EXISTS source TEXT DEFAULT 'building';

CREATE INDEX IF NOT EXISTS idx_inspections_ref ON inspections(reference_number);
CREATE INDEX IF NOT EXISTS idx_inspections_inspector ON inspections(inspector);
CREATE INDEX IF NOT EXISTS idx_inspections_source ON inspections(source);
-- NOTE: uk_inspections_natural UNIQUE index is applied by the inspections_unique
-- migration (run_prod_migrations.py) which deduplicates first. Do NOT add it here
-- because this file runs as one transaction and will fail on existing duplicates.

-- Addenda (3.9M records — permit review routing steps)
CREATE TABLE IF NOT EXISTS addenda (
    id                  INTEGER PRIMARY KEY,
    primary_key         TEXT,
    application_number  TEXT NOT NULL,
    addenda_number      INTEGER,
    step                INTEGER,
    station             TEXT,
    arrive              TEXT,
    assign_date         TEXT,
    start_date          TEXT,
    finish_date         TEXT,
    approved_date       TEXT,
    plan_checked_by     TEXT,
    review_results      TEXT,
    hold_description    TEXT,
    addenda_status      TEXT,
    department          TEXT,
    title               TEXT,
    data_as_of          TEXT
);

CREATE INDEX IF NOT EXISTS idx_addenda_app_num ON addenda(application_number);
CREATE INDEX IF NOT EXISTS idx_addenda_station ON addenda(station);
CREATE INDEX IF NOT EXISTS idx_addenda_reviewer ON addenda(plan_checked_by);
CREATE INDEX IF NOT EXISTS idx_addenda_finish ON addenda(finish_date);
CREATE INDEX IF NOT EXISTS idx_addenda_app_step ON addenda(application_number, addenda_number, step);
CREATE INDEX IF NOT EXISTS idx_addenda_primary_key ON addenda(primary_key);
CREATE INDEX IF NOT EXISTS idx_addenda_dept ON addenda(department);
CREATE INDEX IF NOT EXISTS idx_addenda_status ON addenda(addenda_status);

-- Violations (509K records — Notices of Violation)
CREATE TABLE IF NOT EXISTS violations (
    id                      INTEGER PRIMARY KEY,
    complaint_number        TEXT,
    item_sequence_number    TEXT,
    date_filed              TEXT,
    block                   TEXT,
    lot                     TEXT,
    street_number           TEXT,
    street_name             TEXT,
    street_suffix           TEXT,
    unit                    TEXT,
    status                  TEXT,
    receiving_division      TEXT,
    assigned_division       TEXT,
    nov_category_description TEXT,
    item                    TEXT,
    nov_item_description    TEXT,
    neighborhood            TEXT,
    supervisor_district     TEXT,
    zipcode                 TEXT,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_violations_complaint ON violations(complaint_number);
CREATE INDEX IF NOT EXISTS idx_violations_block_lot ON violations(block, lot);
CREATE INDEX IF NOT EXISTS idx_violations_status ON violations(status);
CREATE INDEX IF NOT EXISTS idx_violations_date ON violations(date_filed);

-- Complaints (326K records — DBI Complaints)
CREATE TABLE IF NOT EXISTS complaints (
    id                      INTEGER PRIMARY KEY,
    complaint_number        TEXT,
    date_filed              TEXT,
    date_abated             TEXT,
    block                   TEXT,
    lot                     TEXT,
    parcel_number           TEXT,
    street_number           TEXT,
    street_name             TEXT,
    street_suffix           TEXT,
    unit                    TEXT,
    zip_code                TEXT,
    complaint_description   TEXT,
    status                  TEXT,
    nov_type                TEXT,
    receiving_division      TEXT,
    assigned_division       TEXT,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_complaints_number ON complaints(complaint_number);
CREATE INDEX IF NOT EXISTS idx_complaints_block_lot ON complaints(block, lot);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_complaints_date ON complaints(date_filed);

-- Businesses (354K records — Registered Business Locations)
CREATE TABLE IF NOT EXISTS businesses (
    id                      INTEGER PRIMARY KEY,
    certificate_number      TEXT,
    ttxid                   TEXT,
    ownership_name          TEXT,
    dba_name                TEXT,
    full_business_address   TEXT,
    city                    TEXT,
    state                   TEXT,
    business_zip            TEXT,
    dba_start_date          TEXT,
    dba_end_date            TEXT,
    location_start_date     TEXT,
    location_end_date       TEXT,
    parking_tax             TEXT,
    transient_occupancy_tax TEXT,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_businesses_ownership ON businesses(ownership_name);
CREATE INDEX IF NOT EXISTS idx_businesses_dba ON businesses(dba_name);
CREATE INDEX IF NOT EXISTS idx_businesses_zip ON businesses(business_zip);
CREATE INDEX IF NOT EXISTS idx_businesses_cert ON businesses(certificate_number);
CREATE INDEX IF NOT EXISTS idx_businesses_ownership_trgm ON businesses USING gin(ownership_name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_businesses_dba_trgm ON businesses USING gin(dba_name gin_trgm_ops);

-- Ingest log (metadata)
CREATE TABLE IF NOT EXISTS ingest_log (
    dataset_id      TEXT PRIMARY KEY,
    dataset_name    TEXT,
    last_fetched    TEXT,
    records_fetched INTEGER,
    last_record_count INTEGER
);

-- Timeline stats (pre-computed from permits — 382K records)
-- This exists in DuckDB as a materialized table; we migrate it directly
-- and later replace with a materialized view.
CREATE TABLE IF NOT EXISTS timeline_stats (
    permit_number           TEXT,
    permit_type_definition  TEXT,
    review_path             TEXT,
    neighborhood            TEXT,
    estimated_cost          DOUBLE PRECISION,
    revised_cost            DOUBLE PRECISION,
    cost_bracket            TEXT,
    filed                   DATE,
    issued                  DATE,
    completed               DATE,
    days_to_issuance        INTEGER,
    days_to_completion      INTEGER,
    supervisor_district     TEXT
);

CREATE INDEX IF NOT EXISTS idx_ts_review ON timeline_stats(review_path);
CREATE INDEX IF NOT EXISTS idx_ts_neighborhood ON timeline_stats(neighborhood);
CREATE INDEX IF NOT EXISTS idx_ts_cost_bracket ON timeline_stats(cost_bracket);
CREATE INDEX IF NOT EXISTS idx_ts_permit_type ON timeline_stats(permit_type_definition);

-- Boiler Permits (~152K records)
CREATE TABLE IF NOT EXISTS boiler_permits (
    permit_number   TEXT PRIMARY KEY,
    block           TEXT,
    lot             TEXT,
    status          TEXT,
    boiler_type     TEXT,
    boiler_serial_number TEXT,
    model           TEXT,
    description     TEXT,
    application_date TEXT,
    expiration_date TEXT,
    street_number   TEXT,
    street_name     TEXT,
    street_suffix   TEXT,
    zip_code        TEXT,
    neighborhood    TEXT,
    supervisor_district TEXT,
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_boiler_block_lot ON boiler_permits(block, lot);
CREATE INDEX IF NOT EXISTS idx_boiler_status ON boiler_permits(status);

-- Fire Permits (~84K records)
CREATE TABLE IF NOT EXISTS fire_permits (
    permit_number   TEXT PRIMARY KEY,
    permit_type     TEXT,
    permit_type_description TEXT,
    permit_status   TEXT,
    permit_address  TEXT,
    permit_holder   TEXT,
    dba_name        TEXT,
    application_date TEXT,
    date_approved   TEXT,
    expiration_date TEXT,
    permit_fee      DOUBLE PRECISION,
    posting_fee     DOUBLE PRECISION,
    referral_fee    DOUBLE PRECISION,
    conditions      TEXT,
    battalion       TEXT,
    fire_prevention_district TEXT,
    night_assembly_permit TEXT,
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_fire_status ON fire_permits(permit_status);
CREATE INDEX IF NOT EXISTS idx_fire_holder ON fire_permits(permit_holder);
CREATE INDEX IF NOT EXISTS idx_fire_address ON fire_permits USING gin(permit_address gin_trgm_ops);

-- Planning Records (~282K records — projects + non-projects merged)
CREATE TABLE IF NOT EXISTS planning_records (
    record_id       TEXT PRIMARY KEY,
    record_type     TEXT,
    record_status   TEXT,
    block           TEXT,
    lot             TEXT,
    address         TEXT,
    project_name    TEXT,
    description     TEXT,
    applicant       TEXT,
    applicant_org   TEXT,
    assigned_planner TEXT,
    open_date       TEXT,
    environmental_doc_type TEXT,
    is_project      BOOLEAN DEFAULT TRUE,
    units_existing  INTEGER,
    units_proposed  INTEGER,
    units_net       DOUBLE PRECISION,
    affordable_units INTEGER,
    child_id        TEXT,
    parent_id       TEXT,
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_planning_block_lot ON planning_records(block, lot);
CREATE INDEX IF NOT EXISTS idx_planning_type ON planning_records(record_type);
CREATE INDEX IF NOT EXISTS idx_planning_status ON planning_records(record_status);
CREATE INDEX IF NOT EXISTS idx_planning_planner ON planning_records(assigned_planner);

-- Tax Rolls (~600K records — latest 3 years)
CREATE TABLE IF NOT EXISTS tax_rolls (
    block           TEXT,
    lot             TEXT,
    tax_year        TEXT,
    property_location TEXT,
    parcel_number   TEXT,
    zoning_code     TEXT,
    use_code        TEXT,
    use_definition  TEXT,
    property_class_code TEXT,
    property_class_code_definition TEXT,
    number_of_stories DOUBLE PRECISION,
    number_of_units INTEGER,
    number_of_rooms INTEGER,
    number_of_bedrooms INTEGER,
    number_of_bathrooms DOUBLE PRECISION,
    lot_area        DOUBLE PRECISION,
    property_area   DOUBLE PRECISION,
    assessed_land_value DOUBLE PRECISION,
    assessed_improvement_value DOUBLE PRECISION,
    assessed_personal_property DOUBLE PRECISION,
    assessed_fixtures DOUBLE PRECISION,
    current_sales_date TEXT,
    neighborhood    TEXT,
    supervisor_district TEXT,
    data_as_of      TEXT,
    PRIMARY KEY (block, lot, tax_year)
);

CREATE INDEX IF NOT EXISTS idx_tax_zoning ON tax_rolls(zoning_code);
CREATE INDEX IF NOT EXISTS idx_tax_block_lot ON tax_rolls(block, lot);
CREATE INDEX IF NOT EXISTS idx_tax_neighborhood ON tax_rolls(neighborhood);

-- Street-Use Permits (~1.2M records)
CREATE TABLE IF NOT EXISTS street_use_permits (
    permit_number       TEXT PRIMARY KEY,
    permit_type         TEXT,
    permit_purpose      TEXT,
    status              TEXT,
    agent               TEXT,
    agent_phone         TEXT,
    contact             TEXT,
    street_name         TEXT,
    cross_street_1      TEXT,
    cross_street_2      TEXT,
    plan_checker        TEXT,
    approved_date       TEXT,
    expiration_date     TEXT,
    neighborhood        TEXT,
    supervisor_district TEXT,
    latitude            DOUBLE PRECISION,
    longitude           DOUBLE PRECISION,
    cnn                 TEXT,
    data_as_of          TEXT
);

CREATE INDEX IF NOT EXISTS idx_street_use_status ON street_use_permits(status);
CREATE INDEX IF NOT EXISTS idx_street_use_street ON street_use_permits(street_name);
CREATE INDEX IF NOT EXISTS idx_street_use_neighborhood ON street_use_permits(neighborhood);

-- SF Development Pipeline (~2K records)
CREATE TABLE IF NOT EXISTS development_pipeline (
    record_id               TEXT PRIMARY KEY,
    bpa_no                  TEXT,
    case_no                 TEXT,
    name_address            TEXT,
    current_status          TEXT,
    description_dbi         TEXT,
    description_planning    TEXT,
    contact                 TEXT,
    sponsor                 TEXT,
    planner                 TEXT,
    proposed_units          INTEGER,
    existing_units          INTEGER,
    net_pipeline_units      INTEGER,
    affordable_units        INTEGER,
    zoning_district         TEXT,
    height_district         TEXT,
    neighborhood            TEXT,
    planning_district       TEXT,
    approved_date_planning  TEXT,
    block_lot               TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_dev_pipeline_bpa ON development_pipeline(bpa_no);
CREATE INDEX IF NOT EXISTS idx_dev_pipeline_case ON development_pipeline(case_no);
CREATE INDEX IF NOT EXISTS idx_dev_pipeline_block_lot ON development_pipeline(block_lot);
CREATE INDEX IF NOT EXISTS idx_dev_pipeline_status ON development_pipeline(current_status);

-- Affordable Housing Pipeline (~194 records)
CREATE TABLE IF NOT EXISTS affordable_housing (
    project_id              TEXT PRIMARY KEY,
    project_name            TEXT,
    project_lead_sponsor    TEXT,
    planning_case_number    TEXT,
    address                 TEXT,
    total_project_units     INTEGER,
    affordable_units        INTEGER,
    affordable_percent      DOUBLE PRECISION,
    construction_status     TEXT,
    housing_tenure          TEXT,
    housing_program         TEXT,
    supervisor_district     TEXT,
    neighborhood            TEXT,
    latitude                DOUBLE PRECISION,
    longitude               DOUBLE PRECISION,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_affordable_status ON affordable_housing(construction_status);
CREATE INDEX IF NOT EXISTS idx_affordable_case ON affordable_housing(planning_case_number);

-- Housing Production (~5.8K records)
CREATE TABLE IF NOT EXISTS housing_production (
    id                      INTEGER PRIMARY KEY,
    bpa                     TEXT,
    address                 TEXT,
    block_lot               TEXT,
    description             TEXT,
    permit_type             TEXT,
    issued_date             TEXT,
    first_completion_date   TEXT,
    latest_completion_date  TEXT,
    proposed_units          INTEGER,
    net_units               INTEGER,
    net_units_completed     INTEGER,
    market_rate             INTEGER,
    affordable_units        INTEGER,
    zoning_district         TEXT,
    neighborhood            TEXT,
    supervisor_district     TEXT,
    data_as_of              TEXT
);

CREATE INDEX IF NOT EXISTS idx_housing_prod_bpa ON housing_production(bpa);
CREATE INDEX IF NOT EXISTS idx_housing_prod_block_lot ON housing_production(block_lot);

-- Dwelling Unit Completions (~2.4K records)
CREATE TABLE IF NOT EXISTS dwelling_completions (
    id                          INTEGER PRIMARY KEY,
    building_address            TEXT,
    building_permit_application TEXT,
    date_issued                 TEXT,
    document_type               TEXT,
    number_of_units_certified   INTEGER,
    data_as_of                  TEXT
);

CREATE INDEX IF NOT EXISTS idx_dwelling_permit ON dwelling_completions(building_permit_application);
CREATE INDEX IF NOT EXISTS idx_dwelling_doc_type ON dwelling_completions(document_type);

-- ============================================================
-- Materialized views (Step 3 — for the 5 decision tools)
-- ============================================================

-- These will be created AFTER data is loaded.
-- See scripts/create_materialized_views.sql

-- ============================================================
-- Reference tables for predict_permits (Sprint 55B)
-- ============================================================

-- Zoning code → agency routing requirements
CREATE TABLE IF NOT EXISTS ref_zoning_routing (
    zoning_code TEXT PRIMARY KEY,
    zoning_category TEXT,
    planning_review_required BOOLEAN DEFAULT FALSE,
    fire_review_required BOOLEAN DEFAULT FALSE,
    health_review_required BOOLEAN DEFAULT FALSE,
    historic_district BOOLEAN DEFAULT FALSE,
    height_limit TEXT,
    notes TEXT
);

-- Project type → required permit forms
CREATE TABLE IF NOT EXISTS ref_permit_forms (
    id SERIAL PRIMARY KEY,
    project_type TEXT NOT NULL,
    permit_form TEXT NOT NULL,
    review_path TEXT,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ref_forms_type ON ref_permit_forms(project_type);

-- Trigger keyword → agency routing
CREATE TABLE IF NOT EXISTS ref_agency_triggers (
    id SERIAL PRIMARY KEY,
    trigger_keyword TEXT NOT NULL,
    agency TEXT NOT NULL,
    reason TEXT,
    adds_weeks INTEGER
);

CREATE INDEX IF NOT EXISTS idx_ref_triggers_keyword ON ref_agency_triggers(trigger_keyword);

-- ============================================================
-- Sprint 56D: Shareable Analysis + Three-Tier Signup
-- ============================================================

-- Analysis sessions (results from the /analyze 5-tool workflow, shareable)
-- NOTE: results_json uses JSONB on Postgres for indexing; TEXT on DuckDB
CREATE TABLE IF NOT EXISTS analysis_sessions (
    id TEXT PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    project_description TEXT NOT NULL,
    address TEXT,
    neighborhood TEXT,
    estimated_cost DOUBLE PRECISION,
    square_footage DOUBLE PRECISION,
    results_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    shared_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user ON analysis_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_sessions_created ON analysis_sessions(created_at);

-- Beta requests queue (organic signups waiting for Tim's approval)
CREATE TABLE IF NOT EXISTS beta_requests (
    id SERIAL PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    name TEXT,
    reason TEXT,
    ip TEXT,
    honeypot_filled BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'pending',
    admin_note TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_beta_requests_email ON beta_requests(email);
CREATE INDEX IF NOT EXISTS idx_beta_requests_status ON beta_requests(status);
-- Sprint 56F: Review Metrics tables
-- ============================================================

-- DBI Permit Issuance Metrics (gzxm-jz5j)
-- Tracks OTC vs in-house issuance timing per permit
CREATE TABLE IF NOT EXISTS permit_issuance_metrics (
    id                  SERIAL PRIMARY KEY,
    bpa                 TEXT,
    addenda_number      INTEGER,
    bpa_addenda         TEXT,
    permit_type         TEXT,
    otc_ih              TEXT,
    status              TEXT,
    block               TEXT,
    lot                 TEXT,
    street_number       TEXT,
    street_name         TEXT,
    street_suffix       TEXT,
    unit                TEXT,
    description         TEXT,
    fire_only_permit    BOOLEAN,
    filed_date          TEXT,
    issued_date         TEXT,
    issued_status       TEXT,
    issued_year         TEXT,
    calendar_days       INTEGER,
    business_days       INTEGER,
    data_as_of          TEXT,
    ingested_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pim_bpa ON permit_issuance_metrics(bpa);
CREATE INDEX IF NOT EXISTS idx_pim_otc_ih ON permit_issuance_metrics(otc_ih);
CREATE INDEX IF NOT EXISTS idx_pim_issued_year ON permit_issuance_metrics(issued_year);

-- DBI Permit Review Metrics (5bat-azvb)
-- Tracks per-station review timing, SLA compliance, and routing results
CREATE TABLE IF NOT EXISTS permit_review_metrics (
    id                  SERIAL PRIMARY KEY,
    primary_key         TEXT,
    bpa                 TEXT,
    addenda_number      INTEGER,
    bpa_addenda         TEXT,
    permit_type         TEXT,
    block               TEXT,
    lot                 TEXT,
    street_number       TEXT,
    street_name         TEXT,
    street_suffix       TEXT,
    description         TEXT,
    fire_only_permit    TEXT,
    filed_date          TEXT,
    status              TEXT,
    department          TEXT,
    station             TEXT,
    review_type         TEXT,
    review_number       INTEGER,
    review_results      TEXT,
    arrive_date         TEXT,
    start_year          TEXT,
    start_date          TEXT,
    start_date_source   TEXT,
    sla_days            INTEGER,
    due_date            TEXT,
    finish_date         TEXT,
    calendar_days       DOUBLE PRECISION,
    met_cal_sla         BOOLEAN,
    data_as_of          TEXT,
    ingested_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prm_bpa ON permit_review_metrics(bpa);
CREATE INDEX IF NOT EXISTS idx_prm_station ON permit_review_metrics(station);
CREATE INDEX IF NOT EXISTS idx_prm_department ON permit_review_metrics(department);
CREATE INDEX IF NOT EXISTS idx_prm_met_sla ON permit_review_metrics(met_cal_sla);

-- Sprint 61B: Projects + project_members (team seed)
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT,
    address TEXT,
    block TEXT,
    lot TEXT,
    neighborhood TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS project_members (
    project_id TEXT NOT NULL REFERENCES projects(id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    role TEXT DEFAULT 'member',
    invited_by INTEGER REFERENCES users(id),
    joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (project_id, user_id)
);
ALTER TABLE analysis_sessions ADD COLUMN IF NOT EXISTS project_id TEXT REFERENCES projects(id);
CREATE INDEX IF NOT EXISTS idx_projects_created_by ON projects (created_by);
CREATE INDEX IF NOT EXISTS idx_projects_parcel ON projects (block, lot);
CREATE INDEX IF NOT EXISTS idx_pm_user ON project_members (user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_project ON analysis_sessions (project_id);

-- Planning Department Review Metrics (d4jk-jw33)
-- Tracks planning review cycle times against SLA targets per project stage
CREATE TABLE IF NOT EXISTS planning_review_metrics (
    id                          SERIAL PRIMARY KEY,
    b1_alt_id                   TEXT,
    project_stage               TEXT,
    observation_window_type     TEXT,
    observation_window_date     TEXT,
    start_event_type            TEXT,
    start_event_date            TEXT,
    end_event_type              TEXT,
    end_event_date              TEXT,
    metric_value                DOUBLE PRECISION,
    sla_value                   DOUBLE PRECISION,
    metric_outcome              TEXT,
    data_as_of                  TEXT,
    ingested_at                 TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_plrm_b1_alt_id ON planning_review_metrics(b1_alt_id);
CREATE INDEX IF NOT EXISTS idx_plrm_stage ON planning_review_metrics(project_stage);
CREATE INDEX IF NOT EXISTS idx_plrm_outcome ON planning_review_metrics(metric_outcome);
