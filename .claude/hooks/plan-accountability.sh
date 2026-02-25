#!/usr/bin/env bash
# Mechanism 2: Plan Accountability
# Called by stop-checkchat.sh. Reads CHECKCHAT message from stdin.
# Checks for descoped items without user approval and BLOCKED items without 3-attempt docs.

set -euo pipefail

# Read message from stdin
MESSAGE=$(cat)

FAILURES=()

# --- Check descoped items ---
DESCOPE_PATTERNS="descoped|deferred|out of scope|dropped|removed from scope|moved to sprint"
APPROVAL_PATTERNS="user approved|per user|asked user|tim approved|tim confirmed"

# Extract lines with descoping language
while IFS= read -r line; do
    [ -z "$line" ] && continue
    # Check if the line (or surrounding context) has approval evidence
    # Get line number
    LINE_NUM=$(echo "$MESSAGE" | grep -n -i -E "$DESCOPE_PATTERNS" | grep -n "$line" | head -1 | cut -d: -f1)

    # Check this line and next 2 lines for approval
    HAS_APPROVAL=false
    CONTEXT=$(echo "$MESSAGE" | grep -i -E "$DESCOPE_PATTERNS" -A 2 | head -10)
    if echo "$CONTEXT" | grep -q -i -E "$APPROVAL_PATTERNS"; then
        HAS_APPROVAL=true
    fi

    if [ "$HAS_APPROVAL" = false ]; then
        # Trim the line for display
        SHORT=$(echo "$line" | head -c 120)
        FAILURES+=("Descoped item '$SHORT' has no user approval evidence")
    fi
done < <(echo "$MESSAGE" | grep -i -E "$DESCOPE_PATTERNS" 2>/dev/null || true)

# --- Check BLOCKED items ---
if echo "$MESSAGE" | grep -q -i "BLOCKED"; then
    # Check that blocked items have attempt documentation
    HAS_ATTEMPTS=false
    if echo "$MESSAGE" | grep -i -E "attempt 1|attempt 2|attempt 3|3 attempts|three attempts" > /dev/null 2>&1; then
        HAS_ATTEMPTS=true
    fi
    if [ "$HAS_ATTEMPTS" = false ]; then
        FAILURES+=("BLOCKED item has no 3-attempt documentation")
    fi
fi

# --- Report ---
if [ ${#FAILURES[@]} -gt 0 ]; then
    for f in "${FAILURES[@]}"; do
        echo "PLAN ACCOUNTABILITY FAIL: $f" >&2
    done
    exit 1
fi

exit 0
