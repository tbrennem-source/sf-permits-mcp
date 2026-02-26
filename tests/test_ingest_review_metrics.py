"""Tests for Sprint 56F — DBI issuance/review metrics + planning review metrics ingest."""

import pytest

import src.db as db_mod
from src.ingest import (
    _normalize_permit_issuance_metric,
    _normalize_permit_review_metric,
    _normalize_planning_review_metric,
    ingest_permit_issuance_metrics,
    ingest_permit_review_metrics,
    ingest_planning_review_metrics,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_review_metrics.duckdb")
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
    """Flask test client with CRON_SECRET set."""
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()
    monkeypatch.setenv("CRON_SECRET", "testsecret")
    monkeypatch.setenv("CRON_WORKER", "1")

    from web.app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── Sample SODA records ───────────────────────────────────────────

SAMPLE_ISSUANCE = {
    "bpa": "202210244955",
    "addenda": "0",
    "bpa_addenda": "202210244955-0",
    "permit_type": "8",
    "otc_ih": "OTC",
    "status": "issued",
    "block": "6461",
    "lot": "003",
    "street_number": "42",
    "street_name": "Allison",
    "street_suffix": "St",
    "unit": None,
    "description": "re-roofing: remove and replace roofing material",
    "fire_only_permit": None,
    "filed_date": "2022-10-24T07:58:12.000",
    "issued_date": "2022-10-24T07:58:41.000",
    "issued_status": "Issued",
    "issued_year": "2022",
    "calendar_days": "1",
    "business_days": "0",
    "data_as_of": "2026-02-25T01:05:02.000",
}

SAMPLE_ISSUANCE_FIRE = {
    "bpa": "202309076037",
    "addenda": "0",
    "bpa_addenda": "202309076037-0",
    "permit_type": "8",
    "otc_ih": "OTC",
    "status": "issued",
    "block": "0313",
    "lot": "018",
    "street_number": "150",
    "street_name": "Stockton",
    "street_suffix": "St",
    "unit": "0",
    "description": "relocate fire sprinklers",
    "fire_only_permit": True,
    "filed_date": "2023-09-07T07:46:06.000",
    "issued_date": "2023-09-07T08:09:41.000",
    "issued_status": "Issued",
    "issued_year": "2023",
    "calendar_days": "1",
    "business_days": "0",
    "data_as_of": "2026-02-25T01:05:02.000",
}

SAMPLE_REVIEW = {
    "primary_key": "3363332",
    "bpa": "202003126926",
    "addenda": "0",
    "bpa_addenda": "202003126926-0",
    "permit_type": "3",
    "block": "0666",
    "lot": "006",
    "street_number": "1522",
    "street_name": "Bush",
    "street_suffix": "St",
    "description": "new fire alarm system",
    "fire_only_permit": "Y",
    "filed_date": "2020-03-12T14:00:52.000",
    "status": "cancelled",
    "department": "SFFD",
    "station": "SFFD",
    "review_type": "First Review",
    "review_number": "1",
    "review_results": None,
    "arrive_date": "2020-03-13T13:01:53.000",
    "start_year": "2020",
    "start_date": "2020-03-12T14:00:52.000",
    "start_date_source": "FILED_DATE",
    "sla_days": "30",
    "due_date": "2020-04-11T14:00:52.000",
    "finish_date": None,
    "calendar_days": None,
    "met_cal_sla": False,
    "data_as_of": "2026-02-25T01:05:02.000",
}

SAMPLE_REVIEW_WITH_FINISH = {
    "primary_key": "3668204",
    "bpa": "202003126924",
    "addenda": "0",
    "bpa_addenda": "202003126924-0",
    "permit_type": "3",
    "block": "2164",
    "lot": "027A",
    "street_number": "2016",
    "street_name": "45th",
    "street_suffix": "Av",
    "description": "to comply w/ nov",
    "fire_only_permit": None,
    "filed_date": "2020-03-12T13:55:45.000",
    "status": "issued",
    "department": "DPW",
    "station": "DPW-BUF",
    "review_type": "First Review",
    "review_number": "1",
    "review_results": "Issued Comments",
    "arrive_date": "2023-04-27T00:00:00.000",
    "start_year": "2020",
    "start_date": "2020-03-12T13:55:45.000",
    "start_date_source": "FILED_DATE",
    "sla_days": "30",
    "due_date": "2020-04-11T13:55:45.000",
    "finish_date": "2024-05-29T00:00:00.000",
    "calendar_days": "1539.0",
    "met_cal_sla": False,
    "data_as_of": "2026-02-25T01:05:02.000",
}

SAMPLE_PLANNING = {
    "b1_alt_id": "2017-016432PRJ",
    "project_stage": "resubmission review",
    "observation_window_type": "first_submitted_date",
    "observation_window_date": "2024-04-01T00:00:00.000",
    "start_event_type": "Plan Revision Received",
    "start_event_date": "2024-06-14T00:00:00.000",
    "end_event_type": "Plan Check Letter Issued",
    "end_event_date": "2024-07-09T00:00:00.000",
    "metric_value": "25.0",
    "sla_value": "14.0",
    "metric_outcome": "Over Deadline",
    "data_as_of": "2024-07-03T12:13:31.823",
}

SAMPLE_PLANNING_UNDER = {
    "b1_alt_id": "2024-005514PRJ",
    "project_stage": "completeness check",
    "observation_window_type": "first_submitted_date",
    "observation_window_date": "2024-06-14T00:00:00.000",
    "start_event_type": "Completeness Check Start Date",
    "start_event_date": "2024-06-14T00:00:00.000",
    "end_event_type": "Incompleteness Letter Issued",
    "end_event_date": "2024-06-27T00:00:00.000",
    "metric_value": "13.0",
    "sla_value": "21.0",
    "metric_outcome": "Under Deadline",
    "data_as_of": "2024-08-01T13:15:59.430",
}


# ── Fake SODA client ─────────────────────────────────────────────


class _FakeClient:
    """Fake SODA client returning canned data."""

    def __init__(self, data=None, data_map=None):
        self._data = data or []
        self._data_map = data_map or {}

    async def count(self, endpoint_id, where=None):
        records = self._data_map.get(endpoint_id, self._data)
        return len(records)

    async def query(self, endpoint_id, where=None, limit=None, offset=None, order=None):
        records = self._data_map.get(endpoint_id, self._data)
        offset = offset or 0
        if limit:
            return records[offset:offset + limit]
        return records[offset:]

    async def close(self):
        pass


# ── Table creation tests ─────────────────────────────────────────


class TestTableCreation:
    def test_permit_issuance_metrics_table_exists(self):
        conn = db_mod.get_connection()
        try:
            rows = conn.execute("SELECT COUNT(*) FROM permit_issuance_metrics").fetchone()
            assert rows[0] == 0
        finally:
            conn.close()

    def test_permit_review_metrics_table_exists(self):
        conn = db_mod.get_connection()
        try:
            rows = conn.execute("SELECT COUNT(*) FROM permit_review_metrics").fetchone()
            assert rows[0] == 0
        finally:
            conn.close()

    def test_planning_review_metrics_table_exists(self):
        conn = db_mod.get_connection()
        try:
            rows = conn.execute("SELECT COUNT(*) FROM planning_review_metrics").fetchone()
            assert rows[0] == 0
        finally:
            conn.close()

    def test_permit_issuance_metrics_schema(self):
        conn = db_mod.get_connection()
        try:
            # Verify key columns exist by inserting a minimal record (id required in DuckDB)
            conn.execute(
                "INSERT INTO permit_issuance_metrics (id, bpa, otc_ih, status, issued_year) VALUES (?, ?, ?, ?, ?)",
                [1, "TEST-001", "OTC", "issued", "2024"],
            )
            row = conn.execute(
                "SELECT bpa, otc_ih, status, issued_year FROM permit_issuance_metrics"
            ).fetchone()
            assert row == ("TEST-001", "OTC", "issued", "2024")
        finally:
            conn.close()

    def test_permit_review_metrics_schema(self):
        conn = db_mod.get_connection()
        try:
            conn.execute(
                "INSERT INTO permit_review_metrics (id, bpa, station, department, met_cal_sla) VALUES (?, ?, ?, ?, ?)",
                [1, "TEST-002", "BLDG", "DBI", False],
            )
            row = conn.execute(
                "SELECT bpa, station, department, met_cal_sla FROM permit_review_metrics"
            ).fetchone()
            assert row == ("TEST-002", "BLDG", "DBI", False)
        finally:
            conn.close()

    def test_planning_review_metrics_schema(self):
        conn = db_mod.get_connection()
        try:
            conn.execute(
                "INSERT INTO planning_review_metrics (id, b1_alt_id, project_stage, metric_outcome) VALUES (?, ?, ?, ?)",
                [1, "2024-001PRJ", "completeness check", "Under Deadline"],
            )
            row = conn.execute(
                "SELECT b1_alt_id, project_stage, metric_outcome FROM planning_review_metrics"
            ).fetchone()
            assert row == ("2024-001PRJ", "completeness check", "Under Deadline")
        finally:
            conn.close()


# ── Normalize: permit_issuance_metrics ──────────────────────────


class TestNormalizePermitIssuanceMetric:
    def test_basic_fields(self):
        result = _normalize_permit_issuance_metric(SAMPLE_ISSUANCE)
        assert result["bpa"] == "202210244955"
        assert result["addenda_number"] == 0
        assert result["bpa_addenda"] == "202210244955-0"
        assert result["permit_type"] == "8"
        assert result["otc_ih"] == "OTC"
        assert result["status"] == "issued"
        assert result["block"] == "6461"
        assert result["lot"] == "003"
        assert result["street_number"] == "42"
        assert result["street_name"] == "Allison"
        assert result["issued_year"] == "2022"
        assert result["calendar_days"] == 1
        assert result["business_days"] == 0

    def test_fire_only_permit_bool(self):
        result = _normalize_permit_issuance_metric(SAMPLE_ISSUANCE_FIRE)
        assert result["fire_only_permit"] is True

    def test_fire_only_permit_none(self):
        result = _normalize_permit_issuance_metric(SAMPLE_ISSUANCE)
        assert result["fire_only_permit"] is None

    def test_empty_record(self):
        result = _normalize_permit_issuance_metric({})
        assert result["bpa"] is None
        assert result["addenda_number"] is None
        assert result["calendar_days"] is None
        assert result["business_days"] is None
        assert result["otc_ih"] is None

    def test_invalid_calendar_days(self):
        record = dict(SAMPLE_ISSUANCE, calendar_days="N/A")
        result = _normalize_permit_issuance_metric(record)
        assert result["calendar_days"] is None

    def test_fire_only_permit_string_true(self):
        record = dict(SAMPLE_ISSUANCE, fire_only_permit="true")
        result = _normalize_permit_issuance_metric(record)
        assert result["fire_only_permit"] is True

    def test_fire_only_permit_string_false(self):
        record = dict(SAMPLE_ISSUANCE, fire_only_permit="false")
        result = _normalize_permit_issuance_metric(record)
        assert result["fire_only_permit"] is False


# ── Normalize: permit_review_metrics ────────────────────────────


class TestNormalizePermitReviewMetric:
    def test_basic_fields(self):
        result = _normalize_permit_review_metric(SAMPLE_REVIEW)
        assert result["primary_key"] == "3363332"
        assert result["bpa"] == "202003126926"
        assert result["addenda_number"] == 0
        assert result["permit_type"] == "3"
        assert result["department"] == "SFFD"
        assert result["station"] == "SFFD"
        assert result["review_type"] == "First Review"
        assert result["review_number"] == 1
        assert result["sla_days"] == 30
        assert result["met_cal_sla"] is False

    def test_with_finish_date_and_calendar_days(self):
        result = _normalize_permit_review_metric(SAMPLE_REVIEW_WITH_FINISH)
        assert result["finish_date"] == "2024-05-29T00:00:00.000"
        assert result["calendar_days"] == 1539.0
        assert result["review_results"] == "Issued Comments"

    def test_null_finish_date(self):
        result = _normalize_permit_review_metric(SAMPLE_REVIEW)
        assert result["finish_date"] is None
        assert result["calendar_days"] is None

    def test_empty_record(self):
        result = _normalize_permit_review_metric({})
        assert result["primary_key"] is None
        assert result["bpa"] is None
        assert result["sla_days"] is None
        assert result["calendar_days"] is None
        assert result["met_cal_sla"] is None

    def test_invalid_review_number(self):
        record = dict(SAMPLE_REVIEW, review_number="N/A")
        result = _normalize_permit_review_metric(record)
        assert result["review_number"] is None

    def test_met_cal_sla_true(self):
        record = dict(SAMPLE_REVIEW, met_cal_sla=True)
        result = _normalize_permit_review_metric(record)
        assert result["met_cal_sla"] is True

    def test_met_cal_sla_string(self):
        record = dict(SAMPLE_REVIEW, met_cal_sla="true")
        result = _normalize_permit_review_metric(record)
        assert result["met_cal_sla"] is True


# ── Normalize: planning_review_metrics ──────────────────────────


class TestNormalizePlanningReviewMetric:
    def test_basic_fields_over_deadline(self):
        result = _normalize_planning_review_metric(SAMPLE_PLANNING)
        assert result["b1_alt_id"] == "2017-016432PRJ"
        assert result["project_stage"] == "resubmission review"
        assert result["observation_window_type"] == "first_submitted_date"
        assert result["start_event_type"] == "Plan Revision Received"
        assert result["end_event_type"] == "Plan Check Letter Issued"
        assert result["metric_value"] == 25.0
        assert result["sla_value"] == 14.0
        assert result["metric_outcome"] == "Over Deadline"

    def test_under_deadline(self):
        result = _normalize_planning_review_metric(SAMPLE_PLANNING_UNDER)
        assert result["b1_alt_id"] == "2024-005514PRJ"
        assert result["project_stage"] == "completeness check"
        assert result["metric_value"] == 13.0
        assert result["sla_value"] == 21.0
        assert result["metric_outcome"] == "Under Deadline"

    def test_empty_record(self):
        result = _normalize_planning_review_metric({})
        assert result["b1_alt_id"] is None
        assert result["metric_value"] is None
        assert result["sla_value"] is None
        assert result["metric_outcome"] is None

    def test_invalid_metric_value(self):
        record = dict(SAMPLE_PLANNING, metric_value="N/A")
        result = _normalize_planning_review_metric(record)
        assert result["metric_value"] is None

    def test_string_metric_value(self):
        record = dict(SAMPLE_PLANNING, metric_value="30.5")
        result = _normalize_planning_review_metric(record)
        assert result["metric_value"] == 30.5


# ── Ingest function tests ────────────────────────────────────────


@pytest.mark.asyncio
async def test_ingest_permit_issuance_metrics_basic():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_ISSUANCE, SAMPLE_ISSUANCE_FIRE])
    count = await ingest_permit_issuance_metrics(conn, client)
    assert count == 2
    rows = conn.execute("SELECT bpa FROM permit_issuance_metrics ORDER BY bpa").fetchall()
    assert [r[0] for r in rows] == ["202210244955", "202309076037"]
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_issuance_metrics_empty():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([])
    count = await ingest_permit_issuance_metrics(conn, client)
    assert count == 0
    rows = conn.execute("SELECT COUNT(*) FROM permit_issuance_metrics").fetchone()
    assert rows[0] == 0
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_issuance_metrics_clears_old_data():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    # Insert pre-existing data
    conn.execute(
        "INSERT INTO permit_issuance_metrics (id, bpa, status) VALUES (?, ?, ?)",
        [999, "OLD-BPA", "issued"],
    )
    client = _FakeClient([SAMPLE_ISSUANCE])
    count = await ingest_permit_issuance_metrics(conn, client)
    assert count == 1
    rows = conn.execute("SELECT bpa FROM permit_issuance_metrics").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "202210244955"
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_issuance_metrics_ingest_log():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_ISSUANCE])
    await ingest_permit_issuance_metrics(conn, client)
    log = conn.execute("SELECT dataset_id FROM ingest_log WHERE dataset_id = 'gzxm-jz5j'").fetchone()
    assert log is not None
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_review_metrics_basic():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_REVIEW, SAMPLE_REVIEW_WITH_FINISH])
    count = await ingest_permit_review_metrics(conn, client)
    assert count == 2
    rows = conn.execute("SELECT bpa FROM permit_review_metrics ORDER BY bpa").fetchall()
    assert [r[0] for r in rows] == ["202003126924", "202003126926"]
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_review_metrics_empty():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([])
    count = await ingest_permit_review_metrics(conn, client)
    assert count == 0
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_review_metrics_clears_old_data():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    conn.execute(
        "INSERT INTO permit_review_metrics (id, bpa, station) VALUES (?, ?, ?)",
        [999, "OLD-BPA", "BLDG"],
    )
    client = _FakeClient([SAMPLE_REVIEW])
    count = await ingest_permit_review_metrics(conn, client)
    assert count == 1
    rows = conn.execute("SELECT bpa FROM permit_review_metrics").fetchall()
    assert len(rows) == 1
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_review_metrics_ingest_log():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_REVIEW])
    await ingest_permit_review_metrics(conn, client)
    log = conn.execute("SELECT dataset_id FROM ingest_log WHERE dataset_id = '5bat-azvb'").fetchone()
    assert log is not None
    conn.close()


@pytest.mark.asyncio
async def test_ingest_permit_review_metrics_met_sla_stored():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    record = dict(SAMPLE_REVIEW, met_cal_sla=False)
    client = _FakeClient([record])
    await ingest_permit_review_metrics(conn, client)
    row = conn.execute("SELECT met_cal_sla FROM permit_review_metrics").fetchone()
    assert row[0] is False
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_basic():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_PLANNING, SAMPLE_PLANNING_UNDER])
    count = await ingest_planning_review_metrics(conn, client)
    assert count == 2
    rows = conn.execute("SELECT b1_alt_id FROM planning_review_metrics ORDER BY b1_alt_id").fetchall()
    assert [r[0] for r in rows] == ["2017-016432PRJ", "2024-005514PRJ"]
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_empty():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([])
    count = await ingest_planning_review_metrics(conn, client)
    assert count == 0
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_clears_old_data():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    conn.execute(
        "INSERT INTO planning_review_metrics (id, b1_alt_id, project_stage) VALUES (?, ?, ?)",
        [999, "OLD-PRJ", "initial review"],
    )
    client = _FakeClient([SAMPLE_PLANNING])
    count = await ingest_planning_review_metrics(conn, client)
    assert count == 1
    rows = conn.execute("SELECT b1_alt_id FROM planning_review_metrics").fetchall()
    assert len(rows) == 1
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_ingest_log():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_PLANNING])
    await ingest_planning_review_metrics(conn, client)
    log = conn.execute("SELECT dataset_id FROM ingest_log WHERE dataset_id = 'd4jk-jw33'").fetchone()
    assert log is not None
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_numeric_values():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_PLANNING])
    await ingest_planning_review_metrics(conn, client)
    row = conn.execute("SELECT metric_value, sla_value FROM planning_review_metrics").fetchone()
    assert row[0] == 25.0
    assert row[1] == 14.0
    conn.close()


@pytest.mark.asyncio
async def test_ingest_planning_review_metrics_outcome_stored():
    conn = db_mod.get_connection()
    db_mod.init_schema(conn)
    client = _FakeClient([SAMPLE_PLANNING_UNDER])
    await ingest_planning_review_metrics(conn, client)
    row = conn.execute("SELECT metric_outcome, project_stage FROM planning_review_metrics").fetchone()
    assert row[0] == "Under Deadline"
    assert row[1] == "completeness check"
    conn.close()


# ── Cron endpoint tests ──────────────────────────────────────────


class TestCronEndpointAuth:
    def test_ingest_issuance_metrics_403_no_auth(self, client):
        resp = client.post("/cron/ingest-permit-issuance-metrics")
        assert resp.status_code == 403

    def test_ingest_issuance_metrics_403_wrong_token(self, client):
        resp = client.post(
            "/cron/ingest-permit-issuance-metrics",
            headers={"Authorization": "Bearer wrongsecret"},
        )
        assert resp.status_code == 403

    def test_ingest_review_metrics_403_no_auth(self, client):
        resp = client.post("/cron/ingest-permit-review-metrics")
        assert resp.status_code == 403

    def test_ingest_review_metrics_403_wrong_token(self, client):
        resp = client.post(
            "/cron/ingest-permit-review-metrics",
            headers={"Authorization": "Bearer wrongsecret"},
        )
        assert resp.status_code == 403

    def test_ingest_planning_metrics_403_no_auth(self, client):
        resp = client.post("/cron/ingest-planning-review-metrics")
        assert resp.status_code == 403

    def test_ingest_planning_metrics_403_wrong_token(self, client):
        resp = client.post(
            "/cron/ingest-planning-review-metrics",
            headers={"Authorization": "Bearer wrongsecret"},
        )
        assert resp.status_code == 403


class TestCronEndpointSuccess:
    def _auth_headers(self):
        return {"Authorization": "Bearer testsecret"}

    def test_ingest_issuance_metrics_200(self, client, monkeypatch):
        """Cron endpoint returns 200 with valid auth (mocked ingest)."""
        async def _mock_ingest(conn, soda_client):
            return 5

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_issuance_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-permit-issuance-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["table"] == "permit_issuance_metrics"
        assert data["rows"] == 5

    def test_ingest_review_metrics_200(self, client, monkeypatch):
        """Cron endpoint returns 200 with valid auth (mocked ingest)."""
        async def _mock_ingest(conn, soda_client):
            return 10

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_review_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-permit-review-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["table"] == "permit_review_metrics"
        assert data["rows"] == 10

    def test_ingest_planning_metrics_200(self, client, monkeypatch):
        """Cron endpoint returns 200 with valid auth (mocked ingest)."""
        async def _mock_ingest(conn, soda_client):
            return 7

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_planning_review_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-planning-review-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["table"] == "planning_review_metrics"
        assert data["rows"] == 7

    def test_ingest_issuance_metrics_returns_elapsed(self, client, monkeypatch):
        """Cron endpoint includes elapsed_s in response."""
        async def _mock_ingest(conn, soda_client):
            return 3

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_issuance_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-permit-issuance-metrics",
            headers=self._auth_headers(),
        )
        data = resp.get_json()
        assert "elapsed_s" in data
        assert isinstance(data["elapsed_s"], (int, float))

    def test_ingest_review_metrics_returns_elapsed(self, client, monkeypatch):
        async def _mock_ingest(conn, soda_client):
            return 3

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_review_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-permit-review-metrics",
            headers=self._auth_headers(),
        )
        data = resp.get_json()
        assert "elapsed_s" in data

    def test_ingest_planning_metrics_returns_elapsed(self, client, monkeypatch):
        async def _mock_ingest(conn, soda_client):
            return 3

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_planning_review_metrics", _mock_ingest)

        resp = client.post(
            "/cron/ingest-planning-review-metrics",
            headers=self._auth_headers(),
        )
        data = resp.get_json()
        assert "elapsed_s" in data

    def test_ingest_issuance_metrics_error_returns_500(self, client, monkeypatch):
        """Cron endpoint returns 500 on ingest error."""
        async def _mock_ingest_error(conn, soda_client):
            raise RuntimeError("SODA timeout")

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_issuance_metrics", _mock_ingest_error)

        resp = client.post(
            "/cron/ingest-permit-issuance-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False
        assert "error" in data

    def test_ingest_review_metrics_error_returns_500(self, client, monkeypatch):
        async def _mock_ingest_error(conn, soda_client):
            raise RuntimeError("Network error")

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_permit_review_metrics", _mock_ingest_error)

        resp = client.post(
            "/cron/ingest-permit-review-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False

    def test_ingest_planning_metrics_error_returns_500(self, client, monkeypatch):
        async def _mock_ingest_error(conn, soda_client):
            raise RuntimeError("API error")

        import src.ingest as ingest_mod
        monkeypatch.setattr(ingest_mod, "ingest_planning_review_metrics", _mock_ingest_error)

        resp = client.post(
            "/cron/ingest-planning-review-metrics",
            headers=self._auth_headers(),
        )
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False


# ── DATASETS dict tests ──────────────────────────────────────────


class TestDatasetsDict:
    def test_permit_issuance_metrics_in_datasets(self):
        from src.ingest import DATASETS
        assert "permit_issuance_metrics" in DATASETS
        assert DATASETS["permit_issuance_metrics"]["endpoint_id"] == "gzxm-jz5j"

    def test_permit_review_metrics_in_datasets(self):
        from src.ingest import DATASETS
        assert "permit_review_metrics" in DATASETS
        assert DATASETS["permit_review_metrics"]["endpoint_id"] == "5bat-azvb"

    def test_planning_review_metrics_in_datasets(self):
        from src.ingest import DATASETS
        assert "planning_review_metrics" in DATASETS
        assert DATASETS["planning_review_metrics"]["endpoint_id"] == "d4jk-jw33"
