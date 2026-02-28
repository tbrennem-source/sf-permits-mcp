# CHANGELOG — Sprint 83-A

## fix: update stale landing test assertions for Sprint 69 redesign

**Date:** 2026-02-27
**Agent:** Sprint 83-A (test fix)
**File changed:** `tests/test_landing.py`

### What changed

Two test assertions in `TestLandingPage` were stale relative to the Sprint 69 landing page redesign:

**`test_landing_has_feature_cards`**
- Old: asserted `"Permit Search"`, `"Plan Analysis"`, `"Morning Brief"`, `"Timeline Estimation"` (pre-Sprint 69 capability card labels)
- New: asserts `"Do I need a permit?"`, `"How long will it take?"`, `"Is my permit stuck?"` (the three capability section headings in the redesigned question-form layout)

**`test_landing_has_stats`**
- Old: asserted `"1.1M+"` and `"Permits tracked"` (pre-Sprint 69 stat display)
- New: asserts `"SF building permits"` and `"City data sources"` (the actual stat labels in the redesigned stats section)

### Test result

All 23 tests in `tests/test_landing.py` pass.
