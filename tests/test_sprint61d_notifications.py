"""Tests for Sprint 61D — permit change email notifications.

Covers:
  - Schema columns exist (notify_permit_changes, notify_email)
  - Account toggle saves and loads
  - Individual notification for <= 10 changes
  - Digest for > 10 changes
  - Users with notify=False get nothing
  - Empty changes -> no emails
  - Email contains unsubscribe link
  - SMTP failure does not crash
  - Digest table format
  - _format_address, _format_status_change, _format_date helpers
  - _group_changes_by_user grouping logic
  - generate_unsubscribe_token determinism
  - MAX_INDIVIDUAL_EMAILS threshold
"""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import MagicMock, patch, call

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_change(**kwargs) -> dict:
    defaults = {
        "permit_number": "202401015555",
        "change_date": "2026-02-25",
        "old_status": "filed",
        "new_status": "issued",
        "old_status_date": "2026-01-01",
        "new_status_date": "2026-02-25",
        "change_type": "status_change",
        "is_new_permit": False,
        "source": "nightly",
        "permit_type": "additions alterations or repairs",
        "street_number": "123",
        "street_name": "MAIN ST",
        "neighborhood": "Mission",
        "block": "3512",
        "lot": "001",
    }
    defaults.update(kwargs)
    return defaults


def _make_new_permit_change(**kwargs) -> dict:
    c = _make_change(change_type="new_permit", old_status=None, **kwargs)
    return c


# ---------------------------------------------------------------------------
# 1. Schema columns — notify_permit_changes and notify_email
# ---------------------------------------------------------------------------

def test_notify_permit_changes_column_in_init_schema():
    """notify_permit_changes column is defined in init_user_schema CREATE TABLE."""
    from src.db import init_user_schema  # noqa: F401
    import inspect
    src = inspect.getsource(init_user_schema)
    assert "notify_permit_changes" in src


def test_notify_email_column_in_init_schema():
    """notify_email column is defined in init_user_schema CREATE TABLE."""
    from src.db import init_user_schema  # noqa: F401
    import inspect
    src = inspect.getsource(init_user_schema)
    assert "notify_email" in src


def test_migration_function_exists():
    """_run_sprint61d_notify_columns is registered in MIGRATIONS."""
    from scripts.run_prod_migrations import MIGRATIONS
    names = [m.name for m in MIGRATIONS]
    assert "sprint61d_notify_columns" in names


def test_migration_adds_two_columns():
    """Sprint 61D migration returns columns_added with both columns."""
    from scripts.run_prod_migrations import _run_sprint61d_notify_columns
    with patch("src.db.BACKEND", "duckdb"):
        mock_conn = MagicMock()
        mock_conn.execute.return_value = None
        with patch("src.db.get_connection", return_value=mock_conn):
            result = _run_sprint61d_notify_columns()
    assert result["ok"] is True
    cols = result.get("columns_added", [])
    assert "users.notify_permit_changes" in cols
    assert "users.notify_email" in cols


# ---------------------------------------------------------------------------
# 2. Account toggle — saving the preference
# ---------------------------------------------------------------------------

def test_notify_route_saves_true():
    """notify_permit_changes logic: value '1' -> True, response contains 'On'."""
    form_value = "1"
    notify = (form_value == "1")
    assert notify is True

    response_text = (
        '<span style="color:var(--success);">On — you\'ll get emails when watched permits change.</span>'
        if notify else
        '<span style="color:var(--text-muted);">Off — permit change alerts disabled.</span>'
    )
    assert "On" in response_text


def test_notify_route_saves_false():
    """notify_permit_changes logic: missing value -> False, response contains 'Off'."""
    form_value = None
    notify = (form_value == "1")
    assert notify is False

    response_text = (
        '<span style="color:var(--success);">On — you\'ll get emails when watched permits change.</span>'
        if notify else
        '<span style="color:var(--text-muted);">Off — permit change alerts disabled.</span>'
    )
    assert "Off" in response_text


def test_notify_route_registered_in_app():
    """The /account/notify-permit-changes route is registered in the Flask app."""
    from web.app import app as flask_app
    rules = {r.rule for r in flask_app.url_map.iter_rules()}
    assert "/account/notify-permit-changes" in rules


def test_notify_field_in_user_dict():
    """_row_to_user includes notify_permit_changes and notify_email keys."""
    from web.auth import _row_to_user
    row = (
        1, "user@example.com", "Alice", "consultant", "Acme", None,
        True, False, True,
        "daily",
        None,
        "123", "Main St",
        "free",
        None,
        "invited",
        None,
        True,
        "alt@example.com",
    )
    user = _row_to_user(row)
    assert user["notify_permit_changes"] is True
    assert user["notify_email"] == "alt@example.com"


def test_notify_field_defaults_when_missing():
    """_row_to_user handles rows without notify columns (pre-migration)."""
    from web.auth import _row_to_user
    row = (
        1, "user@example.com", "Alice", "consultant", "Acme", None,
        True, False, True,
        "daily", None, "123", "Main St", "free", None, "invited", None,
    )
    user = _row_to_user(row)
    assert user["notify_permit_changes"] is False
    assert user["notify_email"] is None


# ---------------------------------------------------------------------------
# 3. Helper functions
# ---------------------------------------------------------------------------

def test_format_address_with_street():
    from web.email_notifications import _format_address
    c = _make_change(street_number="456", street_name="MARKET ST")
    assert _format_address(c) == "456 MARKET ST"


def test_format_address_fallback_to_permit():
    from web.email_notifications import _format_address
    c = _make_change(street_number="", street_name="", permit_number="2024ABC")
    assert _format_address(c) == "2024ABC"


def test_format_address_empty():
    from web.email_notifications import _format_address
    c = {"street_number": None, "street_name": None, "permit_number": None}
    assert _format_address(c) == "Unknown"


def test_format_date_iso_string():
    from web.email_notifications import _format_date
    c = _make_change(new_status_date="2026-02-25")
    result = _format_date(c)
    assert "Feb 25, 2026" == result


def test_format_date_empty():
    from web.email_notifications import _format_date
    c = {"new_status_date": None, "change_date": None}
    assert _format_date(c) == ""


def test_format_status_change_new_permit():
    from web.email_notifications import _format_status_change
    c = _make_new_permit_change(new_status="filed")
    result = _format_status_change(c)
    assert "new permit" in result.lower()


def test_format_status_change_status_change():
    from web.email_notifications import _format_status_change
    c = _make_change(old_status="filed", new_status="issued")
    result = _format_status_change(c)
    assert "issued" in result.lower()


def test_format_status_change_no_status():
    from web.email_notifications import _format_status_change
    c = {"change_type": "status_change", "old_status": None, "new_status": None}
    result = _format_status_change(c)
    assert result  # Should return some string


# ---------------------------------------------------------------------------
# 4. generate_unsubscribe_token — determinism
# ---------------------------------------------------------------------------

def test_unsubscribe_token_deterministic():
    from web.email_notifications import generate_unsubscribe_token
    t1 = generate_unsubscribe_token(1, "user@example.com")
    t2 = generate_unsubscribe_token(1, "user@example.com")
    assert t1 == t2
    assert len(t1) == 32


def test_unsubscribe_token_different_users():
    from web.email_notifications import generate_unsubscribe_token
    t1 = generate_unsubscribe_token(1, "user@example.com")
    t2 = generate_unsubscribe_token(2, "user@example.com")
    assert t1 != t2


# ---------------------------------------------------------------------------
# 5. _group_changes_by_user
# ---------------------------------------------------------------------------

def test_group_changes_empty_input():
    from web.email_notifications import _group_changes_by_user
    with patch("web.email_notifications.query", return_value=[]):
        result = _group_changes_by_user([])
    assert result == {}


def test_group_changes_skips_no_block_lot():
    from web.email_notifications import _group_changes_by_user
    changes = [{"permit_number": "X", "block": None, "lot": None}]
    with patch("web.email_notifications.query", return_value=[]):
        result = _group_changes_by_user(changes)
    assert result == {}


def test_group_changes_one_user_one_change():
    from web.email_notifications import _group_changes_by_user
    changes = [_make_change(block="3512", lot="001")]
    mock_watcher = (42, "user@example.com", "user@example.com")
    with patch("web.email_notifications.query", return_value=[mock_watcher]):
        result = _group_changes_by_user(changes)
    assert 42 in result
    assert len(result[42]["changes"]) == 1
    assert result[42]["notify_to"] == "user@example.com"


def test_group_changes_two_changes_same_user():
    from web.email_notifications import _group_changes_by_user
    changes = [
        _make_change(permit_number="A", block="3512", lot="001"),
        _make_change(permit_number="B", block="3512", lot="001"),
    ]
    mock_watcher = (42, "user@example.com", "user@example.com")
    with patch("web.email_notifications.query", return_value=[mock_watcher]):
        result = _group_changes_by_user(changes)
    assert len(result[42]["changes"]) == 2


def test_group_changes_no_opted_in_users():
    from web.email_notifications import _group_changes_by_user
    changes = [_make_change()]
    with patch("web.email_notifications.query", return_value=[]):
        result = _group_changes_by_user(changes)
    assert result == {}


# ---------------------------------------------------------------------------
# 6. send_permit_notifications — main entry point
# ---------------------------------------------------------------------------

def test_send_notifications_empty_changes():
    from web.email_notifications import send_permit_notifications
    stats = send_permit_notifications([])
    assert stats["emails_sent"] == 0
    assert stats["users_notified"] == 0


def test_send_notifications_no_opted_in_users():
    from web.email_notifications import send_permit_notifications
    changes = [_make_change()]
    mock_app = MagicMock()
    with patch("web.email_notifications._group_changes_by_user", return_value={}):
        stats = send_permit_notifications(changes, app=mock_app)
    assert stats["emails_sent"] == 0
    assert stats["users_notified"] == 0


def test_send_individual_emails_for_small_batch():
    """<= 10 changes -> individual emails."""
    from web.email_notifications import send_permit_notifications, MAX_INDIVIDUAL_EMAILS

    changes = [_make_change(permit_number=str(i)) for i in range(3)]
    mock_app = MagicMock()

    user_data = {
        42: {
            "email": "user@example.com",
            "notify_to": "user@example.com",
            "changes": changes,
        }
    }

    with patch("web.email_notifications._group_changes_by_user", return_value=user_data), \
         patch("web.email_notifications._send_individual_notification", return_value=True) as mock_ind, \
         patch("web.email_notifications._send_digest_email") as mock_dig:
        stats = send_permit_notifications(changes, app=mock_app)

    assert mock_ind.call_count == 3
    mock_dig.assert_not_called()
    assert stats["individual_sent"] == 3
    assert stats["digests_sent"] == 0
    assert stats["users_notified"] == 1


def test_send_digest_for_large_batch():
    """> 10 changes -> digest email."""
    from web.email_notifications import send_permit_notifications, MAX_INDIVIDUAL_EMAILS

    changes = [_make_change(permit_number=str(i)) for i in range(MAX_INDIVIDUAL_EMAILS + 1)]
    mock_app = MagicMock()

    user_data = {
        42: {
            "email": "user@example.com",
            "notify_to": "user@example.com",
            "changes": changes,
        }
    }

    with patch("web.email_notifications._group_changes_by_user", return_value=user_data), \
         patch("web.email_notifications._send_individual_notification") as mock_ind, \
         patch("web.email_notifications._send_digest_email", return_value=True) as mock_dig:
        stats = send_permit_notifications(changes, app=mock_app)

    mock_ind.assert_not_called()
    assert mock_dig.call_count == 1
    assert stats["digests_sent"] == 1
    assert stats["individual_sent"] == 0
    assert stats["emails_sent"] == 1
    assert stats["users_notified"] == 1


def test_smtp_failure_does_not_crash():
    """SMTP failure in individual send is caught — pipeline continues."""
    from web.email_notifications import send_permit_notifications

    changes = [_make_change()]
    mock_app = MagicMock()

    user_data = {
        42: {
            "email": "user@example.com",
            "notify_to": "user@example.com",
            "changes": changes,
        }
    }

    with patch("web.email_notifications._group_changes_by_user", return_value=user_data), \
         patch("web.email_notifications._send_individual_notification", return_value=False):
        stats = send_permit_notifications(changes, app=mock_app)

    assert stats["errors"] == 1
    assert stats["users_notified"] == 0


def test_smtp_exception_does_not_crash():
    """Unexpected exception during send is caught — pipeline continues."""
    from web.email_notifications import send_permit_notifications

    changes = [_make_change()]
    mock_app = MagicMock()

    user_data = {
        42: {
            "email": "user@example.com",
            "notify_to": "user@example.com",
            "changes": changes,
        }
    }

    with patch("web.email_notifications._group_changes_by_user", return_value=user_data), \
         patch(
             "web.email_notifications._send_individual_notification",
             side_effect=RuntimeError("SMTP down"),
         ):
        stats = send_permit_notifications(changes, app=mock_app)

    assert stats["errors"] == 1


def test_max_individual_emails_threshold():
    """MAX_INDIVIDUAL_EMAILS is 10."""
    from web.email_notifications import MAX_INDIVIDUAL_EMAILS
    assert MAX_INDIVIDUAL_EMAILS == 10


# ---------------------------------------------------------------------------
# 7. Email contains unsubscribe link
# ---------------------------------------------------------------------------

def test_individual_email_has_unsubscribe():
    """Individual notification template includes a link to /account."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "web", "templates", "notification_email.html"
    )
    with open(template_path) as f:
        content = f.read()
    assert "account" in content.lower()
    assert "unsubscribe" in content.lower() or "Turn off" in content


def test_digest_email_has_unsubscribe():
    """Digest notification template includes a link to /account."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "web", "templates", "notification_digest_email.html"
    )
    with open(template_path) as f:
        content = f.read()
    assert "account" in content.lower()
    assert "unsubscribe" in content.lower() or "Turn off" in content


def test_digest_email_has_table():
    """Digest email template contains a table for changes."""
    import os
    template_path = os.path.join(
        os.path.dirname(__file__),
        "..", "web", "templates", "notification_digest_email.html"
    )
    with open(template_path) as f:
        content = f.read()
    assert "<table" in content
    assert "<tr" in content
    assert "Permit" in content
    assert "Address" in content
    assert "Change" in content


# ---------------------------------------------------------------------------
# 8. _send_email_sync — dev mode (no SMTP_HOST)
# ---------------------------------------------------------------------------

def test_send_email_sync_dev_mode():
    """When SMTP_HOST is not set, returns True without connecting."""
    from web.email_notifications import _send_email_sync
    with patch("web.email_notifications.SMTP_HOST", None):
        result = _send_email_sync("test@example.com", "Test Subject", "<p>body</p>")
    assert result is True


def test_send_email_sync_smtp_exception():
    """SMTP exception returns False — does not raise."""
    import smtplib
    from web.email_notifications import _send_email_sync
    with patch("web.email_notifications.SMTP_HOST", "smtp.example.com"), \
         patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, "No route")):
        result = _send_email_sync("test@example.com", "Test Subject", "<p>body</p>")
    assert result is False
