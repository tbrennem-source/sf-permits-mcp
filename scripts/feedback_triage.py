"""Fetch and pre-process unresolved feedback for triage.

Usage:
    # Via railway run (picks up CRON_SECRET + RAILWAY_PUBLIC_DOMAIN from env)
    railway run -- python -m scripts.feedback_triage

    # With explicit env vars
    CRON_SECRET=xxx python -m scripts.feedback_triage --host sfpermits-ai-production.up.railway.app

    # Filter to bugs only
    railway run -- python -m scripts.feedback_triage --type bug

    # Include resolved items
    railway run -- python -m scripts.feedback_triage --all
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("httpx is required: pip install httpx", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

HIGH_KEYWORDS = re.compile(
    r"\b(broken|crash|crashes|error|fail|500|404|can'?t|cannot|doesn'?t work|"
    r"not working|blank|empty|missing|wrong|stuck|infinite|loop|hang)\b",
    re.IGNORECASE,
)

LOW_KEYWORDS = re.compile(
    r"\b(would be nice|suggestion|idea|maybe|could you|feature request|"
    r"nice to have|consider|wish|someday)\b",
    re.IGNORECASE,
)


def classify_severity(item: dict) -> str:
    """Classify feedback severity as HIGH, NORMAL, or LOW."""
    # All bugs start at NORMAL, suggestions/questions start at LOW
    if item["feedback_type"] == "bug":
        base = "NORMAL"
    else:
        base = "LOW"

    msg = item["message"]

    if HIGH_KEYWORDS.search(msg):
        return "HIGH"

    if LOW_KEYWORDS.search(msg):
        return "LOW"

    return base


# ---------------------------------------------------------------------------
# Page area extraction
# ---------------------------------------------------------------------------

PAGE_AREAS = {
    "/analyze": "Search/Analyze",
    "/ask": "Ask AI",
    "/report": "Property Report",
    "/brief": "Morning Brief",
    "/account": "Account",
    "/admin": "Admin",
    "/auth": "Auth",
    "/expediter": "Find Expediter",
}


def extract_page_area(page_url: str | None) -> str:
    """Extract feature area from page URL."""
    if not page_url:
        return "Unknown"
    path = urlparse(page_url).path
    for prefix, area in PAGE_AREAS.items():
        if path.startswith(prefix):
            return area
    if path == "/" or path == "":
        return "Home"
    return path


# ---------------------------------------------------------------------------
# Age formatting
# ---------------------------------------------------------------------------

def format_age(iso_timestamp: str | None) -> str:
    """Format timestamp as relative age string."""
    if not iso_timestamp:
        return "unknown"
    try:
        created = datetime.fromisoformat(iso_timestamp)
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - created
        seconds = delta.total_seconds()

        if seconds < 3600:
            mins = max(1, int(seconds / 60))
            return f"{mins}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        else:
            days = int(seconds / 86400)
            return f"{days}d ago"
    except (ValueError, TypeError):
        return "unknown"


# ---------------------------------------------------------------------------
# Fetch from API
# ---------------------------------------------------------------------------

def fetch_feedback(host: str, cron_secret: str, statuses: list[str],
                   limit: int = 100) -> dict:
    """Fetch feedback from the production API."""
    url = f"https://{host}/api/feedback"
    params = [("limit", str(limit))]
    for s in statuses:
        params.append(("status", s))

    resp = httpx.get(
        url,
        params=params,
        headers={"Authorization": f"Bearer {cron_secret}"},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Pre-process and format
# ---------------------------------------------------------------------------

def preprocess(items: list[dict], type_filter: str | None = None) -> list[dict]:
    """Enrich each item with severity, page area, and age."""
    result = []
    for item in items:
        if type_filter and item["feedback_type"] != type_filter:
            continue
        item["severity"] = classify_severity(item)
        item["page_area"] = extract_page_area(item["page_url"])
        item["age"] = format_age(item["created_at"])
        result.append(item)
    return result


def format_triage_report(items: list[dict], counts: dict) -> str:
    """Format enriched items into a triage report string."""
    if not items:
        unresolved = counts.get("new", 0) + counts.get("reviewed", 0)
        return f"No unresolved feedback items. (Total: {counts.get('total', 0)}, Resolved: {counts.get('resolved', 0)})"

    lines = [f"=== Feedback Triage: {len(items)} unresolved items ==="]
    lines.append(
        f"    Counts: {counts.get('new', 0)} new, "
        f"{counts.get('reviewed', 0)} reviewed, "
        f"{counts.get('resolved', 0)} resolved, "
        f"{counts.get('wontfix', 0)} won't-fix"
    )
    lines.append("")

    # Group by severity
    groups = {"HIGH": [], "NORMAL": [], "LOW": []}
    for item in items:
        groups[item["severity"]].append(item)

    for severity in ("HIGH", "NORMAL", "LOW"):
        group = groups[severity]
        if not group:
            continue

        lines.append(f"{severity} PRIORITY ({len(group)})")
        for item in group:
            fid = item["feedback_id"]
            ftype = item["feedback_type"]
            age = item["age"]
            # Truncate message for summary line
            msg_short = item["message"][:80].replace("\n", " ")
            if len(item["message"]) > 80:
                msg_short += "..."
            lines.append(f"  #{fid} [{ftype}] {age} — {msg_short}")

            # Detail line
            parts = [f"Page: {item['page_area']}"]
            parts.append(item.get("email") or "Anonymous")
            if item["has_screenshot"]:
                parts.append("Screenshot attached")
            if item["status"] == "reviewed":
                parts.append("Status: reviewed")
            lines.append(f"      {' | '.join(parts)}")

            if item.get("admin_note"):
                lines.append(f"      Admin note: {item['admin_note']}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Fetch and triage feedback from production")
    parser.add_argument("--host", default=None,
                        help="Production hostname (default: from RAILWAY_PUBLIC_DOMAIN env)")
    parser.add_argument("--type", dest="feedback_type", choices=["bug", "suggestion", "question"],
                        help="Filter by feedback type")
    parser.add_argument("--all", action="store_true",
                        help="Include resolved and wontfix items")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON instead of formatted report")
    parser.add_argument("--limit", type=int, default=100,
                        help="Max items to fetch (default: 100)")
    args = parser.parse_args()

    # Resolve host
    host = args.host or os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not host:
        print("Error: No host specified. Use --host or set RAILWAY_PUBLIC_DOMAIN", file=sys.stderr)
        sys.exit(1)

    # Resolve secret
    cron_secret = os.environ.get("CRON_SECRET", "")
    if not cron_secret:
        print("Error: CRON_SECRET not set in environment", file=sys.stderr)
        sys.exit(1)

    # Determine which statuses to fetch
    if args.all:
        statuses = []  # all
    else:
        statuses = ["new", "reviewed"]

    try:
        data = fetch_feedback(host, cron_secret, statuses, limit=args.limit)
    except httpx.HTTPStatusError as e:
        print(f"Error: API returned {e.response.status_code}", file=sys.stderr)
        sys.exit(1)
    except httpx.ConnectError:
        print(f"Error: Could not connect to {host}", file=sys.stderr)
        sys.exit(1)

    items = preprocess(data["items"], type_filter=args.feedback_type)

    if args.json:
        print(json.dumps({"items": items, "counts": data["counts"]}, indent=2))
    else:
        report = format_triage_report(items, data["counts"])
        print(report)


if __name__ == "__main__":
    main()
