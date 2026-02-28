# CHANGELOG — Sprint 94, Agent 1D (MCP Demo Fix + Integration QA)

## Summary

Fixed a critical animation bug in the MCP demo component where the Claude response content never became visible during the scroll-triggered animation sequence.

## Root Cause

`mcp-demo.js` `animateSlide()` function used `slide.querySelector('.mcp-msg__bubble')` to find the bubble containing typed lines and tables to animate. Because `querySelector` returns the **first** matching element, it always returned the **user message bubble** (`.mcp-msg--user .mcp-msg__bubble`), which contains no `.mcp-typed-line`, `.mcp-response-table`, or `.mcp-stacked-cards` children. Result: `children` was always an empty NodeList, and all Claude response content remained invisible (opacity: 0) indefinitely.

## Fix

**`web/static/mcp-demo.js`** — Changed the selector from:
```js
var bubble = slide.querySelector('.mcp-msg__bubble');
```
to:
```js
var bubble = slide.querySelector('.mcp-msg--claude .mcp-msg__bubble');
```

This correctly targets the Claude response bubble (the one that contains animated content), not the user input bubble.

## Files Modified

- `web/static/mcp-demo.js` — Fix bubble querySelector to target `.mcp-msg--claude .mcp-msg__bubble`

## Files Created

- `tests/test_mcp_demo_fix.py` — 33 tests covering:
  - Render integrity (section present, CSS/JS linked, no crash)
  - Demo content (all 3 tool badges, all 3 transcript contents)
  - CTA section (button, href, 3 steps, nav controls)
  - Template source checks (demo slides, tool badges, CTA href)
  - JS animation fix verification (correct bubble selector, IntersectionObserver, reduced motion)

## Integration QA Results (Flask test client)

All 11 landing page checks passed:
- mcp-demo-section class present
- mcp-demo-slide class present (3 slides)
- mcp-demo.css linked
- mcp-demo.js linked
- Demo 2 tool badge: `what_if_simulator`
- Demo 1 tool badge: `diagnose_stuck_permit`
- Demo 6 tool badge: `estimate_timeline`
- "Connect your AI" CTA present
- nav prev/next buttons present
- `id="mcp-demo"` present

## Test Results

- `tests/test_mcp_demo_fix.py`: 33/33 PASS
- `tests/test_mcp_demo.py` (other agent's tests): 43/43 PASS (all pass including `test_section_has_correct_id`)
- Full suite (`tests/` excluding `test_tools.py` and `e2e/`): 4,719 pass, 2 fail (pre-existing failures in test_tools_polish_a.py and unrelated to MCP demo)

## Pre-existing Failures (not caused by this agent)

- `tests/test_tools_polish_a.py::TestStationPredictorEmptyState::test_empty_state_hint_text` — expects hint text in `station_predictor.html` that another sprint agent is responsible for adding; this template is not in Agent 1D's file ownership
