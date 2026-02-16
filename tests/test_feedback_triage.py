"""Tests for feedback triage tier classification system."""

from datetime import datetime, timezone, timedelta

import pytest

from scripts.feedback_triage import (
    classify_severity,
    classify_tier,
    detect_duplicates,
    is_already_fixed,
    is_test_submission,
    _message_similarity,
    _within_days,
    ADMIN_EMAILS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    feedback_id=1,
    feedback_type="bug",
    message="Something is broken",
    page_url="https://sfpermits.ai/analyze",
    email="user@test.com",
    has_screenshot=False,
    status="new",
    created_at=None,
    admin_note=None,
    resolved_at=None,
):
    return {
        "feedback_id": feedback_id,
        "feedback_type": feedback_type,
        "message": message,
        "page_url": page_url,
        "email": email,
        "has_screenshot": has_screenshot,
        "status": status,
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "admin_note": admin_note,
        "resolved_at": resolved_at,
    }


# ---------------------------------------------------------------------------
# is_test_submission
# ---------------------------------------------------------------------------

class TestIsTestSubmission:
    def test_test_keyword_short_message(self):
        item = _make_item(message="test")
        assert is_test_submission(item) is True

    def test_test_keyword_in_longer_message(self):
        """Test keyword in a 50+ char message should NOT be flagged."""
        item = _make_item(
            message="I'm testing the new search feature and it keeps returning wrong results for my address"
        )
        assert is_test_submission(item) is False

    def test_asdf_junk(self):
        item = _make_item(message="asdf")
        assert is_test_submission(item) is True

    def test_hello_world(self):
        item = _make_item(message="hello world")
        assert is_test_submission(item) is True

    def test_punctuation_only(self):
        item = _make_item(message="... !!! ???")
        assert is_test_submission(item) is True

    def test_short_admin_message(self):
        """Short message from admin user is flagged as test."""
        ADMIN_EMAILS.add("admin@sfpermits.ai")
        try:
            item = _make_item(message="ok", email="admin@sfpermits.ai")
            assert is_test_submission(item) is True
        finally:
            ADMIN_EMAILS.discard("admin@sfpermits.ai")

    def test_short_non_admin_not_flagged(self):
        """Short message from non-admin with real content is not flagged."""
        item = _make_item(message="Page blank", email="user@test.com")
        assert is_test_submission(item) is False

    def test_real_bug_report(self):
        item = _make_item(message="The search results page shows an error when I enter 123 Main St")
        assert is_test_submission(item) is False

    def test_real_suggestion(self):
        item = _make_item(
            feedback_type="suggestion",
            message="Would be nice to have dark mode on the report page",
        )
        assert is_test_submission(item) is False


# ---------------------------------------------------------------------------
# _message_similarity
# ---------------------------------------------------------------------------

class TestMessageSimilarity:
    def test_identical_messages(self):
        assert _message_similarity("hello world", "hello world") == 1.0

    def test_completely_different(self):
        assert _message_similarity("hello world", "foo bar baz") == 0.0

    def test_partial_overlap(self):
        sim = _message_similarity("search is broken", "search feature is working")
        assert 0.2 < sim < 0.8

    def test_high_similarity(self):
        sim = _message_similarity(
            "the search page shows an error",
            "the search page shows an error message",
        )
        assert sim > 0.7

    def test_empty_strings(self):
        assert _message_similarity("", "") == 0.0
        assert _message_similarity("hello", "") == 0.0


# ---------------------------------------------------------------------------
# _within_days
# ---------------------------------------------------------------------------

class TestWithinDays:
    def test_same_day(self):
        now = datetime.now(timezone.utc)
        assert _within_days(now.isoformat(), now.isoformat(), 7) is True

    def test_within_range(self):
        now = datetime.now(timezone.utc)
        three_days_ago = (now - timedelta(days=3)).isoformat()
        assert _within_days(now.isoformat(), three_days_ago, 7) is True

    def test_outside_range(self):
        now = datetime.now(timezone.utc)
        ten_days_ago = (now - timedelta(days=10)).isoformat()
        assert _within_days(now.isoformat(), ten_days_ago, 7) is False

    def test_none_values(self):
        assert _within_days(None, None, 7) is False
        assert _within_days("2025-01-01T00:00:00+00:00", None, 7) is False

    def test_datetime_objects(self):
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        assert _within_days(now, yesterday, 7) is True


# ---------------------------------------------------------------------------
# detect_duplicates
# ---------------------------------------------------------------------------

class TestDetectDuplicates:
    def test_exact_duplicate(self):
        now = datetime.now(timezone.utc)
        items = [
            _make_item(feedback_id=1, message="Button is broken", created_at=(now - timedelta(hours=2)).isoformat()),
            _make_item(feedback_id=2, message="Button is broken", created_at=now.isoformat()),
        ]
        dupes = detect_duplicates(items)
        assert 2 in dupes
        assert dupes[2] == 1

    def test_similar_same_user_page(self):
        """High-similarity messages from same user/page within 7 days = duplicate."""
        now = datetime.now(timezone.utc)
        items = [
            _make_item(
                feedback_id=1,
                message="The search results are completely wrong for my address",
                email="a@b.com",
                page_url="/analyze",
                created_at=(now - timedelta(days=1)).isoformat(),
            ),
            _make_item(
                feedback_id=2,
                message="The search results are completely wrong for my address query",
                email="a@b.com",
                page_url="/analyze",
                created_at=now.isoformat(),
            ),
        ]
        dupes = detect_duplicates(items)
        assert 2 in dupes

    def test_different_users_not_duplicate(self):
        """Same message from different users is still an exact-match duplicate."""
        now = datetime.now(timezone.utc)
        items = [
            _make_item(feedback_id=1, message="Page is blank", email="a@b.com",
                        created_at=(now - timedelta(hours=1)).isoformat()),
            _make_item(feedback_id=2, message="Page is blank", email="c@d.com",
                        created_at=now.isoformat()),
        ]
        dupes = detect_duplicates(items)
        # Exact match still counts
        assert 2 in dupes

    def test_no_duplicates(self):
        items = [
            _make_item(feedback_id=1, message="Search is broken"),
            _make_item(feedback_id=2, message="Add dark mode please"),
        ]
        dupes = detect_duplicates(items)
        assert len(dupes) == 0

    def test_chain_not_double_counted(self):
        """If A is original and B,C are dupes of A, both should reference A."""
        now = datetime.now(timezone.utc)
        items = [
            _make_item(feedback_id=1, message="test bug", created_at=(now - timedelta(hours=3)).isoformat()),
            _make_item(feedback_id=2, message="test bug", created_at=(now - timedelta(hours=2)).isoformat()),
            _make_item(feedback_id=3, message="test bug", created_at=now.isoformat()),
        ]
        dupes = detect_duplicates(items)
        assert dupes.get(2) == 1
        assert dupes.get(3) == 1


# ---------------------------------------------------------------------------
# is_already_fixed
# ---------------------------------------------------------------------------

class TestIsAlreadyFixed:
    def test_similar_resolved_issue(self):
        item = _make_item(
            message="Search page shows error for my address",
            page_url="/analyze",
            feedback_type="bug",
        )
        resolved = [_make_item(
            feedback_id=99,
            message="Search page shows error for an address",
            page_url="/analyze",
            feedback_type="bug",
            status="resolved",
            admin_note="Fixed and deployed in v2.1",
        )]
        assert is_already_fixed(item, resolved) is True

    def test_different_page_not_fixed(self):
        item = _make_item(message="Error on report page", page_url="/report/123")
        resolved = [_make_item(
            feedback_id=99,
            message="Error on report page",
            page_url="/analyze",
            status="resolved",
            admin_note="Fixed",
        )]
        assert is_already_fixed(item, resolved) is False

    def test_no_fix_note_not_flagged(self):
        """Resolved without a fix-indicating note should not match."""
        item = _make_item(message="Button broken", page_url="/analyze")
        resolved = [_make_item(
            feedback_id=99,
            message="Button broken",
            page_url="/analyze",
            status="resolved",
            admin_note="Won't fix — by design",
        )]
        assert is_already_fixed(item, resolved) is False

    def test_no_page_url_not_flagged(self):
        item = _make_item(message="Something broke", page_url=None)
        resolved = [_make_item(
            feedback_id=99,
            message="Something broke",
            page_url=None,
            admin_note="Fixed",
        )]
        assert is_already_fixed(item, resolved) is False


# ---------------------------------------------------------------------------
# classify_tier
# ---------------------------------------------------------------------------

class TestClassifyTier:
    def test_duplicate_is_tier1(self):
        item = _make_item(feedback_id=5)
        tier, reason = classify_tier(item, {5: 1}, [])
        assert tier == 1
        assert "Duplicate" in reason

    def test_test_submission_is_tier1(self):
        item = _make_item(message="test")
        tier, reason = classify_tier(item, {}, [])
        assert tier == 1
        assert "Test" in reason or "test" in reason.lower()

    def test_already_fixed_is_tier1(self):
        item = _make_item(
            feedback_id=10,
            message="Search page shows error for an address",
            page_url="/analyze",
        )
        resolved = [_make_item(
            feedback_id=5,
            message="Search page shows error for an address query",
            page_url="/analyze",
            admin_note="Fixed and deployed",
        )]
        tier, reason = classify_tier(item, {}, resolved)
        assert tier == 1
        assert "already fixed" in reason.lower()

    def test_bug_with_clear_context_is_tier2(self):
        """Bug with page_url + screenshot + actionable signals = Tier 2."""
        item = _make_item(
            feedback_type="bug",
            message="When I click the search button, the page shows an error message",
            page_url="/analyze",
            has_screenshot=True,
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 2

    def test_detailed_bug_with_page_is_tier2(self):
        """Long bug message with page URL = Tier 2."""
        item = _make_item(
            feedback_type="bug",
            message="I searched for 123 Main Street and the results page loaded but then showed "
                    "a completely blank white screen. I tried refreshing and it happened again. "
                    "This is on Chrome on macOS.",
            page_url="/analyze",
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 2

    def test_scoped_suggestion_is_tier2(self):
        """Suggestion with >50 chars and page URL = Tier 2."""
        item = _make_item(
            feedback_type="suggestion",
            message="It would be helpful to show the permit timeline as a visual chart on the report page",
            page_url="/report/123",
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 2

    def test_vague_bug_is_tier3(self):
        """Short bug with no context = Tier 3."""
        item = _make_item(
            feedback_type="bug",
            message="doesn't work",
            page_url=None,
            has_screenshot=False,
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 3

    def test_question_is_tier3(self):
        """Questions always go to Tier 3."""
        item = _make_item(
            feedback_type="question",
            message="How do I look up a permit by number?",
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 3
        assert "question" in reason.lower()

    def test_short_suggestion_no_page_is_tier3(self):
        """Short suggestion with no page URL = Tier 3."""
        item = _make_item(
            feedback_type="suggestion",
            message="Add dark mode",
            page_url=None,
        )
        tier, reason = classify_tier(item, {}, [])
        assert tier == 3


# ---------------------------------------------------------------------------
# Email triage module
# ---------------------------------------------------------------------------

class TestEmailTriage:
    def test_is_today_with_today(self):
        from web.email_triage import _is_today
        now = datetime.now(timezone.utc)
        assert _is_today(now.isoformat()) is True

    def test_is_today_with_yesterday(self):
        from web.email_triage import _is_today
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1))
        assert _is_today(yesterday.isoformat()) is False

    def test_is_today_with_none(self):
        from web.email_triage import _is_today
        assert _is_today(None) is False

    def test_is_today_with_invalid(self):
        from web.email_triage import _is_today
        assert _is_today("not-a-date") is False

    def test_render_triage_email(self):
        """Triage email renders without errors."""
        import os
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from web.app import app
        from web.email_triage import render_triage_email

        triage_data = {
            "tier1": [
                {"feedback_id": 1, "feedback_type": "bug", "message": "test",
                 "admin_note": "[Auto-triage] Test submission", "tier_reason": "Test submission"},
            ],
            "tier2": [
                {"feedback_id": 2, "feedback_type": "bug",
                 "message": "When I click search the page goes blank",
                 "page_url": "/analyze", "email": "user@test.com",
                 "has_screenshot": True, "tier_reason": "Bug with clear reproduction context"},
            ],
            "tier3": [
                {"feedback_id": 3, "feedback_type": "question",
                 "message": "How does permit tracking work?",
                 "page_url": None, "email": None,
                 "has_screenshot": False, "tier_reason": "Question requiring human answer"},
            ],
            "counts": {"new": 2, "reviewed": 1, "resolved": 5, "total": 8},
            "auto_resolved": 1,
            "total_triaged": 3,
        }

        with app.app_context():
            html = render_triage_email(triage_data)
            assert "Triage Report" in html
            assert "Auto-Resolved" in html
            assert "Actionable" in html
            assert "Needs Your Input" in html
            assert "#1" in html
            assert "#2" in html
            assert "#3" in html
            assert "View Feedback Queue" in html

    def test_render_triage_email_empty_tiers(self):
        """Triage email renders cleanly with empty tiers."""
        from web.app import app
        from web.email_triage import render_triage_email

        triage_data = {
            "tier1": [],
            "tier2": [],
            "tier3": [],
            "counts": {"new": 0, "resolved": 0, "total": 0},
            "auto_resolved": 0,
            "total_triaged": 0,
        }

        with app.app_context():
            html = render_triage_email(triage_data)
            assert "Triage Report" in html
            assert "View Feedback Queue" in html
            # Empty tiers should not show section headers
            assert "Auto-Resolved" not in html
