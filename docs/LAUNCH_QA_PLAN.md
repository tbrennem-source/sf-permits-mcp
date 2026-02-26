# Launch QA Plan — sfpermits.ai

_Last updated: QS3 Session C_

## Automated Tests

| Layer | Tool | Count | Command |
|-------|------|-------|---------|
| Unit/Integration | pytest | 3,400+ | `pytest tests/ --ignore=tests/test_tools.py -q` |
| Playwright E2E | pytest + Playwright | 25+ | `pytest tests/e2e/test_scenarios.py -v` |
| Dead link spider | pytest + Flask client | 3 crawls (anon/auth/admin) | `pytest tests/e2e/test_links.py -v` |
| Visual regression | visual_qa.py | 21 pages x 3 viewports | `python scripts/visual_qa.py --url <url> --sprint <sprint>` |

## Smoke Test Checklist (run before every promote-to-prod)

```bash
# 1. Health endpoint — status ok, expected table count
curl -sf https://sfpermits-ai-staging-production.up.railway.app/health | python3 -m json.tool

# 2. Stats API — real numbers (permits > 1M)
curl -sf https://sfpermits-ai-staging-production.up.railway.app/api/stats | python3 -m json.tool

# 3. Landing page renders
curl -sf -o /dev/null -w "%{http_code}" https://sfpermits-ai-staging-production.up.railway.app/

# 4. Search returns results
curl -sf -o /dev/null -w "%{http_code}" "https://sfpermits-ai-staging-production.up.railway.app/search?q=1455+Market+St"

# 5. Methodology page
curl -sf -o /dev/null -w "%{http_code}" https://sfpermits-ai-staging-production.up.railway.app/methodology

# 6. About-data page
curl -sf -o /dev/null -w "%{http_code}" https://sfpermits-ai-staging-production.up.railway.app/about-data

# 7. Robots.txt disallows /admin
curl -sf https://sfpermits-ai-staging-production.up.railway.app/robots.txt | grep /admin

# 8. Full test suite passes
source .venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py -q
```

## Manual Test Scripts (15 Critical Journeys)

### Journey 1: First Visit Discovery
1. Open sfpermits.ai in incognito
2. Landing page loads with hero section, search box, feature cards, stats
3. Nav shows Search + greyed premium features with "Sign up" badges
4. Scroll down — capability cards and social proof visible

### Journey 2: Anonymous Address Search
1. Enter "1455 Market St" in search box
2. Results page loads with permit data
3. Intel preview panel appears (HTMX)
4. Premium cards show lock + signup CTA

### Journey 3: Anonymous Permit Prep Preview
1. Enter "kitchen remodel" in project description on landing page
2. Review path (OTC vs in-house) and timeline estimate appear
3. Additional cards (fees, documents) show locked with signup CTA

### Journey 4: Beta Request / Signup
1. Click "Create free account" or navigate to /beta-request
2. Fill out email, name, reason
3. Confirmation message appears
4. (Admin) Approve request in admin/beta-requests

### Journey 5: Magic Link Login
1. Enter email on login page
2. Click send link
3. Check email for magic link
4. Click link → redirected to dashboard

### Journey 6: Authenticated Dashboard
1. After login, / shows full app (not marketing landing)
2. Nav shows all features ungreyed
3. Search works with full intel panel
4. Account, Portfolio, Brief accessible

### Journey 7: Property Report
1. Search for address, click property link
2. Report page loads with property details
3. Permit history table rendered
4. Health signals (if available) shown

### Journey 8: Morning Brief
1. Navigate to /brief
2. Brief loads with watched property updates
3. "What Changed" section shows specific permit details
4. Pipeline health warnings (if any) visible

### Journey 9: Plan Analysis Upload
1. Navigate to account/analyses
2. Upload a test PDF
3. Analysis queued, progress shown
4. Results render with EPR checks + AI annotations

### Journey 10: Permit Prep (5-tool analysis)
1. Enter project description + address
2. System runs predict_permits, estimate_timeline, estimate_fees, required_documents, revision_risk
3. Results render in tabbed layout
4. Methodology cards expand to show calculation details

### Journey 11: Admin Dashboard
1. Login as admin
2. Navigate to /admin/ops
3. Default tab loads automatically
4. Switch tabs — each loads within 5s
5. DQ tab shows index health, cache status

### Journey 12: Feedback Triage
1. As admin, navigate to /admin/feedback
2. Feedback queue renders with items
3. Review a feedback item
4. Update status (reviewed/resolved)

### Journey 13: Mobile Experience
1. Open sfpermits.ai on iPhone SE (375px viewport)
2. No horizontal overflow
3. Nav stacks correctly
4. Search input stacks below 480px
5. Touch targets >= 44px

### Journey 14: Share Analysis
1. Complete a 5-tool analysis
2. Click Share, enter 2 recipient emails
3. Recipients receive email with link
4. Click link → shared analysis renders without login

### Journey 15: Portfolio Management
1. Navigate to /portfolio
2. View watched properties
3. Add a new watch (address or block/lot)
4. Property appears in portfolio

## Visual Regression Process

1. **Before sprint**: Capture baselines
   ```bash
   TEST_LOGIN_SECRET=xxx python scripts/capture_baselines.py \
       https://sfpermits-ai-staging-production.up.railway.app sprintNN
   ```

2. **After sprint**: Run comparison
   ```bash
   TEST_LOGIN_SECRET=xxx python scripts/visual_qa.py \
       --url https://sfpermits-ai-staging-production.up.railway.app --sprint sprintNN
   ```

3. **Review diffs**: Any pages with >5% pixel change flagged for review

4. **Update baselines**: After review, re-run with `--capture-goldens` to update

5. **Journey recordings** (optional):
   ```bash
   TEST_LOGIN_SECRET=xxx python scripts/visual_qa.py \
       --url ... --sprint sprintNN --journeys
   ```

## E2E Coverage Map

| Scenario ID | Description | Automated? | Test File | Test Name |
|-------------|-------------|------------|-----------|-----------|
| SCENARIO-34 | CSP blocks injected external script | Yes | test_scenarios.py | test_search_xss_sanitized |
| SCENARIO-37 | Anonymous landing page renders | Yes | test_scenarios.py | test_landing_page_renders, test_landing_page_has_stats, test_landing_page_has_cta |
| SCENARIO-38 | Anonymous search with public results | Yes | test_scenarios.py | test_search_returns_results, test_search_works_authenticated |
| SCENARIO-39 | Authenticated user bypasses landing | Yes | test_scenarios.py | test_dashboard_renders_after_login |
| SCENARIO-40 | Login required for premium features | Yes | test_scenarios.py | test_premium_routes_redirect, test_account_page_accessible, test_non_admin_cannot_access_ops |
| SCENARIO-41 | Gated navigation for anonymous | Yes | test_scenarios.py | test_login_page_accessible, test_premium_routes_redirect |
| SCENARIO-49 | Beta request form | Yes | test_scenarios.py | test_beta_request_page |
| SCENARIO-51 | Admin views beta requests | Yes | test_scenarios.py | test_admin_beta_requests_accessible |
| SCENARIO-7 | Admin Ops tabs load | Yes | test_scenarios.py | test_admin_ops_accessible |
| SCENARIO-72 | Mobile layout (no horizontal scroll) | Manual | — | Journey 13 |
| SCENARIO-1-5 | Severity/health scoring | Yes | tests/test_severity*.py | Unit tests |
| SCENARIO-6 | Admin Ops timeout recovery | Manual | — | Journey 11 |
| SCENARIO-8 | Hash routing for Admin Ops | Manual | — | Journey 11 |
| SCENARIO-12 | DQ bulk index health | Manual | — | Journey 11 |
| SCENARIO-14-16 | Intent router / email / exact match | Yes | tests/test_intent*.py | Unit tests |
| SCENARIO-17-24 | Plan analysis UX | Manual | — | Journey 9, 10 |
| SCENARIO-25 | Morning brief changes | Manual | — | Journey 8 |
| SCENARIO-30-31 | SQL injection / path traversal | Yes | tests/test_security*.py | Unit tests |
| SCENARIO-32-33 | Kill switch / cost threshold | Yes | tests/test_cost*.py | Unit tests |
| SCENARIO-35-36 | Bot blocking / rate limiting | Yes | tests/test_rate*.py | Unit tests |
| SCENARIO-42 | Staging banner | Manual | — | Visual check on staging |
| SCENARIO-43 | Test-login 404 on prod | Manual | — | Verify on prod |
| SCENARIO-44-45 | Permit preview / kitchen fork | Manual | — | Journey 3 |
| SCENARIO-46 | Welcome banner for new users | Manual | — | Journey 6 |
| SCENARIO-47-48 | Share analysis | Manual | — | Journey 14 |
| SCENARIO-50 | Shared-link signup | Manual | — | Journey 14 |
| SCENARIO-52-57 | Morning brief advanced | Manual | — | Journey 8 |
| SCENARIO-58-60 | Permit prediction | Yes | tests/test_predict*.py | Unit tests |
| SCENARIO-61-64 | Analysis UX methodology | Manual | — | Journey 10 |
| SCENARIO-65-66 | Entity resolution | Yes | tests/test_entities*.py | Unit tests |
| SCENARIO-67 | Trade permits in search | Yes | tests/test_search*.py | Unit tests |
| SCENARIO-68-69 | Project auto-creation | Yes | tests/test_project*.py | Unit tests |
| SCENARIO-70-71 | Email notifications | Yes | tests/test_email*.py | Unit tests |
| SCENARIO-73 | ADU landing page | Manual | — | ADU page check |

### Coverage Summary
- **Automated (Playwright E2E)**: Scenarios 7, 34, 37-41, 49, 51
- **Automated (unit/integration)**: Scenarios 1-5, 14-16, 26-28, 30-36, 58-60, 65-71
- **Manual only**: Scenarios 6, 8-13, 17-25, 42-48, 50, 52-57, 61-64, 72-73
- **Total coverage**: 73/73 scenarios have at least a manual test path
