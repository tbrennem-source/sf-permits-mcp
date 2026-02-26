"""Tests for scripts/run_prod_migrations.py.

These tests use mocks so no real database connection is needed.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import pytest

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.run_prod_migrations import (
    Migration,
    MIGRATIONS,
    MIGRATION_BY_NAME,
    run_migrations,
    main,
)


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


class TestMigrationRegistry:
    def test_migration_count(self):
        """Thirteen migrations in the registry (Sprint 56D + Sprint 57.0 + Sprint 61B)."""
        assert len(MIGRATIONS) == 13

    def test_all_have_names(self):
        """Every migration has a non-empty name."""
        for m in MIGRATIONS:
            assert m.name, f"Migration has empty name: {m}"

    def test_all_have_descriptions(self):
        """Every migration has a non-empty description."""
        for m in MIGRATIONS:
            assert m.description, f"Migration {m.name} has empty description"

    def test_all_have_callables(self):
        """Every migration run attribute is callable."""
        for m in MIGRATIONS:
            assert callable(m.run), f"Migration {m.name}.run is not callable"

    def test_names_are_unique(self):
        """No duplicate migration names."""
        names = [m.name for m in MIGRATIONS]
        assert len(names) == len(set(names))

    def test_by_name_lookup(self):
        """MIGRATION_BY_NAME contains all migrations."""
        for m in MIGRATIONS:
            assert m.name in MIGRATION_BY_NAME
            assert MIGRATION_BY_NAME[m.name] is m

    def test_expected_migration_names(self):
        """Specific named migrations exist."""
        expected = {
            "schema",
            "user_tables",
            "activity_tables",
            "changes_table",
            "brief_email",
            "invite_code",
            "signals",
            "cron_log_columns",
            "reference_tables",
            "inspections_unique",
            "shareable_analysis",
            "neighborhood_backfill",
            "sprint61b_teams",
        }
        actual = {m.name for m in MIGRATIONS}
        assert expected == actual

    def test_reference_tables_before_inspections(self):
        """'reference_tables' runs before 'inspections_unique'."""
        names = [m.name for m in MIGRATIONS]
        ref_idx = names.index("reference_tables")
        insp_idx = names.index("inspections_unique")
        assert ref_idx < insp_idx

    def test_inspections_unique_before_shareable(self):
        """'inspections_unique' runs before 'shareable_analysis'."""
        names = [m.name for m in MIGRATIONS]
        insp_idx = names.index("inspections_unique")
        share_idx = names.index("shareable_analysis")
        assert insp_idx < share_idx

    def test_shareable_before_neighborhood_backfill(self):
        """'shareable_analysis' runs before 'neighborhood_backfill'."""
        names = [m.name for m in MIGRATIONS]
        share_idx = names.index("shareable_analysis")
        backfill_idx = names.index("neighborhood_backfill")
        assert share_idx < backfill_idx

    def test_neighborhood_backfill_is_last(self):
        """'sprint61b_teams' migration is last in registry (after neighborhood_backfill)."""
        names = [m.name for m in MIGRATIONS]
        assert names[-1] == "sprint61b_teams"

    def test_schema_is_first(self):
        """'schema' migration runs first."""
        assert MIGRATIONS[0].name == "schema"


# ---------------------------------------------------------------------------
# run_migrations tests
# ---------------------------------------------------------------------------


def _make_ok_migration(name: str) -> Migration:
    return Migration(name=name, description=f"Test {name}", run=lambda: {"ok": True})


def _make_fail_migration(name: str, error: str = "DB error") -> Migration:
    return Migration(name=name, description=f"Test {name}",
                     run=lambda: {"ok": False, "error": error})


def _make_skipped_migration(name: str) -> Migration:
    return Migration(name=name, description=f"Test {name}",
                     run=lambda: {"ok": True, "skipped": True, "reason": "DuckDB mode"})


def _make_exception_migration(name: str) -> Migration:
    def _fail():
        raise RuntimeError("unhandled exception")
    return Migration(name=name, description=f"Test {name}", run=_fail)


class TestRunMigrations:
    def test_all_succeed(self):
        migs = [_make_ok_migration(f"m{i}") for i in range(3)]
        succeeded, failed = run_migrations(migs)
        assert succeeded == 3
        assert failed == 0

    def test_one_fails(self):
        migs = [
            _make_ok_migration("ok1"),
            _make_fail_migration("bad1"),
            _make_ok_migration("ok2"),
        ]
        succeeded, failed = run_migrations(migs)
        assert succeeded == 2
        assert failed == 1

    def test_all_fail(self):
        migs = [_make_fail_migration(f"bad{i}") for i in range(3)]
        succeeded, failed = run_migrations(migs)
        assert succeeded == 0
        assert failed == 3

    def test_skipped_counts_as_success(self):
        migs = [_make_skipped_migration("duckdb_skip")]
        succeeded, failed = run_migrations(migs)
        assert succeeded == 1
        assert failed == 0

    def test_exception_counts_as_failure(self):
        migs = [_make_exception_migration("exc1")]
        succeeded, failed = run_migrations(migs)
        assert succeeded == 0
        assert failed == 1

    def test_dry_run_does_not_call_run(self):
        called = []
        def track():
            called.append(1)
            return {"ok": True}
        mig = Migration(name="track", description="Tracking migration", run=track)
        run_migrations([mig], dry_run=True)
        assert not called, "dry_run should not invoke .run()"

    def test_dry_run_counts_all_as_succeeded(self):
        migs = [_make_fail_migration(f"bad{i}") for i in range(5)]
        succeeded, failed = run_migrations(migs, dry_run=True)
        assert succeeded == 5
        assert failed == 0

    def test_empty_list(self):
        succeeded, failed = run_migrations([])
        assert succeeded == 0
        assert failed == 0

    def test_order_preserved(self):
        """Migrations run in the order given."""
        order = []
        def make_tracked(name):
            def run():
                order.append(name)
                return {"ok": True}
            return Migration(name=name, description=name, run=run)

        migs = [make_tracked(n) for n in ["a", "b", "c"]]
        run_migrations(migs)
        assert order == ["a", "b", "c"]

    def test_continues_after_failure(self):
        """A failed migration does not stop subsequent ones."""
        ran = []
        def make_ok(n):
            def run():
                ran.append(n)
                return {"ok": True}
            return Migration(name=n, description=n, run=run)
        def make_fail(n):
            def run():
                ran.append(n)
                return {"ok": False, "error": "DB error"}
            return Migration(name=n, description=n, run=run)

        migs = [make_ok("a"), make_fail("b"), make_ok("c")]
        run_migrations(migs)
        assert ran == ["a", "b", "c"]


# ---------------------------------------------------------------------------
# main() CLI tests
# ---------------------------------------------------------------------------



class TestMainCli:
    def test_list_flag(self, capsys):
        with patch("sys.argv", ["run_prod_migrations", "--list"]):
            exit_code = main()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "signals" in captured.out
        assert "schema" in captured.out

    def test_dry_run_flag(self, capsys):
        # Patch src.db import inside run_migrations
        fake_db = MagicMock()
        fake_db.BACKEND = "duckdb"
        with patch("sys.argv", ["run_prod_migrations", "--dry-run"]):
            with patch.dict("sys.modules", {"src.db": fake_db}):
                exit_code = main()
        assert exit_code == 0

    def test_unknown_only_returns_2(self):
        with patch("sys.argv", ["run_prod_migrations", "--only", "nonexistent"]):
            exit_code = main()
        assert exit_code == 2

    def test_only_known_migration(self):
        """--only with a valid migration name calls only that migration."""
        fake_db = MagicMock()
        fake_db.BACKEND = "duckdb"
        called = []

        def fake_run():
            called.append("signals")
            return {"ok": True, "skipped": True, "reason": "DuckDB"}

        fake_signals = Migration(name="signals", description="test", run=fake_run)
        fake_registry = {"signals": fake_signals}

        with patch("sys.argv", ["run_prod_migrations", "--only", "signals"]):
            with patch.dict("sys.modules", {"src.db": fake_db}):
                with patch("scripts.run_prod_migrations.MIGRATION_BY_NAME", fake_registry):
                    with patch("scripts.run_prod_migrations.MIGRATIONS", list(fake_registry.values())):
                        exit_code = main()

        assert exit_code == 0
        assert called == ["signals"]


# ---------------------------------------------------------------------------
# Individual migration SQL file wrappers
# ---------------------------------------------------------------------------


class TestSqlFileMigrations:
    """Test that SQL-file migrations skip when BACKEND != postgres."""

    def _test_skips_on_duckdb(self, migration_name: str):
        fake_db = MagicMock()
        fake_db.BACKEND = "duckdb"
        with patch.dict("sys.modules", {"src.db": fake_db}):
            from importlib import reload
            import scripts.run_prod_migrations as mod
            result = MIGRATION_BY_NAME[migration_name].run()
        # When the module doesn't actually reload, we test via _run_sql_file directly
        # by patching src.db in the module's namespace
        return result

    def test_user_tables_import(self):
        """_run_user_tables is importable and returns a dict."""
        from scripts.run_prod_migrations import _run_user_tables
        # Patch src.db to avoid real DB connection
        fake_db = MagicMock()
        fake_db.BACKEND = "duckdb"
        with patch.dict("sys.modules", {"src.db": fake_db}):
            # Re-import to get fresh binding
            import importlib
            import scripts.run_prod_migrations as mod
            importlib.reload(mod)
            result = mod._run_user_tables()
        assert isinstance(result, dict)
        assert "ok" in result

    def test_signals_migration_import(self):
        """_run_signals is importable and delegates to migrate_signals.run_migration."""
        fake_run = MagicMock(return_value={"ok": True, "tables": 4, "signal_types": 13})
        with patch("scripts.migrate_signals.run_migration", fake_run):
            from scripts.run_prod_migrations import _run_signals
            result = _run_signals()
        assert result["ok"] is True
        fake_run.assert_called_once()
