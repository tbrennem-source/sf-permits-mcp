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
    data_as_of      TEXT
);

CREATE INDEX IF NOT EXISTS idx_inspections_ref ON inspections(reference_number);
CREATE INDEX IF NOT EXISTS idx_inspections_inspector ON inspections(inspector);

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

-- ============================================================
-- Materialized views (Step 3 — for the 5 decision tools)
-- ============================================================

-- These will be created AFTER data is loaded.
-- See scripts/create_materialized_views.sql
