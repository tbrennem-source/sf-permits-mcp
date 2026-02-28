# CHANGELOG — Sprint 82-C

## fix: prod gate ratchet tracks specific failing checks (Sprint 82-C)

**Date:** 2026-02-27

### Problem
The hotfix ratchet in `scripts/prod_gate.py` triggered HOLD on any consecutive score-3 sprint, regardless of whether the *same issues* were present. QS8 got HOLD because QS7 was also score-3, even though the failing checks were completely different.

### Fix
`scripts/prod_gate.py` — ratchet logic rewritten:

1. **On score <= 3:** Write failing check names to a new `## Failing checks` section in `qa-results/HOTFIX_REQUIRED.md` (in addition to the existing issues narrative).
2. **On next score-3 run:** Parse the `## Failing checks` section from the previous file. Compare via set intersection.
3. **Ratchet triggers (HOLD):** Only when at least one of the same check names is still failing.
4. **Ratchet resets (PROMOTE):** When failing checks are entirely different — overwrite the hotfix file with the new check names, no HOLD.
5. **No previous file:** First occurrence, no ratchet (previous behavior preserved).
6. **Score >= 4:** Hotfix file deleted as before (issues resolved).

The HOLD reason message now names the specific overlapping checks, making it clear what needs to be fixed.

### Tests Added
`tests/test_prod_gate_ratchet.py` — 13 new tests:

- `TestRatchetTriggersOnSameChecks`: ratchet fires on exact match + partial overlap
- `TestRatchetResetsOnDifferentChecks`: no ratchet on different checks; file overwritten; legacy files without structured section do not trigger
- `TestNoRatchetOnFirstOccurrence`: no file = first occurrence = PROMOTE + file created
- `TestRatchetClearsAfterAllGreen`: score 4 and score 5 both clear the file; cleared file means next score-3 is treated as first occurrence
- `TestReadPreviousFailingChecks`: parse helper correctly reads multiple checks, returns empty for missing/malformed files

### Files Changed
- `scripts/prod_gate.py` — ratchet block rewritten (~80 lines)
- `tests/test_prod_gate_ratchet.py` — new file, 13 tests (all passing)
