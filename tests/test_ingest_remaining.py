"""Tests for Sprint 55A — cron endpoints for electrical/plumbing + 5 new dataset schemas/ingest.

Covers:
- DATASETS dict entries: endpoint IDs, names for all 5 new datasets
- Normalizer functions: field mapping, NULL handling, numeric parsing
- Ingest functions: DB round-trip with in-memory DuckDB (no network access)
- Cron endpoint auth: 403 without token, 403 with wrong token
- Schema test: all 5 new tables created by init_schema
- Electrical/plumbing cron endpoints: auth checks
"""

import re
import inspect
import pytest

import src.db as db_mod


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_ingest_remaining.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
    finally:
        conn.close()


@pytest.fixture
def client(monkeypatch):
    """Flask test client."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()

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
        return records[offset:offset + limit] if limit is not None else records[offset:]

    async def close(self):
        pass


# ── DATASETS dict ──────────────────────────────────────────────────


class TestDatasetsDict:
    def test_street_use_permits_present(self):
        from src.ingest import DATASETS
        assert "street_use_permits" in DATASETS

    def test_development_pipeline_present(self):
        from src.ingest import DATASETS
        assert "development_pipeline" in DATASETS

    def test_affordable_housing_present(self):
        from src.ingest import DATASETS
        assert "affordable_housing" in DATASETS

    def test_housing_production_present(self):
        from src.ingest import DATASETS
        assert "housing_production" in DATASETS

    def test_dwelling_completions_present(self):
        from src.ingest import DATASETS
        assert "dwelling_completions" in DATASETS

    def test_street_use_endpoint_id(self):
        from src.ingest import DATASETS
        assert DATASETS["street_use_permits"]["endpoint_id"] == "b6tj-gt35"

    def test_development_pipeline_endpoint_id(self):
        from src.ingest import DATASETS
        assert DATASETS["development_pipeline"]["endpoint_id"] == "6jgi-cpb4"

    def test_affordable_housing_endpoint_id(self):
        from src.ingest import DATASETS
        assert DATASETS["affordable_housing"]["endpoint_id"] == "aaxw-2cb8"

    def test_housing_production_endpoint_id(self):
        from src.ingest import DATASETS
        assert DATASETS["housing_production"]["endpoint_id"] == "xdht-4php"

    def test_dwelling_completions_endpoint_id(self):
        from src.ingest import DATASETS
        assert DATASETS["dwelling_completions"]["endpoint_id"] == "j67f-aayr"

    @pytest.mark.parametrize("key", [
        "street_use_permits", "development_pipeline", "affordable_housing",
        "housing_production", "dwelling_completions",
    ])
    def test_endpoint_id_format(self, key):
        """Endpoint IDs must match Socrata 4x4 format: xxxx-xxxx."""
        from src.ingest import DATASETS
        eid = DATASETS[key]["endpoint_id"]
        assert re.match(r"^[a-z0-9]{4}-[a-z0-9]{4}$", eid), f"Bad endpoint_id for {key}: {eid}"

    @pytest.mark.parametrize("key", [
        "street_use_permits", "development_pipeline", "affordable_housing",
        "housing_production", "dwelling_completions",
    ])
    def test_has_name(self, key):
        from src.ingest import DATASETS
        assert DATASETS[key].get("name"), f"{key} must have a name"


# ── _normalize_street_use_permit ───────────────────────────────────


class TestNormalizeStreetUsePermit:
    def test_basic_fields(self):
        from src.ingest import _normalize_street_use_permit
        record = {
            "unique_identifier": "14B-0016_23775000",
            "permit_number": "14B-0016",
            "permit_type": "Banners",
            "permit_purpose": "Awareness- CITY FUNDED",
            "status": "CLOSED",
            "agent": "AAA FLAG & BANNER",
            "agentphone": "(415) 431-2950",
            "contact": "Heather Cann: (415) 431-2950",
            "streetname": "16TH ST",
            "cross_street_1": "KANSAS ST",
            "cross_street_2": None,
            "planchecker": "Rahul Shah",
            "approved_date": "2014-02-26T13:14:27.000",
            "expiration_date": None,
            "analysis_neighborhood": "Mission Bay",
            "supervisor_district": "6",
            "latitude": "37.766017054635824",
            "longitude": "-122.40364305541603",
            "cnn": "23775000",
            "data_as_of": "2025-12-12T03:52:31.000",
        }
        result = _normalize_street_use_permit(record)
        assert len(result) == 19
        assert result[0] == "14B-0016_23775000"     # permit_number (unique_identifier)
        assert result[1] == "Banners"               # permit_type
        assert result[2] == "Awareness- CITY FUNDED"  # permit_purpose
        assert result[3] == "CLOSED"                # status
        assert result[4] == "AAA FLAG & BANNER"     # agent
        assert result[5] == "(415) 431-2950"        # agent_phone
        assert result[6] == "Heather Cann: (415) 431-2950"  # contact
        assert result[7] == "16TH ST"               # street_name
        assert result[8] == "KANSAS ST"             # cross_street_1
        assert result[9] is None                    # cross_street_2
        assert result[10] == "Rahul Shah"           # plan_checker
        assert result[11] == "2014-02-26T13:14:27.000"  # approved_date
        assert result[12] is None                   # expiration_date
        assert result[13] == "Mission Bay"          # neighborhood
        assert result[14] == "6"                    # supervisor_district
        assert abs(result[15] - 37.766017) < 0.001  # latitude
        assert abs(result[16] - (-122.403643)) < 0.001  # longitude
        assert result[17] == "23775000"             # cnn
        assert result[18] == "2025-12-12T03:52:31.000"  # data_as_of

    def test_uses_unique_identifier_as_pk(self):
        from src.ingest import _normalize_street_use_permit
        record = {
            "unique_identifier": "14B-0016_23775000",
            "permit_number": "14B-0016",
        }
        result = _normalize_street_use_permit(record)
        assert result[0] == "14B-0016_23775000"

    def test_falls_back_to_permit_number_when_no_unique_identifier(self):
        from src.ingest import _normalize_street_use_permit
        record = {"permit_number": "14B-0016"}
        result = _normalize_street_use_permit(record)
        assert result[0] == "14B-0016"

    def test_empty_record(self):
        from src.ingest import _normalize_street_use_permit
        result = _normalize_street_use_permit({})
        assert len(result) == 19
        assert result[0] == ""  # empty fallback

    def test_invalid_lat_lon(self):
        from src.ingest import _normalize_street_use_permit
        record = {"unique_identifier": "X", "latitude": "bad", "longitude": None}
        result = _normalize_street_use_permit(record)
        assert result[15] is None
        assert result[16] is None


# ── _normalize_development_pipeline ───────────────────────────────


class TestNormalizeDevelopmentPipeline:
    def test_basic_fields(self):
        from src.ingest import _normalize_development_pipeline
        record = {
            "bpa_no": "201912311059",
            "case_no": "2020-001009PRJ",
            "nameaddr": "740 Francisco Street",
            "current_status": "BP Issued",
            "description_dbi": "REMODEL & ADDITION",
            "description_planning": "Add second unit",
            "contact": "Michael Morrison",
            "sponsor": "John Lum Architecture",
            "planner": "JVIMR",
            "proposed_units": "2",
            "existing_units": "1",
            "net_pipeline_units": "1",
            "pipeline_affordable_units": "0",
            "zoning_district": "RH-2",
            "height_district": "40-X",
            "nhood37": "Russian Hill",
            "planning_district": "3 - Northeast",
            "approved_date_planning": "2022-10-18T00:00:00.000",
            "blklot": "0044002A",
            "latitude": "37.8044254518062",
            "longitude": "-122.417402560593",
        }
        result = _normalize_development_pipeline(record)
        assert len(result) == 23
        assert result[0] == "201912311059"          # record_id (bpa_no)
        assert result[1] == "201912311059"          # bpa_no
        assert result[2] == "2020-001009PRJ"        # case_no
        assert result[3] == "740 Francisco Street"  # name_address
        assert result[4] == "BP Issued"             # current_status
        assert result[10] == 2                      # proposed_units
        assert result[11] == 1                      # existing_units
        assert result[12] == 1                      # net_pipeline_units
        assert result[13] == 0                      # affordable_units
        assert result[16] == "Russian Hill"         # neighborhood
        assert result[19] == "0044002A"             # block_lot

    def test_missing_bpa_falls_back_to_case_no(self):
        from src.ingest import _normalize_development_pipeline
        record = {"case_no": "2020-001009PRJ"}
        result = _normalize_development_pipeline(record)
        assert result[0] == "2020-001009PRJ"

    def test_invalid_units(self):
        from src.ingest import _normalize_development_pipeline
        record = {"bpa_no": "X", "proposed_units": "N/A", "existing_units": ""}
        result = _normalize_development_pipeline(record)
        assert result[10] is None
        assert result[11] is None

    def test_empty_record(self):
        from src.ingest import _normalize_development_pipeline
        result = _normalize_development_pipeline({})
        assert len(result) == 23


# ── _normalize_affordable_housing ─────────────────────────────────


class TestNormalizeAffordableHousing:
    def test_basic_fields(self):
        from src.ingest import _normalize_affordable_housing
        record = {
            "project_id": "2016-054",
            "project_name": "469 Eddy",
            "project_lead_sponsor": "469 Eddy Street, LLC",
            "planning_case_number": "2014.0562",
            "plannning_approval_address": "469 Eddy St",
            "total_project_units": "28",
            "mohcd_affordable_units": "3",
            "affordable_percent": "11",
            "construction_status": "(4) Site Work Permit Issued",
            "housing_tenure": "Ownership",
            "general_housing_program": "Inclusionary Housing",
            "supervisor_district": "5",
            "city_analysis_neighborhood": "Tenderloin",
            "latitude": "37.78330387",
            "longitude": "-122.4152724",
        }
        result = _normalize_affordable_housing(record)
        assert len(result) == 16
        assert result[0] == "2016-054"              # project_id
        assert result[1] == "469 Eddy"              # project_name
        assert result[2] == "469 Eddy Street, LLC"  # project_lead_sponsor
        assert result[3] == "2014.0562"             # planning_case_number
        assert result[4] == "469 Eddy St"           # address
        assert result[5] == 28                      # total_project_units
        assert result[6] == 3                       # affordable_units
        assert result[7] == 11.0                    # affordable_percent
        assert result[8] == "(4) Site Work Permit Issued"  # construction_status
        assert result[9] == "Ownership"             # housing_tenure
        assert result[12] == "Tenderloin"           # neighborhood
        assert abs(result[13] - 37.7833) < 0.001   # latitude

    def test_missing_project_id_returns_empty_string(self):
        from src.ingest import _normalize_affordable_housing
        result = _normalize_affordable_housing({})
        assert result[0] == ""

    def test_invalid_numeric(self):
        from src.ingest import _normalize_affordable_housing
        record = {"project_id": "X", "total_project_units": "N/A", "affordable_percent": ""}
        result = _normalize_affordable_housing(record)
        assert result[5] is None
        assert result[7] is None

    def test_empty_record(self):
        from src.ingest import _normalize_affordable_housing
        result = _normalize_affordable_housing({})
        assert len(result) == 16


# ── _normalize_housing_production ─────────────────────────────────


class TestNormalizeHousingProduction:
    def test_basic_fields(self):
        from src.ingest import _normalize_housing_production
        record = {
            "bpa": "200209196918",
            "address": "149 PANAMA ST",
            "blocklot": "7178012",
            "description": "ERECT A THREE STORY SINGLE FAMILY DWELLING",
            "permit_type": "Site Permit",
            "issued_date": "2004-05-05T00:00:00.000",
            "first_completion_date": "2005-04-04T00:00:00.000",
            "latest_completion_date": "2005-04-04T00:00:00.000",
            "proposed_units": "1",
            "net_units": "1",
            "net_units_completed": "1",
            "market_rate": "1",
            "affordable_units": "0",
            "zoning_district": "RH-1",
            "analysis_neighborhood": "Oceanview/Merced/Ingleside",
            "supervisor_district": "7",
        }
        result = _normalize_housing_production(record, 42)
        assert len(result) == 18
        assert result[0] == 42                      # id
        assert result[1] == "200209196918"          # bpa
        assert result[2] == "149 PANAMA ST"         # address
        assert result[3] == "7178012"               # block_lot
        assert result[4] == "ERECT A THREE STORY SINGLE FAMILY DWELLING"
        assert result[5] == "Site Permit"           # permit_type
        assert result[9] == 1                       # proposed_units
        assert result[10] == 1                      # net_units
        assert result[11] == 1                      # net_units_completed
        assert result[12] == 1                      # market_rate
        assert result[13] == 0                      # affordable_units
        assert result[15] == "Oceanview/Merced/Ingleside"  # neighborhood

    def test_uses_pts_proposed_units_fallback(self):
        from src.ingest import _normalize_housing_production
        record = {"bpa": "X", "pts_proposed_units": "3"}
        result = _normalize_housing_production(record, 1)
        assert result[9] == 3  # proposed_units via fallback

    def test_invalid_numeric(self):
        from src.ingest import _normalize_housing_production
        record = {"bpa": "X", "proposed_units": "N/A", "net_units": ""}
        result = _normalize_housing_production(record, 1)
        assert result[9] is None
        assert result[10] is None

    def test_empty_record(self):
        from src.ingest import _normalize_housing_production
        result = _normalize_housing_production({}, 1)
        assert len(result) == 18
        assert result[0] == 1  # id


# ── _normalize_dwelling_completion ────────────────────────────────


class TestNormalizeDwellingCompletion:
    def test_basic_fields(self):
        from src.ingest import _normalize_dwelling_completion
        record = {
            "building_permit_application": "201404304554",
            "building_address": "41 Tehama Street",
            "date_issued": "2018-01-11T00:00:00.000",
            "document_type": "Amended TCO",
            "number_of_units_certified": "68",
        }
        result = _normalize_dwelling_completion(record, 7)
        assert len(result) == 7
        assert result[0] == 7                          # id
        assert result[1] == "41 Tehama Street"         # building_address
        assert result[2] == "201404304554"             # building_permit_application
        assert result[3] == "2018-01-11T00:00:00.000" # date_issued
        assert result[4] == "Amended TCO"              # document_type
        assert result[5] == 68                         # number_of_units_certified
        assert result[6] is None                       # data_as_of

    def test_invalid_units_certified(self):
        from src.ingest import _normalize_dwelling_completion
        record = {"building_permit_application": "X", "number_of_units_certified": "N/A"}
        result = _normalize_dwelling_completion(record, 1)
        assert result[5] is None

    def test_empty_record(self):
        from src.ingest import _normalize_dwelling_completion
        result = _normalize_dwelling_completion({}, 1)
        assert len(result) == 7
        assert result[0] == 1  # id


# ── Ingest function DB round-trip tests ───────────────────────────


@pytest.mark.asyncio
async def test_ingest_development_pipeline_round_trip():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    from src.ingest import ingest_development_pipeline
    client = _FakeClient([
        {
            "bpa_no": "201912311059",
            "case_no": "2020-001009PRJ",
            "nameaddr": "740 Francisco Street",
            "current_status": "BP Issued",
            "proposed_units": "2",
            "existing_units": "1",
            "net_pipeline_units": "1",
            "pipeline_affordable_units": "0",
            "nhood37": "Russian Hill",
        },
        {
            "bpa_no": "202001011234",
            "case_no": "2019-000001PRJ",
            "nameaddr": "500 Main St",
            "current_status": "Building Permit Filed",
            "proposed_units": "5",
        },
    ])
    count = await ingest_development_pipeline(conn, client)
    assert count == 2
    rows = conn.execute(
        "SELECT record_id, current_status FROM development_pipeline ORDER BY record_id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][1] == "BP Issued"
    conn.close()


@pytest.mark.asyncio
async def test_ingest_affordable_housing_round_trip():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    from src.ingest import ingest_affordable_housing
    client = _FakeClient([
        {
            "project_id": "2016-054",
            "project_name": "469 Eddy",
            "total_project_units": "28",
            "mohcd_affordable_units": "3",
            "affordable_percent": "11",
            "city_analysis_neighborhood": "Tenderloin",
        },
    ])
    count = await ingest_affordable_housing(conn, client)
    assert count == 1
    row = conn.execute(
        "SELECT project_id, affordable_units, neighborhood FROM affordable_housing"
    ).fetchone()
    assert row[0] == "2016-054"
    assert row[1] == 3
    assert row[2] == "Tenderloin"
    conn.close()


@pytest.mark.asyncio
async def test_ingest_housing_production_round_trip():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    from src.ingest import ingest_housing_production
    client = _FakeClient([
        {
            "bpa": "200209196918",
            "address": "149 PANAMA ST",
            "blocklot": "7178012",
            "proposed_units": "1",
            "net_units": "1",
            "net_units_completed": "1",
            "market_rate": "1",
            "affordable_units": "0",
            "analysis_neighborhood": "Oceanview/Merced/Ingleside",
        },
        {
            "bpa": "202001011111",
            "address": "200 OAK ST",
            "blocklot": "1234567",
            "proposed_units": "10",
        },
    ])
    count = await ingest_housing_production(conn, client)
    assert count == 2
    rows = conn.execute("SELECT bpa FROM housing_production ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["200209196918", "202001011111"]
    conn.close()


@pytest.mark.asyncio
async def test_ingest_dwelling_completions_round_trip():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    from src.ingest import ingest_dwelling_completions
    client = _FakeClient([
        {
            "building_permit_application": "201404304554",
            "building_address": "41 Tehama Street",
            "date_issued": "2018-01-11T00:00:00.000",
            "document_type": "Amended TCO",
            "number_of_units_certified": "68",
        },
        {
            "building_permit_application": "201501011234",
            "building_address": "100 Main St",
            "document_type": "Final TCO",
            "number_of_units_certified": "10",
        },
    ])
    count = await ingest_dwelling_completions(conn, client)
    assert count == 2
    rows = conn.execute(
        "SELECT building_permit_application, number_of_units_certified FROM dwelling_completions ORDER BY id"
    ).fetchall()
    assert rows[0] == ("201404304554", 68)
    assert rows[1] == ("201501011234", 10)
    conn.close()


@pytest.mark.asyncio
async def test_ingest_street_use_permits_round_trip():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    from src.ingest import ingest_street_use_permits
    client = _FakeClient([
        {
            "unique_identifier": "14B-0016_23775000",
            "permit_number": "14B-0016",
            "permit_type": "Banners",
            "status": "CLOSED",
            "streetname": "16TH ST",
            "analysis_neighborhood": "Mission Bay",
            "supervisor_district": "6",
        },
        {
            "unique_identifier": "15C-0100_23775001",
            "permit_number": "15C-0100",
            "permit_type": "Excavation",
            "status": "OPEN",
            "streetname": "MARKET ST",
        },
    ])
    count = await ingest_street_use_permits(conn, client)
    assert count == 2
    rows = conn.execute(
        "SELECT permit_number, status FROM street_use_permits ORDER BY permit_number"
    ).fetchall()
    assert rows[0] == ("14B-0016_23775000", "CLOSED")
    assert rows[1] == ("15C-0100_23775001", "OPEN")
    conn.close()


@pytest.mark.asyncio
async def test_ingest_log_written_for_all_new_datasets():
    """Each ingest function writes to ingest_log."""
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)

    from src.ingest import (
        ingest_development_pipeline,
        ingest_affordable_housing,
        ingest_housing_production,
        ingest_dwelling_completions,
    )

    empty_client = _FakeClient([])

    await ingest_development_pipeline(conn, empty_client)
    await ingest_affordable_housing(conn, empty_client)
    await ingest_housing_production(conn, empty_client)
    await ingest_dwelling_completions(conn, empty_client)

    rows = conn.execute(
        "SELECT dataset_id FROM ingest_log ORDER BY dataset_id"
    ).fetchall()
    dataset_ids = {r[0] for r in rows}
    assert "6jgi-cpb4" in dataset_ids  # development pipeline
    assert "aaxw-2cb8" in dataset_ids  # affordable housing
    assert "xdht-4php" in dataset_ids  # housing production
    assert "j67f-aayr" in dataset_ids  # dwelling completions
    conn.close()


# ── Schema tests ──────────────────────────────────────────────────


class TestSchema:
    def test_all_5_new_tables_created(self):
        """init_schema creates all 5 new tables."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "street_use_permits" in table_names
        assert "development_pipeline" in table_names
        assert "affordable_housing" in table_names
        assert "housing_production" in table_names
        assert "dwelling_completions" in table_names
        conn.close()

    def test_street_use_permits_schema(self):
        """street_use_permits table has correct column count."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'street_use_permits' ORDER BY ordinal_position"
        ).fetchall()
        assert len(cols) == 19
        col_names = [c[0] for c in cols]
        assert "permit_number" in col_names
        assert "neighborhood" in col_names
        assert "cnn" in col_names
        conn.close()

    def test_development_pipeline_schema(self):
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'development_pipeline' ORDER BY ordinal_position"
        ).fetchall()
        assert len(cols) == 23
        col_names = [c[0] for c in cols]
        assert "record_id" in col_names
        assert "bpa_no" in col_names
        assert "affordable_units" in col_names
        conn.close()

    def test_affordable_housing_schema(self):
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'affordable_housing' ORDER BY ordinal_position"
        ).fetchall()
        assert len(cols) == 16
        col_names = [c[0] for c in cols]
        assert "project_id" in col_names
        assert "affordable_percent" in col_names
        conn.close()

    def test_housing_production_schema(self):
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'housing_production' ORDER BY ordinal_position"
        ).fetchall()
        assert len(cols) == 18
        col_names = [c[0] for c in cols]
        assert "id" in col_names
        assert "bpa" in col_names
        assert "net_units_completed" in col_names
        conn.close()

    def test_dwelling_completions_schema(self):
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'dwelling_completions' ORDER BY ordinal_position"
        ).fetchall()
        assert len(cols) == 7
        col_names = [c[0] for c in cols]
        assert "id" in col_names
        assert "building_permit_application" in col_names
        assert "number_of_units_certified" in col_names
        conn.close()


# ── Cron endpoint auth tests ──────────────────────────────────────


NEW_CRON_ENDPOINTS = [
    "/cron/ingest-electrical",
    "/cron/ingest-plumbing",
    "/cron/ingest-street-use",
    "/cron/ingest-development-pipeline",
    "/cron/ingest-affordable-housing",
    "/cron/ingest-housing-production",
    "/cron/ingest-dwelling-completions",
]


class TestCronAuth:
    """All new ingest cron endpoints blocked on web workers by cron guard."""

    @pytest.mark.parametrize("endpoint", NEW_CRON_ENDPOINTS)
    def test_no_auth_blocked_on_web_worker(self, client, endpoint):
        rv = client.post(endpoint)
        assert rv.status_code == 404, f"{endpoint} should return 404 (cron guard blocks POST on web workers)"

    @pytest.mark.parametrize("endpoint", NEW_CRON_ENDPOINTS)
    def test_wrong_token_returns_403_on_cron_worker(self, client, endpoint, monkeypatch):
        monkeypatch.setenv("CRON_WORKER", "true")
        monkeypatch.setenv("CRON_SECRET", "correct-secret")
        rv = client.post(endpoint, headers={"Authorization": "Bearer wrong-secret"})
        assert rv.status_code == 403, f"{endpoint} should return 403 with wrong token on cron worker"


# ── run_ingestion signature tests ─────────────────────────────────


class TestRunIngestionSignature:
    def test_accepts_street_use_kwarg(self):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert "street_use" in sig.parameters

    def test_accepts_development_pipeline_kwarg(self):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert "development_pipeline" in sig.parameters

    def test_accepts_affordable_housing_kwarg(self):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert "affordable_housing" in sig.parameters

    def test_accepts_housing_production_kwarg(self):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert "housing_production" in sig.parameters

    def test_accepts_dwelling_completions_kwarg(self):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert "dwelling_completions" in sig.parameters

    @pytest.mark.parametrize("param", [
        "street_use", "development_pipeline", "affordable_housing",
        "housing_production", "dwelling_completions",
    ])
    def test_new_params_default_to_true(self, param):
        from src.ingest import run_ingestion
        sig = inspect.signature(run_ingestion)
        assert sig.parameters[param].default is True, f"{param} should default to True"


# ── Normalizer tuple length guards ───────────────────────────────


@pytest.mark.parametrize("fn_name,args,expected_len", [
    ("_normalize_street_use_permit", ({},), 19),
    ("_normalize_development_pipeline", ({},), 23),
    ("_normalize_affordable_housing", ({},), 16),
    ("_normalize_housing_production", ({}, 1), 18),
    ("_normalize_dwelling_completion", ({}, 1), 7),
])
def test_normalizer_tuple_length(fn_name, args, expected_len):
    """Each normalizer must produce the exact column count for its table."""
    import src.ingest as ingest_module
    fn = getattr(ingest_module, fn_name)
    result = fn(*args)
    assert len(result) == expected_len, (
        f"{fn_name}() returned {len(result)} columns — expected {expected_len}"
    )
