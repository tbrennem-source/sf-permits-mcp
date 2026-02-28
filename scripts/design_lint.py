#!/usr/bin/env python3
"""Design token lint — verify templates use the design system.

Non-blocking. Produces a report for post-sprint review.
Run: python scripts/design_lint.py [--files path1 path2 ...]
     python scripts/design_lint.py --changed   # only git-changed templates
     python scripts/design_lint.py             # all templates
     python scripts/design_lint.py --live --url https://staging.example.com

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

# --- Live check: token variable → expected hex color mapping ---
# Maps CSS custom property name to expected resolved hex color (from DESIGN_TOKENS.md §1)
# Used by --live mode to verify computed colors on rendered pages.
ALLOWED_TOKENS_VARS = {
    "--accent":          "#5eead4",   # teal brand color
    "--signal-green":    "#34d399",   # on track / success
    "--signal-amber":    "#fbbf24",   # warning / stalled
    "--signal-red":      "#f87171",   # alert / violation
    "--signal-blue":     "#60a5fa",   # informational / premium
    "--dot-green":       "#22c55e",   # status dot green
    "--dot-amber":       "#f59e0b",   # status dot amber
    "--dot-red":         "#ef4444",   # status dot red
    "--obsidian":        "#0a0a0f",   # page background
    "--obsidian-mid":    "#12121a",   # card/surface background
    "--obsidian-light":  "#1a1a26",   # elevated elements
}

# Pages to check in --live mode (public only by default; auth pages added if TEST_LOGIN_SECRET set)
LIVE_PUBLIC_PAGES = [
    {"slug": "landing", "path": "/", "auth": "public"},
    {"slug": "search", "path": "/search?q=kitchen+remodel", "auth": "public"},
    {"slug": "login", "path": "/auth/login", "auth": "public"},
    {"slug": "beta-request", "path": "/beta-request", "auth": "public"},
    {"slug": "property-report", "path": "/report/3512/035", "auth": "public"},
]

LIVE_AUTH_PAGES = [
    {"slug": "account", "path": "/account", "auth": "auth"},
    {"slug": "brief", "path": "/brief", "auth": "auth"},
    {"slug": "portfolio", "path": "/portfolio", "auth": "auth"},
]

AXE_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"


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


def check_missing_csrf(filepath, content, lines):
    """Find POST forms missing a csrf_token hidden input."""
    violations = []
    for m in re.finditer(r'<form\b([^>]*)>', content, re.IGNORECASE):
        attrs = m.group(1)
        if not re.search(r'method=["\']?post', attrs, re.IGNORECASE):
            continue
        end_tag = content.find('</form>', m.end())
        form_body = content[m.end():end_tag] if end_tag != -1 else content[m.end():m.end() + 2000]
        if 'csrf_token' in form_body:
            continue
        line_num = content[:m.start()].count('\n') + 1
        action_match = re.search(r'action=["\']([^"\']+)["\']', attrs)
        action = action_match.group(1) if action_match else "(no action)"
        violations.append({
            "file": filepath,
            "line": line_num,
            "issue": f"POST form missing csrf_token: action={action}",
            "content": lines[line_num - 1].strip()[:120] if line_num <= len(lines) else "",
            "severity": "high",
        })
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
    violations.extend(check_missing_csrf(filepath, content, lines))
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


# --- Live checks (Playwright-based) ---

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int] | None:
    """Parse '#rrggbb' or '#rgb' hex string to (r, g, b) tuple. Returns None on failure."""
    hex_color = hex_color.strip().lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    if len(hex_color) != 6:
        return None
    try:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except ValueError:
        return None


def _parse_computed_color(computed: str) -> tuple[int, int, int] | None:
    """Parse 'rgb(r, g, b)' or 'rgba(r, g, b, a)' string returned by getComputedStyle."""
    m = re.match(r"rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)", computed)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def _rgb_within_tolerance(a: tuple[int, int, int], b: tuple[int, int, int], tolerance: int = 2) -> bool:
    """Return True if all channels differ by at most `tolerance`."""
    return all(abs(a[i] - b[i]) <= tolerance for i in range(3))


def check_computed_colors(page, url: str) -> list[dict]:
    """
    Verify that computed foreground/background colors on representative elements
    match expected token hex values (within ±2 RGB per channel).
    """
    violations = []
    js = """
    () => {
        const results = [];
        const checks = [
            // [selector, property, token_var]
            ['body', 'backgroundColor', '--obsidian'],
            ['.glass-card', 'backgroundColor', '--obsidian-mid'],
            ['a.ghost-cta', 'color', '--accent'],
            ['.signal-green, .status-text--green', 'color', '--signal-green'],
            ['.status-dot--green', 'backgroundColor', '--dot-green'],
        ];
        for (const [sel, prop, tokenVar] of checks) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const computed = window.getComputedStyle(el)[prop];
            results.push({selector: sel, property: prop, tokenVar: tokenVar, computed: computed});
        }
        return results;
    }
    """
    try:
        elements = page.evaluate(js)
    except Exception as e:
        violations.append({
            "file": url,
            "line": 0,
            "issue": f"check_computed_colors JS error: {e}",
            "content": "",
            "severity": "medium",
        })
        return violations

    for item in elements:
        token_var = item.get("tokenVar", "")
        expected_hex = ALLOWED_TOKENS_VARS.get(token_var)
        if not expected_hex:
            continue
        computed_str = item.get("computed", "")
        computed_rgb = _parse_computed_color(computed_str)
        expected_rgb = _hex_to_rgb(expected_hex)
        if computed_rgb is None or expected_rgb is None:
            continue
        if not _rgb_within_tolerance(computed_rgb, expected_rgb):
            violations.append({
                "file": url,
                "line": 0,
                "issue": (
                    f"Computed color mismatch on '{item['selector']}' "
                    f"(property: {item['property']}): "
                    f"got {computed_str}, expected {expected_hex} ({token_var})"
                ),
                "content": "",
                "severity": "medium",
            })
    return violations


def check_computed_fonts(page, url: str) -> list[dict]:
    """
    Verify computed font families:
    - .obs-table elements must resolve to monospace
    - p, .insight__body elements must resolve to sans-serif
    """
    violations = []
    js = """
    () => {
        const results = [];
        const monoChecks = ['.obs-table', '.obs-table__mono'];
        const sansChecks = ['p', '.insight__body'];
        for (const sel of monoChecks) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const ff = window.getComputedStyle(el).fontFamily.toLowerCase();
            results.push({selector: sel, fontFamily: ff, expected: 'mono'});
        }
        for (const sel of sansChecks) {
            const el = document.querySelector(sel);
            if (!el) continue;
            const ff = window.getComputedStyle(el).fontFamily.toLowerCase();
            results.push({selector: sel, fontFamily: ff, expected: 'sans'});
        }
        return results;
    }
    """
    try:
        elements = page.evaluate(js)
    except Exception as e:
        violations.append({
            "file": url,
            "line": 0,
            "issue": f"check_computed_fonts JS error: {e}",
            "content": "",
            "severity": "medium",
        })
        return violations

    MONO_SIGNALS = ["mono", "courier", "consolas", "jetbrains", "cascadia", "ui-monospace"]
    SANS_SIGNALS = ["sans", "inter", "system-ui", "ibm plex", "-apple-system", "blinkmacsystemfont", "segoe"]

    for item in elements:
        ff = item.get("fontFamily", "").lower()
        expected = item.get("expected", "")
        sel = item.get("selector", "")
        if expected == "mono":
            if not any(sig in ff for sig in MONO_SIGNALS):
                violations.append({
                    "file": url,
                    "line": 0,
                    "issue": (
                        f"Font compliance: '{sel}' expected monospace but got: {ff[:80]}"
                    ),
                    "content": "",
                    "severity": "medium",
                })
        elif expected == "sans":
            if not any(sig in ff for sig in SANS_SIGNALS):
                violations.append({
                    "file": url,
                    "line": 0,
                    "issue": (
                        f"Font compliance: '{sel}' expected sans-serif but got: {ff[:80]}"
                    ),
                    "content": "",
                    "severity": "medium",
                })
    return violations


def check_axe_contrast(page, url: str) -> list[dict]:
    """
    Inject axe-core and run WCAG AA color-contrast checks.
    Each axe violation is reported as high severity.
    """
    violations = []
    try:
        page.add_script_tag(url=AXE_CDN_URL)
        # Wait for axe to be available
        page.wait_for_function("typeof axe !== 'undefined'", timeout=10000)
    except Exception as e:
        violations.append({
            "file": url,
            "line": 0,
            "issue": f"axe-core load failed: {e}",
            "content": "",
            "severity": "medium",
        })
        return violations

    js = """
    async () => {
        const result = await axe.run({runOnly: ['color-contrast']});
        return result.violations.map(v => ({
            id: v.id,
            description: v.description,
            nodes: v.nodes.map(n => ({
                target: n.target.join(', '),
                failureSummary: n.failureSummary
            }))
        }));
    }
    """
    try:
        axe_violations = page.evaluate(js)
    except Exception as e:
        violations.append({
            "file": url,
            "line": 0,
            "issue": f"axe.run() failed: {e}",
            "content": "",
            "severity": "medium",
        })
        return violations

    for v in axe_violations:
        for node in v.get("nodes", []):
            target = node.get("target", "")
            summary = node.get("failureSummary", "")[:200]
            violations.append({
                "file": url,
                "line": 0,
                "issue": f"axe WCAG AA contrast violation on '{target}': {summary}",
                "content": "",
                "severity": "high",
            })
    return violations


def check_viewport_overflow(page, url: str) -> list[dict]:
    """
    Check for horizontal scroll (layout breakage).
    scrollWidth > window.innerWidth indicates overflow.
    """
    violations = []
    js = """
    () => ({
        scrollWidth: document.documentElement.scrollWidth,
        innerWidth: window.innerWidth
    })
    """
    try:
        result = page.evaluate(js)
        scroll_w = result.get("scrollWidth", 0)
        inner_w = result.get("innerWidth", 0)
        if scroll_w > inner_w:
            violations.append({
                "file": url,
                "line": 0,
                "issue": (
                    f"Viewport overflow (horizontal scroll): "
                    f"scrollWidth={scroll_w}px > innerWidth={inner_w}px"
                ),
                "content": "",
                "severity": "medium",
            })
    except Exception as e:
        violations.append({
            "file": url,
            "line": 0,
            "issue": f"check_viewport_overflow JS error: {e}",
            "content": "",
            "severity": "medium",
        })
    return violations


def run_live_checks(base_url: str, pages: list[dict], test_secret: str | None = None) -> list[dict]:
    """
    Launch headless Chromium via Playwright and run live CSS checks on each page.
    Returns a flat list of violation dicts (same schema as static check violations).
    """
    # Conditional import — only needed for --live mode
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [{
            "file": base_url,
            "line": 0,
            "issue": "Playwright not installed. Run: pip install playwright && playwright install chromium",
            "content": "",
            "severity": "error",
        }]

    all_violations = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        for page_def in pages:
            page_url = base_url.rstrip("/") + page_def["path"]
            context = browser.new_context(viewport={"width": 1440, "height": 900})

            # If auth page and test_secret provided, inject auth cookie / header
            if page_def.get("auth") == "auth" and test_secret:
                # Use auth test-login endpoint if available (matches web/routes_auth.py pattern)
                try:
                    auth_page = context.new_page()
                    auth_page.goto(
                        base_url.rstrip("/") + f"/auth/test-login?secret={test_secret}",
                        wait_until="networkidle",
                        timeout=15000,
                    )
                    auth_page.close()
                except Exception:
                    pass  # Auth page check continues even if test login fails

            page = context.new_page()
            print(f"  [live] Checking {page_url} ...", file=sys.stderr)

            try:
                page.goto(page_url, wait_until="networkidle", timeout=30000)
            except Exception as e:
                all_violations.append({
                    "file": page_url,
                    "line": 0,
                    "issue": f"Page load failed: {e}",
                    "content": "",
                    "severity": "medium",
                })
                page.close()
                context.close()
                continue

            all_violations.extend(check_computed_colors(page, page_url))
            all_violations.extend(check_computed_fonts(page, page_url))
            all_violations.extend(check_axe_contrast(page, page_url))
            all_violations.extend(check_viewport_overflow(page, page_url))

            page.close()
            context.close()

        browser.close()

    return all_violations


def format_live_report(static_violations, live_violations, static_files, live_pages, combined_score):
    """Format combined static + live violations as a markdown report."""
    lines = []
    lines.append("# Design Token Lint Report — Live + Static")
    lines.append("")
    lines.append(f"**Static files checked:** {len(static_files)}")
    lines.append(f"**Live pages checked:** {len(live_pages)}")
    lines.append(f"**Static violations:** {len(static_violations)}")
    lines.append(f"**Live violations:** {len(live_violations)}")
    lines.append(f"**Combined Score:** {combined_score}/5")
    lines.append("")

    severity_desc = {
        5: "Clean — no violations. Auto-promote to prod.",
        4: "Minor — 1-2 small issues. Auto-promote, hotfix after prod push.",
        3: "Notable — ad-hoc patterns detected. Auto-promote, mandatory hotfix after prod push.",
        2: "Significant — user-visible off-system elements. HOLD prod — Tim reviews, hotfix before promote.",
        1: "Broken — extensive design system violations. HOLD prod — Tim reviews, hotfix before promote.",
    }
    lines.append(f"**Assessment:** {severity_desc.get(combined_score, 'Unknown')}")
    lines.append("")

    all_violations = static_violations + live_violations
    if not all_violations:
        lines.append("No violations found.")
        return "\n".join(lines)

    # Static section
    if static_violations:
        lines.append("## Static Analysis Violations")
        lines.append("")
        by_file = {}
        for v in static_violations:
            by_file.setdefault(v["file"], []).append(v)
        for filepath, file_violations in sorted(by_file.items()):
            lines.append(f"### `{filepath}` ({len(file_violations)} violations)")
            lines.append("")
            for v in file_violations:
                sev_icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "error": "⚫"}.get(v["severity"], "⚪")
                lines.append(f"- {sev_icon} **Line {v['line']}** [{v['severity']}]: {v['issue']}")
                if v.get("content"):
                    lines.append(f"  `{v['content']}`")
            lines.append("")

    # Live section
    if live_violations:
        lines.append("## Live Computed CSS Violations")
        lines.append("")
        by_url = {}
        for v in live_violations:
            by_url.setdefault(v["file"], []).append(v)
        for url, url_violations in sorted(by_url.items()):
            lines.append(f"### `{url}` ({len(url_violations)} violations)")
            lines.append("")
            for v in url_violations:
                sev_icon = {"high": "🔴", "medium": "🟡", "low": "🔵", "error": "⚫"}.get(v["severity"], "⚪")
                lines.append(f"- {sev_icon} [{v['severity']}]: {v['issue']}")
            lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append("| Severity | Static | Live | Total |")
    lines.append("|----------|--------|------|-------|")
    for sev in ["high", "medium", "low"]:
        s_count = sum(1 for v in static_violations if v["severity"] == sev)
        l_count = sum(1 for v in live_violations if v["severity"] == sev)
        if s_count + l_count > 0:
            lines.append(f"| {sev} | {s_count} | {l_count} | {s_count + l_count} |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Design token lint for sfpermits.ai templates")
    parser.add_argument("--files", nargs="*", help="Specific files to lint")
    parser.add_argument("--changed", action="store_true", help="Only lint git-changed templates")
    parser.add_argument("--output", default="qa-results/design-lint-results.md", help="Output file path")
    parser.add_argument("--quiet", action="store_true", help="Only print score line")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live Playwright checks (computed CSS, axe-core WCAG AA contrast, viewport overflow). Requires --url.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Base URL for --live mode (e.g. https://sfpermits-ai-staging-production.up.railway.app)",
    )
    args = parser.parse_args()

    if args.live and not args.url:
        parser.error("--live requires --url (e.g. --url https://staging.example.com)")

    # --- Static checks (always run) ---
    if args.files:
        files = args.files
    elif args.changed:
        files = get_changed_templates()
        if not files and not args.live:
            print("No changed templates found.")
            return
    else:
        files = get_all_templates()

    static_violations = []
    for filepath in files:
        if os.path.exists(filepath):
            static_violations.extend(lint_file(filepath))

    if not args.live:
        # Static-only path (original behavior)
        lint_score = score(static_violations)
        report = format_report(static_violations, files, lint_score)

        output_path = args.output
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(report)

        if args.quiet:
            print(f"Token lint: {lint_score}/5 ({len(static_violations)} violations across {len(files)} files)")
        else:
            print(report)

        sys.exit(0)

    # --- Live path ---
    test_secret = os.environ.get("TEST_LOGIN_SECRET")
    pages_to_check = list(LIVE_PUBLIC_PAGES)
    if test_secret:
        pages_to_check.extend(LIVE_AUTH_PAGES)

    print(f"Running live checks on {len(pages_to_check)} pages at {args.url} ...", file=sys.stderr)
    live_violations = run_live_checks(args.url, pages_to_check, test_secret)

    all_violations = static_violations + live_violations
    combined_score = score(all_violations)

    output_path = args.output if args.output != "qa-results/design-lint-results.md" else "qa-results/design-lint-live-results.md"
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

    report = format_live_report(static_violations, live_violations, files, pages_to_check, combined_score)
    with open(output_path, "w") as f:
        f.write(report)

    if args.quiet:
        print(
            f"Token lint (live): {combined_score}/5 "
            f"(static: {len(static_violations)}, live: {len(live_violations)} violations)"
        )
    else:
        print(report)

    sys.exit(0)


if __name__ == "__main__":
    main()
