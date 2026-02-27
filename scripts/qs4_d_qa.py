"""QS4-D Security QA checks — run against test client."""
import os
import re
import sys

os.environ["TESTING"] = "1"

from web.app import app

results = []


def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    print(f"  {'✓' if passed else '✗'} {name}: {status}" + (f" — {detail}" if detail else ""))


print("=" * 60)
print("QS4-D Security QA Checks")
print("=" * 60)

# Use app in non-TESTING mode for CSRF checks
app.config["TESTING"] = False
c = app.test_client()

# 1. CSP-Report-Only header present
resp = c.get("/health")
csp_ro = resp.headers.get("Content-Security-Policy-Report-Only", "")
check("1. CSP-Report-Only header present", bool(csp_ro))

# 2. CSP-Report-Only contains nonce
has_nonce = "'nonce-" in csp_ro
check("2. CSP-Report-Only contains nonce", has_nonce)

# 3. External sources allowed
ext_ok = all(s in csp_ro for s in [
    "https://unpkg.com", "https://cdn.jsdelivr.net",
    "https://fonts.googleapis.com", "https://fonts.gstatic.com",
    "https://*.posthog.com"
])
check("3. CSP-Report-Only allows external sources", ext_ok)

# 4. Enforced CSP still has unsafe-inline
csp = resp.headers.get("Content-Security-Policy", "")
check("4. Enforced CSP has unsafe-inline", "'unsafe-inline'" in csp)

# 5. POST without CSRF returns 403
resp2 = c.post("/auth/send-link", data={"email": "test@example.com"})
check("5. POST without CSRF returns 403", resp2.status_code == 403,
      f"got {resp2.status_code}")

# 6. POST with valid CSRF succeeds (not 403)
c2 = app.test_client()
c2.get("/auth/login")
with c2.session_transaction() as sess:
    token = sess.get("csrf_token", "")
resp3 = c2.post("/auth/send-link", data={
    "email": "test@example.com",
    "csrf_token": token,
})
check("6. POST with CSRF token not rejected", resp3.status_code != 403,
      f"got {resp3.status_code}")

# 7. X-CSRFToken header accepted
c3 = app.test_client()
c3.get("/auth/login")
with c3.session_transaction() as sess:
    token3 = sess.get("csrf_token", "")
resp4 = c3.post("/auth/logout", headers={"X-CSRFToken": token3})
check("7. HTMX X-CSRFToken header accepted", resp4.status_code != 403,
      f"got {resp4.status_code}")

# 8. auth_login.html contains csrf_token hidden input
app.config["TESTING"] = True  # switch back for template render
c4 = app.test_client()
resp5 = c4.get("/auth/login")
html = resp5.data.decode()
has_csrf_input = 'name="csrf_token"' in html and 'type="hidden"' in html
check("8. auth_login.html has csrf_token hidden input", has_csrf_input)

# 9. posthog_track callable and no-ops
import web.helpers
orig_key = web.helpers._POSTHOG_KEY
web.helpers._POSTHOG_KEY = None
try:
    web.helpers.posthog_track("test_event", {"foo": "bar"})
    posthog_ok = True
except Exception as e:
    posthog_ok = False
web.helpers._POSTHOG_KEY = orig_key
check("9. posthog_track callable, no-ops without key", posthog_ok)

# 10. Nonces change between requests
c5 = app.test_client()
r1 = c5.get("/health")
r2 = c5.get("/health")
csp1 = r1.headers.get("Content-Security-Policy-Report-Only", "")
csp2 = r2.headers.get("Content-Security-Policy-Report-Only", "")
n1 = re.search(r"'nonce-([^']+)'", csp1)
n2 = re.search(r"'nonce-([^']+)'", csp2)
nonce_different = n1 and n2 and n1.group(1) != n2.group(1)
check("10. Nonces change per request", nonce_different)

print()
print("=" * 60)
passed = sum(1 for _, s, _ in results if s == "PASS")
failed = sum(1 for _, s, _ in results if s == "FAIL")
print(f"Results: {passed} PASS / {failed} FAIL / 0 SKIP")
print("=" * 60)

if failed:
    sys.exit(1)
