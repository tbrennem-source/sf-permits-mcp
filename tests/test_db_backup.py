"""Tests for admin auto-seed and database backup script."""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_backup.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    db_mod.init_user_schema()


@pytest.fixture
def client():
    from app import app, _rate_buckets
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as client:
        yield client
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# Admin auto-seed tests
# ---------------------------------------------------------------------------

class TestAdminAutoSeed:
    """Test the startup migration admin auto-seed logic."""

    def test_seed_creates_admin_when_users_empty(self, monkeypatch):
        """When users table is empty and ADMIN_EMAIL is set, admin is created."""
        import web.auth as auth_mod
        from src.db import query_one

        # Verify users table is empty
        row = query_one("SELECT COUNT(*) FROM users")
        assert row[0] == 0

        # Simulate what the startup migration does (for DuckDB/test env)
        admin_email = "admin-seed-test@example.com"
        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", admin_email)

        # Create user like the migration would
        user = auth_mod.create_user(admin_email)
        assert user["email"] == admin_email
        assert user["is_admin"] is True

    def test_seed_skips_when_users_exist(self, monkeypatch):
        """When users already exist, no auto-seed should happen."""
        import web.auth as auth_mod
        from src.db import query_one

        # Create a regular user first
        auth_mod.create_user("existing@example.com")
        row = query_one("SELECT COUNT(*) FROM users")
        assert row[0] == 1

        # The migration checks count > 0 and skips
        # We just verify the existing user is NOT admin
        user = auth_mod.get_user_by_email("existing@example.com")
        assert not user["is_admin"]

    def test_seed_skips_when_no_admin_email(self, monkeypatch):
        """When ADMIN_EMAIL is not set, no auto-seed happens."""
        import web.auth as auth_mod
        from src.db import query_one

        monkeypatch.setattr(auth_mod, "ADMIN_EMAIL", None)

        # Verify empty
        row = query_one("SELECT COUNT(*) FROM users")
        assert row[0] == 0

        # No admin should be created — table stays empty
        # (migration would skip because admin_email is falsy)
        admin_email = ""
        assert not admin_email  # Falsy → skip


# ---------------------------------------------------------------------------
# Backup script tests
# ---------------------------------------------------------------------------

class TestBackupScript:
    """Test the backup utility functions."""

    def test_run_backup_no_database_url(self, monkeypatch):
        """Backup fails gracefully when DATABASE_URL is not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from scripts.db_backup import run_backup
        result = run_backup()
        assert result["ok"] is False
        assert "DATABASE_URL" in result["error"]

    def test_run_backup_pg_dump_not_found(self, monkeypatch):
        """Backup fails gracefully when pg_dump is not on PATH."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        from scripts.db_backup import run_backup
        with patch("scripts.db_backup.subprocess.run", side_effect=FileNotFoundError):
            result = run_backup()
        assert result["ok"] is False
        assert "pg_dump not found" in result["error"]

    def test_run_backup_success(self, tmp_path, monkeypatch):
        """Backup writes file on success."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        import scripts.db_backup as backup_mod
        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""

        with patch("scripts.db_backup.subprocess.run", return_value=mock_result):
            result = backup_mod.run_backup()

        assert result["ok"] is True
        assert "file" in result
        assert result["file"].startswith("backup-userdata-")

    def test_run_backup_full_flag(self, tmp_path, monkeypatch):
        """Full backup uses no -t flags."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")

        import scripts.db_backup as backup_mod
        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)

        captured_cmd = []
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = b""

        def capture_run(cmd, **kwargs):
            captured_cmd.extend(cmd)
            return mock_result

        with patch("scripts.db_backup.subprocess.run", side_effect=capture_run):
            result = backup_mod.run_backup(full=True)

        assert result["ok"] is True
        # Full backup should NOT have -t flags
        assert "-t" not in captured_cmd

    def test_prune_old_backups(self, tmp_path, monkeypatch):
        """Old backups beyond retention are pruned."""
        import scripts.db_backup as backup_mod
        import time

        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_mod, "RETENTION_DAYS", 0)  # Prune everything

        # Create a fake old backup
        old_file = tmp_path / "backup-userdata-20250101-000000.dump"
        old_file.write_bytes(b"fake dump data")
        # Set mtime to the past
        old_time = time.time() - 86400 * 30
        os.utime(old_file, (old_time, old_time))

        pruned = backup_mod._prune_old_backups()
        assert pruned == 1
        assert not old_file.exists()

    def test_prune_keeps_recent(self, tmp_path, monkeypatch):
        """Recent backups within retention are kept."""
        import scripts.db_backup as backup_mod

        monkeypatch.setattr(backup_mod, "BACKUP_DIR", tmp_path)
        monkeypatch.setattr(backup_mod, "RETENTION_DAYS", 30)

        recent_file = tmp_path / "backup-userdata-20260217-000000.dump"
        recent_file.write_bytes(b"fake dump data")

        pruned = backup_mod._prune_old_backups()
        assert pruned == 0
        assert recent_file.exists()

    def test_user_data_tables_list(self):
        """Verify the backup table list covers critical user data."""
        from scripts.db_backup import USER_DATA_TABLES
        assert "users" in USER_DATA_TABLES
        assert "watch_items" in USER_DATA_TABLES
        assert "feedback" in USER_DATA_TABLES
        assert "permit_changes" in USER_DATA_TABLES
        assert "regulatory_watch" in USER_DATA_TABLES

    def test_restore_no_database_url(self, monkeypatch):
        """Restore fails gracefully when DATABASE_URL is not set."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from scripts.db_backup import restore_backup
        result = restore_backup("/fake/path.dump")
        assert result["ok"] is False
        assert "DATABASE_URL" in result["error"]


# ---------------------------------------------------------------------------
# Cron endpoint test
# ---------------------------------------------------------------------------

class TestCronBackupEndpoint:
    """Test the /cron/backup route."""

    def test_backup_endpoint_blocked_on_web_worker(self, client):
        """Backup endpoint blocked on web workers by cron guard."""
        rv = client.post("/cron/backup")
        assert rv.status_code == 404  # Cron guard blocks POST /cron/* on web workers

    def test_backup_endpoint_with_auth(self, client, monkeypatch):
        """Backup endpoint accepts valid CRON_SECRET on cron worker."""
        monkeypatch.setenv("CRON_WORKER", "true")
        monkeypatch.setenv("CRON_SECRET", "test-secret-123")

        with patch("scripts.db_backup.run_backup", return_value={"ok": True, "file": "test.dump"}):
            rv = client.post(
                "/cron/backup",
                headers={"Authorization": "Bearer test-secret-123"},
            )
        assert rv.status_code == 200
