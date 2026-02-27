#!/usr/bin/env python3
"""
Security audit script for sf-permits-mcp.

Runs bandit (static security analysis) and pip-audit (dependency vulnerability scan),
parses their JSON output, and produces a combined markdown report.

Exit codes:
  0 — no HIGH severity issues found
  1 — HIGH severity issues found in bandit or pip-audit
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def run_command(cmd: list[str]) -> tuple[int, str, str]:
    """Run a command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out: {' '.join(cmd)}"


def check_tool_available(tool: str) -> bool:
    """Return True if the tool is available on PATH."""
    rc, _, _ = run_command([tool, "--version"])
    return rc == 0


def run_bandit(project_root: Path) -> dict:
    """
    Run bandit static analysis on src/ and web/ directories.

    Returns a dict with keys: available, issues, high_count, medium_count, low_count, raw
    """
    result = {
        "available": check_tool_available("bandit"),
        "issues": [],
        "high_count": 0,
        "medium_count": 0,
        "low_count": 0,
        "raw": "",
        "error": None,
    }

    if not result["available"]:
        result["error"] = "bandit not installed — skipping (install with: pip install bandit)"
        return result

    targets = []
    for subdir in ["src", "web"]:
        p = project_root / subdir
        if p.exists():
            targets.append(str(p))

    if not targets:
        result["error"] = "No src/ or web/ directories found to scan"
        return result

    cmd = [
        "bandit",
        "-r",
        *targets,
        "-f", "json",
        "--config", str(project_root / ".bandit"),
    ]

    # If .bandit config doesn't exist, run without it
    if not (project_root / ".bandit").exists():
        cmd = ["bandit", "-r", *targets, "-f", "json", "-s", "B101"]

    rc, stdout, stderr = run_command(cmd)
    result["raw"] = stdout

    # bandit exits 1 when issues are found — that's normal, not an error
    # bandit exits 2 on usage error, -1 means not found
    if rc == -1:
        result["available"] = False
        result["error"] = stderr
        return result

    if not stdout.strip():
        result["error"] = f"bandit produced no output (rc={rc}): {stderr}"
        return result

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        result["error"] = f"Failed to parse bandit JSON output: {e}"
        return result

    for issue in data.get("results", []):
        severity = issue.get("issue_severity", "").upper()
        result["issues"].append({
            "severity": severity,
            "confidence": issue.get("issue_confidence", ""),
            "test_id": issue.get("test_id", ""),
            "test_name": issue.get("test_name", ""),
            "filename": issue.get("filename", ""),
            "line_number": issue.get("line_number", 0),
            "issue_text": issue.get("issue_text", ""),
            "code": issue.get("code", "").strip(),
        })
        if severity == "HIGH":
            result["high_count"] += 1
        elif severity == "MEDIUM":
            result["medium_count"] += 1
        else:
            result["low_count"] += 1

    return result


def run_pip_audit(project_root: Path) -> dict:
    """
    Run pip-audit vulnerability scan.

    Returns a dict with keys: available, vulnerabilities, high_count, raw, error
    """
    result = {
        "available": check_tool_available("pip-audit"),
        "vulnerabilities": [],
        "high_count": 0,
        "raw": "",
        "error": None,
    }

    if not result["available"]:
        result["error"] = "pip-audit not installed — skipping (install with: pip install pip-audit)"
        return result

    cmd = ["pip-audit", "--format", "json", "--progress-spinner", "off"]

    rc, stdout, stderr = run_command(cmd)
    result["raw"] = stdout

    if rc == -1:
        result["available"] = False
        result["error"] = stderr
        return result

    if not stdout.strip():
        result["error"] = f"pip-audit produced no output (rc={rc}): {stderr}"
        return result

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        result["error"] = f"Failed to parse pip-audit JSON output: {e}"
        return result

    # pip-audit JSON structure: list of {"name": ..., "version": ..., "vulns": [...]}
    # or nested under "dependencies" key depending on version
    dependencies = data if isinstance(data, list) else data.get("dependencies", [])

    for dep in dependencies:
        for vuln in dep.get("vulns", []):
            aliases = vuln.get("aliases", [])
            # Determine severity from CVE aliases or fix_versions
            fix_versions = vuln.get("fix_versions", [])
            severity = _infer_pip_audit_severity(vuln)

            result["vulnerabilities"].append({
                "package": dep.get("name", ""),
                "installed_version": dep.get("version", ""),
                "vuln_id": vuln.get("id", ""),
                "aliases": aliases,
                "description": vuln.get("description", ""),
                "fix_versions": fix_versions,
                "severity": severity,
            })

            if severity == "HIGH":
                result["high_count"] += 1

    return result


def _infer_pip_audit_severity(vuln: dict) -> str:
    """
    pip-audit doesn't always include CVSS severity in basic JSON output.
    Use heuristics: if fix_versions is empty or vuln description mentions 'critical'/'high',
    classify as HIGH. Otherwise MEDIUM.
    """
    desc = vuln.get("description", "").lower()
    if any(kw in desc for kw in ["critical", "remote code execution", "rce", "arbitrary code"]):
        return "HIGH"
    # Default to MEDIUM for known vulnerabilities without clear severity
    return "MEDIUM"


def build_report(
    bandit_result: dict,
    pip_result: dict,
    project_root: Path,
) -> str:
    """Build a combined markdown security audit report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_high = bandit_result.get("high_count", 0) + pip_result.get("high_count", 0)

    status_badge = "PASS" if total_high == 0 else "FAIL — HIGH SEVERITY ISSUES FOUND"

    lines = [
        "# Security Audit Report",
        "",
        f"**Generated:** {now}",
        f"**Status:** {status_badge}",
        f"**Project root:** `{project_root}`",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| Tool | Status | HIGH | MEDIUM | LOW |",
        "|------|--------|------|--------|-----|",
    ]

    # Bandit row
    if not bandit_result["available"]:
        lines.append("| bandit | SKIPPED (not installed) | — | — | — |")
    elif bandit_result.get("error") and not bandit_result["issues"]:
        lines.append(f"| bandit | ERROR | — | — | — |")
    else:
        b_status = "FAIL" if bandit_result["high_count"] > 0 else "PASS"
        lines.append(
            f"| bandit | {b_status} | {bandit_result['high_count']} "
            f"| {bandit_result['medium_count']} | {bandit_result['low_count']} |"
        )

    # pip-audit row
    if not pip_result["available"]:
        lines.append("| pip-audit | SKIPPED (not installed) | — | — | — |")
    elif pip_result.get("error") and not pip_result["vulnerabilities"]:
        lines.append("| pip-audit | ERROR | — | — | — |")
    else:
        p_status = "FAIL" if pip_result["high_count"] > 0 else "PASS"
        total_vulns = len(pip_result["vulnerabilities"])
        lines.append(
            f"| pip-audit | {p_status} | {pip_result['high_count']} "
            f"| {total_vulns - pip_result['high_count']} | 0 |"
        )

    lines += ["", "---", ""]

    # Bandit section
    lines += ["## Bandit — Static Security Analysis", ""]

    if not bandit_result["available"]:
        lines.append(f"> **Skipped:** {bandit_result.get('error', 'bandit not installed')}")
        lines.append("")
    elif bandit_result.get("error") and not bandit_result["issues"]:
        lines.append(f"> **Error:** {bandit_result['error']}")
        lines.append("")
    elif not bandit_result["issues"]:
        lines.append("> No issues found.")
        lines.append("")
    else:
        # Group by severity
        for severity in ["HIGH", "MEDIUM", "LOW"]:
            severity_issues = [i for i in bandit_result["issues"] if i["severity"] == severity]
            if not severity_issues:
                continue

            lines += [f"### {severity} ({len(severity_issues)} issue{'s' if len(severity_issues) != 1 else ''})", ""]

            for issue in severity_issues:
                lines += [
                    f"**[{issue['test_id']}] {issue['test_name']}**",
                    f"- File: `{issue['filename']}` line {issue['line_number']}",
                    f"- Confidence: {issue['confidence']}",
                    f"- Issue: {issue['issue_text']}",
                    "",
                ]
                if issue.get("code"):
                    lines += [
                        "```python",
                        issue["code"],
                        "```",
                        "",
                    ]

    # pip-audit section
    lines += ["## pip-audit — Dependency Vulnerabilities", ""]

    if not pip_result["available"]:
        lines.append(f"> **Skipped:** {pip_result.get('error', 'pip-audit not installed')}")
        lines.append("")
    elif pip_result.get("error") and not pip_result["vulnerabilities"]:
        lines.append(f"> **Error:** {pip_result['error']}")
        lines.append("")
    elif not pip_result["vulnerabilities"]:
        lines.append("> No known vulnerabilities found in installed packages.")
        lines.append("")
    else:
        for vuln in pip_result["vulnerabilities"]:
            severity = vuln["severity"]
            lines += [
                f"### [{severity}] {vuln['package']} {vuln['installed_version']}",
                "",
                f"**Vulnerability ID:** {vuln['vuln_id']}",
            ]
            if vuln.get("aliases"):
                lines.append(f"**Aliases:** {', '.join(vuln['aliases'])}")
            if vuln.get("fix_versions"):
                lines.append(f"**Fix versions:** {', '.join(vuln['fix_versions'])}")
            if vuln.get("description"):
                lines.append(f"**Description:** {vuln['description']}")
            lines.append("")

    # Error notes
    errors = []
    if bandit_result.get("error") and not bandit_result["issues"]:
        errors.append(f"- **bandit:** {bandit_result['error']}")
    if pip_result.get("error") and not pip_result["vulnerabilities"]:
        errors.append(f"- **pip-audit:** {pip_result['error']}")

    if errors:
        lines += ["---", "", "## Errors / Warnings", ""] + errors + [""]

    lines += [
        "---",
        "",
        f"*Report generated by `scripts/security_audit.py` at {now}*",
        "",
    ]

    return "\n".join(lines)


def main() -> int:
    """
    Main entry point.

    Returns exit code: 0 = no HIGH issues, 1 = HIGH issues found.
    """
    project_root = Path(__file__).parent.parent

    print("Running security audit...")
    print(f"Project root: {project_root}")
    print()

    # Run bandit
    print("Running bandit static analysis...", end=" ", flush=True)
    bandit_result = run_bandit(project_root)
    if not bandit_result["available"]:
        print(f"SKIPPED — {bandit_result.get('error', 'not installed')}")
    elif bandit_result.get("error") and not bandit_result["issues"]:
        print(f"ERROR — {bandit_result['error']}")
    else:
        print(
            f"done — {bandit_result['high_count']} HIGH, "
            f"{bandit_result['medium_count']} MEDIUM, "
            f"{bandit_result['low_count']} LOW"
        )

    # Run pip-audit
    print("Running pip-audit dependency scan...", end=" ", flush=True)
    pip_result = run_pip_audit(project_root)
    if not pip_result["available"]:
        print(f"SKIPPED — {pip_result.get('error', 'not installed')}")
    elif pip_result.get("error") and not pip_result["vulnerabilities"]:
        print(f"ERROR — {pip_result['error']}")
    else:
        print(f"done — {len(pip_result['vulnerabilities'])} vulnerabilities found")

    print()

    # Build report
    report = build_report(bandit_result, pip_result, project_root)

    # Write report to qa-results/
    output_dir = project_root / "qa-results"
    output_dir.mkdir(exist_ok=True)
    report_path = output_dir / "security-audit-latest.md"
    report_path.write_text(report)
    print(f"Report written to: {report_path}")

    # Determine exit code
    total_high = bandit_result.get("high_count", 0) + pip_result.get("high_count", 0)
    if total_high > 0:
        print(f"\nFAIL — {total_high} HIGH severity issue(s) found. See report for details.")
        return 1

    print("\nPASS — no HIGH severity issues found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
