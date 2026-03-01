"""Tests for MCP tool security — run_query table allowlist and read_source path denylist.

Verifies that project intelligence tools block access to sensitive tables/files
and allow access to expected public data tables and source files.

These tests call the async tool functions directly via asyncio.run() — no Flask
client needed, no DB writes, no external I/O for the denylist/allowlist checks.
"""
import asyncio
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    """Run an async tool function synchronously."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# run_query — table allowlist
# ---------------------------------------------------------------------------

def test_run_query_blocks_users_table():
    """SELECT from users table is denied by the allowlist."""
    from src.tools.project_intel import run_query
    result = _run(run_query("SELECT * FROM users LIMIT 1"))
    assert "Access denied" in result or "Error" in result
    assert "users" in result.lower()


def test_run_query_blocks_auth_tokens():
    """SELECT from auth_tokens table is denied."""
    from src.tools.project_intel import run_query
    result = _run(run_query("SELECT * FROM auth_tokens LIMIT 1"))
    assert "Access denied" in result or "Error" in result


def test_run_query_blocks_beta_requests():
    """SELECT from beta_requests (sensitive PII) is denied."""
    from src.tools.project_intel import run_query
    result = _run(run_query("SELECT email FROM beta_requests LIMIT 5"))
    assert "Access denied" in result or "Error" in result


def test_run_query_blocks_feedback():
    """SELECT from feedback table is denied."""
    from src.tools.project_intel import run_query
    result = _run(run_query("SELECT * FROM feedback LIMIT 1"))
    assert "Access denied" in result or "Error" in result


def test_run_query_allows_permits_table():
    """SELECT from permits is in the allowlist — no security block."""
    from src.tools.project_intel import _check_table_allowlist
    # Test the allowlist check directly (no DB call needed)
    result = _check_table_allowlist("SELECT * FROM permits LIMIT 1")
    assert result is None, f"Expected None (allowed) but got: {result}"


def test_run_query_allows_contacts_table():
    """SELECT from contacts is in the allowlist."""
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT id FROM contacts LIMIT 1")
    assert result is None


def test_run_query_allows_inspections_table():
    """SELECT from inspections is in the allowlist."""
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT permit_number FROM inspections")
    assert result is None


def test_run_query_allows_cron_log():
    """SELECT from cron_log is in the allowlist (operational data, not PII)."""
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT * FROM cron_log LIMIT 10")
    assert result is None


def test_run_query_blocks_write_operations():
    """INSERT/UPDATE/DELETE are blocked regardless of table."""
    from src.tools.project_intel import run_query
    result = _run(run_query("INSERT INTO cron_log VALUES (1, 'now')"))
    assert "Error" in result


def test_run_query_blocks_mcp_oauth_clients():
    """SELECT from mcp_oauth_clients is denied."""
    from src.tools.project_intel import _check_table_allowlist
    result = _check_table_allowlist("SELECT * FROM mcp_oauth_clients")
    assert result is not None, "mcp_oauth_clients should be blocked"
    assert "Access denied" in result


# ---------------------------------------------------------------------------
# read_source — path denylist
# ---------------------------------------------------------------------------

def test_read_source_blocks_claude_md():
    """read_source blocks CLAUDE.md — contains sensitive project instructions."""
    from src.tools.project_intel import read_source
    result = _run(read_source("CLAUDE.md"))
    assert "Access denied" in result or "Error" in result


def test_read_source_blocks_claude_md_relative():
    """read_source blocks ./CLAUDE.md variant."""
    from src.tools.project_intel import _check_path_allowed
    # The function normalizes leading slashes; test the raw pattern
    result = _check_path_allowed("CLAUDE.md")
    assert result is not None, "CLAUDE.md should be denied"


def test_read_source_blocks_sprint_prompts():
    """read_source blocks sprint-prompts/ directory — contains agent instructions."""
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("sprint-prompts/qs13-t4.md")
    assert result is not None, "sprint-prompts/ should be denied"


def test_read_source_blocks_dot_env():
    """read_source blocks .env file path."""
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed(".env")
    assert result is not None, ".env should be denied"


def test_read_source_blocks_dot_claude_dir():
    """read_source blocks .claude/ directory — contains hooks and settings."""
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed(".claude/settings.json")
    assert result is not None, ".claude/ should be denied"


def test_read_source_allows_server_py():
    """read_source allows src/server.py — public source file."""
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("src/server.py")
    assert result is None, f"src/server.py should be allowed but got: {result}"


def test_read_source_allows_routes_misc():
    """read_source allows web/routes_misc.py — public source file."""
    from src.tools.project_intel import _check_path_allowed
    result = _check_path_allowed("web/routes_misc.py")
    assert result is None


def test_read_source_blocks_path_traversal():
    """read_source blocks path traversal attempts."""
    from src.tools.project_intel import read_source
    result = _run(read_source("../../etc/passwd"))
    assert "Error" in result or "not allowed" in result.lower()


def test_read_source_blocks_absolute_path():
    """read_source blocks absolute path attempts."""
    from src.tools.project_intel import read_source
    result = _run(read_source("/etc/hosts"))
    assert "Error" in result or "Absolute" in result
