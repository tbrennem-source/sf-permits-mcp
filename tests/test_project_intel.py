"""Tests for Project Intelligence tools.

Tests:
- run_query: rejects INSERT/DELETE/DROP, accepts SELECT, respects limit, timeout
- read_source: rejects path traversal, reads .py files, line range works
- search_source: finds known pattern, respects max_results
- schema_info: lists tables, shows columns for specific table
- list_tests: finds test files, pattern filter works
"""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# ── run_query tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_query_rejects_insert():
    from src.tools.project_intel import run_query
    result = await run_query("INSERT INTO users (email) VALUES ('x')")
    assert "Error" in result
    assert "not allowed" in result.lower() or "SELECT" in result


@pytest.mark.asyncio
async def test_run_query_rejects_delete():
    from src.tools.project_intel import run_query
    result = await run_query("DELETE FROM users WHERE 1=1")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_drop():
    from src.tools.project_intel import run_query
    result = await run_query("DROP TABLE users")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_update():
    from src.tools.project_intel import run_query
    result = await run_query("UPDATE users SET email = 'hacked'")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_truncate():
    from src.tools.project_intel import run_query
    result = await run_query("TRUNCATE TABLE users")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_alter():
    from src.tools.project_intel import run_query
    result = await run_query("ALTER TABLE users ADD COLUMN pwned TEXT")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_create():
    from src.tools.project_intel import run_query
    result = await run_query("CREATE TABLE evil (id INT)")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_rejects_comment_disguised_write():
    """Reject queries that hide write ops after comments."""
    from src.tools.project_intel import run_query
    result = await run_query("-- SELECT * FROM users\nDELETE FROM users")
    assert "Error" in result


@pytest.mark.asyncio
async def test_run_query_accepts_select():
    """SELECT should pass validation and execute against mock DB."""
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.description = [("count",)]
        mock_cursor.fetchall.return_value = [(42,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.project_intel.BACKEND", "postgres"):
            from src.tools.project_intel import run_query
            result = await run_query("SELECT COUNT(*) FROM permits")

        assert "42" in result
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_run_query_accepts_with_cte():
    """WITH (CTE) queries should be accepted."""
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.description = [("n",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.project_intel.BACKEND", "postgres"):
            from src.tools.project_intel import run_query
            result = await run_query("WITH x AS (SELECT 1 AS n) SELECT * FROM x")

        assert "1" in result


@pytest.mark.asyncio
async def test_run_query_respects_limit():
    """User-specified LIMIT should be capped at the tool's max."""
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        mock_cursor = MagicMock()
        mock_cursor.description = [("id",)]
        mock_cursor.fetchall.return_value = [(1,)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        with patch("src.tools.project_intel.BACKEND", "postgres"):
            from src.tools.project_intel import run_query
            # User asks for LIMIT 5000 but tool max is 50
            result = await run_query("SELECT id FROM permits LIMIT 5000", limit=50)

        # The SQL sent should have LIMIT 50, not 5000
        executed_sql = mock_cursor.execute.call_args[0][0]
        assert "LIMIT 50" in executed_sql


@pytest.mark.asyncio
async def test_run_query_no_false_positive_on_column_names():
    """Column names like 'deleted_at' or 'update_count' should not be rejected."""
    from src.tools.project_intel import _strip_sql_comments, _FORBIDDEN_SQL
    sql = "SELECT deleted_at, update_count, created_by FROM permits"
    clean = _strip_sql_comments(sql)
    # The word-boundary regex should NOT match these
    # deleted_at contains DELETE but \bDELETE\b won't match "deleted_at"
    # update_count contains UPDATE but \bUPDATE\b won't match "update_count"
    match = _FORBIDDEN_SQL.search(clean)
    assert match is None, f"False positive on: {match.group()}"


# ── read_source tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_read_source_rejects_absolute_path():
    from src.tools.project_intel import read_source
    result = await read_source("/etc/passwd")
    assert "Error" in result
    assert "Absolute" in result


@pytest.mark.asyncio
async def test_read_source_rejects_path_traversal():
    from src.tools.project_intel import read_source
    result = await read_source("../../../etc/passwd")
    assert "Error" in result
    assert "traversal" in result.lower() or ".." in result


@pytest.mark.asyncio
async def test_read_source_reads_py_file():
    """Should read a known .py file from the repo."""
    from src.tools.project_intel import read_source
    result = await read_source("src/db.py")
    assert "db.py" in result
    assert "Database connection" in result or "get_connection" in result


@pytest.mark.asyncio
async def test_read_source_line_range():
    from src.tools.project_intel import read_source
    result = await read_source("src/db.py", line_start=1, line_end=5)
    assert "lines 1-5" in result
    # Should have exactly 5 numbered lines
    lines = [l for l in result.split("\n") if l.strip().startswith(("1 |", "2 |", "3 |", "4 |", "5 |"))]
    assert len(lines) == 5


@pytest.mark.asyncio
async def test_read_source_rejects_binary():
    """Should reject non-allowed file extensions."""
    from src.tools.project_intel import read_source
    result = await read_source("data/sf_permits.duckdb")
    assert "Error" in result
    assert "not supported" in result.lower() or "not found" in result.lower()


@pytest.mark.asyncio
async def test_read_source_nonexistent_file():
    from src.tools.project_intel import read_source
    result = await read_source("src/does_not_exist.py")
    assert "Error" in result
    assert "not found" in result.lower()


# ── search_source tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_source_finds_known_pattern():
    """Should find 'def get_connection' — only defined in src/db.py."""
    from src.tools.project_intel import search_source
    result = await search_source("def get_connection", "*.py", max_results=5)
    assert "get_connection" in result
    assert "src/db.py" in result


@pytest.mark.asyncio
async def test_search_source_respects_max_results():
    """Should not return more than max_results matches."""
    from src.tools.project_intel import search_source
    result = await search_source("import", "*.py", max_results=3)
    # Count lines in the code block (exclude header/footer)
    code_block = result.split("```")[1] if "```" in result else ""
    lines = [l for l in code_block.strip().splitlines() if l.strip()]
    assert len(lines) <= 3


@pytest.mark.asyncio
async def test_search_source_no_match():
    from src.tools.project_intel import search_source
    # Use a pattern that won't appear even in this test file — by searching
    # only in .sql files (where this string definitely doesn't exist)
    result = await search_source("xyzzy_impossible_match_999", "*.sql")
    assert "No matches" in result


# ── schema_info tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schema_info_lists_tables():
    """Should list tables when no table arg given."""
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        # DuckDB SHOW TABLES returns list of single-element tuples
        mock_conn.execute.return_value.fetchall.side_effect = [
            [("permits",), ("users",), ("contacts",)],  # SHOW TABLES
            [(100,)],  # COUNT for permits
            [(50,)],   # COUNT for users
            [(200,)],  # COUNT for contacts
        ]

        with patch("src.tools.project_intel.BACKEND", "duckdb"):
            from src.tools.project_intel import schema_info
            result = await schema_info()

        assert "permits" in result
        assert "users" in result
        assert "contacts" in result
        assert "3 tables" in result
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_schema_info_describes_table():
    """Should show columns for a specific table."""
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        # DuckDB DESCRIBE returns tuples: (name, type, null, key, default, extra)
        mock_conn.execute.return_value.fetchall.side_effect = [
            [
                ("permit_number", "VARCHAR", "NO", "PRI", None, None),
                ("status", "VARCHAR", "YES", None, None, None),
            ],  # DESCRIBE
            [(1000,)],  # COUNT
        ]

        with patch("src.tools.project_intel.BACKEND", "duckdb"):
            from src.tools.project_intel import schema_info
            result = await schema_info(table="permits")

        assert "permit_number" in result
        assert "status" in result
        assert "VARCHAR" in result
        mock_conn.close.assert_called_once()


@pytest.mark.asyncio
async def test_schema_info_rejects_invalid_table_name():
    from src.tools.project_intel import schema_info
    # SQL injection attempt
    with patch("src.tools.project_intel.get_connection") as mock_conn_fn:
        mock_conn = MagicMock()
        mock_conn_fn.return_value = mock_conn

        result = await schema_info(table="users; DROP TABLE users")
        assert "Error" in result
        assert "Invalid" in result


# ── list_tests tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tests_finds_files():
    """Should find test files in the tests/ directory."""
    from src.tools.project_intel import list_tests
    result = await list_tests()
    assert "test_" in result
    assert "Test Files" in result


@pytest.mark.asyncio
async def test_list_tests_pattern_filter():
    """Should filter by pattern."""
    from src.tools.project_intel import list_tests
    result = await list_tests(pattern="addenda")
    assert "addenda" in result.lower()
    # Should NOT include unrelated files
    assert "test_vision_client" not in result


@pytest.mark.asyncio
async def test_list_tests_pattern_no_match():
    from src.tools.project_intel import list_tests
    result = await list_tests(pattern="xyzzy_nonexistent_12345")
    assert "No test files" in result
