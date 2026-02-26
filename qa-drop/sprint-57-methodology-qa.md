# Sprint 57: Methodology Transparency QA Script

## Setup
- Start dev server: `python -c "from web.app import app; app.run(port=5099, debug=False)"`
- Use Playwright headless Chromium

## Steps

### 1. Tool return_structured=False backward compatibility
- Import each tool: estimate_fees, estimate_timeline, predict_permits, required_documents, revision_risk
- Call each with default params (no return_structured)
- PASS: All 5 return `str` type
- FAIL: Any returns tuple

### 2. Tool return_structured=True returns tuple
- Call each tool with `return_structured=True`
- PASS: All 5 return `(str, dict)` tuple
- FAIL: Any does not return tuple

### 3. Methodology dict has required keys
- For each tool's methodology dict, check keys: tool, headline, formula_steps, data_sources, sample_size, data_freshness, confidence, coverage_gaps
- PASS: All 8 keys present in all 5 dicts
- FAIL: Any key missing

### 4. Fee estimate has Cost Revision Risk section
- Call estimate_fees with cost=50000
- PASS: Output contains "Cost Revision Risk" and "ceiling"
- FAIL: Missing revision risk section

### 5. Coverage disclaimers in all tool outputs
- Call each tool with default params
- PASS: All 5 contain "## Data Coverage" section
- FAIL: Any missing Data Coverage

### 6. Navigate to /analyze, submit project
- POST to /analyze with description="Kitchen remodel in SoMa", cost=75000
- PASS: Response 200, HTML contains `methodology-card` class
- FAIL: 4xx/5xx or no methodology card

### 7. Methodology cards expand on click
- Locate `<details class="methodology-card">` elements
- PASS: Elements present without `open` attribute (collapsed default)
- FAIL: Cards missing or pre-expanded

### 8. Coverage gaps render in methodology cards
- Check for `.methodology-gaps` element in HTML
- PASS: At least one gap note rendered
- FAIL: No gap notes

### 9. Methodology card styling
- Check for `.methodology-card` CSS rules in response
- PASS: Styles include border-left, background, font-size
- FAIL: Missing styles

### 10. Shared analysis template has methodology cards
- Read analysis_shared.html template
- PASS: Contains `methodology-card` class and styles
- FAIL: Missing methodology support

### 11. All tests pass
- Run: pytest tests/test_methodology.py tests/test_methodology_ux.py tests/test_pipeline_verification.py -v
- PASS: 83+ tests pass, 0 fail
- FAIL: Any failure

### 12. No regressions
- Run: pytest tests/ -q --ignore=tests/test_tools.py --ignore=tests/test_analyze_plans.py --ignore=tests/e2e/ --ignore=tests/test_ingest_review_metrics.py -k "not (test_no_auth_returns_403 or test_wrong_token_returns_403 or test_ingest_plumbing)"
- PASS: 2,465+ pass
- FAIL: Count below 2,382 (baseline)
