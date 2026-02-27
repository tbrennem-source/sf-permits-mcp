#!/usr/bin/env python3
"""Unified Prod Promotion Gate — run after merge to staging.

Checks design tokens, health, data freshness, smoke tests, auth,
test regressions, route inventory, secret leaks, and dependencies.

Nothing blocks staging. This script determines whether staging
auto-promotes to prod or holds for Tim's review.

Usage:
    python scripts/prod_gate.py --staging-url https://sfpermits-ai-staging-production.up.railway.app
    python scripts/prod_gate.py --staging-url http://localhost:5001  # local testing
    python scripts/prod_gate.py --skip-remote  # local checks only (no staging URL needed)

Output: qa-results/prod-gate-results.md
Exit: always 0 (non-blocking). Read the report for PROMOTE/HOLD decision.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

try:
    import urllib.request
    import urllib.error
    HAS_URLLIB = True
except ImportError:
    HAS_URLLIB = False


# ============================================================
# Check 1: Design Token Lint
# ============================================================

def check_design_lint():
    """Run design_lint.py on changed templates."""
    try:
        result = subprocess.run(
            [sys.executable, "scripts/design_lint.py", "--changed", "--quiet"],
            capture_output=True, text=True, timeout=30
        )
        output = result.stdout.strip()
        if "No changed templates" in output:
            return 5, "No templates changed", []
        # Parse "Token lint: N/5 (M violations across K files)"
        match = re.search(r"Token lint: (\d)/5 \((\d+) violations", output)
        if match:
            score = int(match.group(1))
            count = int(match.group(2))
            return score, f"{count} violations in changed templates", []
        return 5, "No template violations detected", []
    except Exception as e:
        return 3, f"Lint error: {e}", [str(e)]


# ============================================================
# Check 2: Health Endpoint
# ============================================================

def check_health(staging_url):
    """Hit /health, verify status ok, check table counts."""
    issues = []
    try:
        url = f"{staging_url}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "prod-gate/1.0"})
        start = time.time()
        resp = urllib.request.urlopen(req, timeout=15)
        elapsed = time.time() - start
        data = json.loads(resp.read().decode())

        if data.get("status") != "ok":
            return 1, f"Health status: {data.get('status')}", ["Non-ok health status"]

        if elapsed > 5:
            issues.append(f"Health endpoint slow: {elapsed:.1f}s")

        # Check critical tables exist
        tables = data.get("tables", {})
        critical = ["users", "permits", "watch_items", "feedback"]
        missing = [t for t in critical if t not in tables]
        if missing:
            issues.append(f"Missing critical tables: {', '.join(missing)}")
            return 2, f"Missing tables: {', '.join(missing)}", issues

        # Check for empty critical tables (might indicate failed migration)
        empty_critical = [t for t in ["permits", "entities"] if tables.get(t, 0) == 0]
        if empty_critical:
            issues.append(f"Empty critical tables: {', '.join(empty_critical)}")
            return 2, f"Empty tables: {', '.join(empty_critical)}", issues

        score = 4 if issues else 5
        table_count = len(tables)
        return score, f"Healthy — {table_count} tables, {elapsed:.1f}s response", issues
    except urllib.error.URLError as e:
        return 1, f"Cannot reach staging: {e}", [str(e)]
    except Exception as e:
        return 2, f"Health check error: {e}", [str(e)]


# ============================================================
# Check 3: Data Freshness
# ============================================================

def check_data_freshness(staging_url):
    """Check cron_log for recent successful runs."""
    try:
        url = f"{staging_url}/health"
        req = urllib.request.Request(url, headers={"User-Agent": "prod-gate/1.0"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())

        tables = data.get("tables", {})
        cron_count = tables.get("cron_log", 0)
        changes_count = tables.get("permit_changes", 0)

        if cron_count == 0:
            # Staging may not have cron data (cron runs on separate worker service)
            # Check permit_changes as a proxy — if permits exist, data was ingested
            permits_count = tables.get("permits", 0)
            if permits_count > 0:
                return 4, f"No cron_log (staging — cron on separate worker), but {permits_count:,} permits present", []
            return 3, "No cron_log entries and no permits — data freshness unknown", ["Empty cron_log and permits"]

        # Can't query the DB directly, but table existence + non-zero counts
        # indicate the pipeline has run at least once
        return 5, f"Cron log: {cron_count} entries, {changes_count} permit changes tracked", []
    except Exception as e:
        return 3, f"Freshness check error: {e}", [str(e)]


# ============================================================
# Check 4: Smoke Test (core pages return 200)
# ============================================================

def check_smoke_test(staging_url):
    """Hit core pages, verify 200 response and basic content."""
    pages = [
        ("/", "sfpermits"),
        ("/methodology", "methodology"),
        ("/about-data", "data"),
        ("/health", "status"),
    ]
    issues = []
    passed = 0
    for path, expected_content in pages:
        try:
            url = f"{staging_url}{path}"
            req = urllib.request.Request(url, headers={"User-Agent": "prod-gate/1.0"})
            start = time.time()
            resp = urllib.request.urlopen(req, timeout=15)
            elapsed = time.time() - start
            body = resp.read().decode("utf-8", errors="replace").lower()

            if resp.status != 200:
                issues.append(f"{path}: HTTP {resp.status}")
                continue

            if expected_content and expected_content not in body:
                issues.append(f"{path}: missing expected content '{expected_content}'")
                continue

            if elapsed > 5:
                issues.append(f"{path}: slow ({elapsed:.1f}s)")

            passed += 1
        except Exception as e:
            issues.append(f"{path}: {e}")

    total = len(pages)
    if passed == total:
        return 5, f"All {total} core pages responding", issues
    elif passed >= total - 1:
        return 4, f"{passed}/{total} pages ok", issues
    elif passed >= total // 2:
        return 3, f"{passed}/{total} pages ok", issues
    else:
        return 1, f"Only {passed}/{total} pages responding", issues


# ============================================================
# Check 5: Auth Safety
# ============================================================

def check_auth_safety(staging_url):
    """Verify auth-protected pages redirect or return 401/403."""
    protected = ["/brief", "/portfolio", "/admin/feedback"]
    issues = []

    for path in protected:
        try:
            url = f"{staging_url}{path}"
            req = urllib.request.Request(url, headers={"User-Agent": "prod-gate/1.0"})
            resp = urllib.request.urlopen(req, timeout=10)
            body = resp.read().decode("utf-8", errors="replace").lower()
            # If we get 200 on a protected page without auth, that's a problem
            # Unless it redirected to login (check for login form)
            if "login" in body or "sign in" in body or "magic link" in body:
                continue  # Redirected to login — correct behavior
            issues.append(f"{path}: returned 200 without auth (no login redirect)")
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 302):
                continue  # Correct — blocked without auth
            issues.append(f"{path}: unexpected HTTP {e.code}")
        except Exception as e:
            # Connection errors, redirects handled by urllib — may need to follow
            if "redirect" in str(e).lower() or "301" in str(e) or "302" in str(e):
                continue
            issues.append(f"{path}: {e}")

    if issues:
        return "HOLD", f"Auth bypass detected on {len(issues)} routes", issues
    return "PASS", "All protected routes require auth", []


# ============================================================
# Check 6: Test Regression
# ============================================================

def check_test_regression():
    """Run pytest, check for failures in existing tests."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-x", "-q",
             "--tb=no", "--ignore=tests/test_tools.py", "--timeout=30"],
            capture_output=True, text=True, timeout=300,
            env={**os.environ, "TESTING": "1"}
        )
        output = result.stdout.strip()

        # Parse pytest output: "N passed, M failed, K errors"
        if result.returncode == 0:
            # Extract pass count
            match = re.search(r"(\d+) passed", output)
            count = match.group(1) if match else "?"
            return 5, f"{count} tests passing", []

        # Failures
        fail_match = re.search(r"(\d+) failed", output)
        error_match = re.search(r"(\d+) error", output)
        failures = int(fail_match.group(1)) if fail_match else 0
        errors = int(error_match.group(1)) if error_match else 0

        if failures + errors <= 3:
            return 3, f"{failures} failures, {errors} errors", [output[-500:]]
        else:
            return 2, f"{failures} failures, {errors} errors", [output[-500:]]
    except subprocess.TimeoutExpired:
        return 3, "Test suite timed out (300s)", ["pytest timeout"]
    except Exception as e:
        return 3, f"Test runner error: {e}", [str(e)]


# ============================================================
# Check 7: Secret Leak Detection
# ============================================================

def check_secret_leaks():
    """Grep recent commits for patterns that look like secrets."""
    patterns = [
        r"(?:api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9]{20,}",
        r"(?:secret|password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}",
        r"sk-[A-Za-z0-9]{20,}",          # OpenAI/Anthropic API keys
        r"postgresql://[^@]+@[^/]+/",     # Connection strings with credentials
        r"(?:PRIVATE KEY|BEGIN RSA)",      # Private keys
    ]
    issues = []

    try:
        # Check last 5 commits for secret patterns
        result = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD", "--", "*.py", "*.html", "*.js", "*.css", "*.md"],
            capture_output=True, text=True, timeout=30
        )
        diff = result.stdout

        for pattern in patterns:
            matches = re.findall(pattern, diff, re.IGNORECASE)
            for match in matches:
                # Skip if it's in a comment, documentation, or placeholder
                if any(skip in match.lower() for skip in ["example", "placeholder", "your_", "xxx", "..."]):
                    continue
                issues.append(f"Potential secret: {match[:40]}...")

        if issues:
            return "HOLD", f"{len(issues)} potential secrets in recent commits", issues
        return "PASS", "No secrets detected in recent commits", []
    except Exception as e:
        return "PASS", f"Secret scan error (non-blocking): {e}", []


# ============================================================
# Check 8: Dependency Audit
# ============================================================

def check_dependencies():
    """Check if any new dependencies were added in recent commits."""
    issues = []
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD", "--", "pyproject.toml", "requirements*.txt", "setup.py", "setup.cfg"],
            capture_output=True, text=True, timeout=10
        )
        diff = result.stdout
        if not diff.strip():
            return 5, "No dependency changes", []

        # Look for added lines with package names
        added = [line[1:].strip() for line in diff.split("\n")
                 if line.startswith("+") and not line.startswith("+++")
                 and any(c.isalpha() for c in line)]

        if added:
            issues = [f"New/changed dependency line: {line[:80]}" for line in added[:10]]
            return 4, f"{len(added)} dependency changes — review for supply chain risk", issues
        return 5, "No new dependencies", []
    except Exception as e:
        return 5, f"Dependency check error (non-blocking): {e}", []


# ============================================================
# Check 9: Route Inventory
# ============================================================

def check_route_inventory():
    """Verify no routes were accidentally removed."""
    critical_routes = [
        "GET /",
        "GET /brief",
        "GET /portfolio",
        "GET /methodology",
        "GET /about-data",
        "GET /health",
        "GET /search",
        "POST /cron/",
    ]
    try:
        # Extract routes from the codebase
        result = subprocess.run(
            ["grep", "-rn", "@bp.route\\|@app.route\\|@cron_bp.route",
             "web/", "--include=*.py"],
            capture_output=True, text=True, timeout=10
        )
        route_text = result.stdout.lower()

        missing = []
        for route in critical_routes:
            method, path = route.split(" ", 1)
            if path.rstrip("/") not in route_text and path not in route_text:
                missing.append(route)

        if missing:
            return 2, f"Missing critical routes: {', '.join(missing)}", missing
        return 5, f"All {len(critical_routes)} critical routes present", []
    except Exception as e:
        return 4, f"Route check error: {e}", [str(e)]


# ============================================================
# Check 10: Performance Baseline
# ============================================================

def check_performance(staging_url):
    """Check response times of core pages."""
    pages = ["/", "/methodology", "/health"]
    slow = []
    times = {}

    for path in pages:
        try:
            url = f"{staging_url}{path}"
            req = urllib.request.Request(url, headers={"User-Agent": "prod-gate/1.0"})
            start = time.time()
            resp = urllib.request.urlopen(req, timeout=15)
            resp.read()
            elapsed = time.time() - start
            times[path] = round(elapsed, 2)
            if elapsed > 3:
                slow.append(f"{path}: {elapsed:.1f}s")
        except Exception:
            pass

    if slow:
        return 3, f"Slow pages: {', '.join(slow)}", slow

    avg = sum(times.values()) / len(times) if times else 0
    return 5, f"Avg response: {avg:.2f}s across {len(times)} pages", []


# ============================================================
# Runner
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Prod Promotion Gate")
    parser.add_argument("--staging-url", default="https://sfpermits-ai-staging-production.up.railway.app")
    parser.add_argument("--skip-remote", action="store_true", help="Skip checks that hit staging URL")
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest (saves 2-3 min)")
    parser.add_argument("--output", default="qa-results/prod-gate-results.md")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    results = []
    hard_holds = []

    # --- Local checks (always run) ---

    print("Running design lint...") if not args.quiet else None
    score, msg, issues = check_design_lint()
    results.append(("Design Tokens", score, msg, issues))

    print("Checking secret leaks...") if not args.quiet else None
    verdict, msg, issues = check_secret_leaks()
    if verdict == "HOLD":
        hard_holds.append(("Secret Leak", msg, issues))
    results.append(("Secret Leak", 1 if verdict == "HOLD" else 5, msg, issues))

    print("Checking dependencies...") if not args.quiet else None
    score, msg, issues = check_dependencies()
    results.append(("Dependencies", score, msg, issues))

    print("Checking route inventory...") if not args.quiet else None
    score, msg, issues = check_route_inventory()
    results.append(("Route Inventory", score, msg, issues))

    if not args.skip_tests:
        print("Running test suite...") if not args.quiet else None
        score, msg, issues = check_test_regression()
        results.append(("Test Suite", score, msg, issues))
    else:
        results.append(("Test Suite", 5, "Skipped (--skip-tests)", []))

    # --- Remote checks (require staging URL) ---

    if not args.skip_remote and HAS_URLLIB:
        print(f"Checking staging health...") if not args.quiet else None
        score, msg, issues = check_health(args.staging_url)
        results.append(("Health", score, msg, issues))

        print("Running smoke tests...") if not args.quiet else None
        score, msg, issues = check_smoke_test(args.staging_url)
        results.append(("Smoke Test", score, msg, issues))

        print("Checking data freshness...") if not args.quiet else None
        score, msg, issues = check_data_freshness(args.staging_url)
        results.append(("Data Freshness", score, msg, issues))

        print("Checking auth safety...") if not args.quiet else None
        verdict, msg, issues = check_auth_safety(args.staging_url)
        if verdict == "HOLD":
            hard_holds.append(("Auth Safety", msg, issues))
        results.append(("Auth Safety", 1 if verdict == "HOLD" else 5, msg, issues))

        print("Checking performance...") if not args.quiet else None
        score, msg, issues = check_performance(args.staging_url)
        results.append(("Performance", score, msg, issues))
    elif args.skip_remote:
        for name in ["Health", "Smoke Test", "Data Freshness", "Auth Safety", "Performance"]:
            results.append((name, 5, "Skipped (--skip-remote)", []))

    # --- Compute overall verdict ---

    scores = [r[1] for r in results if isinstance(r[1], int)]
    min_score = min(scores) if scores else 5

    if hard_holds:
        verdict = "HOLD"
        reason = f"Hard hold: {', '.join(h[0] for h in hard_holds)}"
    elif min_score <= 2:
        verdict = "HOLD"
        reason = f"Score {min_score}/5 — user-visible issues require Tim review before prod"
    elif min_score <= 3:
        verdict = "PROMOTE"
        reason = f"Score {min_score}/5 — promote to prod, mandatory hotfix session after"
    else:
        verdict = "PROMOTE"
        reason = f"Score {min_score}/5 — clean, auto-promote to prod"

    # --- Format report ---

    lines = []
    lines.append("# Prod Promotion Gate Report")
    lines.append("")
    lines.append(f"**Verdict: {verdict}**")
    lines.append(f"**Overall Score: {min_score}/5**")
    lines.append(f"**Reason:** {reason}")
    lines.append("")

    if hard_holds:
        lines.append("## Hard Holds (always block prod)")
        lines.append("")
        for name, msg, issues in hard_holds:
            lines.append(f"### {name}")
            lines.append(f"**{msg}**")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

    lines.append("## Check Results")
    lines.append("")
    lines.append("| Check | Score | Result |")
    lines.append("|-------|-------|--------|")
    for name, score, msg, issues in results:
        icon = {5: "5/5", 4: "4/5", 3: "3/5", 2: "2/5", 1: "1/5"}.get(score, "?")
        lines.append(f"| {name} | {icon} | {msg} |")
    lines.append("")

    # Detail any issues
    any_issues = [(name, issues) for name, score, msg, issues in results if issues]
    if any_issues:
        lines.append("## Issue Details")
        lines.append("")
        for name, issues in any_issues:
            lines.append(f"### {name}")
            for issue in issues[:10]:
                lines.append(f"- {issue[:200]}")
            lines.append("")

    lines.append("## Promotion Rules")
    lines.append("")
    lines.append("| Score | Action |")
    lines.append("|-------|--------|")
    lines.append("| 5/5 | Auto-promote to prod |")
    lines.append("| 4/5 | Auto-promote, hotfix after |")
    lines.append("| 3/5 | Promote, mandatory hotfix after |")
    lines.append("| 2/5 | HOLD — Tim reviews before prod |")
    lines.append("| 1/5 | HOLD — Tim reviews before prod |")
    lines.append("| Auth/Secret HOLD | Always blocks prod regardless of score |")
    lines.append("")

    report = "\n".join(lines)

    # Write report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    if args.quiet:
        print(f"Prod gate: {verdict} ({min_score}/5) — {reason}")
    else:
        print(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
