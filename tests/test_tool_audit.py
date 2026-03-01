"""Tests for tool security hardening and audit requirements."""
import pytest


def test_run_query_blocks_users_table():
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT * FROM users WHERE id = 1")
    assert result is not None
    assert "denied" in result.lower()


def test_run_query_allows_permits_table():
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT permit_number FROM permits LIMIT 10")
    assert result is None


def test_run_query_blocks_pg_system_tables():
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT * FROM pg_tables")
    assert result is not None


def test_run_query_blocks_auth_tokens():
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT token FROM auth_tokens")
    assert result is not None


def test_run_query_blocks_oauth_tables():
    from src.tools.project_intel import _check_table_allowlist
    for table in ["mcp_oauth_clients", "mcp_oauth_codes", "mcp_oauth_tokens"]:
        result = _check_table_allowlist(f"SELECT * FROM {table}")
        assert result is not None, f"Should block {table}"


def test_read_source_blocks_claude_md():
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("CLAUDE.md")
    assert result is not None
    assert "denied" in result.lower()


def test_read_source_blocks_sprint_prompts():
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("sprint-prompts/qs13-t2-oauth.md")
    assert result is not None


def test_read_source_allows_normal_files():
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("src/server.py")
    assert result is None


def test_list_feedback_restriction_env():
    """list_feedback returns error when MCP_RESTRICT_FEEDBACK=1."""
    import os
    import asyncio
    import inspect
    import importlib
    from unittest.mock import patch

    with patch.dict(os.environ, {"MCP_RESTRICT_FEEDBACK": "1"}):
        import src.tools.list_feedback as lf
        importlib.reload(lf)

        if inspect.iscoroutinefunction(lf.list_feedback):
            result = asyncio.run(lf.list_feedback())
        else:
            result = lf.list_feedback()

    assert "insufficient permissions" in result.lower() or "professional" in result.lower()
