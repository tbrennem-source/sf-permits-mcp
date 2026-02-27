# Sprint 78 — Test Harness Fix (Solo Sprint)

> 1 agent, 1 task: migrate test harness to temp Postgres per session.
> Eliminates DuckDB lock contention AND DuckDB/Postgres divergence bugs.

## Pre-Flight

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
source .venv/bin/activate
pytest tests/ -x -q --tb=no --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -5
echo "Sprint start: $(git rev-parse --short HEAD)"
```

## Launch Agent A (FOREGROUND)

```
Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="""
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.

CRITICAL: NEVER run 'git checkout main' or 'git merge'. NEVER push to main.
COMMIT to your worktree branch ONLY. The orchestrator handles all merges.

## YOUR TASK: Migrate test harness from DuckDB to temp Postgres (#357)

### Problem
Two problems, one fix:
1. **Lock contention:** 90 test files open the same DuckDB file. Parallel pytest sessions
   (or 16 swarm agents) cause random `IOException: Could not set lock on file` failures.
   Merge-ceremony test runs become unreliable.
2. **SQL divergence:** Prod uses Postgres. Tests use DuckDB. Bugs like `INSERT OR REPLACE`
   (DuckDB) vs `ON CONFLICT DO NOTHING` (Postgres), GROUP BY behavior differences, unique
   index handling, and autocommit semantics only surface on staging — too late.

### Solution: temp Postgres per pytest session via `testing.postgresql`
Each pytest session spins up an isolated, temporary Postgres instance. Zero contention,
zero DuckDB/Postgres divergence. The `testing.postgresql` package bundles a Postgres binary
— no system install needed.

### Read First
- tests/conftest.py (root conftest — currently just clears rate state)
- src/db.py (get_connection, BACKEND, _DUCKDB_PATH, DATABASE_URL — understand both paths)
- src/db.py — find init_user_schema or any schema initialization functions
- tests/test_web.py lines 1-50 (see how Flask test client creates app)
- pyproject.toml (dev dependencies section)
- web/app.py lines 1-50 (app factory, how DATABASE_URL is used at startup)

### Known DuckDB/Postgres Gotchas (from QS5, QS7 post-mortems)
- `INSERT OR REPLACE` → Postgres needs `ON CONFLICT DO NOTHING` or `ON CONFLICT DO UPDATE`
- `CREATE UNIQUE INDEX` on dirty data → fails on Postgres (need DISTINCT ON)
- DuckDB uses `?` placeholders, Postgres uses `%s`
- `conn.execute()` vs `cursor.execute()` patterns differ
- Streaming ingest must `conn.commit()` per batch on Postgres
- GROUP BY + INSERT with PK on LEFT JOIN columns → duplicate rows on Postgres
- CRON_WORKER env var must be set for cron route tests (CRON_GUARD returns 404 without it)
- TESTING mode must be checked in before_request hooks or daily limits accumulate across test files

### Build

**Task A-1: Install Postgres + testing.postgresql**

`testing.postgresql` requires a Postgres binary on the machine (`pg_ctl` on PATH).

Step 1: Check if Postgres is already installed:
```bash
which pg_ctl && pg_ctl --version
```

Step 2: If not installed:
```bash
brew install postgresql@16
echo 'export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"' >> ~/.zshrc
export PATH="/opt/homebrew/opt/postgresql@16/bin:$PATH"
```

Step 3: Add to pyproject.toml dev dependencies:
```
testing.postgresql>=1.3.0
```
Run: `pip install -e ".[dev]"`

Step 4: Verify it works:
```python
import testing.postgresql
with testing.postgresql.Postgresql() as pg:
    print(pg.url())  # Should print a postgres:// URL
```

**CLOCK CHECK:** If you're not past this point within 10 minutes, skip to Fallback.

Step 5: Document in docs/ONBOARDING.md under "Dev Dependencies":
```
### Postgres (for tests)
brew install postgresql@16
# Required by testing.postgresql — spins up temp instances for test isolation
```

**Task A-2: Create session-scoped Postgres fixture in tests/conftest.py**

```python
import pytest
import os

@pytest.fixture(autouse=True, scope="session")
def _isolated_test_db():
    """Spin up a temp Postgres per session — zero contention, matches prod."""
    try:
        import testing.postgresql
    except ImportError:
        # Fallback: per-session temp DuckDB (see fallback below)
        yield from _fallback_duckdb_isolation()
        return

    # Start temp Postgres
    postgresql = testing.postgresql.Postgresql()
    dsn = postgresql.url()

    # Patch src.db to use temp Postgres
    import src.db as db_mod
    original_url = os.environ.get("DATABASE_URL")
    original_backend = db_mod.BACKEND

    os.environ["DATABASE_URL"] = dsn
    db_mod.BACKEND = "postgres"
    db_mod.DATABASE_URL = dsn

    # Reset any cached connection pool
    if hasattr(db_mod, '_pool') and db_mod._pool is not None:
        try:
            db_mod._pool.closeall()
        except Exception:
            pass
        db_mod._pool = None

    # Initialize schema
    conn = db_mod.get_connection()
    try:
        # Run all schema creation needed for tests
        _init_test_schema(conn)
        conn.commit()
    except Exception as e:
        print(f"Schema init warning: {e}")
    finally:
        conn.close()

    yield dsn

    # Cleanup
    db_mod.BACKEND = original_backend
    if original_url:
        os.environ["DATABASE_URL"] = original_url
    else:
        os.environ.pop("DATABASE_URL", None)
    db_mod.DATABASE_URL = original_url
    postgresql.stop()
```

**Task A-3: Write _init_test_schema(conn)**

Read src/db.py to find all schema init functions. The temp Postgres is empty —
you need to create every table tests expect. Look for:
- `init_user_schema()` or similar — creates users, auth_tokens, watch_items, feedback, etc.
- Permit data tables — permits, contacts, entities, relationships, inspections, timeline_stats
- page_cache table (added in QS7)
- Any CREATE TABLE statements in src/db.py or web/app.py startup

Write a `_init_test_schema(conn)` function in conftest.py that creates ALL tables.
Use `CREATE TABLE IF NOT EXISTS` for safety. Copy the DDL from src/db.py.

**Task A-4: Handle the BACKEND switch throughout src/db.py**

When BACKEND is "postgres", src/db.py uses psycopg2 connection pooling.
When BACKEND is "duckdb", it opens a file connection. Verify that:
- get_connection() works with the temp Postgres DSN
- The connection pool initializes correctly with the temp DSN
- query() and execute() work with Postgres %s placeholders (not DuckDB ?)

If any test files import BACKEND directly and branch on it, they should now
take the Postgres path.

**Task A-5: Fix any tests that use DuckDB-specific SQL**

Grep for:
- `INSERT OR REPLACE` → change to `INSERT ... ON CONFLICT`
- `?` placeholder in SQL strings → change to `%s`
- `conn.execute()` without cursor → use `with conn.cursor() as cur:`
- Any DuckDB-specific functions (e.g., `list_value`, `struct_pack`)

These changes should be in test files only. Do NOT modify src/ production code.
If production code has DuckDB-specific SQL in a code path that tests exercise,
note it in your commit message but don't change it — that's a separate task.

**Task A-6: Verify existing _clear_rate_state fixture coexists**

The current conftest.py has a function-scoped fixture that clears rate state.
Session-scoped DB + function-scoped rate clearing should coexist fine.
Verify by running the auth tests.

### HARD TIME-BOX: 10 minutes for Postgres setup

Start a timer when you begin Task A-1. If `testing.postgresql` is not fully working
(installed, binary starts, tests pass) within 10 minutes of agent start, STOP the
Postgres path immediately and ship the DuckDB fallback below instead.

Do NOT debug `pg_ctl`, `brew install` failures, binary version mismatches, or
connection pool issues past the 10-minute mark. The DuckDB fallback solves the P0
(lock contention). Postgres migration becomes a P1 follow-up.

If you use the fallback, add this task to your commit message:
"FOLLOW-UP NEEDED: P1 — migrate test harness to temp Postgres (testing.postgresql
setup failed within time-box, shipped DuckDB isolation instead)"

### Fallback: DuckDB Isolation (ships if Postgres setup exceeds 10-minute time-box)

If `testing.postgresql` won't install, the binary won't start, or startup takes
>5 seconds per session, fall back to this approach instead:

```python
@pytest.fixture(autouse=True, scope="session")
def _fallback_duckdb_isolation(tmp_path_factory):
    """Per-session temp DuckDB — fixes contention, NOT divergence."""
    tmpdir = tmp_path_factory.mktemp("duckdb")
    db_path = str(tmpdir / "test_permits.duckdb")

    import src.db as db_mod
    original_path = db_mod._DUCKDB_PATH
    original_backend = db_mod.BACKEND
    db_mod._DUCKDB_PATH = db_path
    db_mod.BACKEND = "duckdb"

    conn = db_mod.get_connection()
    try:
        _init_test_schema_duckdb(conn)
    except Exception:
        pass
    finally:
        conn.close()

    yield db_path

    db_mod._DUCKDB_PATH = original_path
    db_mod.BACKEND = original_backend
```

If you use the fallback, document it clearly in your commit message:
"FALLBACK: testing.postgresql failed — using per-session temp DuckDB.
Fixes contention but NOT divergence. Postgres migration deferred."

### Test

```bash
source .venv/bin/activate

# 1. Full suite passes
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -10

# 2. Verify tests run against Postgres (not DuckDB)
python -c "
from tests.conftest import *
import src.db as db_mod
print(f'BACKEND: {db_mod.BACKEND}')
# Should print 'postgres' when fixture is active
"

# 3. Parallel contention test (the actual fix)
pytest tests/test_auth.py -x -q --tb=short &
pytest tests/test_brief.py -x -q --tb=short &
wait
# Both should pass — no lock contention

# 4. Triple parallel (stress test)
pytest tests/test_auth.py -q &
pytest tests/test_brief.py -q &
pytest tests/test_landing.py -q &
wait

# 5. Divergence verification — run a query that behaves differently on DuckDB vs Postgres
# (e.g., standard GROUP BY behavior, ON CONFLICT syntax)
pytest tests/test_page_cache.py -x -q --tb=short
# page_cache tests use INSERT...ON CONFLICT — these should pass on Postgres
```

### Commit
`fix: migrate test harness to temp Postgres — eliminates lock contention + divergence (#357)`

If using fallback:
`fix: per-session temp DuckDB for tests — eliminates lock contention (#357)`
""")
```

---

## Post-Agent: Merge

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main

# Merge agent branch
git merge <agent-a-branch> --no-edit

# Full test suite
source .venv/bin/activate
pytest tests/ -x -q --tb=short --ignore=tests/test_tools.py --ignore=tests/e2e 2>&1 | tail -10

# Parallel contention test
pytest tests/test_auth.py -x -q &
pytest tests/test_brief.py -x -q &
wait

# Prod gate
python scripts/prod_gate.py --quiet

# Push
git push origin main

# Promote
git checkout prod && git merge main && git push origin prod && git checkout main
```

## Report Template

```
Sprint 78 COMPLETE — Test Harness Fix
============================================
Agent A (#357):     [PASS/FAIL]
  Approach:         [Postgres / DuckDB fallback]
  Backend in tests: [postgres / duckdb]

Post-merge:
  Full test suite: [N passed / M failed]
  Parallel test (2x): [PASS/FAIL]
  Parallel test (3x): [PASS/FAIL]
  Prod gate: [PROMOTE/HOLD]
```
