"""
Tests for Sprint 74-3: Security Audit Tooling
Covers scripts/security_audit.py, .bandit config, and .github/workflows/security.yml
"""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent


# ---------------------------------------------------------------------------
# Task 74-3-1: scripts/security_audit.py
# ---------------------------------------------------------------------------


class TestSecurityAuditImport:
    """The script must be importable without side effects."""

    def test_module_imports(self):
        """security_audit.py imports without error."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "security_audit",
            PROJECT_ROOT / "scripts" / "security_audit.py",
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert hasattr(mod, "main")
        assert hasattr(mod, "run_bandit")
        assert hasattr(mod, "run_pip_audit")
        assert hasattr(mod, "build_report")

    def test_script_file_exists(self):
        """scripts/security_audit.py exists."""
        assert (PROJECT_ROOT / "scripts" / "security_audit.py").exists()


class TestRunCommand:
    """run_command returns (returncode, stdout, stderr) tuples."""

    def test_successful_command(self):
        from scripts.security_audit import run_command

        rc, stdout, stderr = run_command([sys.executable, "-c", "print('hello')"])
        assert rc == 0
        assert "hello" in stdout

    def test_missing_tool_returns_minus_one(self):
        from scripts.security_audit import run_command

        rc, stdout, stderr = run_command(["__nonexistent_tool_xyz__"])
        assert rc == -1
        assert "not found" in stderr.lower() or "__nonexistent_tool_xyz__" in stderr


class TestRunBanditMocked:
    """run_bandit parses JSON output and counts issues by severity."""

    def _make_bandit_json(self, issues: list) -> str:
        return json.dumps({"results": issues, "metrics": {}})

    def test_bandit_high_count(self):
        from scripts.security_audit import run_bandit

        bandit_output = self._make_bandit_json([
            {
                "issue_severity": "HIGH",
                "issue_confidence": "HIGH",
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
                "filename": "src/foo.py",
                "line_number": 10,
                "issue_text": "subprocess call with shell=True",
                "code": "subprocess.Popen(cmd, shell=True)",
            },
            {
                "issue_severity": "MEDIUM",
                "issue_confidence": "MEDIUM",
                "test_id": "B501",
                "test_name": "weak_tls",
                "filename": "src/bar.py",
                "line_number": 20,
                "issue_text": "TLSv1 usage",
                "code": "ssl.TLSv1",
            },
        ])

        with patch("scripts.security_audit.check_tool_available", return_value=True), \
             patch("scripts.security_audit.run_command", return_value=(1, bandit_output, "")):
            result = run_bandit(PROJECT_ROOT)

        assert result["available"] is True
        assert result["high_count"] == 1
        assert result["medium_count"] == 1
        assert result["low_count"] == 0
        assert len(result["issues"]) == 2

    def test_bandit_no_issues(self):
        from scripts.security_audit import run_bandit

        bandit_output = self._make_bandit_json([])

        with patch("scripts.security_audit.check_tool_available", return_value=True), \
             patch("scripts.security_audit.run_command", return_value=(0, bandit_output, "")):
            result = run_bandit(PROJECT_ROOT)

        assert result["high_count"] == 0
        assert result["issues"] == []

    def test_bandit_not_installed(self):
        from scripts.security_audit import run_bandit

        with patch("scripts.security_audit.check_tool_available", return_value=False):
            result = run_bandit(PROJECT_ROOT)

        assert result["available"] is False
        assert result["error"] is not None
        assert "not installed" in result["error"].lower()

    def test_bandit_invalid_json_sets_error(self):
        from scripts.security_audit import run_bandit

        with patch("scripts.security_audit.check_tool_available", return_value=True), \
             patch("scripts.security_audit.run_command", return_value=(1, "not-json", "")):
            result = run_bandit(PROJECT_ROOT)

        assert result["error"] is not None
        assert "parse" in result["error"].lower() or "json" in result["error"].lower()


class TestRunPipAuditMocked:
    """run_pip_audit parses JSON output and counts vulnerabilities."""

    def _make_pip_audit_json(self, deps: list) -> str:
        return json.dumps(deps)

    def test_pip_audit_with_vuln(self):
        from scripts.security_audit import run_pip_audit

        pip_output = self._make_pip_audit_json([
            {
                "name": "requests",
                "version": "2.25.0",
                "vulns": [
                    {
                        "id": "PYSEC-2023-1",
                        "aliases": ["CVE-2023-12345"],
                        "description": "Remote code execution vulnerability in requests.",
                        "fix_versions": ["2.31.0"],
                    }
                ],
            }
        ])

        with patch("scripts.security_audit.check_tool_available", return_value=True), \
             patch("scripts.security_audit.run_command", return_value=(1, pip_output, "")):
            result = run_pip_audit(PROJECT_ROOT)

        assert result["available"] is True
        assert len(result["vulnerabilities"]) == 1
        assert result["vulnerabilities"][0]["package"] == "requests"
        # RCE in description triggers HIGH
        assert result["vulnerabilities"][0]["severity"] == "HIGH"
        assert result["high_count"] == 1

    def test_pip_audit_no_vulns(self):
        from scripts.security_audit import run_pip_audit

        pip_output = self._make_pip_audit_json([
            {"name": "flask", "version": "3.1.0", "vulns": []}
        ])

        with patch("scripts.security_audit.check_tool_available", return_value=True), \
             patch("scripts.security_audit.run_command", return_value=(0, pip_output, "")):
            result = run_pip_audit(PROJECT_ROOT)

        assert result["vulnerabilities"] == []
        assert result["high_count"] == 0

    def test_pip_audit_not_installed(self):
        from scripts.security_audit import run_pip_audit

        with patch("scripts.security_audit.check_tool_available", return_value=False):
            result = run_pip_audit(PROJECT_ROOT)

        assert result["available"] is False
        assert "not installed" in result["error"].lower()


class TestBuildReport:
    """build_report produces a well-formed markdown string."""

    def _empty_bandit(self):
        return {
            "available": True,
            "issues": [],
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
            "raw": "",
            "error": None,
        }

    def _empty_pip(self):
        return {
            "available": True,
            "vulnerabilities": [],
            "high_count": 0,
            "raw": "",
            "error": None,
        }

    def test_report_is_string(self):
        from scripts.security_audit import build_report

        report = build_report(self._empty_bandit(), self._empty_pip(), PROJECT_ROOT)
        assert isinstance(report, str)
        assert len(report) > 100

    def test_report_contains_pass_status(self):
        from scripts.security_audit import build_report

        report = build_report(self._empty_bandit(), self._empty_pip(), PROJECT_ROOT)
        assert "PASS" in report

    def test_report_contains_fail_status_on_high_issue(self):
        from scripts.security_audit import build_report

        bandit = self._empty_bandit()
        bandit["high_count"] = 1
        bandit["issues"] = [{
            "severity": "HIGH",
            "confidence": "HIGH",
            "test_id": "B602",
            "test_name": "subprocess_shell",
            "filename": "src/foo.py",
            "line_number": 1,
            "issue_text": "shell=True",
            "code": "",
        }]

        report = build_report(bandit, self._empty_pip(), PROJECT_ROOT)
        assert "FAIL" in report
        assert "HIGH" in report

    def test_report_skipped_tools_noted(self):
        from scripts.security_audit import build_report

        bandit = self._empty_bandit()
        bandit["available"] = False
        bandit["error"] = "bandit not installed"

        pip = self._empty_pip()
        pip["available"] = False
        pip["error"] = "pip-audit not installed"

        report = build_report(bandit, pip, PROJECT_ROOT)
        assert "SKIPPED" in report

    def test_report_has_expected_sections(self):
        from scripts.security_audit import build_report

        report = build_report(self._empty_bandit(), self._empty_pip(), PROJECT_ROOT)
        assert "# Security Audit Report" in report
        assert "## Summary" in report
        assert "## Bandit" in report
        assert "## pip-audit" in report


class TestMainExitCode:
    """main() returns 0 when no HIGH issues, 1 when HIGH issues exist."""

    def test_main_returns_0_on_clean_run(self):
        from scripts.security_audit import main

        clean_bandit = {
            "available": True, "issues": [], "high_count": 0,
            "medium_count": 0, "low_count": 0, "raw": "", "error": None,
        }
        clean_pip = {
            "available": True, "vulnerabilities": [], "high_count": 0,
            "raw": "", "error": None,
        }

        with patch("scripts.security_audit.run_bandit", return_value=clean_bandit), \
             patch("scripts.security_audit.run_pip_audit", return_value=clean_pip):
            rc = main()

        assert rc == 0

    def test_main_returns_1_on_high_issue(self):
        from scripts.security_audit import main

        high_bandit = {
            "available": True,
            "issues": [{"severity": "HIGH", "confidence": "HIGH", "test_id": "B602",
                        "test_name": "shell", "filename": "f.py", "line_number": 1,
                        "issue_text": "shell=True", "code": ""}],
            "high_count": 1,
            "medium_count": 0,
            "low_count": 0,
            "raw": "",
            "error": None,
        }
        clean_pip = {
            "available": True, "vulnerabilities": [], "high_count": 0,
            "raw": "", "error": None,
        }

        with patch("scripts.security_audit.run_bandit", return_value=high_bandit), \
             patch("scripts.security_audit.run_pip_audit", return_value=clean_pip):
            rc = main()

        assert rc == 1


# ---------------------------------------------------------------------------
# Task 74-3-2: .bandit config
# ---------------------------------------------------------------------------


class TestBanditConfig:
    """Validate .bandit configuration file."""

    def test_bandit_config_exists(self):
        """`.bandit` config file exists at project root."""
        assert (PROJECT_ROOT / ".bandit").exists()

    def test_bandit_config_has_skips(self):
        """`.bandit` skips B101 (assert_used)."""
        content = (PROJECT_ROOT / ".bandit").read_text()
        assert "B101" in content

    def test_bandit_config_excludes_tests(self):
        """`.bandit` excludes the tests directory."""
        content = (PROJECT_ROOT / ".bandit").read_text()
        assert "tests" in content

    def test_bandit_config_has_bandit_section(self):
        """`.bandit` has a [bandit] section header."""
        content = (PROJECT_ROOT / ".bandit").read_text()
        assert "[bandit]" in content


# ---------------------------------------------------------------------------
# Task 74-3-3: .github/workflows/security.yml
# ---------------------------------------------------------------------------


class TestSecurityWorkflow:
    """Validate .github/workflows/security.yml is valid YAML and well-structured."""

    @pytest.fixture
    def workflow(self):
        path = PROJECT_ROOT / ".github" / "workflows" / "security.yml"
        assert path.exists(), f"security.yml not found at {path}"
        return yaml.safe_load(path.read_text())

    @pytest.fixture
    def workflow_raw_text(self):
        path = PROJECT_ROOT / ".github" / "workflows" / "security.yml"
        return path.read_text()

    def test_workflow_file_exists(self):
        """security.yml exists in .github/workflows/."""
        assert (PROJECT_ROOT / ".github" / "workflows" / "security.yml").exists()

    def test_workflow_valid_yaml(self, workflow):
        """security.yml parses as valid YAML."""
        assert workflow is not None
        assert isinstance(workflow, dict)

    def test_workflow_has_weekly_cron(self, workflow_raw_text):
        """Workflow has a weekly schedule trigger (Sunday 6am UTC).

        Note: PyYAML parses `on` as boolean True — check raw text instead.
        """
        assert "0 6 * * 0" in workflow_raw_text, (
            "Expected cron '0 6 * * 0' (Sunday 6am UTC) in security.yml"
        )

    def test_workflow_has_push_trigger(self, workflow_raw_text):
        """Workflow triggers on push to main.

        Note: PyYAML parses `on` as boolean True — check raw text instead.
        """
        assert "push:" in workflow_raw_text
        assert "main" in workflow_raw_text

    def test_workflow_has_continue_on_error(self, workflow):
        """Workflow uses continue-on-error on the audit step."""
        jobs = workflow.get("jobs", {})
        for job in jobs.values():
            steps = job.get("steps", [])
            for step in steps:
                if step.get("continue-on-error"):
                    return  # Found it
        pytest.fail("No step with continue-on-error: true found in security.yml")

    def test_workflow_uploads_artifact(self, workflow):
        """Workflow uploads the security report as an artifact."""
        jobs = workflow.get("jobs", {})
        for job in jobs.values():
            steps = job.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "upload-artifact" in uses:
                    return  # Found it
        pytest.fail("No upload-artifact step found in security.yml")

    def test_workflow_installs_bandit_and_pip_audit(self, workflow):
        """Workflow installs both bandit and pip-audit."""
        jobs = workflow.get("jobs", {})
        full_text = str(workflow)
        assert "bandit" in full_text, "bandit not mentioned in workflow"
        assert "pip-audit" in full_text, "pip-audit not mentioned in workflow"
