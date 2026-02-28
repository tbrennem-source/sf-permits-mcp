#!/usr/bin/env python3
"""CHECKQUAD Step 4: Test Hygiene Audit.

Scans test files for common anti-patterns that cause cross-contamination,
env leaks, and import collisions. Outputs a markdown report suitable for
embedding in CHECKQUAD session artifacts.

Anti-patterns checked:
1. os.environ[] assignments (must use monkeypatch)
2. sys.path.insert (breaks module isolation)
3. importlib.reload without restore fixture
4. Bare "from app import" (dual module bug)
5. Sprint-numbered test files (prefer feature names)

Usage:
    python scripts/test_hygiene.py                    # scan all tests/
    python scripts/test_hygiene.py --changed           # only git-changed test files
    python scripts/test_hygiene.py --files tests/test_foo.py tests/test_bar.py
    python scripts/test_hygiene.py --quiet             # exit code only (0=clean, 1=violations)
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


# --- Anti-pattern definitions ---

CHECKS = [
    {
        "id": "ENV_ASSIGN",
        "name": "os.environ[] assignment",
        "description": "Direct os.environ assignments leak across tests. Use monkeypatch.setenv() instead.",
        "pattern": re.compile(r"""os\.environ\["""),
        # Exclude reads: os.environ.get(), os.environ.pop(), os.environ.setdefault()
        "exclude_pattern": re.compile(r"""os\.environ\.(get|pop|setdefault|copy|keys|values|items)\b"""),
        # Also exclude lines that ARE monkeypatch usage
        "exclude_line_pattern": re.compile(r"""monkeypatch"""),
        "severity": "high",
    },
    {
        "id": "SYS_PATH",
        "name": "sys.path.insert",
        "description": "sys.path.insert breaks module isolation and causes import order bugs.",
        "pattern": re.compile(r"""sys\.path\.insert"""),
        "exclude_pattern": None,
        "exclude_line_pattern": None,
        "severity": "high",
    },
    {
        "id": "RELOAD_NO_RESTORE",
        "name": "importlib.reload without restore",
        "description": "importlib.reload mutates global module state. Must be paired with a restore fixture.",
        "pattern": re.compile(r"""importlib\.reload"""),
        "exclude_pattern": None,
        "exclude_line_pattern": None,
        "severity": "medium",
    },
    {
        "id": "BARE_APP_IMPORT",
        "name": "bare 'from app import'",
        "description": "Bare 'from app import' triggers the dual module bug. Use 'from web.app import' instead.",
        "pattern": re.compile(r"""^from app import"""),
        "exclude_pattern": None,
        "exclude_line_pattern": None,
        "severity": "high",
    },
]


def get_changed_test_files() -> list[Path]:
    """Get test files changed vs HEAD (staged + unstaged)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD", "--", "tests/"],
            capture_output=True, text=True, check=True,
        )
        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--", "tests/"],
            capture_output=True, text=True, check=True,
        )
        files = set(result.stdout.strip().split("\n") + staged.stdout.strip().split("\n"))
        return [Path(f) for f in files if f.endswith(".py") and Path(f).exists()]
    except subprocess.CalledProcessError:
        return []


def get_sprint_named_files() -> list[Path]:
    """Find test files with sprint numbers in their names (recent commits only)."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~10", "--", "tests/"],
            capture_output=True, text=True,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []
        return [Path(f) for f in files if re.search(r"test_sprint_\d+", f)]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def scan_file(filepath: Path) -> list[dict]:
    """Scan a single file for anti-patterns."""
    violations = []
    try:
        lines = filepath.read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        return violations

    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue

        for check in CHECKS:
            if check["pattern"].search(stripped):
                # Apply exclusions
                if check.get("exclude_pattern") and check["exclude_pattern"].search(stripped):
                    continue
                if check.get("exclude_line_pattern") and check["exclude_line_pattern"].search(stripped):
                    continue
                violations.append({
                    "file": str(filepath),
                    "line": line_num,
                    "check_id": check["id"],
                    "check_name": check["name"],
                    "severity": check["severity"],
                    "content": stripped[:120],
                    "description": check["description"],
                })

    return violations


def generate_report(violations: list[dict], sprint_files: list[Path], scanned_count: int) -> str:
    """Generate markdown report for CHECKQUAD session artifact."""
    lines = ["## Test Hygiene Audit", ""]

    if not violations and not sprint_files:
        lines.append(f"**Result: CLEAN** — {scanned_count} files scanned, 0 violations found.")
        return "\n".join(lines)

    # Summary
    high = sum(1 for v in violations if v["severity"] == "high")
    medium = sum(1 for v in violations if v["severity"] == "medium")
    lines.append(f"**Scanned:** {scanned_count} files")
    lines.append(f"**Violations:** {len(violations)} ({high} high, {medium} medium)")
    if sprint_files:
        lines.append(f"**Sprint-named files:** {len(sprint_files)} (prefer feature names)")
    lines.append("")

    # Group by check
    if violations:
        lines.append("### Violations")
        lines.append("")
        lines.append("| File | Line | Check | Severity | Code |")
        lines.append("|------|------|-------|----------|------|")
        for v in sorted(violations, key=lambda x: (x["severity"] != "high", x["file"], x["line"])):
            lines.append(
                f"| `{v['file']}` | {v['line']} | {v['check_name']} | {v['severity']} | `{v['content'][:60]}` |"
            )
        lines.append("")

    # Sprint-named files warning
    if sprint_files:
        lines.append("### Sprint-Named Files (warning)")
        lines.append("")
        lines.append("These files use sprint numbers instead of feature names. Consider renaming:")
        for f in sprint_files:
            lines.append(f"- `{f}`")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="CHECKQUAD test hygiene audit")
    parser.add_argument("--changed", action="store_true", help="Only scan git-changed test files")
    parser.add_argument("--files", nargs="+", help="Specific files to scan")
    parser.add_argument("--quiet", action="store_true", help="Exit code only (0=clean, 1=violations)")
    args = parser.parse_args()

    # Determine files to scan
    if args.files:
        test_files = [Path(f) for f in args.files if Path(f).exists()]
    elif args.changed:
        test_files = get_changed_test_files()
    else:
        test_dir = Path("tests")
        if not test_dir.exists():
            print("No tests/ directory found.", file=sys.stderr)
            sys.exit(0)
        test_files = sorted(test_dir.rglob("*.py"))

    # Scan
    all_violations = []
    for f in test_files:
        all_violations.extend(scan_file(f))

    sprint_files = get_sprint_named_files()

    if args.quiet:
        sys.exit(1 if all_violations else 0)

    report = generate_report(all_violations, sprint_files, len(test_files))
    print(report)

    sys.exit(1 if all_violations else 0)


if __name__ == "__main__":
    main()
