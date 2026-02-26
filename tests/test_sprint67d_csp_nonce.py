"""Tests for Sprint 67-D: CSP Nonce Migration (Report-Only).

Verifies:
- Per-request nonce is generated
- CSP-Report-Only header is present with nonce
- CSP report endpoint accepts violations
- Templates have nonce attributes on script/style tags
- Email templates do NOT have nonces (they're not served via web)
"""

import glob
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "web"))

from app import app, _rate_buckets


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    app.config["TESTING"] = True
    _rate_buckets.clear()
    with app.test_client() as c:
        yield c
    _rate_buckets.clear()


# ---------------------------------------------------------------------------
# 1. Nonce generation
# ---------------------------------------------------------------------------

class TestNonceGeneration:
    """Verify per-request CSP nonce is generated."""

    def test_nonce_in_response_header(self, client):
        """CSP-Report-Only header contains a nonce."""
        rv = client.get("/")
        csp_ro = rv.headers.get("Content-Security-Policy-Report-Only", "")
        assert "nonce-" in csp_ro, (
            f"CSP-Report-Only header missing nonce. Got: {csp_ro}"
        )

    def test_nonce_is_unique_per_request(self, client):
        """Each request gets a different nonce."""
        rv1 = client.get("/")
        rv2 = client.get("/")
        csp1 = rv1.headers.get("Content-Security-Policy-Report-Only", "")
        csp2 = rv2.headers.get("Content-Security-Policy-Report-Only", "")

        # Extract nonce values
        import re
        nonces1 = re.findall(r"nonce-([a-f0-9]+)", csp1)
        nonces2 = re.findall(r"nonce-([a-f0-9]+)", csp2)

        assert nonces1, "No nonce found in first request"
        assert nonces2, "No nonce found in second request"
        assert nonces1[0] != nonces2[0], (
            f"Same nonce used for two different requests: {nonces1[0]}"
        )

    def test_nonce_is_32_hex_chars(self, client):
        """Nonce is a 32-character hex string (16 bytes)."""
        rv = client.get("/")
        csp_ro = rv.headers.get("Content-Security-Policy-Report-Only", "")
        nonces = re.findall(r"nonce-([a-f0-9]+)", csp_ro)
        assert nonces, "No nonce found"
        assert len(nonces[0]) == 32, f"Nonce length is {len(nonces[0])}, expected 32"

    def test_nonce_in_template_context(self, client):
        """Nonce appears in rendered HTML page."""
        rv = client.get("/")
        html = rv.data.decode()
        # The nonce should be in script or style tags
        assert 'nonce="' in html, "No nonce= attribute found in rendered HTML"


# ---------------------------------------------------------------------------
# 2. CSP headers
# ---------------------------------------------------------------------------

class TestCSPHeaders:
    """Verify CSP headers are correctly configured."""

    def test_enforced_csp_still_has_unsafe_inline(self, client):
        """Enforced CSP still uses unsafe-inline (nothing should break)."""
        rv = client.get("/")
        csp = rv.headers.get("Content-Security-Policy", "")
        assert "'unsafe-inline'" in csp, (
            f"Enforced CSP should keep unsafe-inline. Got: {csp}"
        )

    def test_report_only_has_nonce_and_unsafe_inline(self, client):
        """Report-Only CSP has both nonce AND unsafe-inline."""
        rv = client.get("/")
        csp_ro = rv.headers.get("Content-Security-Policy-Report-Only", "")
        assert "'unsafe-inline'" in csp_ro, (
            f"Report-Only CSP should keep unsafe-inline as fallback. Got: {csp_ro}"
        )
        assert "nonce-" in csp_ro, (
            f"Report-Only CSP should have nonce. Got: {csp_ro}"
        )

    def test_report_only_has_report_uri(self, client):
        """Report-Only CSP includes report-uri directive."""
        rv = client.get("/")
        csp_ro = rv.headers.get("Content-Security-Policy-Report-Only", "")
        assert "report-uri /api/csp-report" in csp_ro, (
            f"Report-Only CSP should have report-uri. Got: {csp_ro}"
        )


# ---------------------------------------------------------------------------
# 3. CSP report endpoint
# ---------------------------------------------------------------------------

class TestCSPReportEndpoint:
    """Verify POST /api/csp-report works."""

    def test_csp_report_returns_204(self, client):
        """CSP report endpoint returns 204 No Content."""
        rv = client.post(
            "/api/csp-report",
            data=json.dumps({
                "csp-report": {
                    "document-uri": "https://sfpermits.ai/",
                    "violated-directive": "script-src",
                    "blocked-uri": "inline",
                }
            }),
            content_type="application/json",
        )
        assert rv.status_code == 204

    def test_csp_report_handles_empty_body(self, client):
        """CSP report endpoint handles empty body gracefully."""
        rv = client.post("/api/csp-report", data="", content_type="application/json")
        assert rv.status_code == 204

    def test_csp_report_handles_malformed_json(self, client):
        """CSP report endpoint handles malformed JSON gracefully."""
        rv = client.post(
            "/api/csp-report",
            data="not json",
            content_type="application/csp-report",
        )
        assert rv.status_code == 204

    def test_csp_report_no_auth_required(self, client):
        """CSP report endpoint does not require authentication."""
        rv = client.post(
            "/api/csp-report",
            data=json.dumps({"csp-report": {}}),
            content_type="application/json",
        )
        # Should not redirect to login
        assert rv.status_code == 204


# ---------------------------------------------------------------------------
# 4. Template nonce coverage
# ---------------------------------------------------------------------------

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web", "templates")

EMAIL_TEMPLATES = {
    "analysis_email.html", "brief_email.html", "invite_email.html",
    "notification_digest_email.html", "notification_email.html",
    "plan_analysis_email.html", "report_email.html", "triage_report_email.html",
}


class TestTemplateNonces:
    """Verify all web-served templates have nonce attributes."""

    def test_all_script_tags_have_nonce(self):
        """Every <script> tag in non-email templates has nonce attribute."""
        issues = []
        all_files = (
            glob.glob(os.path.join(TEMPLATE_DIR, "*.html"))
            + glob.glob(os.path.join(TEMPLATE_DIR, "fragments", "*.html"))
        )
        for filepath in sorted(all_files):
            filename = os.path.basename(filepath)
            if filename in EMAIL_TEMPLATES:
                continue
            with open(filepath) as f:
                content = f.read()
            for match in re.finditer(r"<script(\s[^>]*)?>", content):
                if "nonce=" not in match.group(0):
                    issues.append(f"{filename}: {match.group(0)[:50]}")

        assert not issues, (
            f"Script tags without nonce ({len(issues)}):\n"
            + "\n".join(f"  {i}" for i in issues)
        )

    def test_all_style_tags_have_nonce(self):
        """Every <style> tag in non-email templates has nonce attribute."""
        issues = []
        all_files = (
            glob.glob(os.path.join(TEMPLATE_DIR, "*.html"))
            + glob.glob(os.path.join(TEMPLATE_DIR, "fragments", "*.html"))
        )
        for filepath in sorted(all_files):
            filename = os.path.basename(filepath)
            if filename in EMAIL_TEMPLATES:
                continue
            with open(filepath) as f:
                content = f.read()
            for match in re.finditer(r"<style(\s[^>]*)?>", content):
                if "nonce=" not in match.group(0):
                    issues.append(f"{filename}: {match.group(0)[:50]}")

        assert not issues, (
            f"Style tags without nonce ({len(issues)}):\n"
            + "\n".join(f"  {i}" for i in issues)
        )

    def test_email_templates_do_not_have_nonce(self):
        """Email templates should NOT have nonce attributes."""
        for filename in EMAIL_TEMPLATES:
            filepath = os.path.join(TEMPLATE_DIR, filename)
            if not os.path.exists(filepath):
                continue
            with open(filepath) as f:
                content = f.read()
            assert "csp_nonce" not in content, (
                f"Email template {filename} should not have nonce attributes"
            )
