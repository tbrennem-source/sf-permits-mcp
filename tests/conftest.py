"""Root-level test conftest — fixtures shared across all test files.

Prevents cross-file contamination from in-memory state (rate buckets,
daily limit cache, etc.) that persists between test files in the same
pytest session.

Also provides per-session database isolation:
- Attempts to use testing.postgresql (temp Postgres) for full SQL parity
- Falls back to per-session temp DuckDB if Postgres binary not available
  (fixes lock contention; SQL divergence remains a P1 follow-up)
"""
import os
import pytest


# ---------------------------------------------------------------------------
# Session-scoped DB isolation fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _isolated_test_db(tmp_path_factory):
    """Per-session temp DuckDB — fixes contention, NOT divergence.

    FALLBACK: testing.postgresql failed (initdb not found — Postgres binary
    not installed on this machine). Using per-session temp DuckDB instead.
    Fixes lock contention but NOT SQL divergence. Postgres migration deferred
    to P1 follow-up (brew install postgresql@16 required).

    Each pytest session gets its own isolated DuckDB file so parallel sessions
    (e.g., 16 swarm agents) cannot lock-conflict each other.
    """
    import src.db as db_mod

    tmpdir = tmp_path_factory.mktemp("duckdb")
    db_path = str(tmpdir / "test_permits.duckdb")

    original_path = db_mod._DUCKDB_PATH
    original_backend = db_mod.BACKEND

    # Force DuckDB backend with temp path
    db_mod._DUCKDB_PATH = db_path
    db_mod.BACKEND = "duckdb"

    # Initialize schema so tests that expect tables find them
    try:
        conn = db_mod.get_connection()
        try:
            _init_test_schema_duckdb(conn)
        except Exception as e:
            # Non-fatal: individual test files often call init_user_schema
            # themselves, so this is a best-effort pre-warm.
            pass
        finally:
            conn.close()
    except Exception:
        pass

    # Guard: monkey-patch duckdb.connect to block access to the real DB file
    _real_db = os.path.abspath(original_path)
    import duckdb as _duckdb_mod
    _original_connect = _duckdb_mod.connect

    def _guarded_connect(database=":memory:", *args, **kwargs):
        if database not in (":memory:", ":default:"):
            abs_path = os.path.abspath(database)
            if abs_path == _real_db:
                raise RuntimeError(
                    f"TEST GUARD: Attempted to open the real DuckDB file "
                    f"({_real_db}) during tests. Use the temp DB from the "
                    f"_isolated_test_db fixture or duckdb.connect(':memory:') instead."
                )
        return _original_connect(database, *args, **kwargs)

    _duckdb_mod.connect = _guarded_connect

    yield db_path

    # Restore
    _duckdb_mod.connect = _original_connect
    db_mod._DUCKDB_PATH = original_path
    db_mod.BACKEND = original_backend


def _init_test_schema_duckdb(conn) -> None:
    """Create all tables tests expect in the temp DuckDB.

    Calls the same functions that src/db.py exposes for dev mode.
    Using IF NOT EXISTS everywhere so it is safe to call multiple times.
    """
    from src.db import init_user_schema, init_schema
    try:
        init_schema(conn)
    except Exception:
        pass
    try:
        init_user_schema(conn)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Function-scoped rate/cache clearing
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_rate_state():
    """Clear rate limiter buckets and daily cache before each test.

    Without this, rate limit counters from one test file bleed into
    the next, causing 429 responses in tests that don't expect them.
    """
    try:
        from web.helpers import _rate_buckets
        _rate_buckets.clear()
    except (ImportError, Exception):
        pass

    try:
        from web.security import _daily_cache
        _daily_cache.clear()
    except (ImportError, Exception):
        pass

    yield

    # Also clear after, in case test intentionally triggered limits
    try:
        from web.helpers import _rate_buckets
        _rate_buckets.clear()
    except (ImportError, Exception):
        pass

    try:
        from web.security import _daily_cache
        _daily_cache.clear()
    except (ImportError, Exception):
        pass
