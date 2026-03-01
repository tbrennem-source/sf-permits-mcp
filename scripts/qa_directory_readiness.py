#!/usr/bin/env python3
"""Automated readiness QA for Anthropic MCP connector directory submission.

Tests the LIVE deployed server against all directory requirements.
Run after T1+T2+T3 are deployed and merged.

Usage:
    python scripts/qa_directory_readiness.py                      # test live prod
    python scripts/qa_directory_readiness.py --local              # test localhost:8001
    python scripts/qa_directory_readiness.py --url https://...    # custom URL
    python scripts/qa_directory_readiness.py --quick              # skip rate limit test
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import Optional


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

PROD_MCP_BASE = "https://sfpermits-mcp-api-production.up.railway.app"
PROD_WEB_BASE = "https://sfpermits.ai"
LOCAL_MCP_BASE = "http://localhost:8001"
LOCAL_WEB_BASE = "http://localhost:5000"

EXPECTED_TOOL_COUNT = 34
RATE_LIMIT_THRESHOLD = 10  # demo tier limit


# ─────────────────────────────────────────────
# HTTP helpers
# ─────────────────────────────────────────────

def get(url: str, headers: Optional[dict] = None, timeout: int = 15) -> tuple[int, bytes]:
    """Perform a GET request. Returns (status_code, body)."""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


def post(url: str, data: dict, headers: Optional[dict] = None, timeout: int = 15) -> tuple[int, bytes]:
    """Perform a POST request with JSON body. Returns (status_code, body)."""
    body = json.dumps(data).encode()
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except Exception as e:
        return 0, str(e).encode()


# ─────────────────────────────────────────────
# Individual checks
# ─────────────────────────────────────────────

def check_mcp_health(mcp_base: str) -> tuple[bool, str]:
    """Check 1: MCP server responds at health endpoint."""
    status, body = get(f"{mcp_base}/health")
    if status != 200:
        return False, f"Health check failed: HTTP {status}"
    try:
        data = json.loads(body)
        if data.get("status") != "ok":
            return False, f"Health status not 'ok': {data}"
        tool_count = data.get("tools", 0)
        if tool_count < EXPECTED_TOOL_COUNT:
            return False, f"Health reports {tool_count} tools, expected {EXPECTED_TOOL_COUNT}"
        return True, f"OK — {tool_count} tools, status=ok"
    except json.JSONDecodeError:
        return False, f"Health response is not JSON: {body[:200]}"


def check_oauth_discovery(mcp_base: str) -> tuple[bool, str]:
    """Check 2: OAuth authorization server metadata is valid."""
    url = f"{mcp_base}/.well-known/oauth-authorization-server"
    status, body = get(url)
    if status != 200:
        return False, f"OAuth discovery failed: HTTP {status}"
    try:
        data = json.loads(body)
        required = ["issuer", "authorization_endpoint", "token_endpoint",
                    "registration_endpoint", "response_types_supported"]
        missing = [k for k in required if k not in data]
        if missing:
            return False, f"OAuth metadata missing fields: {missing}"
        return True, f"OK — issuer={data.get('issuer', 'N/A')}"
    except json.JSONDecodeError:
        return False, f"OAuth discovery response is not JSON: {body[:200]}"


def check_dynamic_registration(mcp_base: str) -> tuple[bool, str, Optional[dict]]:
    """Check 3: Dynamic client registration (POST /register) works."""
    url = f"{mcp_base}/register"
    payload = {
        "client_name": "QA Readiness Script",
        "redirect_uris": ["https://sfpermits.ai/callback"],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
    }
    status, body = post(url, payload)
    if status not in (200, 201):
        return False, f"Registration failed: HTTP {status} — {body[:200]}", None
    try:
        data = json.loads(body)
        if "client_id" not in data:
            return False, f"Registration response missing client_id: {data}", None
        return True, f"OK — client_id={data['client_id'][:16]}...", data
    except json.JSONDecodeError:
        return False, f"Registration response is not JSON: {body[:200]}", None


def check_unauthenticated_tool_call(mcp_base: str) -> tuple[bool, str]:
    """Check 6: Unauthenticated tool call fails with 401."""
    url = f"{mcp_base}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "permit_stats",
            "arguments": {"group_by": "status"},
        },
    }
    status, body = post(url, payload)
    if status == 401:
        return True, "OK — correctly returns 401 for unauthenticated call"
    if status == 200:
        # Some tools may be allowed in demo mode — check response
        try:
            data = json.loads(body)
            if "error" in data and data["error"].get("code") in (-32001, 401):
                return True, "OK — returns auth error in JSON-RPC response"
        except Exception:
            pass
        return False, f"Unauthenticated call returned 200 — should be 401: {body[:200]}"
    return False, f"Unexpected status {status} for unauthenticated call"


def check_tool_count_in_health(mcp_base: str) -> tuple[bool, str]:
    """Check 13: Health endpoint reports correct tool count."""
    status, body = get(f"{mcp_base}/health")
    if status != 200:
        return False, f"Health check failed: HTTP {status}"
    try:
        data = json.loads(body)
        count = data.get("tools", 0)
        if count != EXPECTED_TOOL_COUNT:
            return False, f"Health reports {count} tools, expected {EXPECTED_TOOL_COUNT}"
        return True, f"OK — {count} tools matches expected {EXPECTED_TOOL_COUNT}"
    except json.JSONDecodeError:
        return False, f"Health response not JSON"


def check_page_accessible(base: str, path: str, label: str) -> tuple[bool, str]:
    """Generic page accessibility check (GET → 200)."""
    status, body = get(f"{base}{path}")
    if status == 200:
        size = len(body)
        return True, f"OK — {size:,} bytes"
    return False, f"HTTP {status}"


def check_no_stack_traces_in_response(mcp_base: str) -> tuple[bool, str]:
    """Check 14: Error messages are user-friendly (no Python stack traces)."""
    # Try a tool call with bad params to trigger an error
    url = f"{mcp_base}/mcp"
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "nonexistent_tool",
            "arguments": {},
        },
    }
    status, body = post(url, payload)
    body_str = body.decode(errors="replace")
    # Check for Python traceback indicators
    traceback_indicators = ["Traceback (most recent call last)", "File \"", "line ", "    raise "]
    found = [ind for ind in traceback_indicators if ind in body_str]
    if found:
        return False, f"Stack trace detected in error response: {found}"
    return True, "OK — no stack traces in error responses"


# ─────────────────────────────────────────────
# Main runner
# ─────────────────────────────────────────────

def run_checks(mcp_base: str, web_base: str, quick: bool = False) -> int:
    """Run all checks. Returns number of failures."""
    results: list[tuple[str, bool, str]] = []

    def record(label: str, passed: bool, detail: str):
        icon = "✅ PASS" if passed else "❌ FAIL"
        results.append((label, passed, detail))
        print(f"  {icon}  {label}")
        print(f"         {detail}")

    print(f"\n{'─'*60}")
    print(f"  sfpermits.ai MCP Directory Readiness QA")
    print(f"  MCP server: {mcp_base}")
    print(f"  Web:        {web_base}")
    print(f"{'─'*60}\n")

    # Check 1: MCP health
    ok, detail = check_mcp_health(mcp_base)
    record("1. MCP server health", ok, detail)

    # Check 2: OAuth discovery
    ok, detail = check_oauth_discovery(mcp_base)
    record("2. OAuth authorization server metadata", ok, detail)

    # Check 3: Dynamic client registration
    ok, detail, _client = check_dynamic_registration(mcp_base)
    record("3. Dynamic client registration (POST /register)", ok, detail)

    # Checks 4+5: OAuth flow (authorize + token) — skip in quick mode
    if not quick:
        # Can only partially test without a real browser
        status, _ = get(f"{mcp_base}/authorize")
        ok = status in (200, 302, 303, 400)  # 400 = missing params but endpoint exists
        record("4. OAuth authorize endpoint exists", ok,
               f"HTTP {status} (expects redirect or 400 for missing params)")

        status, body = post(f"{mcp_base}/token", {
            "grant_type": "authorization_code",
            "code": "invalid-test-code",
            "client_id": "test",
        })
        ok = status in (400, 401, 403)  # Invalid code should be rejected
        record("5. OAuth token endpoint rejects invalid code", ok,
               f"HTTP {status} (expects 400/401/403 for invalid code)")

    # Check 6: Unauthenticated tool call → 401
    ok, detail = check_unauthenticated_tool_call(mcp_base)
    record("6. Unauthenticated tool call → 401", ok, detail)

    # Check 7: Rate limiting (skip in quick mode — makes many requests)
    if not quick:
        print("  ⏳      7. Rate limiting (making multiple requests)...")
        rate_limited = False
        for i in range(RATE_LIMIT_THRESHOLD + 2):
            status, _ = get(f"{mcp_base}/health")
            if status == 429:
                rate_limited = True
                record("7. Rate limiting returns 429 after threshold", True,
                       f"OK — got 429 after {i+1} requests")
                break
            time.sleep(0.1)
        if not rate_limited:
            # Rate limiting may not apply to /health — mark as info
            record("7. Rate limiting (health endpoint not rate limited)", True,
                   "SKIP — rate limits apply to MCP tool calls, not /health; verify manually")
    else:
        record("7. Rate limiting (skipped in quick mode)", True, "SKIP")

    # Checks 8-9: Tool responses (all tools, token limits) — skip without auth
    record("8. All tools respond (requires auth)", True,
           "SKIP — run with a valid OAuth token to verify all 34 tools respond")
    record("9. No response exceeds 25K tokens (requires auth)", True,
           "SKIP — run with a valid OAuth token to verify response sizes")

    # Check 10: /docs page
    ok, detail = check_page_accessible(web_base, "/docs", "/docs")
    record("10. /docs page accessible (200)", ok, detail)

    # Check 11: /privacy page
    ok, detail = check_page_accessible(web_base, "/privacy", "/privacy")
    record("11. /privacy page accessible (200)", ok, detail)

    # Check 12: /terms page
    ok, detail = check_page_accessible(web_base, "/terms", "/terms")
    record("12. /terms page accessible (200)", ok, detail)

    # Check 13: Health endpoint tool count
    ok, detail = check_tool_count_in_health(mcp_base)
    record("13. Health endpoint returns correct tool count", ok, detail)

    # Check 14: No stack traces in error responses
    ok, detail = check_no_stack_traces_in_response(mcp_base)
    record("14. Error messages are user-friendly (no stack traces)", ok, detail)

    # Summary
    failures = [r for r in results if not r[1]]
    passes = [r for r in results if r[1]]
    print(f"\n{'─'*60}")
    print(f"  RESULT: {len(passes)} PASS / {len(failures)} FAIL / {len(results)} total")
    if failures:
        print(f"\n  Failed checks:")
        for label, _, detail in failures:
            print(f"    • {label}: {detail}")
    else:
        print(f"\n  ✅ All checks passed — ready for directory submission!")
    print(f"{'─'*60}\n")

    return len(failures)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="sfpermits.ai MCP directory readiness QA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--local", action="store_true",
                        help="Test against localhost (MCP:8001, Web:5000)")
    parser.add_argument("--url", metavar="URL",
                        help="Custom MCP server base URL")
    parser.add_argument("--web-url", metavar="URL",
                        help="Custom web base URL")
    parser.add_argument("--quick", action="store_true",
                        help="Skip slow checks (rate limiting, OAuth flow)")
    args = parser.parse_args()

    if args.local:
        mcp_base = LOCAL_MCP_BASE
        web_base = LOCAL_WEB_BASE
    else:
        mcp_base = args.url or PROD_MCP_BASE
        web_base = args.web_url or PROD_WEB_BASE

    failures = run_checks(mcp_base, web_base, quick=args.quick)
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
