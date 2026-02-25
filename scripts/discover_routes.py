#!/usr/bin/env python3
"""
scripts/discover_routes.py

Parse web/app.py to extract all Flask route definitions and output
siteaudit_manifest.json at the repo root.

Usage:
    python scripts/discover_routes.py
    python scripts/discover_routes.py --output /custom/path/manifest.json
"""

import re
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Matches:  @app.route("/path")  or  @app.route("/path", methods=["GET","POST"])
# The methods group may span the same line or a short continuation — we handle
# multi-line separately in the block-level parser.
ROUTE_RE = re.compile(
    r'@app\.route\(\s*["\']([^"\']+)["\']'
    r'(?:[^)]*?methods\s*=\s*\[([^\]]+)\])?'
)

# Function def immediately after the decorators
FUNC_RE = re.compile(r'^def\s+(\w+)\s*\(')

# render_template call — capture first argument (template filename)
TEMPLATE_RE = re.compile(r'render_template\(\s*["\']([^"\']+)["\']')

# Auth decorators on their own line (Python decorator syntax)
DECORATOR_LOGIN = re.compile(r'@login_required\b')
DECORATOR_ADMIN = re.compile(r'@admin_required\b')

# Inline admin guards inside function bodies — only is_admin checks, not generic abort(403)
# require_admin() call or .get("is_admin") check that's not inside an "if" that loads extra data.
# We use a targeted pattern: a bare "is_admin" guard at the top of the function
# (i.e., "if not g.user.get('is_admin'): abort" pattern)
BODY_ADMIN_GUARD = re.compile(
    r'require_admin\(\)|'
    r'if\s+not\s+g\.user(?:\.get\(["\']is_admin["\']|\[.is_admin.\])|'
    r'if\s+not\s+(?:g\.user\s+or\s+not\s+g\.user\.get\(["\']is_admin["\'])'
)


# ---------------------------------------------------------------------------
# User journeys (static definition)
# ---------------------------------------------------------------------------

USER_JOURNEYS = {
    "property_research": ["/", "/search", "/report/<block>/<lot>"],
    "morning_brief":     ["/brief", "/brief/email-preview"],
    "admin_ops":         ["/admin/dashboard", "/admin/feedback", "/admin/costs"],
    "plan_analysis":     ["/analyze-plans", "/account/analyses", "/account/analyses/compare"],
}


# ---------------------------------------------------------------------------
# Core parser
# ---------------------------------------------------------------------------

def _parse_methods(methods_str: str) -> list[str]:
    """Turn a raw methods string like '"GET", "POST"' into ["GET", "POST"]."""
    if not methods_str:
        return ["GET"]
    return sorted({m.strip().strip('"\'') for m in methods_str.split(",") if m.strip().strip('"\'')}  )


def _classify_auth(path: str, decorator_lines: list[str], body_lines: list[str]) -> str:
    """
    Determine auth level for a route.

    Priority (highest to lowest):
        cron   — path starts with /cron/ or /api/
        admin  — @admin_required decorator  OR  /admin path prefix
                 OR function body has a top-level is_admin guard
                 (only when @login_required is also present)
        auth   — @login_required decorator present
        public — everything else
    """
    # Cron / API — checked first regardless of anything else
    if path.startswith("/cron") or path.startswith("/api/"):
        return "cron"

    dec_text = "\n".join(decorator_lines)
    # Only inspect the first ~20 lines of the body for auth guards
    # (avoids false positives from deep conditional admin feature flags)
    body_head = "\n".join(body_lines[:20])

    has_login_required = bool(DECORATOR_LOGIN.search(dec_text))
    has_admin_required = bool(DECORATOR_ADMIN.search(dec_text))

    # Admin path prefix is the strongest structural signal
    if path.startswith("/admin"):
        return "admin"

    if has_admin_required:
        return "admin"

    # Top-of-body admin guard: "if not g.user.get('is_admin'): abort(403)"
    # This is deliberately narrow to avoid classifying routes that merely
    # *expose extra data* to admins as admin-only.
    if has_login_required and BODY_ADMIN_GUARD.search(body_head):
        return "admin"

    if has_login_required:
        return "auth"

    return "public"


def _extract_template(body_lines: list[str]) -> str | None:
    """Return the first template filename found in render_template() calls."""
    for line in body_lines:
        m = TEMPLATE_RE.search(line)
        if m:
            return m.group(1)
    return None


def parse_app(app_path: Path) -> list[dict]:
    """
    Parse app_path line-by-line, grouping lines into route blocks.

    A block starts at an @app.route decorator and ends just before the next
    @app.route decorator (or end-of-file).  Within each block we capture:
      - The route path and methods (from the @app.route line(s))
      - Any auth decorators between @app.route and the def
      - The function name from the def line
      - The function body (everything after the def line until the next block)
    """
    lines = app_path.read_text(encoding="utf-8").splitlines()
    n = len(lines)

    # Find the line indices of every @app.route
    route_starts = [i for i, ln in enumerate(lines) if ROUTE_RE.search(ln)]

    routes: list[dict] = []

    for idx, start in enumerate(route_starts):
        end = route_starts[idx + 1] if idx + 1 < len(route_starts) else n

        block = lines[start:end]

        # --- Extract path and methods from the @app.route line(s) ---
        # The decorator may span two lines if methods=[...] wraps.
        # Collect up to 3 lines starting at the @app.route to handle wrap.
        route_snippet = " ".join(block[:3])
        m = ROUTE_RE.search(route_snippet)
        if not m:
            continue

        path = m.group(1)
        methods = _parse_methods(m.group(2) or "")

        # --- Separate decorator lines / def / body ---
        # Scan forward through the block until we hit the `def` line.
        decorator_lines: list[str] = []
        func_name: str = "unknown"
        body_lines: list[str] = []
        found_def = False

        for ln in block:
            stripped = ln.strip()
            if not found_def:
                if FUNC_RE.match(stripped):
                    fm = FUNC_RE.match(stripped)
                    func_name = fm.group(1)
                    found_def = True
                else:
                    decorator_lines.append(stripped)
            else:
                body_lines.append(stripped)

        auth_level = _classify_auth(path, decorator_lines, body_lines)
        template = _extract_template(body_lines)

        routes.append({
            "path": path,
            "methods": methods,
            "auth_level": auth_level,
            "template": template,
            "function_name": func_name,
        })

    return routes


# ---------------------------------------------------------------------------
# Manifest assembly
# ---------------------------------------------------------------------------

def build_manifest(routes: list[dict]) -> dict:
    auth_summary: dict[str, int] = {"public": 0, "auth": 0, "admin": 0, "cron": 0}
    for r in routes:
        lvl = r["auth_level"]
        auth_summary[lvl] = auth_summary.get(lvl, 0) + 1

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_routes": len(routes),
        "routes": routes,
        "user_journeys": USER_JOURNEYS,
        "auth_summary": auth_summary,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Generate siteaudit_manifest.json from web/app.py")
    parser.add_argument(
        "--app",
        default=None,
        help="Path to web/app.py (default: auto-detect relative to repo root)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path for manifest JSON (default: siteaudit_manifest.json at repo root)",
    )
    args = parser.parse_args()

    # Resolve paths relative to this script's parent (repo root)
    repo_root = Path(__file__).resolve().parent.parent

    app_path = Path(args.app) if args.app else repo_root / "web" / "app.py"
    output_path = Path(args.output) if args.output else repo_root / "siteaudit_manifest.json"

    if not app_path.exists():
        raise FileNotFoundError(f"app.py not found at {app_path}")

    print(f"Parsing {app_path} ...")
    routes = parse_app(app_path)
    manifest = build_manifest(routes)

    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Written {output_path}")
    print(f"  total_routes : {manifest['total_routes']}")
    print(f"  auth_summary : {manifest['auth_summary']}")


if __name__ == "__main__":
    main()
