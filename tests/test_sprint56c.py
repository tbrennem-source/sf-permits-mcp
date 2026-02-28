"""Tests for Sprint 56C — plumbing inspections, street use / dev pipeline brief + nightly.

Covers:
- normalize_plumbing_inspection: field mapping, source tag, NULL handling
- ingest_plumbing_inspections: DB round-trip in-memory DuckDB (no network)
- inspections table: source column exists and defaults to 'building'
- Brief street use activity: _get_street_use_activity, get_street_use_activity_for_user
- Brief nearby development: _get_nearby_development, get_nearby_development_for_user
- get_morning_brief includes street_use_activity + nearby_development keys
- Nightly change detection: detect_street_use_changes, detect_development_pipeline_changes
- Cron endpoint /cron/ingest-plumbing-inspections: auth, happy-path
"""

import asyncio
import pytest
import duckdb

import src.db as db_mod
from src.db import init_schema, init_user_schema


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_sprint56c.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    conn = db_mod.get_connection()
    try:
        init_schema(conn)
        init_user_schema(conn)
    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    """Flask test client."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    monkeypatch.setenv("CRON_WORKER", "1")
    monkeypatch.setenv("CRON_SECRET", "correct-secret")

    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class _FakeClient:
    """Fake SODA client that returns canned data without network calls."""

    def __init__(self, data=None, data_map=None):
        self._data = data or []
        self._data_map = data_map or {}

    async def count(self, endpoint_id, where=None):
        if self._data_map:
            return len(self._data_map.get(endpoint_id, []))
        return len(self._data)

    async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
        records = self._data_map.get(endpoint_id, self._data) if self._data_map else self._data
        offset = offset or 0
        return records[offset:offset + (limit or len(records))]

    async def close(self):
        pass


# ── Sample records ─────────────────────────────────────────────────

SAMPLE_PLUMBING_INSP = {
    "reference_number": "PP20250627121",
    "reference_number_type": "permit",
    "block": "3534",
    "lot": "068",
    "street_number": "102",
    "avs_street_name": "GUERRERO",
    "avs_street_sfx": "ST",
    "inspector": "Edward Kelly",
    "scheduled_date": "2025-07-08T00:00:00.000",
    "inspection_description": "SHOWER PAN INSTALLATION",
    "zip_code": "94103",
    "supervisor_district": "9",
    "analysis_neighborhood": "Mission",
    "data_as_of": "2026-02-25T00:33:03.000",
}

SAMPLE_PLUMBING_INSP_NO_RESULT = {
    "reference_number": "PP20250627122",
    "reference_number_type": "permit",
    "block": "3755",
    "lot": "023",
    "street_number": "1140",
    "avs_street_name": "HARRISON",
    "avs_street_sfx": "ST",
    "inspector": "David Gordon",
    "scheduled_date": "2025-04-29T00:00:00.000",
    "inspection_description": "FINAL PLUMBING INSPECTION",
    "zip_code": "94103",
    "supervisor_district": "3",
    "analysis_neighborhood": "South of Market",
    "data_as_of": "2026-02-25T00:33:03.000",
}

SAMPLE_STREET_USE = {
    "permit_number": "SUP-2026-001",
    "permit_type": "occupancy",
    "permit_purpose": "Construction",
    "status": "approved",
    "agent": "ABC Construction",
    "agent_phone": "415-555-1234",
    "contact": "John Doe",
    "street_name": "MARKET",
    "cross_street_1": "4TH",
    "cross_street_2": "5TH",
    "plan_checker": "Jane Smith",
    "approved_date": "2026-02-01T00:00:00.000",
    "expiration_date": "2026-08-01T00:00:00.000",
    "neighborhood": "Tenderloin",
    "supervisor_district": "6",
    "latitude": 37.7749,
    "longitude": -122.4194,
    "data_as_of": "2026-02-25T00:33:03.000",
}

SAMPLE_DEV_PIPELINE = {
    "record_id": "DEV-2026-001",
    "bpa_no": "202501012345",
    "case_no": "2025-001234ENX",
    "name_address": "100 NEW ST",
    "current_status": "BUILDING PERMIT ISSUED",
    "description_dbi": "New 50-unit residential",
    "description_planning": "Market-rate housing development",
    "contact": "Developer LLC",
    "sponsor": "Developer LLC",
    "planner": "Planner Name",
    "proposed_units": 50,
    "existing_units": 0,
    "net_pipeline_units": 50,
    "affordable_units": 10,
    "zoning_district": "UMU",
    "height_district": "85-X",
    "neighborhood": "Mission",
    "planning_district": "6",
    "approved_date_planning": "2026-01-15T00:00:00.000",
    "block_lot": "3534/001",
    "latitude": 37.7598,
    "longitude": -122.4148,
    "data_as_of": "2026-02-25T00:33:03.000",
}


# ── C1: normalize_plumbing_inspection ─────────────────────────────


class TestNormalizePlumbingInspection:
    def test_source_is_plumbing(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        # source is the last element (index 16)
        assert row[16] == "plumbing"

    def test_reference_number(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[1] == "PP20250627121"

    def test_reference_number_type(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[2] == "permit"

    def test_inspector_stripped(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[3] == "Edward Kelly"

    def test_scheduled_date(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[4] == "2025-07-08T00:00:00.000"

    def test_result_none_when_missing(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        # result is index 5; plumbing inspections don't have result field
        assert row[5] is None

    def test_inspection_description(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[6] == "SHOWER PAN INSTALLATION"

    def test_block_lot(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[7] == "3534"
        assert row[8] == "068"

    def test_street_name_from_avs(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[10] == "GUERRERO"

    def test_neighborhood(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[12] == "Mission"

    def test_tuple_length(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert len(row) == 17  # 16 original fields + source

    def test_empty_inspector_becomes_none(self):
        from src.ingest import normalize_plumbing_inspection
        record = dict(SAMPLE_PLUMBING_INSP, inspector="  ")
        row = normalize_plumbing_inspection(record, row_id=1)
        assert row[3] is None

    def test_missing_fields_graceful(self):
        from src.ingest import normalize_plumbing_inspection
        row = normalize_plumbing_inspection({"reference_number": "PP-TEST"}, row_id=99)
        assert row[0] == 99
        assert row[1] == "PP-TEST"
        assert row[16] == "plumbing"


# ── C1: inspections table source column ───────────────────────────


class TestInspectionsSourceColumn:
    def test_source_column_exists_in_schema(self):
        conn = db_mod.get_connection()
        try:
            result = conn.execute("SELECT source FROM inspections LIMIT 0").fetchall()
            assert result == []
        finally:
            conn.close()

    def test_building_inspection_default_source(self):
        from src.ingest import _normalize_inspection
        row = _normalize_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
        assert row[16] == "building"

    def test_plumbing_inspection_source_tag(self):
        from src.ingest import _normalize_inspection
        row = _normalize_inspection(SAMPLE_PLUMBING_INSP, row_id=1, source="plumbing")
        assert row[16] == "plumbing"

    def test_insert_with_source_column(self):
        from src.ingest import normalize_plumbing_inspection
        conn = db_mod.get_connection()
        try:
            row = normalize_plumbing_inspection(SAMPLE_PLUMBING_INSP, row_id=1)
            conn.execute(
                "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                row,
            )
            result = conn.execute(
                "SELECT source FROM inspections WHERE reference_number = 'PP20250627121'"
            ).fetchone()
            assert result is not None
            assert result[0] == "plumbing"
        finally:
            conn.close()


# ── C1: ingest_plumbing_inspections round-trip ────────────────────


class TestIngestPlumbingInspections:
    def test_inserts_records_with_plumbing_source(self):
        from src.ingest import ingest_plumbing_inspections
        fake_client = _FakeClient(data_map={
            "fuas-yurr": [SAMPLE_PLUMBING_INSP, SAMPLE_PLUMBING_INSP_NO_RESULT]
        })
        conn = db_mod.get_connection()
        try:
            count = asyncio.run(ingest_plumbing_inspections(conn, fake_client))
            assert count == 2
            rows = conn.execute(
                "SELECT source FROM inspections WHERE source = 'plumbing'"
            ).fetchall()
            assert len(rows) == 2
        finally:
            conn.close()

    def test_does_not_delete_building_inspections(self):
        from src.ingest import ingest_plumbing_inspections, _normalize_inspection
        conn = db_mod.get_connection()
        try:
            # Insert a building inspection first
            building_row = _normalize_inspection(SAMPLE_PLUMBING_INSP, row_id=1, source="building")
            conn.execute(
                "INSERT INTO inspections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                building_row,
            )
            # Now ingest plumbing inspections
            fake_client = _FakeClient(data_map={"fuas-yurr": [SAMPLE_PLUMBING_INSP_NO_RESULT]})
            asyncio.run(ingest_plumbing_inspections(conn, fake_client))
            # Building row should still exist
            building_count = conn.execute(
                "SELECT COUNT(*) FROM inspections WHERE source = 'building'"
            ).fetchone()[0]
            assert building_count == 1
        finally:
            conn.close()

    def test_empty_dataset_returns_zero(self):
        from src.ingest import ingest_plumbing_inspections
        fake_client = _FakeClient(data_map={"fuas-yurr": []})
        conn = db_mod.get_connection()
        try:
            count = asyncio.run(ingest_plumbing_inspections(conn, fake_client))
            assert count == 0
        finally:
            conn.close()

    def test_plumbing_inspections_in_datasets_dict(self):
        from src.ingest import DATASETS
        assert "plumbing_inspections" in DATASETS
        assert DATASETS["plumbing_inspections"]["endpoint_id"] == "fuas-yurr"

    def test_ingest_log_updated(self):
        from src.ingest import ingest_plumbing_inspections
        fake_client = _FakeClient(data_map={"fuas-yurr": [SAMPLE_PLUMBING_INSP]})
        conn = db_mod.get_connection()
        try:
            asyncio.run(ingest_plumbing_inspections(conn, fake_client))
            row = conn.execute(
                "SELECT dataset_id FROM ingest_log WHERE dataset_id = 'fuas-yurr'"
            ).fetchone()
            assert row is not None
        finally:
            conn.close()


# ── C2: Brief street use activity ─────────────────────────────────


def _seed_street_use(conn):
    """Seed street_use_permits table with sample data."""
    conn.execute(
        "INSERT INTO street_use_permits (permit_number, permit_type, permit_purpose, "
        "status, agent, street_name, cross_street_1, approved_date, expiration_date, "
        "neighborhood) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            SAMPLE_STREET_USE["permit_number"],
            SAMPLE_STREET_USE["permit_type"],
            SAMPLE_STREET_USE["permit_purpose"],
            SAMPLE_STREET_USE["status"],
            SAMPLE_STREET_USE["agent"],
            SAMPLE_STREET_USE["street_name"],
            SAMPLE_STREET_USE["cross_street_1"],
            SAMPLE_STREET_USE["approved_date"],
            SAMPLE_STREET_USE["expiration_date"],
            SAMPLE_STREET_USE["neighborhood"],
        ),
    )


class TestGetStreetUseActivity:
    def test_returns_matching_street_use_permits(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [("100", "MARKET")])
            assert len(results) == 1
            assert results[0]["permit_number"] == "SUP-2026-001"
        finally:
            conn.close()

    def test_empty_addresses_returns_empty(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [])
            assert results == []
        finally:
            conn.close()

    def test_no_match_returns_empty(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [("100", "NONEXISTENT")])
            assert results == []
        finally:
            conn.close()

    def test_deduplicates_by_permit_number(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            # Query same street twice
            results = _get_street_use_activity(conn, [("100", "MARKET"), ("200", "MARKET")])
            permit_numbers = [r["permit_number"] for r in results]
            assert len(permit_numbers) == len(set(permit_numbers))
        finally:
            conn.close()

    def test_watched_address_included_in_result(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [("100", "MARKET")])
            assert results[0]["watched_address"] == "100 MARKET"
        finally:
            conn.close()

    def test_case_insensitive_match(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [("100", "market")])
            assert len(results) == 1
        finally:
            conn.close()

    def test_result_fields_present(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
            results = _get_street_use_activity(conn, [("100", "MARKET")])
            r = results[0]
            assert "permit_number" in r
            assert "permit_type" in r
            assert "permit_purpose" in r
            assert "status" in r
            assert "approved_date" in r
            assert "neighborhood" in r
        finally:
            conn.close()

    def test_empty_table_returns_empty(self):
        from web.brief import _get_street_use_activity
        conn = db_mod.get_connection()
        try:
            results = _get_street_use_activity(conn, [("100", "MARKET")])
            assert results == []
        finally:
            conn.close()


# ── C3: Brief nearby development ──────────────────────────────────


def _seed_dev_pipeline(conn):
    """Seed development_pipeline table with sample data."""
    conn.execute(
        "INSERT INTO development_pipeline (record_id, name_address, current_status, "
        "proposed_units, net_pipeline_units, affordable_units, neighborhood, "
        "block_lot, description_planning, approved_date_planning) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            SAMPLE_DEV_PIPELINE["record_id"],
            SAMPLE_DEV_PIPELINE["name_address"],
            SAMPLE_DEV_PIPELINE["current_status"],
            SAMPLE_DEV_PIPELINE["proposed_units"],
            SAMPLE_DEV_PIPELINE["net_pipeline_units"],
            SAMPLE_DEV_PIPELINE["affordable_units"],
            SAMPLE_DEV_PIPELINE["neighborhood"],
            SAMPLE_DEV_PIPELINE["block_lot"],
            SAMPLE_DEV_PIPELINE["description_planning"],
            SAMPLE_DEV_PIPELINE["approved_date_planning"],
        ),
    )


class TestGetNearbyDevelopment:
    def test_returns_dev_pipeline_for_watched_parcel(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            results = _get_nearby_development(conn, [("3534", "001")])
            assert len(results) == 1
            assert results[0]["record_id"] == "DEV-2026-001"
        finally:
            conn.close()

    def test_empty_parcels_returns_empty(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            results = _get_nearby_development(conn, [])
            assert results == []
        finally:
            conn.close()

    def test_no_match_returns_empty(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            results = _get_nearby_development(conn, [("9999", "001")])
            assert results == []
        finally:
            conn.close()

    def test_result_fields_present(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            results = _get_nearby_development(conn, [("3534", "001")])
            r = results[0]
            assert "record_id" in r
            assert "name_address" in r
            assert "current_status" in r
            assert "proposed_units" in r
            assert "affordable_units" in r
            assert "neighborhood" in r
            assert "watched_parcel" in r
        finally:
            conn.close()

    def test_watched_parcel_in_result(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            results = _get_nearby_development(conn, [("3534", "001")])
            assert results[0]["watched_parcel"] == "3534/001"
        finally:
            conn.close()

    def test_block_level_matching(self):
        """Results returned for same block even different lot."""
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            # Watch lot 099, but dev pipeline row is at 3534/001 (same block)
            results = _get_nearby_development(conn, [("3534", "099")])
            assert len(results) == 1
        finally:
            conn.close()

    def test_empty_table_returns_empty(self):
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            results = _get_nearby_development(conn, [("3534", "001")])
            assert results == []
        finally:
            conn.close()

    def test_deduplicates_records(self):
        """Same record should not appear twice if two watched parcels match it."""
        from web.brief import _get_nearby_development
        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
            # Two parcels on same block
            results = _get_nearby_development(conn, [("3534", "001"), ("3534", "002")])
            record_ids = [r["record_id"] for r in results]
            assert len(record_ids) == len(set(record_ids))
        finally:
            conn.close()


# ── C2/C3: get_morning_brief includes new sections ────────────────


class TestMorningBriefInclusion:
    def test_brief_has_street_use_activity_key(self, monkeypatch):
        """get_morning_brief returns street_use_activity key."""
        from web.brief import get_morning_brief

        # Patch the user-specific functions to avoid watch_items dependency
        monkeypatch.setattr("web.brief.get_street_use_activity_for_user", lambda uid: [])
        monkeypatch.setattr("web.brief.get_nearby_development_for_user", lambda uid: [])

        result = get_morning_brief(user_id=1)
        assert "street_use_activity" in result

    def test_brief_has_nearby_development_key(self, monkeypatch):
        """get_morning_brief returns nearby_development key."""
        from web.brief import get_morning_brief

        monkeypatch.setattr("web.brief.get_street_use_activity_for_user", lambda uid: [])
        monkeypatch.setattr("web.brief.get_nearby_development_for_user", lambda uid: [])

        result = get_morning_brief(user_id=1)
        assert "nearby_development" in result

    def test_brief_summary_counts_present(self, monkeypatch):
        """Summary dict includes street_use_count and nearby_development_count."""
        from web.brief import get_morning_brief

        monkeypatch.setattr(
            "web.brief.get_street_use_activity_for_user",
            lambda uid: [{"permit_number": "X"}],
        )
        monkeypatch.setattr(
            "web.brief.get_nearby_development_for_user",
            lambda uid: [{"record_id": "Y"}, {"record_id": "Z"}],
        )

        result = get_morning_brief(user_id=1)
        assert result["summary"]["street_use_count"] == 1
        assert result["summary"]["nearby_development_count"] == 2


# ── C4: Nightly street-use change detection ───────────────────────


class TestDetectStreetUseChanges:
    def test_inserts_new_permit_change(self):
        from scripts.nightly_changes import detect_street_use_changes
        init_user_schema()

        records = [SAMPLE_STREET_USE]
        count = detect_street_use_changes(records, dry_run=False, source="nightly")
        assert count == 1

        rows = db_mod.query(
            "SELECT change_type FROM permit_changes WHERE permit_number = 'SUP-2026-001'"
        )
        assert len(rows) == 1
        assert rows[0][0] == "street_use_change"

    def test_skips_unchanged_record(self):
        from scripts.nightly_changes import detect_street_use_changes
        init_user_schema()

        # Seed the street_use_permits table so the status matches
        conn = db_mod.get_connection()
        try:
            _seed_street_use(conn)
        finally:
            conn.close()

        count = detect_street_use_changes([SAMPLE_STREET_USE], dry_run=False)
        assert count == 0

    def test_dry_run_does_not_insert(self):
        from scripts.nightly_changes import detect_street_use_changes
        init_user_schema()

        count = detect_street_use_changes([SAMPLE_STREET_USE], dry_run=True)
        assert count == 1  # Reports 1 detected

        rows = db_mod.query("SELECT COUNT(*) FROM permit_changes")
        assert rows[0][0] == 0  # Nothing actually inserted

    def test_empty_records_returns_zero(self):
        from scripts.nightly_changes import detect_street_use_changes
        init_user_schema()
        count = detect_street_use_changes([], dry_run=False)
        assert count == 0

    def test_missing_permit_number_skipped(self):
        from scripts.nightly_changes import detect_street_use_changes
        init_user_schema()
        record = dict(SAMPLE_STREET_USE)
        del record["permit_number"]
        count = detect_street_use_changes([record])
        assert count == 0


# ── C4: Nightly dev pipeline change detection ─────────────────────


class TestDetectDevPipelineChanges:
    def test_inserts_new_pipeline_change(self):
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()

        records = [SAMPLE_DEV_PIPELINE]
        count = detect_development_pipeline_changes(records, dry_run=False, source="nightly")
        assert count == 1

        rows = db_mod.query(
            "SELECT change_type FROM permit_changes WHERE permit_number = 'DEV-2026-001'"
        )
        assert len(rows) == 1
        assert rows[0][0] == "dev_pipeline_change"

    def test_skips_unchanged_record(self):
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()

        conn = db_mod.get_connection()
        try:
            _seed_dev_pipeline(conn)
        finally:
            conn.close()

        count = detect_development_pipeline_changes([SAMPLE_DEV_PIPELINE], dry_run=False)
        assert count == 0

    def test_dry_run_does_not_insert(self):
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()

        count = detect_development_pipeline_changes([SAMPLE_DEV_PIPELINE], dry_run=True)
        assert count == 1

        rows = db_mod.query("SELECT COUNT(*) FROM permit_changes")
        assert rows[0][0] == 0

    def test_empty_records_returns_zero(self):
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()
        count = detect_development_pipeline_changes([])
        assert count == 0

    def test_missing_record_id_skipped(self):
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()
        record = dict(SAMPLE_DEV_PIPELINE)
        del record["record_id"]
        count = detect_development_pipeline_changes([record])
        assert count == 0

    def test_block_lot_parsed_from_block_lot_field(self):
        """block/lot should be extracted from the block_lot string."""
        from scripts.nightly_changes import detect_development_pipeline_changes
        init_user_schema()
        records = [SAMPLE_DEV_PIPELINE]
        detect_development_pipeline_changes(records, dry_run=False)

        rows = db_mod.query(
            "SELECT block, lot FROM permit_changes WHERE permit_number = 'DEV-2026-001'"
        )
        assert rows[0][0] == "3534"
        assert rows[0][1] == "001"


# ── Cron endpoint auth ────────────────────────────────────────────


class TestCronIngestPlumbingInspectionsEndpoint:
    def test_no_auth_returns_403(self, client):
        resp = client.post("/cron/ingest-plumbing-inspections")
        assert resp.status_code == 403

    def test_wrong_token_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "correct-secret")

        resp = client.post(
            "/cron/ingest-plumbing-inspections",
            headers={"Authorization": "Bearer wrong-secret"},
        )
        assert resp.status_code == 403

    def test_endpoint_is_registered(self, client):
        from web.app import app
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert "/cron/ingest-plumbing-inspections" in rules
