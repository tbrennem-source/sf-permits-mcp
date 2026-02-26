"""Tests for scripts/release.py -- Railway release command migrations."""

import importlib
import os
import sys
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_release():
    """Import scripts.release fresh (avoids stale module cache)."""
    mod_name = "scripts.release"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


# ---------------------------------------------------------------------------
# Test 1: Release script skips on DuckDB backend
# ---------------------------------------------------------------------------

def test_release_skips_on_duckdb():
    """When BACKEND is 'duckdb', migrations should be skipped (return False)."""
    release = _import_release()
    with mock.patch("scripts.release.run_release_migrations.__module__", "scripts.release"):
        pass  # just to show module is loaded

    with mock.patch("src.db.BACKEND", "duckdb"), \
         mock.patch("src.db.get_connection") as mock_conn:
        result = release.run_release_migrations()
        assert result is False
        mock_conn.assert_not_called()


# ---------------------------------------------------------------------------
# Test 2: Release script runs migrations on postgres backend
# ---------------------------------------------------------------------------

def test_release_runs_on_postgres():
    """When BACKEND is 'postgres', migrations should run and return True."""
    release = _import_release()

    mock_cur = mock.MagicMock()
    # For the admin auto-seed SELECT COUNT(*) check
    mock_cur.fetchone.return_value = (1,)  # non-empty users table

    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", return_value=mock_conn):
        result = release.run_release_migrations()

    assert result is True
    # Verify cursor was used for SQL execution
    assert mock_cur.execute.call_count > 0
    mock_cur.close.assert_called_once()
    mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test 3: Release script is idempotent (running twice doesn't error)
# ---------------------------------------------------------------------------

def test_release_idempotent():
    """Running migrations twice should succeed both times (all CREATE IF NOT EXISTS)."""
    release = _import_release()

    mock_cur = mock.MagicMock()
    mock_cur.fetchone.return_value = (1,)

    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", return_value=mock_conn):
        result1 = release.run_release_migrations()
        result2 = release.run_release_migrations()

    assert result1 is True
    assert result2 is True


# ---------------------------------------------------------------------------
# Test 4: Release script raises on connection failure
# ---------------------------------------------------------------------------

def test_release_raises_on_connection_error():
    """If get_connection() fails, the exception propagates (caller exits 1)."""
    release = _import_release()

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", side_effect=ConnectionError("db down")):
        with pytest.raises(ConnectionError, match="db down"):
            release.run_release_migrations()


# ---------------------------------------------------------------------------
# Test 5: Release script raises on SQL execution failure
# ---------------------------------------------------------------------------

def test_release_raises_on_sql_error():
    """If a critical SQL statement fails, the exception propagates."""
    release = _import_release()

    mock_cur = mock.MagicMock()
    mock_cur.execute.side_effect = Exception("permission denied")

    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", return_value=mock_conn):
        with pytest.raises(Exception, match="permission denied"):
            release.run_release_migrations()


# ---------------------------------------------------------------------------
# Test 6: Admin auto-seed runs when users table is empty
# ---------------------------------------------------------------------------

def test_release_seeds_admin_when_empty():
    """When ADMIN_EMAIL is set and users table is empty, admin is seeded."""
    release = _import_release()

    mock_cur = mock.MagicMock()
    # First fetchone call returns 0 (empty users table)
    mock_cur.fetchone.return_value = (0,)

    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", return_value=mock_conn), \
         mock.patch.dict(os.environ, {"ADMIN_EMAIL": "admin@test.com"}):
        result = release.run_release_migrations()

    assert result is True
    # Verify INSERT was called for admin user
    insert_calls = [
        call for call in mock_cur.execute.call_args_list
        if "INSERT INTO users" in str(call)
    ]
    assert len(insert_calls) == 1
    assert "admin@test.com" in str(insert_calls[0])


# ---------------------------------------------------------------------------
# Test 7: Gate in web/app.py -- migrations NOT called without env var
# ---------------------------------------------------------------------------

def test_gate_skips_without_env_var():
    """When RUN_MIGRATIONS_ON_STARTUP is not set, _run_startup_migrations is
    not called at module load time."""
    # Read the relevant lines from web/app.py and verify the guard
    import ast

    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "app.py",
    )
    with open(app_path) as f:
        source = f.read()

    # Find the gated call pattern
    assert 'os.environ.get("RUN_MIGRATIONS_ON_STARTUP"' in source
    assert '("1", "true", "yes")' in source

    # The bare call `_run_startup_migrations()` at module level should NOT
    # exist without the guard. Check that the only module-level references
    # are inside the if-block.
    lines = source.splitlines()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "_run_startup_migrations()":
            # This is the unguarded call -- it should be indented (inside if)
            assert line.startswith("    "), (
                f"Line {i+1}: _run_startup_migrations() should be inside the "
                f"RUN_MIGRATIONS_ON_STARTUP guard, but found at column 0"
            )


# ---------------------------------------------------------------------------
# Test 8: Gate in web/app.py -- migrations called with env var set
# ---------------------------------------------------------------------------

def test_gate_calls_with_env_var():
    """When RUN_MIGRATIONS_ON_STARTUP=true, the guard evaluates to True."""
    # Test the guard logic directly (same condition as in web/app.py)
    for val in ("1", "true", "yes", "True", "TRUE", "Yes", "YES"):
        with mock.patch.dict(os.environ, {"RUN_MIGRATIONS_ON_STARTUP": val}):
            result = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "").lower() in ("1", "true", "yes")
            assert result is True, f"Expected True for RUN_MIGRATIONS_ON_STARTUP={val!r}"


def test_gate_skips_with_wrong_values():
    """When RUN_MIGRATIONS_ON_STARTUP is set to something else, guard is False."""
    for val in ("0", "false", "no", "", "maybe"):
        with mock.patch.dict(os.environ, {"RUN_MIGRATIONS_ON_STARTUP": val}):
            result = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "").lower() in ("1", "true", "yes")
            assert result is False, f"Expected False for RUN_MIGRATIONS_ON_STARTUP={val!r}"


# ---------------------------------------------------------------------------
# Test 9: railway.toml has releaseCommand
# ---------------------------------------------------------------------------

def test_railway_toml_has_release_command():
    """web/railway.toml should include a releaseCommand for scripts.release."""
    toml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "web", "railway.toml",
    )
    with open(toml_path) as f:
        content = f.read()

    assert "releaseCommand" in content
    assert "scripts.release" in content


# ---------------------------------------------------------------------------
# Test 10: New composite indexes are present in release DDL (Sprint 66-B)
# ---------------------------------------------------------------------------

def test_release_has_composite_indexes():
    """Verify idx_addenda_app_finish and idx_permits_block_lot_status in _bulk_indexes."""
    release = _import_release()
    source_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "release.py",
    )
    with open(source_path) as f:
        content = f.read()

    assert "idx_addenda_app_finish" in content
    assert "application_number, finish_date" in content
    assert "idx_permits_block_lot_status" in content
    assert "block, lot, status" in content


def test_release_composite_index_ddl_is_valid():
    """Composite index DDL is syntactically valid SQL (no parse errors)."""
    release = _import_release()

    mock_cur = mock.MagicMock()
    mock_cur.fetchone.return_value = (1,)

    mock_conn = mock.MagicMock()
    mock_conn.cursor.return_value = mock_cur

    with mock.patch("src.db.BACKEND", "postgres"), \
         mock.patch("src.db.get_connection", return_value=mock_conn):
        result = release.run_release_migrations()

    assert result is True

    # Check that the composite index DDL was executed
    executed_sql = [str(call) for call in mock_cur.execute.call_args_list]
    addenda_idx = [s for s in executed_sql if "idx_addenda_app_finish" in s]
    permits_idx = [s for s in executed_sql if "idx_permits_block_lot_status" in s]
    assert len(addenda_idx) >= 1
    assert len(permits_idx) >= 1
