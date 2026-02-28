## SUGGESTED SCENARIO: Notification system silenced during CI or non-interactive runs
**Source:** scripts/notify.sh, NOTIFY_ENABLED check
**User:** admin
**Starting state:** NOTIFY_ENABLED=0 is set in the shell environment
**Goal:** Run sprint agents without triggering audio alerts on a headless server or CI machine
**Expected outcome:** notify.sh exits immediately without playing any sound or opening notification center; no errors emitted
**Edge cases seen in code:** NOTIFY_ENABLED check must happen before the case statement so afplay is never reached
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: QA failure triggers audible alert automatically
**Source:** .claude/hooks/notify-events.sh, qa-fail detection
**User:** admin
**Starting state:** Agent writes a QA results file to qa-results/ containing the word FAIL
**Goal:** Tim hears a distinct low tone immediately when a QA failure is written without having to watch the terminal
**Expected outcome:** Basso sound plays on the local machine within seconds of the write; macOS notification center shows "QA failure detected" under sfpermits.ai title
**Edge cases seen in code:** Hook only fires for qa-results/ path AND "FAIL" substring — a file in qa-results/ with only PASSes should not trigger the alert
**CC confidence:** high
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Prod promotion triggers celebratory sound
**Source:** .claude/hooks/notify-events.sh, prod push detection
**User:** admin
**Starting state:** Tim runs the prod promotion ceremony: git push origin prod
**Goal:** Hear audible confirmation that the prod push command was issued
**Expected outcome:** Funk sound plays; notification center shows "Promoted to prod" under sfpermits.ai
**Edge cases seen in code:** Hook only matches "git push origin prod" — git push origin main should not trigger prod-promoted
**CC confidence:** medium
**Status:** PENDING REVIEW

## SUGGESTED SCENARIO: Terminal CHECKQUAD COMPLETE signals via Glass tone
**Source:** .claude/hooks/notify-events.sh, CHECKQUAD COMPLETE pattern
**User:** admin
**Starting state:** Agent writes a CHECKQUAD session close artifact containing both "CHECKQUAD" and "COMPLETE"
**Goal:** T0 orchestrator hears Glass tone as each T1-T4 terminal finishes without watching four terminals simultaneously
**Expected outcome:** Glass sound plays once per terminal close; does not fire for mid-session writes that don't contain both keywords
**Edge cases seen in code:** Pattern requires BOTH keywords in the written content — a file containing "CHECKQUAD" alone (e.g., the CLAUDE.md documentation update) should not trigger the sound
**CC confidence:** medium
**Status:** PENDING REVIEW
