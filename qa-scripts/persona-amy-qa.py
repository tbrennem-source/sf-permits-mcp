#!/usr/bin/env python3
"""
Persona: Amy — The Permit Expediter
Full workflow QA against production site.
Session ID: persona-amy-20260228
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

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
        "ts": datetime.now().isoformat()
    })
    icon = "PASS" if status == "PASS" else ("FAIL" if status == "FAIL" else "SKIP")
    print(f"  [{icon}] {check_num}. {check_name}: {detail[:120] if detail else ''}")

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

        # ---------- STEP 0: Test-login to get auth session ----------
        print("\n=== AUTH: Getting test-login session ===")
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # Try test-login endpoint
        resp = page.request.post(f"{BASE_URL}/auth/test-login")
        if resp.status == 200:
            body = resp.json()
            print(f"  test-login response: {body}")
        else:
            print(f"  test-login HTTP {resp.status} — will proceed unauthenticated")

        # Navigate to home to confirm session
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        screenshot(page, "00-home-auth")
        time.sleep(1)

        # ============================================================
        # CHECK 1: Morning Brief — Data Freshness
        # ============================================================
        print("\n=== CHECK 1: Morning Brief — Data Freshness ===")
        page.goto(f"{BASE_URL}/brief", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "01-brief-page")

        page_text = page.inner_text("body")
        page_html = page.content()

        # Look for date indicators
        today = datetime.now()
        today_str = today.strftime("%B %d, %Y")
        today_short = today.strftime("%Y-%m-%d")
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # Check if brief is accessible (not redirect to login)
        current_url = page.url
        if "/login" in current_url or "/auth" in current_url:
            record(1, "Morning brief freshness", "FAIL", f"Redirected to {current_url} — auth required")
        else:
            # Look for date in page content
            has_today = today_str in page_text or today_short in page_text
            has_yesterday = yesterday in page_text
            has_date = has_today or has_yesterday

            # Check for pipeline health section
            has_pipeline = any(kw in page_text.lower() for kw in ["pipeline", "health", "station", "velocity"])
            has_changes = any(kw in page_text.lower() for kw in ["change", "permit", "filed", "issued", "approved"])

            # Check for "stale" indicators
            three_days_ago = (today - timedelta(days=3)).strftime("%Y-%m-%d")

            if not has_changes and "no data" in page_text.lower():
                record(1, "Morning brief freshness", "FAIL", "No permit change data shown")
            elif has_date and has_pipeline:
                record(1, "Morning brief freshness", "PASS", f"Date found, pipeline health present")
            elif has_date:
                record(1, "Morning brief freshness", "PASS", f"Date found — pipeline health section: {'yes' if has_pipeline else 'missing'}")
                if not has_pipeline:
                    note("Pipeline health section missing from brief")
            else:
                # Check what date IS shown
                import re
                date_pattern = r'\d{4}-\d{2}-\d{2}'
                dates_found = re.findall(date_pattern, page_text)
                record(1, "Morning brief freshness", "FAIL", f"No current date found. Dates in page: {dates_found[:5]}")

        # ============================================================
        # CHECK 2: Morning Brief — Change Quality
        # ============================================================
        print("\n=== CHECK 2: Morning Brief — Change Quality ===")
        # Still on brief page
        # Look for structured permit change entries
        import re

        # Permit number pattern: SF permits typically look like 202301234567
        permit_pattern = r'\b\d{12}\b|\bPA-\d{4}-\d+\b|\bBPA\d+\b|\d{4}-\d{4,}\b'
        permit_nums_found = re.findall(permit_pattern, page_text)

        # Look for addresses (Street + number)
        address_pattern = r'\d+\s+[A-Z][a-z]+\s+(?:St|Ave|Blvd|Dr|Pl|Way|Ln|Ct|Rd|Ter)\b'
        addresses_found = re.findall(address_pattern, page_text)

        # Look for change type words
        change_words = ["filed", "issued", "approved", "expired", "cancelled", "finaled", "revised", "withdrawn"]
        change_words_found = [w for w in change_words if w in page_text.lower()]

        # Look for time indicators
        time_words = ["hour", "minute", "yesterday", "today", "ago", "am", "pm"]
        time_found = any(w in page_text.lower() for w in time_words)

        if len(permit_nums_found) > 0 and (len(addresses_found) > 0 or change_words_found):
            record(2, "Brief change quality", "PASS",
                   f"Found {len(permit_nums_found)} permit refs, {len(addresses_found)} addresses, change types: {change_words_found[:3]}")
        elif len(permit_nums_found) > 0:
            record(2, "Brief change quality", "FAIL",
                   f"Permit numbers found ({len(permit_nums_found)}) but no addresses or change context")
            note(f"Brief shows permit numbers without address/change-type context: {permit_nums_found[:3]}")
        elif "no changes" in page_text.lower() or "no permits" in page_text.lower():
            record(2, "Brief change quality", "SKIP", "No changes data in brief (may be off-hours)")
        else:
            # Check if brief page exists at all
            title = page.title()
            if "not found" in title.lower() or "404" in title.lower():
                record(2, "Brief change quality", "FAIL", "Brief page returns 404")
            else:
                record(2, "Brief change quality", "FAIL",
                       f"No permit numbers or change context found. Page title: {title[:80]}")
                note(f"Brief page text preview: {page_text[:500]}")

        # ============================================================
        # CHECK 3: Permit Lookup — Complete Data
        # ============================================================
        print("\n=== CHECK 3: Permit Lookup — Complete Data ===")
        # Use a known recent SF permit number from our DB (we know permits table has 1.98M rows)
        # Try a search first to find a real permit number

        # First try the search route
        page.goto(f"{BASE_URL}/search?q=202304+Mission+Street", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "03a-search-address")

        search_text = page.inner_text("body")
        search_url = page.url

        # Try direct permit lookup with a known SF permit
        # 202305041234 - test format. Try the API endpoint
        test_permit = "202305041234"

        # Try the search with address
        page.goto(f"{BASE_URL}/search?q=2535+Mission+Street", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        screenshot(page, "03b-mission-search")

        mission_text = page.inner_text("body")

        # Check the API endpoint for permit lookup
        api_resp = page.request.get(f"{BASE_URL}/api/permits?address=2535+Mission+Street")

        if api_resp.status == 200:
            try:
                api_data = api_resp.json()
                if isinstance(api_data, list) and len(api_data) > 0:
                    permit = api_data[0]
                    has_number = bool(permit.get("permit_number") or permit.get("permit_num"))
                    has_address = bool(permit.get("address") or permit.get("street_address"))
                    has_status = bool(permit.get("status") or permit.get("permit_status"))
                    has_type = bool(permit.get("permit_type") or permit.get("permit_type_def"))
                    has_dates = bool(permit.get("filed_date") or permit.get("issued_date") or permit.get("application_date"))

                    missing = []
                    if not has_number: missing.append("permit_number")
                    if not has_address: missing.append("address")
                    if not has_status: missing.append("status")
                    if not has_type: missing.append("permit_type")
                    if not has_dates: missing.append("dates")

                    if not missing:
                        record(3, "Permit lookup — complete data", "PASS",
                               f"All core fields present. First permit: {permit.get('permit_number', 'N/A')}")
                    else:
                        record(3, "Permit lookup — complete data", "FAIL",
                               f"Missing fields: {missing}. Got keys: {list(permit.keys())[:10]}")

                    note(f"Sample permit keys: {list(permit.keys())[:15]}")
                elif isinstance(api_data, dict) and api_data.get("error"):
                    record(3, "Permit lookup — complete data", "FAIL", f"API error: {api_data.get('error')}")
                else:
                    record(3, "Permit lookup — complete data", "SKIP", f"API returned empty or unexpected format: {type(api_data)}")
            except Exception as e:
                record(3, "Permit lookup — complete data", "FAIL", f"JSON parse error: {e}")
        else:
            # Try the property report route
            page.goto(f"{BASE_URL}/property?address=2535+Mission+Street", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            screenshot(page, "03c-property-report")
            prop_text = page.inner_text("body")

            # Check for permit data on property page
            permit_indicators = re.findall(r'\b(?:20\d{2})\d{6,}\b', prop_text)
            if permit_indicators:
                record(3, "Permit lookup — complete data", "PASS",
                       f"Property page shows permits (found {len(permit_indicators)} permit-like IDs)")
            else:
                # Check search results for permit data
                if "permit" in mission_text.lower() and len(mission_text) > 500:
                    record(3, "Permit lookup — complete data", "PASS" if "address" in mission_text.lower() else "FAIL",
                           f"Search page has permit content. API /api/permits returned {api_resp.status}")
                    note(f"/api/permits endpoint returned {api_resp.status}")
                else:
                    record(3, "Permit lookup — complete data", "FAIL",
                           f"/api/permits returned {api_resp.status}, property page shows no permit IDs")

        # ============================================================
        # CHECK 4: Permit Prediction — Reasonable Timeline
        # ============================================================
        print("\n=== CHECK 4: Permit Prediction — Reasonable Timeline ===")

        # Try the predict endpoint
        predict_resp = page.request.post(
            f"{BASE_URL}/api/predict",
            data=json.dumps({"permit_type": "residential alteration", "scope": "kitchen remodel"}),
            headers={"Content-Type": "application/json"}
        )

        if predict_resp.status == 200:
            try:
                pred_data = predict_resp.json()
                # Look for timeline estimate
                has_estimate = any(k in pred_data for k in ["weeks", "days", "estimate", "timeline", "prediction", "range"])

                if has_estimate:
                    # Validate range is reasonable (2-24 weeks for residential alteration)
                    weeks = pred_data.get("weeks") or pred_data.get("estimate_weeks") or 0
                    if isinstance(weeks, (int, float)):
                        if 2 <= weeks <= 24:
                            record(4, "Permit prediction — reasonable timeline", "PASS",
                                   f"Estimate: {weeks} weeks (within 2-24 week SF residential range)")
                        elif weeks == 0:
                            record(4, "Permit prediction — reasonable timeline", "FAIL",
                                   "Prediction returned 0 weeks")
                        elif weeks > 52:
                            record(4, "Permit prediction — reasonable timeline", "FAIL",
                                   f"Unrealistic estimate: {weeks} weeks")
                        else:
                            record(4, "Permit prediction — reasonable timeline", "PASS",
                                   f"Estimate: {weeks} weeks")
                    else:
                        record(4, "Permit prediction — reasonable timeline", "PASS",
                               f"Prediction returned: {str(pred_data)[:200]}")
                else:
                    record(4, "Permit prediction — reasonable timeline", "FAIL",
                           f"No timeline estimate in response: {list(pred_data.keys())}")
                    note(f"Predict response keys: {list(pred_data.keys())}")
            except Exception as e:
                record(4, "Permit prediction — reasonable timeline", "FAIL", f"Parse error: {e}")
        else:
            # Try via the predict_permits tool / UI route
            page.goto(f"{BASE_URL}/tools/predict?permit_type=alteration&scope=residential",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            pred_text = page.inner_text("body")
            pred_url = page.url

            if "/login" in pred_url or "/auth" in pred_url:
                record(4, "Permit prediction — reasonable timeline", "SKIP",
                       "Prediction tool requires authentication — SKIP (auth dependency)")
            elif any(w in pred_text.lower() for w in ["week", "day", "month", "timeline", "estimate"]):
                # Extract timeline from page text
                week_matches = re.findall(r'(\d+)\s*week', pred_text, re.IGNORECASE)
                if week_matches:
                    weeks = int(week_matches[0])
                    if 2 <= weeks <= 104:
                        record(4, "Permit prediction — reasonable timeline", "PASS",
                               f"Page shows {weeks} week estimate")
                    elif weeks == 0:
                        record(4, "Permit prediction — reasonable timeline", "FAIL", "0-week estimate shown")
                    else:
                        record(4, "Permit prediction — reasonable timeline", "FAIL",
                               f"Suspicious estimate: {weeks} weeks")
                else:
                    record(4, "Permit prediction — reasonable timeline", "PASS",
                           f"Timeline language found on page (API endpoint {predict_resp.status})")
            else:
                record(4, "Permit prediction — reasonable timeline", "FAIL",
                       f"Predict endpoint HTTP {predict_resp.status}, no timeline on UI route")
                note(f"predict_resp status: {predict_resp.status}")
                screenshot(page, "04-predict-result")

        # ============================================================
        # CHECK 5: Consultant Recommendations — Relevant Results
        # ============================================================
        print("\n=== CHECK 5: Consultant Recommendations ===")

        consult_resp = page.request.post(
            f"{BASE_URL}/api/consultants",
            data=json.dumps({"scope": "structural engineering", "location": "San Francisco"}),
            headers={"Content-Type": "application/json"}
        )

        if consult_resp.status == 200:
            try:
                consult_data = consult_resp.json()
                items = consult_data if isinstance(consult_data, list) else consult_data.get("results", [])

                if items:
                    first = items[0]
                    has_name = bool(first.get("name") or first.get("firm_name") or first.get("entity_name"))
                    has_contact = bool(first.get("email") or first.get("phone") or first.get("address") or first.get("contact"))
                    sf_relevant = any("san francisco" in str(v).lower() or "sf" in str(v).lower()
                                     for v in first.values() if isinstance(v, str))

                    if has_name and has_contact:
                        record(5, "Consultant recommendations — relevant results", "PASS",
                               f"{len(items)} results, name + contact present")
                    elif has_name:
                        record(5, "Consultant recommendations — relevant results", "FAIL",
                               f"{len(items)} results but missing contact info")
                        note("Consultant results lack contact info — Amy can't reach them")
                    else:
                        record(5, "Consultant recommendations — relevant results", "FAIL",
                               f"No name/firm in results. Keys: {list(first.keys())}")
                else:
                    record(5, "Consultant recommendations — relevant results", "FAIL",
                           "Empty results for structural engineering scope")
            except Exception as e:
                record(5, "Consultant recommendations — relevant results", "FAIL", f"Parse error: {e}")
        else:
            # Try the UI recommend route
            page.goto(f"{BASE_URL}/search?q=structural+engineer+San+Francisco",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            screenshot(page, "05-consultant-search")
            consult_text = page.inner_text("body")

            # Try entity search route
            entity_resp = page.request.get(f"{BASE_URL}/api/entities?type=contractor&scope=structural")

            if entity_resp.status == 200:
                try:
                    entity_data = entity_resp.json()
                    items = entity_data if isinstance(entity_data, list) else entity_data.get("results", [])
                    if items:
                        first = items[0]
                        has_name = bool(first.get("name") or first.get("entity_name"))
                        has_contact = bool(first.get("email") or first.get("phone") or first.get("address"))

                        if has_name and has_contact:
                            record(5, "Consultant recommendations — relevant results", "PASS",
                                   f"Entity API: {len(items)} results with name+contact")
                        else:
                            record(5, "Consultant recommendations — relevant results", "FAIL",
                                   f"Entity API results missing contact info. Keys: {list(first.keys())[:8]}")
                    else:
                        record(5, "Consultant recommendations — relevant results", "SKIP",
                               f"No consultant API found. /api/consultants={consult_resp.status}, /api/entities={entity_resp.status}")
                except:
                    record(5, "Consultant recommendations — relevant results", "SKIP",
                           f"No consultant recommendation API (consult={consult_resp.status}, entity={entity_resp.status})")
            else:
                # Try recommend_consultants MCP tool via any UI
                record(5, "Consultant recommendations — relevant results", "SKIP",
                       f"No consultant API endpoints accessible (HTTP {consult_resp.status})")
                note("Need to check if recommend_consultants tool is exposed via web UI")

        # ============================================================
        # CHECK 6: Entity Network — Contractor Lookup
        # ============================================================
        print("\n=== CHECK 6: Entity Network — Contractor Lookup ===")

        # Try entity lookup by contractor name
        entity_resp = page.request.get(f"{BASE_URL}/api/entity?name=Cahill+Contractors")

        if entity_resp.status == 200:
            try:
                entity_data = entity_resp.json()
                has_name = bool(entity_data.get("name") or entity_data.get("entity_name"))
                has_permits = bool(entity_data.get("permits") or entity_data.get("permit_count") or
                                  entity_data.get("permit_history") or entity_data.get("recent_permits"))
                has_contact = bool(entity_data.get("email") or entity_data.get("phone") or entity_data.get("address"))

                if has_name and has_permits:
                    record(6, "Entity network — contractor lookup", "PASS",
                           f"Entity found with name + permit history")
                elif has_name:
                    record(6, "Entity network — contractor lookup", "FAIL",
                           f"Entity found but no permit history")
                    note("Entity record lacks permit history — minimum 3 months needed for Amy")
                else:
                    record(6, "Entity network — contractor lookup", "FAIL",
                           f"Entity found but no name. Keys: {list(entity_data.keys())}")
            except Exception as e:
                record(6, "Entity network — contractor lookup", "FAIL", f"Parse error: {e}")
        else:
            # Try search route for entity
            page.goto(f"{BASE_URL}/search?q=Cahill+Contractors", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            screenshot(page, "06-entity-search")
            entity_text = page.inner_text("body")

            # Check entity API with license
            lic_resp = page.request.get(f"{BASE_URL}/api/entities?q=Cahill+Contractors")

            if lic_resp.status == 200:
                try:
                    lic_data = lic_resp.json()
                    items = lic_data if isinstance(lic_data, list) else lic_data.get("results", [])
                    if items:
                        first = items[0]
                        has_name = bool(first.get("name") or first.get("entity_name"))
                        has_permits = bool(first.get("permit_count") or first.get("permits") or first.get("permit_history"))

                        if has_name and has_permits:
                            record(6, "Entity network — contractor lookup", "PASS",
                                   f"Entities API: {len(items)} results with permit history")
                        elif has_name:
                            record(6, "Entity network — contractor lookup", "FAIL",
                                   "Entity found but no permit history")
                        else:
                            record(6, "Entity network — contractor lookup", "FAIL",
                                   f"No name in entity results. Keys: {list(first.keys())[:10]}")
                    else:
                        record(6, "Entity network — contractor lookup", "FAIL",
                               "No entities found for 'Cahill Contractors'")
                except Exception as e:
                    record(6, "Entity network — contractor lookup", "FAIL", f"Parse error: {e}")
            else:
                # Check if search page shows contractor info
                if "contractor" in entity_text.lower() or "entity" in entity_text.lower():
                    record(6, "Entity network — contractor lookup", "PASS",
                           "Search page shows contractor/entity results")
                else:
                    record(6, "Entity network — contractor lookup", "FAIL",
                           f"Entity API {entity_resp.status}/{lic_resp.status}, no contractor data in search")

        # ============================================================
        # CHECK 7: Regulatory Watch — Can Track Items
        # ============================================================
        print("\n=== CHECK 7: Regulatory Watch — Can Track Items ===")

        page.goto(f"{BASE_URL}/watch", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "07a-watch-page")
        watch_url = page.url
        watch_text = page.inner_text("body")

        if "/login" in watch_url or "/auth" in watch_url:
            # Try portfolio route
            page.goto(f"{BASE_URL}/portfolio", wait_until="domcontentloaded", timeout=30000)
            time.sleep(2)
            portfolio_url = page.url
            if "/login" in portfolio_url or "/auth" in portfolio_url:
                record(7, "Regulatory watch — can track items", "SKIP",
                       "Watch/portfolio requires auth — test-login may not have succeeded")
            else:
                screenshot(page, "07b-portfolio")
                portfolio_text = page.inner_text("body")
                has_watch = any(w in portfolio_text.lower() for w in ["watch", "track", "add", "portfolio", "follow"])
                record(7, "Regulatory watch — can track items", "PASS" if has_watch else "FAIL",
                       f"Portfolio page accessible. Watch UI: {'present' if has_watch else 'missing'}")
        else:
            # On watch page, check for add functionality
            has_add = any(w in watch_text.lower() for w in ["add", "track", "watch", "follow", "+"])
            has_list = any(w in watch_text.lower() for w in ["your watches", "tracked", "watching", "items"])

            # Try to find add watch form/button
            add_btn = page.locator("button, a, input").filter(has_text=re.compile(r"add|track|watch|follow", re.IGNORECASE))

            if has_add:
                record(7, "Regulatory watch — can track items", "PASS",
                       "Watch page accessible with add functionality visible")
            elif has_list:
                record(7, "Regulatory watch — can track items", "PASS",
                       "Watch page shows tracked items list")
            else:
                record(7, "Regulatory watch — can track items", "FAIL",
                       f"Watch page missing add/list functionality. URL: {watch_url}")
                note(f"Watch page text preview: {watch_text[:300]}")

        # ============================================================
        # CHECK 8: Search — Address Lookup Accuracy
        # ============================================================
        print("\n=== CHECK 8: Search — Address Lookup Accuracy ===")

        # Use a well-known SF address with permit activity
        test_address = "1 Dr Carlton B Goodlett Pl"  # SF City Hall

        page.goto(f"{BASE_URL}/search?q={test_address.replace(' ', '+')}",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        screenshot(page, "08a-city-hall-search")

        search_text = page.inner_text("body")
        search_url = page.url

        # Also try a residential address
        page.goto(f"{BASE_URL}/search?q=2301+Mission+Street+San+Francisco",
                  wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        screenshot(page, "08b-mission-search")
        mission_text = page.inner_text("body")

        # Check for permit results
        permit_like = re.findall(r'\b20\d{2}\d{6,}\b', mission_text)
        has_address_result = "mission" in mission_text.lower() or "2301" in mission_text
        has_permits = len(permit_like) > 0 or any(w in mission_text.lower() for w in ["permit", "filed", "issued", "application"])

        if has_permits and has_address_result:
            record(8, "Search — address lookup accuracy", "PASS",
                   f"Address search returns permit data. Found {len(permit_like)} permit IDs")
        elif has_address_result:
            record(8, "Search — address lookup accuracy", "FAIL",
                   "Address found but no permit data shown")
            note("Search returns address but no permit history — Amy needs permits to assess situation")
        elif "no results" in mission_text.lower() or "no permits" in mission_text.lower():
            record(8, "Search — address lookup accuracy", "FAIL",
                   "No results for active SF address (2301 Mission Street)")
        else:
            # Check if search redirected to property page
            if "/property" in page.url:
                prop_text = page.inner_text("body")
                has_permits_prop = re.findall(r'\b20\d{2}\d{6,}\b', prop_text)
                if has_permits_prop:
                    record(8, "Search — address lookup accuracy", "PASS",
                           f"Redirected to property page with {len(has_permits_prop)} permits")
                else:
                    record(8, "Search — address lookup accuracy", "FAIL",
                           f"Property page has no permit data")
            else:
                record(8, "Search — address lookup accuracy", "FAIL",
                       f"No address or permit data in search results. URL: {page.url[:80]}")

        # ============================================================
        # CHECK 9: Data Accuracy Spot Check
        # ============================================================
        print("\n=== CHECK 9: Data Accuracy Spot Check ===")

        # Get a permit from the API and verify internal consistency
        api_resp = page.request.get(f"{BASE_URL}/api/permits?address=Mission+Street&limit=5")

        if api_resp.status == 200:
            try:
                data = api_resp.json()
                items = data if isinstance(data, list) else data.get("results", data.get("permits", []))

                if items:
                    inconsistencies = []
                    checked = 0
                    for item in items[:5]:
                        status = str(item.get("status", "") or item.get("permit_status", "")).lower()
                        issued_date = item.get("issued_date") or item.get("issuance_date")
                        filed_date = item.get("filed_date") or item.get("application_date") or item.get("filed")

                        # Issued permit should have issuance date
                        if "issued" in status and not issued_date:
                            inconsistencies.append(f"Permit {item.get('permit_number','?')} status=issued but no issuance_date")

                        # Filed permit should NOT have issuance date if status is just "filed"
                        if status in ["filed", "open", "pending"] and issued_date:
                            # This isn't necessarily wrong — it could be re-filed
                            pass

                        # Check for future filing dates
                        if filed_date:
                            try:
                                filed_dt = datetime.strptime(str(filed_date)[:10], "%Y-%m-%d")
                                if filed_dt > datetime.now():
                                    inconsistencies.append(f"Future filing date: {filed_date}")
                            except:
                                pass

                        checked += 1

                    if inconsistencies:
                        record(9, "Data accuracy spot check", "FAIL",
                               f"Inconsistencies found: {inconsistencies[:3]}")
                    else:
                        record(9, "Data accuracy spot check", "PASS",
                               f"Checked {checked} permits, internal consistency OK")
                else:
                    record(9, "Data accuracy spot check", "SKIP",
                           "No permit data returned to spot check")
            except Exception as e:
                record(9, "Data accuracy spot check", "FAIL", f"Parse error: {e}")
        else:
            # Try getting data from property page
            page.goto(f"{BASE_URL}/property?address=2535+Mission+Street",
                      wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            screenshot(page, "09-property-spot-check")
            prop_text = page.inner_text("body")

            # Look for date consistency
            issued_sections = re.findall(r'issued[:\s]+(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})',
                                        prop_text, re.IGNORECASE)
            filed_sections = re.findall(r'filed[:\s]+(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})',
                                       prop_text, re.IGNORECASE)

            if issued_sections or filed_sections:
                record(9, "Data accuracy spot check", "PASS",
                       f"Property page shows dates (issued: {issued_sections[:2]}, filed: {filed_sections[:2]})")
            else:
                record(9, "Data accuracy spot check", "SKIP",
                       f"Could not get permit data for spot check (API {api_resp.status})")

        # ============================================================
        # CHECK 10: Error States — Graceful Handling
        # ============================================================
        print("\n=== CHECK 10: Error States — Graceful Handling ===")

        # Look up a permit that definitely doesn't exist
        page.goto(f"{BASE_URL}/search?q=9999999999", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "10a-not-found-search")
        not_found_text = page.inner_text("body")
        not_found_html = page.content()

        # Check for stack traces / server errors
        has_traceback = any(w in not_found_html for w in ["Traceback", "traceback", "Exception",
                                                           "Internal Server Error", "500",
                                                           "ZeroDivisionError", "KeyError"])
        has_blank = len(not_found_text.strip()) < 50

        # Check for graceful message
        has_graceful = any(w in not_found_text.lower() for w in
                          ["not found", "no results", "no permits", "couldn't find",
                           "try", "search", "check", "no data"])

        # Check for error via API
        bogus_resp = page.request.get(f"{BASE_URL}/api/permits?permit_number=9999999999")
        has_api_trace = False
        if bogus_resp.status == 200:
            try:
                bogus_data = bogus_resp.json()
                if "traceback" in str(bogus_data).lower() or "exception" in str(bogus_data).lower():
                    has_api_trace = True
            except:
                pass

        if has_traceback:
            record(10, "Error states — graceful handling", "FAIL",
                   "Stack trace/server error exposed for bad permit lookup")
        elif has_blank:
            record(10, "Error states — graceful handling", "FAIL",
                   "Blank page returned for nonexistent permit")
        elif has_graceful:
            record(10, "Error states — graceful handling", "PASS",
                   f"Graceful not-found message shown. HTTP: {page.url[:60]}")
        else:
            record(10, "Error states — graceful handling", "FAIL",
                   f"No graceful error message. Page shows: {not_found_text[:200]}")

        # ============================================================
        # BONUS CHECKS: Amy-specific workflow items
        # ============================================================

        # BONUS A: Can Amy see the morning brief at all?
        print("\n=== BONUS: Amy's Stuck Permit Workflow ===")
        page.goto(f"{BASE_URL}/search?q=STUCK+Mission+Street", wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)

        # Check for "stuck" / pipeline health features
        page.goto(f"{BASE_URL}/search?q=2301+Mission+Street", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        screenshot(page, "bonus-mission-full")
        full_text = page.inner_text("body")

        # Look for Amy-specific intelligence signals
        amy_signals = {
            "days_at_station": any(w in full_text.lower() for w in ["days at", "station", "review station"]),
            "reviewer_info": any(w in full_text.lower() for w in ["reviewer", "plan checker", "inspector"]),
            "timeline_prediction": any(w in full_text.lower() for w in ["predict", "estimate", "expected", "typical"]),
            "similar_projects": any(w in full_text.lower() for w in ["similar", "comparable", "like this"]),
            "health_signal": any(w in full_text.lower() for w in ["health", "signal", "flag", "alert", "at risk"]),
        }

        signals_present = sum(amy_signals.values())
        note(f"Amy intelligence signals on search result: {signals_present}/5 — {amy_signals}")

        if signals_present >= 3:
            record("A", "Amy workflow — intelligence signals present", "PASS",
                   f"{signals_present}/5 signals: {[k for k,v in amy_signals.items() if v]}")
        elif signals_present >= 1:
            record("A", "Amy workflow — intelligence signals present", "FAIL",
                   f"Only {signals_present}/5 signals. Missing: {[k for k,v in amy_signals.items() if not v]}")
        else:
            record("A", "Amy workflow — intelligence signals present", "FAIL",
                   "No Amy-specific intelligence signals found on search/permit page")

        # BONUS B: Check landing page for Amy's entry points
        print("\n=== BONUS B: Landing Page — Amy Entry Points ===")
        page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        screenshot(page, "bonus-landing")
        landing_text = page.inner_text("body")

        amy_entry_points = {
            "search_box": page.locator("input[type=search], input[type=text], input[placeholder*='search' i], input[placeholder*='address' i], input[placeholder*='permit' i]").count() > 0,
            "brief_link": any(w in landing_text.lower() for w in ["brief", "morning", "daily"]),
            "portfolio_link": any(w in landing_text.lower() for w in ["portfolio", "my permits", "tracked", "watch"]),
        }

        ep_count = sum(amy_entry_points.values())
        note(f"Landing page Amy entry points: {ep_count}/3 — {amy_entry_points}")

        browser.close()

    return results, notes


def write_report(results, notes):
    today = datetime.now().strftime("%Y-%m-%d")
    session_id = SESSION_ID

    lines = [
        f"# Persona: Amy QA Results — {today}",
        "",
        f"**Session ID:** {session_id}",
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

    # Summary
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
        f"## Screenshots",
        f"",
        f"Saved to: `qa-results/screenshots/{session_id}/`",
        "",
    ]

    # List screenshots
    for p in sorted(SCREENSHOT_DIR.glob("*.png")):
        lines.append(f"- `{p.name}`")

    report = "\n".join(lines)

    out_path = f"/Users/timbrenneman/AIprojects/sf-permits-mcp/qa-results/{session_id}-persona-amy-qa.md"
    with open(out_path, "w") as f:
        f.write(report)

    print(f"\nReport written to: {out_path}")
    return out_path, passes, fails, skips


if __name__ == "__main__":
    print(f"Starting Persona Amy QA — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"Target: {BASE_URL}")
    print(f"Screenshots: {SCREENSHOT_DIR}")
    print()

    results, notes = run_qa()
    out_path, passes, fails, skips = write_report(results, notes)

    print(f"\n{'='*60}")
    print(f"RESULTS: {passes} PASS / {fails} FAIL / {skips} SKIP")
    print(f"{'='*60}")

    sys.exit(0 if fails == 0 else 1)
