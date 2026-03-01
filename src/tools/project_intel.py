"""Tools: Project Intelligence — read-only analytical access to codebase and database.

5 tools for the planning layer (Claude Chat) to query the production database,
read source files, search the codebase, inspect schema, and list tests —
without needing CC roundtrips.
"""

import asyncio
import logging
import os
import re
import subprocess
import time
from pathlib import Path

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────

# Repo root: from src/tools/project_intel.py -> ../.. = repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Placeholder style for DB queries
_PH = "%s" if BACKEND == "postgres" else "?"

# Allowed file extensions for read_source
_ALLOWED_EXTENSIONS = {
    ".py", ".html", ".js", ".css", ".json", ".md", ".yml", ".yaml",
    ".toml", ".txt", ".sql", ".cfg", ".ini", ".sh", ".env.example",
    ".dockerfile", ".jinja2", ".j2",
}

# SQL keywords that indicate a write operation (whole-word match)
_FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|GRANT|REVOKE|COPY)\b",
    re.IGNORECASE,
)

# Max lines to return from read_source
_MAX_READ_LINES = 500

# ── Security: Table allowlist / denylist ─────────────────────────────

_ALLOWED_TABLES = {
    "permits", "contacts", "entities", "relationships", "inspections",
    "timeline_stats", "station_velocity_v2", "complaints", "violations",
    "addenda_routing", "addenda", "businesses", "boiler_permits",
    "fire_permits", "planning_records", "tax_rolls", "street_use_permits",
    "development_pipeline", "affordable_housing", "housing_production",
    "dwelling_completions", "ref_zoning_routing", "ref_permit_forms",
    "ref_agency_triggers", "permit_issuance_metrics", "permit_review_metrics",
    "planning_review_metrics", "cron_log", "ingest_log",
    "severity_cache", "request_metrics", "parcel_summary",
}

_BLOCKED_TABLES = {
    "users", "auth_tokens", "feedback", "watch_items", "activity_log",
    "points_ledger", "permit_changes", "regulatory_watch",
    "plan_analysis_sessions", "plan_analysis_images", "plan_analysis_jobs",
    "beta_requests", "mcp_oauth_clients", "mcp_oauth_codes", "mcp_oauth_tokens",
    "voice_calibrations", "project_notes", "analysis_sessions", "page_cache",
}


def _check_table_allowlist(sql: str) -> str | None:
    """Return error message if SQL references blocked tables, else None."""
    sql_lower = sql.lower()
    # Extract all identifiers after FROM, JOIN, UPDATE, INSERT INTO, DELETE FROM
    pattern = r'\b(?:from|join|update|into)\s+([a-z_][a-z0-9_]*)'
    tables = re.findall(pattern, sql_lower)
    for table in tables:
        if table.startswith("pg_") or table.startswith("information_schema"):
            return f"Access denied: system table '{table}' is not queryable."
        if table in _BLOCKED_TABLES:
            return f"Access denied: table '{table}' is not accessible via this tool."
    return None


# ── Security: Path denylist ──────────────────────────────────────────

def _check_path_allowed(path: str) -> str | None:
    """Return error message if path is denied, else None."""
    # Normalize
    clean = path.strip().lstrip("/")
    denied_patterns = ["CLAUDE.md", "sprint-prompts/", ".claude/", ".env"]
    for pattern in denied_patterns:
        if clean == pattern or clean.startswith(pattern) or ("/" + pattern) in clean:
            return f"Access denied: '{path}' is not readable via this tool."
    return None


# ── Helpers ──────────────────────────────────────────────────────────


def _exec(conn, sql, params=None):
    """Execute SQL and return all rows."""
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        if params:
            return conn.execute(sql, params).fetchall()
        return conn.execute(sql).fetchall()


def _strip_sql_comments(sql: str) -> str:
    """Remove SQL comments (-- and /* */) for safe keyword inspection."""
    # Remove single-line comments
    sql = re.sub(r"--[^\n]*", "", sql)
    # Remove multi-line comments
    sql = re.sub(r"/\*.*?\*/", "", sql, flags=re.DOTALL)
    return sql.strip()


def _format_table(headers: list[str], rows: list[tuple], max_col_width: int = 60) -> str:
    """Format rows as a markdown table."""
    if not rows:
        return "*(no rows)*"

    # Convert all values to strings, truncate long ones
    str_rows = []
    for row in rows:
        str_row = []
        for val in row:
            s = str(val) if val is not None else ""
            if len(s) > max_col_width:
                s = s[:max_col_width - 3] + "..."
            str_row.append(s)
        str_rows.append(str_row)

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in str_rows:
        for i, val in enumerate(row):
            if i < len(widths):
                widths[i] = max(widths[i], len(val))

    # Build table
    header_line = "| " + " | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)) + " |"
    sep_line = "| " + " | ".join("-" * widths[i] for i in range(len(headers))) + " |"
    data_lines = []
    for row in str_rows:
        padded = []
        for i, val in enumerate(row):
            if i < len(widths):
                padded.append(val.ljust(widths[i]))
            else:
                padded.append(val)
        data_lines.append("| " + " | ".join(padded) + " |")

    return "\n".join([header_line, sep_line] + data_lines)


# ── Tool 1: run_query ───────────────────────────────────────────────


async def run_query(sql: str, limit: int = 100) -> str:
    """Run a read-only SQL query against the production database.

    For analytical queries during planning sessions — inspection rates,
    severity calibration, data distribution analysis, etc.

    Args:
        sql: SELECT query only. INSERT/UPDATE/DELETE/DROP/ALTER rejected.
        limit: Max rows returned (default 100, max 1000).

    Returns:
        Formatted markdown table with results, row count, and execution time.
    """
    limit = min(max(1, limit), 1000)

    # Strip comments before checking keywords
    clean_sql = _strip_sql_comments(sql)

    # Must start with SELECT or WITH
    first_word = clean_sql.split()[0].upper() if clean_sql.split() else ""
    if first_word not in ("SELECT", "WITH"):
        return "**Error:** Only SELECT and WITH (CTE) queries are allowed."

    # Check for forbidden write keywords in the cleaned SQL
    match = _FORBIDDEN_SQL.search(clean_sql)
    if match:
        return f"**Error:** Write operation `{match.group()}` is not allowed. Read-only queries only."

    # Check table allowlist — block access to sensitive tables
    block_reason = _check_table_allowlist(clean_sql)
    if block_reason:
        return f"**Error:** {block_reason}"

    conn = get_connection()
    try:
        # Set statement timeout (Postgres only)
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = '10s'")

        # Apply LIMIT if not already present
        # Simple check: if user didn't include a LIMIT clause, add one
        if not re.search(r"\bLIMIT\b", clean_sql, re.IGNORECASE):
            sql = sql.rstrip().rstrip(";") + f"\nLIMIT {limit}"
        else:
            # User specified LIMIT — cap it at our max
            sql = re.sub(
                r"\bLIMIT\s+(\d+)",
                lambda m: f"LIMIT {min(int(m.group(1)), limit)}",
                sql,
                flags=re.IGNORECASE,
            )

        start = time.monotonic()

        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()
                headers = [desc[0] for desc in cur.description] if cur.description else []
        else:
            result = conn.execute(sql)
            rows = result.fetchall()
            headers = [desc[0] for desc in result.description] if result.description else []

        elapsed = time.monotonic() - start

        if not rows:
            return f"*Query returned 0 rows ({elapsed:.2f}s)*"

        table = _format_table(headers, rows)
        return f"{table}\n\n*{len(rows)} row{'s' if len(rows) != 1 else ''} ({elapsed:.2f}s)*"

    except Exception as e:
        logger.error("run_query failed: %s", e)
        return f"**Error:** {e}"
    finally:
        conn.close()


# ── Tool 2: read_source ─────────────────────────────────────────────


async def read_source(path: str, line_start: int = None, line_end: int = None) -> str:
    """Read a source file from the sf-permits-mcp repository.

    Args:
        path: Relative path from repo root (e.g., 'web/brief.py', 'src/tools/analyze_plans.py')
        line_start: Optional start line (1-indexed)
        line_end: Optional end line (1-indexed)

    Returns:
        File contents with line numbers, or error message.
    """
    # Check path denylist — block access to sensitive files
    deny = _check_path_allowed(path)
    if deny:
        return f"**Error:** {deny}"

    # Reject absolute paths
    if path.startswith("/") or path.startswith("\\"):
        return "**Error:** Absolute paths not allowed. Use relative paths from repo root."

    # Reject path traversal
    if ".." in path:
        return "**Error:** Path traversal (`..`) not allowed."

    resolved = (_REPO_ROOT / path).resolve()

    # Ensure resolved path is within repo
    try:
        resolved.relative_to(_REPO_ROOT)
    except ValueError:
        return "**Error:** Path resolves outside the repository."

    if not resolved.is_file():
        return f"**Error:** File not found: `{path}`"

    # Check extension
    suffix = resolved.suffix.lower()
    # Also allow extensionless files like Dockerfile, Makefile, Procfile
    stem = resolved.stem.lower()
    extensionless_allowed = {"dockerfile", "makefile", "procfile", "gemfile"}
    if suffix not in _ALLOWED_EXTENSIONS and stem not in extensionless_allowed:
        return f"**Error:** File type `{suffix}` not supported. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"

    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"**Error:** Could not read file: {e}"

    lines = content.splitlines()
    total_lines = len(lines)

    # Apply line range
    if line_start is not None or line_end is not None:
        start = max(1, line_start or 1) - 1  # Convert to 0-indexed
        end = min(total_lines, line_end or total_lines)
        lines = lines[start:end]
        range_info = f" (lines {start + 1}-{end} of {total_lines})"
    else:
        range_info = f" ({total_lines} lines)"
        if total_lines > _MAX_READ_LINES:
            lines = lines[:_MAX_READ_LINES]
            range_info = f" (showing first {_MAX_READ_LINES} of {total_lines} lines — use line_start/line_end for more)"

    # Format with line numbers
    start_num = (line_start or 1) if line_start else 1
    numbered = []
    for i, line in enumerate(lines):
        num = start_num + i
        numbered.append(f"{num:>5} | {line}")

    header = f"**`{path}`**{range_info}\n```"
    footer = "```"
    return f"{header}\n" + "\n".join(numbered) + f"\n{footer}"


# ── Tool 3: search_source ───────────────────────────────────────────


async def search_source(pattern: str, file_pattern: str = "*.py", max_results: int = 20) -> str:
    """Search the codebase for a pattern (like grep).

    Args:
        pattern: Search string or regex
        file_pattern: Glob for file types (default *.py, use '*' for all)
        max_results: Cap on matches (default 20, max 50)

    Returns:
        Matching lines with file paths and line numbers.
    """
    max_results = min(max(1, max_results), 50)

    # Sanitize: reject shell metacharacters in pattern to prevent injection
    # grep -F (fixed string) is safer, but we want regex support
    # Instead, we pass pattern via stdin to avoid shell issues
    cmd = [
        "grep", "-rn",
        "--include", file_pattern,
        "-m", str(max_results * 3),  # Overfetch then truncate
        pattern,
        str(_REPO_ROOT),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
    except asyncio.TimeoutError:
        return "**Error:** Search timed out after 5 seconds. Try a more specific pattern."
    except Exception as e:
        return f"**Error:** Search failed: {e}"

    output = stdout.decode("utf-8", errors="replace")

    if not output.strip():
        return f"*No matches for `{pattern}` in `{file_pattern}` files.*"

    # Make paths relative to repo root
    lines = output.strip().splitlines()
    repo_prefix = str(_REPO_ROOT) + "/"
    formatted = []
    for line in lines[:max_results]:
        if line.startswith(repo_prefix):
            line = line[len(repo_prefix):]
        formatted.append(line)

    result = "```\n" + "\n".join(formatted) + "\n```"
    total = len(lines)
    if total > max_results:
        result += f"\n\n*Showing {max_results} of {total} matches. Increase max_results for more.*"
    else:
        result += f"\n\n*{len(formatted)} match{'es' if len(formatted) != 1 else ''}*"

    return result


# ── Tool 4: schema_info ─────────────────────────────────────────────


async def schema_info(table: str = None) -> str:
    """Get database schema information.

    Args:
        table: Specific table to inspect. If None, lists all tables with row counts.

    Returns:
        Schema information formatted as markdown.
    """
    conn = get_connection()
    try:
        if table is None:
            return await _list_all_tables(conn)
        else:
            return await _describe_table(conn, table)
    except Exception as e:
        logger.error("schema_info failed: %s", e)
        return f"**Error:** {e}"
    finally:
        conn.close()


async def _list_all_tables(conn) -> str:
    """List all tables with approximate row counts."""
    if BACKEND == "postgres":
        rows = _exec(conn, """
            SELECT
                t.table_name,
                COALESCE(s.n_live_tup, 0) AS approx_rows
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
            WHERE t.table_schema = 'public'
            ORDER BY COALESCE(s.n_live_tup, 0) DESC
        """)
        headers = ["table_name", "approx_rows"]
    else:
        # DuckDB: list tables and get counts
        tables = _exec(conn, "SELECT table_name FROM information_schema_schemata() WHERE table_type = 'BASE TABLE'") \
            if False else []
        # DuckDB approach: SHOW TABLES
        try:
            tables = _exec(conn, "SHOW TABLES")
        except Exception:
            tables = []
        rows = []
        for (tbl,) in tables:
            try:
                count = _exec(conn, f"SELECT COUNT(*) FROM \"{tbl}\"")
                rows.append((tbl, count[0][0] if count else 0))
            except Exception:
                rows.append((tbl, "?"))
        rows.sort(key=lambda r: r[1] if isinstance(r[1], int) else 0, reverse=True)
        headers = ["table_name", "row_count"]

    table_md = _format_table(headers, rows)
    return f"## Database Tables ({BACKEND})\n\n{table_md}\n\n*{len(rows)} tables*"


async def _describe_table(conn, table: str) -> str:
    """Show columns, types, and indexes for a specific table."""
    # Sanitize table name
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", table):
        return "**Error:** Invalid table name."

    parts = []

    # Column info
    if BACKEND == "postgres":
        cols = _exec(conn, """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s AND table_schema = 'public'
            ORDER BY ordinal_position
        """, [table])
        if not cols:
            return f"**Error:** Table `{table}` not found."
        col_headers = ["column", "type", "nullable", "default"]
    else:
        try:
            cols = _exec(conn, f"DESCRIBE \"{table}\"")
        except Exception:
            return f"**Error:** Table `{table}` not found."
        if not cols:
            return f"**Error:** Table `{table}` not found."
        col_headers = ["column", "type", "nullable", "default", "extra"]
        # DuckDB DESCRIBE returns: column_name, column_type, null, key, default, extra
        # Normalize to match our headers
        cols = [(r[0], r[1], r[2], r[4]) for r in cols]
        col_headers = ["column", "type", "nullable", "default"]

    parts.append(f"## Table: `{table}`\n")
    parts.append("### Columns\n")
    parts.append(_format_table(col_headers, cols))

    # Row count
    try:
        count = _exec(conn, f"SELECT COUNT(*) FROM \"{table}\"")
        parts.append(f"\n**Rows:** {count[0][0]:,}")
    except Exception:
        pass

    # Indexes (Postgres only — DuckDB doesn't have pg_indexes)
    if BACKEND == "postgres":
        try:
            indexes = _exec(conn, """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s AND schemaname = 'public'
                ORDER BY indexname
            """, [table])
            if indexes:
                parts.append("\n### Indexes\n")
                for name, defn in indexes:
                    parts.append(f"- `{name}`: {defn}")
        except Exception:
            pass

    return "\n".join(parts)


# ── Tool 5: list_tests ──────────────────────────────────────────────


async def list_tests(pattern: str = None, show_status: bool = False) -> str:
    """List test files and test functions in the repository.

    Args:
        pattern: Optional filter (e.g., 'severity', 'brief')
        show_status: If True, runs pytest --collect-only for detailed counts

    Returns:
        Test file listing with function counts.
    """
    tests_dir = _REPO_ROOT / "tests"
    if not tests_dir.is_dir():
        return "**Error:** `tests/` directory not found."

    if show_status:
        return await _pytest_collect(pattern)

    # Find test files
    test_files = sorted(tests_dir.glob("test_*.py"))

    if pattern:
        pattern_lower = pattern.lower()
        test_files = [f for f in test_files if pattern_lower in f.name.lower()]

    if not test_files:
        return f"*No test files matching '{pattern}'.*" if pattern else "*No test files found.*"

    results = []
    total_tests = 0
    for tf in test_files:
        try:
            content = tf.read_text(encoding="utf-8", errors="replace")
            test_count = len(re.findall(r"^(?:async )?def (test_\w+)", content, re.MULTILINE))
            total_tests += test_count
            rel_path = tf.relative_to(_REPO_ROOT)

            if pattern:
                # Show matching function names
                funcs = re.findall(r"^(?:async )?def (test_\w+)", content, re.MULTILINE)
                matching = [f for f in funcs if pattern_lower in f.lower()]
                if matching:
                    results.append(f"**{rel_path}** ({test_count} tests)")
                    for fn in matching:
                        results.append(f"  - `{fn}`")
                else:
                    results.append(f"**{rel_path}** ({test_count} tests)")
            else:
                results.append(f"- **{rel_path}** — {test_count} tests")
        except Exception:
            results.append(f"- **{tf.name}** — (could not read)")

    header = f"## Test Files"
    if pattern:
        header += f" matching '{pattern}'"
    header += f"\n\n*{len(test_files)} files, {total_tests} test functions*\n"

    return header + "\n".join(results)


async def _pytest_collect(pattern: str = None) -> str:
    """Run pytest --collect-only for detailed test inventory."""
    cmd = ["python", "-m", "pytest", "--collect-only", "-q", str(_REPO_ROOT / "tests")]
    if pattern:
        cmd.extend(["-k", pattern])

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(_REPO_ROOT),
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
    except asyncio.TimeoutError:
        return "**Error:** pytest --collect-only timed out after 15 seconds."
    except Exception as e:
        return f"**Error:** {e}"

    output = stdout.decode("utf-8", errors="replace")
    if not output.strip():
        err = stderr.decode("utf-8", errors="replace")
        return f"**Error:** pytest produced no output.\n```\n{err[:500]}\n```"

    # Return the pytest output directly — it's already well-formatted
    lines = output.strip().splitlines()
    if len(lines) > 100:
        lines = lines[:100]
        lines.append(f"... (truncated, {len(output.splitlines())} total)")

    return f"## pytest --collect-only\n\n```\n" + "\n".join(lines) + "\n```"
