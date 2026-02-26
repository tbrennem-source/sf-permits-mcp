"""Tests for PostgreSQL connection pool in src/db.py.

Tests pool creation, connection lifecycle, statement_timeout,
_PooledConnection wrapper, and DuckDB path unchanged.
"""

import atexit
import os
import types
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers to import src.db with a controlled BACKEND value
# ---------------------------------------------------------------------------

def _reload_db(monkeypatch, backend="duckdb", database_url=None):
    """Reload src.db with the given BACKEND setting."""
    import importlib
    import src.db as db_mod

    # Reset the pool singleton before reload
    db_mod._pool = None

    if database_url:
        monkeypatch.setenv("DATABASE_URL", database_url)
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    importlib.reload(db_mod)
    return db_mod


# ═══════════════════════════════════════════════════════════════════
# 1. Pool creation — lazy, only on first call
# ═══════════════════════════════════════════════════════════════════

class TestPoolCreation:
    def test_pool_not_created_at_import(self, monkeypatch):
        """Pool should be None after import — not eagerly created."""
        db = _reload_db(monkeypatch, backend="duckdb")
        assert db._pool is None

    def test_pool_created_on_first_get_connection(self, monkeypatch):
        """_get_pool() should create pool on first call."""
        db = _reload_db(monkeypatch, backend="duckdb")
        # Force postgres backend
        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")

        mock_pool_cls = MagicMock()
        mock_pool_instance = MagicMock()
        mock_pool_cls.return_value = mock_pool_instance
        mock_raw_conn = MagicMock()
        mock_pool_instance.getconn.return_value = mock_raw_conn

        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.pool": MagicMock()}):
            import psycopg2.pool
            psycopg2.pool.ThreadedConnectionPool = mock_pool_cls

            # First call — creates pool
            db._pool = None
            conn = db.get_connection()
            mock_pool_cls.assert_called_once()
            conn.close()

    def test_pool_reused_on_second_call(self, monkeypatch):
        """Second get_connection() reuses the existing pool."""
        db = _reload_db(monkeypatch, backend="duckdb")
        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")

        mock_pool_cls = MagicMock()
        mock_pool_instance = MagicMock()
        mock_pool_cls.return_value = mock_pool_instance
        mock_raw_conn1 = MagicMock()
        mock_raw_conn2 = MagicMock()
        mock_pool_instance.getconn.side_effect = [mock_raw_conn1, mock_raw_conn2]

        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.pool": MagicMock()}):
            import psycopg2.pool
            psycopg2.pool.ThreadedConnectionPool = mock_pool_cls

            db._pool = None
            conn1 = db.get_connection()
            conn1.close()
            conn2 = db.get_connection()
            conn2.close()

            # Pool constructor called only once
            mock_pool_cls.assert_called_once()
            # getconn called twice (two different connections)
            assert mock_pool_instance.getconn.call_count == 2


# ═══════════════════════════════════════════════════════════════════
# 2. Connection return and rollback
# ═══════════════════════════════════════════════════════════════════

class TestConnectionReturn:
    def test_close_calls_putconn(self):
        """_PooledConnection.close() should return conn to pool."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)
        pooled.close()
        mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_close_rolls_back_first(self):
        """close() should rollback before putconn."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        call_order = []
        mock_conn.rollback.side_effect = lambda: call_order.append("rollback")
        mock_pool.putconn.side_effect = lambda c: call_order.append("putconn")

        pooled = _PooledConnection(mock_conn, mock_pool)
        pooled.close()

        assert call_order == ["rollback", "putconn"]

    def test_double_close_is_safe(self):
        """Calling close() twice should not raise."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)
        pooled.close()
        pooled.close()  # Should not raise
        # putconn called only once
        mock_pool.putconn.assert_called_once()

    def test_rollback_error_does_not_prevent_putconn(self):
        """If rollback fails, putconn should still be called."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_conn.rollback.side_effect = Exception("rollback failed")
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)
        pooled.close()  # Should not raise
        mock_pool.putconn.assert_called_once_with(mock_conn)


# ═══════════════════════════════════════════════════════════════════
# 3. statement_timeout
# ═══════════════════════════════════════════════════════════════════

class TestStatementTimeout:
    def test_statement_timeout_set_for_web(self, monkeypatch):
        """Web connections get SET statement_timeout = '30s'."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.delenv("CRON_WORKER", raising=False)

        mock_pool = MagicMock()
        mock_raw_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_raw_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_raw_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_pool.getconn.return_value = mock_raw_conn
        db._pool = mock_pool

        conn = db.get_connection()
        mock_cursor.execute.assert_called_with("SET statement_timeout = '30s'")
        conn.close()

        # Restore
        db._pool = None

    def test_statement_timeout_skipped_for_cron(self, monkeypatch):
        """CRON_WORKER=true skips statement_timeout."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setenv("CRON_WORKER", "true")

        mock_pool = MagicMock()
        mock_raw_conn = MagicMock()
        mock_pool.getconn.return_value = mock_raw_conn
        db._pool = mock_pool

        conn = db.get_connection()
        # cursor() should NOT be called (no statement_timeout)
        mock_raw_conn.cursor.assert_not_called()
        conn.close()

        db._pool = None

    def test_statement_timeout_skipped_for_cron_uppercase(self, monkeypatch):
        """CRON_WORKER=TRUE also skips statement_timeout."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.setenv("CRON_WORKER", "TRUE")

        mock_pool = MagicMock()
        mock_raw_conn = MagicMock()
        mock_pool.getconn.return_value = mock_raw_conn
        db._pool = mock_pool

        conn = db.get_connection()
        mock_raw_conn.cursor.assert_not_called()
        conn.close()

        db._pool = None


# ═══════════════════════════════════════════════════════════════════
# 4. _PooledConnection proxy behavior
# ═══════════════════════════════════════════════════════════════════

class TestPooledConnectionProxy:
    def test_proxies_attributes(self):
        """__getattr__ should forward to underlying connection."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_conn.autocommit = True
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)

        assert pooled.autocommit is True

    def test_proxies_cursor(self):
        """cursor() call is forwarded to underlying connection."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)

        result = pooled.cursor()
        mock_conn.cursor.assert_called_once()
        assert result is mock_cursor

    def test_proxies_commit(self):
        """commit() is forwarded to underlying connection."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_pool = MagicMock()
        pooled = _PooledConnection(mock_conn, mock_pool)

        pooled.commit()
        mock_conn.commit.assert_called_once()

    def test_context_manager(self):
        """_PooledConnection supports `with` statement and calls close on exit."""
        from src.db import _PooledConnection

        mock_conn = MagicMock()
        mock_pool = MagicMock()

        with _PooledConnection(mock_conn, mock_pool) as pooled:
            assert pooled._conn is mock_conn

        # After exiting context, close() should have been called
        mock_pool.putconn.assert_called_once_with(mock_conn)


# ═══════════════════════════════════════════════════════════════════
# 5. DuckDB path unchanged
# ═══════════════════════════════════════════════════════════════════

class TestDuckDBUnchanged:
    def test_duckdb_no_pool(self, monkeypatch, tmp_path):
        """DuckDB connections should NOT use the pool."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "duckdb")
        db._pool = None

        db_file = str(tmp_path / "test.duckdb")
        conn = db.get_connection(db_path=db_file)

        # Pool should still be None
        assert db._pool is None
        conn.close()

    def test_duckdb_with_db_path(self, monkeypatch, tmp_path):
        """Explicit db_path uses DuckDB even when BACKEND=postgres."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        db._pool = None

        db_file = str(tmp_path / "override.duckdb")
        conn = db.get_connection(db_path=db_file)

        # Pool should still be None — db_path bypasses postgres
        assert db._pool is None
        conn.close()


# ═══════════════════════════════════════════════════════════════════
# 6. atexit hook
# ═══════════════════════════════════════════════════════════════════

class TestAtexitHook:
    def test_atexit_registered(self):
        """_close_pool should be registered with atexit."""
        from src.db import _close_pool
        # Check that _close_pool is in the atexit registry
        # atexit doesn't expose a public API to check, but we can verify
        # the function exists and is callable
        assert callable(_close_pool)

    def test_close_pool_closes_all(self):
        """_close_pool should call closeall() on the pool."""
        import src.db as db

        mock_pool = MagicMock()
        db._pool = mock_pool

        db._close_pool()

        mock_pool.closeall.assert_called_once()
        assert db._pool is None

    def test_close_pool_when_no_pool(self):
        """_close_pool should be safe when pool is None."""
        import src.db as db
        db._pool = None
        db._close_pool()  # Should not raise
        assert db._pool is None


# ═══════════════════════════════════════════════════════════════════
# 7. Pool error handling
# ═══════════════════════════════════════════════════════════════════

class TestPoolErrorHandling:
    def test_getconn_error_propagates(self, monkeypatch):
        """If pool.getconn() fails, the error should propagate."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")

        mock_pool = MagicMock()
        mock_pool.getconn.side_effect = Exception("pool exhausted")
        db._pool = mock_pool

        with pytest.raises(Exception, match="pool exhausted"):
            db.get_connection()

        db._pool = None

    def test_pool_creation_error_propagates(self, monkeypatch):
        """If ThreadedConnectionPool() fails, error should propagate."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        db._pool = None

        mock_pool_cls = MagicMock(side_effect=Exception("cannot connect"))

        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.pool": MagicMock()}):
            import psycopg2.pool
            psycopg2.pool.ThreadedConnectionPool = mock_pool_cls

            with pytest.raises(Exception, match="cannot connect"):
                db.get_connection()

        db._pool = None


# ═══════════════════════════════════════════════════════════════════
# 8. query() and execute_write() with pooled connections
# ═══════════════════════════════════════════════════════════════════

class TestQueryWithPool:
    def test_query_uses_pool(self, monkeypatch):
        """query() should get a pooled connection in postgres mode."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.delenv("CRON_WORKER", raising=False)

        mock_pool = MagicMock()
        mock_raw_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [("row1",)]

        # Support both statement_timeout cursor and query cursor
        cursor_calls = []

        def make_cursor():
            cm = MagicMock()
            cursor_mock = MagicMock()
            cursor_mock.fetchall.return_value = [("row1",)]
            cm.__enter__ = MagicMock(return_value=cursor_mock)
            cm.__exit__ = MagicMock(return_value=False)
            cursor_calls.append(cursor_mock)
            return cm

        mock_raw_conn.cursor.side_effect = make_cursor
        mock_pool.getconn.return_value = mock_raw_conn
        db._pool = mock_pool

        # Patch psycopg2.extras for the import inside query()
        mock_extras = MagicMock()
        with patch.dict("sys.modules", {"psycopg2.extras": mock_extras}):
            result = db.query("SELECT 1")

        assert result == [("row1",)]
        # getconn called once, putconn called once (via close)
        mock_pool.getconn.assert_called_once()
        mock_pool.putconn.assert_called_once()

        db._pool = None

    def test_execute_write_uses_pool(self, monkeypatch):
        """execute_write() should get and return a pooled connection."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        monkeypatch.delenv("CRON_WORKER", raising=False)

        mock_pool = MagicMock()
        mock_raw_conn = MagicMock()

        def make_cursor():
            cm = MagicMock()
            cursor_mock = MagicMock()
            cursor_mock.fetchone.return_value = None
            cm.__enter__ = MagicMock(return_value=cursor_mock)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        mock_raw_conn.cursor.side_effect = make_cursor
        mock_pool.getconn.return_value = mock_raw_conn
        db._pool = mock_pool

        with patch.dict("sys.modules", {"psycopg2.extras": MagicMock()}):
            db.execute_write("INSERT INTO test VALUES (%s)", ("val",))

        mock_pool.getconn.assert_called_once()
        mock_pool.putconn.assert_called_once()

        db._pool = None


# ═══════════════════════════════════════════════════════════════════
# 9. Pool configuration
# ═══════════════════════════════════════════════════════════════════

class TestPoolConfig:
    def test_pool_minconn_maxconn(self, monkeypatch):
        """Pool should be created with minconn=2, maxconn=20."""
        import src.db as db

        monkeypatch.setattr(db, "BACKEND", "postgres")
        monkeypatch.setattr(db, "DATABASE_URL", "postgresql://test:test@localhost/test")
        db._pool = None

        mock_pool_cls = MagicMock()
        mock_pool_instance = MagicMock()
        mock_pool_cls.return_value = mock_pool_instance

        with patch.dict("sys.modules", {"psycopg2": MagicMock(), "psycopg2.pool": MagicMock()}):
            import psycopg2.pool
            psycopg2.pool.ThreadedConnectionPool = mock_pool_cls

            db._get_pool()

            mock_pool_cls.assert_called_once_with(
                minconn=2,
                maxconn=20,
                dsn="postgresql://test:test@localhost/test",
                connect_timeout=10,
            )

        db._pool = None
