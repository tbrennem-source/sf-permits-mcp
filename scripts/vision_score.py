#!/usr/bin/env python3
"""Send dashboard screenshots to Claude Vision for scoring.

Usage:
    # Default: scores existing dashboard-loop screenshots
    python scripts/vision_score.py [round_num]

    # Changed-pages mode: score pages changed since last commit
    python scripts/vision_score.py --changed --url https://staging.example.com --sprint qs10
    python scripts/vision_score.py --changed --url https://... --sprint qs10 --output qa-results/my-scores.json
"""
import anthropic
import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

VISION_PROMPT = """You are a strict web design reviewer. Score this page on an ABSOLUTE scale, not relative to anything else.

RUBRIC:
5/5 EXCELLENT: Content in centered max-width container (~1100px). Glass-morphism cards with rounded corners and subtle borders for each content section. Monospace display font for headings, clean sans-serif for body. Navigation is a clean horizontal bar with no wrapping. Adequate whitespace between sections (24px+). Dark theme with consistent color tokens. Professional, polished, ready for paying customers.

4/5 GOOD: Centered content, cards present, good spacing. Minor issues like slightly inconsistent fonts or one section without a card. Nav works but could be tighter.

3/5 MEDIOCRE: Some centering but inconsistent. Some sections have cards, others are raw. Font usage mixed. Nav functional but crowded. Spacing uneven. Looks like a dev tool, not a product.

2/5 POOR: Content mostly flush-left or full-width. Few or no cards. Nav overflows or wraps. Large unstyled sections. Poor spacing. Looks unfinished.

1/5 BROKEN: No centering, no cards, nav broken, raw HTML, light theme on a dark-theme site, fundamentally unstyled.

CHECK EACH:
1. CENTERING: Is main content in a centered max-width container? Or flush-left/full-width sprawl?
2. NAV: Does nav display on one line without wrapping? Are items reasonably sized?
3. CARDS: Are content sections wrapped in card containers (rounded borders, background, shadow)?
4. TYPOGRAPHY: Monospace headings? Sans-serif body? Consistent sizing hierarchy?
5. SPACING: Adequate gaps between sections? Not cramped?
6. SEARCH BAR: If present, is it styled as a prominent input with rounded corners?
7. RECENT ITEMS: If present, are they styled as cards/chips, not raw text links?
8. ACTION LINKS: If present, are they styled as buttons, not tiny text?

For EACH failing check, describe the SPECIFIC CSS fix needed (property: value).

Return ONLY this JSON:
{"score": N, "checks": {"centering": {"pass": bool, "fix": "css fix or null"}, "nav": {"pass": bool, "fix": "css fix or null"}, "cards": {"pass": bool, "fix": "css fix or null"}, "typography": {"pass": bool, "fix": "css fix or null"}, "spacing": {"pass": bool, "fix": "css fix or null"}, "search_bar": {"pass": bool, "fix": "css fix or null"}, "recent_items": {"pass": bool, "fix": "css fix or null"}, "action_links": {"pass": bool, "fix": "css fix or null"}}, "summary": "one line overall assessment"}"""

# Mapping of template filenames/paths to page slugs.
# Keys: lowercase filename stems or partial paths that git diff --name-only returns.
# Values: page slug from PAGES list in visual_qa.py.
TEMPLATE_TO_PAGE: dict[str, str] = {
    # Public pages
    "landing": "landing",
    "index": "landing",
    "search": "search",
    "login": "login",
    "beta_request": "beta-request",
    "beta-request": "beta-request",
    "property_report": "property-report",
    "property-report": "property-report",
    "report": "property-report",
    # Auth pages
    "account": "account",
    "brief": "brief",
    "portfolio": "portfolio",
    "consultants": "consultants",
    "bottlenecks": "bottlenecks",
    "analyses": "analyses",
    "voice_calibration": "voice-calibration",
    "voice-calibration": "voice-calibration",
    "watch_list": "watch-list",
    "watch-list": "watch-list",
    "watch": "watch-list",
    # Admin pages
    "admin_feedback": "admin-feedback",
    "admin-feedback": "admin-feedback",
    "feedback": "admin-feedback",
    "admin_activity": "admin-activity",
    "admin-activity": "admin-activity",
    "activity": "admin-activity",
    "admin_ops": "admin-ops",
    "admin-ops": "admin-ops",
    "ops": "admin-ops",
    "admin_sources": "admin-sources",
    "admin-sources": "admin-sources",
    "sources": "admin-sources",
    "admin_regulatory": "admin-regulatory",
    "admin-regulatory": "admin-regulatory",
    "regulatory": "admin-regulatory",
    "regulatory_watch": "admin-regulatory",
    "admin_costs": "admin-costs",
    "admin-costs": "admin-costs",
    "costs": "admin-costs",
    "admin_pipeline": "admin-pipeline",
    "admin-pipeline": "admin-pipeline",
    "pipeline": "admin-pipeline",
    "admin_beta": "admin-beta",
    "admin-beta": "admin-beta",
    "beta_requests": "admin-beta",
    "beta-requests": "admin-beta",
}

# All 21 pages from visual_qa.py PAGES list with their paths
PAGES: list[dict] = [
    # --- Public (no auth) ---
    {"slug": "landing", "path": "/", "auth": "public"},
    {"slug": "search", "path": "/search?q=kitchen+remodel&neighborhood=Mission", "auth": "public"},
    {"slug": "login", "path": "/auth/login", "auth": "public"},
    {"slug": "beta-request", "path": "/beta-request", "auth": "public"},
    {"slug": "property-report", "path": "/report/3512/035", "auth": "public"},
    # --- Auth (logged-in user) ---
    {"slug": "account", "path": "/account", "auth": "auth"},
    {"slug": "brief", "path": "/brief", "auth": "auth"},
    {"slug": "portfolio", "path": "/portfolio", "auth": "auth"},
    {"slug": "consultants", "path": "/consultants", "auth": "auth"},
    {"slug": "bottlenecks", "path": "/dashboard/bottlenecks", "auth": "auth"},
    {"slug": "analyses", "path": "/account/analyses", "auth": "auth"},
    {"slug": "voice-calibration", "path": "/account/voice-calibration", "auth": "auth"},
    {"slug": "watch-list", "path": "/watch/list", "auth": "auth"},
    # --- Admin ---
    {"slug": "admin-feedback", "path": "/admin/feedback", "auth": "admin"},
    {"slug": "admin-activity", "path": "/admin/activity", "auth": "admin"},
    {"slug": "admin-ops", "path": "/admin/ops", "auth": "admin"},
    {"slug": "admin-sources", "path": "/admin/sources", "auth": "admin"},
    {"slug": "admin-regulatory", "path": "/admin/regulatory-watch", "auth": "admin"},
    {"slug": "admin-costs", "path": "/admin/costs", "auth": "admin"},
    {"slug": "admin-pipeline", "path": "/admin/pipeline", "auth": "admin"},
    {"slug": "admin-beta", "path": "/admin/beta-requests", "auth": "admin"},
]

# Build slug -> page def for fast lookup
PAGES_BY_SLUG: dict[str, dict] = {p["slug"]: p for p in PAGES}


def score_screenshot(image_path: str, label: str = "") -> dict:
    """Send a screenshot to Claude Vision and return the score.

    Returns a dict with keys: score, checks, summary.
    checks is a dict of dimension -> {pass: bool, fix: str|None}.
    """
    client = anthropic.Anthropic()

    with open(image_path, "rb") as f:
        image_data = base64.standard_b64encode(f.read()).decode("utf-8")

    suffix = f" ({label})" if label else ""
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": image_data,
                        },
                    },
                    {
                        "type": "text",
                        "text": VISION_PROMPT + f"\n\nThis is a screenshot of the authenticated dashboard{suffix}.",
                    },
                ],
            }
        ],
    )

    text = response.content[0].text
    # Try to parse JSON from response
    try:
        # Find JSON in the response
        start = text.index("{")
        end = text.rindex("}") + 1
        result = json.loads(text[start:end])
        return result
    except (ValueError, json.JSONDecodeError):
        print(f"WARNING: Could not parse JSON from Vision response:\n{text}")
        return {"score": 0, "checks": {}, "raw": text}


def get_changed_pages() -> list[str]:
    """Find page slugs for templates changed since last commit."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "--", "web/templates/", "web/static/"],
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
        )
        changed_files = [f for f in result.stdout.strip().split("\n") if f]
    except Exception as e:
        print(f"WARNING: git diff failed: {e}", file=sys.stderr)
        return []

    matched_slugs: list[str] = []
    seen: set[str] = set()

    for filepath in changed_files:
        # Extract the filename stem (without extension)
        stem = Path(filepath).stem.lower().replace("-", "_")
        # Also try the full last component with dashes
        stem_dash = Path(filepath).stem.lower()

        for key in [stem, stem_dash]:
            if key in TEMPLATE_TO_PAGE:
                slug = TEMPLATE_TO_PAGE[key]
                if slug not in seen:
                    seen.add(slug)
                    matched_slugs.append(slug)
                break

    return matched_slugs


def _login_via_test_secret(page, base_url: str, role: str, secret: str) -> bool:
    """Authenticate using the test-login endpoint. Returns True on success."""
    email = f"test-{role}@sfpermits.ai" if role == "admin" else "test-user@sfpermits.ai"
    try:
        resp = page.request.post(
            f"{base_url}/auth/test-login",
            data=json.dumps({"email": email, "secret": secret}),
            headers={"Content-Type": "application/json"},
        )
        return resp.status == 200 or resp.status == 302
    except Exception:
        return False


def take_screenshot(page, url: str, screenshot_path: str) -> bool:
    """Navigate to URL and take a full-page screenshot. Returns True on success."""
    for attempt in range(3):
        try:
            if attempt > 0:
                page.wait_for_timeout(3000)
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(1500)
            page.screenshot(path=screenshot_path, full_page=True)
            return True
        except Exception as e:
            if attempt == 2:
                print(f"WARNING: Navigation failed after 3 attempts for {url}: {e}", file=sys.stderr)
    return False


def append_pending_review(result_entry: dict, pending_reviews_path: str) -> None:
    """Append a low-scoring result to the pending-reviews.json file."""
    path = Path(pending_reviews_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing entries or initialize
    if path.exists():
        try:
            with open(path) as f:
                entries = json.load(f)
        except (json.JSONDecodeError, IOError):
            entries = []
    else:
        entries = []

    entries.append(result_entry)

    with open(path, "w") as f:
        json.dump(entries, f, indent=2)


def run_changed_mode(args) -> int:
    """Score pages changed since last commit using Playwright screenshots."""
    from playwright.sync_api import sync_playwright

    base_url = args.url.rstrip("/")
    sprint = args.sprint or "latest"
    output_path = args.output or "qa-results/vision-scores-latest.json"
    pending_reviews_path = "qa-results/pending-reviews.json"
    test_secret = os.environ.get("TEST_LOGIN_SECRET", "")

    # Find changed page slugs
    changed_slugs = get_changed_pages()
    if not changed_slugs:
        print("No changed templates matched to known pages.")
        return 0

    print(f"Changed pages detected: {', '.join(changed_slugs)}")

    # Prepare screenshot directory
    screenshots_dir = Path("qa-results") / "screenshots" / sprint
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    all_results: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)

        # Determine max auth level needed
        pages_to_score = [PAGES_BY_SLUG[s] for s in changed_slugs if s in PAGES_BY_SLUG]
        needs_admin = any(p["auth"] == "admin" for p in pages_to_score)
        needs_auth = needs_admin or any(p["auth"] == "auth" for p in pages_to_score)

        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = context.new_page()

        # Login if needed
        logged_in = False
        if needs_auth and test_secret:
            role = "admin" if needs_admin else "user"
            logged_in = _login_via_test_secret(page, base_url, role, test_secret)
            if not logged_in:
                print("WARNING: Login failed — auth/admin pages will be skipped", file=sys.stderr)

        for page_def in pages_to_score:
            slug = page_def["slug"]
            auth_level = page_def["auth"]
            url = f"{base_url}{page_def['path']}"
            screenshot_path = str(screenshots_dir / f"{slug}-desktop.png")

            if auth_level in ("auth", "admin") and not logged_in:
                print(f"  SKIP {slug}: auth required but not logged in")
                continue

            print(f"  Scoring {slug} ({url})...")
            nav_ok = take_screenshot(page, url, screenshot_path)

            if not nav_ok:
                print(f"  FAIL {slug}: could not navigate")
                continue

            result = score_screenshot(screenshot_path, label=slug)
            score_val = result.get("score", 0)
            checks = result.get("checks", {})
            summary = result.get("summary", "")

            # Count passing dimensions
            passing = sum(1 for v in checks.values() if isinstance(v, dict) and v.get("pass"))
            total_dims = len(checks)

            result_entry = {
                "page": slug,
                "url": url,
                "score": score_val,
                "checks": checks,
                "summary": summary,
                "screenshot": screenshot_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            all_results.append(result_entry)

            # Append to pending-reviews.json if score < 3.0
            if score_val < 3.0:
                append_pending_review(result_entry, pending_reviews_path)
                action = "FLAGGED (score < 3.0)"
            else:
                action = "OK"

            print(f"  {slug}: {score_val}/5 | {passing}/{total_dims} dimensions passing | {action}")

        page.close()
        context.close()
        browser.close()

    # Print summary table
    print("\n--- Vision Score Summary ---")
    print(f"{'Page':<25} {'Score':<8} {'Dims Pass':<12} {'Action'}")
    print("-" * 65)
    for r in all_results:
        checks = r.get("checks", {})
        passing = sum(1 for v in checks.values() if isinstance(v, dict) and v.get("pass"))
        total_dims = len(checks)
        action = "FLAGGED" if r["score"] < 3.0 else "OK"
        print(f"{r['page']:<25} {r['score']:<8} {passing}/{total_dims:<11} {action}")

    # Write output JSON
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to {output_path}")

    flagged = [r for r in all_results if r["score"] < 3.0]
    if flagged:
        print(f"{len(flagged)} page(s) flagged in {pending_reviews_path}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score screenshots with Claude Vision",
    )
    parser.add_argument("--changed", action="store_true", help="Score git-changed pages (requires --url)")
    parser.add_argument("--url", help="Base URL (e.g. https://sfpermits-ai-staging-production.up.railway.app)")
    parser.add_argument("--sprint", help="Sprint label for screenshot filenames (e.g. qs10)")
    parser.add_argument("--output", help="Path for per-run JSON results (default: qa-results/vision-scores-latest.json)")

    # Allow positional round_num for legacy mode
    parser.add_argument("round_num", nargs="?", type=int, default=None, help="Round number for legacy dashboard-loop mode")

    args = parser.parse_args()

    if args.changed:
        if not args.url:
            print("ERROR: --changed requires --url", file=sys.stderr)
            return 1
        return run_changed_mode(args)

    # Legacy mode: score dashboard-loop screenshots
    screenshot_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "qa-results", "screenshots", "dashboard-loop"
    )

    round_num = args.round_num if args.round_num is not None else 1

    results = {}
    for variant in ["desktop", "mobile"]:
        path = os.path.join(screenshot_dir, f"round-{round_num}-{variant}.png")
        if os.path.exists(path):
            print(f"\n--- Scoring round-{round_num}-{variant}.png ---")
            result = score_screenshot(path, label=f"round {round_num}, {variant}")
            results[variant] = result
            print(json.dumps(result, indent=2))
        else:
            print(f"SKIP: {path} not found")

    # Write results to file
    results_path = os.path.join(screenshot_dir, f"round-{round_num}-scores.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nScores saved to {results_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
