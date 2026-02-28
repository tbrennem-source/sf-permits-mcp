"""Root-level test conftest — fixtures shared across all test files.

Prevents cross-file contamination from in-memory state (rate buckets,
daily limit cache, etc.) that persists between test files in the same
pytest session.

Database isolation: each pytest session gets its own temp Postgres instance
via testing.postgresql. Falls back to per-session temp DuckDB if Postgres
binary is not available (e.g., CI without postgresql installed).
"""
import os
import pytest


# ---------------------------------------------------------------------------
# Session-scoped DB isolation fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True, scope="session")
def _isolated_test_db(tmp_path_factory):
    """Spin up a temp Postgres per session — zero contention, matches prod.

    Falls back to per-session temp DuckDB if testing.postgresql is not
    available (no pg_ctl on PATH).
    """
    import src.db as db_mod

    original_backend = db_mod.BACKEND
    original_url = os.environ.get("DATABASE_URL")
    original_duckdb_path = db_mod._DUCKDB_PATH

    # Guard: block access to the real DuckDB file regardless of which path we take
    _real_db = os.path.abspath(original_duckdb_path)
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

    # --- Try Postgres if opted in ---
    # Default: DuckDB isolation (all tests pass, fixes contention)
    # Opt-in: USE_POSTGRES_TESTS=1 for full SQL parity (many tests still need migration)
    pg_instance = None
    use_postgres = os.environ.get("USE_POSTGRES_TESTS", "").lower() in ("1", "true", "yes")
    try:
        if not use_postgres:
            raise ImportError("Postgres tests not opted in — using DuckDB isolation")
        import testing.postgresql
        pg_instance = testing.postgresql.Postgresql()
        dsn = pg_instance.url()

        # Wire src.db to use temp Postgres
        os.environ["DATABASE_URL"] = dsn
        db_mod.DATABASE_URL = dsn
        db_mod.BACKEND = "postgres"

        # Reset connection pool so it picks up the temp DSN
        if db_mod._pool is not None:
            try:
                db_mod._pool.closeall()
            except Exception:
                pass
            db_mod._pool = None

        # Initialize schema in temp Postgres
        conn = db_mod.get_connection()
        try:
            _init_test_schema_postgres(conn)
            conn.commit()
        finally:
            conn.close()

        yield dsn

    except Exception:
        # --- Fallback: per-session temp DuckDB ---
        if pg_instance is not None:
            try:
                pg_instance.stop()
            except Exception:
                pass
            pg_instance = None

        tmpdir = tmp_path_factory.mktemp("duckdb")
        db_path = str(tmpdir / "test_permits.duckdb")

        db_mod._DUCKDB_PATH = db_path
        db_mod.BACKEND = "duckdb"
        # Clear DATABASE_URL so get_connection() takes the DuckDB path
        os.environ.pop("DATABASE_URL", None)
        db_mod.DATABASE_URL = None

        try:
            conn = db_mod.get_connection()
            try:
                _init_test_schema_duckdb(conn)
            except Exception:
                pass
            finally:
                conn.close()
        except Exception:
            pass

        yield db_path

    finally:
        # Restore everything
        _duckdb_mod.connect = _original_connect
        db_mod._DUCKDB_PATH = original_duckdb_path
        db_mod.BACKEND = original_backend
        if original_url:
            os.environ["DATABASE_URL"] = original_url
        else:
            os.environ.pop("DATABASE_URL", None)
        db_mod.DATABASE_URL = original_url

        # Close pool and stop Postgres
        if db_mod._pool is not None:
            try:
                db_mod._pool.closeall()
            except Exception:
                pass
            db_mod._pool = None
        if pg_instance is not None:
            try:
                pg_instance.stop()
            except Exception:
                pass


def _init_test_schema_postgres(conn):
    """Create all tables tests expect in the temp Postgres.

    init_user_schema uses conn.execute() (DuckDB pattern) which doesn't work
    with psycopg2 (needs cursor.execute()). We wrap the raw connection to add
    a .execute() shim so the existing init functions work on both backends.
    """
    # Get the raw psycopg2 connection from _PooledConnection wrapper
    raw = conn._conn if hasattr(conn, '_conn') else conn

    # Use autocommit so each DDL statement is its own transaction.
    # Without this, one failing statement (e.g., duplicate ALTER TABLE)
    # aborts the Postgres transaction and all subsequent statements fail.
    old_autocommit = raw.autocommit
    raw.autocommit = True

    class _PgExecShim:
        """Adds .execute() to a psycopg2 connection for DuckDB-style calls."""
        def __init__(self, pg_conn):
            self._conn = pg_conn
        def execute(self, sql, params=None):
            with self._conn.cursor() as cur:
                try:
                    cur.execute(sql, params)
                except Exception:
                    pass  # Individual DDL failures are expected (e.g., column already exists)
        def commit(self):
            pass  # autocommit handles this
        def close(self):
            pass  # Don't close the pooled connection

    shim = _PgExecShim(raw)
    from src.db import init_user_schema, init_schema
    try:
        init_schema(shim)
    except Exception:
        pass
    try:
        init_user_schema(shim)
    except Exception:
        pass

    raw.autocommit = old_autocommit


def _init_test_schema_duckdb(conn):
    """Create all tables tests expect in the temp DuckDB."""
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


# ---------------------------------------------------------------------------
# Function-scoped DB-path guard
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_db_path():
    """Save and restore src.db._DUCKDB_PATH and BACKEND around every test.

    Some tests (e.g. test_qs3_a_permit_prep.py) call importlib.reload(src.db),
    which resets _DUCKDB_PATH back to the environment default (the real DuckDB
    file path).  Without this fixture, the session-scoped _isolated_test_db
    temp path is lost for all subsequent tests — causing the TEST GUARD to
    block every get_connection() call, which is silently swallowed inside
    get_cached_or_compute(), making the page_cache appear to never persist.

    Runs after every test (yield teardown) to restore the path that was
    active before the test started.
    """
    try:
        import src.db as db_mod
        saved_path = db_mod._DUCKDB_PATH
        saved_backend = db_mod.BACKEND
        saved_db_url = db_mod.DATABASE_URL
    except (ImportError, Exception):
        yield
        return

    yield

    try:
        import src.db as db_mod
        db_mod._DUCKDB_PATH = saved_path
        db_mod.BACKEND = saved_backend
        db_mod.DATABASE_URL = saved_db_url
    except (ImportError, Exception):
        pass


# ---------------------------------------------------------------------------
# Function-scoped Flask app guard
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _restore_flask_app():
    """Restore the Flask app instance on web.app after each test.

    Some tests (e.g. test_sprint56c.py) call importlib.reload(web.app),
    which creates a NEW Flask app on the module. Tests that imported the
    old app via ``from web.app import app`` then hold a stale reference
    with no registered routes, causing 404s.

    This fixture saves the module-level ``app`` before each test and
    restores it afterwards, ensuring any reload is undone.
    """
    try:
        import web.app as app_mod
        saved_app = app_mod.app
    except (ImportError, Exception):
        yield
        return

    yield

    try:
        import web.app as app_mod
        if app_mod.app is not saved_app:
            app_mod.app = saved_app
    except (ImportError, Exception):
        pass


@pytest.fixture(autouse=True)
def _clear_cron_worker():
    """Ensure CRON_WORKER env var is cleaned up after each test.

    Some tests set CRON_WORKER=1 via os.environ directly (not monkeypatch).
    If a test fails before cleanup, the env var leaks into subsequent tests,
    causing all non-/cron routes to return 404 via the _cron_guard hook.
    """
    yield
    os.environ.pop("CRON_WORKER", None)
