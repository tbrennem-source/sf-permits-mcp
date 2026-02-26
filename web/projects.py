"""Sprint 61B: Projects Blueprint — team seed (projects + members + auto-create + auto-join).

Provides:
  - _create_project(address, block, lot, neighborhood, user_id)
  - _get_or_create_project(address, block, lot, neighborhood, user_id)
  - _auto_join_project(user_id, analysis_id)
  - GET  /projects           — list user's projects
  - GET  /project/<id>       — project detail with members + analyses
  - POST /project/<id>/invite — email invite to collaborator
  - POST /project/<id>/join  — self-join a project (linked via shared analysis)
"""

from __future__ import annotations

import logging
import uuid

from flask import Blueprint, abort, g, jsonify, redirect, render_template, request, url_for

logger = logging.getLogger(__name__)

projects_bp = Blueprint("projects", __name__)

_TABLES_INITIALIZED = False


def _ensure_tables() -> None:
    """Lazy DDL: create projects + project_members + project_id column if they don't exist.

    Called on first use so tests with a fresh DuckDB get the schema automatically.
    Idempotent — safe to call multiple times.
    """
    global _TABLES_INITIALIZED
    if _TABLES_INITIALIZED:
        return
    _TABLES_INITIALIZED = True
    try:
        from src.db import get_connection, BACKEND, _DUCKDB_PATH
        conn = get_connection()
        try:
            if BACKEND == "postgres":
                import psycopg2
                conn.autocommit = False
                cur = conn.cursor()
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS projects ("
                    "id TEXT PRIMARY KEY, name TEXT, address TEXT, block TEXT, lot TEXT, "
                    "neighborhood TEXT, created_by INTEGER, "
                    "created_at TIMESTAMPTZ DEFAULT NOW())"
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_projects_parcel ON projects(block, lot)")
                cur.execute(
                    "CREATE TABLE IF NOT EXISTS project_members ("
                    "project_id TEXT, user_id INTEGER, role TEXT DEFAULT 'member', "
                    "invited_by INTEGER, joined_at TIMESTAMPTZ DEFAULT NOW(), "
                    "PRIMARY KEY (project_id, user_id))"
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_pm_user ON project_members(user_id)")
                cur.execute(
                    "ALTER TABLE analysis_sessions ADD COLUMN IF NOT EXISTS project_id TEXT"
                )
                conn.commit()
            else:
                for _ddl in [
                    ("CREATE TABLE IF NOT EXISTS projects ("
                     "id TEXT PRIMARY KEY, name TEXT, address TEXT, block TEXT, lot TEXT, "
                     "neighborhood TEXT, created_by INTEGER, "
                     "created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"),
                    "CREATE INDEX IF NOT EXISTS idx_projects_parcel ON projects (block, lot)",
                    ("CREATE TABLE IF NOT EXISTS project_members ("
                     "project_id TEXT NOT NULL, user_id INTEGER NOT NULL, "
                     "role TEXT DEFAULT 'member', invited_by INTEGER, "
                     "joined_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, "
                     "PRIMARY KEY (project_id, user_id))"),
                    "CREATE INDEX IF NOT EXISTS idx_pm_user ON project_members (user_id)",
                    "ALTER TABLE analysis_sessions ADD COLUMN project_id TEXT",
                    "CREATE INDEX IF NOT EXISTS idx_analysis_project ON analysis_sessions (project_id)",
                ]:
                    try:
                        conn.execute(_ddl)
                    except Exception:
                        pass
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("_ensure_tables failed: %s", exc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_project(
    address: str | None,
    block: str | None,
    lot: str | None,
    neighborhood: str | None,
    user_id: int,
) -> str | None:
    """Create a new project owned by user_id. Returns project id or None on failure.

    Does NOT create a project when address, block, AND lot are all null.
    """
    _ensure_tables()
    if not address and not block and not lot:
        return None
    from src.db import execute_write as _ew, BACKEND
    project_id = str(uuid.uuid4())
    name = address or (f"Block {block} Lot {lot}" if block and lot else "Untitled Project")
    try:
        if BACKEND == "postgres":
            _ew(
                "INSERT INTO projects (id, name, address, block, lot, neighborhood, created_by) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (project_id, name, address, block, lot, neighborhood, user_id),
            )
            _ew(
                "INSERT INTO project_members (project_id, user_id, role, invited_by) "
                "VALUES (%s, %s, 'owner', %s)",
                (project_id, user_id, user_id),
            )
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                conn.execute(
                    "INSERT INTO projects (id, name, address, block, lot, neighborhood, created_by) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    [project_id, name, address, block, lot, neighborhood, user_id],
                )
                conn.execute(
                    "INSERT INTO project_members (project_id, user_id, role, invited_by) "
                    "VALUES (?, ?, 'owner', ?)",
                    [project_id, user_id, user_id],
                )
            finally:
                conn.close()
        return project_id
    except Exception as exc:
        logger.warning("_create_project failed: %s", exc)
        return None


def _get_or_create_project(
    address: str | None,
    block: str | None,
    lot: str | None,
    neighborhood: str | None,
    user_id: int,
) -> str | None:
    """Find or create a project deduped by parcel (block+lot). Returns project id or None.

    - If block AND lot are known: look for an existing project with matching parcel.
    - If found: add user as member if not already; return existing project id.
    - If not found: create new project and return its id.
    - If address/block/lot are all None: return None (no project).
    """
    _ensure_tables()
    if not address and not block and not lot:
        return None
    from src.db import query_one as _qone, execute_write as _ew, BACKEND

    # Parcel dedup: only deduplicate when we have both block and lot
    if block and lot:
        try:
            if BACKEND == "postgres":
                existing = _qone(
                    "SELECT id FROM projects WHERE block = %s AND lot = %s ORDER BY created_at LIMIT 1",
                    (block, lot),
                )
            else:
                import duckdb as _duck
                from src.db import _DUCKDB_PATH
                conn = _duck.connect(_DUCKDB_PATH)
                try:
                    row = conn.execute(
                        "SELECT id FROM projects WHERE block = ? AND lot = ? ORDER BY created_at LIMIT 1",
                        [block, lot],
                    ).fetchone()
                    existing = row
                finally:
                    conn.close()
            if existing:
                project_id = existing[0]
                # Add user as member if not already (idempotent)
                try:
                    if BACKEND == "postgres":
                        _ew(
                            "INSERT INTO project_members (project_id, user_id, role, invited_by) "
                            "VALUES (%s, %s, 'member', %s) ON CONFLICT DO NOTHING",
                            (project_id, user_id, user_id),
                        )
                    else:
                        import duckdb as _duck2
                        conn2 = _duck2.connect(_DUCKDB_PATH)
                        try:
                            row2 = conn2.execute(
                                "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
                                [project_id, user_id],
                            ).fetchone()
                            if not row2:
                                conn2.execute(
                                    "INSERT INTO project_members (project_id, user_id, role, invited_by) "
                                    "VALUES (?, ?, 'member', ?)",
                                    [project_id, user_id, user_id],
                                )
                        finally:
                            conn2.close()
                except Exception as exc:
                    logger.warning("_get_or_create_project member insert failed: %s", exc)
                return project_id
        except Exception as exc:
            logger.warning("_get_or_create_project lookup failed: %s", exc)
            # Fall through to create

    return _create_project(address, block, lot, neighborhood, user_id)


def _auto_join_project(user_id: int, analysis_id: str) -> str | None:
    """On signup via shared link: look up project_id from analysis_sessions, add user as member.

    Also auto-adds address to watch_items if address is known.
    Returns project_id or None if not applicable.
    """
    _ensure_tables()
    from src.db import query_one as _qone, execute_write as _ew, BACKEND
    try:
        if BACKEND == "postgres":
            row = _qone(
                "SELECT project_id, address FROM analysis_sessions WHERE id = %s",
                (analysis_id,),
            )
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                row = conn.execute(
                    "SELECT project_id, address FROM analysis_sessions WHERE id = ?",
                    [analysis_id],
                ).fetchone()
            finally:
                conn.close()
    except Exception as exc:
        logger.warning("_auto_join_project session lookup failed: %s", exc)
        return None

    if not row or not row[0]:
        return None

    project_id = row[0]
    address = row[1]

    # Add member (idempotent)
    try:
        if BACKEND == "postgres":
            _ew(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (%s, %s, 'member') ON CONFLICT DO NOTHING",
                (project_id, user_id),
            )
        else:
            import duckdb as _duck2
            from src.db import _DUCKDB_PATH
            conn2 = _duck2.connect(_DUCKDB_PATH)
            try:
                existing = conn2.execute(
                    "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
                    [project_id, user_id],
                ).fetchone()
                if not existing:
                    conn2.execute(
                        "INSERT INTO project_members (project_id, user_id, role) VALUES (?, ?, 'member')",
                        [project_id, user_id],
                    )
            finally:
                conn2.close()
    except Exception as exc:
        logger.warning("_auto_join_project member insert failed: %s", exc)

    # Auto-add address to watch_items if we have one
    if address:
        try:
            from web.auth import get_watches
            existing_watches = get_watches(user_id)
            already_watching = any(
                w.get("address", "").lower() == address.lower()
                for w in (existing_watches or [])
            )
            if not already_watching:
                if BACKEND == "postgres":
                    _ew(
                        "INSERT INTO watch_items (user_id, address, created_at) "
                        "VALUES (%s, %s, NOW())",
                        (user_id, address),
                    )
                else:
                    import duckdb as _duck3
                    conn3 = _duck3.connect(_DUCKDB_PATH)
                    try:
                        conn3.execute(
                            "INSERT INTO watch_items (user_id, address) VALUES (?, ?)",
                            [user_id, address],
                        )
                    finally:
                        conn3.close()
        except Exception as exc:
            logger.warning("_auto_join_project watch insert failed (non-fatal): %s", exc)

    return project_id


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@projects_bp.route("/projects")
def projects_list():
    """List all projects the current user belongs to."""
    if not g.user:
        return redirect(url_for("auth_login"))
    user_id = g.user["user_id"]
    from src.db import query as _qa, BACKEND
    try:
        if BACKEND == "postgres":
            rows = _qa(
                "SELECT p.id, p.name, p.address, p.neighborhood, pm.role, "
                "       p.created_at, p.created_by "
                "FROM projects p "
                "JOIN project_members pm ON pm.project_id = p.id "
                "WHERE pm.user_id = %s "
                "ORDER BY p.created_at DESC",
                (user_id,),
            )
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                rows = conn.execute(
                    "SELECT p.id, p.name, p.address, p.neighborhood, pm.role, "
                    "       p.created_at, p.created_by "
                    "FROM projects p "
                    "JOIN project_members pm ON pm.project_id = p.id "
                    "WHERE pm.user_id = ? "
                    "ORDER BY p.created_at DESC",
                    [user_id],
                ).fetchall()
            finally:
                conn.close()
    except Exception as exc:
        logger.warning("projects_list query failed: %s", exc)
        rows = []

    projects = []
    for r in (rows or []):
        projects.append({
            "id": r[0],
            "name": r[1] or r[2] or "Untitled Project",
            "address": r[2],
            "neighborhood": r[3],
            "role": r[4],
            "created_at": r[5],
            "created_by": r[6],
        })
    return render_template("projects.html", projects=projects, active_page="projects")


@projects_bp.route("/project/<project_id>")
def project_detail(project_id):
    """Show project detail: meta, members, linked analyses."""
    if not g.user:
        return redirect(url_for("auth_login"))
    user_id = g.user["user_id"]
    from src.db import query_one as _qone, query as _qa, BACKEND

    # Load project
    try:
        if BACKEND == "postgres":
            proj_row = _qone(
                "SELECT id, name, address, block, lot, neighborhood, created_by, created_at "
                "FROM projects WHERE id = %s",
                (project_id,),
            )
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                proj_row = conn.execute(
                    "SELECT id, name, address, block, lot, neighborhood, created_by, created_at "
                    "FROM projects WHERE id = ?",
                    [project_id],
                ).fetchone()
            finally:
                conn.close()
    except Exception as exc:
        logger.warning("project_detail project query failed: %s", exc)
        proj_row = None

    if not proj_row:
        abort(404)

    # Auth check: must be a member
    try:
        if BACKEND == "postgres":
            mem_row = _qone(
                "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
                (project_id, user_id),
            )
        else:
            import duckdb as _duck2
            from src.db import _DUCKDB_PATH
            conn2 = _duck2.connect(_DUCKDB_PATH)
            try:
                mem_row = conn2.execute(
                    "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                    [project_id, user_id],
                ).fetchone()
            finally:
                conn2.close()
    except Exception:
        mem_row = None

    if not mem_row and not g.user.get("is_admin"):
        abort(403)

    my_role = mem_row[0] if mem_row else "observer"

    # Load members
    try:
        if BACKEND == "postgres":
            member_rows = _qa(
                "SELECT u.email, u.display_name, pm.role, pm.joined_at "
                "FROM project_members pm "
                "JOIN users u ON u.user_id = pm.user_id "
                "WHERE pm.project_id = %s "
                "ORDER BY pm.joined_at",
                (project_id,),
            )
        else:
            import duckdb as _duck3
            from src.db import _DUCKDB_PATH
            conn3 = _duck3.connect(_DUCKDB_PATH)
            try:
                member_rows = conn3.execute(
                    "SELECT u.email, u.display_name, pm.role, pm.joined_at "
                    "FROM project_members pm "
                    "JOIN users u ON u.user_id = pm.user_id "
                    "WHERE pm.project_id = ? "
                    "ORDER BY pm.joined_at",
                    [project_id],
                ).fetchall()
            finally:
                conn3.close()
    except Exception as exc:
        logger.warning("project_detail members query failed: %s", exc)
        member_rows = []

    members = [
        {"email": r[0], "display_name": r[1] or r[0], "role": r[2], "joined_at": r[3]}
        for r in (member_rows or [])
    ]

    # Load linked analyses
    try:
        if BACKEND == "postgres":
            analysis_rows = _qa(
                "SELECT id, project_description, address, created_at "
                "FROM analysis_sessions WHERE project_id = %s ORDER BY created_at DESC LIMIT 20",
                (project_id,),
            )
        else:
            import duckdb as _duck4
            from src.db import _DUCKDB_PATH
            conn4 = _duck4.connect(_DUCKDB_PATH)
            try:
                analysis_rows = conn4.execute(
                    "SELECT id, project_description, address, created_at "
                    "FROM analysis_sessions WHERE project_id = ? ORDER BY created_at DESC LIMIT 20",
                    [project_id],
                ).fetchall()
            finally:
                conn4.close()
    except Exception as exc:
        logger.warning("project_detail analyses query failed: %s", exc)
        analysis_rows = []

    analyses = [
        {
            "id": r[0],
            "description": (r[1] or "")[:80],
            "address": r[2],
            "created_at": r[3],
        }
        for r in (analysis_rows or [])
    ]

    project = {
        "id": proj_row[0],
        "name": proj_row[1] or proj_row[2] or "Untitled Project",
        "address": proj_row[2],
        "block": proj_row[3],
        "lot": proj_row[4],
        "neighborhood": proj_row[5],
        "created_by": proj_row[6],
        "created_at": proj_row[7],
    }

    return render_template(
        "project_detail.html",
        project=project,
        members=members,
        analyses=analyses,
        my_role=my_role,
        active_page="projects",
    )


@projects_bp.route("/project/<project_id>/invite", methods=["POST"])
def project_invite(project_id):
    """Send an email invite to a collaborator (owner/admin only)."""
    if not g.user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401
    user_id = g.user["user_id"]
    from src.db import query_one as _qone, BACKEND

    # Auth: must be owner or admin
    try:
        if BACKEND == "postgres":
            mem_row = _qone(
                "SELECT role FROM project_members WHERE project_id = %s AND user_id = %s",
                (project_id, user_id),
            )
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                mem_row = conn.execute(
                    "SELECT role FROM project_members WHERE project_id = ? AND user_id = ?",
                    [project_id, user_id],
                ).fetchone()
            finally:
                conn.close()
    except Exception:
        mem_row = None

    if not mem_row:
        return jsonify({"ok": False, "error": "Not a member of this project"}), 403
    if mem_row[0] not in ("owner", "admin") and not g.user.get("is_admin"):
        return jsonify({"ok": False, "error": "Only project owners can invite members"}), 403

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "error": "Valid email required"}), 400

    # Load project info for email
    try:
        if BACKEND == "postgres":
            proj_row = _qone("SELECT name, address FROM projects WHERE id = %s", (project_id,))
        else:
            import duckdb as _duck2
            from src.db import _DUCKDB_PATH
            conn2 = _duck2.connect(_DUCKDB_PATH)
            try:
                proj_row = conn2.execute(
                    "SELECT name, address FROM projects WHERE id = ?", [project_id]
                ).fetchone()
            finally:
                conn2.close()
    except Exception:
        proj_row = None

    project_name = proj_row[0] if proj_row else "a permit project"

    # Send invite email
    try:
        from web.auth import BASE_URL, SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USER, SMTP_PASS
        import smtplib
        from email.message import EmailMessage

        invite_url = f"{BASE_URL}/auth/login?referral_source=project_invite&project_id={project_id}"
        sender_name = g.user.get("display_name") or g.user.get("email", "sfpermits.ai")

        msg = EmailMessage()
        msg["Subject"] = f"{sender_name} invited you to collaborate on {project_name}"
        msg["From"] = SMTP_FROM
        msg["To"] = email
        msg.set_content(
            f"{sender_name} has invited you to collaborate on {project_name} on sfpermits.ai.\n\n"
            f"Click here to join: {invite_url}\n\n"
            "sfpermits.ai — AI-powered permit guidance for San Francisco."
        )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(SMTP_USER, SMTP_PASS)
            smtp.send_message(msg)

        return jsonify({"ok": True, "message": f"Invite sent to {email}"})
    except Exception as exc:
        logger.warning("project_invite email failed: %s", exc)
        return jsonify({"ok": False, "error": "Failed to send invite email"}), 500


@projects_bp.route("/project/<project_id>/join", methods=["POST"])
def project_join(project_id):
    """Self-join a project (must be logged in; project must exist)."""
    if not g.user:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401
    user_id = g.user["user_id"]
    from src.db import query_one as _qone, execute_write as _ew, BACKEND

    # Check project exists
    try:
        if BACKEND == "postgres":
            proj_row = _qone("SELECT id FROM projects WHERE id = %s", (project_id,))
        else:
            import duckdb as _duck
            from src.db import _DUCKDB_PATH
            conn = _duck.connect(_DUCKDB_PATH)
            try:
                proj_row = conn.execute(
                    "SELECT id FROM projects WHERE id = ?", [project_id]
                ).fetchone()
            finally:
                conn.close()
    except Exception:
        proj_row = None

    if not proj_row:
        return jsonify({"ok": False, "error": "Project not found"}), 404

    # Add member (idempotent)
    try:
        if BACKEND == "postgres":
            _ew(
                "INSERT INTO project_members (project_id, user_id, role) "
                "VALUES (%s, %s, 'member') ON CONFLICT DO NOTHING",
                (project_id, user_id),
            )
        else:
            import duckdb as _duck2
            from src.db import _DUCKDB_PATH
            conn2 = _duck2.connect(_DUCKDB_PATH)
            try:
                existing = conn2.execute(
                    "SELECT 1 FROM project_members WHERE project_id = ? AND user_id = ?",
                    [project_id, user_id],
                ).fetchone()
                if not existing:
                    conn2.execute(
                        "INSERT INTO project_members (project_id, user_id, role) "
                        "VALUES (?, ?, 'member')",
                        [project_id, user_id],
                    )
            finally:
                conn2.close()
        return jsonify({"ok": True, "project_id": project_id})
    except Exception as exc:
        logger.warning("project_join failed: %s", exc)
        return jsonify({"ok": False, "error": "Failed to join project"}), 500
