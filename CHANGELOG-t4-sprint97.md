# CHANGELOG — T4 Sprint 97 (Agent 4D)

## Differentiated Notification Sounds for CC Workflow Events

**Branch:** worktree-agent-aebcb9f4
**Commit:** 61e2d94

### What was built

#### scripts/notify.sh (new, executable)
Bash script for differentiated audio notifications. Maps workflow events to distinct macOS system sounds:
- `agent-done` → Tink (light, brief — individual agent signal)
- `terminal-done` → Glass (clear, ringing — T1-T4 completion)
- `sprint-done` → Hero (triumphant — full sprint done)
- `qa-fail` → Basso (deep, attention-getting)
- `prod-promoted` → Funk (celebratory)
- fallback → Pop (neutral)

Fires `afplay` in background, then `osascript` for macOS notification center. Respects `NOTIFY_ENABLED=0` env var for silent/CI environments. Early-exit guard placed before case statement.

#### .claude/hooks/notify-events.sh (new, executable)
PostToolUse hook (Write + Bash) with three detection rules:
1. Write to `qa-results/` containing "FAIL" → `qa-fail` sound
2. Write containing "CHECKQUAD" AND "COMPLETE" → `terminal-done` sound
3. Bash command containing `git push origin prod` → `prod-promoted` sound

Hook is non-blocking (always exits 0). Audio fires in background subshell. Resolves REPO_ROOT from hook file path so it works from any CWD.

#### .claude/settings.json (modified)
Added `notify-events.sh` to PostToolUse hooks for both `Write` and `Bash` matchers. Existing Write hooks (detect-descope.sh, test-hygiene-hook.sh) preserved and ordered first.

#### CLAUDE.md (appended — section 14)
Documents the notification system: sound map table, CLI usage examples, hook detection logic, how to add new event types, list of available macOS system sounds, and NOTIFY_ENABLED disable pattern.

#### tests/test_notify.py (new)
13 tests covering:
- File existence and executability
- All 5 named event types (agent-done, terminal-done, sprint-done, qa-fail, prod-promoted)
- Default fallback case presence
- NOTIFY_ENABLED check presence and correct comparison value
- Disabled early-exit behavior via subprocess
- afplay and osascript presence
- Sound distinctness (≥5 unique sound files)

All 13 tests pass.

### Files touched
| File | Action |
|------|--------|
| `scripts/notify.sh` | CREATE |
| `.claude/hooks/notify-events.sh` | CREATE |
| `.claude/settings.json` | MODIFY |
| `CLAUDE.md` | APPEND (section 14) |
| `tests/test_notify.py` | CREATE |

### Files NOT touched (per ownership matrix)
- `web/templates/*`, `web/static/*`, `web/routes_*.py` — not in scope
- Existing hooks: stop-checkchat.sh, block-playwright.sh, plan-accountability.sh, detect-descope.sh, test-hygiene-hook.sh
