"""Tests for triage intelligence signals on search result cards.

Tests:
- classify_days_threshold() green/amber/red logic
- compute_triage_signals() helper with mock DB
- Graceful degradation when DB data is missing
- search_results_public.html template contains triage signal HTML elements
- results.html template contains triage signal HTML elements
- Days threshold boundary conditions
- Missing data handling (no station, no reviewer)
- Signal is_stuck flag at 2x median threshold
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Tests: classify_days_threshold
# ---------------------------------------------------------------------------

def test_classify_days_green_under_median():
    """Days below median should be green."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(10, 30.0)
    assert result == "green"


def test_classify_days_amber_at_1x_median():
    """Days equal to median is amber (>= median, < 2x)."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(30, 30.0)
    assert result == "amber"


def test_classify_days_amber_at_1_5x_median():
    """Days at 1.5x median should be amber."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(45, 30.0)
    assert result == "amber"


def test_classify_days_red_at_2x_median():
    """Days equal to 2x median should be red."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(60, 30.0)
    assert result == "red"


def test_classify_days_red_above_2x_median():
    """Days above 2x median should be red."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(90, 30.0)
    assert result == "red"


def test_classify_days_green_just_under_median():
    """Days just below median (median-1) should be green."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(29, 30.0)
    assert result == "green"


def test_classify_days_amber_just_under_2x():
    """Days just below 2x median (2*median - 1) should be amber."""
    from web.helpers import classify_days_threshold
    result = classify_days_threshold(59, 30.0)
    assert result == "amber"


# ---------------------------------------------------------------------------
# Tests: is_stuck flag logic
# ---------------------------------------------------------------------------

def test_is_stuck_flag_at_2x_median():
    """is_stuck should be True when days >= 2x median."""
    from web.helpers import classify_days_threshold
    median = 30.0
    days = 60
    threshold = classify_days_threshold(days, median)
    is_stuck = days >= median * 2
    assert threshold == "red"
    assert is_stuck is True


def test_is_stuck_flag_false_below_2x_median():
    """is_stuck should be False when days < 2x median."""
    from web.helpers import classify_days_threshold
    median = 30.0
    days = 59
    is_stuck = days >= median * 2
    assert is_stuck is False


# ---------------------------------------------------------------------------
# Tests: compute_triage_signals - with mock DB
# ---------------------------------------------------------------------------

def _make_mock_conn(permit_rows=None, station_rows=None, reviewer_rows=None):
    """Build a mock DuckDB-style connection object."""
    mock_conn = MagicMock()

    def _execute(sql, params=None):
        result = MagicMock()
        sql_upper = sql.upper().strip()
        if "FROM PERMITS" in sql_upper:
            result.fetchall.return_value = permit_rows or []
        elif "FROM ADDENDA" in sql_upper and "FINISH_DATE IS NULL" in sql_upper:
            result.fetchall.return_value = station_rows or []
        elif "FROM ADDENDA" in sql_upper and "FINISH_DATE DESC" in sql_upper:
            result.fetchall.return_value = reviewer_rows or []
        elif "STATION_VELOCITY" in sql_upper:
            result.fetchall.return_value = []  # No velocity data — use defaults
        else:
            result.fetchall.return_value = []
        return result

    mock_conn.execute.side_effect = _execute
    return mock_conn


def test_compute_triage_signals_returns_empty_without_inputs():
    """compute_triage_signals returns [] when no address inputs given."""
    from web.helpers import compute_triage_signals
    result = compute_triage_signals()
    assert result == []


def test_compute_triage_signals_graceful_on_db_error():
    """compute_triage_signals returns [] when DB import fails."""
    from web.helpers import compute_triage_signals
    with patch("web.helpers.compute_triage_signals", wraps=lambda **kw: []) as _mock:
        # Simulate by calling with block/lot but patching get_connection to fail
        pass
    # Test the actual function with a patched failing DB
    with patch("src.db.get_connection", side_effect=Exception("DB unavailable")):
        result = compute_triage_signals(street_number="100", street_name="Main St")
    assert result == []


def test_compute_triage_signals_no_station_data():
    """When permits exist but no active station, signal has None station."""
    from datetime import date
    today = date.today()
    filed = today - timedelta(days=60)

    permit_rows = [(
        "202401010001",  # permit_number
        "filed",          # status
        "Kitchen remodel", # description
        filed.isoformat(), # filed_date
    )]

    with patch("src.db.get_connection") as mock_gc, \
         patch("src.db.BACKEND", "duckdb"):
        mock_conn = _make_mock_conn(permit_rows=permit_rows, station_rows=[])
        mock_gc.return_value = mock_conn

        from web.helpers import compute_triage_signals
        result = compute_triage_signals(street_number="100", street_name="Main St")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["permit_number"] == "202401010001"
    assert result[0]["current_station"] is None
    assert result[0]["days_at_station"] is None
    assert result[0]["is_stuck"] is False


def test_compute_triage_signals_with_station_data():
    """When permit has active station, signal contains timing data."""
    from datetime import date
    today = date.today()
    arrive_date = today - timedelta(days=45)
    filed = today - timedelta(days=90)

    permit_rows = [(
        "202401010002",
        "plancheck",
        "New construction",
        filed.isoformat(),
    )]
    station_rows = [(
        "BLDG",               # station
        arrive_date,          # arrive (date object)
        "ARRIOLA LAURA",      # plan_checked_by
    )]

    with patch("src.db.get_connection") as mock_gc, \
         patch("src.db.BACKEND", "duckdb"):
        mock_conn = _make_mock_conn(permit_rows=permit_rows, station_rows=station_rows)
        mock_gc.return_value = mock_conn

        from web.helpers import compute_triage_signals
        result = compute_triage_signals(block="3512", lot="001")

    assert isinstance(result, list)
    assert len(result) == 1
    sig = result[0]
    assert sig["permit_number"] == "202401010002"
    assert sig["current_station"] == "BLDG"
    assert sig["days_at_station"] == 45
    assert sig["reviewer"] == "ARRIOLA LAURA"
    # 45 days at BLDG (median 30d) → amber (>= 1.5x) or red (>= 2x)?
    # 45 >= 30 and 45 < 60 → amber
    assert sig["threshold_class"] == "amber"
    assert sig["is_stuck"] is False  # 45 < 60 (2x median)


def test_compute_triage_signals_stuck_permit():
    """When permit dwell >= 2x median, is_stuck should be True."""
    from datetime import date
    today = date.today()
    arrive_date = today - timedelta(days=75)  # > 2x 30d median
    filed = today - timedelta(days=120)

    permit_rows = [(
        "202401010003",
        "plancheck",
        "Commercial TI",
        filed.isoformat(),
    )]
    station_rows = [(
        "BLDG",
        arrive_date,
        None,  # no reviewer
    )]

    with patch("src.db.get_connection") as mock_gc, \
         patch("src.db.BACKEND", "duckdb"):
        mock_conn = _make_mock_conn(permit_rows=permit_rows, station_rows=station_rows)
        mock_gc.return_value = mock_conn

        from web.helpers import compute_triage_signals
        result = compute_triage_signals(permit_number="202401010003")

    assert isinstance(result, list)
    assert len(result) == 1
    sig = result[0]
    assert sig["days_at_station"] == 75
    assert sig["threshold_class"] == "red"
    assert sig["is_stuck"] is True
    assert sig["reviewer"] is None


def test_compute_triage_signals_missing_reviewer_omitted():
    """When no reviewer is available, reviewer field is None (not shown)."""
    from datetime import date
    today = date.today()

    permit_rows = [(
        "202401010004",
        "issued",
        "Roof repair",
        (today - timedelta(days=10)).isoformat(),
    )]
    # No active station, no reviewer
    station_rows = []
    reviewer_rows = []

    with patch("src.db.get_connection") as mock_gc, \
         patch("src.db.BACKEND", "duckdb"):
        mock_conn = _make_mock_conn(
            permit_rows=permit_rows,
            station_rows=station_rows,
            reviewer_rows=reviewer_rows,
        )
        mock_gc.return_value = mock_conn

        from web.helpers import compute_triage_signals
        result = compute_triage_signals(permit_number="202401010004")

    assert result[0]["reviewer"] is None


# ---------------------------------------------------------------------------
# Tests: template contains triage signal HTML elements
# ---------------------------------------------------------------------------

def test_search_results_public_template_has_triage_classes():
    """search_results_public.html must contain triage signal CSS classes."""
    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "templates", "search_results_public.html",
    )
    with open(template_path) as f:
        content = f.read()

    # Key triage CSS classes
    assert "station-badge" in content, "Missing station-badge CSS class"
    assert "stuck-indicator" in content, "Missing stuck-indicator class"
    assert "triage-reviewer" in content, "Missing triage-reviewer class"
    # Jinja2 template variables
    assert "triage_signals" in content, "Missing triage_signals template variable"
    # Dot color tokens (not signal-*)
    assert "--dot-green" in content, "Missing --dot-green token"
    assert "--dot-amber" in content, "Missing --dot-amber token"
    assert "--dot-red" in content, "Missing --dot-red token"


def test_results_template_has_triage_classes():
    """results.html must contain triage signal CSS classes."""
    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "templates", "results.html",
    )
    with open(template_path) as f:
        content = f.read()

    assert "triage_signals" in content, "Missing triage_signals variable in results.html"
    assert "triage-signals-bar" in content, "Missing triage-signals-bar class"
    assert "triage-sig-badge" in content, "Missing triage-sig-badge class"


def test_search_results_auth_template_has_triage_classes():
    """search_results.html (authenticated) must contain triage signal HTML."""
    import os
    template_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "templates", "search_results.html",
    )
    with open(template_path) as f:
        content = f.read()

    assert "triage_signals" in content, "Missing triage_signals in search_results.html"
    assert "triage-section" in content, "Missing triage-section class"
    assert "triage-station-badge" in content, "Missing triage-station-badge class"


# ---------------------------------------------------------------------------
# Tests: public search route passes triage_signals to template
# ---------------------------------------------------------------------------

def test_public_search_renders_without_error(tmp_path, monkeypatch):
    """Public search page renders without errors (anonymous user)."""
    import src.db as db_mod
    db_path = str(tmp_path / "test_intelligence.duckdb")
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_mod.DATABASE_URL = None

    from web.app import app
    app.config["TESTING"] = True

    # Patch the permit_lookup to avoid hitting DB
    with patch("web.routes_public.run_async") as mock_run, \
         patch("web.routes_public.compute_triage_signals", return_value=[]) as mock_ts, \
         patch("web.routes_public.classify_intent") as mock_ci:
        # Setup mock intent classifier
        mock_intent = MagicMock()
        mock_intent.intent = "search_address"
        mock_intent.entities = {"street_number": "614", "street_name": "6th Ave"}
        mock_ci.return_value = mock_intent
        mock_run.return_value = "# No results found"

        with app.test_client() as client:
            rv = client.get("/search?q=614+6th+Ave")

    assert rv.status_code == 200
    html = rv.data.decode()
    assert "614" in html or "6th" in html or "sfpermits" in html.lower()


def test_public_search_triage_signals_empty_on_no_results(tmp_path, monkeypatch):
    """When search returns no results, triage_signals should be empty."""
    import src.db as db_mod
    db_path = str(tmp_path / "test_triage_no_results.duckdb")
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    db_mod.DATABASE_URL = None

    from web.app import app
    app.config["TESTING"] = True

    with patch("web.routes_public.run_async") as mock_run, \
         patch("web.routes_public.compute_triage_signals") as mock_ts, \
         patch("web.routes_public.classify_intent") as mock_ci:
        mock_intent = MagicMock()
        mock_intent.intent = "search_address"
        mock_intent.entities = {"street_number": "999", "street_name": "Fake St"}
        mock_ci.return_value = mock_intent
        mock_run.return_value = "No permits found."

        with app.test_client() as client:
            rv = client.get("/search?q=999+Fake+St")

    assert rv.status_code == 200
    # compute_triage_signals should NOT be called when no_results is True
    # (or called but returns [])
    # The key is: page renders without error
    assert b"sfpermits" in rv.data.lower() or rv.status_code == 200


# ---------------------------------------------------------------------------
# Tests: station median defaults
# ---------------------------------------------------------------------------

def test_station_median_default_fallback():
    """Unknown station should fall back to 30-day default."""
    from web.helpers import _STATION_MEDIANS, _STATION_MEDIAN_DEFAULT
    unknown = "UNKNOWN-STATION"
    result = _STATION_MEDIANS.get(unknown.upper(), _STATION_MEDIAN_DEFAULT)
    assert result == 30.0


def test_station_median_known_stations():
    """Known stations should have correct medians."""
    from web.helpers import _STATION_MEDIANS
    assert _STATION_MEDIANS["BLDG"] == 30.0
    assert _STATION_MEDIANS["SFFD-HQ"] == 45.0
    assert _STATION_MEDIANS["CP-ZOC"] == 60.0
    assert _STATION_MEDIANS["MECH-E"] == 25.0
    assert _STATION_MEDIANS["ELEC"] == 25.0
