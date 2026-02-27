# QA: QS5-C Trade Permit Bridge + Orphan Inspections

## Tests (run from worktree root)
```
source .venv/bin/activate && pytest tests/test_qs5_c_bridges.py -v
```

## Checks

1. [NEW] _check_orphan_inspections returns structured DQ result with all required fields (name, category, value, status, detail) — PASS/FAIL
2. [NEW] Orphan inspection thresholds match spec: green <5%, yellow 5-15%, red >15% — PASS/FAIL
3. [NEW] _check_trade_permit_counts returns green when both tables populated — PASS/FAIL
4. [NEW] _check_trade_permit_counts returns red when a table is empty — PASS/FAIL
5. [NEW] EXPECTED_TABLES includes boiler_permits and fire_permits — PASS/FAIL
6. [NEW] Investigation findings documented in CHANGELOG-qs5-c.md — PASS/FAIL
7. [NEW] boiler_permits schema has block/lot columns — PASS/FAIL
8. [NEW] fire_permits schema does NOT have block/lot columns — PASS/FAIL
9. [NEW] Orphan check filters to reference_number_type='permit' (excludes complaints) — PASS/FAIL
10. [NEW] Both new checks registered in run_all_checks() universal_checks list — PASS/FAIL
