"""Tests for QS8-T3-C — electrical, plumbing, and boiler permit ingest functions.

Covers:
- DATASETS dict entries for electrical_permits, plumbing_permits, boiler_permits
- _normalize_boiler_permit(): field positions, NULL handling, missing fields
- _normalize_electrical_permit(): already exercised in test_ingest_electrical_plumbing.py
  — re-verified here for permit_type column integrity
- _normalize_plumbing_permit(): already exercised in test_ingest_electrical_plumbing.py
  — re-verified here for permit_type column integrity
- ingest_electrical_permits(): DB round-trip with mocked SODA, verify INSERT
- ingest_plumbing_permits(): DB round-trip with mocked SODA, verify INSERT
- ingest_boiler_permits(): DB round-trip with mocked SODA, verify INSERT
- CLI main(): --electrical, --plumbing, --boiler flags exist and map to correct kwargs
- run_ingestion(): electrical_permits, plumbing_permits, boiler kwargs accepted
"""

import re
import inspect
import pytest


# ── Helpers ───────────────────────────────────────────────────────


class _MockSODAClient:
    """Mock SODA client that returns fixed data without network access."""

    def __init__(self, records):
        self._records = records

    async def count(self, endpoint_id, where=None):
        return len(self._records)

    async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
        offset = offset or 0
        if limit is not None:
            return self._records[offset : offset + limit]
        return self._records[offset:]

    async def close(self):
        pass


@pytest.fixture
def duck_conn(tmp_path):
    """Return an in-memory-ish DuckDB connection with schema initialized."""
    import duckdb
    from src.db import init_schema

    path = str(tmp_path / "test_sprint_81_3.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)
    return conn


# ── DATASETS dict ─────────────────────────────────────────────────


def test_datasets_boiler_permits_present():
    from src.ingest import DATASETS
    assert "boiler_permits" in DATASETS


def test_datasets_electrical_permits_present():
    from src.ingest import DATASETS
    assert "electrical_permits" in DATASETS


def test_datasets_plumbing_permits_present():
    from src.ingest import DATASETS
    assert "plumbing_permits" in DATASETS


def test_boiler_permits_endpoint_id():
    from src.ingest import DATASETS
    # Correct production endpoint for SF Boiler Permits
    assert DATASETS["boiler_permits"]["endpoint_id"] == "5dp4-gtxk"


def test_electrical_permits_endpoint_id():
    from src.ingest import DATASETS
    # Correct production endpoint for SF Electrical Permits
    assert DATASETS["electrical_permits"]["endpoint_id"] == "ftty-kx6y"


def test_plumbing_permits_endpoint_id():
    from src.ingest import DATASETS
    # Correct production endpoint for SF Plumbing Permits
    assert DATASETS["plumbing_permits"]["endpoint_id"] == "a6aw-rudh"


@pytest.mark.parametrize("key", ["electrical_permits", "plumbing_permits", "boiler_permits"])
def test_endpoint_id_format(key):
    """All endpoint IDs must match Socrata 4x4 format: xxxx-xxxx."""
    from src.ingest import DATASETS
    eid = DATASETS[key]["endpoint_id"]
    assert re.match(r"^[a-z0-9]{4}-[a-z0-9]{4}$", eid), f"Bad endpoint_id for {key}: {eid}"


@pytest.mark.parametrize("key", ["electrical_permits", "plumbing_permits", "boiler_permits"])
def test_datasets_has_name(key):
    from src.ingest import DATASETS
    assert DATASETS[key].get("name"), f"{key} must have a 'name' field"


# ── _normalize_boiler_permit ──────────────────────────────────────


def test_normalize_boiler_permit_basic():
    """Basic boiler permit record maps all expected fields."""
    from src.ingest import _normalize_boiler_permit

    record = {
        "permit_number": "BLR2025-0001",
        "block": "4200",
        "lot": "015",
        "status": "Issued",
        "boiler_type": "Steam",
        "boiler_serial_number": "SN123456",
        "model": "Cleaver-Brooks CB-200",
        "description": "Replace steam boiler — 200 HP",
        "application_date": "2025-06-01",
        "expiration_date": "2026-06-01",
        "street_number": "500",
        "street_name": "MARKET",
        "street_suffix": "ST",
        "zip_code": "94105",
        "neighborhood": "Financial District",
        "supervisor_district": "3",
        "data_as_of": "2026-02-27",
    }

    result = _normalize_boiler_permit(record)

    # 17 columns in boiler_permits table
    assert len(result) == 17

    # Column positions:
    # 0: permit_number, 1: block, 2: lot, 3: status, 4: boiler_type,
    # 5: boiler_serial_number, 6: model, 7: description,
    # 8: application_date, 9: expiration_date,
    # 10: street_number, 11: street_name, 12: street_suffix,
    # 13: zip_code, 14: neighborhood, 15: supervisor_district, 16: data_as_of

    assert result[0] == "BLR2025-0001"
    assert result[1] == "4200"
    assert result[2] == "015"
    assert result[3] == "Issued"
    assert result[4] == "Steam"
    assert result[5] == "SN123456"
    assert result[6] == "Cleaver-Brooks CB-200"
    assert result[7] == "Replace steam boiler — 200 HP"
    assert result[8] == "2025-06-01"
    assert result[9] == "2026-06-01"
    assert result[10] == "500"
    assert result[11] == "MARKET"
    assert result[12] == "ST"
    assert result[13] == "94105"
    assert result[14] == "Financial District"
    assert result[15] == "3"
    assert result[16] == "2026-02-27"


def test_normalize_boiler_permit_missing_permit_number():
    """Missing permit_number falls back to empty string (not None)."""
    from src.ingest import _normalize_boiler_permit
    result = _normalize_boiler_permit({})
    assert result[0] == ""


def test_normalize_boiler_permit_minimal_record():
    """Record with only permit_number should not raise and fills nulls."""
    from src.ingest import _normalize_boiler_permit
    result = _normalize_boiler_permit({"permit_number": "BLR999"})
    assert result[0] == "BLR999"
    assert len(result) == 17
    # All optional fields should be None
    for i in range(1, 17):
        assert result[i] is None, f"Expected None at position {i}, got {result[i]!r}"


def test_normalize_boiler_permit_partial_address():
    """Partial address — only street_number — doesn't crash."""
    from src.ingest import _normalize_boiler_permit
    record = {
        "permit_number": "BLR2025-0002",
        "street_number": "100",
    }
    result = _normalize_boiler_permit(record)
    assert result[10] == "100"
    assert result[11] is None  # street_name
    assert result[12] is None  # street_suffix


def test_normalize_boiler_permit_null_status():
    """None status is preserved as None, not coerced to empty string."""
    from src.ingest import _normalize_boiler_permit
    record = {"permit_number": "BLR001", "status": None}
    result = _normalize_boiler_permit(record)
    assert result[3] is None


def test_normalize_boiler_permit_various_status_values():
    """Status values are passed through verbatim."""
    from src.ingest import _normalize_boiler_permit
    for status_val in ("Issued", "Filed", "Expired", "Cancelled", "Approved"):
        result = _normalize_boiler_permit({"permit_number": "BLR001", "status": status_val})
        assert result[3] == status_val


def test_normalize_boiler_permit_uses_zip_code_not_zipcode():
    """Boiler permits use 'zip_code' field name (not 'zipcode')."""
    from src.ingest import _normalize_boiler_permit
    record = {"permit_number": "BLR001", "zip_code": "94110", "zipcode": "99999"}
    result = _normalize_boiler_permit(record)
    # The normalizer reads record.get("zip_code") — should get "94110"
    assert result[13] == "94110"


def test_normalize_boiler_permit_no_zip_returns_none():
    """Missing zip_code results in None."""
    from src.ingest import _normalize_boiler_permit
    result = _normalize_boiler_permit({"permit_number": "BLR001"})
    assert result[13] is None


# ── _normalize_electrical_permit — permit_type integrity ─────────


def test_normalize_electrical_permit_type_constant():
    """permit_type must always be 'electrical' (not inferred from data)."""
    from src.ingest import _normalize_electrical_permit
    record = {"permit_number": "E001", "permit_type": "should be ignored"}
    result = _normalize_electrical_permit(record)
    assert result[1] == "electrical"
    assert result[2] == "Electrical Permit"


def test_normalize_electrical_permit_tuple_length():
    """Output tuple must be 26 columns to match permits table schema."""
    from src.ingest import _normalize_electrical_permit
    result = _normalize_electrical_permit({"permit_number": "E001"})
    assert len(result) == 26


# ── _normalize_plumbing_permit — permit_type integrity ───────────


def test_normalize_plumbing_permit_type_constant():
    """permit_type must always be 'plumbing'."""
    from src.ingest import _normalize_plumbing_permit
    record = {"permit_number": "PM001", "permit_type": "should be ignored"}
    result = _normalize_plumbing_permit(record)
    assert result[1] == "plumbing"
    assert result[2] == "Plumbing Permit"


def test_normalize_plumbing_permit_tuple_length():
    """Output tuple must be 26 columns to match permits table schema."""
    from src.ingest import _normalize_plumbing_permit
    result = _normalize_plumbing_permit({"permit_number": "PM001"})
    assert len(result) == 26


# ── ingest_electrical_permits — DB round-trip ────────────────────


@pytest.mark.asyncio
async def test_ingest_electrical_permits_inserts_records(duck_conn):
    """Mock SODA client → ingest → verify records in permits table."""
    from src.ingest import ingest_electrical_permits

    sample = [
        {
            "permit_number": "E-2025-001",
            "street_number": "123",
            "street_name": "MISSION",
            "street_suffix": "ST",
            "description": "Install EV charging circuit",
            "status": "issued",
            "filed_date": "2025-01-15",
            "issued_date": "2025-02-01",
            "completed_date": None,
            "zip_code": "94103",
            "block": "3701",
            "lot": "001",
            "data_as_of": "2026-02-27",
        },
        {
            "permit_number": "E-2025-002",
            "street_number": "456",
            "street_name": "VALENCIA",
            "street_suffix": "ST",
            "description": "100A panel upgrade",
            "status": "complete",
            "filed_date": "2025-03-01",
            "issued_date": "2025-03-10",
            "completed_date": "2025-03-20",
            "zip_code": "94110",
            "block": "6510",
            "lot": "005",
            "data_as_of": "2026-02-27",
        },
    ]

    client = _MockSODAClient(sample)
    count = await ingest_electrical_permits(duck_conn, client)

    assert count == 2

    rows = duck_conn.execute(
        "SELECT permit_number, permit_type, permit_type_definition, zipcode "
        "FROM permits WHERE permit_type = 'electrical' ORDER BY permit_number"
    ).fetchall()

    assert len(rows) == 2
    assert rows[0] == ("E-2025-001", "electrical", "Electrical Permit", "94103")
    assert rows[1] == ("E-2025-002", "electrical", "Electrical Permit", "94110")


@pytest.mark.asyncio
async def test_ingest_electrical_permits_logs_to_ingest_log(duck_conn):
    """ingest_electrical_permits writes an entry to ingest_log."""
    from src.ingest import ingest_electrical_permits

    client = _MockSODAClient([{"permit_number": "E-001", "data_as_of": "2026-02-27"}])
    await ingest_electrical_permits(duck_conn, client)

    rows = duck_conn.execute(
        "SELECT dataset_id, dataset_name FROM ingest_log WHERE dataset_id = 'ftty-kx6y'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "ftty-kx6y"
    assert rows[0][1] == "Electrical Permits"


@pytest.mark.asyncio
async def test_ingest_electrical_permits_empty_dataset(duck_conn):
    """Empty SODA response → zero records inserted, no exception."""
    from src.ingest import ingest_electrical_permits

    count = await ingest_electrical_permits(duck_conn, _MockSODAClient([]))
    assert count == 0


@pytest.mark.asyncio
async def test_ingest_electrical_permits_idempotent(duck_conn):
    """Re-running ingest with same permit_number uses INSERT OR REPLACE — no duplicates."""
    from src.ingest import ingest_electrical_permits

    record = [{"permit_number": "E-DUPE", "zip_code": "94103", "status": "issued", "data_as_of": "2026-02-27"}]
    client = _MockSODAClient(record)

    await ingest_electrical_permits(duck_conn, client)
    await ingest_electrical_permits(duck_conn, client)

    rows = duck_conn.execute(
        "SELECT COUNT(*) FROM permits WHERE permit_number = 'E-DUPE'"
    ).fetchone()
    assert rows[0] == 1


# ── ingest_plumbing_permits — DB round-trip ──────────────────────


@pytest.mark.asyncio
async def test_ingest_plumbing_permits_inserts_records(duck_conn):
    """Mock SODA client → ingest → verify records in permits table."""
    from src.ingest import ingest_plumbing_permits

    sample = [
        {
            "permit_number": "PM-2025-001",
            "street_number": "789",
            "street_name": "FOLSOM",
            "street_suffix": "ST",
            "description": "Replace water heater",
            "status": "complete",
            "filed_date": "2025-04-01",
            "issued_date": "2025-04-05",
            "completed_date": "2025-04-10",
            "zipcode": "94107",
            "block": "3800",
            "lot": "010",
            "data_as_of": "2026-02-27",
        },
        {
            "permit_number": "PM-2025-002",
            "street_number": "321",
            "street_name": "BRANNAN",
            "street_suffix": "ST",
            "description": "New gas line for range",
            "status": "issued",
            "filed_date": "2025-05-01",
            "issued_date": "2025-05-08",
            "completed_date": None,
            "zipcode": "94107",
            "block": "3755",
            "lot": "020",
            "data_as_of": "2026-02-27",
        },
    ]

    count = await ingest_plumbing_permits(duck_conn, _MockSODAClient(sample))

    assert count == 2

    rows = duck_conn.execute(
        "SELECT permit_number, permit_type, permit_type_definition, zipcode "
        "FROM permits WHERE permit_type = 'plumbing' ORDER BY permit_number"
    ).fetchall()

    assert len(rows) == 2
    assert rows[0] == ("PM-2025-001", "plumbing", "Plumbing Permit", "94107")
    assert rows[1] == ("PM-2025-002", "plumbing", "Plumbing Permit", "94107")


@pytest.mark.asyncio
async def test_ingest_plumbing_permits_logs_to_ingest_log(duck_conn):
    """ingest_plumbing_permits writes an entry to ingest_log."""
    from src.ingest import ingest_plumbing_permits

    await ingest_plumbing_permits(duck_conn, _MockSODAClient([{"permit_number": "PM-001"}]))

    rows = duck_conn.execute(
        "SELECT dataset_id, dataset_name FROM ingest_log WHERE dataset_id = 'a6aw-rudh'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "a6aw-rudh"
    assert rows[0][1] == "Plumbing Permits"


@pytest.mark.asyncio
async def test_ingest_plumbing_permits_empty_dataset(duck_conn):
    """Empty SODA response → zero records inserted."""
    from src.ingest import ingest_plumbing_permits
    count = await ingest_plumbing_permits(duck_conn, _MockSODAClient([]))
    assert count == 0


@pytest.mark.asyncio
async def test_ingest_plumbing_permits_idempotent(duck_conn):
    """Re-running ingest with same permit_number → no duplicates."""
    from src.ingest import ingest_plumbing_permits

    record = [{"permit_number": "PM-DUPE", "zipcode": "94102", "status": "issued"}]
    client = _MockSODAClient(record)

    await ingest_plumbing_permits(duck_conn, client)
    await ingest_plumbing_permits(duck_conn, client)

    rows = duck_conn.execute(
        "SELECT COUNT(*) FROM permits WHERE permit_number = 'PM-DUPE'"
    ).fetchone()
    assert rows[0] == 1


# ── ingest_boiler_permits — DB round-trip ────────────────────────


@pytest.mark.asyncio
async def test_ingest_boiler_permits_inserts_records(duck_conn):
    """Mock SODA client → ingest → verify records in boiler_permits table."""
    from src.ingest import ingest_boiler_permits

    sample = [
        {
            "permit_number": "BLR-2025-001",
            "block": "4200",
            "lot": "015",
            "status": "Issued",
            "boiler_type": "Steam",
            "boiler_serial_number": "SN001",
            "model": "Cleaver-Brooks 200",
            "description": "Install new steam boiler",
            "application_date": "2025-01-10",
            "expiration_date": "2026-01-10",
            "street_number": "500",
            "street_name": "MARKET",
            "street_suffix": "ST",
            "zip_code": "94105",
            "neighborhood": "Financial District",
            "supervisor_district": "3",
            "data_as_of": "2026-02-27",
        },
        {
            "permit_number": "BLR-2025-002",
            "block": "1001",
            "lot": "002",
            "status": "Filed",
            "boiler_type": "Hot Water",
            "boiler_serial_number": "SN002",
            "model": "Burnham IN6",
            "description": "Replace hot water boiler",
            "application_date": "2025-06-01",
            "expiration_date": "2026-06-01",
            "street_number": "100",
            "street_name": "FELL",
            "street_suffix": "ST",
            "zip_code": "94102",
            "neighborhood": "Hayes Valley",
            "supervisor_district": "5",
            "data_as_of": "2026-02-27",
        },
    ]

    count = await ingest_boiler_permits(duck_conn, _MockSODAClient(sample))

    assert count == 2

    rows = duck_conn.execute(
        "SELECT permit_number, status, boiler_type, zip_code "
        "FROM boiler_permits ORDER BY permit_number"
    ).fetchall()

    assert len(rows) == 2
    assert rows[0] == ("BLR-2025-001", "Issued", "Steam", "94105")
    assert rows[1] == ("BLR-2025-002", "Filed", "Hot Water", "94102")


@pytest.mark.asyncio
async def test_ingest_boiler_permits_logs_to_ingest_log(duck_conn):
    """ingest_boiler_permits writes an entry to ingest_log."""
    from src.ingest import ingest_boiler_permits

    await ingest_boiler_permits(duck_conn, _MockSODAClient([{"permit_number": "BLR-001"}]))

    rows = duck_conn.execute(
        "SELECT dataset_id, dataset_name FROM ingest_log WHERE dataset_id = '5dp4-gtxk'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "5dp4-gtxk"
    assert rows[0][1] == "Boiler Permits"


@pytest.mark.asyncio
async def test_ingest_boiler_permits_empty_dataset(duck_conn):
    """Empty SODA response → zero records inserted."""
    from src.ingest import ingest_boiler_permits
    count = await ingest_boiler_permits(duck_conn, _MockSODAClient([]))
    assert count == 0


@pytest.mark.asyncio
async def test_ingest_boiler_permits_clears_existing_rows(duck_conn):
    """Each ingest run deletes and re-inserts — table is wiped first."""
    from src.ingest import ingest_boiler_permits

    first_batch = [{"permit_number": "BLR-OLD", "status": "Expired"}]
    second_batch = [{"permit_number": "BLR-NEW", "status": "Issued"}]

    await ingest_boiler_permits(duck_conn, _MockSODAClient(first_batch))
    await ingest_boiler_permits(duck_conn, _MockSODAClient(second_batch))

    # After second run, only BLR-NEW should exist
    rows = duck_conn.execute("SELECT permit_number FROM boiler_permits ORDER BY permit_number").fetchall()
    permit_nums = [r[0] for r in rows]
    assert "BLR-NEW" in permit_nums
    assert "BLR-OLD" not in permit_nums


@pytest.mark.asyncio
async def test_ingest_boiler_permits_all_fields_stored(duck_conn):
    """All 17 boiler permit fields are correctly stored."""
    from src.ingest import ingest_boiler_permits

    record = {
        "permit_number": "BLR-FULL",
        "block": "9999",
        "lot": "099",
        "status": "Issued",
        "boiler_type": "Hot Water",
        "boiler_serial_number": "HW-SERIAL",
        "model": "Weil-McLain Ultra",
        "description": "Full field test boiler",
        "application_date": "2025-10-01",
        "expiration_date": "2026-10-01",
        "street_number": "42",
        "street_name": "ANSWER",
        "street_suffix": "BLVD",
        "zip_code": "94118",
        "neighborhood": "Richmond District",
        "supervisor_district": "1",
        "data_as_of": "2026-02-27",
    }

    await ingest_boiler_permits(duck_conn, _MockSODAClient([record]))

    row = duck_conn.execute(
        "SELECT permit_number, block, lot, status, boiler_type, boiler_serial_number, "
        "model, description, application_date, expiration_date, "
        "street_number, street_name, street_suffix, zip_code, "
        "neighborhood, supervisor_district, data_as_of "
        "FROM boiler_permits WHERE permit_number = 'BLR-FULL'"
    ).fetchone()

    assert row is not None
    assert row[0] == "BLR-FULL"
    assert row[1] == "9999"        # block
    assert row[2] == "099"         # lot
    assert row[3] == "Issued"      # status
    assert row[4] == "Hot Water"   # boiler_type
    assert row[5] == "HW-SERIAL"   # boiler_serial_number
    assert row[6] == "Weil-McLain Ultra"  # model
    assert row[7] == "Full field test boiler"  # description
    assert row[8] == "2025-10-01"  # application_date
    assert row[9] == "2026-10-01"  # expiration_date
    assert row[10] == "42"         # street_number
    assert row[11] == "ANSWER"     # street_name
    assert row[12] == "BLVD"       # street_suffix
    assert row[13] == "94118"      # zip_code
    assert row[14] == "Richmond District"  # neighborhood
    assert row[15] == "1"          # supervisor_district
    assert row[16] == "2026-02-27" # data_as_of


# ── CLI flags ─────────────────────────────────────────────────────


def test_cli_has_electrical_permits_flag():
    """--electrical-permits flag must exist in the CLI parser."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "--electrical-permits" in source


def test_cli_has_plumbing_permits_flag():
    """--plumbing-permits flag must exist in the CLI parser."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "--plumbing-permits" in source


def test_cli_has_boiler_flag():
    """--boiler flag must exist in the CLI parser."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "--boiler" in source


def test_cli_electrical_permits_passes_to_run_ingestion():
    """--electrical-permits CLI flag maps to electrical_permits kwarg in run_ingestion."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "electrical_permits" in source


def test_cli_plumbing_permits_passes_to_run_ingestion():
    """--plumbing-permits CLI flag maps to plumbing_permits kwarg in run_ingestion."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "plumbing_permits" in source


def test_cli_boiler_passes_to_run_ingestion():
    """--boiler CLI flag maps to boiler kwarg in run_ingestion."""
    import src.ingest as ingest_mod
    source = inspect.getsource(ingest_mod.main)
    assert "boiler" in source


# ── run_ingestion signature ───────────────────────────────────────


def test_run_ingestion_accepts_electrical_permits_kwarg():
    """run_ingestion must accept electrical_permits keyword argument."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    assert "electrical_permits" in sig.parameters


def test_run_ingestion_accepts_plumbing_permits_kwarg():
    """run_ingestion must accept plumbing_permits keyword argument."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    assert "plumbing_permits" in sig.parameters


def test_run_ingestion_accepts_boiler_kwarg():
    """run_ingestion must accept boiler keyword argument."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    assert "boiler" in sig.parameters


def test_run_ingestion_electrical_permits_default_true():
    """electrical_permits defaults to True so it runs in the standard pipeline."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    default = sig.parameters["electrical_permits"].default
    assert default is True


def test_run_ingestion_plumbing_permits_default_true():
    """plumbing_permits defaults to True."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    default = sig.parameters["plumbing_permits"].default
    assert default is True


def test_run_ingestion_boiler_default_true():
    """boiler defaults to True."""
    import src.ingest as ingest_mod
    sig = inspect.signature(ingest_mod.run_ingestion)
    default = sig.parameters["boiler"].default
    assert default is True


# ── Cross-type isolation ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_electrical_and_plumbing_do_not_contaminate_permits_table(duck_conn):
    """Electrical and plumbing permits are distinguishable by permit_type column."""
    from src.ingest import ingest_electrical_permits, ingest_plumbing_permits

    elec = [{"permit_number": "E-CROSS", "zip_code": "94101", "status": "issued"}]
    plmb = [{"permit_number": "PM-CROSS", "zipcode": "94102", "status": "complete"}]

    await ingest_electrical_permits(duck_conn, _MockSODAClient(elec))
    await ingest_plumbing_permits(duck_conn, _MockSODAClient(plmb))

    elec_rows = duck_conn.execute(
        "SELECT permit_type FROM permits WHERE permit_number = 'E-CROSS'"
    ).fetchall()
    plmb_rows = duck_conn.execute(
        "SELECT permit_type FROM permits WHERE permit_number = 'PM-CROSS'"
    ).fetchall()

    assert elec_rows[0][0] == "electrical"
    assert plmb_rows[0][0] == "plumbing"


@pytest.mark.asyncio
async def test_boiler_permits_stored_in_separate_table(duck_conn):
    """Boiler permits are stored in boiler_permits, NOT in the shared permits table."""
    from src.ingest import ingest_boiler_permits

    await ingest_boiler_permits(
        duck_conn, _MockSODAClient([{"permit_number": "BLR-SEP", "status": "Issued"}])
    )

    # Should be in boiler_permits
    boiler_rows = duck_conn.execute(
        "SELECT permit_number FROM boiler_permits WHERE permit_number = 'BLR-SEP'"
    ).fetchall()
    assert len(boiler_rows) == 1

    # Should NOT be in the shared permits table
    permits_rows = duck_conn.execute(
        "SELECT permit_number FROM permits WHERE permit_number = 'BLR-SEP'"
    ).fetchall()
    assert len(permits_rows) == 0
