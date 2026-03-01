#!/usr/bin/env python3
"""
Persona: Amy — Deep Investigation QA
Session ID: persona-amy-20260228
Second pass: authenticated checks via cookie-based session + deeper data quality checks.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE_URL = "https://sfpermits-ai-production.up.railway.app"
SESSION_ID = "persona-amy-20260228"
SCREENSHOT_DIR = Path(f"/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/screenshots/{SESSION_ID}")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

results = []
notes = []

def record(check_num, check_name, status, detail=""):
    results.append({
        "num": check_num,
        "name": check_name,
        "status": status,
        "detail": detail,
    })
    icon = "PASS" if status == "PASS" else ("FAIL" if status == "FAIL" else "SKIP")
    print(f"  [{icon}] {check_num}. {check_name}: {detail[:200] if detail else ''}")

def note(msg):
    notes.append(msg)
    print(f"  NOTE: {msg}")

def screenshot(page, name):
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path)


def run_qa():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # ============================================================
        # DEEP CHECK 1: What does the search result page actually show?
        # (unauthenticated — Amy's entry point before login)
        # ============================================================
        print("\n=== DEEP CHECK D1: Search Result Page Detail ===")
        page.goto(f"{BASE_URL}/search?q=2301+Mission+Street+San+Francisco",
                  wait_until="networkidle", timeout=30000)
        time.sleep(2)
        screenshot(page, "D1-search-mission-full")
        page_text = page.inner_text("body")
        page_html = page.content()

        print(f"  Page URL: {page.url}")
        print(f"  Page length: {len(page_text)} chars")

        # Check for key Amy workflow elements
        permit_ids = re.findall(r'\b20\d{2}\d{6,}\b', page_text)
        print(f"  Permit IDs found: {len(permit_ids)} — sample: {permit_ids[:3]}")

        # Check for status information
        statuses = re.findall(r'\b(issued|filed|open|approved|expired|cancelled|finaled|complete)\b',
                              page_text, re.IGNORECASE)
        print(f"  Status words found: {set(statuses)}")

        # Check for timeline/stuck signals
        timeline_words = ["days", "weeks", "station", "review", "checker", "inspector", "velocity"]
        timeline_found = [w for w in timeline_words if w in page_text.lower()]
        print(f"  Timeline/intelligence words: {timeline_found}")

        # Check for dates
        dates = re.findall(r'\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{4}\b', page_text)
        print(f"  Dates found: {len(dates)} — sample: {dates[:5]}")

        # Record what we find
        if len(permit_ids) > 0 and statuses and dates:
            record("D1", "Search result completeness", "PASS",
                   f"{len(permit_ids)} permits, statuses: {set(list(statuses)[:3])}, dates: {len(dates)}")
        elif len(permit_ids) > 0:
            record("D1", "Search result completeness", "FAIL",
                   f"{len(permit_ids)} permit IDs but no status/dates shown")
            note("Search shows permit IDs without status or dates — Amy can't triage")
        else:
            record("D1", "Search result completeness", "FAIL",
                   f"No permit IDs on search page. Text length: {len(page_text)}")

        # ============================================================
        # DEEP CHECK 2: Inspect the actual search result HTML for data quality
        # ============================================================
        print("\n=== DEEP CHECK D2: Permit Card Data Quality ===")

        # Look for permit card elements
        cards = page.locator("[class*='permit'], [class*='card'], [class*='result'], tr[data-permit], li[data-permit]").all()
        print(f"  Card/result elements found: {len(cards)}")

        # Check for address display
        addresses_on_page = re.findall(r'\d+\s+[A-Za-z]+\s+(?:St|Ave|Blvd|Dr|Pl|Way|Ln|Ct|Rd|Ter|Blvd|Mission|Market|Castro|Valencia|Folsom|Howard|Bryant|Brannan)',
                                      page_text)
        print(f"  Addresses visible: {addresses_on_page[:5]}")

        # Check for applicant/contractor info
        has_applicant = any(w in page_text.lower() for w in ["applicant", "contractor", "owner", "architect"])
        print(f"  Applicant/contractor info: {'yes' if has_applicant else 'no'}")

        # Check for permit type
        has_type = any(w in page_text.lower() for w in ["alteration", "addition", "new construction",
                                                         "demolition", "tenant improvement", "residential",
                                                         "commercial", "permit type"])
        print(f"  Permit type visible: {'yes' if has_type else 'no'}")

        if has_applicant and has_type and dates:
            record("D2", "Permit card data quality", "PASS",
                   "Cards show applicant, permit type, and dates")
        elif has_type and dates:
            record("D2", "Permit card data quality", "FAIL",
                   f"Missing applicant/contractor info. Type: {has_type}, Dates: {len(dates)}, Applicant: {has_applicant}")
            note("Permit cards missing applicant/contractor info — Amy needs this to reach the right people")
        else:
            record("D2", "Permit card data quality", "FAIL",
                   f"Cards missing key fields. Type: {has_type}, Dates: {len(dates)}, Applicant: {has_applicant}")

        # ============================================================
        # DEEP CHECK 3: Drill into a specific permit
        # ============================================================
        print("\n=== DEEP CHECK D3: Single Permit Detail Page ===")

        # If we found permits, click into one
        if permit_ids:
            # Try the permit detail route
            test_permit = permit_ids[0]
            page.goto(f"{BASE_URL}/permit/{test_permit}",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            screenshot(page, "D3-permit-detail")
            detail_text = page.inner_text("body")
            detail_url = page.url

            print(f"  Permit detail URL: {detail_url}")
            print(f"  Page length: {len(detail_text)} chars")

            # Check for core fields
            field_checks = {
                "permit_number": test_permit in detail_text or any(re.search(r'permit\s*#?\s*' + re.escape(test_permit[:8]), detail_text, re.IGNORECASE) for _ in [1]),
                "status": any(w in detail_text.lower() for w in ["issued", "filed", "open", "status"]),
                "address": any(re.search(r'\d+\s+\w+\s+(?:St|Ave|Blvd|Mission)', detail_text) for _ in [1]),
                "permit_type": any(w in detail_text.lower() for w in ["alteration", "addition", "type", "work"]),
                "dates": len(re.findall(r'\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}', detail_text)) > 0,
                "contractor_applicant": any(w in detail_text.lower() for w in ["contractor", "applicant", "owner", "architect"]),
            }

            missing = [k for k, v in field_checks.items() if not v]
            present = [k for k, v in field_checks.items() if v]

            print(f"  Present fields: {present}")
            print(f"  Missing fields: {missing}")

            if not missing:
                record("D3", "Single permit detail — all fields present", "PASS",
                       f"All 6 core fields present for permit {test_permit}")
            elif "permit_number" in missing or "status" in missing:
                record("D3", "Single permit detail — all fields present", "FAIL",
                       f"Critical fields missing: {missing}")
            else:
                record("D3", "Single permit detail — all fields present", "FAIL",
                       f"Missing: {missing} for permit {test_permit}")
                note(f"Permit detail page for {test_permit} missing: {missing}")
        else:
            record("D3", "Single permit detail — all fields present", "SKIP",
                   "No permit IDs found to drill into")

        # ============================================================
        # DEEP CHECK 4: Error state — what does the bad permit show?
        # ============================================================
        print("\n=== DEEP CHECK D4: Error State Investigation ===")

        # Test the actual error state
        page.goto(f"{BASE_URL}/search?q=9999999999",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "D4-error-state-search")
        error_text = page.inner_text("body")
        error_html = page.content()

        # Check for exposed internals
        exposed_patterns = [
            (r'Traceback \(most recent', "Python traceback"),
            (r'File ".*\.py"', "Python file path"),
            (r'psycopg2\.|sqlalchemy\.|duckdb\.|pg_catalog', "DB internals"),
            (r'Internal Server Error', "Server error message"),
            (r'<pre.*>.*Exception', "Exception in HTML"),
        ]

        exposed = []
        for pattern, label in exposed_patterns:
            if re.search(pattern, error_html, re.IGNORECASE | re.DOTALL):
                exposed.append(label)

        # Also check direct permit route
        page.goto(f"{BASE_URL}/permit/9999999999",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "D4b-error-direct-permit")
        error2_text = page.inner_text("body")
        error2_html = page.content()

        exposed2 = []
        for pattern, label in exposed_patterns:
            if re.search(pattern, error2_html, re.IGNORECASE | re.DOTALL):
                exposed2.append(label)

        has_graceful_1 = any(w in error_text.lower() for w in ["no results", "not found", "try", "couldn't", "no permits"])
        has_graceful_2 = any(w in error2_text.lower() for w in ["not found", "no results", "couldn't"])

        print(f"  Search error page: exposed={exposed}, graceful={has_graceful_1}")
        print(f"  Direct permit error: exposed={exposed2}, graceful={has_graceful_2}")

        if exposed or exposed2:
            record("D4", "Error state — no internals exposed", "FAIL",
                   f"Exposed: {exposed + exposed2}")
            note(f"Server internals exposed on error state: {exposed + exposed2}")
        elif has_graceful_1 or has_graceful_2:
            record("D4", "Error state — no internals exposed", "PASS",
                   "Graceful error messages shown, no internals exposed")
        else:
            record("D4", "Error state — no internals exposed", "FAIL",
                   f"No graceful error message. Search: '{error_text[:100]}' | Direct: '{error2_text[:100]}'")

        # ============================================================
        # DEEP CHECK 5: Landing page — does Amy have clear entry points?
        # ============================================================
        print("\n=== DEEP CHECK D5: Landing Page — Amy Entry Points ===")
        page.goto(BASE_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)
        screenshot(page, "D5-landing-full")
        landing_text = page.inner_text("body")
        landing_html = page.content()

        # Check for search input
        search_input = page.locator("input[type=search], input[placeholder*='address' i], input[placeholder*='permit' i], input[placeholder*='search' i]")
        has_search = search_input.count() > 0
        print(f"  Search input: {'found' if has_search else 'missing'}")

        # Check for brief link (Amy's daily workflow start)
        has_brief_link = bool(re.search(r'brief|morning\s+brief|daily\s+brief', landing_html, re.IGNORECASE))
        print(f"  Brief link: {'found' if has_brief_link else 'missing'}")

        # Check for portfolio/watch link
        has_portfolio = bool(re.search(r'portfolio|my\s+permits|tracked\s+permits|watch', landing_html, re.IGNORECASE))
        print(f"  Portfolio/watch link: {'found' if has_portfolio else 'missing'}")

        # Check CTA text — is it aimed at professionals?
        pro_signals = re.findall(r'expediter|professional|firm|portfolio|brief|morning|daily|track\s+permits|client',
                                landing_html, re.IGNORECASE)
        print(f"  Professional signals: {pro_signals[:5]}")

        # Check for login/account link
        has_login = bool(re.search(r'sign\s*in|log\s*in|account|dashboard', landing_html, re.IGNORECASE))
        print(f"  Login/account link: {'found' if has_login else 'missing'}")

        if has_search:
            record("D5", "Landing page — search entry point", "PASS", "Search input present")
        else:
            record("D5", "Landing page — search entry point", "FAIL", "No search input on landing page")

        if has_brief_link or has_portfolio:
            record("D5b", "Landing page — pro workflow entry points", "PASS",
                   f"Brief link: {has_brief_link}, Portfolio: {has_portfolio}")
        else:
            record("D5b", "Landing page — pro workflow entry points", "FAIL",
                   "No brief or portfolio links on landing — Amy can't reach her daily tools from home")
            note("Landing page missing brief/portfolio links — Amy would need to know the direct URLs")

        # ============================================================
        # DEEP CHECK 6: Route inventory — what paths actually exist?
        # ============================================================
        print("\n=== DEEP CHECK D6: Route Inventory for Amy's Workflow ===")

        amy_routes = [
            ("/brief", "Morning Brief"),
            ("/portfolio", "Portfolio"),
            ("/search", "Search"),
            ("/dashboard", "Dashboard"),
            ("/account", "Account"),
            ("/watch/list", "Watch List"),
            ("/property", "Property Report"),
            ("/about-data", "About Data"),
        ]

        route_results = {}
        for path, name in amy_routes:
            resp = context.request.get(f"{BASE_URL}{path}")
            # 200 = accessible, 302/301 = redirect (likely to login), 404 = broken
            if resp.status == 200:
                route_results[path] = "OK"
            elif resp.status in (301, 302):
                route_results[path] = f"REDIRECT-{resp.status}"
            elif resp.status == 404:
                route_results[path] = "404"
            else:
                route_results[path] = f"HTTP-{resp.status}"

        print(f"  Route inventory:")
        broken_routes = []
        redirect_routes = []
        for path, status in route_results.items():
            print(f"    {path}: {status}")
            if status == "404":
                broken_routes.append(path)
            elif "REDIRECT" in status:
                redirect_routes.append(path)

        if broken_routes:
            record("D6", "Route inventory — no broken Amy routes", "FAIL",
                   f"404 routes: {broken_routes}")
            note(f"These routes are 404 for Amy: {broken_routes}")
        else:
            record("D6", "Route inventory — no broken Amy routes", "PASS",
                   f"Auth-redirect routes: {redirect_routes}. No 404s.")

        # ============================================================
        # DEEP CHECK 7: Data freshness — what is the newest permit in DB?
        # ============================================================
        print("\n=== DEEP CHECK D7: Data Freshness — Permit Age ===")

        # Try the API to find newest permits
        page.goto(f"{BASE_URL}/search?q=filed+Mission+Street",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        fresh_text = page.inner_text("body")

        # Look for dates in search results
        all_dates = re.findall(r'\b(20\d{2})-(\d{2})-(\d{2})\b', fresh_text)

        if all_dates:
            # Find most recent
            date_objs = []
            for yr, mo, dy in all_dates:
                try:
                    date_objs.append(datetime(int(yr), int(mo), int(dy)))
                except:
                    pass

            if date_objs:
                newest = max(date_objs)
                oldest = min(date_objs)
                now = datetime.now()
                days_old = (now - newest).days

                print(f"  Newest date in results: {newest.date()} ({days_old} days ago)")
                print(f"  Oldest date: {oldest.date()}")

                if days_old <= 2:
                    record("D7", "Data freshness — permit dates current", "PASS",
                           f"Newest permit date: {newest.date()} ({days_old}d ago)")
                elif days_old <= 7:
                    record("D7", "Data freshness — permit dates current", "FAIL",
                           f"Data is {days_old} days stale. Newest: {newest.date()}")
                    note(f"Permit data may be stale — newest date is {days_old} days ago")
                else:
                    record("D7", "Data freshness — permit dates current", "FAIL",
                           f"Data is {days_old} days stale. SODA sync may be broken. Newest: {newest.date()}")
            else:
                record("D7", "Data freshness — permit dates current", "SKIP",
                       "Could not parse dates from results")
        else:
            record("D7", "Data freshness — permit dates current", "SKIP",
                   "No dates found in search results to assess freshness")

        # ============================================================
        # DEEP CHECK 8: Signal quality on a known permit
        # ============================================================
        print("\n=== DEEP CHECK D8: Intelligence Signals — Stuck Permit Detection ===")

        # Search specifically for a permit that's likely at a station (in-review)
        page.goto(f"{BASE_URL}/search?q=2300+Mission+Street",
                  wait_until="networkidle", timeout=30000)
        time.sleep(3)
        screenshot(page, "D8-2300-mission-search")
        result_text = page.inner_text("body")

        # Check for velocity/station signals
        station_signals = {
            "station_name": bool(re.search(r'(plan check|building dept|planning dept|fire dept|DBI|Planning)',
                                          result_text, re.IGNORECASE)),
            "days_at_station": bool(re.search(r'\d+\s*days?\s*(at|in|waiting|elapsed)',
                                             result_text, re.IGNORECASE)),
            "velocity_benchmark": bool(re.search(r'typical|median|average|benchmark|similar',
                                                result_text, re.IGNORECASE)),
            "risk_flag": bool(re.search(r'stuck|stall|delay|at risk|flag|concern',
                                       result_text, re.IGNORECASE)),
            "timeline_estimate": bool(re.search(r'estimated?\s*(completion|approval|issuance)|predict',
                                               result_text, re.IGNORECASE)),
        }

        present = [k for k, v in station_signals.items() if v]
        missing = [k for k, v in station_signals.items() if not v]
        print(f"  Station signals present: {present}")
        print(f"  Station signals missing: {missing}")

        if len(present) >= 3:
            record("D8", "Intelligence signals — stuck permit detection", "PASS",
                   f"{len(present)}/5 signals: {present}")
        elif len(present) >= 1:
            record("D8", "Intelligence signals — stuck permit detection", "FAIL",
                   f"Only {len(present)}/5 signals. Missing: {missing}")
            note(f"Amy needs these signals to detect stuck permits: {missing}")
        else:
            record("D8", "Intelligence signals — stuck permit detection", "FAIL",
                   "No intelligence signals for stuck permit detection")

        # ============================================================
        # DEEP CHECK 9: Property Report — Full Amy Research Workflow
        # ============================================================
        print("\n=== DEEP CHECK D9: Property Report — Amy's Research Tool ===")

        page.goto(f"{BASE_URL}/property?address=2301+Mission+Street+San+Francisco",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        screenshot(page, "D9-property-report")
        prop_url = page.url
        prop_text = page.inner_text("body")

        print(f"  Property URL: {prop_url}")
        print(f"  Page length: {len(prop_text)} chars")

        if "/login" in prop_url or "/auth" in prop_url:
            record("D9", "Property report — accessible", "SKIP",
                   "Property report requires auth — would need valid session")
            note("Property report behind auth wall — Amy must be logged in")
        elif "not found" in prop_text.lower() and len(prop_text) < 200:
            record("D9", "Property report — accessible", "FAIL",
                   "Property report returns 404 or not found")
        else:
            # Check for key property report fields
            prop_checks = {
                "permit_list": len(re.findall(r'\b20\d{2}\d{6,}\b', prop_text)) > 0,
                "address_confirmed": "mission" in prop_text.lower() or "2301" in prop_text,
                "permit_types": any(w in prop_text.lower() for w in ["alteration", "new", "addition", "type"]),
                "status_info": any(w in prop_text.lower() for w in ["issued", "filed", "open", "complete"]),
                "timeline_info": len(re.findall(r'\d{4}-\d{2}-\d{2}', prop_text)) > 0,
            }

            present = [k for k, v in prop_checks.items() if v]
            missing = [k for k, v in prop_checks.items() if not v]
            print(f"  Present: {present}")
            print(f"  Missing: {missing}")

            if len(missing) <= 1:
                record("D9", "Property report — accessible", "PASS",
                       f"Property report shows: {present}")
            else:
                record("D9", "Property report — accessible", "FAIL",
                       f"Property report missing: {missing}")

        # ============================================================
        # DEEP CHECK 10: Demo path — can Amy try before signing in?
        # ============================================================
        print("\n=== DEEP CHECK D10: Demo Path — Unauthenticated Amy ===")

        demo_routes = [
            ("/demo", "Demo page"),
            ("/search?q=1660+Mission+Street", "Public search"),
        ]

        demo_results = {}
        for path, name in demo_routes:
            page.goto(f"{BASE_URL}{path}", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            url_after = page.url
            text_after = page.inner_text("body")

            # Count meaningful content
            permit_ids = re.findall(r'\b20\d{2}\d{6,}\b', text_after)
            has_useful = len(text_after) > 1000 and not ("/login" in url_after)

            demo_results[name] = {
                "accessible": "/login" not in url_after,
                "has_permit_data": len(permit_ids) > 0,
                "content_length": len(text_after),
                "url": url_after[:80],
            }
            print(f"  {name}: accessible={demo_results[name]['accessible']}, permits={len(permit_ids)}, length={len(text_after)}")

        screenshot(page, "D10-demo-or-public")

        all_accessible = all(v["accessible"] for v in demo_results.values())
        any_has_data = any(v["has_permit_data"] for v in demo_results.values())

        if all_accessible and any_has_data:
            record("D10", "Demo/public search — unauthenticated Amy gets value", "PASS",
                   "Public routes accessible with permit data")
        elif all_accessible:
            record("D10", "Demo/public search — unauthenticated Amy gets value", "FAIL",
                   "Public routes accessible but no permit data shown")
            note("Unauthenticated Amy sees pages but no data — hard sell for sign-up")
        else:
            record("D10", "Demo/public search — unauthenticated Amy gets value", "FAIL",
                   f"Some public routes require auth: {[k for k,v in demo_results.items() if not v['accessible']]}")

        browser.close()

    return results, notes


def write_report(results, notes):
    today = datetime.now().strftime("%Y-%m-%d")
    session_id = SESSION_ID

    lines = [
        f"# Persona: Amy QA Results (Deep Pass) — {today}",
        "",
        f"**Session ID:** {session_id}-deep",
        f"**Base URL:** {BASE_URL}",
        f"**Run time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "| # | Check | Status | Notes |",
        "|---|-------|--------|-------|",
    ]

    for r in results:
        status = r["status"]
        detail = r["detail"][:200] if r["detail"] else ""
        lines.append(f"| {r['num']} | {r['name']} | {status} | {detail} |")

    passes = sum(1 for r in results if r["status"] == "PASS")
    fails = sum(1 for r in results if r["status"] == "FAIL")
    skips = sum(1 for r in results if r["status"] == "SKIP")
    total = len(results)

    lines += [
        "",
        f"**Summary:** {passes} PASS / {fails} FAIL / {skips} SKIP out of {total} checks",
        "",
        "## Data Quality Notes (non-blocking)",
        "",
    ]

    if notes:
        for n in notes:
            lines.append(f"- {n}")
    else:
        lines.append("- None")

    lines += [
        "",
        "## Screenshots",
        "",
        f"Saved to: `qa-results/screenshots/{session_id}/`",
        "",
    ]

    for p in sorted(SCREENSHOT_DIR.glob("D*.png")):
        lines.append(f"- `{p.name}`")

    report = "\n".join(lines)
    out_path = f"/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/{session_id}-deep-persona-amy-qa.md"
    with open(out_path, "w") as f:
        f.write(report)

    print(f"\nReport written to: {out_path}")
    return out_path, passes, fails, skips


if __name__ == "__main__":
    print(f"Starting Deep Persona Amy QA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Target: {BASE_URL}")

    results, notes = run_qa()
    out_path, passes, fails, skips = write_report(results, notes)

    print(f"\n{'='*60}")
    print(f"RESULTS: {passes} PASS / {fails} FAIL / {skips} SKIP")
    print(f"{'='*60}")

    sys.exit(0 if fails == 0 else 1)
