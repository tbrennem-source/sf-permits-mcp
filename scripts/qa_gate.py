#!/usr/bin/env python3
"""QA gate — merge gate script that orchestrates visual QA checks.

Runs structural visual QA and design token lint checks against a staging URL.
Exits 0 only if both pass. Exits 1 if either fails.

Usage:
    python scripts/qa_gate.py --url https://sfpermits-ai-staging-production.up.railway.app --sprint qs10

    # Skip individual checks during development:
    python scripts/qa_gate.py --url https://... --sprint qs10 --skip-structural
    python scripts/qa_gate.py --url https://... --sprint qs10 --skip-lint
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


QA_RESULTS_DIR = Path("qa-results")
GATE_RESULTS_FILE = QA_RESULTS_DIR / "qa-gate-results.md"


def run_structural_check(url: str, sprint: str) -> tuple[bool, str, list[str]]:
    """Run visual_qa.py structural check.

    Returns (passed, details_str, failed_pages).
    """
    cmd = [
        sys.executable,
        "scripts/visual_qa.py",
        "--url", url,
        "--sprint", sprint,
    ]

    print(f"Running structural check: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=300,
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode

        # Parse output for failures
        failed_pages: list[str] = []
        lines = stdout.splitlines()
        for line in lines:
            # visual_qa.py prints "N/M OK" lines per viewport
            # It also prints FAIL in results markdown
            if "FAIL" in line and "| FAIL |" in line:
                # Markdown table row: | page | FAIL | diff% | msg |
                parts = [p.strip() for p in line.split("|")]
                if len(parts) >= 3:
                    page_slug = parts[1]
                    failed_pages.append(page_slug)

        # Check return code
        passed = returncode == 0 and len(failed_pages) == 0
        details = stdout[:2000] if stdout else "(no output)"
        if stderr:
            details += f"\nSTDERR: {stderr[:500]}"

        return passed, details, failed_pages

    except subprocess.TimeoutExpired:
        return False, "Structural check timed out after 300s", []
    except FileNotFoundError:
        return False, "scripts/visual_qa.py not found", []
    except Exception as e:
        return False, f"Structural check error: {e}", []


def run_lint_check(url: str) -> tuple[bool, int, str]:
    """Run design_lint.py against changed templates.

    Returns (passed, score, details_str).
    Fails if score <= 2.
    """
    cmd = [
        sys.executable,
        "scripts/design_lint.py",
        "--changed",
        "--quiet",
    ]

    print(f"Running lint check: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=60,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # Parse score from output: "Token lint: N/5 (M violations across K files)"
        score = 5  # default to clean if no output
        score_match = re.search(r"Token lint:\s*(\d)/5", stdout)
        if score_match:
            score = int(score_match.group(1))

        # Also handle "No changed templates found." — treat as clean
        if "No changed templates found" in stdout:
            score = 5

        passed = score > 2
        details = stdout if stdout else "(no output)"
        if stderr:
            details += f"\nSTDERR: {stderr[:500]}"

        return passed, score, details

    except subprocess.TimeoutExpired:
        return False, 0, "Lint check timed out after 60s"
    except FileNotFoundError:
        return False, 0, "scripts/design_lint.py not found"
    except Exception as e:
        return False, 0, f"Lint check error: {e}"


def write_gate_results(
    url: str,
    sprint: str,
    structural_passed: bool,
    structural_details: str,
    failed_pages: list[str],
    lint_passed: bool,
    lint_score: int,
    lint_details: str,
    overall_passed: bool,
    skip_structural: bool,
    skip_lint: bool,
) -> str:
    """Write gate results to qa-results/qa-gate-results.md. Returns path."""
    QA_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status_icon = "PASS" if overall_passed else "FAIL"

    lines = [
        f"# QA Gate Results — {sprint}",
        f"Generated: {timestamp}",
        f"URL: {url}",
        f"**Overall: {status_icon}**",
        "",
        "## Check Results",
        "",
        "| Check | Status | Details |",
        "|-------|--------|---------|",
    ]

    if skip_structural:
        lines.append("| Structural | SKIP | --skip-structural flag |")
    else:
        struct_status = "PASS" if structural_passed else "FAIL"
        struct_detail = f"{len(failed_pages)} failed pages" if not structural_passed else "all pages OK"
        lines.append(f"| Structural | {struct_status} | {struct_detail} |")

    if skip_lint:
        lines.append("| Design Lint | SKIP | --skip-lint flag |")
    else:
        lint_status = "PASS" if lint_passed else "FAIL"
        lint_detail = f"Score {lint_score}/5"
        if not lint_passed:
            lint_detail += " (threshold: >2)"
        lines.append(f"| Design Lint | {lint_status} | {lint_detail} |")

    lines.append("")

    if not skip_structural and not structural_passed and failed_pages:
        lines.append("## Structural Failures")
        lines.append("")
        for page in failed_pages:
            lines.append(f"- {page}")
        lines.append("")

    lines.append("## Structural Check Output")
    lines.append("```")
    lines.append(structural_details[:3000] if not skip_structural else "(skipped)")
    lines.append("```")
    lines.append("")
    lines.append("## Lint Check Output")
    lines.append("```")
    lines.append(lint_details[:1000] if not skip_lint else "(skipped)")
    lines.append("```")

    content = "\n".join(lines)
    GATE_RESULTS_FILE.write_text(content)
    return str(GATE_RESULTS_FILE)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="QA gate — orchestrates visual QA and design lint checks",
    )
    parser.add_argument("--url", required=True, help="Base URL to test against")
    parser.add_argument("--sprint", required=True, help="Sprint label (e.g. qs10)")
    parser.add_argument("--skip-structural", action="store_true", help="Skip structural visual check")
    parser.add_argument("--skip-lint", action="store_true", help="Skip design lint check")
    args = parser.parse_args()

    print(f"QA Gate — sprint={args.sprint} url={args.url}")
    print("=" * 60)

    # --- Structural check ---
    structural_passed = True
    structural_details = "(skipped)"
    failed_pages: list[str] = []

    if not args.skip_structural:
        structural_passed, structural_details, failed_pages = run_structural_check(args.url, args.sprint)
        if structural_passed:
            print("Structural check: PASS")
        else:
            print(f"Structural check: FAIL ({len(failed_pages)} pages failed)", file=sys.stderr)
            if failed_pages:
                for pg in failed_pages:
                    print(f"  - {pg}", file=sys.stderr)
    else:
        print("Structural check: SKIP (--skip-structural)")

    print()

    # --- Lint check ---
    lint_passed = True
    lint_score = 5
    lint_details = "(skipped)"

    if not args.skip_lint:
        lint_passed, lint_score, lint_details = run_lint_check(args.url)
        if lint_passed:
            print(f"Design lint: PASS (score {lint_score}/5)")
        else:
            print(f"Design lint: FAIL (score {lint_score}/5 — threshold >2)", file=sys.stderr)
    else:
        print("Design lint: SKIP (--skip-lint)")

    print()

    # --- Overall result ---
    overall_passed = structural_passed and lint_passed

    results_path = write_gate_results(
        url=args.url,
        sprint=args.sprint,
        structural_passed=structural_passed,
        structural_details=structural_details,
        failed_pages=failed_pages,
        lint_passed=lint_passed,
        lint_score=lint_score,
        lint_details=lint_details,
        overall_passed=overall_passed,
        skip_structural=args.skip_structural,
        skip_lint=args.skip_lint,
    )

    print(f"Results written to {results_path}")
    print()

    if overall_passed:
        print("QA GATE: PASS — merge is clear")
        return 0
    else:
        failures = []
        if not structural_passed:
            failures.append(f"structural check ({len(failed_pages)} pages failed)")
        if not lint_passed:
            failures.append(f"design lint (score {lint_score}/5)")
        print(f"QA GATE: FAIL — {', '.join(failures)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
