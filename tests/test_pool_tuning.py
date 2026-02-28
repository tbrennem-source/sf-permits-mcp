"""Tests for DB pool default tuning (Sprint 84-A).

Verifies:
- DB_POOL_MIN default changed to 5
- DB_POOL_MAX default changed to 50
- Pool config can be overridden via env vars
- Exhaustion warning fires when pool utilization >= threshold

These tests are backend-agnostic — they patch psycopg2 and inspect the
arguments _get_pool() would pass, rather than opening a real PostgreSQL
connection.
"""

import logging
import os
import unittest
from unittest.mock import MagicMock, patch, call


def _fresh_db_module(env_overrides=None):
    """Import src.db with a clean module state (no cached _pool singleton).

    Uses importlib.reload() after temporarily patching os.environ and resetting
    the module-level _pool global so each test starts from a clean slate.

    Returns the reloaded module.
    """
    import importlib
    import src.db as db_mod

    # Reset the lazy singleton before reload
    db_mod._pool = None

    env = {**os.environ, **(env_overrides or {})}
    with patch.dict(os.environ, env, clear=False):
        importlib.reload(db_mod)

    return db_mod


class TestDefaultPoolMin(unittest.TestCase):
    """DB_POOL_MIN default is 5."""

    def test_default_pool_min_is_5(self):
        """_get_pool() passes minconn=5 when DB_POOL_MIN is not set."""
        import importlib
        import src.db as db_mod

        # Ensure a fresh state
        db_mod._pool = None

        mock_pool = MagicMock()
        env = {
            "DATABASE_URL": "postgresql://localhost/test",
            # Explicitly remove DB_POOL_MIN so we get the default
        }
        # Strip DB_POOL_MIN from env if present
        env_clean = {k: v for k, v in os.environ.items() if k != "DB_POOL_MIN"}
        env_clean["DATABASE_URL"] = "postgresql://localhost/test"
        env_clean.pop("DB_POOL_MAX", None)

        with patch.dict(os.environ, env_clean, clear=True):
            importlib.reload(db_mod)
            db_mod._pool = None  # reset after reload
            with patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool) as mock_cls:
                db_mod._get_pool()
                args, kwargs = mock_cls.call_args
                self.assertEqual(kwargs.get("minconn", args[0] if args else None), 5)


class TestDefaultPoolMax(unittest.TestCase):
    """DB_POOL_MAX default is 50."""

    def test_default_pool_max_is_50(self):
        """_get_pool() passes maxconn=50 when DB_POOL_MAX is not set."""
        import importlib
        import src.db as db_mod

        db_mod._pool = None

        mock_pool = MagicMock()
        env_clean = {k: v for k, v in os.environ.items() if k not in ("DB_POOL_MAX", "DB_POOL_MIN")}
        env_clean["DATABASE_URL"] = "postgresql://localhost/test"

        with patch.dict(os.environ, env_clean, clear=True):
            importlib.reload(db_mod)
            db_mod._pool = None
            with patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool) as mock_cls:
                db_mod._get_pool()
                args, kwargs = mock_cls.call_args
                self.assertEqual(kwargs.get("maxconn", args[1] if len(args) > 1 else None), 50)


class TestPoolConfigFromEnvVars(unittest.TestCase):
    """Pool settings respect all documented env vars."""

    def _call_get_pool(self, env_overrides):
        """Helper: call _get_pool() with patched env, return the captured kwargs."""
        import importlib
        import src.db as db_mod

        db_mod._pool = None
        mock_pool = MagicMock()

        base_env = {k: v for k, v in os.environ.items()
                    if k not in ("DB_POOL_MIN", "DB_POOL_MAX", "DB_CONNECT_TIMEOUT")}
        base_env["DATABASE_URL"] = "postgresql://localhost/test"
        base_env.update(env_overrides)

        with patch.dict(os.environ, base_env, clear=True):
            importlib.reload(db_mod)
            db_mod._pool = None
            with patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool) as mock_cls:
                db_mod._get_pool()
                _, kwargs = mock_cls.call_args
                return kwargs

    def test_pool_config_from_env_vars(self):
        """DB_POOL_MIN, DB_POOL_MAX, and DB_CONNECT_TIMEOUT are all forwarded."""
        kwargs = self._call_get_pool({
            "DB_POOL_MIN": "10",
            "DB_POOL_MAX": "100",
            "DB_CONNECT_TIMEOUT": "5",
        })
        self.assertEqual(kwargs["minconn"], 10)
        self.assertEqual(kwargs["maxconn"], 100)
        self.assertEqual(kwargs["connect_timeout"], 5)

    def test_custom_min_only(self):
        """Only DB_POOL_MIN overridden — max keeps default of 50."""
        kwargs = self._call_get_pool({"DB_POOL_MIN": "8"})
        self.assertEqual(kwargs["minconn"], 8)
        self.assertEqual(kwargs["maxconn"], 50)

    def test_custom_max_only(self):
        """Only DB_POOL_MAX overridden — min keeps default of 5."""
        kwargs = self._call_get_pool({"DB_POOL_MAX": "80"})
        self.assertEqual(kwargs["minconn"], 5)
        self.assertEqual(kwargs["maxconn"], 80)


class TestPoolExhaustionWarning(unittest.TestCase):
    """_check_pool_exhaustion_warning() emits WARNING at >= threshold."""

    def setUp(self):
        import importlib
        import src.db as db_mod
        importlib.reload(db_mod)
        self.db_mod = db_mod

    def _make_mock_pool(self, maxconn, used_count):
        pool = MagicMock()
        pool.maxconn = maxconn
        pool._used = set(range(used_count))  # simulate used connections
        return pool

    def test_warning_fires_at_80_percent(self):
        """Warning emitted when 80% of max connections are in use."""
        pool = self._make_mock_pool(maxconn=50, used_count=40)  # 80%
        env = {k: v for k, v in os.environ.items() if k != "DB_POOL_WARN_THRESHOLD"}

        with patch.dict(os.environ, env, clear=True):
            with self.assertLogs("src.db", level="WARNING") as cm:
                self.db_mod._check_pool_exhaustion_warning(pool)

        self.assertTrue(any("exhaustion" in line.lower() or "near" in line.lower() for line in cm.output))

    def test_warning_fires_above_threshold(self):
        """Warning emitted when utilization > 80%."""
        pool = self._make_mock_pool(maxconn=50, used_count=45)  # 90%
        env = {k: v for k, v in os.environ.items() if k != "DB_POOL_WARN_THRESHOLD"}

        with patch.dict(os.environ, env, clear=True):
            with self.assertLogs("src.db", level="WARNING") as cm:
                self.db_mod._check_pool_exhaustion_warning(pool)

        self.assertTrue(any("exhaustion" in line.lower() or "near" in line.lower() for line in cm.output))

    def test_no_warning_below_threshold(self):
        """No WARNING logged when utilization < 80%."""
        pool = self._make_mock_pool(maxconn=50, used_count=30)  # 60%
        env = {k: v for k, v in os.environ.items() if k != "DB_POOL_WARN_THRESHOLD"}

        with patch.dict(os.environ, env, clear=True):
            with self.assertLogs("src.db", level="WARNING") as cm_outer:
                # Emit a harmless warning so assertLogs doesn't raise on empty
                logging.getLogger("src.db").warning("sentinel")
            # Now check that _check_pool_exhaustion_warning produces nothing extra
            import io
            handler = logging.handlers_hack = None
            logger = logging.getLogger("src.db")
            original_level = logger.level

            captured = []

            class CapturingHandler(logging.Handler):
                def emit(self, record):
                    captured.append(record)

            ch = CapturingHandler()
            ch.setLevel(logging.WARNING)
            logger.addHandler(ch)
            try:
                self.db_mod._check_pool_exhaustion_warning(pool)
            finally:
                logger.removeHandler(ch)

            exhaustion_records = [r for r in captured if "exhaustion" in r.getMessage().lower()
                                  or "near" in r.getMessage().lower()]
            self.assertEqual(len(exhaustion_records), 0,
                             f"Expected no exhaustion warning but got: {[r.getMessage() for r in exhaustion_records]}")

    def test_custom_threshold_respected(self):
        """DB_POOL_WARN_THRESHOLD env var overrides the 0.8 default."""
        pool = self._make_mock_pool(maxconn=50, used_count=30)  # 60%

        # With threshold=0.5, 60% should trigger a warning
        with patch.dict(os.environ, {"DB_POOL_WARN_THRESHOLD": "0.5"}, clear=False):
            with self.assertLogs("src.db", level="WARNING") as cm:
                self.db_mod._check_pool_exhaustion_warning(pool)

        self.assertTrue(any("exhaustion" in line.lower() or "near" in line.lower() for line in cm.output))

    def test_warning_includes_utilization_stats(self):
        """Warning log contains used count, max conn, and percentage."""
        pool = self._make_mock_pool(maxconn=50, used_count=40)  # 80%
        env = {k: v for k, v in os.environ.items() if k != "DB_POOL_WARN_THRESHOLD"}

        with patch.dict(os.environ, env, clear=True):
            with self.assertLogs("src.db", level="WARNING") as cm:
                self.db_mod._check_pool_exhaustion_warning(pool)

        warning_text = " ".join(cm.output)
        # Should mention the counts
        self.assertIn("40", warning_text)
        self.assertIn("50", warning_text)

    def test_no_crash_on_missing_pool_internals(self):
        """Warning check is silent when pool lacks _used attribute."""
        pool = MagicMock(spec=[])  # no _used attribute
        pool.maxconn = 50

        # Should not raise
        try:
            self.db_mod._check_pool_exhaustion_warning(pool)
        except Exception as e:
            self.fail(f"_check_pool_exhaustion_warning raised unexpectedly: {e}")


if __name__ == "__main__":
    unittest.main()
