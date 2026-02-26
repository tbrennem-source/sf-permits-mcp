"""Tests for Sprint 57.5D: background task executor, async email, slow-request logging."""

from __future__ import annotations

import logging
import time
from concurrent.futures import Future
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1-3: web/background.py — submit_task
# ---------------------------------------------------------------------------

class TestSubmitTask:
    """Tests for web.background.submit_task."""

    def test_submit_task_runs_function(self):
        """submit_task executes the given function."""
        from web.background import submit_task

        result_holder = {}

        def _worker(key, value):
            result_holder[key] = value

        future = submit_task(_worker, "hello", "world")
        future.result(timeout=5)  # wait for completion
        assert result_holder == {"hello": "world"}

    def test_submit_task_returns_future(self):
        """submit_task returns a concurrent.futures.Future."""
        from web.background import submit_task

        future = submit_task(lambda: 42)
        assert isinstance(future, Future)
        assert future.result(timeout=5) == 42

    def test_submit_task_handles_exceptions(self):
        """A function that raises does not crash the thread pool."""
        from web.background import submit_task

        def _boom():
            raise ValueError("kaboom")

        future = submit_task(_boom)
        with pytest.raises(ValueError, match="kaboom"):
            future.result(timeout=5)

        # Pool still works after an exception
        future2 = submit_task(lambda: "still alive")
        assert future2.result(timeout=5) == "still alive"


# ---------------------------------------------------------------------------
# 4-6: web/auth.py — send_magic_link async/sync
# ---------------------------------------------------------------------------

class TestSendMagicLink:
    """Tests for send_magic_link with async/sync modes."""

    @patch("web.auth.SMTP_HOST", "smtp.example.com")
    @patch("web.background.submit_task")
    def test_async_default_uses_submit_task(self, mock_submit):
        """Default (sync=False) dispatches to background thread."""
        from web.auth import send_magic_link

        mock_submit.return_value = MagicMock()
        result = send_magic_link("user@example.com", "token123")

        assert result is True
        mock_submit.assert_called_once()
        # First positional arg is the sync helper function
        args = mock_submit.call_args
        assert args[0][0].__name__ == "_send_magic_link_sync"

    @patch("web.auth.SMTP_HOST", "smtp.example.com")
    @patch("web.auth._send_magic_link_sync")
    def test_sync_calls_smtp_directly(self, mock_sync):
        """sync=True calls _send_magic_link_sync directly."""
        from web.auth import send_magic_link

        mock_sync.return_value = True
        result = send_magic_link("user@example.com", "token123", sync=True)

        assert result is True
        mock_sync.assert_called_once()

    @patch("web.auth.SMTP_HOST", "")
    def test_dev_mode_logs_link(self, caplog):
        """When SMTP_HOST is empty, logs the magic link instead of sending."""
        from web.auth import send_magic_link

        with caplog.at_level(logging.INFO, logger="web.auth"):
            result = send_magic_link("dev@example.com", "devtoken")

        assert result is True
        assert "Magic link for dev@example.com" in caplog.text


# ---------------------------------------------------------------------------
# 7-8: web/email_brief.py — send_brief_email sync/async
# ---------------------------------------------------------------------------

class TestSendBriefEmail:
    """Tests for send_brief_email with sync/async modes."""

    @patch("web.email_brief.SMTP_HOST", "smtp.example.com")
    @patch("web.email_brief._send_brief_sync")
    def test_sync_default_calls_smtp(self, mock_sync):
        """Default (sync=True) calls _send_brief_sync directly."""
        from web.email_brief import send_brief_email

        mock_sync.return_value = True
        result = send_brief_email("user@example.com", "<html>Brief</html>")

        assert result is True
        mock_sync.assert_called_once()

    @patch("web.email_brief.SMTP_HOST", "smtp.example.com")
    @patch("web.background.submit_task")
    def test_async_uses_submit_task(self, mock_submit):
        """sync=False dispatches to background thread."""
        from web.email_brief import send_brief_email

        mock_submit.return_value = MagicMock()
        result = send_brief_email("user@example.com", "<html>Brief</html>", sync=False)

        assert result is True
        mock_submit.assert_called_once()
        args = mock_submit.call_args
        assert args[0][0].__name__ == "_send_brief_sync"

    @patch("web.email_brief.SMTP_HOST", "")
    def test_dev_mode_no_smtp(self, caplog):
        """When SMTP_HOST is empty, logs instead of sending."""
        from web.email_brief import send_brief_email

        with caplog.at_level(logging.INFO, logger="web.email_brief"):
            result = send_brief_email("dev@example.com", "<html>Test</html>")

        assert result is True
        assert "SMTP not configured" in caplog.text


# ---------------------------------------------------------------------------
# 9-10: web/email_triage.py — send_triage_email sync/async
# ---------------------------------------------------------------------------

class TestSendTriageEmail:
    """Tests for send_triage_email with sync/async modes."""

    @patch("web.email_triage.SMTP_HOST", "smtp.example.com")
    @patch("web.email_triage._send_triage_sync")
    def test_sync_default_calls_smtp(self, mock_sync):
        """Default (sync=True) calls _send_triage_sync directly."""
        from web.email_triage import send_triage_email

        mock_sync.return_value = True
        result = send_triage_email("admin@example.com", "<html>Triage</html>")

        assert result is True
        mock_sync.assert_called_once()

    @patch("web.email_triage.SMTP_HOST", "smtp.example.com")
    @patch("web.background.submit_task")
    def test_async_uses_submit_task(self, mock_submit):
        """sync=False dispatches to background thread."""
        from web.email_triage import send_triage_email

        mock_submit.return_value = MagicMock()
        result = send_triage_email("admin@example.com", "<html>Triage</html>", sync=False)

        assert result is True
        mock_submit.assert_called_once()
        args = mock_submit.call_args
        assert args[0][0].__name__ == "_send_triage_sync"

    @patch("web.email_triage.SMTP_HOST", "")
    def test_dev_mode_no_smtp(self, caplog):
        """When SMTP_HOST is empty, logs instead of sending."""
        from web.email_triage import send_triage_email

        with caplog.at_level(logging.INFO, logger="web.email_triage"):
            result = send_triage_email("dev@example.com", "<html>Test</html>")

        assert result is True
        assert "SMTP not configured" in caplog.text


# ---------------------------------------------------------------------------
# 11-12: Slow request logging in web/app.py
# ---------------------------------------------------------------------------

class TestSlowRequestLogging:
    """Tests for slow-request logging middleware."""

    @pytest.fixture
    def client(self):
        """Create a Flask test client with a test route."""
        from web.app import app
        app.config["TESTING"] = True
        with app.test_client() as client:
            yield client

    def test_slow_request_logs_warning(self, client, caplog):
        """Requests over 5 seconds produce a warning log."""
        # Mock time.monotonic to simulate a slow request:
        # First call is _start_timer (before_request), second is _slow_request_log (after_request)
        original_monotonic = time.monotonic
        call_count = [0]

        def fake_monotonic():
            call_count[0] += 1
            # Return values that make elapsed = 6.0 seconds
            # _start_timer gets value 100.0, _slow_request_log gets 106.0
            if call_count[0] % 2 == 1:
                return 100.0
            else:
                return 106.0

        with patch("time.monotonic", side_effect=fake_monotonic):
            with caplog.at_level(logging.WARNING, logger="slow_request"):
                client.get("/health")

        assert "SLOW REQUEST" in caplog.text
        assert "6.0s" in caplog.text

    def test_fast_request_no_warning(self, client, caplog):
        """Fast requests do not produce a warning log."""
        with caplog.at_level(logging.WARNING, logger="slow_request"):
            client.get("/health")

        # Real request should be sub-millisecond — no SLOW REQUEST log
        slow_messages = [r for r in caplog.records if "SLOW REQUEST" in r.getMessage()]
        assert len(slow_messages) == 0
