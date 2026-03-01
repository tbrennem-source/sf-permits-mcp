"""Tests for the directory submission package (Agent 3C)."""

import os
import importlib
import pytest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_directory_submission_exists():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    assert os.path.isfile(path), "docs/DIRECTORY_SUBMISSION.md does not exist"


def test_directory_submission_contains_server_url():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "sfpermits-mcp-api-production.up.railway.app/mcp" in content


def test_directory_submission_contains_docs_url():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "sfpermits.ai/docs" in content


def test_directory_submission_contains_privacy_url():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "sfpermits.ai/privacy" in content


def test_directory_submission_contains_terms_url():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "sfpermits.ai/terms" in content


def test_directory_submission_contains_tool_count():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "34" in content


def test_directory_submission_contains_oauth_info():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "OAuth" in content


def test_directory_submission_contains_example_prompts():
    path = os.path.join(REPO_ROOT, "docs", "DIRECTORY_SUBMISSION.md")
    content = open(path).read()
    assert "Example Prompts" in content
    # Should have at least 5 example prompts
    lines_with_quotes = [l for l in content.split("\n") if l.strip().startswith('"') or
                         (l.strip() and l.strip()[0].isdigit() and '"' in l)]
    assert len(lines_with_quotes) >= 3, "Expected at least 3 example prompt lines"


def test_qa_directory_readiness_exists():
    path = os.path.join(REPO_ROOT, "scripts", "qa_directory_readiness.py")
    assert os.path.isfile(path), "scripts/qa_directory_readiness.py does not exist"


def test_qa_directory_readiness_importable():
    """Script should be importable (no syntax errors)."""
    import importlib.util
    path = os.path.join(REPO_ROOT, "scripts", "qa_directory_readiness.py")
    spec = importlib.util.spec_from_file_location("qa_directory_readiness", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # Will raise on syntax errors
    assert hasattr(mod, "run_checks"), "qa_directory_readiness missing run_checks function"
    assert hasattr(mod, "main"), "qa_directory_readiness missing main function"
