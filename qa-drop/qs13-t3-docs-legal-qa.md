# QS13-T3: Docs + Legal + Directory QA

**Session:** QS13-T3
**Branch:** worktree-qs13-t3 (merged to main)
**Features:** /docs API page, /privacy, /terms, DIRECTORY_SUBMISSION.md, qa_directory_readiness.py

---

## Automated Checks (pytest)

- [ ] `python -m pytest tests/test_docs_page.py tests/test_legal_pages.py tests/test_directory_package.py -v`
- [ ] Expected: 31 PASS, 0 FAIL
- [ ] Full suite: `pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -q`
- [ ] Expected: 4903+ passed, 0 failed

## Design Token Compliance

- [ ] Run: `python scripts/design_lint.py --changed --quiet`
- [ ] Score: 5/5 (confirmed clean)
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Footer links use --text-secondary (not --text-tertiary)
- [ ] No new components (no DESIGN_COMPONENT_LOG.md updates needed)

---

## Route Smoke Tests (Playwright or curl)

### 1. GET /docs → 200
**PASS criterion:** Response 200, contains "API Documentation"
```bash
curl -s -o /dev/null -w "%{http_code}" https://sfpermits-ai-staging-production.up.railway.app/docs
# expect: 200
```

### 2. /docs contains 7 category sections
**PASS criterion:** All 7 category headings visible: Search & Lookup, Analytics, Intelligence, Advanced, Plan Analysis, Network, System

### 3. /docs lists 34 tools
**PASS criterion:** At least 30 tool names appear in the page (some may be below fold)

### 4. /docs quick start section present
**PASS criterion:** "Connect via Claude.ai" heading and 3-step instructions visible

### 5. /docs rate limits table present
**PASS criterion:** Table with "Demo", "Professional", "Unlimited" tiers visible

### 6. GET /privacy → 200
**PASS criterion:** Response 200, "Privacy Policy" in page title/heading

### 7. /privacy key sections present
**PASS criterion:** "What We Collect", "What We Don't Do", "Third Parties", "MCP Server" sections visible

### 8. GET /terms → 200
**PASS criterion:** Response 200, "Terms of Service" in page title/heading

### 9. /terms key sections present
**PASS criterion:** "Beta Status", "Data Accuracy", "Acceptable Use" sections visible
**PASS criterion:** "This is not legal advice" notice box visible

### 10. /privacy links to /terms and vice versa
**PASS criterion:** /privacy page has link to /terms; /terms page has link to /privacy

### 11. /docs links to /privacy and /terms
**PASS criterion:** /docs page footer/content has links to /privacy and /terms

### 12. All three pages accessible without login
**PASS criterion:** None of the three pages redirect to /auth/login

---

## Directory Package Checks (no server needed)

### 13. DIRECTORY_SUBMISSION.md exists and complete
**PASS criterion:** `ls docs/DIRECTORY_SUBMISSION.md` exists
**PASS criterion:** File contains: server URL, /docs URL, /privacy URL, /terms URL, OAuth mention, 34 tool count, 5 example prompts

### 14. qa_directory_readiness.py importable
**PASS criterion:** `python scripts/qa_directory_readiness.py --help` exits 0

### 15. qa_directory_readiness.py runs against staging (quick mode)
**PASS criterion:** `python scripts/qa_directory_readiness.py --url https://sfpermits-mcp-api-production.up.railway.app --web-url https://sfpermits-ai-staging-production.up.railway.app --quick`
**PASS criterion:** Health check PASS, /docs PASS, /privacy PASS, /terms PASS

---

## Edge Cases

### 16. /docs renders with no auth cookie
**PASS criterion:** Private/incognito window → /docs returns full page (not login redirect)

### 17. /privacy and /terms render with no auth cookie
**PASS criterion:** Same — public pages, no auth required
