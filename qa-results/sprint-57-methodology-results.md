# Public QA Results — 2026-02-25

Sprint 57: Methodology Transparency

| # | Check | Status | Notes |
|---|-------|--------|-------|
| 1a | estimate_fees returns str (no return_structured) | PASS | |
| 1b | estimate_timeline returns str | PASS | |
| 1c | predict_permits returns str | PASS | |
| 1d | required_documents returns str | PASS | |
| 1e | revision_risk returns str | PASS | |
| 2a | estimate_fees returns (str, dict) with return_structured=True | PASS | |
| 2b | estimate_timeline returns (str, dict) | PASS | |
| 2c | predict_permits returns (str, dict) | PASS | |
| 2d | required_documents returns (str, dict) | PASS | |
| 2e | revision_risk returns (str, dict) | PASS | |
| 3a | estimate_fees methodology dict has all 8 required keys | PASS | keys: tool, headline, formula_steps, data_sources, sample_size, data_freshness, confidence, coverage_gaps |
| 3b | estimate_timeline methodology dict has all 8 required keys | PASS | |
| 3c | predict_permits methodology dict has all 8 required keys | PASS | |
| 3d | required_documents methodology dict has all 8 required keys | PASS | |
| 3e | revision_risk methodology dict has all 8 required keys | PASS | |
| 4 | estimate_fees(cost=50000) has "Cost Revision Risk" and "ceiling" | PASS | bracket: $25K-$100K, rate 28.6%, ceiling calculated |
| 5a | estimate_fees has "## Data Coverage" section | PASS | |
| 5b | estimate_timeline has "## Data Coverage" section | PASS | |
| 5c | predict_permits has "## Data Coverage" section | PASS | |
| 5d | required_documents has "## Data Coverage" section | PASS | |
| 5e | revision_risk has "## Data Coverage" section | PASS | |
| 6 | POST /analyze returns 200 with methodology-card in HTML | PASS | Flask test client |
| 7 | methodology-card <details> elements default collapsed (no open attr) | PASS | |
| 8 | .methodology-gaps element present with coverage gap notes | PASS | "Planning fees not included" visible |
| 9 | .methodology-card CSS present (border-left, background, font-size) | PASS | .methodology-sources and .methodology-gaps also present |
| 10 | analysis_shared.html has methodology-card class + "How we calculated this" | PASS | lines 81-86, 145-154 |
| 11 | pytest test_methodology.py + test_methodology_ux.py + test_pipeline_verification.py | PASS | 83/83 passed |
| 12 | Full regression suite (filtered) | PASS | 2465 passed, 1 skipped, 0 failed (baseline: 2382) |

Screenshots: qa-results/screenshots/sprint-57/methodology-qa-summary.png
