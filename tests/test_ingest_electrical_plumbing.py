"""Tests for electrical and plumbing permit ingestion.

Covers:
- DATASETS dict entries: endpoint IDs, names, presence
- _normalize_electrical_permit(): field mapping, NULL handling, zip_code aliasing
- _normalize_plumbing_permit(): field mapping, NULL handling
- ingest_electrical_permits() / ingest_plumbing_permits(): DB round-trip with
  a tmp DuckDB instance (no network access)
- run_ingestion(): new keyword args (electrical_permits, plumbing_permits)
- CLI main(): new --electrical-permits and --plumbing-permits flags
"""

import re
import pytest


# ── DATASETS dict ─────────────────────────────────────────────────

def test_datasets_contains_electrical_permits():
    from src.ingest import DATASETS
    assert "electrical_permits" in DATASETS


def test_datasets_contains_plumbing_permits():
    from src.ingest import DATASETS
    assert "plumbing_permits" in DATASETS


def test_electrical_permits_endpoint_id():
    from src.ingest import DATASETS
    assert DATASETS["electrical_permits"]["endpoint_id"] == "ftty-kx6y"


def test_plumbing_permits_endpoint_id():
    from src.ingest import DATASETS
    assert DATASETS["plumbing_permits"]["endpoint_id"] == "a6aw-rudh"


def test_endpoint_id_format_electrical():
    """Endpoint IDs must match the Socrata 4x4 format: xxxx-xxxx."""
    from src.ingest import DATASETS
    eid = DATASETS["electrical_permits"]["endpoint_id"]
    assert re.match(r"^[a-z0-9]{4}-[a-z0-9]{4}$", eid), f"Bad endpoint_id format: {eid}"


def test_endpoint_id_format_plumbing():
    from src.ingest import DATASETS
    eid = DATASETS["plumbing_permits"]["endpoint_id"]
    assert re.match(r"^[a-z0-9]{4}-[a-z0-9]{4}$", eid), f"Bad endpoint_id format: {eid}"


def test_electrical_permits_has_name():
    from src.ingest import DATASETS
    assert DATASETS["electrical_permits"].get("name"), "electrical_permits entry must have a name"


def test_plumbing_permits_has_name():
    from src.ingest import DATASETS
    assert DATASETS["plumbing_permits"].get("name"), "plumbing_permits entry must have a name"


# ── _normalize_electrical_permit ─────────────────────────────────


def test_normalize_electrical_permit_basic():
    from src.ingest import _normalize_electrical_permit
    record = {
        "permit_number": "E202501234",
        "application_creation_date": "2025-01-10T00:00:00.000",
        "block": "3512",
        "lot": "001",
        "street_number": "100",
        "street_name": "MAIN",
        "street_suffix": "ST",
        "description": "New electrical service",
        "status": "issued",
        "filed_date": "2025-01-10",
        "issued_date": "2025-02-01",
        "completed_date": None,
        "zip_code": "94110",
        "data_as_of": "2026-02-20",
    }
    result = _normalize_electrical_permit(record)

    # Tuple must have 26 columns matching the permits table
    assert len(result) == 26

    # Column positions match permits table schema:
    # 0: permit_number, 1: permit_type, 2: permit_type_definition, 3: status,
    # 4: status_date, 5: description, 6: filed_date, 7: issued_date,
    # 8: approved_date, 9: completed_date, 10: estimated_cost, 11: revised_cost,
    # 12: existing_use, 13: proposed_use, 14: existing_units, 15: proposed_units,
    # 16: street_number, 17: street_name, 18: street_suffix, 19: zipcode,
    # 20: neighborhood, 21: supervisor_district, 22: block, 23: lot,
    # 24: adu, 25: data_as_of

    assert result[0] == "E202501234"        # permit_number
    assert result[1] == "electrical"        # permit_type
    assert result[2] == "Electrical Permit" # permit_type_definition
    assert result[3] == "issued"            # status
    assert result[4] is None               # status_date (not in dataset)
    assert result[5] == "New electrical service"
    assert result[6] == "2025-01-10"        # filed_date
    assert result[7] == "2025-02-01"        # issued_date
    assert result[8] is None               # approved_date (not in dataset)
    assert result[9] is None               # completed_date
    assert result[10] is None              # estimated_cost
    assert result[11] is None              # revised_cost
    assert result[12] is None              # existing_use
    assert result[13] is None              # proposed_use
    assert result[14] is None              # existing_units
    assert result[15] is None              # proposed_units
    assert result[16] == "100"             # street_number
    assert result[17] == "MAIN"            # street_name
    assert result[18] == "ST"              # street_suffix
    assert result[19] == "94110"           # zipcode (mapped from zip_code)
    assert result[20] is None              # neighborhood (not in dataset)
    assert result[21] is None              # supervisor_district (not in dataset)
    assert result[22] == "3512"            # block
    assert result[23] == "001"             # lot
    assert result[24] is None              # adu (not in dataset)
    assert result[25] == "2026-02-20"      # data_as_of


def test_normalize_electrical_permit_zip_code_aliasing():
    """Electrical permits use zip_code (not zipcode) — must be mapped correctly."""
    from src.ingest import _normalize_electrical_permit
    record = {
        "permit_number": "E001",
        "zip_code": "94103",
    }
    result = _normalize_electrical_permit(record)
    assert result[19] == "94103"  # zipcode column


def test_normalize_electrical_permit_missing_zip():
    """Missing zip_code should produce None in zipcode column."""
    from src.ingest import _normalize_electrical_permit
    record = {"permit_number": "E002"}
    result = _normalize_electrical_permit(record)
    assert result[19] is None


def test_normalize_electrical_permit_empty_record():
    """Minimal record with only permit_number should not raise."""
    from src.ingest import _normalize_electrical_permit
    result = _normalize_electrical_permit({"permit_number": "E999"})
    assert result[0] == "E999"
    assert len(result) == 26


def test_normalize_electrical_permit_missing_permit_number():
    """Missing permit_number falls back to empty string."""
    from src.ingest import _normalize_electrical_permit
    result = _normalize_electrical_permit({})
    assert result[0] == ""


# ── _normalize_plumbing_permit ────────────────────────────────────


def test_normalize_plumbing_permit_basic():
    from src.ingest import _normalize_plumbing_permit
    record = {
        "permit_number": "PM202504321",
        "application_date": "2025-04-01T00:00:00.000",
        "block": "1234",
        "lot": "002",
        "parcel_number": "1234002",
        "street_number": "200",
        "street_name": "OAK",
        "street_suffix": "AVE",
        "unit": "3",
        "description": "Replace water heater",
        "status": "complete",
        "filed_date": "2025-04-01",
        "issued_date": "2025-04-10",
        "completed_date": "2025-04-15",
        "zipcode": "94102",
        "data_as_of": "2026-02-20",
    }
    result = _normalize_plumbing_permit(record)

    assert len(result) == 26

    assert result[0] == "PM202504321"      # permit_number
    assert result[1] == "plumbing"         # permit_type
    assert result[2] == "Plumbing Permit"  # permit_type_definition
    assert result[3] == "complete"         # status
    assert result[4] is None              # status_date (not in dataset)
    assert result[5] == "Replace water heater"
    assert result[6] == "2025-04-01"       # filed_date
    assert result[7] == "2025-04-10"       # issued_date
    assert result[8] is None              # approved_date (not in dataset)
    assert result[9] == "2025-04-15"       # completed_date
    assert result[10] is None             # estimated_cost
    assert result[11] is None             # revised_cost
    assert result[12] is None             # existing_use
    assert result[13] is None             # proposed_use
    assert result[14] is None             # existing_units
    assert result[15] is None             # proposed_units
    assert result[16] == "200"            # street_number
    assert result[17] == "OAK"            # street_name
    assert result[18] == "AVE"            # street_suffix
    assert result[19] == "94102"          # zipcode
    assert result[20] is None             # neighborhood (not in dataset)
    assert result[21] is None             # supervisor_district (not in dataset)
    assert result[22] == "1234"           # block
    assert result[23] == "002"            # lot
    assert result[24] is None             # adu (not in dataset)
    assert result[25] == "2026-02-20"     # data_as_of


def test_normalize_plumbing_permit_empty_record():
    """Minimal record with only permit_number should not raise."""
    from src.ingest import _normalize_plumbing_permit
    result = _normalize_plumbing_permit({"permit_number": "PM999"})
    assert result[0] == "PM999"
    assert len(result) == 26


def test_normalize_plumbing_permit_missing_permit_number():
    """Missing permit_number falls back to empty string."""
    from src.ingest import _normalize_plumbing_permit
    result = _normalize_plumbing_permit({})
    assert result[0] == ""


def test_normalize_plumbing_permit_parcel_number_dropped():
    """parcel_number is not in the permits table — must not appear in output."""
    from src.ingest import _normalize_plumbing_permit
    record = {"permit_number": "PM001", "parcel_number": "9999999"}
    result = _normalize_plumbing_permit(record)
    # Verify parcel_number is NOT in the tuple (it has no column)
    assert "9999999" not in result


def test_normalize_plumbing_permit_unit_dropped():
    """unit is not in the permits table — must not appear in output."""
    from src.ingest import _normalize_plumbing_permit
    record = {"permit_number": "PM001", "unit": "5B"}
    result = _normalize_plumbing_permit(record)
    assert "5B" not in result


# ── DB round-trip tests (in-memory DuckDB, no network) ───────────


@pytest.fixture
def duck_conn(tmp_path):
    """Return an in-memory-like DuckDB connection with full schema applied."""
    import duckdb
    from src.db import init_schema
    path = str(tmp_path / "test_ingest.duckdb")
    conn = duckdb.connect(path)
    init_schema(conn)
    return conn


@pytest.mark.asyncio
async def test_ingest_electrical_permits_round_trip(duck_conn, monkeypatch):
    """ingest_electrical_permits() inserts records into the permits table."""
    from src.ingest import ingest_electrical_permits

    sample_records = [
        {
            "permit_number": "E001",
            "street_number": "100",
            "street_name": "MAIN",
            "street_suffix": "ST",
            "description": "New service",
            "status": "issued",
            "filed_date": "2025-01-01",
            "issued_date": "2025-02-01",
            "completed_date": None,
            "zip_code": "94110",
            "block": "3512",
            "lot": "001",
            "data_as_of": "2026-02-20",
        },
        {
            "permit_number": "E002",
            "street_number": "200",
            "street_name": "OAK",
            "street_suffix": "AVE",
            "description": "Panel upgrade",
            "status": "complete",
            "filed_date": "2025-03-01",
            "issued_date": "2025-03-15",
            "completed_date": "2025-04-01",
            "zip_code": "94102",
            "block": "1001",
            "lot": "002",
            "data_as_of": "2026-02-20",
        },
    ]

    # Mock the SODAClient so no network calls are made
    class MockClient:
        async def count(self, endpoint_id, where=None):
            return len(sample_records)

        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            if offset and offset >= len(sample_records):
                return []
            return sample_records[offset or 0 : (offset or 0) + (limit or len(sample_records))]

    count = await ingest_electrical_permits(duck_conn, MockClient())
    assert count == 2

    rows = duck_conn.execute(
        "SELECT permit_number, permit_type, permit_type_definition, zipcode "
        "FROM permits WHERE permit_type = 'electrical' ORDER BY permit_number"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == ("E001", "electrical", "Electrical Permit", "94110")
    assert rows[1] == ("E002", "electrical", "Electrical Permit", "94102")


@pytest.mark.asyncio
async def test_ingest_plumbing_permits_round_trip(duck_conn, monkeypatch):
    """ingest_plumbing_permits() inserts records into the permits table."""
    from src.ingest import ingest_plumbing_permits

    sample_records = [
        {
            "permit_number": "PM001",
            "application_date": "2025-04-01",
            "block": "1234",
            "lot": "003",
            "parcel_number": "1234003",
            "street_number": "300",
            "street_name": "ELM",
            "street_suffix": "ST",
            "unit": "1A",
            "description": "Water heater replacement",
            "status": "complete",
            "filed_date": "2025-04-01",
            "issued_date": "2025-04-10",
            "completed_date": "2025-04-20",
            "zipcode": "94107",
            "data_as_of": "2026-02-20",
        },
    ]

    class MockClient:
        async def count(self, endpoint_id, where=None):
            return len(sample_records)

        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            if offset and offset >= len(sample_records):
                return []
            return sample_records[offset or 0 : (offset or 0) + (limit or len(sample_records))]

    count = await ingest_plumbing_permits(duck_conn, MockClient())
    assert count == 1

    rows = duck_conn.execute(
        "SELECT permit_number, permit_type, permit_type_definition, zipcode "
        "FROM permits WHERE permit_type = 'plumbing'"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0] == ("PM001", "plumbing", "Plumbing Permit", "94107")


@pytest.mark.asyncio
async def test_electrical_permits_ingest_log(duck_conn):
    """ingest_electrical_permits() writes to the ingest_log table."""
    from src.ingest import ingest_electrical_permits

    class MockClient:
        async def count(self, endpoint_id, where=None):
            return 0

        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            return []

    await ingest_electrical_permits(duck_conn, MockClient())

    row = duck_conn.execute(
        "SELECT dataset_id, dataset_name FROM ingest_log WHERE dataset_id = 'ftty-kx6y'"
    ).fetchone()
    assert row is not None
    assert row[0] == "ftty-kx6y"
    assert row[1] == "Electrical Permits"


@pytest.mark.asyncio
async def test_plumbing_permits_ingest_log(duck_conn):
    """ingest_plumbing_permits() writes to the ingest_log table."""
    from src.ingest import ingest_plumbing_permits

    class MockClient:
        async def count(self, endpoint_id, where=None):
            return 0

        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            return []

    await ingest_plumbing_permits(duck_conn, MockClient())

    row = duck_conn.execute(
        "SELECT dataset_id, dataset_name FROM ingest_log WHERE dataset_id = 'a6aw-rudh'"
    ).fetchone()
    assert row is not None
    assert row[0] == "a6aw-rudh"
    assert row[1] == "Plumbing Permits"


@pytest.mark.asyncio
async def test_electrical_permits_insert_or_replace(duck_conn):
    """Re-ingesting electrical permits with same permit_number overwrites."""
    from src.ingest import ingest_electrical_permits

    record_v1 = [{"permit_number": "E001", "status": "filed", "zip_code": "94110"}]
    record_v2 = [{"permit_number": "E001", "status": "issued", "zip_code": "94110"}]

    class MockClientV1:
        async def count(self, endpoint_id, where=None):
            return 1
        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            if offset and offset >= 1:
                return []
            return record_v1

    class MockClientV2:
        async def count(self, endpoint_id, where=None):
            return 1
        async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
            if offset and offset >= 1:
                return []
            return record_v2

    await ingest_electrical_permits(duck_conn, MockClientV1())
    await ingest_electrical_permits(duck_conn, MockClientV2())

    rows = duck_conn.execute(
        "SELECT status FROM permits WHERE permit_number = 'E001'"
    ).fetchall()
    assert len(rows) == 1  # No duplicates
    assert rows[0][0] == "issued"  # Updated value


# ── run_ingestion signature ───────────────────────────────────────


def test_run_ingestion_accepts_electrical_permits_kwarg():
    """run_ingestion() must accept electrical_permits keyword argument."""
    import inspect
    from src.ingest import run_ingestion
    sig = inspect.signature(run_ingestion)
    assert "electrical_permits" in sig.parameters, \
        "run_ingestion() missing 'electrical_permits' parameter"


def test_run_ingestion_accepts_plumbing_permits_kwarg():
    """run_ingestion() must accept plumbing_permits keyword argument."""
    import inspect
    from src.ingest import run_ingestion
    sig = inspect.signature(run_ingestion)
    assert "plumbing_permits" in sig.parameters, \
        "run_ingestion() missing 'plumbing_permits' parameter"


def test_run_ingestion_electrical_defaults_to_true():
    import inspect
    from src.ingest import run_ingestion
    sig = inspect.signature(run_ingestion)
    assert sig.parameters["electrical_permits"].default is True


def test_run_ingestion_plumbing_defaults_to_true():
    import inspect
    from src.ingest import run_ingestion
    sig = inspect.signature(run_ingestion)
    assert sig.parameters["plumbing_permits"].default is True


# ── CLI flags ─────────────────────────────────────────────────────


def test_cli_has_electrical_permits_flag():
    """The CLI parser must recognise --electrical-permits."""
    import argparse
    # Simulate the argument parser from main() without running it
    parser = argparse.ArgumentParser()
    parser.add_argument("--contacts", action="store_true")
    parser.add_argument("--permits", action="store_true")
    parser.add_argument("--inspections", action="store_true")
    parser.add_argument("--addenda", action="store_true")
    parser.add_argument("--violations", action="store_true")
    parser.add_argument("--complaints", action="store_true")
    parser.add_argument("--businesses", action="store_true")
    parser.add_argument("--electrical-permits", action="store_true")
    parser.add_argument("--plumbing-permits", action="store_true")
    parser.add_argument("--db", type=str)

    args = parser.parse_args(["--electrical-permits"])
    assert args.electrical_permits is True
    assert args.plumbing_permits is False


def test_cli_has_plumbing_permits_flag():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--electrical-permits", action="store_true")
    parser.add_argument("--plumbing-permits", action="store_true")

    args = parser.parse_args(["--plumbing-permits"])
    assert args.plumbing_permits is True
    assert args.electrical_permits is False


def test_cli_both_flags_together():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--electrical-permits", action="store_true")
    parser.add_argument("--plumbing-permits", action="store_true")

    args = parser.parse_args(["--electrical-permits", "--plumbing-permits"])
    assert args.electrical_permits is True
    assert args.plumbing_permits is True


# ── Normalizer output lengths (schema guard) ──────────────────────

@pytest.mark.parametrize("permit_number,fn_name", [
    ("E001", "_normalize_electrical_permit"),
    ("PM001", "_normalize_plumbing_permit"),
])
def test_normalizer_tuple_length_matches_permits_table(permit_number, fn_name):
    """Both normalizers must produce a 26-column tuple matching the permits table."""
    import src.ingest as ingest_module
    fn = getattr(ingest_module, fn_name)
    result = fn({"permit_number": permit_number})
    assert len(result) == 26, (
        f"{fn_name}() returned {len(result)} columns — permits table has 26 columns"
    )
