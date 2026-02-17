"""Database connection for sf-permits-mcp.

Supports two backends:
  - PostgreSQL (production on Railway) — when DATABASE_URL is set
  - DuckDB (local development) — fallback when no DATABASE_URL

The tools don't care which backend they're talking to — the SQL is
standard enough to work on both (with minor syntax helpers below).
"""

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


def get_connection(db_path: str | None = None):
    """Get a database connection (Postgres or DuckDB).

    Args:
        db_path: Optional DuckDB file path override (for ingestion scripts).
                 Ignored when BACKEND is 'postgres'.

    Returns a connection object. Caller is responsible for closing it.
    Both backends support: conn.execute(), conn.close(), cursor context.
    """
    if BACKEND == "postgres" and not db_path:
        import psycopg2
        try:
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=10)
            return conn
        except Exception as e:
            logger.error("Postgres connection failed: %s", e)
            raise
    else:
        import duckdb
        path = db_path or _DUCKDB_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        conn = duckdb.connect(path)
        return conn


def query(sql: str, params=None) -> list:
    """Execute a SELECT and return all rows as a list of tuples.

    Handles parameter style differences:
      - Postgres uses %s placeholders
      - DuckDB uses ? placeholders

    Callers should use %s style — this function auto-converts for DuckDB.
    """
    conn = get_connection()
    try:
        if BACKEND == "duckdb" and params:
            # Convert %s → ? for DuckDB
            sql = sql.replace("%s", "?")
        if BACKEND == "postgres":
            import psycopg2.extras
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchall()
        else:
            if params:
                return conn.execute(sql, params).fetchall()
            return conn.execute(sql).fetchall()
    finally:
        conn.close()


def query_one(sql: str, params=None):
    """Execute a SELECT and return the first row, or None."""
    rows = query(sql, params)
    return rows[0] if rows else None


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
                primary_street_name TEXT
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
        # Add columns for existing DuckDB databases
        for alter_stmt in [
            "ALTER TABLE feedback ADD COLUMN screenshot_data TEXT",
            "ALTER TABLE watch_items ADD COLUMN tags TEXT DEFAULT ''",
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
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_plan_sessions_created ON plan_analysis_sessions (created_at)")
        except Exception:
            pass

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
            data_as_of TEXT
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
        ("idx_permits_neighborhood", "permits", "neighborhood"),
        ("idx_permits_block_lot", "permits", "block, lot"),
        ("idx_permits_street", "permits", "street_number, street_name"),
        ("idx_relationships_a", "relationships", "entity_id_a"),
        ("idx_relationships_b", "relationships", "entity_id_b"),
        ("idx_entities_name", "entities", "canonical_name"),
        ("idx_entities_license", "entities", "license_number"),
        ("idx_entities_pts", "entities", "pts_agent_id"),
    ]
    for idx_name, table, columns in indexes:
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({columns})")
        except duckdb.CatalogException:
            pass
