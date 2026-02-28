#!/usr/bin/env python3
"""Seed a user account with demo data for Zoom presentations and QA demos.

Usage:
    python scripts/seed_demo.py --email tbrennem@gmail.com
    python scripts/seed_demo.py --email tbrennem@gmail.com --dry-run

This script is IDEMPOTENT — safe to run multiple times. It will:
  1. Find or confirm the user exists (creates if missing)
  2. Add 3 watch items for canonical demo parcels (skip if already watching)
  3. Add 5 recent searches to activity_log (always appends new ones)
  4. Print a summary of what was created vs. skipped

Demo parcels:
  - 1455 Market St   Block 3507 / Lot 004  (South of Market — rich data)
  - 146 Lake St      Block 1386 / Lot 025  (Richmond — typical residential)
  - 125 Mason St     Block 0312 / Lot 005  (Tenderloin — mixed-use)

Requirements:
  - Activate the project venv first: source .venv/bin/activate
  - Set DATABASE_URL env var for Postgres, or rely on local DuckDB fallback
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path regardless of where script is called from
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

# ── Demo data constants ───────────────────────────────────────────────────────

DEMO_WATCHES = [
    {
        "label": "1455 Market St — Demo (SoMa)",
        "watch_type": "address",
        "street_number": "1455",
        "street_name": "MARKET",
        "block": "3507",
        "lot": "004",
        "neighborhood": "South of Market",
    },
    {
        "label": "146 Lake St — Demo (Richmond)",
        "watch_type": "address",
        "street_number": "146",
        "street_name": "LAKE",
        "block": "1386",
        "lot": "025",
        "neighborhood": "Inner Richmond",
    },
    {
        "label": "125 Mason St — Demo (Tenderloin)",
        "watch_type": "address",
        "street_number": "125",
        "street_name": "MASON",
        "block": "0312",
        "lot": "005",
        "neighborhood": "Tenderloin",
    },
]

DEMO_SEARCHES = [
    "1455 Market St permits",
    "kitchen remodel do I need a permit",
    "ADU accessory dwelling unit SF requirements",
    "146 Lake St property report",
    "how long does a building permit take in San Francisco",
]


# ── Core logic ────────────────────────────────────────────────────────────────

def find_or_create_user(email: str, dry_run: bool = False) -> dict:
    """Find user by email, or create if missing. Returns user dict."""
    from web.auth import get_user_by_email, create_user

    user = get_user_by_email(email)
    if user:
        print(f"  [FOUND]   User {email!r} exists (user_id={user['user_id']})")
        return user

    if dry_run:
        print(f"  [DRY-RUN] Would create user {email!r}")
        return {"user_id": 0, "email": email}

    print(f"  [CREATE]  Creating user {email!r} ...")
    user = create_user(email, referral_source="demo_seed")
    print(f"  [OK]      Created user_id={user['user_id']}")
    return user


def seed_watch_items(user: dict, dry_run: bool = False) -> dict:
    """Add demo watch items if not already watching. Returns counts."""
    from web.auth import add_watch, check_watch

    user_id = user["user_id"]
    added = 0
    skipped = 0

    for watch in DEMO_WATCHES:
        label = watch["label"]
        kwargs = {k: v for k, v in watch.items() if k != "label"}
        watch_type = kwargs.pop("watch_type")

        existing = check_watch(
            user_id,
            watch_type,
            street_number=kwargs.get("street_number"),
            street_name=kwargs.get("street_name"),
            block=kwargs.get("block"),
            lot=kwargs.get("lot"),
        )

        if existing:
            print(f"  [SKIP]    Already watching: {label}")
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY-RUN] Would add watch: {label}")
            added += 1
            continue

        add_watch(user_id, watch_type, label=label, **kwargs)
        print(f"  [ADD]     Added watch: {label}")
        added += 1

    return {"added": added, "skipped": skipped}


def seed_recent_searches(user: dict, dry_run: bool = False) -> int:
    """Add demo recent searches to activity_log. Returns count added."""
    from src.db import BACKEND, get_connection

    user_id = user["user_id"]
    now = datetime.now(timezone.utc).isoformat()
    added = 0

    if dry_run:
        print(f"  [DRY-RUN] Would add {len(DEMO_SEARCHES)} recent searches")
        return len(DEMO_SEARCHES)

    conn = get_connection()
    try:
        for i, query_text in enumerate(DEMO_SEARCHES):
            try:
                if BACKEND == "postgres":
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO activity_log "
                            "(user_id, action, detail, created_at) "
                            "VALUES (%s, %s, %s, %s)",
                            (user_id, "search", query_text, now),
                        )
                    conn.commit()
                else:
                    conn.execute(
                        "INSERT INTO activity_log "
                        "(user_id, action, detail, created_at) "
                        "VALUES (?, ?, ?, ?)",
                        (user_id, "search", query_text, now),
                    )
                print(f"  [ADD]     Recent search #{i + 1}: {query_text!r}")
                added += 1
            except Exception as e:
                # activity_log may not exist in all envs — non-fatal
                print(f"  [WARN]    Could not add search {i + 1}: {e}")
                break
    finally:
        conn.close()

    return added


def seed_demo_user(email: str, dry_run: bool = False) -> None:
    """Full demo seed: find/create user, add watches, add searches."""
    print(f"\nSeeding demo data for: {email}")
    print(f"  Mode: {'DRY-RUN (no writes)' if dry_run else 'LIVE (writes enabled)'}")
    print("-" * 60)

    # Step 1: User
    print("\n[Step 1] User account")
    user = find_or_create_user(email, dry_run=dry_run)

    if dry_run and user["user_id"] == 0:
        # Can't continue without a real user_id in dry-run
        print("\n[DRY-RUN] Skipping watch/search steps (no user_id available)")
        print("\nDry-run summary: no changes made.")
        return

    # Step 2: Watch items
    print("\n[Step 2] Watch items")
    watch_counts = seed_watch_items(user, dry_run=dry_run)

    # Step 3: Recent searches
    print("\n[Step 3] Recent searches")
    search_count = seed_recent_searches(user, dry_run=dry_run)

    # Summary
    print("\n" + "=" * 60)
    print("SEED COMPLETE")
    print(f"  User:           {email} (id={user['user_id']})")
    print(f"  Watch items:    {watch_counts['added']} added, {watch_counts['skipped']} already present")
    print(f"  Recent searches: {search_count} added")
    print("=" * 60)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed a user account with demo data for presentations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/seed_demo.py --email tbrennem@gmail.com
  python scripts/seed_demo.py --email demo@sfpermits.ai --dry-run

Demo parcels seeded:
  - 1455 Market St  (Block 3507 / Lot 004) — South of Market
  - 146 Lake St     (Block 1386 / Lot 025) — Inner Richmond
  - 125 Mason St    (Block 0312 / Lot 005) — Tenderloin
""",
    )
    parser.add_argument(
        "--email",
        required=True,
        help="Email address of the user to seed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be done without making any changes",
    )

    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print(f"ERROR: Invalid email address: {email!r}", file=sys.stderr)
        sys.exit(1)

    try:
        seed_demo_user(email, dry_run=args.dry_run)
    except ImportError as e:
        print(
            f"\nERROR: Could not import project modules: {e}\n"
            "Make sure you have activated the virtual environment:\n"
            "  source .venv/bin/activate\n",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Seed failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
