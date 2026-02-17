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
# Tier 1: Auto-resolvable detection
# ---------------------------------------------------------------------------

TEST_PATTERNS = re.compile(
    r"\b(test|testing|asdf|hello world|lorem ipsum|xxx|aaa|zzz)\b",
    re.IGNORECASE,
)

# Populated at runtime from admin user list
ADMIN_EMAILS: set[str] = set()


def is_test_submission(item: dict) -> bool:
    """Detect test/junk submissions."""
    msg = item["message"].strip()

    # Very short messages from admin users
    if len(msg) < 10 and item.get("email", "").lower() in ADMIN_EMAILS:
        return True

    # Pattern match for test keywords (only for short messages)
    if TEST_PATTERNS.search(msg) and len(msg) < 50:
        return True

    # Only whitespace/punctuation (no 3+ letter/digit sequences)
    if not re.search(r"[a-zA-Z0-9]{3,}", msg):
        return True

    return False


def _message_similarity(a: str, b: str) -> float:
    """Word-overlap Jaccard similarity ratio."""
    words_a = set(a.lower().split())
    words_b = set(b.lower().split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def _within_days(ts1, ts2, days: int) -> bool:
    """Check if two timestamps are within N days of each other."""
    if not ts1 or not ts2:
        return False
    try:
        if isinstance(ts1, str):
            d1 = datetime.fromisoformat(ts1)
        else:
            d1 = ts1
        if isinstance(ts2, str):
            d2 = datetime.fromisoformat(ts2)
        else:
            d2 = ts2
        if d1.tzinfo is None:
            d1 = d1.replace(tzinfo=timezone.utc)
        if d2.tzinfo is None:
            d2 = d2.replace(tzinfo=timezone.utc)
        return abs((d2 - d1).total_seconds()) < days * 86400
    except (ValueError, TypeError):
        return False


def detect_duplicates(items: list[dict]) -> dict[int, int]:
    """Find duplicate feedback items. Returns {dup_id: original_id}."""
    duplicates: dict[int, int] = {}
    seen_messages: dict[str, int] = {}

    sorted_items = sorted(items, key=lambda x: x.get("created_at") or "")

    for item in sorted_items:
        fid = item["feedback_id"]
        msg_normalized = item["message"].strip().lower()

        # Exact message match
        if msg_normalized in seen_messages:
            duplicates[fid] = seen_messages[msg_normalized]
            continue

        # Same user + same page + high similarity within 7 days
        for prev_item in sorted_items:
            if prev_item["feedback_id"] >= fid:
                break
            if prev_item["feedback_id"] in duplicates:
                continue
            if (prev_item.get("email") == item.get("email")
                    and prev_item.get("page_url") == item.get("page_url")
                    and _message_similarity(prev_item["message"], item["message"]) > 0.8
                    and _within_days(prev_item.get("created_at"), item.get("created_at"), 7)):
                duplicates[fid] = prev_item["feedback_id"]
                break

        if fid not in duplicates:
            seen_messages[msg_normalized] = fid

    return duplicates


def is_already_fixed(item: dict, resolved_items: list[dict]) -> bool:
    """Check if a similar issue was recently resolved."""
    if not item.get("page_url"):
        return False
    for resolved in resolved_items:
        if (resolved.get("page_url") == item["page_url"]
                and resolved.get("feedback_type") == item["feedback_type"]
                and resolved.get("admin_note")
                and any(w in resolved["admin_note"].lower()
                        for w in ("fixed", "deployed", "resolved", "shipped", "patched"))
                and _message_similarity(item["message"], resolved["message"]) > 0.5):
            return True
    return False


# ---------------------------------------------------------------------------
# Actionability classification (Tier 2 vs Tier 3)
# ---------------------------------------------------------------------------

ACTIONABLE_SIGNALS = re.compile(
    r"(steps? to reproduce|when i click|after i|error message|"
    r"expected|actual|screenshot|console|page.*blank|"
    r"button.*not|link.*broken|shows?.*wrong|displays?.*incorrect|"
    r"returns?.*error|status.*code|traceback)",
    re.IGNORECASE,
)


def classify_tier(
    item: dict,
    duplicates: dict[int, int],
    resolved_items: list[dict],
) -> tuple[int, str]:
    """Classify a feedback item into tier 1 (auto-resolve), 2 (actionable), or 3 (needs input)."""
    fid = item["feedback_id"]

    # --- Tier 1: Auto-resolvable ---
    if fid in duplicates:
        return (1, f"Duplicate of #{duplicates[fid]}")
    if is_test_submission(item):
        return (1, "Test/junk submission")
    if is_already_fixed(item, resolved_items):
        return (1, "Issue already fixed in a recent resolution")

    # --- Tier 2: Actionable ---
    if item["feedback_type"] == "bug":
        msg = item["message"]
        has_signals = bool(ACTIONABLE_SIGNALS.search(msg))
        has_page = bool(item.get("page_url"))
        has_screenshot = bool(item.get("has_screenshot"))
        score = sum([has_signals, has_page, has_screenshot])
        if score >= 2:
            return (2, "Bug with clear reproduction context")
        if len(msg) > 100 and has_page:
            return (2, "Detailed bug report with page context")

    if item["feedback_type"] == "suggestion":
        if len(item["message"]) > 50 and item.get("page_url"):
            return (2, "Scoped suggestion with page context")

    # --- Tier 3: Needs human input ---
    if item["feedback_type"] == "question":
        return (3, "Question requiring human answer")

    return (3, "Needs human review")


def auto_resolve_tier1(
    host: str, cron_secret: str, tier1_items: list[dict],
) -> list[dict]:
    """Auto-resolve Tier 1 items via the PATCH API."""
    if not tier1_items:
        return []
    results = []
    for item in tier1_items:
        fid = item["feedback_id"]
        reason = item.get("tier_reason", "Auto-resolved by nightly triage")
        note = f"[Auto-triage] {reason}"
        result = resolve_items(host, cron_secret, [fid], status="resolved", note=note)
        results.extend(result)
    return results


def run_triage(host: str, cron_secret: str) -> dict:
    """Run the full feedback triage pipeline.

    1. Fetch unresolved + recently resolved feedback
    2. Detect duplicates and classify into tiers
    3. Auto-resolve Tier 1 items
    4. Return structured results for the report email
    """
    unresolved_data = fetch_feedback(host, cron_secret,
                                     statuses=["new", "reviewed"], limit=500)
    unresolved = preprocess(unresolved_data["items"])

    resolved_data = fetch_feedback(host, cron_secret,
                                   statuses=["resolved"], limit=100)
    resolved_items = resolved_data["items"]

    duplicates = detect_duplicates(unresolved)

    tier1, tier2, tier3 = [], [], []
    for item in unresolved:
        tier, reason = classify_tier(item, duplicates, resolved_items)
        item["tier"] = tier
        item["tier_reason"] = reason
        if tier == 1:
            tier1.append(item)
        elif tier == 2:
            tier2.append(item)
        else:
            tier3.append(item)

    resolve_results = auto_resolve_tier1(host, cron_secret, tier1)
    ok_count = sum(1 for r in resolve_results if r.get("ok"))

    return {
        "tier1": tier1,
        "tier2": tier2,
        "tier3": tier3,
        "counts": unresolved_data["counts"],
        "auto_resolved": ok_count,
        "auto_resolve_failed": len(tier1) - ok_count,
        "total_triaged": len(unresolved),
    }


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
    "/consultants": "Find a Consultant",
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

def resolve_items(host: str, cron_secret: str, ids: list[int],
                   status: str = "resolved", note: str | None = None,
                   first_reporter: bool = False) -> list[dict]:
    """Mark feedback items as resolved (or other status) via API."""
    results = []
    for fid in ids:
        url = f"https://{host}/api/feedback/{fid}"
        body = {"status": status}
        if note:
            body["admin_note"] = note
        if first_reporter:
            body["first_reporter"] = True
        try:
            resp = httpx.patch(
                url,
                json=body,
                headers={"Authorization": f"Bearer {cron_secret}"},
                timeout=15,
            )
            resp.raise_for_status()
            results.append({"feedback_id": fid, "ok": True, **resp.json()})
        except Exception as e:
            results.append({"feedback_id": fid, "ok": False, "error": str(e)})
    return results


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
    parser.add_argument("--resolve", type=str, default=None,
                        help="Comma-separated feedback IDs to mark resolved (e.g. --resolve 4,5)")
    parser.add_argument("--note", type=str, default=None,
                        help="Admin note when resolving (used with --resolve)")
    parser.add_argument("--status", type=str, default="resolved",
                        choices=["resolved", "reviewed", "wontfix", "new"],
                        help="Status to set when using --resolve (default: resolved)")
    parser.add_argument("--first-reporter", action="store_true",
                        help="Grant first reporter bonus when resolving (used with --resolve)")
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

    # Handle --resolve mode
    if args.resolve:
        try:
            ids = [int(x.strip()) for x in args.resolve.split(",") if x.strip()]
        except ValueError:
            print("Error: --resolve must be comma-separated integers (e.g. --resolve 4,5)", file=sys.stderr)
            sys.exit(1)

        results = resolve_items(host, cron_secret, ids, status=args.status,
                                note=args.note, first_reporter=args.first_reporter)
        for r in results:
            if r["ok"]:
                print(f"  ✓ #{r['feedback_id']} → {r['status']}")
            else:
                print(f"  ✗ #{r['feedback_id']} — {r['error']}")
        ok_count = sum(1 for r in results if r["ok"])
        print(f"\n{ok_count}/{len(results)} items updated.")
        sys.exit(0)

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
