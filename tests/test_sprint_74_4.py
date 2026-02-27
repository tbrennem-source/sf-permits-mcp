"""Tests for Sprint 74-4: Connection Pool Tuning.

Covers:
- DB_POOL_MIN env var configures minconn
- DB_CONNECT_TIMEOUT env var configures connect_timeout
- DB_STATEMENT_TIMEOUT env var is applied to new connections
- Pool exhaustion logs a WARNING with pool stats
- get_pool_health() returns correct structure
- get_pool_stats() includes health dict
"""
import importlib
import logging
import sys
import types
import unittest.mock as mock
from unittest.mock import MagicMock, patch


# ── helpers ──────────────────────────────────────────────────────────────────

def _reload_db(monkeypatch, env: dict):
    """Reload src.db with a clean _pool=None and given env vars."""
    # Remove cached module so imports are fresh
    for mod_name in list(sys.modules.keys()):
        if mod_name == "src.db" or mod_name.startswith("src.db."):
            del sys.modules[mod_name]

    for key, val in env.items():
        monkeypatch.setenv(key, val)

    import src.db as db_mod  # noqa: PLC0415
    # Ensure pool is None (module-level singleton reset)
    db_mod._pool = None
    return db_mod


# ── Task 74-4-1: DB_POOL_MIN env var ─────────────────────────────────────────

def test_pool_min_default(monkeypatch):
    """DB_POOL_MIN defaults to 2 when not set."""
    monkeypatch.delenv("DB_POOL_MIN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    captured = {}

    def fake_pool(minconn, maxconn, dsn, connect_timeout):
        captured["minconn"] = minconn
        captured["maxconn"] = maxconn
        pool_obj = MagicMock()
        pool_obj.closed = False
        pool_obj.minconn = minconn
        pool_obj.maxconn = maxconn
        pool_obj._pool = []
        pool_obj._used = set()
        return pool_obj

    import psycopg2.pool as pg_pool  # noqa: PLC0415
    with patch.object(pg_pool, "ThreadedConnectionPool", side_effect=fake_pool):
        monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
        db_mod.DATABASE_URL = "postgresql://fake/db"
        db_mod.BACKEND = "postgres"
        db_mod._pool = None
        db_mod._get_pool()

    assert captured["minconn"] == 2


def test_pool_min_custom(monkeypatch):
    """DB_POOL_MIN=5 is passed as minconn to ThreadedConnectionPool."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    captured = {}

    def fake_pool(minconn, maxconn, dsn, connect_timeout):
        captured["minconn"] = minconn
        pool_obj = MagicMock()
        pool_obj.closed = False
        pool_obj.minconn = minconn
        pool_obj.maxconn = maxconn
        pool_obj._pool = []
        pool_obj._used = set()
        return pool_obj

    import psycopg2.pool as pg_pool  # noqa: PLC0415
    monkeypatch.setenv("DB_POOL_MIN", "5")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
    db_mod.DATABASE_URL = "postgresql://fake/db"
    db_mod.BACKEND = "postgres"
    db_mod._pool = None

    with patch.object(pg_pool, "ThreadedConnectionPool", side_effect=fake_pool):
        db_mod._get_pool()

    assert captured["minconn"] == 5


# ── Task 74-4-2: DB_CONNECT_TIMEOUT env var ──────────────────────────────────

def test_connect_timeout_default(monkeypatch):
    """DB_CONNECT_TIMEOUT defaults to 10."""
    monkeypatch.delenv("DB_CONNECT_TIMEOUT", raising=False)
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    captured = {}

    def fake_pool(minconn, maxconn, dsn, connect_timeout):
        captured["connect_timeout"] = connect_timeout
        pool_obj = MagicMock()
        pool_obj.closed = False
        pool_obj.minconn = minconn
        pool_obj.maxconn = maxconn
        pool_obj._pool = []
        pool_obj._used = set()
        return pool_obj

    import psycopg2.pool as pg_pool  # noqa: PLC0415
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
    db_mod.DATABASE_URL = "postgresql://fake/db"
    db_mod.BACKEND = "postgres"

    with patch.object(pg_pool, "ThreadedConnectionPool", side_effect=fake_pool):
        db_mod._get_pool()

    assert captured["connect_timeout"] == 10


def test_connect_timeout_custom(monkeypatch):
    """DB_CONNECT_TIMEOUT=30 is passed to ThreadedConnectionPool."""
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "30")
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    captured = {}

    def fake_pool(minconn, maxconn, dsn, connect_timeout):
        captured["connect_timeout"] = connect_timeout
        pool_obj = MagicMock()
        pool_obj.closed = False
        pool_obj.minconn = minconn
        pool_obj.maxconn = maxconn
        pool_obj._pool = []
        pool_obj._used = set()
        return pool_obj

    import psycopg2.pool as pg_pool  # noqa: PLC0415
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/db")
    db_mod.DATABASE_URL = "postgresql://fake/db"
    db_mod.BACKEND = "postgres"

    with patch.object(pg_pool, "ThreadedConnectionPool", side_effect=fake_pool):
        db_mod._get_pool()

    assert captured["connect_timeout"] == 30


# ── Task 74-4-3: DB_STATEMENT_TIMEOUT applied to new connections ──────────────

def test_statement_timeout_applied_default(monkeypatch):
    """Default DB_STATEMENT_TIMEOUT='30s' is SET on new connections."""
    monkeypatch.delenv("DB_STATEMENT_TIMEOUT", raising=False)
    monkeypatch.delenv("CRON_WORKER", raising=False)

    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None
    db_mod.BACKEND = "postgres"

    # Build a fake raw connection
    fake_cursor = MagicMock()
    fake_cursor.__enter__ = lambda s: s
    fake_cursor.__exit__ = MagicMock(return_value=False)
    fake_raw_conn = MagicMock()
    fake_raw_conn.cursor.return_value = fake_cursor

    fake_pool_obj = MagicMock()
    fake_pool_obj.getconn.return_value = fake_raw_conn

    db_mod._pool = fake_pool_obj

    conn = db_mod.get_connection()
    conn.close()

    # cursor.execute should have been called with the timeout param
    fake_cursor.execute.assert_called_once_with("SET statement_timeout = %s", ("30s",))


def test_statement_timeout_custom(monkeypatch):
    """DB_STATEMENT_TIMEOUT='60s' is applied to new connections."""
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT", "60s")
    monkeypatch.delenv("CRON_WORKER", raising=False)

    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None
    db_mod.BACKEND = "postgres"

    fake_cursor = MagicMock()
    fake_cursor.__enter__ = lambda s: s
    fake_cursor.__exit__ = MagicMock(return_value=False)
    fake_raw_conn = MagicMock()
    fake_raw_conn.cursor.return_value = fake_cursor

    fake_pool_obj = MagicMock()
    fake_pool_obj.getconn.return_value = fake_raw_conn

    db_mod._pool = fake_pool_obj

    conn = db_mod.get_connection()
    conn.close()

    fake_cursor.execute.assert_called_once_with("SET statement_timeout = %s", ("60s",))


def test_statement_timeout_skipped_for_cron_worker(monkeypatch):
    """Statement timeout is NOT set when CRON_WORKER=true."""
    monkeypatch.setenv("CRON_WORKER", "true")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT", "30s")

    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None
    db_mod.BACKEND = "postgres"

    fake_raw_conn = MagicMock()
    fake_pool_obj = MagicMock()
    fake_pool_obj.getconn.return_value = fake_raw_conn

    db_mod._pool = fake_pool_obj

    conn = db_mod.get_connection()
    conn.close()

    # cursor should NOT have been used for statement_timeout
    fake_raw_conn.cursor.assert_not_called()


# ── Task 74-4-4: Pool exhaustion logging ─────────────────────────────────────

def test_pool_exhaustion_logs_warning(monkeypatch, caplog):
    """PoolError raises and logs a WARNING with pool stats."""
    monkeypatch.delenv("CRON_WORKER", raising=False)

    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    import psycopg2.pool as pg_pool  # noqa: PLC0415

    db_mod.BACKEND = "postgres"

    fake_pool_obj = MagicMock()
    fake_pool_obj.closed = False
    fake_pool_obj.minconn = 2
    fake_pool_obj.maxconn = 5
    fake_pool_obj._pool = []
    fake_pool_obj._used = set()
    fake_pool_obj.getconn.side_effect = pg_pool.PoolError("connection pool exhausted")

    db_mod._pool = fake_pool_obj

    with caplog.at_level(logging.WARNING, logger="src.db"):
        import pytest  # noqa: PLC0415
        with pytest.raises(pg_pool.PoolError):
            db_mod.get_connection()

    assert any("Pool exhausted" in r.message for r in caplog.records)
    assert any("pool_stats" in r.message for r in caplog.records)


# ── Task 74-4-5: get_pool_health() ───────────────────────────────────────────

def test_get_pool_health_no_pool():
    """get_pool_health() returns healthy=False when pool is None."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    health = db_mod.get_pool_health()
    assert health["healthy"] is False
    assert health["min"] == 0
    assert health["max"] == 0
    assert health["in_use"] == 0
    assert health["available"] == 0


def test_get_pool_health_with_pool():
    """get_pool_health() returns correct values from an active pool."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod

    fake_pool_obj = MagicMock()
    fake_pool_obj.closed = False
    fake_pool_obj.minconn = 2
    fake_pool_obj.maxconn = 10
    # Simulate 3 connections in pool, 2 in use
    fake_pool_obj._pool = [MagicMock(), MagicMock(), MagicMock()]
    fake_pool_obj._used = {MagicMock(), MagicMock()}

    db_mod._pool = fake_pool_obj

    health = db_mod.get_pool_health()
    assert health["healthy"] is True
    assert health["min"] == 2
    assert health["max"] == 10
    assert health["in_use"] == 2
    assert health["available"] == 1  # 3 pool - 2 used


def test_get_pool_health_closed_pool():
    """get_pool_health() returns healthy=False when pool is closed."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod

    fake_pool_obj = MagicMock()
    fake_pool_obj.closed = True  # Pool is closed
    fake_pool_obj.minconn = 2
    fake_pool_obj.maxconn = 10
    fake_pool_obj._pool = []
    fake_pool_obj._used = set()

    db_mod._pool = fake_pool_obj

    health = db_mod.get_pool_health()
    assert health["healthy"] is False


# ── Task 74-4-6: get_pool_stats() includes health ────────────────────────────

def test_get_pool_stats_includes_health():
    """get_pool_stats() result includes a 'health' key with the health dict."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod

    fake_pool_obj = MagicMock()
    fake_pool_obj.closed = False
    fake_pool_obj.minconn = 2
    fake_pool_obj.maxconn = 20
    fake_pool_obj._pool = [MagicMock()]
    fake_pool_obj._used = set()

    db_mod._pool = fake_pool_obj

    stats = db_mod.get_pool_stats()
    assert "health" in stats
    health = stats["health"]
    assert "healthy" in health
    assert "min" in health
    assert "max" in health
    assert "in_use" in health
    assert "available" in health


def test_get_pool_stats_no_pool_no_health_key():
    """get_pool_stats() returns status='no_pool' when pool is None (no health key needed)."""
    for mod in list(sys.modules):
        if "src.db" in mod:
            del sys.modules[mod]

    import src.db as db_mod
    db_mod._pool = None

    stats = db_mod.get_pool_stats()
    assert stats["status"] == "no_pool"
    assert stats["backend"] == db_mod.BACKEND
