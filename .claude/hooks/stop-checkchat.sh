#!/usr/bin/env bash
# Mechanism 1: CHECKCHAT Pre-flight Gate
# Stop hook. Fires when agent finishes responding. Detects CHECKCHAT content
# and blocks session close unless QA evidence exists.
#
# Input (stdin): JSON with fields including:
#   - last_assistant_message: the assistant's response text
#   - stop_hook_active: true if already retrying after a previous block

set -euo pipefail

HOOKS_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$HOOKS_DIR/../.." && pwd)"
LOCK_FILE="$HOOKS_DIR/.stop_hook_fired"

# Read the JSON input from stdin
RAW_INPUT=$(cat)

# Extract last_assistant_message from JSON; fall back to raw input if parsing fails
MESSAGE=$(echo "$RAW_INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('last_assistant_message',''))" 2>/dev/null || echo "$RAW_INPUT")

# --- Only enforce on CHECKCHAT messages ---
# Match the EXACT markdown H2 header "## CHECKCHAT", not the word in conversation
if ! echo "$MESSAGE" | grep -q "## CHECKCHAT"; then
    exit 0
fi

# --- Infinite loop prevention ---
# Built-in: stop_hook_active=true means we already blocked once
STOP_ACTIVE=$(echo "$RAW_INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('stop_hook_active',False))" 2>/dev/null || echo "False")
if [ "$STOP_ACTIVE" = "True" ]; then
    rm -f "$LOCK_FILE"
    exit 0
fi
# Fallback: temp file guard
if [ -f "$LOCK_FILE" ]; then
    rm -f "$LOCK_FILE"
    exit 0
fi

FAILURES=()

# --- DeskCC detection ---
# DeskCC sessions contain "DeskRelay" but not "BUILD"
IS_DESKCC=false
if echo "$MESSAGE" | grep -q -i "DeskRelay" && ! echo "$MESSAGE" | grep -q "BUILD"; then
    IS_DESKCC=true
fi

# --- Check 1: Screenshots exist ---
if [ "$IS_DESKCC" = false ]; then
    SCREENSHOT_DIR="$REPO_ROOT/qa-results/screenshots"
    HAS_SCREENSHOTS=false
    if [ -d "$SCREENSHOT_DIR" ]; then
        # Find PNG files and verify magic bytes
        while IFS= read -r png_file; do
            if file "$png_file" 2>/dev/null | grep -q "PNG image data"; then
                HAS_SCREENSHOTS=true
                break
            fi
        done < <(find "$SCREENSHOT_DIR" -name "*.png" -type f 2>/dev/null)
    fi
    if [ "$HAS_SCREENSHOTS" = false ]; then
        FAILURES+=("No PNG screenshots found in qa-results/screenshots/. Run Playwright QA subagents first.")
    fi
fi

# --- Check 2: QA results file with PASS/FAIL ---
HAS_RESULTS=false
for results_file in "$REPO_ROOT"/qa-results/*-results.md; do
    [ -f "$results_file" ] || continue
    if grep -E "(PASS|FAIL)" "$results_file" > /dev/null 2>&1; then
        HAS_RESULTS=true
        break
    fi
done
if [ "$HAS_RESULTS" = false ]; then
    FAILURES+=("No QA results file found matching qa-results/*-results.md with PASS/FAIL lines.")
fi

# --- Check 3: Scenarios modified ---
SCENARIOS_MODIFIED=false
if cd "$REPO_ROOT" && git diff HEAD -- scenarios-pending-review.md 2>/dev/null | grep -q "^+"; then
    SCENARIOS_MODIFIED=true
fi
# Also check if scenarios file has uncommitted changes
if cd "$REPO_ROOT" && git diff --cached -- scenarios-pending-review.md 2>/dev/null | grep -q "^+"; then
    SCENARIOS_MODIFIED=true
fi
# Check for untracked or modified in working tree
if cd "$REPO_ROOT" && git status --porcelain scenarios-pending-review.md 2>/dev/null | grep -q "[MA?]"; then
    SCENARIOS_MODIFIED=true
fi
if [ "$SCENARIOS_MODIFIED" = false ]; then
    FAILURES+=("scenarios-pending-review.md has no changes this session. Add scenarios before closing.")
fi

# --- Check 4: Plan accountability ---
PLAN_CHECK_OUTPUT=$(echo "$MESSAGE" | bash "$HOOKS_DIR/plan-accountability.sh" 2>&1) || {
    # plan-accountability.sh failed — capture its stderr as failures
    while IFS= read -r line; do
        [ -n "$line" ] && FAILURES+=("$line")
    done <<< "$PLAN_CHECK_OUTPUT"
}

# --- Report ---
if [ ${#FAILURES[@]} -gt 0 ]; then
    # Mark that we've blocked once (infinite loop prevention)
    touch "$LOCK_FILE"
    echo "CHECKCHAT BLOCKED — missing evidence:" >&2
    for f in "${FAILURES[@]}"; do
        echo "  - $f" >&2
    done
    echo "" >&2
    echo "Fix the above issues, then try CHECKCHAT again. You get ONE retry." >&2
    exit 2
fi

# All checks passed — clean up lock if it exists
rm -f "$LOCK_FILE"
exit 0
