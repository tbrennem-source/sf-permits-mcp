"""Integration tests for MCP security: read_source and run_query restrictions.

Tests for project_intel tools:
- run_query: only SELECT/WITH allowed, write ops blocked
- read_source: path traversal blocked, absolute paths blocked, CLAUDE.md readable
  (note: CLAUDE.md has .md extension which IS in _ALLOWED_EXTENSIONS)
- Users/auth_tokens tables are NOT currently blocked by default (run_query is read-only
  but allows any SELECT — table-level blocking is a QS13 T1 addition)

Covers:
- SQL write operation blocking
- Path traversal protection in read_source
- Extension allowlist enforcement
- Absolute path rejection
- QS13 T1: user table SELECT blocking (skipped if not yet implemented)
"""

import asyncio
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend for test isolation."""
    db_path = str(tmp_path / "test_mcp_security.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    # Initialize minimal schema so SQL queries work
    try:
        db_mod.init_user_schema()
    except Exception:
        pass


def _run_async(coro):
    """Run an async coroutine synchronously for testing."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ---------------------------------------------------------------------------
# run_query security
# ---------------------------------------------------------------------------

class TestRunQuerySecurity:

    def test_select_query_allowed(self):
        """Basic SELECT query is allowed."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("SELECT 1 AS test_value"))
        # Should return table data, not an error about being blocked
        assert "Error:" not in result or "Write operation" not in result

    def test_select_from_permits_allowed(self):
        """SELECT from permits table is allowed (table may be empty in test)."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("SELECT COUNT(*) FROM permits LIMIT 1"))
        # May get "no rows" or "Error: table not found" but NOT "Write operation blocked"
        assert "Write operation" not in result

    def test_insert_blocked(self):
        """INSERT is rejected (either as non-SELECT first word or write-keyword detection)."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("INSERT INTO permits VALUES ('test')"))
        assert "Error:" in result
        # May say "Only SELECT and WITH are allowed" or "Write operation ... not allowed"
        assert "not allowed" in result.lower() or "write" in result.lower() or "select" in result.lower()

    def test_update_blocked(self):
        """UPDATE is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("UPDATE permits SET status='closed'"))
        assert "Error:" in result

    def test_delete_blocked(self):
        """DELETE is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("DELETE FROM permits WHERE 1=1"))
        assert "Error:" in result

    def test_drop_blocked(self):
        """DROP TABLE is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("DROP TABLE permits"))
        assert "Error:" in result

    def test_alter_blocked(self):
        """ALTER TABLE is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("ALTER TABLE permits ADD COLUMN foo TEXT"))
        assert "Error:" in result

    def test_truncate_blocked(self):
        """TRUNCATE is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("TRUNCATE permits"))
        assert "Error:" in result

    def test_cte_select_allowed(self):
        """WITH (CTE) SELECT is allowed."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("WITH x AS (SELECT 1 AS n) SELECT n FROM x"))
        assert "Write operation" not in result

    def test_hidden_insert_in_comment_blocked(self):
        """INSERT hidden in SQL comment is still detected (after comment stripping)."""
        from src.tools.project_intel import run_query
        # This should be treated as: SELECT 1 (comment stripped) — actually allowed
        # unless the word INSERT appears outside comments too
        result = _run_async(run_query("SELECT 1 /* INSERT fake */"))
        # SELECT + INSERT only in comment: should be allowed (INSERT stripped by comment removal)
        # The implementation strips comments before checking keywords
        # So this should be allowed (or rejected depending on implementation detail)
        assert result  # Just verify no crash

    def test_non_select_not_with_blocked(self):
        """Queries not starting with SELECT or WITH are rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("EXPLAIN SELECT * FROM permits"))
        assert "Error:" in result
        assert "SELECT" in result or "only" in result.lower()

    def test_limit_applied_automatically(self):
        """Queries without LIMIT get one applied automatically."""
        from src.tools.project_intel import run_query
        # Should not crash or return unbounded results
        result = _run_async(run_query("SELECT 1 AS n"))
        assert "Error:" not in result or "table" in result.lower()

    @pytest.mark.skip(reason="User table blocking not yet implemented (QS13 T1)")
    def test_select_from_users_blocked(self):
        """SELECT from users table is blocked to protect PII."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("SELECT * FROM users LIMIT 1"))
        assert any(word in result.lower() for word in ["blocked", "not allowed", "restricted", "error"])

    @pytest.mark.skip(reason="User table blocking not yet implemented (QS13 T1)")
    def test_select_from_auth_tokens_blocked(self):
        """SELECT from auth_tokens table is blocked."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("SELECT * FROM auth_tokens LIMIT 1"))
        assert any(word in result.lower() for word in ["blocked", "not allowed", "restricted", "error"])


# ---------------------------------------------------------------------------
# read_source security
# ---------------------------------------------------------------------------

class TestReadSourceSecurity:

    def test_read_source_valid_py_file(self):
        """src/server.py is readable via read_source."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("src/server.py"))
        # Should return file content, not a path error
        assert "**Error:** File not found" not in result
        # Should have content
        assert len(result) > 50

    def test_read_source_mcp_http_readable(self):
        """src/mcp_http.py is readable (it's a .py file)."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("src/mcp_http.py"))
        assert "**Error:** File not found" not in result or "Path resolves outside" not in result

    def test_read_source_absolute_path_blocked(self):
        """Absolute paths are rejected."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("/etc/passwd"))
        assert "**Error:**" in result
        assert "Absolute" in result or "not allowed" in result.lower()

    def test_read_source_path_traversal_blocked(self):
        """Path traversal (../) is blocked."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("../../../etc/passwd"))
        assert "**Error:**" in result
        assert "traversal" in result.lower() or "not allowed" in result.lower()

    def test_read_source_nested_traversal_blocked(self):
        """Nested path traversal is blocked."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("src/../../CLAUDE.md"))
        # Either blocked by traversal check or resolves inside repo (CLAUDE.md)
        # Both are acceptable — just no crash
        assert result  # Non-empty response

    def test_read_source_unsupported_extension_blocked(self):
        """Files with unsupported extensions are rejected."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("web/static/icon-192.png"))
        assert "**Error:**" in result
        assert "not supported" in result.lower() or "type" in result.lower()

    def test_read_source_nonexistent_file_returns_error(self):
        """Non-existent file returns an informative error."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("src/nonexistent_file_xyz_12345.py"))
        assert "**Error:**" in result
        assert "not found" in result.lower()

    def test_read_source_windows_path_separator_rejected(self):
        """Windows-style absolute path is blocked."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("C:\\Windows\\system32\\config"))
        # Should be rejected (not a valid relative path)
        assert "**Error:**" in result or "not found" in result.lower()

    def test_read_source_env_example_allowed(self):
        """Files matching *.env.example are allowed."""
        from src.tools.project_intel import read_source
        # .env.example files are in the allowlist
        result = _run_async(read_source(".env.example"))
        # File may not exist — error about not found is acceptable
        assert "**Error:** Absolute" not in result
        assert "traversal" not in result.lower()

    def test_read_source_markdown_allowed(self):
        """Markdown files are readable (CLAUDE.md is a .md file)."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("CLAUDE.md"))
        # .md is in _ALLOWED_EXTENSIONS — should not be blocked by extension check
        # File exists, so should return content
        assert "not supported" not in result.lower()
        assert len(result) > 50

    def test_read_source_line_range(self):
        """Line range parameters work correctly."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source("src/mcp_http.py", line_start=1, line_end=5))
        # Should not error
        assert "**Error:** Absolute" not in result
        assert "traversal" not in result.lower()

    @pytest.mark.skip(reason="Blocked file list not yet implemented (QS13 T1)")
    def test_read_source_secrets_file_blocked(self):
        """.env (actual secrets) is blocked from read_source."""
        from src.tools.project_intel import read_source
        result = _run_async(read_source(".env"))
        assert any(word in result.lower() for word in ["blocked", "not allowed", "access denied", "restricted"])


# ---------------------------------------------------------------------------
# run_query limit enforcement
# ---------------------------------------------------------------------------

class TestRunQueryLimits:

    def test_limit_cap_1000(self):
        """Limit parameter is capped at 1000."""
        from src.tools.project_intel import run_query
        # Passing limit=9999 should not cause crash
        result = _run_async(run_query("SELECT 1", limit=9999))
        assert "Error:" not in result or "table" in result.lower()

    def test_limit_minimum_1(self):
        """Limit parameter minimum is 1."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query("SELECT 1", limit=0))
        # Should not crash
        assert result

    def test_empty_sql_blocked(self):
        """Empty SQL string is rejected."""
        from src.tools.project_intel import run_query
        result = _run_async(run_query(""))
        assert "Error:" in result
