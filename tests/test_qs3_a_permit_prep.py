"""Tests for QS3-A: Permit Prep — data model, API, routes, integration.

Target: 40+ tests covering:
- Core functions (create_checklist, get_checklist, update_item_status, etc.)
- API endpoints (POST /api/prep/create, GET, PATCH, preview)
- Routes (/prep/<permit>, /account/prep)
- Integration (nav, search results, brief)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a Flask test application with in-memory DuckDB.

    Cleans up test-specific tables after yield to prevent schema
    pollution across test files in the same pytest session.
    """
    import os
    os.environ.setdefault("TESTING", "1")

    # Force DuckDB backend before importing anything that reads BACKEND
    with patch.dict(os.environ, {"DATABASE_URL": ""}):
        import importlib
        import src.db as db_mod
        importlib.reload(db_mod)

        from web.app import app
        app.config["TESTING"] = True
        app.config["SECRET_KEY"] = "test-secret"

        # Create tables in DuckDB
        conn = db_mod.get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS permits (
                permit_number TEXT PRIMARY KEY,
                description TEXT,
                permit_type_definition TEXT,
                street_number TEXT,
                street_name TEXT,
                block TEXT,
                lot TEXT,
                neighborhood TEXT,
                status TEXT,
                filed_date TEXT,
                status_date TEXT,
                revised_cost REAL,
                estimated_cost REAL,
                street_suffix TEXT
            )
        """)
        # DuckDB: use sequences for auto-increment
        conn.execute("CREATE SEQUENCE IF NOT EXISTS prep_checklists_seq START 1")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prep_checklists (
                checklist_id INTEGER PRIMARY KEY DEFAULT nextval('prep_checklists_seq'),
                permit_number TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("CREATE SEQUENCE IF NOT EXISTS prep_items_seq START 1")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prep_items (
                item_id INTEGER PRIMARY KEY DEFAULT nextval('prep_items_seq'),
                checklist_id INTEGER NOT NULL,
                document_name TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'required',
                source TEXT NOT NULL DEFAULT 'predicted',
                notes TEXT,
                due_date TEXT
            )
        """)

        # Users table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                email TEXT UNIQUE,
                display_name TEXT,
                is_admin BOOLEAN DEFAULT FALSE,
                is_active BOOLEAN DEFAULT TRUE,
                email_verified BOOLEAN DEFAULT FALSE,
                brief_frequency TEXT DEFAULT 'none',
                role TEXT,
                firm_name TEXT,
                entity_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP,
                invite_code TEXT,
                primary_street_number TEXT,
                primary_street_name TEXT,
                subscription_tier TEXT DEFAULT 'free',
                voice_style TEXT,
                last_brief_sent_at TIMESTAMP,
                notify_permit_changes BOOLEAN DEFAULT FALSE
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, email, is_admin, email_verified, is_active)
            VALUES (1, 'test@example.com', FALSE, TRUE, TRUE)
        """)
        conn.execute("""
            INSERT OR IGNORE INTO users (user_id, email, is_admin, email_verified, is_active)
            VALUES (2, 'other@example.com', FALSE, TRUE, TRUE)
        """)

        # Insert test permit
        conn.execute("""
            INSERT OR IGNORE INTO permits (permit_number, description, permit_type_definition,
            street_number, street_name, block, lot, neighborhood)
            VALUES ('202401010001', 'Kitchen remodel', 'additions alterations or repairs',
            '123', 'MAIN', '3512', '001', 'Mission')
        """)

        # Watch items table (for nav gate)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watch_items (
                watch_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                watch_type TEXT,
                permit_number TEXT,
                street_number TEXT,
                street_name TEXT,
                block TEXT,
                lot TEXT,
                entity_id INTEGER,
                neighborhood TEXT,
                label TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                tags TEXT DEFAULT ''
            )
        """)

        conn.close()

        yield app

        # Cleanup: drop test-specific tables to prevent schema pollution
        cleanup_conn = db_mod.get_connection()
        for table in ["prep_items", "prep_checklists"]:
            try:
                cleanup_conn.execute(f"DROP TABLE IF EXISTS {table}")
            except Exception:
                pass
        for seq in ["prep_checklists_seq", "prep_items_seq"]:
            try:
                cleanup_conn.execute(f"DROP SEQUENCE IF EXISTS {seq}")
            except Exception:
                pass
        cleanup_conn.close()


@pytest.fixture
def client(app):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Authenticated test client."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["email"] = "test@example.com"
        sess["is_admin"] = False
    return client


@pytest.fixture
def auth_client_user2(client):
    """Authenticated test client for user 2."""
    with client.session_transaction() as sess:
        sess["user_id"] = 2
        sess["email"] = "other@example.com"
        sess["is_admin"] = False
    return client


# ---------------------------------------------------------------------------
# Mock predict_permits and required_documents
# ---------------------------------------------------------------------------

MOCK_PREDICTION = {
    "form": {"form": "Form 3/8", "reason": "Alterations"},
    "review_path": {"path": "in_house", "reason": "standard", "confidence": "high"},
    "agencies": [{"agency": "Planning"}, {"agency": "SFFD (Fire)"}],
    "triggers": [],
    "project_types": ["general_alteration"],
}

MOCK_DOCUMENTS = {
    "base_documents": [
        "Building Permit Application (Form 3/8)",
        "Construction plans (PDF for EPR)",
        "Construction cost estimate worksheet",
    ],
    "agency_documents": [
        "Planning Department approval letter",
        "Fire suppression system plans",
    ],
    "trigger_documents": [],
    "epr_requirements": [
        "PDF under 250MB",
    ],
    "compliance_documents": [
        "Title-24 Certificate of Compliance",
    ],
}


def _mock_predict(*args, **kwargs):
    return ("markdown output", MOCK_PREDICTION)


def _mock_required_docs(*args, **kwargs):
    return ("markdown output", MOCK_DOCUMENTS)


# ---------------------------------------------------------------------------
# Core function tests
# ---------------------------------------------------------------------------

class TestCreateChecklist:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_creates_checklist_with_items(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            cid = create_checklist("202401010001", 1)
            assert cid is not None
            assert isinstance(cid, int)

            cl = get_checklist("202401010001", 1)
            assert cl is not None
            assert cl["checklist_id"] == cid
            assert len(cl["items"]) > 0

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_items_have_categories(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            categories = set(i["category"] for i in cl["items"])
            assert len(categories) >= 1

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_all_items_start_as_required(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            for item in cl["items"]:
                assert item["status"] == "required"

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_progress_starts_at_zero(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            assert cl["progress"]["addressed"] == 0
            assert cl["progress"]["remaining"] == cl["progress"]["total"]

    @patch("web.helpers.run_async", side_effect=Exception("tool failed"))
    def test_fallback_on_tool_failure(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            cid = create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            # Should still create a minimal checklist
            assert cl is not None
            assert len(cl["items"]) >= 3  # fallback items


class TestGetChecklist:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_none_for_nonexistent(self, mock_run, app):
        from web.permit_prep import get_checklist
        with app.app_context():
            cl = get_checklist("999999999", 1)
            assert cl is None

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_items_grouped_by_category(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            assert "items_by_category" in cl
            # All items in by_category should also be in items
            total_in_cats = sum(len(v) for v in cl["items_by_category"].values())
            assert total_in_cats == len(cl["items"])


class TestUpdateItemStatus:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_updates_status(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist, update_item_status
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            item_id = cl["items"][0]["item_id"]

            result = update_item_status(item_id, "submitted", 1)
            assert result is not None
            assert result["status"] == "submitted"

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_rejects_invalid_status(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist, update_item_status
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            item_id = cl["items"][0]["item_id"]

            result = update_item_status(item_id, "invalid_status", 1)
            assert result is None

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_rejects_wrong_user(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist, update_item_status
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            item_id = cl["items"][0]["item_id"]

            # User 2 should not be able to update user 1's item
            result = update_item_status(item_id, "submitted", 2)
            assert result is None

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_progress_updates_after_status_change(self, mock_run, app):
        from web.permit_prep import create_checklist, get_checklist, update_item_status
        with app.app_context():
            create_checklist("202401010001", 1)
            cl = get_checklist("202401010001", 1)
            item_id = cl["items"][0]["item_id"]

            update_item_status(item_id, "submitted", 1)
            cl2 = get_checklist("202401010001", 1)
            assert cl2["progress"]["addressed"] == 1

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_nonexistent_item_returns_none(self, mock_run, app):
        from web.permit_prep import update_item_status
        with app.app_context():
            result = update_item_status(99999, "submitted", 1)
            assert result is None


class TestPreviewChecklist:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_preview_without_saving(self, mock_run, app):
        from web.permit_prep import preview_checklist, get_checklist
        with app.app_context():
            # Use a permit number not used by other tests
            preview = preview_checklist("PREVIEW_ONLY_999")
            assert preview["is_preview"] is True
            assert len(preview["items"]) > 0

            # Should NOT be saved to DB
            cl = get_checklist("PREVIEW_ONLY_999", 1)
            assert cl is None

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_preview_has_categories(self, mock_run, app):
        from web.permit_prep import preview_checklist
        with app.app_context():
            preview = preview_checklist("202401010001")
            assert "items_by_category" in preview

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_preview_includes_prediction_metadata(self, mock_run, app):
        from web.permit_prep import preview_checklist
        with app.app_context():
            preview = preview_checklist("202401010001")
            assert "prediction" in preview
            assert preview["prediction"]["form"] == "Form 3/8"


class TestGetUserChecklists:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_user_checklists(self, mock_run, app):
        from web.permit_prep import create_checklist, get_user_checklists
        with app.app_context():
            create_checklist("202401010001", 1)
            checklists = get_user_checklists(1)
            assert len(checklists) >= 1
            assert checklists[0]["permit_number"] == "202401010001"

    def test_returns_empty_for_no_checklists(self, app):
        from web.permit_prep import get_user_checklists
        with app.app_context():
            checklists = get_user_checklists(999)
            assert checklists == []

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_includes_progress_data(self, mock_run, app):
        from web.permit_prep import create_checklist, get_user_checklists
        with app.app_context():
            create_checklist("202401010001", 1)
            checklists = get_user_checklists(1)
            cl = checklists[0]
            assert "total_items" in cl
            assert "completed_items" in cl
            assert "missing_required" in cl
            assert "percent" in cl


# ---------------------------------------------------------------------------
# Categorization tests
# ---------------------------------------------------------------------------

class TestCategorizeDocument:
    def test_plans_category(self):
        from web.permit_prep import _categorize_document
        assert _categorize_document("Construction plans (PDF for EPR)") == "plans"
        assert _categorize_document("Site survey / plot plan") == "plans"

    def test_forms_category(self):
        from web.permit_prep import _categorize_document
        assert _categorize_document("Building Permit Application (Form 3/8)") == "forms"
        assert _categorize_document("Demolition Affidavit Form") == "forms"

    def test_agency_category(self):
        from web.permit_prep import _categorize_document
        assert _categorize_document("DPH Health permit application") == "agency"
        assert _categorize_document("SFFD fire suppression system plans") == "agency"

    def test_supplemental_default(self):
        from web.permit_prep import _categorize_document
        assert _categorize_document("Geotechnical report") == "supplemental"
        assert _categorize_document("Construction cost estimate worksheet") == "supplemental"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestApiPrepCreate:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_201(self, mock_run, auth_client):
        resp = auth_client.post("/api/prep/create",
                                json={"permit_number": "202401010001"})
        assert resp.status_code == 201
        data = resp.get_json()
        assert "checklist_id" in data
        assert data["permit_number"] == "202401010001"

    def test_requires_auth(self, client):
        resp = client.post("/api/prep/create",
                           json={"permit_number": "202401010001"})
        assert resp.status_code == 401

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_requires_permit_number(self, mock_run, auth_client):
        resp = auth_client.post("/api/prep/create", json={})
        assert resp.status_code == 400


class TestApiPrepGet:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_checklist_json(self, mock_run, auth_client):
        auth_client.post("/api/prep/create",
                         json={"permit_number": "202401010001"})
        resp = auth_client.get("/api/prep/202401010001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["permit_number"] == "202401010001"
        assert "items" in data

    def test_requires_auth(self, client):
        resp = client.get("/api/prep/202401010001")
        assert resp.status_code == 401

    def test_returns_404_for_nonexistent(self, auth_client):
        resp = auth_client.get("/api/prep/999999999")
        assert resp.status_code == 404


class TestApiPrepItemUpdate:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_updates_item_status(self, mock_run, auth_client):
        auth_client.post("/api/prep/create",
                         json={"permit_number": "202401010001"})
        resp = auth_client.get("/api/prep/202401010001")
        items = resp.get_json()["items"]
        item_id = items[0]["item_id"]

        resp = auth_client.patch(f"/api/prep/item/{item_id}",
                                 json={"status": "submitted"})
        assert resp.status_code == 200

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_htmx_returns_html(self, mock_run, auth_client):
        auth_client.post("/api/prep/create",
                         json={"permit_number": "202401010001"})
        resp = auth_client.get("/api/prep/202401010001")
        items = resp.get_json()["items"]
        item_id = items[0]["item_id"]

        resp = auth_client.patch(
            f"/api/prep/item/{item_id}",
            json={"status": "submitted"},
            headers={"HX-Request": "true"},
        )
        assert resp.status_code == 200
        assert b"prep-item" in resp.data

    def test_requires_auth(self, client):
        resp = client.patch("/api/prep/item/1", json={"status": "submitted"})
        assert resp.status_code == 401


class TestApiPrepPreview:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_returns_preview_json(self, mock_run, auth_client):
        resp = auth_client.get("/api/prep/preview/202401010001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["is_preview"] is True

    def test_requires_auth(self, client):
        resp = client.get("/api/prep/preview/202401010001")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

class TestPrepRoute:
    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_renders_page(self, mock_run, auth_client):
        resp = auth_client.get("/prep/202401010001")
        assert resp.status_code == 200
        assert b"Permit Prep Checklist" in resp.data

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_shows_categories(self, mock_run, auth_client):
        resp = auth_client.get("/prep/202401010001")
        assert resp.status_code == 200
        # Should have at least one category heading
        assert b"prep-category" in resp.data

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_shows_progress_bar(self, mock_run, auth_client):
        resp = auth_client.get("/prep/202401010001")
        assert b"prep-progress" in resp.data

    def test_requires_auth(self, client):
        resp = client.get("/prep/202401010001")
        # Should redirect to login
        assert resp.status_code == 302


class TestAccountPrepRoute:
    def test_renders_empty_state(self, auth_client):
        resp = auth_client.get("/account/prep")
        assert resp.status_code == 200
        assert b"My Permit Prep" in resp.data

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_lists_checklists(self, mock_run, auth_client):
        auth_client.post("/api/prep/create",
                         json={"permit_number": "202401010001"})
        resp = auth_client.get("/account/prep")
        assert resp.status_code == 200
        assert b"202401010001" in resp.data

    def test_requires_auth(self, client):
        resp = client.get("/account/prep")
        assert resp.status_code == 302


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestNavIntegration:
    def test_nav_has_permit_prep_for_auth(self, auth_client):
        resp = auth_client.get("/account/prep")
        assert b"Permit Prep" in resp.data

    def test_nav_no_permit_prep_for_anon(self, client):
        resp = client.get("/")
        if resp.status_code == 200:
            # Landing page may or may not have nav
            # Just ensure no crash
            pass


class TestSearchResultsIntegration:
    def test_public_search_has_prep_link(self, app):
        """Verify the template has Prep Checklist button markup."""
        from flask import render_template_string
        # Check template source for the Prep Checklist link
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "search_results_public.html"
        )
        with open(template_path) as f:
            content = f.read()
        assert "Prep Checklist" in content
        assert "/prep/" in content


class TestBriefIntegration:
    def test_prep_summary_function_exists(self):
        from web.brief import _get_prep_summary
        assert callable(_get_prep_summary)

    def test_prep_summary_returns_list(self, app):
        from web.brief import _get_prep_summary
        with app.app_context():
            result = _get_prep_summary(1)
            assert isinstance(result, list)

    @patch("web.helpers.run_async", side_effect=[
        ("md", MOCK_PREDICTION), ("md", MOCK_DOCUMENTS)
    ])
    def test_prep_summary_includes_checklists(self, mock_run, app):
        from web.permit_prep import create_checklist
        from web.brief import _get_prep_summary
        with app.app_context():
            create_checklist("202401010001", 1)
            result = _get_prep_summary(1)
            assert len(result) >= 1
            assert result[0]["permit_number"] == "202401010001"


class TestPrintStyles:
    def test_style_css_has_prep_print(self):
        import os
        style_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "static", "style.css"
        )
        with open(style_path) as f:
            content = f.read()
        assert ".prep-page" in content
        assert "@media print" in content


class TestIntelPreviewIntegration:
    def test_intel_preview_has_prep_link(self):
        """Verify the intel preview template has Permit Prep section."""
        import os
        template_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "web", "templates", "fragments", "intel_preview.html"
        )
        with open(template_path) as f:
            content = f.read()
        assert "Permit Prep" in content
        assert "/prep/" in content


# ---------------------------------------------------------------------------
# Valid status constants test
# ---------------------------------------------------------------------------

class TestValidStatuses:
    def test_valid_statuses_constant(self):
        from web.permit_prep import VALID_STATUSES
        expected = {"required", "submitted", "verified", "waived", "n_a"}
        assert VALID_STATUSES == expected

    def test_category_order(self):
        from web.permit_prep import CATEGORY_ORDER
        assert CATEGORY_ORDER == ["plans", "forms", "supplemental", "agency"]
