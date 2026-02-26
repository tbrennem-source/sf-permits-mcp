"""Permit Prep — checklist generation and management for permit submission.

Creates checklists from predict_permits + required_documents output,
tracks document submission status per user per permit.
"""

import logging
from datetime import datetime

from src.db import BACKEND, get_connection, query, query_one, execute_write

logger = logging.getLogger(__name__)

# Valid item statuses
VALID_STATUSES = {"required", "submitted", "verified", "waived", "n_a"}

# Category ordering for display
CATEGORY_ORDER = ["plans", "forms", "supplemental", "agency"]
CATEGORY_LABELS = {
    "plans": "Required Plans",
    "forms": "Application Forms",
    "supplemental": "Supplemental Documents",
    "agency": "Agency-Specific",
}


def _categorize_document(doc_name: str) -> str:
    """Assign a category based on document name heuristics."""
    lower = doc_name.lower()
    if any(kw in lower for kw in ["plan", "drawing", "layout", "survey", "plot"]):
        return "plans"
    if any(kw in lower for kw in ["form", "application", "permit", "affidavit", "checklist", "certificate"]):
        return "forms"
    if any(kw in lower for kw in ["dph", "sffd", "sfpuc", "dpw", "planning department", "fire"]):
        return "agency"
    return "supplemental"


def create_checklist(permit_number: str, user_id: int, conn=None) -> int:
    """Generate checklist from predict_permits + required_documents output.

    Args:
        permit_number: The permit to create a checklist for.
        user_id: Owner of the checklist.
        conn: Optional DB connection (will create one if not provided).

    Returns:
        checklist_id of the created checklist.
    """
    from web.helpers import run_async
    from src.tools.predict_permits import predict_permits
    from src.tools.required_documents import required_documents as required_documents_tool

    own_conn = conn is None
    if own_conn:
        conn = get_connection()

    try:
        # Look up permit description from DB
        ph = "%s" if BACKEND == "postgres" else "?"
        description = ""
        permit_type_def = ""
        try:
            row = query_one(
                f"SELECT description, permit_type_definition FROM permits "
                f"WHERE permit_number = {ph} LIMIT 1",
                (permit_number,),
            )
            if row:
                description = row[0] or ""
                permit_type_def = row[1] or ""
        except Exception:
            pass

        if not description:
            description = permit_type_def or "general alterations"

        # Call predict_permits for form + review path
        try:
            _, prediction = run_async(predict_permits(
                project_description=description,
                return_structured=True,
            ))
        except Exception as e:
            logger.warning("predict_permits failed for %s: %s", permit_number, e)
            prediction = {}

        # Extract structured data from prediction
        form_info = prediction.get("form", {})
        form_name = form_info.get("form", "Form 3/8") if isinstance(form_info, dict) else "Form 3/8"
        review_info = prediction.get("review_path", {})
        review_path = review_info.get("path", "in_house") if isinstance(review_info, dict) else "in_house"
        agencies_list = prediction.get("agencies", [])
        agency_names = []
        for a in agencies_list:
            if isinstance(a, dict):
                agency_names.append(a.get("agency", ""))
            elif isinstance(a, str):
                agency_names.append(a)
        triggers = prediction.get("triggers", [])
        project_types = prediction.get("project_types", [])
        project_type = project_types[0] if project_types else None

        # Call required_documents for document list
        try:
            _, doc_data = run_async(required_documents_tool(
                permit_forms=[form_name],
                review_path=review_path,
                agency_routing=agency_names or None,
                project_type=project_type,
                triggers=triggers or None,
                return_structured=True,
            ))
        except Exception as e:
            logger.warning("required_documents failed for %s: %s", permit_number, e)
            doc_data = {}

        # Extract documents from structured data
        documents = []
        for cat_key in ["base_documents", "agency_documents", "trigger_documents",
                        "epr_requirements", "compliance_documents"]:
            items = doc_data.get(cat_key, [])
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, str):
                        documents.append(item)
                    elif isinstance(item, dict):
                        documents.append(item.get("name", item.get("document", str(item))))

        # Deduplicate
        seen = set()
        unique_docs = []
        for d in documents:
            d_lower = d.strip().lower()
            if d_lower and d_lower not in seen:
                seen.add(d_lower)
                unique_docs.append(d.strip())

        # Fallback: if no documents extracted, create minimal checklist
        if not unique_docs:
            unique_docs = [
                "Building Permit Application",
                "Construction plans (PDF for EPR)",
                "Construction cost estimate worksheet",
            ]

        # Insert checklist
        if BACKEND == "postgres":
            row = query_one(
                "INSERT INTO prep_checklists (permit_number, user_id) "
                "VALUES (%s, %s) RETURNING checklist_id",
                (permit_number, user_id),
            )
            checklist_id = row[0]
        else:
            execute_write(
                "INSERT INTO prep_checklists (permit_number, user_id) VALUES (?, ?)",
                (permit_number, user_id),
            )
            row = query_one("SELECT last_insert_rowid()")
            checklist_id = row[0]

        # Insert items
        for doc_name in unique_docs:
            category = _categorize_document(doc_name)
            if BACKEND == "postgres":
                execute_write(
                    "INSERT INTO prep_items (checklist_id, document_name, category, status, source) "
                    "VALUES (%s, %s, %s, 'required', 'predicted')",
                    (checklist_id, doc_name, category),
                )
            else:
                execute_write(
                    "INSERT INTO prep_items (checklist_id, document_name, category, status, source) "
                    "VALUES (?, ?, ?, 'required', 'predicted')",
                    (checklist_id, doc_name, category),
                )

        return checklist_id

    finally:
        if own_conn:
            conn.close()


def get_checklist(permit_number: str, user_id: int, conn=None) -> dict | None:
    """Return checklist with all items for a permit.

    Returns:
        Dict with checklist metadata and items grouped by category, or None.
    """
    ph = "%s" if BACKEND == "postgres" else "?"

    row = query_one(
        f"SELECT checklist_id, permit_number, user_id, created_at, updated_at "
        f"FROM prep_checklists WHERE permit_number = {ph} AND user_id = {ph} "
        f"ORDER BY created_at DESC LIMIT 1",
        (permit_number, user_id),
    )
    if not row:
        return None

    checklist_id = row[0]
    checklist = {
        "checklist_id": checklist_id,
        "permit_number": row[1],
        "user_id": row[2],
        "created_at": row[3],
        "updated_at": row[4],
        "items": [],
        "items_by_category": {},
        "progress": {},
    }

    items_rows = query(
        f"SELECT item_id, document_name, category, status, source, notes, due_date "
        f"FROM prep_items WHERE checklist_id = {ph} ORDER BY category, item_id",
        (checklist_id,),
    )

    items = []
    by_category = {cat: [] for cat in CATEGORY_ORDER}
    total = 0
    addressed = 0

    for r in (items_rows or []):
        item = {
            "item_id": r[0],
            "document_name": r[1],
            "category": r[2],
            "status": r[3],
            "source": r[4],
            "notes": r[5],
            "due_date": r[6],
        }
        items.append(item)
        cat = item["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)
        total += 1
        if item["status"] in ("submitted", "verified", "waived", "n_a"):
            addressed += 1

    checklist["items"] = items
    checklist["items_by_category"] = by_category
    checklist["progress"] = {
        "total": total,
        "addressed": addressed,
        "remaining": total - addressed,
        "percent": round((addressed / total * 100) if total > 0 else 0),
    }

    return checklist


def update_item_status(item_id: int, new_status: str, user_id: int, conn=None) -> dict | None:
    """Update a single item's status. Validate ownership.

    Returns:
        Updated item dict, or None if not found/not authorized.
    """
    if new_status not in VALID_STATUSES:
        return None

    ph = "%s" if BACKEND == "postgres" else "?"

    # Verify ownership
    row = query_one(
        f"SELECT pi.item_id, pi.document_name, pi.category, pi.source, pi.notes, pi.due_date, "
        f"pc.user_id, pc.checklist_id "
        f"FROM prep_items pi "
        f"JOIN prep_checklists pc ON pi.checklist_id = pc.checklist_id "
        f"WHERE pi.item_id = {ph}",
        (item_id,),
    )
    if not row:
        return None
    if row[6] != user_id:
        return None

    execute_write(
        f"UPDATE prep_items SET status = {ph} WHERE item_id = {ph}",
        (new_status, item_id),
    )

    # Update checklist timestamp
    checklist_id = row[7]
    try:
        if BACKEND == "postgres":
            execute_write(
                "UPDATE prep_checklists SET updated_at = NOW() WHERE checklist_id = %s",
                (checklist_id,),
            )
        else:
            execute_write(
                "UPDATE prep_checklists SET updated_at = CURRENT_TIMESTAMP WHERE checklist_id = ?",
                (checklist_id,),
            )
    except Exception:
        pass

    return {
        "item_id": item_id,
        "document_name": row[1],
        "category": row[2],
        "status": new_status,
        "source": row[3],
        "notes": row[4],
        "due_date": row[5],
    }


def get_user_checklists(user_id: int, conn=None) -> list[dict]:
    """Return all checklists for a user with progress summary."""
    ph = "%s" if BACKEND == "postgres" else "?"

    rows = query(
        f"SELECT checklist_id, permit_number, created_at, updated_at "
        f"FROM prep_checklists WHERE user_id = {ph} ORDER BY updated_at DESC",
        (user_id,),
    )

    checklists = []
    for r in (rows or []):
        checklist_id = r[0]
        # Count items by status
        item_rows = query(
            f"SELECT status, COUNT(*) FROM prep_items "
            f"WHERE checklist_id = {ph} GROUP BY status",
            (checklist_id,),
        )
        total = 0
        addressed = 0
        missing_required = 0
        for ir in (item_rows or []):
            count = ir[1]
            total += count
            if ir[0] in ("submitted", "verified", "waived", "n_a"):
                addressed += count
            if ir[0] == "required":
                missing_required += count

        checklists.append({
            "checklist_id": checklist_id,
            "permit_number": r[1],
            "created_at": r[2],
            "updated_at": r[3],
            "total_items": total,
            "completed_items": addressed,
            "missing_required": missing_required,
            "percent": round((addressed / total * 100) if total > 0 else 0),
        })

    return checklists


def preview_checklist(permit_number: str, conn=None) -> dict:
    """Generate predicted checklist without saving — for Preview Mode.

    Returns:
        Dict with items grouped by category (not persisted).
    """
    from web.helpers import run_async
    from src.tools.predict_permits import predict_permits
    from src.tools.required_documents import required_documents as required_documents_tool

    # Look up permit description
    ph = "%s" if BACKEND == "postgres" else "?"
    description = ""
    try:
        row = query_one(
            f"SELECT description, permit_type_definition FROM permits "
            f"WHERE permit_number = {ph} LIMIT 1",
            (permit_number,),
        )
        if row:
            description = row[0] or row[1] or ""
    except Exception:
        pass

    if not description:
        description = "general alterations"

    # Predict
    try:
        _, prediction = run_async(predict_permits(
            project_description=description,
            return_structured=True,
        ))
    except Exception:
        prediction = {}

    form_info = prediction.get("form", {})
    form_name = form_info.get("form", "Form 3/8") if isinstance(form_info, dict) else "Form 3/8"
    review_info = prediction.get("review_path", {})
    review_path = review_info.get("path", "in_house") if isinstance(review_info, dict) else "in_house"
    agencies_list = prediction.get("agencies", [])
    agency_names = [a.get("agency", "") if isinstance(a, dict) else a for a in agencies_list]
    triggers = prediction.get("triggers", [])
    project_types = prediction.get("project_types", [])
    project_type = project_types[0] if project_types else None

    try:
        _, doc_data = run_async(required_documents_tool(
            permit_forms=[form_name],
            review_path=review_path,
            agency_routing=agency_names or None,
            project_type=project_type,
            triggers=triggers or None,
            return_structured=True,
        ))
    except Exception:
        doc_data = {}

    documents = []
    for cat_key in ["base_documents", "agency_documents", "trigger_documents",
                    "epr_requirements", "compliance_documents"]:
        items = doc_data.get(cat_key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    documents.append(item)
                elif isinstance(item, dict):
                    documents.append(item.get("name", item.get("document", str(item))))

    seen = set()
    unique_docs = []
    for d in documents:
        d_lower = d.strip().lower()
        if d_lower and d_lower not in seen:
            seen.add(d_lower)
            unique_docs.append(d.strip())

    if not unique_docs:
        unique_docs = [
            "Building Permit Application",
            "Construction plans (PDF for EPR)",
            "Construction cost estimate worksheet",
        ]

    items = []
    by_category = {cat: [] for cat in CATEGORY_ORDER}
    for doc_name in unique_docs:
        category = _categorize_document(doc_name)
        item = {
            "document_name": doc_name,
            "category": category,
            "status": "required",
            "source": "predicted",
        }
        items.append(item)
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(item)

    return {
        "permit_number": permit_number,
        "items": items,
        "items_by_category": by_category,
        "total_items": len(items),
        "prediction": {
            "form": form_name,
            "review_path": review_path,
            "agencies": agency_names,
            "project_type": project_type,
        },
        "is_preview": True,
    }
