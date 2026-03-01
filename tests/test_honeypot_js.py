"""Tests for honeypot.js file existence and landing.html wiring."""
import os
import pytest


HONEYPOT_JS_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'static', 'js', 'honeypot.js'
)
LANDING_HTML_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'web', 'templates', 'landing.html'
)


def test_honeypot_js_exists():
    """honeypot.js file exists."""
    assert os.path.isfile(HONEYPOT_JS_PATH), f"honeypot.js not found at {HONEYPOT_JS_PATH}"


def test_honeypot_js_has_domaincontent_listener():
    """honeypot.js contains DOMContentLoaded listener."""
    with open(HONEYPOT_JS_PATH) as f:
        content = f.read()
    assert 'DOMContentLoaded' in content


def test_honeypot_js_has_track_event():
    """honeypot.js contains trackEvent function."""
    with open(HONEYPOT_JS_PATH) as f:
        content = f.read()
    assert 'trackEvent' in content


def test_honeypot_js_has_scroll_depth():
    """honeypot.js contains scroll depth tracking."""
    with open(HONEYPOT_JS_PATH) as f:
        content = f.read()
    assert 'scroll_depth' in content or 'scrollDepth' in content


def test_landing_html_has_honeypot_script():
    """landing.html includes honeypot.js script tag."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'honeypot.js' in content, "landing.html should include honeypot.js"


def test_landing_html_has_data_honeypot_attribute():
    """landing.html body tag has data-honeypot attribute."""
    with open(LANDING_HTML_PATH) as f:
        content = f.read()
    assert 'data-honeypot' in content, "landing.html body should have data-honeypot attribute"
