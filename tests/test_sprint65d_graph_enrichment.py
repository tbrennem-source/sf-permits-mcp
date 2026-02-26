"""Tests for Sprint 65-D: Entity graph enrichment.

Tests reviewer-entity edges, entity quality scoring, and reviewer
approval rate anomaly detection.
"""

import pytest
import duckdb

import src.db as db_mod
from src.db import init_schema


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _use_duckdb(tmp_path, monkeypatch):
    """Force DuckDB backend with temp database for isolation."""
    db_path = str(tmp_path / "test_65d.duckdb")
    monkeypatch.setenv("SF_PERMITS_DB", db_path)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(db_mod, "BACKEND", "duckdb")
    monkeypatch.setattr(db_mod, "_DUCKDB_PATH", db_path)
    conn = db_mod.get_connection()
    try:
        init_schema(conn)
    finally:
        conn.close()


def _get_conn():
    return db_mod.get_connection()


def _seed_addenda(conn, records):
    """Insert addenda records for testing."""
    for i, r in enumerate(records):
        conn.execute(
            "INSERT INTO addenda (id, primary_key, application_number, addenda_number, "
            "step, station, plan_checked_by, review_results) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [i + 1, f"PK-{i}", r[0], 0, 1, r.get(1, "BLDG") if isinstance(r, dict) else "BLDG",
             r[1] if isinstance(r, (tuple, list)) else r.get("reviewer"),
             r[2] if isinstance(r, (tuple, list)) else r.get("result", "Approved")],
        )


def _seed_entity_with_contacts(conn, entity_id, name, sources, role="architect",
                                 permit_nums=None, from_dates=None):
    """Create an entity with associated contacts."""
    conn.execute(
        "INSERT INTO entities (entity_id, canonical_name, entity_type, "
        "resolution_method, resolution_confidence, contact_count, permit_count, source_datasets) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [entity_id, name, role, "test", "high",
         len(permit_nums or ["P001"]), len(permit_nums or ["P001"]), ",".join(sources)],
    )

    permits = permit_nums or ["P001"]
    dates = from_dates or [None] * len(permits)
    for i, (pnum, fdate) in enumerate(zip(permits, dates)):
        source = sources[i % len(sources)] if sources else "building"
        conn.execute(
            "INSERT INTO contacts (id, source, permit_number, role, name, entity_id, from_date) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [entity_id * 1000 + i, source, pnum, role, name, entity_id, fdate],
        )


# ── Reviewer-entity edge tests ───────────────────────────────────


class TestBuildReviewerEdges:
    def test_basic_reviewer_edges(self):
        from src.graph import build_reviewer_edges
        conn = _get_conn()
        try:
            # Create entity (architect on permit P001)
            _seed_entity_with_contacts(conn, 1, "ALICE ARCHITECT", ["building"],
                                        role="architect", permit_nums=["P001"])
            # Add addenda: reviewer reviewed permit P001
            conn.execute(
                "INSERT INTO addenda (id, primary_key, application_number, plan_checked_by, review_results) "
                "VALUES (1, 'PK1', 'P001', 'BOB REVIEWER', 'Approved')"
            )
        finally:
            conn.close()

        stats = build_reviewer_edges()
        assert stats["reviewer_edges"] >= 1

    def test_no_addenda_returns_zero(self):
        from src.graph import build_reviewer_edges
        stats = build_reviewer_edges()
        assert stats["reviewer_edges"] == 0

    def test_reviewer_with_no_matching_entities(self):
        from src.graph import build_reviewer_edges
        conn = _get_conn()
        try:
            # Add addenda for permit that has no entity contacts
            conn.execute(
                "INSERT INTO addenda (id, primary_key, application_number, plan_checked_by, review_results) "
                "VALUES (1, 'PK1', 'ORPHAN-PERMIT', 'LONELY REVIEWER', 'Approved')"
            )
        finally:
            conn.close()

        stats = build_reviewer_edges()
        assert stats["reviewer_edges"] == 0

    def test_multiple_reviewers_multiple_entities(self):
        from src.graph import build_reviewer_edges
        conn = _get_conn()
        try:
            _seed_entity_with_contacts(conn, 1, "ARCH ONE", ["building"],
                                        role="architect", permit_nums=["P001", "P002"])
            _seed_entity_with_contacts(conn, 2, "ENGINEER ONE", ["building"],
                                        role="engineer", permit_nums=["P001"])

            conn.execute(
                "INSERT INTO addenda (id, primary_key, application_number, plan_checked_by, review_results) "
                "VALUES (1, 'PK1', 'P001', 'REVIEWER A', 'Approved')"
            )
            conn.execute(
                "INSERT INTO addenda (id, primary_key, application_number, plan_checked_by, review_results) "
                "VALUES (2, 'PK2', 'P002', 'REVIEWER B', 'Issued Comments')"
            )
        finally:
            conn.close()

        stats = build_reviewer_edges()
        # REVIEWER A -> ARCH ONE, REVIEWER A -> ENGINEER ONE, REVIEWER B -> ARCH ONE
        assert stats["reviewer_edges"] >= 3

    def test_creates_reviewer_interactions_table(self):
        from src.graph import build_reviewer_edges
        conn = _get_conn()
        try:
            _seed_entity_with_contacts(conn, 1, "ARCH", ["building"],
                                        role="architect", permit_nums=["P001"])
            conn.execute(
                "INSERT INTO addenda (id, primary_key, application_number, plan_checked_by, review_results) "
                "VALUES (1, 'PK1', 'P001', 'REVIEWER', 'Approved')"
            )
        finally:
            conn.close()

        build_reviewer_edges()

        conn = _get_conn()
        try:
            rows = conn.execute("SELECT * FROM reviewer_interactions").fetchall()
            assert len(rows) >= 1
            # Check columns
            row = rows[0]
            assert row[0]  # reviewer_name
            assert row[1]  # entity_id
            assert row[2] >= 1  # interaction_count
        finally:
            conn.close()


# ── Entity quality scoring tests ─────────────────────────────────


class TestComputeEntityQuality:
    def test_basic_quality_score(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            _seed_entity_with_contacts(conn, 1, "TEST ENTITY", ["building"],
                                        role="architect", permit_nums=["P001"])
            result = compute_entity_quality(1, conn)
            assert "score" in result
            assert 0 <= result["score"] <= 100
            assert "components" in result
            assert "details" in result
        finally:
            conn.close()

    def test_entity_not_found(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            result = compute_entity_quality(99999, conn)
            assert result["score"] == 0
            assert "error" in result
        finally:
            conn.close()

    def test_multi_source_higher_score(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            # Entity with 1 source
            _seed_entity_with_contacts(conn, 1, "SINGLE SOURCE", ["building"],
                                        role="architect", permit_nums=["P001"])
            # Entity with 3 sources
            _seed_entity_with_contacts(conn, 2, "MULTI SOURCE", ["building", "electrical", "plumbing"],
                                        role="architect", permit_nums=["P010", "P011", "P012"])

            score1 = compute_entity_quality(1, conn)
            score2 = compute_entity_quality(2, conn)

            assert score2["components"]["source_diversity"] > score1["components"]["source_diversity"]
        finally:
            conn.close()

    def test_consistent_name_higher_score(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            # Entity with perfectly consistent name
            conn.execute(
                "INSERT INTO entities (entity_id, canonical_name, entity_type, "
                "resolution_method, resolution_confidence, contact_count, permit_count, source_datasets) "
                "VALUES (1, 'JOHN SMITH', 'architect', 'test', 'high', 2, 2, 'building')"
            )
            conn.execute(
                "INSERT INTO contacts (id, source, permit_number, role, name, entity_id) "
                "VALUES (1, 'building', 'P001', 'architect', 'JOHN SMITH', 1)"
            )
            conn.execute(
                "INSERT INTO contacts (id, source, permit_number, role, name, entity_id) "
                "VALUES (2, 'building', 'P002', 'architect', 'JOHN SMITH', 1)"
            )

            result = compute_entity_quality(1, conn)
            assert result["components"]["name_consistency"] == 25  # Perfect score
        finally:
            conn.close()

    def test_relationship_count_component(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            _seed_entity_with_contacts(conn, 1, "CONNECTED", ["building"],
                                        role="architect", permit_nums=["P001"])
            _seed_entity_with_contacts(conn, 2, "OTHER", ["building"],
                                        role="engineer", permit_nums=["P001"])

            # Add some relationships
            for i in range(5):
                conn.execute(
                    "INSERT INTO relationships (entity_id_a, entity_id_b, shared_permits) "
                    "VALUES (?, ?, ?)",
                    [1, 10 + i, 1],
                )

            result = compute_entity_quality(1, conn)
            assert result["components"]["relationship_count"] >= 15  # 5 relationships
            assert result["details"]["relationship_count"] == 5
        finally:
            conn.close()

    def test_score_components_sum_to_total(self):
        from src.entities import compute_entity_quality
        conn = _get_conn()
        try:
            _seed_entity_with_contacts(conn, 1, "TEST", ["building", "electrical"],
                                        role="architect", permit_nums=["P001", "P002"])
            result = compute_entity_quality(1, conn)
            components = result["components"]
            expected_total = sum(components.values())
            assert result["score"] == expected_total
        finally:
            conn.close()

    def test_max_score_possible(self):
        """Score can reach up to 100 with ideal data."""
        from src.entities import compute_entity_quality
        from datetime import date, timedelta
        conn = _get_conn()
        try:
            recent_date = str(date.today() - timedelta(days=30))
            conn.execute(
                "INSERT INTO entities (entity_id, canonical_name, entity_type, "
                "resolution_method, resolution_confidence, contact_count, permit_count, source_datasets) "
                "VALUES (1, 'PERFECT ENTITY', 'architect', 'test', 'high', 5, 5, 'building,electrical,plumbing,planning')"
            )
            # Single consistent name
            conn.execute(
                "INSERT INTO contacts (id, source, permit_number, role, name, entity_id, from_date) "
                "VALUES (1, 'building', 'P001', 'architect', 'PERFECT ENTITY', 1, ?)",
                [recent_date],
            )
            # 20+ relationships
            for i in range(25):
                conn.execute(
                    "INSERT INTO relationships (entity_id_a, entity_id_b, shared_permits) "
                    "VALUES (1, ?, 1)", [100 + i],
                )

            result = compute_entity_quality(1, conn)
            assert result["score"] == 100
        finally:
            conn.close()


# ── Reviewer approval rate anomaly tests ─────────────────────────


class TestReviewerApprovalRateAnomalies:
    def test_no_addenda_returns_empty(self):
        """When addenda table is empty, no reviewer anomalies flagged."""
        from src.validate import anomaly_scan
        result = anomaly_scan(min_permits=1)
        assert "reviewer_high_approval_rate" in result["anomalies"]
        assert len(result["anomalies"]["reviewer_high_approval_rate"]) == 0

    def test_normal_reviewers_not_flagged(self):
        """Reviewers with normal approval rates are not flagged."""
        from src.validate import anomaly_scan
        conn = _get_conn()
        try:
            # Add many reviewers with varying approval rates (50-80%)
            id_counter = 1
            for reviewer_idx in range(5):
                reviewer = f"REVIEWER_{reviewer_idx}"
                for i in range(20):
                    result = "Approved" if i < 12 else "Issued Comments"
                    conn.execute(
                        "INSERT INTO addenda (id, primary_key, application_number, "
                        "plan_checked_by, review_results) "
                        "VALUES (?, ?, ?, ?, ?)",
                        [id_counter, f"PK-{id_counter}", f"P-{id_counter}",
                         reviewer, result],
                    )
                    id_counter += 1
        finally:
            conn.close()

        result = anomaly_scan(min_permits=10)
        anomalies = result["anomalies"]["reviewer_high_approval_rate"]
        # With uniform ~60% rate, none should be flagged as anomalous
        assert len(anomalies) == 0

    def test_high_approval_rate_flagged(self):
        """Reviewer with 100% approval rate over 50+ reviews is flagged."""
        from src.validate import anomaly_scan
        conn = _get_conn()
        try:
            id_counter = 1
            # Normal reviewers (60% approval)
            for reviewer_idx in range(5):
                reviewer = f"NORMAL_{reviewer_idx}"
                for i in range(30):
                    result = "Approved" if i < 18 else "Issued Comments"
                    conn.execute(
                        "INSERT INTO addenda (id, primary_key, application_number, "
                        "plan_checked_by, review_results) "
                        "VALUES (?, ?, ?, ?, ?)",
                        [id_counter, f"PK-{id_counter}", f"P-{id_counter}",
                         reviewer, result],
                    )
                    id_counter += 1

            # Suspicious reviewer — 100% approval over 60 reviews
            for i in range(60):
                conn.execute(
                    "INSERT INTO addenda (id, primary_key, application_number, "
                    "plan_checked_by, review_results) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [id_counter, f"PK-{id_counter}", f"P-{id_counter}",
                     "SUSPICIOUS_REVIEWER", "Approved"],
                )
                id_counter += 1
        finally:
            conn.close()

        result = anomaly_scan(min_permits=10)
        anomalies = result["anomalies"]["reviewer_high_approval_rate"]
        suspicious = [a for a in anomalies if a["reviewer"] == "SUSPICIOUS_REVIEWER"]
        assert len(suspicious) == 1
        assert suspicious[0]["approval_rate"] == 100.0

    def test_anomaly_scan_summary_includes_reviewer(self):
        """Summary dict includes the new reviewer category."""
        from src.validate import anomaly_scan
        result = anomaly_scan(min_permits=1)
        assert "reviewer_high_approval_rate" in result["summary"]
