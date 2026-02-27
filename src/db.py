"""Database connection for sf-permits-mcp.

Supports two backends:
  - PostgreSQL (production on Railway) — when DATABASE_URL is set
  - DuckDB (local development) — fallback when no DATABASE_URL

The tools don't care which backend they're talking to — the SQL is
standard enough to work on both (with minor syntax helpers below).
"""

import atexit
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Backend detection ─────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")

# DuckDB fallback path (local development)
_DUCKDB_PATH = os.environ.get(
    "SF_PERMITS_DB",
    str(Path(__file__).parent.parent / "data" / "sf_permits.duckdb"),
)

# Which backend are we using?
BACKEND = "postgres" if DATABASE_URL else "duckdb"


# ── PostgreSQL Connection Pool ────────────────────────────────────

# Lazy singleton — created on first get_connection() call
_pool = None


def _get_pool():
    """Get or create the PostgreSQL connection pool (lazy singleton)."""
    global _pool
    if _pool is None:
        import psycopg2.pool
        _maxconn = int(os.environ.get("DB_POOL_MAX", "20"))
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=_maxconn,
            dsn=DATABASE_URL,
            connect_timeout=10,
        )
        logger.info("PostgreSQL connection pool created (minconn=2, maxconn=%d)", _maxconn)
    return _pool


def get_pool_stats() -> dict:
    """Return connection pool statistics for /health endpoint."""
    if _pool is None:
        return {"status": "no_pool", "backend": BACKEND}
    return {
        "backend": BACKEND,
        "minconn": _pool.minconn,
        "maxconn": _pool.maxconn,
        "closed": _pool.closed,
        "pool_size": len(_pool._pool) if hasattr(_pool, '_pool') else -1,
        "used_count": len(_pool._used) if hasattr(_pool, '_used') else -1,
    }


def _close_pool():
    """Close the connection pool on shutdown."""
    global _pool
    if _pool is not None:
        try:
            _pool.closeall()
            logger.info("PostgreSQL connection pool closed")
        except Exception as e:
            logger.warning("Error closing pool: %s", e)
        _pool = None


atexit.register(_close_pool)


class _PooledConnection:
    """Wrapper around a psycopg2 connection that returns it to the pool on close.

    Instead of destroying the connection, .close() rolls back any uncommitted
    transaction and returns the connection to the pool via putconn().
    """

    def __init__(self, conn, pool):
        self._conn = conn
        self._pool = pool

    def close(self):
        """Roll back uncommitted work and return connection to pool."""
        if self._conn is not None:
            try:
                self._conn.rollback()
            except Exception:
                pass
            try:
                self._pool.putconn(self._conn)
            except Exception:
                pass
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def __setattr__(self, name, value):
        # Allow our own internal attributes to be set normally
        if name in ("_conn", "_pool"):
            super().__setattr__(name, value)
        else:
            # Delegate to the underlying psycopg2 connection (e.g., autocommit)
            setattr(self._conn, name, value)


def get_connection(db_path: str | None = None):
    """Get a database connection (Postgres or DuckDB).

    Args:
        db_path: Optional DuckDB file path override (for ingestion scripts).
                 Ignored when BACKEND is 'postgres'.

    Returns a connection object. Caller is responsible for closing it.
    Both backends support: conn.execute(), conn.close(), cursor context.

    For Postgres (no db_path override): returns a _PooledConnection from the
    connection pool. Sets statement_timeout=30s unless CRON_WORKER=true.
    """
    if BACKEND == "postgres" and not db_path:
        try:
            pool = _get_pool()
            raw_conn = pool.getconn()
            # Set statement_timeout for web requests; skip for cron workers
            if not os.environ.get("CRON_WORKER", "").lower() == "true":
                with raw_conn.cursor() as cur:
                    cur.execute("SET statement_timeout = '30s'")
                raw_conn.commit()
            return _PooledConnection(raw_conn, pool)
        except Exception as e:
            logger.error("Postgres pool connection failed: %s", e)
            raise
    else:
        import duckdb
        path = db_path or _DUCKDB_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = duckdb.connect(path)
        return conn


SLOW_QUERY_THRESHOLD_SECS = 5.0


def _log_slow_query(conn, sql: str, duration: float):
    """Log slow queries with EXPLAIN ANALYZE output (PostgreSQL only)."""
    logger.warning(
        "Slow query detected (%.1fs): %s",
        duration,
        sql[:200],
    )
    if BACKEND == "postgres":
        try:
            with conn.cursor() as cur:
                cur.execute(f"EXPLAIN ANALYZE {sql}")
                plan = cur.fetchall()
                plan_text = "\n".join(row[0] for row in plan)
                logger.warning("EXPLAIN ANALYZE output:\n%s", plan_text)
        except Exception:
            logger.debug("Could not run EXPLAIN ANALYZE for slow query", exc_info=True)


def query(sql: str, params=None) -> list:
    """Execute a SELECT and return all rows as a list of tuples.

    Handles parameter style differences:
      - Postgres uses %s placeholders
      - DuckDB uses ? placeholders

    Callers should use %s style — this function auto-converts for DuckDB.
    """
    import time
    conn = get_connection()
    try:
        if BACKEND == "duckdb" and params:
            # Convert %s → ? for DuckDB
            sql = sql.replace("%s", "?")
        t0 = time.monotonic()
        if BACKEND == "postgres":
            import psycopg2.extras
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchall()
        else:
            if params:
                result = conn.execute(sql, params).fetchall()
            else:
                result = conn.execute(sql).fetchall()
        elapsed = time.monotonic() - t0
        if elapsed >= SLOW_QUERY_THRESHOLD_SECS:
            _log_slow_query(conn, sql, elapsed)
        return result
    finally:
        conn.close()


def query_one(sql: str, params=None):
    """Execute a SELECT and return the first row, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


# ── Circuit Breaker ────────────────────────────────────────────────

import time as _time


class CircuitBreaker:
    """Per-category query circuit breaker.

    Tracks failures per category. After max_failures within window_seconds,
    the circuit "opens" and auto-skips queries for cooldown_seconds.
    """

    def __init__(self, max_failures=3, window_seconds=120, cooldown_seconds=300):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._failures: dict[str, list[float]] = {}  # category -> list of timestamps
        self._open_until: dict[str, float] = {}  # category -> timestamp when circuit closes

    def is_open(self, category: str) -> bool:
        """Return True if circuit is open (should skip queries)."""
        deadline = self._open_until.get(category)
        if deadline is None:
            return False
        if _time.monotonic() >= deadline:
            # Cooldown expired — close the circuit
            del self._open_until[category]
            self._failures.pop(category, None)
            return False
        return True

    def record_failure(self, category: str):
        """Record a failure. Opens circuit if threshold exceeded."""
        now = _time.monotonic()
        # Prune old failures outside the window
        failures = self._failures.get(category, [])
        cutoff = now - self.window_seconds
        failures = [t for t in failures if t > cutoff]
        failures.append(now)
        self._failures[category] = failures

        if len(failures) >= self.max_failures:
            self._open_until[category] = now + self.cooldown_seconds
            logger.warning(
                "Circuit breaker OPEN for '%s' (%d failures in %ds, cooldown %ds)",
                category, len(failures), self.window_seconds, self.cooldown_seconds,
            )

    def record_success(self, category: str):
        """Record success. Resets failure count for category."""
        self._failures.pop(category, None)
        self._open_until.pop(category, None)

    def get_status(self) -> dict:
        """Return status dict for /health endpoint."""
        status = {}
        # Report on all categories that have any state
        all_cats = set(self._failures.keys()) | set(self._open_until.keys())
        if not all_cats:
            return status
        now = _time.monotonic()
        for cat in sorted(all_cats):
            deadline = self._open_until.get(cat)
            if deadline is not None and now < deadline:
                remaining = int(deadline - now)
                failures = len(self._failures.get(cat, []))
                mins = remaining // 60
                secs = remaining % 60
                status[cat] = f"open ({failures} failures, reopens in {mins}m{secs:02d}s)"
            else:
                status[cat] = "closed"
        return status


# Module-level singleton
circuit_breaker = CircuitBreaker()


# ── Write helpers ──────────────────────────────────────────────────

def execute_write(sql: str, params=None, return_id: bool = False):
    """Execute an INSERT/UPDATE/DELETE and optionally return a generated id.

    Uses RETURNING for both Postgres and DuckDB (DuckDB >=0.9 supports it).
    Callers should use %s placeholders — auto-converted for DuckDB.
    """
    conn = get_connection()
    try:
        if BACKEND == "duckdb" and params:
            sql = sql.replace("%s", "?")
        if BACKEND == "postgres":
            with conn.cursor() as cur:
                cur.execute(sql, params)
                result = cur.fetchone() if return_id else None
                conn.commit()
                return result[0] if result else None
        else:
            if params:
                result = conn.execute(sql, params)
            else:
                result = conn.execute(sql)
            if return_id:
                row = result.fetchone()
                return row[0] if row else None
            return None
    finally:
        conn.close()


# ── User schema (DuckDB dev mode) ────────────────────────────────

def init_user_schema(conn=None) -> None:
    """Create user/auth/watch tables in DuckDB (dev mode).

    Called lazily on first auth/watch operation. Idempotent.
    If no conn provided, creates one internally.
    """
    close = False
    if conn is None:
        conn = get_connection()
        close = True
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT,
                role TEXT,
                firm_name TEXT,
                entity_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP,
                email_verified BOOLEAN NOT NULL DEFAULT FALSE,
                is_admin BOOLEAN NOT NULL DEFAULT FALSE,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                brief_frequency TEXT NOT NULL DEFAULT 'none',
                last_brief_sent_at TIMESTAMP,
                invite_code TEXT,
                primary_street_number TEXT,
                primary_street_name TEXT,
                subscription_tier TEXT NOT NULL DEFAULT 'free',
                voice_style TEXT,
                notify_permit_changes BOOLEAN NOT NULL DEFAULT FALSE,
                notify_email TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL UNIQUE,
                purpose TEXT NOT NULL DEFAULT 'login',
                expires_at TIMESTAMP NOT NULL,
                used_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_items (
                watch_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                watch_type TEXT NOT NULL,
                permit_number TEXT,
                street_number TEXT,
                street_name TEXT,
                block TEXT,
                lot TEXT,
                entity_id INTEGER,
                neighborhood TEXT,
                label TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                tags TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permit_changes (
                change_id INTEGER PRIMARY KEY,
                permit_number TEXT NOT NULL,
                change_date DATE NOT NULL,
                detected_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                old_status TEXT,
                new_status TEXT NOT NULL,
                old_status_date TEXT,
                new_status_date TEXT,
                change_type TEXT NOT NULL,
                is_new_permit BOOLEAN NOT NULL DEFAULT FALSE,
                source TEXT NOT NULL DEFAULT 'nightly',
                permit_type TEXT,
                street_number TEXT,
                street_name TEXT,
                neighborhood TEXT,
                block TEXT,
                lot TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                log_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                action TEXT NOT NULL,
                detail TEXT,
                path TEXT,
                ip_hash TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                feedback_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                feedback_type TEXT NOT NULL DEFAULT 'suggestion',
                message TEXT NOT NULL,
                page_url TEXT,
                screenshot_data TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                admin_note TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS points_ledger (
                ledger_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                points INTEGER NOT NULL,
                reason TEXT NOT NULL,
                feedback_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add columns for existing DuckDB databases (migration for pre-existing DBs)
        for alter_stmt in [
            "ALTER TABLE feedback ADD COLUMN screenshot_data TEXT",
            "ALTER TABLE watch_items ADD COLUMN tags TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN voice_style TEXT",
            "ALTER TABLE users ADD COLUMN brief_frequency TEXT DEFAULT 'none'",
            "ALTER TABLE users ADD COLUMN invite_code TEXT",
            "ALTER TABLE users ADD COLUMN primary_street_number TEXT",
            "ALTER TABLE users ADD COLUMN primary_street_name TEXT",
            "ALTER TABLE users ADD COLUMN subscription_tier TEXT DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN notify_permit_changes BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN notify_email TEXT",
        ]:
            try:
                conn.execute(alter_stmt)
            except Exception:
                pass  # Column already exists
        # Indexes (no partial indexes in DuckDB)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_users_email ON users (email)",
            "CREATE INDEX IF NOT EXISTS idx_watch_user ON watch_items (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_watch_permit ON watch_items (permit_number)",
            "CREATE INDEX IF NOT EXISTS idx_auth_token ON auth_tokens (token)",
            "CREATE INDEX IF NOT EXISTS idx_pc_date ON permit_changes (change_date)",
            "CREATE INDEX IF NOT EXISTS idx_pc_permit ON permit_changes (permit_number)",
            "CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_activity_action ON activity_log (action)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback (status)",
            "CREATE INDEX IF NOT EXISTS idx_points_user ON points_ledger (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_points_feedback ON points_ledger (feedback_id)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Addenda changes table (tracks plan review routing changes)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS addenda_changes (
                change_id           INTEGER PRIMARY KEY,
                application_number  TEXT NOT NULL,
                change_date         DATE NOT NULL,
                detected_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                station             TEXT,
                addenda_number      INTEGER,
                step                INTEGER,
                plan_checked_by     TEXT,
                old_review_results  TEXT,
                new_review_results  TEXT,
                hold_description    TEXT,
                finish_date         TEXT,
                change_type         TEXT NOT NULL,
                source              TEXT NOT NULL DEFAULT 'nightly',
                department          TEXT,
                permit_type         TEXT,
                street_number       TEXT,
                street_name         TEXT,
                neighborhood        TEXT,
                block               TEXT,
                lot                 TEXT
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_ac_date ON addenda_changes (change_date)",
            "CREATE INDEX IF NOT EXISTS idx_ac_app_num ON addenda_changes (application_number)",
            "CREATE INDEX IF NOT EXISTS idx_ac_station ON addenda_changes (station)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Regulatory watch table (tracks pending legislation / code amendments)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS regulatory_watch (
                watch_id        INTEGER PRIMARY KEY,
                title           TEXT NOT NULL,
                description     TEXT,
                source_type     TEXT NOT NULL,
                source_id       TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'monitoring',
                impact_level    TEXT DEFAULT 'moderate',
                affected_sections TEXT,
                semantic_concepts TEXT,
                url             TEXT,
                filed_date      TEXT,
                effective_date  TEXT,
                notes           TEXT,
                created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_regwatch_status ON regulatory_watch (status)")
        except Exception:
            pass

        # Plan analysis session tables (DuckDB version - TEXT instead of JSONB, TIMESTAMP instead of TIMESTAMPTZ)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plan_analysis_sessions (
                session_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                page_count INTEGER NOT NULL,
                page_extractions TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plan_analysis_images (
                session_id TEXT NOT NULL,
                page_number INTEGER NOT NULL,
                image_data TEXT NOT NULL,
                image_size_kb INTEGER,
                PRIMARY KEY (session_id, page_number),
                FOREIGN KEY (session_id) REFERENCES plan_analysis_sessions(session_id)
            )
        """)
        # user_id + page_annotations columns on sessions
        for alter_stmt in [
            "ALTER TABLE plan_analysis_sessions ADD COLUMN user_id INTEGER",
            "ALTER TABLE plan_analysis_sessions ADD COLUMN page_annotations TEXT",
        ]:
            try:
                conn.execute(alter_stmt)
            except Exception:
                pass  # Column already exists

        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_created ON plan_analysis_sessions (created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_user ON plan_analysis_sessions (user_id)")
        except Exception:
            pass

        # Plan analysis jobs table (async processing + job history)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS plan_analysis_jobs (
                job_id              TEXT PRIMARY KEY,
                user_id             INTEGER,
                session_id          TEXT,
                filename            TEXT NOT NULL,
                file_size_mb        REAL NOT NULL,
                status              TEXT NOT NULL DEFAULT 'pending',
                is_async            BOOLEAN NOT NULL DEFAULT FALSE,
                project_description TEXT,
                permit_type         TEXT,
                is_addendum         BOOLEAN NOT NULL DEFAULT FALSE,
                quick_check         BOOLEAN NOT NULL DEFAULT FALSE,
                report_md           TEXT,
                error_message       TEXT,
                pdf_data            BLOB,
                property_address    TEXT,
                permit_number       TEXT,
                address_source      TEXT,
                permit_source       TEXT,
                created_at          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                started_at          TIMESTAMP,
                completed_at        TIMESTAMP,
                email_sent          BOOLEAN NOT NULL DEFAULT FALSE
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_plan_jobs_user ON plan_analysis_jobs (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_plan_jobs_status ON plan_analysis_jobs (status)",
            "CREATE INDEX IF NOT EXISTS idx_plan_jobs_permit ON plan_analysis_jobs (permit_number)",
            "CREATE INDEX IF NOT EXISTS idx_plan_jobs_address ON plan_analysis_jobs (property_address)",
            "CREATE INDEX IF NOT EXISTS idx_plan_jobs_created ON plan_analysis_jobs (created_at)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Incremental columns added after initial table creation
        for alter_stmt in [
            "ALTER TABLE plan_analysis_jobs ADD COLUMN progress_stage TEXT",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN progress_detail TEXT",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN vision_usage_json TEXT",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN gallery_duration_ms INTEGER",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN analysis_mode TEXT DEFAULT 'sample'",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN pages_analyzed INTEGER",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN submission_stage TEXT",
            # Phase D1: Close Project — archive flag (DuckDB doesn't support NOT NULL in ALTER)
            "ALTER TABLE plan_analysis_jobs ADD COLUMN is_archived BOOLEAN DEFAULT FALSE",
            # Phase D2: Document Fingerprinting
            "ALTER TABLE plan_analysis_jobs ADD COLUMN pdf_hash TEXT",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN pdf_hash_failed BOOLEAN DEFAULT FALSE",
            # structural_fingerprint stored as JSON text in DuckDB (JSONB only in Postgres)
            "ALTER TABLE plan_analysis_jobs ADD COLUMN structural_fingerprint TEXT",
            # Phase E1: Version Chain data model
            "ALTER TABLE plan_analysis_jobs ADD COLUMN version_group TEXT",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN version_number INTEGER",
            "ALTER TABLE plan_analysis_jobs ADD COLUMN parent_job_id TEXT",
            # Phase E2: Comparison cache (TEXT in DuckDB, JSONB in Postgres)
            "ALTER TABLE plan_analysis_jobs ADD COLUMN comparison_json TEXT",
        ]:
            try:
                conn.execute(alter_stmt)
            except Exception:
                pass  # Column already exists

        # Reference tables for predict_permits (Sprint 55B)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ref_zoning_routing (
                zoning_code TEXT PRIMARY KEY,
                zoning_category TEXT,
                planning_review_required BOOLEAN DEFAULT FALSE,
                fire_review_required BOOLEAN DEFAULT FALSE,
                health_review_required BOOLEAN DEFAULT FALSE,
                historic_district BOOLEAN DEFAULT FALSE,
                height_limit TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ref_permit_forms (
                id INTEGER PRIMARY KEY,
                project_type TEXT NOT NULL,
                permit_form TEXT NOT NULL,
                review_path TEXT,
                notes TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ref_agency_triggers (
                id INTEGER PRIMARY KEY,
                trigger_keyword TEXT NOT NULL,
                agency TEXT NOT NULL,
                reason TEXT,
                adds_weeks INTEGER
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_ref_forms_type ON ref_permit_forms (project_type)",
            "CREATE INDEX IF NOT EXISTS idx_ref_triggers_keyword ON ref_agency_triggers (trigger_keyword)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Voice calibration — per-scenario style preferences
        conn.execute("""
            CREATE TABLE IF NOT EXISTS voice_calibrations (
                calibration_id  INTEGER PRIMARY KEY,
                user_id         INTEGER NOT NULL,
                scenario_key    TEXT NOT NULL,
                audience        TEXT NOT NULL,
                situation       TEXT NOT NULL,
                template_text   TEXT NOT NULL,
                user_text       TEXT,
                style_notes     TEXT,
                is_calibrated   BOOLEAN NOT NULL DEFAULT FALSE,
                created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, scenario_key)
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_voicecal_user ON voice_calibrations (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_voicecal_scenario ON voice_calibrations (scenario_key)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Phase F2: Project Notes — free-text per version group
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_notes (
                note_id         INTEGER PRIMARY KEY,
                user_id         INTEGER NOT NULL,
                version_group   TEXT NOT NULL,
                notes_text      TEXT NOT NULL DEFAULT '',
                updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, version_group)
            )
        """)
        try:
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_project_notes_user_group "
                "ON project_notes (user_id, version_group)"
            )
        except Exception:
            pass

        # Sprint 56D: Analysis Sessions — shareable analysis results
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analysis_sessions (
                id TEXT PRIMARY KEY,
                user_id INTEGER,
                project_description TEXT NOT NULL,
                address TEXT,
                neighborhood TEXT,
                estimated_cost REAL,
                square_footage REAL,
                results_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                shared_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user ON analysis_sessions (user_id)",
            "CREATE INDEX IF NOT EXISTS idx_analysis_sessions_created ON analysis_sessions (created_at)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Sprint 56D: Users table — three-tier signup columns
        for alter_stmt in [
            "ALTER TABLE users ADD COLUMN referral_source TEXT DEFAULT 'invited'",
            "ALTER TABLE users ADD COLUMN detected_persona TEXT",
            "ALTER TABLE users ADD COLUMN beta_requested_at TIMESTAMP",
            "ALTER TABLE users ADD COLUMN beta_approved_at TIMESTAMP",
        ]:
            try:
                conn.execute(alter_stmt)
            except Exception:
                pass  # Column already exists

        # Sprint 56D: Beta requests queue (organic signups waiting for approval)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS beta_requests (
                id INTEGER PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                name TEXT,
                reason TEXT,
                ip TEXT,
                honeypot_filled BOOLEAN NOT NULL DEFAULT FALSE,
                status TEXT NOT NULL DEFAULT 'pending',
                admin_note TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                approved_at TIMESTAMP
            )
        """)
        for stmt in [
            "CREATE INDEX IF NOT EXISTS idx_beta_requests_email ON beta_requests (email)",
            "CREATE INDEX IF NOT EXISTS idx_beta_requests_status ON beta_requests (status)",
        ]:
            try:
                conn.execute(stmt)
            except Exception:
                pass

        # Sprint 61B: Projects + project_members (team seed)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS projects ("
            "id TEXT PRIMARY KEY, name TEXT, address TEXT, block TEXT, lot TEXT, "
            "neighborhood TEXT, created_by INTEGER, "
            "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS project_members ("
            "project_id TEXT NOT NULL, user_id INTEGER NOT NULL, "
            "role TEXT DEFAULT 'member', invited_by INTEGER, "
            "joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
            "PRIMARY KEY (project_id, user_id))"
        )
        for _s61b in [
            "CREATE INDEX IF NOT EXISTS idx_projects_created_by ON projects (created_by)",
            "CREATE INDEX IF NOT EXISTS idx_projects_parcel ON projects (block, lot)",
            "CREATE INDEX IF NOT EXISTS idx_pm_user ON project_members (user_id)",
            "ALTER TABLE analysis_sessions ADD COLUMN project_id TEXT",
            "CREATE INDEX IF NOT EXISTS idx_analysis_project ON analysis_sessions (project_id)",
        ]:
            try:
                conn.execute(_s61b)
            except Exception:
                pass  # Column/index already exists

        # QS5-A: Materialized parcel summary
        conn.execute("""
            CREATE TABLE IF NOT EXISTS parcel_summary (
                block TEXT NOT NULL, lot TEXT NOT NULL,
                canonical_address TEXT, neighborhood TEXT, supervisor_district TEXT,
                permit_count INTEGER DEFAULT 0, open_permit_count INTEGER DEFAULT 0,
                complaint_count INTEGER DEFAULT 0, violation_count INTEGER DEFAULT 0,
                boiler_permit_count INTEGER DEFAULT 0, inspection_count INTEGER DEFAULT 0,
                tax_value DOUBLE, zoning_code TEXT, use_definition TEXT,
                number_of_units INTEGER, health_tier TEXT, last_permit_date TEXT,
                refreshed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (block, lot)
            )
        """)

    finally:
        if close:
            conn.close()


# ── Legacy DuckDB-only functions (for ingestion scripts) ──────────

def init_schema(conn) -> None:
    """Create all DuckDB tables if they don't exist (ingestion only)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            permit_number TEXT NOT NULL,
            role TEXT,
            name TEXT,
            first_name TEXT,
            last_name TEXT,
            firm_name TEXT,
            pts_agent_id TEXT,
            license_number TEXT,
            sf_business_license TEXT,
            phone TEXT,
            address TEXT,
            city TEXT,
            state TEXT,
            zipcode TEXT,
            is_applicant TEXT,
            from_date TEXT,
            entity_id INTEGER,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            entity_id INTEGER PRIMARY KEY,
            canonical_name TEXT,
            canonical_firm TEXT,
            entity_type TEXT,
            pts_agent_id TEXT,
            license_number TEXT,
            sf_business_license TEXT,
            resolution_method TEXT,
            resolution_confidence TEXT,
            contact_count INTEGER,
            permit_count INTEGER,
            source_datasets TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS relationships (
            entity_id_a INTEGER,
            entity_id_b INTEGER,
            shared_permits INTEGER,
            permit_numbers TEXT,
            permit_types TEXT,
            date_range_start TEXT,
            date_range_end TEXT,
            total_estimated_cost DOUBLE,
            neighborhoods TEXT,
            PRIMARY KEY (entity_id_a, entity_id_b)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS permits (
            permit_number TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_type_definition TEXT,
            status TEXT,
            status_date TEXT,
            description TEXT,
            filed_date TEXT,
            issued_date TEXT,
            approved_date TEXT,
            completed_date TEXT,
            estimated_cost DOUBLE,
            revised_cost DOUBLE,
            existing_use TEXT,
            proposed_use TEXT,
            existing_units INTEGER,
            proposed_units INTEGER,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            zipcode TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            block TEXT,
            lot TEXT,
            adu TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY,
            reference_number TEXT,
            reference_number_type TEXT,
            inspector TEXT,
            scheduled_date TEXT,
            result TEXT,
            inspection_description TEXT,
            block TEXT,
            lot TEXT,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            zipcode TEXT,
            data_as_of TEXT,
            source TEXT DEFAULT 'building'
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS addenda (
            id                  INTEGER PRIMARY KEY,
            primary_key         TEXT,
            application_number  TEXT NOT NULL,
            addenda_number      INTEGER,
            step                INTEGER,
            station             TEXT,
            arrive              TEXT,
            assign_date         TEXT,
            start_date          TEXT,
            finish_date         TEXT,
            approved_date       TEXT,
            plan_checked_by     TEXT,
            review_results      TEXT,
            hold_description    TEXT,
            addenda_status      TEXT,
            department          TEXT,
            title               TEXT,
            data_as_of          TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY,
            complaint_number TEXT,
            item_sequence_number TEXT,
            date_filed TEXT,
            block TEXT,
            lot TEXT,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            unit TEXT,
            status TEXT,
            receiving_division TEXT,
            assigned_division TEXT,
            nov_category_description TEXT,
            item TEXT,
            nov_item_description TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            zipcode TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY,
            complaint_number TEXT,
            date_filed TEXT,
            date_abated TEXT,
            block TEXT,
            lot TEXT,
            parcel_number TEXT,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            unit TEXT,
            zip_code TEXT,
            complaint_description TEXT,
            status TEXT,
            nov_type TEXT,
            receiving_division TEXT,
            assigned_division TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id INTEGER PRIMARY KEY,
            certificate_number TEXT,
            ttxid TEXT,
            ownership_name TEXT,
            dba_name TEXT,
            full_business_address TEXT,
            city TEXT,
            state TEXT,
            business_zip TEXT,
            dba_start_date TEXT,
            dba_end_date TEXT,
            location_start_date TEXT,
            location_end_date TEXT,
            parking_tax TEXT,
            transient_occupancy_tax TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS boiler_permits (
            permit_number TEXT PRIMARY KEY,
            block TEXT,
            lot TEXT,
            status TEXT,
            boiler_type TEXT,
            boiler_serial_number TEXT,
            model TEXT,
            description TEXT,
            application_date TEXT,
            expiration_date TEXT,
            street_number TEXT,
            street_name TEXT,
            street_suffix TEXT,
            zip_code TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS fire_permits (
            permit_number TEXT PRIMARY KEY,
            permit_type TEXT,
            permit_type_description TEXT,
            permit_status TEXT,
            permit_address TEXT,
            permit_holder TEXT,
            dba_name TEXT,
            application_date TEXT,
            date_approved TEXT,
            expiration_date TEXT,
            permit_fee DOUBLE,
            posting_fee DOUBLE,
            referral_fee DOUBLE,
            conditions TEXT,
            battalion TEXT,
            fire_prevention_district TEXT,
            night_assembly_permit TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS planning_records (
            record_id TEXT PRIMARY KEY,
            record_type TEXT,
            record_status TEXT,
            block TEXT,
            lot TEXT,
            address TEXT,
            project_name TEXT,
            description TEXT,
            applicant TEXT,
            applicant_org TEXT,
            assigned_planner TEXT,
            open_date TEXT,
            environmental_doc_type TEXT,
            is_project BOOLEAN DEFAULT TRUE,
            units_existing INTEGER,
            units_proposed INTEGER,
            units_net DOUBLE,
            affordable_units INTEGER,
            child_id TEXT,
            parent_id TEXT,
            data_as_of TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tax_rolls (
            block TEXT,
            lot TEXT,
            tax_year TEXT,
            property_location TEXT,
            parcel_number TEXT,
            zoning_code TEXT,
            use_code TEXT,
            use_definition TEXT,
            property_class_code TEXT,
            property_class_code_definition TEXT,
            number_of_stories DOUBLE,
            number_of_units INTEGER,
            number_of_rooms INTEGER,
            number_of_bedrooms INTEGER,
            number_of_bathrooms DOUBLE,
            lot_area DOUBLE,
            property_area DOUBLE,
            assessed_land_value DOUBLE,
            assessed_improvement_value DOUBLE,
            assessed_personal_property DOUBLE,
            assessed_fixtures DOUBLE,
            current_sales_date TEXT,
            neighborhood TEXT,
            supervisor_district TEXT,
            data_as_of TEXT,
            PRIMARY KEY (block, lot, tax_year)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ingest_log (
            dataset_id TEXT PRIMARY KEY,
            dataset_name TEXT,
            last_fetched TEXT,
            records_fetched INTEGER,
            last_record_count INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS street_use_permits (
            permit_number       TEXT PRIMARY KEY,
            permit_type         TEXT,
            permit_purpose      TEXT,
            status              TEXT,
            agent               TEXT,
            agent_phone         TEXT,
            contact             TEXT,
            street_name         TEXT,
            cross_street_1      TEXT,
            cross_street_2      TEXT,
            plan_checker        TEXT,
            approved_date       TEXT,
            expiration_date     TEXT,
            neighborhood        TEXT,
            supervisor_district TEXT,
            latitude            DOUBLE,
            longitude           DOUBLE,
            cnn                 TEXT,
            data_as_of          TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS development_pipeline (
            record_id               TEXT PRIMARY KEY,
            bpa_no                  TEXT,
            case_no                 TEXT,
            name_address            TEXT,
            current_status          TEXT,
            description_dbi         TEXT,
            description_planning    TEXT,
            contact                 TEXT,
            sponsor                 TEXT,
            planner                 TEXT,
            proposed_units          INTEGER,
            existing_units          INTEGER,
            net_pipeline_units      INTEGER,
            affordable_units        INTEGER,
            zoning_district         TEXT,
            height_district         TEXT,
            neighborhood            TEXT,
            planning_district       TEXT,
            approved_date_planning  TEXT,
            block_lot               TEXT,
            latitude                DOUBLE,
            longitude               DOUBLE,
            data_as_of              TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS affordable_housing (
            project_id              TEXT PRIMARY KEY,
            project_name            TEXT,
            project_lead_sponsor    TEXT,
            planning_case_number    TEXT,
            address                 TEXT,
            total_project_units     INTEGER,
            affordable_units        INTEGER,
            affordable_percent      DOUBLE,
            construction_status     TEXT,
            housing_tenure          TEXT,
            housing_program         TEXT,
            supervisor_district     TEXT,
            neighborhood            TEXT,
            latitude                DOUBLE,
            longitude               DOUBLE,
            data_as_of              TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS housing_production (
            id                      INTEGER PRIMARY KEY,
            bpa                     TEXT,
            address                 TEXT,
            block_lot               TEXT,
            description             TEXT,
            permit_type             TEXT,
            issued_date             TEXT,
            first_completion_date   TEXT,
            latest_completion_date  TEXT,
            proposed_units          INTEGER,
            net_units               INTEGER,
            net_units_completed     INTEGER,
            market_rate             INTEGER,
            affordable_units        INTEGER,
            zoning_district         TEXT,
            neighborhood            TEXT,
            supervisor_district     TEXT,
            data_as_of              TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS dwelling_completions (
            id                          INTEGER PRIMARY KEY,
            building_address            TEXT,
            building_permit_application TEXT,
            date_issued                 TEXT,
            document_type               TEXT,
            number_of_units_certified   INTEGER,
            data_as_of                  TEXT
        )
    """)

    # Reference tables for predict_permits (Sprint 55B)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ref_zoning_routing (
            zoning_code TEXT PRIMARY KEY,
            zoning_category TEXT,
            planning_review_required BOOLEAN DEFAULT FALSE,
            fire_review_required BOOLEAN DEFAULT FALSE,
            health_review_required BOOLEAN DEFAULT FALSE,
            historic_district BOOLEAN DEFAULT FALSE,
            height_limit TEXT,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ref_permit_forms (
            id INTEGER PRIMARY KEY,
            project_type TEXT NOT NULL,
            permit_form TEXT NOT NULL,
            review_path TEXT,
            notes TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ref_agency_triggers (
            id INTEGER PRIMARY KEY,
            trigger_keyword TEXT NOT NULL,
            agency TEXT NOT NULL,
            reason TEXT,
            adds_weeks INTEGER
        )
    """)
    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_ref_forms_type ON ref_permit_forms (project_type)",
        "CREATE INDEX IF NOT EXISTS idx_ref_triggers_keyword ON ref_agency_triggers (trigger_keyword)",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass

    # Add source column to existing inspections tables (migration for pre-existing DBs)
    try:
        conn.execute("ALTER TABLE inspections ADD COLUMN source TEXT DEFAULT 'building'")
    except Exception:
        pass  # Column already exists
    # === SESSION F: REVIEW METRICS INGEST — 3 new metric tables ===
    conn.execute("""
        CREATE TABLE IF NOT EXISTS permit_issuance_metrics (
            id                  INTEGER PRIMARY KEY,
            bpa                 TEXT,
            addenda_number      INTEGER,
            bpa_addenda         TEXT,
            permit_type         TEXT,
            otc_ih              TEXT,
            status              TEXT,
            block               TEXT,
            lot                 TEXT,
            street_number       TEXT,
            street_name         TEXT,
            street_suffix       TEXT,
            unit                TEXT,
            description         TEXT,
            fire_only_permit    BOOLEAN,
            filed_date          TEXT,
            issued_date         TEXT,
            issued_status       TEXT,
            issued_year         TEXT,
            calendar_days       INTEGER,
            business_days       INTEGER,
            data_as_of          TEXT,
            ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS permit_review_metrics (
            id                  INTEGER PRIMARY KEY,
            primary_key         TEXT,
            bpa                 TEXT,
            addenda_number      INTEGER,
            bpa_addenda         TEXT,
            permit_type         TEXT,
            block               TEXT,
            lot                 TEXT,
            street_number       TEXT,
            street_name         TEXT,
            street_suffix       TEXT,
            description         TEXT,
            fire_only_permit    TEXT,
            filed_date          TEXT,
            status              TEXT,
            department          TEXT,
            station             TEXT,
            review_type         TEXT,
            review_number       INTEGER,
            review_results      TEXT,
            arrive_date         TEXT,
            start_year          TEXT,
            start_date          TEXT,
            start_date_source   TEXT,
            sla_days            INTEGER,
            due_date            TEXT,
            finish_date         TEXT,
            calendar_days       REAL,
            met_cal_sla         BOOLEAN,
            data_as_of          TEXT,
            ingested_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS planning_review_metrics (
            id                          INTEGER PRIMARY KEY,
            b1_alt_id                   TEXT,
            project_stage               TEXT,
            observation_window_type     TEXT,
            observation_window_date     TEXT,
            start_event_type            TEXT,
            start_event_date            TEXT,
            end_event_type              TEXT,
            end_event_date              TEXT,
            metric_value                REAL,
            sla_value                   REAL,
            metric_outcome              TEXT,
            data_as_of                  TEXT,
            ingested_at                 TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    for stmt in [
        "CREATE INDEX IF NOT EXISTS idx_pim_bpa ON permit_issuance_metrics (bpa)",
        "CREATE INDEX IF NOT EXISTS idx_pim_otc_ih ON permit_issuance_metrics (otc_ih)",
        "CREATE INDEX IF NOT EXISTS idx_pim_issued_year ON permit_issuance_metrics (issued_year)",
        "CREATE INDEX IF NOT EXISTS idx_prm_bpa ON permit_review_metrics (bpa)",
        "CREATE INDEX IF NOT EXISTS idx_prm_station ON permit_review_metrics (station)",
        "CREATE INDEX IF NOT EXISTS idx_prm_department ON permit_review_metrics (department)",
        "CREATE INDEX IF NOT EXISTS idx_prm_met_sla ON permit_review_metrics (met_cal_sla)",
        "CREATE INDEX IF NOT EXISTS idx_plrm_b1_alt_id ON planning_review_metrics (b1_alt_id)",
        "CREATE INDEX IF NOT EXISTS idx_plrm_stage ON planning_review_metrics (project_stage)",
        "CREATE INDEX IF NOT EXISTS idx_plrm_outcome ON planning_review_metrics (metric_outcome)",
    ]:
        try:
            conn.execute(stmt)
        except Exception:
            pass
    # === END SESSION F ===

    _create_indexes(conn)


def _create_indexes(conn) -> None:
    """Create indexes on key join columns (DuckDB)."""
    import duckdb
    indexes = [
        ("idx_contacts_permit", "contacts", "permit_number"),
        ("idx_contacts_pts_agent", "contacts", "pts_agent_id"),
        ("idx_contacts_license", "contacts", "license_number"),
        ("idx_contacts_sf_biz", "contacts", "sf_business_license"),
        ("idx_contacts_entity", "contacts", "entity_id"),
        ("idx_contacts_role", "contacts", "role"),
        ("idx_contacts_name", "contacts", "name"),
        ("idx_inspections_ref", "inspections", "reference_number"),
        ("idx_inspections_inspector", "inspections", "inspector"),
        ("idx_inspections_block_lot", "inspections", "block, lot"),
        ("idx_inspections_source", "inspections", "source"),
        ("idx_permits_neighborhood", "permits", "neighborhood"),
        ("idx_permits_block_lot", "permits", "block, lot"),
        ("idx_permits_street", "permits", "street_number, street_name"),
        ("idx_relationships_a", "relationships", "entity_id_a"),
        ("idx_relationships_b", "relationships", "entity_id_b"),
        ("idx_entities_name", "entities", "canonical_name"),
        ("idx_entities_license", "entities", "license_number"),
        ("idx_entities_pts", "entities", "pts_agent_id"),
        # Addenda indexes (main's 6 + department/status)
        ("idx_addenda_app_num", "addenda", "application_number"),
        ("idx_addenda_station", "addenda", "station"),
        ("idx_addenda_reviewer", "addenda", "plan_checked_by"),
        ("idx_addenda_finish", "addenda", "finish_date"),
        ("idx_addenda_app_step", "addenda", "application_number, addenda_number, step"),
        ("idx_addenda_primary_key", "addenda", "primary_key"),
        ("idx_addenda_dept", "addenda", "department"),
        ("idx_addenda_status", "addenda", "addenda_status"),
        # Violation indexes
        ("idx_violations_complaint", "violations", "complaint_number"),
        ("idx_violations_block_lot", "violations", "block, lot"),
        ("idx_violations_status", "violations", "status"),
        ("idx_violations_date", "violations", "date_filed"),
        # Complaint indexes
        ("idx_complaints_number", "complaints", "complaint_number"),
        ("idx_complaints_block_lot", "complaints", "block, lot"),
        ("idx_complaints_status", "complaints", "status"),
        ("idx_complaints_date", "complaints", "date_filed"),
        # Business indexes
        ("idx_businesses_ownership", "businesses", "ownership_name"),
        ("idx_businesses_dba", "businesses", "dba_name"),
        ("idx_businesses_zip", "businesses", "business_zip"),
        ("idx_businesses_cert", "businesses", "certificate_number"),
        # Boiler permit indexes
        ("idx_boiler_block_lot", "boiler_permits", "block, lot"),
        ("idx_boiler_status", "boiler_permits", "status"),
        # Fire permit indexes
        ("idx_fire_status", "fire_permits", "permit_status"),
        ("idx_fire_holder", "fire_permits", "permit_holder"),
        # Planning record indexes
        ("idx_planning_block_lot", "planning_records", "block, lot"),
        ("idx_planning_type", "planning_records", "record_type"),
        ("idx_planning_status", "planning_records", "record_status"),
        ("idx_planning_planner", "planning_records", "assigned_planner"),
        # Tax roll indexes
        ("idx_tax_zoning", "tax_rolls", "zoning_code"),
        ("idx_tax_block_lot", "tax_rolls", "block, lot"),
        ("idx_tax_neighborhood", "tax_rolls", "neighborhood"),
        # Street-use permit indexes
        ("idx_street_use_status", "street_use_permits", "status"),
        ("idx_street_use_street", "street_use_permits", "street_name"),
        ("idx_street_use_neighborhood", "street_use_permits", "neighborhood"),
        # Development pipeline indexes
        ("idx_dev_pipeline_bpa", "development_pipeline", "bpa_no"),
        ("idx_dev_pipeline_case", "development_pipeline", "case_no"),
        ("idx_dev_pipeline_block_lot", "development_pipeline", "block_lot"),
        ("idx_dev_pipeline_status", "development_pipeline", "current_status"),
        # Affordable housing indexes
        ("idx_affordable_status", "affordable_housing", "construction_status"),
        ("idx_affordable_case", "affordable_housing", "planning_case_number"),
        # Housing production indexes
        ("idx_housing_prod_bpa", "housing_production", "bpa"),
        ("idx_housing_prod_block_lot", "housing_production", "block_lot"),
        # Dwelling completions indexes
        ("idx_dwelling_permit", "dwelling_completions", "building_permit_application"),
        ("idx_dwelling_doc_type", "dwelling_completions", "document_type"),
    ]
    for idx_name, table, columns in indexes:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
        except duckdb.CatalogException:
            pass
