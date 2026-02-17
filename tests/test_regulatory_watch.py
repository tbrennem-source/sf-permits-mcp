"""Tests for regulatory watch — CRUD, query helpers, brief + report integration."""

import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_regwatch.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    import src.db as db_mod
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    import web.regulatory_watch as rw_mod
    monkeypatch.setattr(rw_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(rw_mod, "_schema_initialized", False)
    import web.brief as brief_mod
    monkeypatch.setattr(brief_mod, "BACKEND", "duckdb")
    import web.auth as auth_mod
    monkeypatch.setattr(auth_mod, "_schema_initialized", False)
    # Init user schema (creates regulatory_watch table)
    db_mod.init_user_schema()
    # Init main data schema (creates permits table etc.)
    conn = db_mod.get_connection()
    try:
        db_mod.init_schema(conn)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD: create_watch_item
# ---------------------------------------------------------------------------

class TestCreateWatchItem:
    def test_create_basic(self):
        from web.regulatory_watch import create_watch_item, get_watch_item
        wid = create_watch_item(
            title="Test Ordinance",
            source_type="bos_file",
            source_id="File No. 999",
        )
        assert isinstance(wid, int)
        assert wid >= 1

        item = get_watch_item(wid)
        assert item is not None
        assert item["title"] == "Test Ordinance"
        assert item["source_type"] == "bos_file"
        assert item["source_id"] == "File No. 999"
        assert item["status"] == "monitoring"
        assert item["impact_level"] == "moderate"

    def test_create_with_all_fields(self):
        from web.regulatory_watch import create_watch_item, get_watch_item
        wid = create_watch_item(
            title="Permit Expiration Revision",
            source_type="bos_file",
            source_id="File No. 250811",
            description="Amends permit expiration rules",
            status="monitoring",
            impact_level="high",
            affected_sections=["106A.3.4.2.3", "106A.3.7", "106A.4.4"],
            semantic_concepts=["permit_expiration"],
            url="https://example.com/250811.pdf",
            filed_date="2026-01-23",
            effective_date=None,
            notes="Filed by Supervisors Mahmood and Dorsey",
        )
        item = get_watch_item(wid)
        assert item["title"] == "Permit Expiration Revision"
        assert item["impact_level"] == "high"
        assert item["affected_sections_list"] == ["106A.3.4.2.3", "106A.3.7", "106A.4.4"]
        assert item["semantic_concepts_list"] == ["permit_expiration"]
        assert item["filed_date"] == "2026-01-23"
        assert item["notes"] == "Filed by Supervisors Mahmood and Dorsey"

    def test_create_generates_sequential_ids(self):
        from web.regulatory_watch import create_watch_item
        id1 = create_watch_item(title="First", source_type="other", source_id="A")
        id2 = create_watch_item(title="Second", source_type="other", source_id="B")
        assert id2 > id1


# ---------------------------------------------------------------------------
# CRUD: get_watch_item
# ---------------------------------------------------------------------------

class TestGetWatchItem:
    def test_get_nonexistent_returns_none(self):
        from web.regulatory_watch import get_watch_item
        assert get_watch_item(99999) is None

    def test_get_returns_dict(self):
        from web.regulatory_watch import create_watch_item, get_watch_item
        wid = create_watch_item(title="X", source_type="other", source_id="Y")
        item = get_watch_item(wid)
        assert isinstance(item, dict)
        assert "watch_id" in item
        assert "title" in item
        assert "status" in item
        assert "created_at" in item


# ---------------------------------------------------------------------------
# CRUD: list_watch_items
# ---------------------------------------------------------------------------

class TestListWatchItems:
    def test_list_empty(self):
        from web.regulatory_watch import list_watch_items
        items = list_watch_items()
        assert items == []

    def test_list_all(self):
        from web.regulatory_watch import create_watch_item, list_watch_items
        create_watch_item(title="A", source_type="other", source_id="1")
        create_watch_item(title="B", source_type="other", source_id="2")
        items = list_watch_items()
        assert len(items) == 2

    def test_list_with_status_filter(self):
        from web.regulatory_watch import create_watch_item, list_watch_items, update_watch_item
        id1 = create_watch_item(title="Mon", source_type="other", source_id="1")
        id2 = create_watch_item(title="Pass", source_type="other", source_id="2")
        update_watch_item(id2, status="passed")

        monitoring = list_watch_items(status_filter="monitoring")
        assert len(monitoring) == 1
        assert monitoring[0]["title"] == "Mon"

        passed = list_watch_items(status_filter="passed")
        assert len(passed) == 1
        assert passed[0]["title"] == "Pass"

    def test_list_orders_by_impact(self):
        from web.regulatory_watch import create_watch_item, list_watch_items
        create_watch_item(title="Low", source_type="other", source_id="1", impact_level="low")
        create_watch_item(title="High", source_type="other", source_id="2", impact_level="high")
        create_watch_item(title="Mod", source_type="other", source_id="3", impact_level="moderate")
        items = list_watch_items()
        assert items[0]["title"] == "High"
        assert items[1]["title"] == "Mod"
        assert items[2]["title"] == "Low"

    def test_list_invalid_status_filter_returns_all(self):
        from web.regulatory_watch import create_watch_item, list_watch_items
        create_watch_item(title="A", source_type="other", source_id="1")
        items = list_watch_items(status_filter="invalid_status")
        assert len(items) == 1


# ---------------------------------------------------------------------------
# CRUD: update_watch_item
# ---------------------------------------------------------------------------

class TestUpdateWatchItem:
    def test_update_status(self):
        from web.regulatory_watch import create_watch_item, get_watch_item, update_watch_item
        wid = create_watch_item(title="Test", source_type="other", source_id="1")
        result = update_watch_item(wid, status="passed")
        assert result is True

        item = get_watch_item(wid)
        assert item["status"] == "passed"

    def test_update_multiple_fields(self):
        from web.regulatory_watch import create_watch_item, get_watch_item, update_watch_item
        wid = create_watch_item(title="Test", source_type="other", source_id="1")
        update_watch_item(wid, title="Updated Title", impact_level="high", notes="New note")

        item = get_watch_item(wid)
        assert item["title"] == "Updated Title"
        assert item["impact_level"] == "high"
        assert item["notes"] == "New note"

    def test_update_json_fields(self):
        from web.regulatory_watch import create_watch_item, get_watch_item, update_watch_item
        wid = create_watch_item(title="Test", source_type="other", source_id="1")
        update_watch_item(wid, affected_sections=["106A.4.4"], semantic_concepts=["permit_expiration"])

        item = get_watch_item(wid)
        assert item["affected_sections_list"] == ["106A.4.4"]
        assert item["semantic_concepts_list"] == ["permit_expiration"]

    def test_update_no_valid_fields_returns_false(self):
        from web.regulatory_watch import create_watch_item, update_watch_item
        wid = create_watch_item(title="Test", source_type="other", source_id="1")
        result = update_watch_item(wid, nonexistent_field="value")
        assert result is False

    def test_update_preserves_unchanged_fields(self):
        from web.regulatory_watch import create_watch_item, get_watch_item, update_watch_item
        wid = create_watch_item(title="Original", source_type="bos_file", source_id="F1",
                                impact_level="high", notes="Keep this")
        update_watch_item(wid, status="passed")

        item = get_watch_item(wid)
        assert item["title"] == "Original"
        assert item["impact_level"] == "high"
        assert item["notes"] == "Keep this"


# ---------------------------------------------------------------------------
# CRUD: delete_watch_item
# ---------------------------------------------------------------------------

class TestDeleteWatchItem:
    def test_delete(self):
        from web.regulatory_watch import create_watch_item, delete_watch_item, get_watch_item
        wid = create_watch_item(title="Delete Me", source_type="other", source_id="1")
        assert get_watch_item(wid) is not None

        delete_watch_item(wid)
        assert get_watch_item(wid) is None

    def test_delete_nonexistent_returns_true(self):
        from web.regulatory_watch import delete_watch_item
        # Should not raise
        result = delete_watch_item(99999)
        assert result is True


# ---------------------------------------------------------------------------
# Query helpers: get_alerts_for_concepts
# ---------------------------------------------------------------------------

class TestGetAlertsForConcepts:
    def test_matches_overlapping_concepts(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts
        create_watch_item(
            title="Permit Expiration Change",
            source_type="bos_file",
            source_id="F1",
            semantic_concepts=["permit_expiration"],
        )
        create_watch_item(
            title="ADU Reform",
            source_type="bos_file",
            source_id="F2",
            semantic_concepts=["adu_rules"],
        )

        alerts = get_alerts_for_concepts(["permit_expiration"])
        assert len(alerts) == 1
        assert alerts[0]["title"] == "Permit Expiration Change"

    def test_returns_empty_when_no_overlap(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts
        create_watch_item(
            title="ADU Reform",
            source_type="bos_file",
            source_id="F1",
            semantic_concepts=["adu_rules"],
        )
        alerts = get_alerts_for_concepts(["inspections"])
        assert alerts == []

    def test_excludes_effective_and_withdrawn(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts, update_watch_item
        wid = create_watch_item(
            title="Old Law",
            source_type="bos_file",
            source_id="F1",
            semantic_concepts=["permit_expiration"],
        )
        update_watch_item(wid, status="effective")

        alerts = get_alerts_for_concepts(["permit_expiration"])
        assert alerts == []

    def test_includes_monitoring_and_passed(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts, update_watch_item
        id1 = create_watch_item(
            title="Monitoring",
            source_type="bos_file",
            source_id="F1",
            semantic_concepts=["permit_expiration"],
        )
        id2 = create_watch_item(
            title="Passed",
            source_type="bos_file",
            source_id="F2",
            semantic_concepts=["permit_expiration"],
        )
        update_watch_item(id2, status="passed")

        alerts = get_alerts_for_concepts(["permit_expiration"])
        assert len(alerts) == 2

    def test_case_insensitive_matching(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts
        create_watch_item(
            title="Test",
            source_type="other",
            source_id="1",
            semantic_concepts=["Permit_Expiration"],
        )
        alerts = get_alerts_for_concepts(["permit_expiration"])
        assert len(alerts) == 1

    def test_no_concepts_on_item_returns_empty(self):
        from web.regulatory_watch import create_watch_item, get_alerts_for_concepts
        create_watch_item(
            title="No Concepts",
            source_type="other",
            source_id="1",
        )
        alerts = get_alerts_for_concepts(["permit_expiration"])
        assert alerts == []


# ---------------------------------------------------------------------------
# Query helpers: get_approaching_effective
# ---------------------------------------------------------------------------

class TestGetApproachingEffective:
    def test_returns_items_within_window(self):
        from web.regulatory_watch import create_watch_item, get_approaching_effective
        future = (date.today() + timedelta(days=30)).isoformat()
        create_watch_item(
            title="Soon Effective",
            source_type="bos_file",
            source_id="F1",
            effective_date=future,
        )
        items = get_approaching_effective(days_ahead=90)
        assert len(items) == 1
        assert items[0]["title"] == "Soon Effective"

    def test_excludes_items_past_window(self):
        from web.regulatory_watch import create_watch_item, get_approaching_effective
        far_future = (date.today() + timedelta(days=200)).isoformat()
        create_watch_item(
            title="Far Off",
            source_type="bos_file",
            source_id="F1",
            effective_date=far_future,
        )
        items = get_approaching_effective(days_ahead=90)
        assert items == []

    def test_excludes_past_effective_dates(self):
        from web.regulatory_watch import create_watch_item, get_approaching_effective
        past = (date.today() - timedelta(days=10)).isoformat()
        create_watch_item(
            title="Already Effective",
            source_type="bos_file",
            source_id="F1",
            effective_date=past,
        )
        items = get_approaching_effective(days_ahead=90)
        assert items == []

    def test_excludes_null_effective_dates(self):
        from web.regulatory_watch import create_watch_item, get_approaching_effective
        create_watch_item(
            title="No Date",
            source_type="bos_file",
            source_id="F1",
            effective_date=None,
        )
        items = get_approaching_effective(days_ahead=90)
        assert items == []


# ---------------------------------------------------------------------------
# Query helpers: get_regulatory_alerts (brief integration)
# ---------------------------------------------------------------------------

class TestGetRegulatoryAlerts:
    def test_returns_monitoring_items(self):
        from web.regulatory_watch import create_watch_item, get_regulatory_alerts
        create_watch_item(title="Active", source_type="other", source_id="1")
        alerts = get_regulatory_alerts()
        assert len(alerts) == 1

    def test_returns_passed_items(self):
        from web.regulatory_watch import create_watch_item, get_regulatory_alerts, update_watch_item
        wid = create_watch_item(title="Passed", source_type="other", source_id="1")
        update_watch_item(wid, status="passed")
        alerts = get_regulatory_alerts()
        assert len(alerts) == 1

    def test_excludes_effective_items(self):
        from web.regulatory_watch import create_watch_item, get_regulatory_alerts, update_watch_item
        wid = create_watch_item(title="Done", source_type="other", source_id="1")
        update_watch_item(wid, status="effective")
        alerts = get_regulatory_alerts()
        assert alerts == []

    def test_excludes_withdrawn_items(self):
        from web.regulatory_watch import create_watch_item, get_regulatory_alerts, update_watch_item
        wid = create_watch_item(title="Dropped", source_type="other", source_id="1")
        update_watch_item(wid, status="withdrawn")
        alerts = get_regulatory_alerts()
        assert alerts == []


# ---------------------------------------------------------------------------
# Brief integration: morning brief includes regulatory_alerts
# ---------------------------------------------------------------------------

class TestBriefIntegration:
    def _login_and_get_brief(self, client, monkeypatch):
        from app import app
        app.config["TESTING"] = True
        from web.auth import get_or_create_user, create_magic_token
        with app.test_client() as c:
            user = get_or_create_user("regwatch@example.com")
            token = create_magic_token(user["user_id"])
            c.get(f"/auth/verify/{token}", follow_redirects=True)
            return user, c

    def test_brief_returns_regulatory_alerts_key(self, monkeypatch):
        from web.brief import get_morning_brief
        from web.auth import get_or_create_user
        user = get_or_create_user("brief@regwatch.com")
        brief = get_morning_brief(user["user_id"])
        assert "regulatory_alerts" in brief
        assert isinstance(brief["regulatory_alerts"], list)

    def test_brief_summary_includes_regulatory_count(self, monkeypatch):
        from web.brief import get_morning_brief
        from web.auth import get_or_create_user
        from web.regulatory_watch import create_watch_item
        user = get_or_create_user("brief2@regwatch.com")

        create_watch_item(title="Test Alert", source_type="other", source_id="1")

        brief = get_morning_brief(user["user_id"])
        assert brief["summary"]["regulatory_count"] == 1

    def test_brief_regulatory_alerts_match_active_items(self, monkeypatch):
        from web.brief import get_morning_brief
        from web.auth import get_or_create_user
        from web.regulatory_watch import create_watch_item, update_watch_item
        user = get_or_create_user("brief3@regwatch.com")

        id1 = create_watch_item(title="Active One", source_type="other", source_id="1")
        id2 = create_watch_item(title="Withdrawn", source_type="other", source_id="2")
        update_watch_item(id2, status="withdrawn")

        brief = get_morning_brief(user["user_id"])
        assert len(brief["regulatory_alerts"]) == 1
        assert brief["regulatory_alerts"][0]["title"] == "Active One"


# ---------------------------------------------------------------------------
# Report integration: pending_regulation risk type
# ---------------------------------------------------------------------------

class TestReportIntegration:
    def test_pending_regulation_risk_when_concepts_overlap(self):
        from web.report import _compute_risk_assessment
        from web.regulatory_watch import create_watch_item

        create_watch_item(
            title="Permit Expiration Change",
            source_type="bos_file",
            source_id="File No. 250811",
            impact_level="high",
            semantic_concepts=["permit_expiration"],
        )

        permits = [{
            "permit_number": "P200",
            "status": "ISSUED",
            "permit_type_definition": "additions alterations or repairs",
            "estimated_cost": 100000,
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        pending = [r for r in risks if r["risk_type"] == "pending_regulation"]
        assert len(pending) >= 1
        assert "250811" in pending[0]["description"] or "Permit Expiration" in pending[0]["title"]

    def test_no_pending_regulation_when_no_concept_overlap(self):
        from web.report import _compute_risk_assessment
        from web.regulatory_watch import create_watch_item

        create_watch_item(
            title="ADU Reform",
            source_type="bos_file",
            source_id="F99",
            semantic_concepts=["adu_rules"],
        )

        # A demolition permit maps to "demolition" concept, not "adu_rules"
        permits = [{
            "permit_number": "P201",
            "status": "ISSUED",
            "permit_type_definition": "demolitions",
            "estimated_cost": 50000,
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        pending = [r for r in risks if r["risk_type"] == "pending_regulation"]
        assert len(pending) == 0

    def test_no_pending_regulation_when_no_watch_items(self):
        from web.report import _compute_risk_assessment
        permits = [{
            "permit_number": "P202",
            "status": "ISSUED",
            "permit_type_definition": "additions alterations or repairs",
            "estimated_cost": 100000,
        }]
        risks = _compute_risk_assessment(permits=permits, complaints=[], violations=[], property_data=[])
        pending = [r for r in risks if r["risk_type"] == "pending_regulation"]
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# Row deserialization
# ---------------------------------------------------------------------------

class TestRowToDict:
    def test_json_arrays_deserialized(self):
        from web.regulatory_watch import create_watch_item, get_watch_item
        wid = create_watch_item(
            title="Test",
            source_type="other",
            source_id="1",
            affected_sections=["A", "B"],
            semantic_concepts=["C"],
        )
        item = get_watch_item(wid)
        assert item["affected_sections_list"] == ["A", "B"]
        assert item["semantic_concepts_list"] == ["C"]
        # Raw JSON is also available
        assert '"A"' in item["affected_sections"]

    def test_null_json_arrays_become_empty_lists(self):
        from web.regulatory_watch import create_watch_item, get_watch_item
        wid = create_watch_item(title="Test", source_type="other", source_id="1")
        item = get_watch_item(wid)
        assert item["affected_sections_list"] == []
        assert item["semantic_concepts_list"] == []
