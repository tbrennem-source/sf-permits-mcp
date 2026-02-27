#!/usr/bin/env python3
"""Design token lint — verify templates use the design system.

Non-blocking. Produces a report for post-sprint review.
Run: python scripts/design_lint.py [--files path1 path2 ...]
     python scripts/design_lint.py --changed   # only git-changed templates
     python scripts/design_lint.py             # all templates

Output: prints report to stdout, writes to qa-results/design-lint-results.md
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# --- Token palette (from docs/DESIGN_TOKENS.md §1) ---

ALLOWED_HEX = {
    # Backgrounds
    "#0a0a0f", "#12121a", "#1a1a26",
    # Accent
    "#5eead4",
    # Signal
    "#34d399", "#fbbf24", "#f87171", "#60a5fa",
    # Dots (high saturation)
    "#22c55e", "#f59e0b", "#ef4444",
    # Common shorthand equivalents
    "#fff", "#000",
}

# rgba patterns that are part of the token system
ALLOWED_RGBA_PATTERNS = [
    r"rgba\(255,\s*255,\s*255,\s*0?\.?\d+\)",  # white at any alpha (all text/glass tokens)
    r"rgba\(94,\s*234,\s*212",                  # accent variants (any alpha)
    r"rgba\(52,\s*211,\s*153",                  # signal-green variants
    r"rgba\(251,\s*191,\s*36",                  # signal-amber variants
    r"rgba\(248,\s*113,\s*113",                 # signal-red variants
    r"rgba\(96,\s*165,\s*250",                  # signal-blue variants
    r"rgba\(0,\s*0,\s*0",                       # black variants (backdrop)
    r"rgba\(34,\s*211,\s*238",                  # cyan variants (legacy accent)
]

# Token CSS custom properties — if templates use var(--xxx), that's fine
TOKEN_VAR_RE = re.compile(r"var\(--[\w-]+\)")

# Font families that are allowed
ALLOWED_FONTS = {"var(--mono)", "var(--sans)", "--mono", "--sans"}

# Token component classes (from DESIGN_TOKENS.md §5)
TOKEN_CLASSES = {
    "glass-card", "search-input", "search-bar", "ghost-cta",
    "action-btn", "action-btn--danger",
    "status-dot", "status-dot--green", "status-dot--amber", "status-dot--red",
    "status-text--green", "status-text--amber", "status-text--red",
    "chip", "data-row", "data-row__label", "data-row__value",
    "stat-number", "stat-label", "stat-item",
    "progress-track", "progress-fill", "progress-label",
    "dropdown", "dropdown__item", "dropdown__label",
    "section-divider",
    "skeleton", "skeleton--heading", "skeleton--text", "skeleton--dot", "skeleton-row",
    "obs-table", "obs-table-wrap", "obs-table__mono", "obs-table__empty",
    "form-label", "form-input", "form-check", "form-check__input",
    "form-check__box", "form-check__label",
    "form-toggle", "form-toggle__input", "form-toggle__track", "form-toggle__thumb",
    "form-toggle__label", "form-select",
    "form-upload", "form-upload__input", "form-upload__zone",
    "form-upload__icon", "form-upload__text", "form-upload__hint",
    "toast", "toast--success", "toast--error", "toast--info",
    "toast__icon", "toast__message", "toast__action", "toast__dismiss",
    "modal-backdrop", "modal", "modal__header", "modal__title",
    "modal__close", "modal__body", "modal__footer",
    "insight", "insight--green", "insight--amber", "insight--red", "insight--info",
    "insight__label", "insight__body",
    "expandable", "expandable__summary", "expandable__title",
    "expandable__arrow", "expandable__body",
    "risk-flag", "risk-flag--high", "risk-flag--medium", "risk-flag--low",
    "risk-flag__dot", "risk-flag__text",
    "action-prompt", "action-prompt__context",
    "tabs", "tab", "tab--active", "tab__count", "tab-panel",
    "load-more", "load-more__count", "load-more__btn", "load-more__spinner",
    "nav-float", "nav-float--hidden", "nav-float__wordmark", "nav-float__link",
    "reveal", "reveal-delay-1", "reveal-delay-2", "reveal-delay-3", "reveal-delay-4",
    "ambient",
    "obs-container", "obs-container-wide",
    "kbd-hint", "search-icon",
}


# --- Checks ---

def check_hex_colors(filepath, content, lines):
    """Find hex colors not in the token palette."""
    violations = []
    hex_re = re.compile(r"#([0-9a-fA-F]{3,8})\b")
    for i, line in enumerate(lines, 1):
        # Skip comments, Jinja2 comments, SVG fill="none"
        stripped = line.strip()
        if stripped.startswith("{#") or stripped.startswith("<!--") or stripped.startswith("//"):
            continue
        for match in hex_re.finditer(line):
            hex_val = f"#{match.group(1).lower()}"
            # Normalize 6-char to compare
            if len(hex_val) == 7 and hex_val in ALLOWED_HEX:
                continue
            if len(hex_val) == 4 and hex_val in ALLOWED_HEX:
                continue
            # Skip if inside a var() reference or SVG attribute
            context = line[max(0, match.start() - 30):match.end() + 10]
            if "var(--" in context:
                continue
            # Skip SVG stroke/fill hex in inline SVGs (common in templates)
            if "stroke=" in context or "fill=" in context or "stop-color=" in context:
                continue
            # Skip data URIs
            if "data:image" in line:
                continue
            violations.append({
                "file": filepath,
                "line": i,
                "issue": f"Non-token hex color: {hex_val}",
                "content": stripped[:120],
                "severity": "medium",
            })
    return violations


def check_font_families(filepath, content, lines):
    """Find font-family declarations not using token variables."""
    violations = []
    font_re = re.compile(r"font-family\s*:\s*([^;}{]+)")
    for i, line in enumerate(lines, 1):
        for match in font_re.finditer(line):
            value = match.group(1).strip()
            # OK if it uses var(--mono) or var(--sans)
            if "var(--mono)" in value or "var(--sans)" in value:
                continue
            # OK if it's in a <style> block referencing the token
            if "--mono" in value or "--sans" in value:
                continue
            violations.append({
                "file": filepath,
                "line": i,
                "issue": f"Non-token font-family: {value[:60]}",
                "content": line.strip()[:120],
                "severity": "high",
            })
    return violations


def check_inline_styles(filepath, content, lines):
    """Find inline style attributes with color/font/padding values."""
    violations = []
    style_re = re.compile(r'style\s*=\s*"([^"]*)"')
    flagged_props = {"color:", "background:", "background-color:", "font-family:", "font-size:", "border-color:"}
    for i, line in enumerate(lines, 1):
        for match in style_re.finditer(line):
            style_val = match.group(1).lower()
            for prop in flagged_props:
                if prop in style_val and "var(--" not in style_val:
                    violations.append({
                        "file": filepath,
                        "line": i,
                        "issue": f"Inline style with {prop} (should use token class or var())",
                        "content": line.strip()[:120],
                        "severity": "medium",
                    })
                    break
    return violations


def check_tertiary_misuse(filepath, content, lines):
    """Find --text-tertiary on interactive elements."""
    violations = []
    for i, line in enumerate(lines, 1):
        lower = line.lower()
        if "text-tertiary" not in lower:
            continue
        # Check if this line is associated with an interactive element
        # Look for nearby <a>, <button>, or clickable context
        context_window = "\n".join(lines[max(0, i - 3):min(len(lines), i + 2)]).lower()
        interactive_signals = ["<a ", "<button", "cursor: pointer", "onclick", "hx-get", "hx-post", "href="]
        for signal in interactive_signals:
            if signal in context_window:
                violations.append({
                    "file": filepath,
                    "line": i,
                    "issue": "--text-tertiary near interactive element (use --text-secondary for WCAG AA)",
                    "content": line.strip()[:120],
                    "severity": "high",
                })
                break
    return violations


def check_rgba_colors(filepath, content, lines):
    """Find rgba() colors not in the token system."""
    violations = []
    rgba_re = re.compile(r"rgba\([^)]+\)")
    for i, line in enumerate(lines, 1):
        for match in rgba_re.finditer(line):
            rgba_val = match.group(0)
            # Check against allowed patterns
            allowed = False
            for pattern in ALLOWED_RGBA_PATTERNS:
                if re.search(pattern, rgba_val):
                    allowed = True
                    break
            if not allowed:
                violations.append({
                    "file": filepath,
                    "line": i,
                    "issue": f"Non-token rgba color: {rgba_val[:60]}",
                    "content": line.strip()[:120],
                    "severity": "low",
                })
    return violations


# --- Runner ---

def get_changed_templates():
    """Get templates changed since last commit on main."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "--", "web/templates/", "web/static/"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        files = [f for f in result.stdout.strip().split("\n") if f]
        return files
    except Exception:
        return []


def get_all_templates():
    """Get all template and static files."""
    templates = list(Path("web/templates").rglob("*.html"))
    static_css = list(Path("web/static").rglob("*.css"))
    static_html = list(Path("web/static").rglob("*.html"))
    # Exclude mockups (they're reference files, not production)
    all_files = templates + static_css + static_html
    return [str(f) for f in all_files if "mockups" not in str(f)]


def lint_file(filepath):
    """Run all checks on a single file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
            lines = content.split("\n")
    except Exception as e:
        return [{"file": filepath, "line": 0, "issue": f"Could not read: {e}", "severity": "error"}]

    violations = []
    violations.extend(check_hex_colors(filepath, content, lines))
    violations.extend(check_font_families(filepath, content, lines))
    violations.extend(check_inline_styles(filepath, content, lines))
    violations.extend(check_tertiary_misuse(filepath, content, lines))
    violations.extend(check_rgba_colors(filepath, content, lines))
    return violations


def score(violations):
    """Score 1-5 based on violation count and severity."""
    if not violations:
        return 5
    high = sum(1 for v in violations if v["severity"] == "high")
    medium = sum(1 for v in violations if v["severity"] == "medium")
    low = sum(1 for v in violations if v["severity"] == "low")
    weighted = high * 3 + medium * 2 + low * 1
    if weighted <= 2:
        return 4
    elif weighted <= 8:
        return 3
    elif weighted <= 20:
        return 2
    else:
        return 1


def format_report(violations, files_checked, lint_score):
    """Format violations as markdown report."""
    lines = []
    lines.append("# Design Token Lint Report")
    lines.append("")
    lines.append(f"**Files checked:** {len(files_checked)}")
    lines.append(f"**Violations:** {len(violations)}")
    lines.append(f"**Score:** {lint_score}/5")
    lines.append("")

    severity_desc = {
        5: "Clean — no violations. Auto-promote to prod.",
        4: "Minor — 1-2 small issues. Auto-promote, hotfix after prod push.",
        3: "Notable — ad-hoc patterns detected. Auto-promote, mandatory hotfix after prod push.",
        2: "Significant — user-visible off-system elements. HOLD prod — Tim reviews, hotfix before promote.",
        1: "Broken — extensive design system violations. HOLD prod — Tim reviews, hotfix before promote.",
    }
    lines.append(f"**Assessment:** {severity_desc.get(lint_score, 'Unknown')}")
    lines.append("")

    if not violations:
        lines.append("No violations found. All templates follow the design token system.")
        return "\n".join(lines)

    # Group by file
    by_file = {}
    for v in violations:
        by_file.setdefault(v["file"], []).append(v)

    lines.append("## Violations by File")
    lines.append("")
    for filepath, file_violations in sorted(by_file.items()):
        lines.append(f"### `{filepath}` ({len(file_violations)} violations)")
        lines.append("")
        for v in file_violations:
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "error": "⚫"}.get(v["severity"], "⚪")
            lines.append(f"- {sev_icon} **Line {v['line']}** [{v['severity']}]: {v['issue']}")
            if v.get("content"):
                lines.append(f"  `{v['content']}`")
        lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    for sev in ["high", "medium", "low"]:
        count = sum(1 for v in violations if v["severity"] == sev)
        if count > 0:
            lines.append(f"| {sev} | {count} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Design token lint for sfpermits.ai templates")
    parser.add_argument("--files", nargs="*", help="Specific files to lint")
    parser.add_argument("--changed", action="store_true", help="Only lint git-changed templates")
    parser.add_argument("--output", default="qa-results/design-lint-results.md", help="Output file path")
    parser.add_argument("--quiet", action="store_true", help="Only print score line")
    args = parser.parse_args()

    if args.files:
        files = args.files
    elif args.changed:
        files = get_changed_templates()
        if not files:
            print("No changed templates found.")
            return
    else:
        files = get_all_templates()

    all_violations = []
    for filepath in files:
        if os.path.exists(filepath):
            all_violations.extend(lint_file(filepath))

    lint_score = score(all_violations)
    report = format_report(all_violations, files, lint_score)

    # Write report
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        f.write(report)

    if args.quiet:
        print(f"Token lint: {lint_score}/5 ({len(all_violations)} violations across {len(files)} files)")
    else:
        print(report)

    # Exit code: 0 always (non-blocking), but print score for CI
    sys.exit(0)


if __name__ == "__main__":
    main()
