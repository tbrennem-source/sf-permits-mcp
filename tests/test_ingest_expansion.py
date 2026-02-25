"""Tests for Sprint 54C data ingest expansion — boiler, fire, planning, tax rolls."""

import pytest

import src.db as db_mod
from src.ingest import (
    _normalize_boiler_permit,
    _normalize_fire_permit,
    _normalize_planning_project,
    _normalize_planning_non_project,
    _normalize_tax_roll,
    ingest_boiler_permits,
    ingest_fire_permits,
    ingest_planning_records,
    ingest_tax_rolls,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_ingest.duckdb")
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


# ── Normalize function tests ─────────────────────────────────────


class TestNormalizeBoiler:
    def test_basic_fields(self):
        record = {
            "permit_number": "BP-001",
            "block": "1234",
            "lot": "005",
            "status": "issued",
            "boiler_type": "low_pressure",
            "boiler_serial_number": "SN123",
            "model": "ModelX",
            "description": "Boiler install",
            "application_date": "2024-01-15",
            "expiration_date": "2025-01-15",
            "street_number": "100",
            "street_name": "MAIN",
            "street_suffix": "ST",
            "zip_code": "94105",
            "neighborhood": "SoMa",
            "supervisor_district": "6",
            "data_as_of": "2025-01-01",
        }
        result = _normalize_boiler_permit(record)
        assert result[0] == "BP-001"
        assert result[1] == "1234"
        assert result[2] == "005"
        assert result[3] == "issued"
        assert result[4] == "low_pressure"
        assert len(result) == 17

    def test_missing_fields(self):
        result = _normalize_boiler_permit({})
        assert result[0] == ""
        assert result[1] is None
        assert len(result) == 17


class TestNormalizeFire:
    def test_basic_fields(self):
        record = {
            "permit_number": "FP-001",
            "permit_type": "1",
            "permit_type_description": "Places of Assembly",
            "permit_status": "active",
            "permit_address": "123 MAIN ST",
            "permit_holder": "ACME Corp",
            "dba_name": "Acme",
            "application_date": "2024-06-01",
            "date_approved": "2024-06-15",
            "expiration_date": "2025-06-15",
            "permit_fee": "500.00",
            "posting_fee": "50.00",
            "referral_fee": "25.00",
            "conditions": "None",
            "battalion": "B01",
            "fire_prevention_district": "1",
            "night_assembly_permit": "N",
            "data_as_of": "2025-01-01",
        }
        result = _normalize_fire_permit(record)
        assert result[0] == "FP-001"
        assert result[10] == 500.0  # permit_fee
        assert result[11] == 50.0   # posting_fee
        assert result[12] == 25.0   # referral_fee
        assert len(result) == 18

    def test_invalid_fee(self):
        record = {"permit_number": "FP-002", "permit_fee": "N/A"}
        result = _normalize_fire_permit(record)
        assert result[10] is None  # invalid fee → None


class TestNormalizePlanning:
    def test_project(self):
        record = {
            "record_id": "PR-001",
            "record_type": "CUA",
            "record_status": "approved",
            "block": "3512",
            "lot": "001",
            "address": "123 MAIN ST",
            "project_name": "Big Project",
            "description": "New building",
            "applicant": "Jane Doe",
            "applicant_org": "Doe Corp",
            "assigned_planner": "John Smith",
            "open_date": "2024-01-01",
            "environmental_doc_type": "Cat Ex",
            "units_existing": "0",
            "units_proposed": "10",
            "units_net": "10.0",
            "affordable_units": "2",
            "child_id": "CH-001",
            "data_as_of": "2025-01-01",
        }
        result = _normalize_planning_project(record)
        assert result[0] == "PR-001"
        assert result[13] is True   # is_project
        assert result[14] == 0      # units_existing
        assert result[15] == 10     # units_proposed
        assert result[16] == 10.0   # units_net
        assert result[17] == 2      # affordable_units
        assert result[19] is None   # parent_id (projects don't have)
        assert len(result) == 21

    def test_non_project(self):
        record = {
            "record_id": "NP-001",
            "record_type": "Letter",
            "record_status": "closed",
            "block": "3512",
            "lot": "001",
            "address": "123 MAIN ST",
            "description": "Zoning letter",
            "applicant": "Jane Doe",
            "assigned_planner": "John Smith",
            "open_date": "2024-03-01",
            "parent_id": "PR-001",
            "data_as_of": "2025-01-01",
        }
        result = _normalize_planning_non_project(record)
        assert result[0] == "NP-001"
        assert result[13] is False  # is_project
        assert result[6] is None    # project_name
        assert result[19] == "PR-001"  # parent_id
        assert len(result) == 21


class TestNormalizeTaxRoll:
    def test_basic_fields(self):
        record = {
            "block": "3512",
            "lot": "001",
            "closed_roll_year": "2024",
            "property_location": "123 MAIN ST",
            "parcel_number": "3512001",
            "zoning_code": "RC-4",
            "use_code": "01",
            "use_definition": "Residential",
            "property_class_code": "R",
            "property_class_code_definition": "Residential",
            "number_of_stories": "3",
            "number_of_units": "6",
            "number_of_rooms": "18",
            "number_of_bedrooms": "12",
            "number_of_bathrooms": "6.5",
            "lot_area": "2500.0",
            "property_area": "5000.0",
            "assessed_land_value": "1000000",
            "assessed_improvement_value": "500000",
            "assessed_personal_property": "0",
            "assessed_fixtures": "0",
            "current_sales_date": "2020-05-15",
            "neighborhood": "Noe Valley",
            "supervisor_district": "8",
            "data_as_of": "2025-01-01",
        }
        result = _normalize_tax_roll(record)
        assert result[0] == "3512"
        assert result[1] == "001"
        assert result[2] == "2024"  # tax_year from closed_roll_year
        assert result[5] == "RC-4"  # zoning_code
        assert result[10] == 3.0    # number_of_stories
        assert result[11] == 6      # number_of_units (int)
        assert result[14] == 6.5    # number_of_bathrooms (float)
        assert result[17] == 1000000.0  # assessed_land_value
        assert len(result) == 25

    def test_invalid_numeric(self):
        record = {"block": "1", "lot": "2", "closed_roll_year": "2024",
                  "number_of_stories": "N/A", "assessed_land_value": ""}
        result = _normalize_tax_roll(record)
        assert result[10] is None  # invalid stories → None
        assert result[17] is None  # empty value → None


# ── Ingest function tests ────────────────────────────────────────


class _FakeClient:
    """Fake SODA client that returns canned data."""

    def __init__(self, data: list[dict] | None = None, data_map: dict | None = None):
        self._data = data or []
        self._data_map = data_map or {}

    async def count(self, endpoint_id, where=None):
        if self._data_map:
            return len(self._data_map.get(endpoint_id, []))
        return len(self._data)

    async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
        records = self._data_map.get(endpoint_id, self._data) if self._data_map else self._data
        return records[offset:offset + limit] if offset is not None else records

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_ingest_boiler():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([
        {"permit_number": "BP-1", "block": "1000", "lot": "001", "status": "issued"},
        {"permit_number": "BP-2", "block": "2000", "lot": "002", "status": "expired"},
    ])
    count = await ingest_boiler_permits(conn, client)
    assert count == 2
    rows = conn.execute("SELECT permit_number FROM boiler_permits ORDER BY permit_number").fetchall()
    assert [r[0] for r in rows] == ["BP-1", "BP-2"]
    conn.close()


@pytest.mark.asyncio
async def test_ingest_fire():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([
        {"permit_number": "FP-1", "permit_status": "active", "permit_fee": "100"},
    ])
    count = await ingest_fire_permits(conn, client)
    assert count == 1
    row = conn.execute("SELECT permit_fee FROM fire_permits").fetchone()
    assert row[0] == 100.0
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient(data_map={
        "qvu5-m3a2": [
            {"record_id": "PR-1", "record_type": "CUA", "record_status": "filed",
             "block": "1000", "lot": "001"},
        ],
        "y673-d69b": [
            {"record_id": "NP-1", "record_type": "Letter", "record_status": "closed",
             "block": "2000", "lot": "002", "parent_id": "PR-1"},
        ],
    })
    count = await ingest_planning_records(conn, client)
    assert count == 2
    # Verify is_project flag
    projects = conn.execute(
        "SELECT record_id, is_project FROM planning_records ORDER BY record_id"
    ).fetchall()
    assert projects[0] == ("NP-1", False)
    assert projects[1] == ("PR-1", True)
    conn.close()


@pytest.mark.asyncio
async def test_ingest_tax_rolls():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([
        {"block": "1000", "lot": "001", "closed_roll_year": "2024",
         "zoning_code": "RC-4", "assessed_land_value": "500000"},
        {"block": "1000", "lot": "001", "closed_roll_year": "2023",
         "zoning_code": "RC-4", "assessed_land_value": "480000"},
    ])
    count = await ingest_tax_rolls(conn, client)
    assert count == 2
    row = conn.execute(
        "SELECT zoning_code FROM tax_rolls WHERE tax_year = '2024'"
    ).fetchone()
    assert row[0] == "RC-4"
    conn.close()


# ── Cron endpoint tests ──────────────────────────────────────────


CRON_ENDPOINTS = [
    "/cron/ingest-boiler",
    "/cron/ingest-fire",
    "/cron/ingest-planning",
    "/cron/ingest-tax-rolls",
    "/cron/cross-ref-check",
]


class TestCronAuth:
    """All ingest cron endpoints require CRON_SECRET auth."""

    @pytest.mark.parametrize("endpoint", CRON_ENDPOINTS)
    def test_no_auth_returns_403(self, client, endpoint):
        rv = client.post(endpoint)
        assert rv.status_code == 403

    @pytest.mark.parametrize("endpoint", CRON_ENDPOINTS)
    def test_wrong_token_returns_403(self, client, endpoint, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "correct-secret")
        rv = client.post(endpoint, headers={"Authorization": "Bearer wrong-secret"})
        assert rv.status_code == 403


# ── Schema tests ─────────────────────────────────────────────────


class TestSchema:
    def test_new_tables_created(self):
        """init_schema creates all 4 new tables."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        tables = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "boiler_permits" in table_names
        assert "fire_permits" in table_names
        assert "planning_records" in table_names
        assert "tax_rolls" in table_names
        conn.close()

    def test_tax_rolls_composite_pk(self):
        """Tax rolls table has composite PK (block, lot, tax_year)."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        # Insert two rows with same block/lot but different year
        conn.execute(
            "INSERT INTO tax_rolls (block, lot, tax_year) VALUES ('1', '2', '2024')"
        )
        conn.execute(
            "INSERT INTO tax_rolls (block, lot, tax_year) VALUES ('1', '2', '2023')"
        )
        count = conn.execute("SELECT COUNT(*) FROM tax_rolls").fetchone()[0]
        assert count == 2
        conn.close()


# ── Cross-reference join tests ────────────────────────────────────


class TestCrossRef:
    def test_planning_to_permits_join(self):
        """Planning records join to permits via block/lot."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        conn.execute(
            "INSERT INTO permits (permit_number, block, lot, status) "
            "VALUES ('P-1', '1000', '001', 'issued')"
        )
        conn.execute(
            "INSERT INTO planning_records (record_id, block, lot, record_status) "
            "VALUES ('PR-1', '1000', '001', 'filed')"
        )
        result = conn.execute("""
            SELECT COUNT(DISTINCT pr.record_id)
            FROM planning_records pr
            JOIN permits p ON pr.block = p.block AND pr.lot = p.lot
        """).fetchone()[0]
        assert result == 1
        conn.close()

    def test_boiler_to_permits_join(self):
        """Boiler permits join to building permits via block/lot."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        conn.execute(
            "INSERT INTO permits (permit_number, block, lot, status) "
            "VALUES ('P-1', '2000', '005', 'issued')"
        )
        conn.execute(
            "INSERT INTO boiler_permits (permit_number, block, lot, status) "
            "VALUES ('BP-1', '2000', '005', 'issued')"
        )
        result = conn.execute("""
            SELECT COUNT(DISTINCT bp.permit_number)
            FROM boiler_permits bp
            JOIN permits p ON bp.block = p.block AND bp.lot = p.lot
        """).fetchone()[0]
        assert result == 1
        conn.close()

    def test_tax_to_permits_join(self):
        """Tax rolls join to active permits via block/lot."""
        conn = db_mod.get_connection()
        db_mod.init_schema(conn)
        conn.execute(
            "INSERT INTO permits (permit_number, block, lot, status) "
            "VALUES ('P-1', '3000', '010', 'issued')"
        )
        conn.execute(
            "INSERT INTO tax_rolls (block, lot, tax_year, zoning_code) "
            "VALUES ('3000', '010', '2024', 'RC-4')"
        )
        result = conn.execute("""
            SELECT COUNT(DISTINCT tr.block || '-' || tr.lot)
            FROM tax_rolls tr
            JOIN permits p ON tr.block = p.block AND tr.lot = p.lot
            WHERE p.status IN ('issued', 'complete', 'filed', 'approved')
        """).fetchone()[0]
        assert result == 1
        conn.close()
