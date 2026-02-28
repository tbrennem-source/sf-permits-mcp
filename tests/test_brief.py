"""Tests for morning brief dashboard — all 6 features + route."""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_brief.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    import web.brief as brief_mod
    monkeypatch.setattr(brief_mod, "BACKEND", "duckdb")
    # Init user schema (creates users, auth_tokens, watch_items, permit_changes)
    db_mod.init_user_schema()
    # Init main data schema (creates permits, inspections, contacts, entities)
    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
        # Create timeline_stats table (normally built from permits data)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS timeline_stats (
                permit_number TEXT,
                permit_type_definition TEXT,
                review_path TEXT,
                neighborhood TEXT,
                estimated_cost DOUBLE,
                revised_cost DOUBLE,
                cost_bracket TEXT,
                filed DATE,
                issued DATE,
                completed DATE,
                days_to_issuance INTEGER,
                days_to_completion INTEGER,
                supervisor_district TEXT
            )
        """)
    finally:
        conn.close()


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


def _login_user(client, email="brief@example.com"):
    """Helper: create user and magic-link session."""
    from web.auth import get_or_create_user, create_magic_token
    user = get_or_create_user(email)
    token = create_magic_token(user["user_id"])
    client.get(f"/auth/verify/{token}", follow_redirects=True)
    return user


def _seed_permit(conn, permit_number, **kwargs):
    """Insert a test permit row."""
    defaults = {
        "permit_type": "1",
        "permit_type_definition": "otc alterations permit",
        "status": "filed",
        "status_date": str(date.today()),
        "description": "Test permit",
        "filed_date": str(date.today() - timedelta(days=30)),
        "issued_date": None,
        "approved_date": None,
        "completed_date": None,
        "estimated_cost": 50000.0,
        "revised_cost": None,
        "existing_use": "1 family dwelling",
        "proposed_use": "1 family dwelling",
        "existing_units": 1,
        "proposed_units": 1,
        "street_number": "100",
        "street_name": "Main",
        "street_suffix": "St",
        "zipcode": "94105",
        "neighborhood": "Mission",
        "supervisor_district": "6",
        "block": "3512",
        "lot": "001",
        "adu": None,
        "data_as_of": str(date.today()),
    }
    defaults.update(kwargs)
    cols = ["permit_number"] + list(defaults.keys())
    vals = [permit_number] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO permits ({col_names}) VALUES ({placeholders})", vals)


def _seed_change(conn, permit_number, change_date, new_status, **kwargs):
    """Insert a test permit_changes row."""
    defaults = {
        "old_status": None,
        "old_status_date": None,
        "new_status_date": str(change_date),
        "change_type": "status_change",
        "is_new_permit": False,
        "source": "nightly",
        "permit_type": "otc alterations permit",
        "street_number": "100",
        "street_name": "Main",
        "neighborhood": "Mission",
        "block": "3512",
        "lot": "001",
    }
    defaults.update(kwargs)
    # Generate change_id
    result = conn.execute("SELECT COALESCE(MAX(change_id), 0) + 1 FROM permit_changes").fetchone()
    change_id = result[0]
    cols = ["change_id", "permit_number", "change_date", "new_status"] + list(defaults.keys())
    vals = [change_id, permit_number, change_date, new_status] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO permit_changes ({col_names}) VALUES ({placeholders})", vals)


def _seed_inspection(conn, reference_number, scheduled_date, result, **kwargs):
    """Insert a test inspection row."""
    defaults = {
        "reference_number_type": "permit",
        "inspector": "Smith J",
        "inspection_description": "Plumbing rough",
        "block": "3512",
        "lot": "001",
        "street_number": "100",
        "street_name": "Main",
        "street_suffix": "St",
        "neighborhood": "Mission",
        "supervisor_district": "6",
        "zipcode": "94105",
        "data_as_of": str(date.today()),
    }
    defaults.update(kwargs)
    result_row = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM inspections").fetchone()
    insp_id = result_row[0]
    cols = ["id", "reference_number", "scheduled_date", "result"] + list(defaults.keys())
    vals = [insp_id, reference_number, str(scheduled_date), result] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO inspections ({col_names}) VALUES ({placeholders})", vals)


def _seed_timeline_stats(conn, permit_number, days_to_issuance, **kwargs):
    """Insert a test timeline_stats row."""
    defaults = {
        "permit_type_definition": "otc alterations permit",
        "review_path": "otc",
        "neighborhood": "Mission",
        "estimated_cost": 50000.0,
        "revised_cost": None,
        "cost_bracket": "50k_150k",
        "filed": str(date.today() - timedelta(days=days_to_issuance + 30)),
        "issued": str(date.today() - timedelta(days=30)),
        "completed": None,
        "days_to_completion": None,
        "supervisor_district": "6",
    }
    defaults.update(kwargs)
    cols = ["permit_number", "days_to_issuance"] + list(defaults.keys())
    vals = [permit_number, days_to_issuance] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO timeline_stats ({col_names}) VALUES ({placeholders})", vals)


def _seed_entity(conn, entity_id, canonical_name, **kwargs):
    """Insert a test entity row."""
    defaults = {
        "canonical_firm": None,
        "entity_type": "person",
        "pts_agent_id": None,
        "license_number": None,
        "sf_business_license": None,
        "resolution_method": "exact",
        "resolution_confidence": "high",
        "contact_count": 5,
        "permit_count": 3,
        "source_datasets": "building_permits",
    }
    defaults.update(kwargs)
    cols = ["entity_id", "canonical_name"] + list(defaults.keys())
    vals = [entity_id, canonical_name] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO entities ({col_names}) VALUES ({placeholders})", vals)


def _seed_contact(conn, permit_number, entity_id, role="contractor", **kwargs):
    """Insert a test contact row."""
    defaults = {
        "source": "building_permits",
        "name": "Test Person",
        "first_name": "Test",
        "last_name": "Person",
        "firm_name": None,
        "pts_agent_id": None,
        "license_number": None,
        "sf_business_license": None,
        "phone": None,
        "address": None,
        "city": None,
        "state": None,
        "zipcode": None,
        "is_applicant": None,
        "from_date": None,
        "data_as_of": str(date.today()),
    }
    defaults.update(kwargs)
    result = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM contacts").fetchone()
    contact_id = result[0]
    cols = ["id", "permit_number", "entity_id", "role"] + list(defaults.keys())
    vals = [contact_id, permit_number, entity_id, role] + list(defaults.values())
    placeholders = ", ".join(["?"] * len(vals))
    col_names = ", ".join(cols)
    conn.execute(f"INSERT INTO contacts ({col_names}) VALUES ({placeholders})", vals)


# ---------------------------------------------------------------------------
# Brief route: access control
# ---------------------------------------------------------------------------

def test_brief_requires_login(client):
    rv = client.get("/brief", follow_redirects=False)
    assert rv.status_code == 302
    assert "/auth/login" in rv.headers["Location"]


def test_brief_loads_when_logged_in(client):
    _login_user(client)
    rv = client.get("/brief")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Good morning" in html


def test_brief_empty_watch_list(client):
    _login_user(client)
    rv = client.get("/brief")
    html = rv.data.decode()
    # With 0 watches, shows onboarding empty state (E5: updated text)
    assert "morning brief" in html.lower()
    assert "/search" in html


def test_brief_lookback_toggle(client):
    _login_user(client)
    rv = client.get("/brief?lookback=7")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "7 days lookback" in html


def test_brief_lookback_clamped(client):
    _login_user(client)
    # Over max
    rv = client.get("/brief?lookback=999")
    html = rv.data.decode()
    assert "90 days lookback" in html
    # Under min
    rv = client.get("/brief?lookback=0")
    html = rv.data.decode()
    assert "1 day lookback" in html


def test_brief_lookback_invalid_value(client):
    _login_user(client)
    rv = client.get("/brief?lookback=abc")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "1 day lookback" in html


# ---------------------------------------------------------------------------
# Section 1: What Changed — permit watches
# ---------------------------------------------------------------------------

def test_changes_for_permit_watch(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "202401010001")
        _seed_change(conn, "202401010001", date.today(), "approved",
                     old_status="filed")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="202401010001",
              label="My project")

    rv = client.get("/brief?lookback=1")
    html = rv.data.decode()
    assert "My project" in html or "202401010001" in html
    assert "approved" in html.lower()


def test_changes_for_address_watch(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "202401010002", date.today(), "issued",
                     old_status="approved",
                     street_number="200", street_name="Valencia")
    finally:
        conn.close()

    add_watch(user["user_id"], "address", street_number="200",
              street_name="Valencia", label="Valencia site")

    rv = client.get("/brief?lookback=1")
    html = rv.data.decode()
    assert "issued" in html.lower()


def test_changes_for_parcel_watch(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "202401010003", date.today(), "approved",
                     block="1234", lot="005")
    finally:
        conn.close()

    add_watch(user["user_id"], "parcel", block="1234", lot="005")

    rv = client.get("/brief?lookback=1")
    html = rv.data.decode()
    assert "approved" in html.lower()


def test_changes_for_neighborhood_watch(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "202401010004", date.today(), "filed",
                     neighborhood="Noe Valley")
    finally:
        conn.close()

    add_watch(user["user_id"], "neighborhood", neighborhood="Noe Valley")

    rv = client.get("/brief?lookback=1")
    html = rv.data.decode()
    assert "filed" in html.lower()


def test_changes_lookback_filtering(client):
    """Changes outside the lookback window should not appear."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # Change from 10 days ago — should NOT show with lookback=1
        _seed_change(conn, "202401010005", date.today() - timedelta(days=10),
                     "approved", old_status="filed")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="202401010005")

    rv = client.get("/brief?lookback=1")
    html = rv.data.decode()
    assert "No status changes" in html

    # But should appear with lookback=30
    rv = client.get("/brief?lookback=30")
    html = rv.data.decode()
    assert "202401010005" in html


def test_changes_deduplicated(client):
    """A permit matching multiple watches should appear only once."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "202401010006", date.today(), "approved",
                     old_status="filed", street_number="100",
                     street_name="Main", neighborhood="Mission")
    finally:
        conn.close()

    # Watch as both permit and address
    add_watch(user["user_id"], "permit", permit_number="202401010006")
    add_watch(user["user_id"], "address", street_number="100",
              street_name="Main")

    # Use the backend directly to check dedup
    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], lookback_days=1)
    permit_numbers = [c["permit_number"] for c in brief["changes"]]
    assert permit_numbers.count("202401010006") == 1


# ---------------------------------------------------------------------------
# Section 2: Permit Health / Predictability
# ---------------------------------------------------------------------------

def test_health_on_track(client):
    """A permit well within p50 should show as on_track."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # Permit filed 20 days ago
        _seed_permit(conn, "HEALTH001", status="filed",
                     filed_date=str(date.today() - timedelta(days=20)),
                     permit_type_definition="otc alterations permit",
                     neighborhood="Mission", estimated_cost=75000.0)
        # Seed enough timeline_stats for p50 calc (need >= 10 rows)
        for i in range(15):
            _seed_timeline_stats(conn, f"TS{i:04d}", days_to_issuance=60,
                                 review_path="otc", neighborhood="Mission",
                                 cost_bracket="50k_150k",
                                 permit_type_definition="otc alterations permit")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="HEALTH001",
              label="On Track Project")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["health"]) == 1
    assert brief["health"][0]["status"] == "on_track"
    assert brief["health"][0]["elapsed_days"] == 20


def test_health_at_risk(client):
    """A permit far past p90 should show as at_risk."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # Permit filed 200 days ago — way past typical
        _seed_permit(conn, "HEALTH002", status="filed",
                     filed_date=str(date.today() - timedelta(days=200)),
                     permit_type_definition="otc alterations permit",
                     neighborhood="Mission", estimated_cost=75000.0)
        for i in range(15):
            _seed_timeline_stats(conn, f"TSR{i:04d}", days_to_issuance=60,
                                 review_path="otc", neighborhood="Mission",
                                 cost_bracket="50k_150k",
                                 permit_type_definition="otc alterations permit")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="HEALTH002")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["health"]) == 1
    assert brief["health"][0]["status"] == "at_risk"


def test_health_excludes_completed(client):
    """Completed permits should not appear in health section."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "HEALTH003", status="completed",
                     filed_date=str(date.today() - timedelta(days=100)),
                     completed_date=str(date.today()))
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="HEALTH003")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["health"]) == 0


def test_health_sorts_worst_first(client):
    """Health items should be sorted: at_risk, behind, slower, on_track."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # One on track (filed 10 days ago), one at risk (filed 300 days ago)
        _seed_permit(conn, "SORT001", status="filed",
                     filed_date=str(date.today() - timedelta(days=10)),
                     permit_type_definition="otc alterations permit",
                     neighborhood="Mission", estimated_cost=75000.0)
        _seed_permit(conn, "SORT002", status="filed",
                     filed_date=str(date.today() - timedelta(days=300)),
                     permit_type_definition="otc alterations permit",
                     neighborhood="Mission", estimated_cost=75000.0)
        for i in range(15):
            _seed_timeline_stats(conn, f"TSS{i:04d}", days_to_issuance=60,
                                 review_path="otc", neighborhood="Mission",
                                 cost_bracket="50k_150k",
                                 permit_type_definition="otc alterations permit")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="SORT001")
    add_watch(user["user_id"], "permit", permit_number="SORT002")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["health"]) == 2
    # Worst (at_risk) should be first
    assert brief["health"][0]["permit_number"] == "SORT002"
    assert brief["health"][0]["status"] == "at_risk"
    assert brief["health"][1]["permit_number"] == "SORT001"
    assert brief["health"][1]["status"] == "on_track"


# ---------------------------------------------------------------------------
# Section 3: Inspection Results
# ---------------------------------------------------------------------------

def test_inspections_for_watched_permit(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "INSP001")
        _seed_inspection(conn, "INSP001", date.today(), "approved",
                         inspection_description="Electrical rough")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="INSP001")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["inspections"]) == 1
    assert brief["inspections"][0]["is_pass"] is True
    assert brief["inspections"][0]["description"] == "Electrical rough"


def test_inspection_fail_flagged(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "INSP002")
        _seed_inspection(conn, "INSP002", date.today(), "disapproved")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="INSP002")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["inspections"]) == 1
    assert brief["inspections"][0]["is_fail"] is True
    assert brief["inspections"][0]["is_pass"] is False


def test_inspections_excludes_unwatched(client):
    """Inspections on unwatched permits should not appear."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "INSP003")
        _seed_inspection(conn, "INSP003", date.today(), "approved")
        # Watch a different permit
        _seed_permit(conn, "INSP004")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="INSP004")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["inspections"]) == 0


def test_inspections_lookback_filtering(client):
    """Old inspections should not appear with a short lookback."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "INSP005")
        _seed_inspection(conn, "INSP005",
                         date.today() - timedelta(days=15), "approved")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="INSP005")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], lookback_days=1)
    assert len(brief["inspections"]) == 0

    brief7 = get_morning_brief(user["user_id"], lookback_days=30)
    assert len(brief7["inspections"]) == 1


# ---------------------------------------------------------------------------
# Section 4: New Filings at watched locations
# ---------------------------------------------------------------------------

def test_new_filings_at_watched_address(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "NEW001", date.today(), "filed",
                     is_new_permit=True,
                     street_number="500", street_name="Folsom")
    finally:
        conn.close()

    add_watch(user["user_id"], "address", street_number="500",
              street_name="Folsom")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["new_filings"]) == 1
    assert brief["new_filings"][0]["permit_number"] == "NEW001"


def test_new_filings_at_watched_parcel(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "NEW002", date.today(), "filed",
                     is_new_permit=True,
                     block="9999", lot="010")
    finally:
        conn.close()

    add_watch(user["user_id"], "parcel", block="9999", lot="010")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["new_filings"]) == 1


def test_new_filings_at_watched_neighborhood(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "NEW003", date.today(), "filed",
                     is_new_permit=True,
                     neighborhood="Pacific Heights")
    finally:
        conn.close()

    add_watch(user["user_id"], "neighborhood",
              neighborhood="Pacific Heights")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["new_filings"]) == 1


def test_new_filings_excludes_status_changes(client):
    """Regular status changes (is_new_permit=FALSE) should not appear in new filings."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_change(conn, "NEW004", date.today(), "approved",
                     is_new_permit=False,
                     street_number="500", street_name="Folsom")
    finally:
        conn.close()

    add_watch(user["user_id"], "address", street_number="500",
              street_name="Folsom")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["new_filings"]) == 0


# ---------------------------------------------------------------------------
# Section 5: Team Activity
# ---------------------------------------------------------------------------

def test_team_activity_for_entity_watch(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_entity(conn, 99001, "John Builder")
        _seed_permit(conn, "TEAM001",
                     filed_date=str(date.today()),
                     status="filed")
        _seed_contact(conn, "TEAM001", 99001, role="contractor",
                      name="John Builder")
    finally:
        conn.close()

    add_watch(user["user_id"], "entity", entity_id=99001,
              label="John Builder")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["team_activity"]) == 1
    assert brief["team_activity"][0]["entity_name"] == "John Builder"
    assert brief["team_activity"][0]["role"] == "contractor"


def test_team_activity_lookback(client):
    """Entity permits outside lookback should not appear."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_entity(conn, 99002, "Old Builder")
        _seed_permit(conn, "TEAM002",
                     filed_date=str(date.today() - timedelta(days=60)),
                     status="filed")
        _seed_contact(conn, "TEAM002", 99002, role="contractor")
    finally:
        conn.close()

    add_watch(user["user_id"], "entity", entity_id=99002)

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], lookback_days=1)
    assert len(brief["team_activity"]) == 0

    brief30 = get_morning_brief(user["user_id"], lookback_days=30)
    # filed_date is 60 days ago, still outside 30 day window
    assert len(brief30["team_activity"]) == 0


# ---------------------------------------------------------------------------
# Section 6: Expiring Permits
# ---------------------------------------------------------------------------

def test_expiring_permit_flagged(client):
    """$50K permit issued 350 days ago (10 days left of 360-day limit) should be flagged."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "EXP001", status="issued",
                     issued_date=str(date.today() - timedelta(days=350)),
                     filed_date=str(date.today() - timedelta(days=380)),
                     completed_date=None,
                     estimated_cost=50000.0)
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EXP001")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["expiring"]) == 1
    assert brief["expiring"][0]["expires_in"] == 10
    assert brief["expiring"][0]["is_expired"] is False


def test_expired_permit_flagged(client):
    """$50K permit issued 380 days ago (expired 20 days past 360-day limit) should show as expired."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "EXP002", status="issued",
                     issued_date=str(date.today() - timedelta(days=380)),
                     filed_date=str(date.today() - timedelta(days=410)),
                     completed_date=None,
                     estimated_cost=50000.0)
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EXP002")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["expiring"]) == 1
    assert brief["expiring"][0]["is_expired"] is True
    assert brief["expiring"][0]["expires_in"] == -20


def test_expiring_not_flagged_when_far_out(client):
    """$50K permit issued 30 days ago (330 days left of 360-day limit) should NOT be flagged."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "EXP003", status="issued",
                     issued_date=str(date.today() - timedelta(days=30)),
                     filed_date=str(date.today() - timedelta(days=60)),
                     completed_date=None,
                     estimated_cost=50000.0)
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EXP003")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["expiring"]) == 0


def test_expiring_excludes_completed(client):
    """Completed permits should not appear in expiring section."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "EXP004", status="completed",
                     issued_date=str(date.today() - timedelta(days=350)),
                     filed_date=str(date.today() - timedelta(days=380)),
                     completed_date=str(date.today()),
                     estimated_cost=50000.0)
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EXP004")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["expiring"]) == 0


def test_expiring_sorts_soonest_first(client):
    """Expired permits first, then soonest-to-expire (Table B: $50K = 360-day limit)."""
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # 10 days left (issued 350 days ago, 360-day limit)
        _seed_permit(conn, "EXP005", status="issued",
                     issued_date=str(date.today() - timedelta(days=350)),
                     completed_date=None,
                     estimated_cost=50000.0)
        # Already expired (issued 370 days ago, 360-day limit → expired 10 days ago)
        _seed_permit(conn, "EXP006", status="issued",
                     issued_date=str(date.today() - timedelta(days=370)),
                     completed_date=None,
                     estimated_cost=50000.0)
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EXP005")
    add_watch(user["user_id"], "permit", permit_number="EXP006")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert len(brief["expiring"]) == 2
    # Expired first (most negative expires_in)
    assert brief["expiring"][0]["permit_number"] == "EXP006"
    assert brief["expiring"][0]["is_expired"] is True
    assert brief["expiring"][1]["permit_number"] == "EXP005"


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

def test_summary_counts(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "SUM001")
        _seed_change(conn, "SUM001", date.today(), "approved",
                     old_status="filed")
        _seed_inspection(conn, "SUM001", date.today(), "approved")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="SUM001")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert brief["summary"]["total_watches"] == 1
    assert brief["summary"]["changes_count"] == 1
    assert brief["summary"]["inspections_count"] == 1


def test_summary_at_risk_count(client):
    from src.db import get_connection
    from web.auth import add_watch
    user = _login_user(client)

    conn = get_connection()
    try:
        # A permit filed 300 days ago — should be at_risk
        _seed_permit(conn, "RISK001", status="filed",
                     filed_date=str(date.today() - timedelta(days=300)),
                     permit_type_definition="otc alterations permit",
                     neighborhood="Mission", estimated_cost=75000.0)
        for i in range(15):
            _seed_timeline_stats(conn, f"TSRISK{i:04d}", days_to_issuance=60,
                                 review_path="otc", neighborhood="Mission",
                                 cost_bracket="50k_150k",
                                 permit_type_definition="otc alterations permit")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="RISK001")

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"])
    assert brief["summary"]["at_risk_count"] >= 1


# ---------------------------------------------------------------------------
# Navigation link
# ---------------------------------------------------------------------------

def test_nav_shows_brief_link_for_logged_in(client):
    _login_user(client)
    rv = client.get("/")
    html = rv.data.decode()
    assert 'href="/brief"' in html


def test_nav_shows_brief_link_for_anonymous(client):
    """Landing page does not show brief link (premium feature)."""
    rv = client.get("/")
    html = rv.data.decode()
    # Anonymous users see landing page which doesn't have nav brief link
    assert "Building Permit Intelligence" in html


# ---------------------------------------------------------------------------
# Email delivery
# ---------------------------------------------------------------------------

def test_email_unsubscribe_token_roundtrip():
    """Unsubscribe token generation and verification."""
    from web.email_brief import generate_unsubscribe_token, verify_unsubscribe_token
    token = generate_unsubscribe_token(1, "test@example.com")
    assert verify_unsubscribe_token(1, "test@example.com", token) is True
    # Wrong email
    assert verify_unsubscribe_token(1, "other@example.com", token) is False
    # Wrong user_id
    assert verify_unsubscribe_token(2, "test@example.com", token) is False
    # Tampered token
    assert verify_unsubscribe_token(1, "test@example.com", "bad" + token[3:]) is False


def test_email_brief_render(client):
    """Email template renders without errors."""
    user = _login_user(client)
    from web.brief import get_morning_brief
    from web.email_brief import render_brief_email
    brief_data = get_morning_brief(user["user_id"], lookback_days=1)

    with app.app_context():
        html = render_brief_email(user, brief_data)
    assert "sfpermits" in html
    assert "Good Morning" in html
    assert "View Full Brief" in html
    assert "Unsubscribe" in html


def test_email_brief_render_with_data(client):
    """Email template renders correctly with actual brief data."""
    from src.db import get_connection
    from web.auth import add_watch
    from web.brief import get_morning_brief
    from web.email_brief import render_brief_email
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "EMAIL001")
        _seed_change(conn, "EMAIL001", date.today(), "approved",
                     old_status="filed")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EMAIL001",
              label="My email test")
    brief_data = get_morning_brief(user["user_id"], lookback_days=1)

    with app.app_context():
        html = render_brief_email(user, brief_data)
    assert "What Changed" in html
    assert "EMAIL001" in html or "My email test" in html


def test_send_brief_skips_empty(client, monkeypatch):
    """send_briefs skips users with nothing to report."""
    from src.db import execute_write
    user = _login_user(client, email="daily@example.com")

    # Set frequency to daily
    execute_write(
        "UPDATE users SET brief_frequency = %s WHERE user_id = %s",
        ("daily", user["user_id"]),
    )

    # No watches, so nothing to report — user won't even be fetched
    # (the query requires EXISTS watch_items)
    from web.email_brief import send_briefs
    with app.app_context():
        result = send_briefs("daily")
    assert result["total"] == 0
    assert result["sent"] == 0


def test_send_brief_with_watch(client, monkeypatch):
    """send_briefs sends to a user with an active watch and changes."""
    from src.db import get_connection, execute_write
    from web.auth import add_watch
    user = _login_user(client, email="watchmail@example.com")

    # Set frequency to daily
    execute_write(
        "UPDATE users SET brief_frequency = %s WHERE user_id = %s",
        ("daily", user["user_id"]),
    )

    conn = get_connection()
    try:
        _seed_permit(conn, "EMAILSEND001")
        _seed_change(conn, "EMAILSEND001", date.today(), "approved",
                     old_status="filed")
    finally:
        conn.close()

    add_watch(user["user_id"], "permit", permit_number="EMAILSEND001",
              label="Brief test")

    # Mock SMTP — no actual email
    sent_emails = []
    monkeypatch.setattr("web.email_brief.SMTP_HOST", None)

    from web.email_brief import send_briefs
    with app.app_context():
        result = send_briefs("daily")
    assert result["total"] == 1
    assert result["sent"] == 1
    assert result["skipped"] == 0


def test_brief_frequency_update(client):
    """User can update their brief email frequency."""
    user = _login_user(client)

    rv = client.post("/account/brief-frequency", data={"brief_frequency": "daily"})
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Daily" in html

    # Verify it persisted
    from web.auth import get_user_by_id
    updated = get_user_by_id(user["user_id"])
    assert updated["brief_frequency"] == "daily"


def test_brief_frequency_requires_login(client):
    """Updating brief frequency requires authentication."""
    rv = client.post("/account/brief-frequency",
                     data={"brief_frequency": "daily"},
                     follow_redirects=False)
    assert rv.status_code == 302


def test_brief_frequency_invalid_value(client):
    """Invalid frequency values default to 'none'."""
    user = _login_user(client)

    rv = client.post("/account/brief-frequency",
                     data={"brief_frequency": "hourly"})
    assert rv.status_code == 200

    from web.auth import get_user_by_id
    updated = get_user_by_id(user["user_id"])
    assert updated["brief_frequency"] == "none"


def test_email_unsubscribe_route(client):
    """Unsubscribe endpoint with valid token."""
    from web.email_brief import generate_unsubscribe_token
    from src.db import execute_write
    user = _login_user(client, email="unsub@example.com")

    # Enable daily
    execute_write(
        "UPDATE users SET brief_frequency = %s WHERE user_id = %s",
        ("daily", user["user_id"]),
    )

    token = generate_unsubscribe_token(user["user_id"], "unsub@example.com")
    rv = client.get(f"/email/unsubscribe?uid={user['user_id']}&token={token}")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "unsubscribed" in html.lower()

    # Verify frequency changed to none
    from web.auth import get_user_by_id
    updated = get_user_by_id(user["user_id"])
    assert updated["brief_frequency"] == "none"


def test_email_unsubscribe_bad_token(client):
    """Unsubscribe endpoint rejects bad tokens."""
    user = _login_user(client, email="badsub@example.com")
    rv = client.get(f"/email/unsubscribe?uid={user['user_id']}&token=badtoken")
    assert rv.status_code == 400


def test_cron_send_briefs_blocked_on_web_worker(client):
    """Cron send-briefs endpoint blocked on web workers by cron guard."""
    rv = client.post("/cron/send-briefs")
    assert rv.status_code == 404  # Cron guard blocks POST /cron/* on web workers


def test_cron_send_briefs_with_auth(client, monkeypatch):
    """Cron send-briefs endpoint works with correct bearer token on cron worker."""
    monkeypatch.setenv("CRON_WORKER", "true")
    monkeypatch.setenv("CRON_SECRET", "test-secret")

    rv = client.post(
        "/cron/send-briefs",
        headers={"Authorization": "Bearer test-secret"},
    )
    assert rv.status_code == 200
    import json
    data = json.loads(rv.data)
    assert data["status"] == "ok"


def test_account_shows_email_preferences(client):
    """Account page shows email preferences section."""
    user = _login_user(client)
    rv = client.get("/account")
    html = rv.data.decode()
    assert "Email Preferences" in html
    assert "brief_frequency" in html


# ---------------------------------------------------------------------------
# Section 7: Property Synopsis
# ---------------------------------------------------------------------------

def test_property_synopsis_with_permits(client):
    """Property synopsis shows permit summary for primary address."""
    from src.db import get_connection
    user = _login_user(client)

    conn = get_connection()
    try:
        _seed_permit(conn, "PROP001", street_number="75", street_name="ROBIN HOOD",
                     street_suffix="DR", status="complete", neighborhood="West of Twin Peaks",
                     block="2800", lot="010", filed_date="2020-03-15",
                     permit_type_definition="otc alterations permit")
        _seed_permit(conn, "PROP002", street_number="75", street_name="ROBIN HOOD",
                     street_suffix="DR", status="issued", neighborhood="West of Twin Peaks",
                     block="2800", lot="010", filed_date="2024-06-01",
                     permit_type_definition="additions alterations or repairs")
    finally:
        conn.close()

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], primary_address={
        "street_number": "75", "street_name": "Robin Hood Dr",
    })

    ps = brief["property_synopsis"]
    assert ps is not None
    assert ps["total_permits"] == 2
    assert ps["active_count"] == 1  # issued is active
    assert ps["neighborhood"] == "West of Twin Peaks"
    assert ps["block"] == "2800"
    assert ps["lot"] == "010"
    assert len(ps["top_types"]) >= 1
    assert ps["latest_permit"]["permit_number"] == "PROP002"


def test_property_synopsis_none_when_no_permits(client):
    """Property synopsis is None when no permits exist at address."""
    user = _login_user(client)

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], primary_address={
        "street_number": "999", "street_name": "Nonexistent Blvd",
    })
    assert brief["property_synopsis"] is None


def test_property_synopsis_none_when_no_primary_address(client):
    """No primary address means no property synopsis."""
    user = _login_user(client)

    from web.brief import get_morning_brief
    brief = get_morning_brief(user["user_id"], primary_address=None)
    assert brief["property_synopsis"] is None


def test_brief_route_shows_property_synopsis(client):
    """Brief page shows property synopsis section when primary address is set."""
    from src.db import get_connection
    from web.auth import set_primary_address
    user = _login_user(client)

    set_primary_address(user["user_id"], "75", "Robin Hood Dr")

    conn = get_connection()
    try:
        _seed_permit(conn, "BRIEFPROP001", street_number="75",
                     street_name="ROBIN HOOD", street_suffix="DR",
                     status="complete", neighborhood="West of Twin Peaks")
    finally:
        conn.close()

    rv = client.get("/brief")
    assert rv.status_code == 200
    html = rv.data.decode()
    assert "Your Property" in html
    assert "Robin Hood" in html
    assert "Total Permits" in html


def test_brief_route_shows_address_in_subtitle(client):
    """Brief subtitle shows the monitored address."""
    from web.auth import set_primary_address
    from src.db import get_connection
    user = _login_user(client)

    set_primary_address(user["user_id"], "614", "6th Ave")

    conn = get_connection()
    try:
        _seed_permit(conn, "SUBTITLE001", street_number="614",
                     street_name="6TH", street_suffix="AVE",
                     status="filed")
    finally:
        conn.close()

    rv = client.get("/brief")
    html = rv.data.decode()
    assert "Monitoring" in html
    assert "614" in html
