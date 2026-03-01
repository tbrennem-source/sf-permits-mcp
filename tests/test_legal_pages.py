"""Tests for /privacy and /terms legal pages."""

import pytest

from web.app import app, _rate_buckets


@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


def test_privacy_returns_200(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200


def test_privacy_contains_privacy_in_title(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Privacy" in html


def test_privacy_contains_key_sections(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    html = resp.data.decode()
    for section in ["What We Collect", "What We Don't Do", "Third Parties", "Data Retention"]:
        assert section in html, f"Section '{section}' not found in /privacy"


def test_privacy_no_auth_required(client):
    """Privacy page is public."""
    resp = client.get("/privacy")
    assert resp.status_code == 200


def test_terms_returns_200(client):
    resp = client.get("/terms")
    assert resp.status_code == 200


def test_terms_contains_terms_in_title(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    html = resp.data.decode()
    assert "Terms" in html


def test_terms_contains_key_sections(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    html = resp.data.decode()
    for section in ["Beta Status", "Data Accuracy", "Acceptable Use", "Rate Limits"]:
        assert section in html, f"Section '{section}' not found in /terms"


def test_terms_no_auth_required(client):
    """Terms page is public."""
    resp = client.get("/terms")
    assert resp.status_code == 200


def test_privacy_links_to_terms(client):
    resp = client.get("/privacy")
    assert resp.status_code == 200
    assert b"/terms" in resp.data


def test_terms_links_to_privacy(client):
    resp = client.get("/terms")
    assert resp.status_code == 200
    assert b"/privacy" in resp.data
