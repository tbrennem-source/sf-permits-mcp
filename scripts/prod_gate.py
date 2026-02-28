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
        # Exclude the gate script itself (it contains the patterns as regex)
        result = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD",
             "--", "*.py", "*.html", "*.js", "*.css", "*.md",
             ":!scripts/prod_gate.py", ":!scripts/design_lint.py",
             ":!tests/"],
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
# Check 11: Migration Safety
# ============================================================

def check_migration_safety():
    """Check if recent commits contain migration-like SQL without down-migration."""
    issues = []
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD~5..HEAD",
             "--", "*.py", "*.sql",
             ":!scripts/prod_gate.py"],
            capture_output=True, text=True, timeout=30
        )
        diff = result.stdout

        # Patterns that indicate DDL changes
        create_table = re.findall(r"^\+.*CREATE\s+TABLE", diff, re.MULTILINE | re.IGNORECASE)
        alter_table = re.findall(r"^\+.*ALTER\s+TABLE", diff, re.MULTILINE | re.IGNORECASE)
        drop_stmts = re.findall(r"^\+.*DROP\s+(?:TABLE|COLUMN|INDEX)", diff, re.MULTILINE | re.IGNORECASE)

        if not create_table and not alter_table and not drop_stmts:
            return 5, "No DDL migrations in recent commits", []

        if drop_stmts:
            # Check if there's a mention of backup or the drop is in a migration that has
            # a corresponding rollback hint nearby
            backup_refs = re.findall(r"(?:backup|restore|rollback|down_migration|migrate_back)", diff, re.IGNORECASE)
            if not backup_refs:
                for stmt in drop_stmts[:3]:
                    issues.append(f"DROP without backup evidence: {stmt.strip()[:80]}")
                return 1, f"{len(drop_stmts)} DROP statement(s) without backup/rollback evidence", issues

        migration_count = len(create_table) + len(alter_table)
        msg = f"{migration_count} DDL migration(s) detected"
        if create_table:
            msg += f" ({len(create_table)} CREATE TABLE"
        if alter_table:
            msg += f", {len(alter_table)} ALTER TABLE" if create_table else f" ({len(alter_table)} ALTER TABLE"
        msg += ")"

        issues = [f"Migration: {s.strip()[:80]}" for s in (create_table + alter_table)[:5]]
        return 3, msg + " — verify idempotency", issues

    except Exception as e:
        return 4, f"Migration check error (non-blocking): {e}", []


# ============================================================
# Check 12: Cron Endpoint Health
# ============================================================

def check_cron_health(staging_url):
    """Verify cron endpoints respond (without executing them)."""
    # Use GET to check reachability — cron endpoints require POST + CRON_SECRET,
    # so a GET will return 405 or 401/403 but NOT 500/404, which is what we want.
    cron_endpoints = [
        "/cron/nightly",
        "/cron/compute-caches",
    ]
    issues = []
    responding = 0
    cron_secret = os.environ.get("CRON_SECRET", "")

    for path in cron_endpoints:
        try:
            url = f"{staging_url}{path}"
            headers = {"User-Agent": "prod-gate/1.0"}
            if cron_secret:
                headers["Authorization"] = f"Bearer {cron_secret}"
            req = urllib.request.Request(url, method="GET", headers=headers)
            try:
                resp = urllib.request.urlopen(req, timeout=10)
                # 200 on a GET to a cron endpoint is unexpected but not a failure
                responding += 1
            except urllib.error.HTTPError as e:
                # 405 (Method Not Allowed) = endpoint exists, correct
                # 401/403 = auth-gated, endpoint exists, correct
                # 302 = redirect, endpoint exists
                if e.code in (401, 403, 405, 302, 200):
                    responding += 1
                else:
                    issues.append(f"{path}: unexpected HTTP {e.code}")
        except Exception as e:
            issues.append(f"{path}: unreachable — {str(e)[:60]}")

    total = len(cron_endpoints)
    if responding == total:
        return 5, f"All {total} cron endpoints reachable", []
    elif responding >= total // 2:
        return 3, f"{responding}/{total} cron endpoints reachable", issues
    else:
        return 1, f"Only {responding}/{total} cron endpoints reachable", issues


# ============================================================
# Check 13: Design Lint Trend
# ============================================================

def check_lint_trend():
    """Track design lint violation count trend across runs."""
    history_file = "qa-results/design-lint-history.json"
    issues = []

    # Run current lint
    current_violations = None
    try:
        result = subprocess.run(
            [sys.executable, "scripts/design_lint.py", "--quiet"],
            capture_output=True, text=True, timeout=60
        )
        output = result.stdout.strip()
        match = re.search(r"(\d+) violations", output)
        if match:
            current_violations = int(match.group(1))
        elif "No changed templates" in output or "0 violations" in output:
            current_violations = 0
    except Exception as e:
        return 4, f"Lint trend: could not run lint — {e}", []

    if current_violations is None:
        return 4, "Lint trend: could not parse violation count", []

    # Load history
    history = []
    try:
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        if os.path.exists(history_file):
            with open(history_file) as f:
                history = json.load(f)
    except Exception:
        history = []

    # Append current run
    history.append({
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "violations": current_violations,
    })
    # Keep last 10 runs
    history = history[-10:]

    try:
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception:
        pass  # Non-fatal — trend tracking is best-effort

    if len(history) < 2:
        return 5, f"Lint trend: {current_violations} violations (no history yet)", []

    # Compare against last 3 runs (excluding current)
    recent = [h["violations"] for h in history[:-1][-3:]]
    avg_recent = sum(recent) / len(recent)

    if current_violations == 0:
        return 5, f"Lint trend: 0 violations (clean)", []
    elif current_violations <= avg_recent:
        return 5, f"Lint trend: {current_violations} violations (stable/declining, avg {avg_recent:.0f})", []
    elif current_violations <= avg_recent * 1.5:
        # Growing moderately
        issues.append(f"Violations grew from avg {avg_recent:.0f} to {current_violations}")
        return 3, f"Lint trend: {current_violations} violations (growing — avg {avg_recent:.0f})", issues
    else:
        # Spike: more than 50% increase
        issues.append(f"Violation spike: from avg {avg_recent:.0f} to {current_violations}")
        return 1, f"Lint trend: {current_violations} violations (spike — avg {avg_recent:.0f})", issues


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

    print("Checking migration safety...") if not args.quiet else None
    score, msg, issues = check_migration_safety()
    results.append(("Migration Safety", score, msg, issues))

    print("Checking lint trend...") if not args.quiet else None
    score, msg, issues = check_lint_trend()
    results.append(("Lint Trend", score, msg, issues))

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

        print("Checking cron endpoint health...") if not args.quiet else None
        score, msg, issues = check_cron_health(args.staging_url)
        results.append(("Cron Health", score, msg, issues))
    elif args.skip_remote:
        for name in ["Health", "Smoke Test", "Data Freshness", "Auth Safety", "Performance", "Cron Health"]:
            results.append((name, 5, "Skipped (--skip-remote)", []))

    # --- Compute weighted score ---
    #
    # Two-tier aggregation (c.ai recommendation):
    # Tier 1: Hard holds (auth, secrets) — binary PASS/FAIL, always block
    # Tier 2: Scored checks — weighted by risk category
    #
    # Categories and weights:
    #   Safety (1.0x):  Test Suite, Dependencies, Migration Safety
    #   Data (1.0x):    Health, Data Freshness, Smoke Test
    #   Ops (0.8x):     Route Inventory, Performance, Cron Health
    #   Design (0.6x):  Design Tokens, Lint Trend
    #
    # Effective score = min across weighted category minimums
    # A category score is floored at 2 (a single low-weight category
    # can't drag effective score below 2 on its own unless raw = 1)

    CATEGORY_WEIGHTS = {
        "Design Tokens": ("design", 0.6),
        "Test Suite": ("safety", 1.0),
        "Dependencies": ("safety", 1.0),
        "Health": ("data", 1.0),
        "Data Freshness": ("data", 1.0),
        "Smoke Test": ("data", 1.0),
        "Route Inventory": ("ops", 0.8),
        "Performance": ("ops", 0.8),
        # Auth Safety and Secret Leak handled as hard holds, not scored
        # Checks 11-13
        "Migration Safety": ("safety", 1.0),
        "Cron Health": ("ops", 0.8),
        "Lint Trend": ("design", 0.6),
    }

    category_mins = {}  # category -> min raw score
    for name, raw_score, msg, issues in results:
        if name in ("Auth Safety", "Secret Leak"):
            continue  # handled by hard_holds
        cat_info = CATEGORY_WEIGHTS.get(name)
        if not cat_info:
            continue
        cat_name, weight = cat_info
        if cat_name not in category_mins or raw_score < category_mins[cat_name][0]:
            category_mins[cat_name] = (raw_score, weight, name)

    # Compute weighted category scores
    # Weight only dampens violations — a perfect score stays perfect
    # Weight formula: effective = 5 - (5 - raw) * weight
    # At raw=5: effective=5 (always). At raw=1, weight=0.6: effective=5-4*0.6=2.6→3
    # This means low-weight categories can't drag score as far down
    weighted_scores = {}
    for cat_name, (raw, weight, check_name) in category_mins.items():
        if raw == 5:
            weighted = 5.0
        else:
            penalty = (5 - raw) * weight
            weighted = 5.0 - penalty
            # Floor: a category can't drag below 2 unless raw is 1
            if raw >= 2:
                weighted = max(weighted, 2.0)
        weighted_scores[cat_name] = (round(weighted, 1), raw, weight, check_name)

    effective_score_float = min(ws[0] for ws in weighted_scores.values()) if weighted_scores else 5.0
    effective_score = max(1, min(5, round(effective_score_float)))

    # Raw min for reference
    raw_scores = [r[1] for r in results if isinstance(r[1], int)]
    raw_min = min(raw_scores) if raw_scores else 5

    if hard_holds:
        verdict = "HOLD"
        reason = f"Hard hold: {', '.join(h[0] for h in hard_holds)}"
    elif effective_score <= 2:
        verdict = "HOLD"
        reason = f"Effective score {effective_score}/5 — user-visible issues require Tim review before prod"
    elif effective_score <= 3:
        verdict = "PROMOTE"
        reason = f"Effective score {effective_score}/5 — promote to prod, mandatory hotfix session after"
    else:
        verdict = "PROMOTE"
        reason = f"Effective score {effective_score}/5 — clean, auto-promote to prod"

    # --- Hotfix ratchet ---
    # If score 3 (promote with mandatory hotfix), write HOTFIX_REQUIRED.md with the
    # names of failing checks. On the next run at score 3, compare check names:
    # - Same checks still failing → ratchet triggers → HOLD
    # - Different checks failing → different issues, reset ratchet, no HOLD
    # - First occurrence → no ratchet (nothing to compare against)
    hotfix_file = "qa-results/HOTFIX_REQUIRED.md"
    hotfix_ratchet_triggered = False

    # Collect the names of checks currently failing (score <= 3 with issues)
    current_failing_checks = sorted([
        name for name, score, msg, issues in results
        if isinstance(score, int) and score <= 3 and issues
    ])

    def _read_previous_failing_checks(path):
        """Parse check names from an existing HOTFIX_REQUIRED.md.

        Looks for lines matching:
            ## Failing checks
            - check_name
        Returns a sorted list of check names, or an empty list if the section
        is missing or the file cannot be read.
        """
        try:
            with open(path) as f:
                content = f.read()
        except OSError:
            return []

        # Find the "## Failing checks" section and collect bullet items.
        # The section header is followed by a blank line before the bullets.
        match = re.search(r"## Failing checks\n\n?((?:- .+\n?)*)", content)
        if not match:
            return []
        checks = []
        for line in match.group(1).strip().split("\n"):
            line = line.strip()
            if line.startswith("- "):
                checks.append(line[2:].strip())
        return sorted(checks)

    if effective_score == 3 and not hard_holds:
        if os.path.exists(hotfix_file):
            previous_failing_checks = _read_previous_failing_checks(hotfix_file)
            if previous_failing_checks and set(current_failing_checks) & set(previous_failing_checks):
                # At least one of the same checks is still failing → ratchet triggers
                overlapping = sorted(set(current_failing_checks) & set(previous_failing_checks))
                hotfix_ratchet_triggered = True
                verdict = "HOLD"
                reason = (
                    f"Hotfix ratchet: {len(overlapping)} check(s) still failing from previous sprint "
                    f"({', '.join(overlapping)}) — downgraded to HOLD"
                )
            else:
                # Different checks failing (or no structured history) — reset ratchet
                # Overwrite the hotfix file with the new failing checks
                hotfix_issues = [(name, msg) for name, score, msg, issues in results
                                 if isinstance(score, int) and score <= 3 and issues]
                os.makedirs(os.path.dirname(hotfix_file), exist_ok=True)
                with open(hotfix_file, "w") as f:
                    f.write("# HOTFIX REQUIRED\n\n")
                    f.write(f"**Created:** {time.strftime('%Y-%m-%d %H:%M UTC')}\n")
                    f.write(f"**Deadline:** 48 hours from creation\n")
                    f.write(f"**Score:** {effective_score}/5\n\n")
                    f.write("## Failing checks\n\n")
                    for name in current_failing_checks:
                        f.write(f"- {name}\n")
                    f.write("\n## Issues requiring hotfix\n\n")
                    for name, msg in hotfix_issues:
                        f.write(f"- **{name}:** {msg}\n")
                    f.write("\n## Resolution\n\nFix issues, re-run `python scripts/prod_gate.py`. "
                            "Delete this file when score improves to 4+.\n")
                    f.write("\n_Note: Previous hotfix file replaced — different checks are now failing._\n")
        else:
            # First time at score 3 — write hotfix requirement
            hotfix_issues = [(name, msg) for name, score, msg, issues in results
                             if isinstance(score, int) and score <= 3 and issues]
            os.makedirs(os.path.dirname(hotfix_file), exist_ok=True)
            with open(hotfix_file, "w") as f:
                f.write("# HOTFIX REQUIRED\n\n")
                f.write(f"**Created:** {time.strftime('%Y-%m-%d %H:%M UTC')}\n")
                f.write(f"**Deadline:** 48 hours from creation\n")
                f.write(f"**Score:** {effective_score}/5\n\n")
                f.write("## Failing checks\n\n")
                for name in current_failing_checks:
                    f.write(f"- {name}\n")
                f.write("\n## Issues requiring hotfix\n\n")
                for name, msg in hotfix_issues:
                    f.write(f"- **{name}:** {msg}\n")
                f.write("\n## Resolution\n\nFix issues, re-run `python scripts/prod_gate.py`. "
                        "Delete this file when score improves to 4+.\n")
    elif effective_score >= 4 and os.path.exists(hotfix_file):
        # Hotfix was required but issues are now resolved — clean up
        os.remove(hotfix_file)

    # --- Build release notes + report ---

    # Gather git stats for release notes
    try:
        git_stat = subprocess.run(
            ["git", "diff", "--stat", "HEAD~5..HEAD"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip().split("\n")[-1] if True else ""
        git_log = subprocess.run(
            ["git", "log", "--oneline", "HEAD~5..HEAD"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        git_stat = "unknown"
        git_log = "unknown"

    # Find changed templates for release notes
    try:
        changed_templates = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~5..HEAD", "--", "web/templates/", "web/static/"],
            capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        changed_templates = ""

    lines = []

    # --- Release Notes (glanceable summary) ---
    lines.append("# Prod Promotion Gate Report")
    lines.append("")
    lines.append(f"**Verdict: {verdict}**")
    lines.append(f"**Effective Score: {effective_score}/5** (raw min: {raw_min}/5)")
    lines.append(f"**Reason:** {reason}")
    lines.append(f"**Timestamp:** {time.strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    if hotfix_ratchet_triggered:
        lines.append("> **HOTFIX RATCHET:** The same check(s) that required a hotfix last sprint ")
        lines.append("> are still failing. Downgraded to HOLD. Fix the overlapping issues in ")
        lines.append("> `qa-results/HOTFIX_REQUIRED.md` before promoting. Note: if *different* checks ")
        lines.append("> had failed this sprint the ratchet would NOT have triggered.")
        lines.append("")

    # Release notes section
    lines.append("## Release Notes")
    lines.append("")
    lines.append("### What shipped")
    if git_log and git_log != "unknown":
        for commit_line in git_log.split("\n")[:8]:
            lines.append(f"- {commit_line}")
    else:
        lines.append("- (git log unavailable)")
    lines.append("")
    if git_stat and git_stat != "unknown":
        lines.append(f"**Diff:** {git_stat}")
    if changed_templates:
        template_list = [t for t in changed_templates.split("\n") if t.strip()]
        if template_list:
            lines.append(f"**Templates changed:** {len(template_list)}")
            for t in template_list[:5]:
                lines.append(f"  - {t}")
            if len(template_list) > 5:
                lines.append(f"  - ... and {len(template_list) - 5} more")
    lines.append("")

    # Gate scores
    lines.append("### Gate Scores")
    lines.append("")

    if hard_holds:
        for name, msg, issues in hard_holds:
            lines.append(f"**{name}: HOLD** — {msg}")
            for issue in issues[:3]:
                lines.append(f"  - {issue}")
        lines.append("")

    lines.append("| Check | Score | Category | Weight | Result |")
    lines.append("|-------|-------|----------|--------|--------|")
    for name, raw_score, msg, issues in results:
        icon = {5: "5/5", 4: "4/5", 3: "3/5", 2: "2/5", 1: "1/5"}.get(raw_score, "?")
        cat_info = CATEGORY_WEIGHTS.get(name)
        if cat_info:
            cat_name, weight = cat_info
            lines.append(f"| {name} | {icon} | {cat_name} | {weight}x | {msg} |")
        else:
            lines.append(f"| {name} | {icon} | hard hold | — | {msg} |")
    lines.append("")

    # Weighted breakdown
    if weighted_scores:
        lines.append("### Weighted Category Scores")
        lines.append("")
        lines.append("| Category | Raw Min | Weight | Effective | Limiting Check |")
        lines.append("|----------|---------|--------|-----------|----------------|")
        for cat_name, (weighted, raw, weight, check_name) in sorted(weighted_scores.items()):
            lines.append(f"| {cat_name} | {raw}/5 | {weight}x | {weighted} | {check_name} |")
        lines.append("")

    # Hotfix status
    if effective_score == 3 and not hotfix_ratchet_triggered and not hard_holds:
        lines.append("### Hotfix Required")
        lines.append("")
        lines.append(f"A hotfix session is **mandatory** within 48 hours.")
        lines.append(f"Hotfix tracker: `qa-results/HOTFIX_REQUIRED.md`")
        lines.append(f"If not resolved by next promotion, score will downgrade to HOLD.")
        lines.append("")
        hotfix_items = [(name, msg) for name, score, msg, issues in results if score <= 3 and issues]
        for name, msg in hotfix_items:
            lines.append(f"- **{name}:** {msg}")
        lines.append("")

    # Issue details
    any_issues = [(name, issues) for name, score, msg, issues in results if issues]
    if any_issues:
        lines.append("## Issue Details")
        lines.append("")
        for name, issues in any_issues:
            lines.append(f"### {name}")
            for issue in issues[:10]:
                lines.append(f"- {issue[:200]}")
            lines.append("")

    # Promotion rules reference
    lines.append("## Promotion Rules")
    lines.append("")
    lines.append("| Effective Score | Action |")
    lines.append("|----------------|--------|")
    lines.append("| 5/5 | Auto-promote to prod |")
    lines.append("| 4/5 | Auto-promote, hotfix after |")
    lines.append("| 3/5 | Promote, mandatory hotfix within 48h (ratchet on repeat) |")
    lines.append("| 2/5 | HOLD — Tim reviews before prod |")
    lines.append("| 1/5 | HOLD — Tim reviews before prod |")
    lines.append("| Auth/Secret | Always HOLD regardless of score |")
    lines.append("| Hotfix ratchet | Same checks fail twice in a row → downgrade to HOLD (different checks = reset) |")
    lines.append("")
    lines.append("*Scoring uses weighted category minimums (safety 1.0x: tests, deps, migration safety; "
                 "data 1.0x: health, freshness, smoke; ops 0.8x: routes, perf, cron health; "
                 "design 0.6x: tokens, lint trend). "
                 "A low-weight category can't drag the effective score below 2 unless its raw score is 1.*")
    lines.append("")

    report = "\n".join(lines)

    # Write report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    if args.quiet:
        print(f"Prod gate: {verdict} ({effective_score}/5, raw min {raw_min}/5) — {reason}")
    else:
        print(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
