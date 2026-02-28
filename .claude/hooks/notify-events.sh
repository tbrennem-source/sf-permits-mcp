#!/usr/bin/env bash
# Notification Events Hook
# PostToolUse hook on Write and Bash tools.
# Triggers differentiated notification sounds based on CC workflow events.
#
# Detects:
#   1. Write to qa-results/ with FAIL content  → qa-fail sound
#   2. Write containing "CHECKQUAD" + "COMPLETE" → terminal-done sound
#   3. Bash command: git push origin prod       → prod-promoted sound
#
# Input (stdin): JSON with tool_input fields.
#   Write: tool_input.file_path, tool_input.content
#   Bash:  tool_input.command

set -euo pipefail

# Resolve the repo root so notify.sh can be called from any CWD
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# hooks are at .claude/hooks/ — repo root is two levels up
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
NOTIFY="$REPO_ROOT/scripts/notify.sh"

# Bail silently if notify.sh doesn't exist yet (bootstrap safety)
if [ ! -x "$NOTIFY" ]; then
    exit 0
fi

# Read stdin once
INPUT=$(cat)

# Determine which tool fired this hook
TOOL_NAME=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('tool_name', d.get('tool', '')))
" 2>/dev/null || echo "")

# -----------------------------------------------------------------------
# Write tool events
# -----------------------------------------------------------------------
if [ "$TOOL_NAME" = "Write" ] || [ -z "$TOOL_NAME" ]; then
    FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('file_path', ''))
" 2>/dev/null || echo "")

    CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('content', ti.get('new_string', '')))
" 2>/dev/null || echo "")

    # Rule 1: qa-results/ write with FAIL content
    if echo "$FILE_PATH" | grep -q "qa-results/"; then
        if echo "$CONTENT" | grep -q "FAIL"; then
            "$NOTIFY" qa-fail "QA failure detected" &
        fi
    fi

    # Rule 2: CHECKQUAD COMPLETE pattern
    if echo "$CONTENT" | grep -q "CHECKQUAD" && echo "$CONTENT" | grep -q "COMPLETE"; then
        "$NOTIFY" terminal-done "Terminal complete" &
    fi
fi

# -----------------------------------------------------------------------
# Bash tool events
# -----------------------------------------------------------------------
if [ "$TOOL_NAME" = "Bash" ]; then
    COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('command', ''))
" 2>/dev/null || echo "")

    # Rule 3: prod push
    if echo "$COMMAND" | grep -q "git push origin prod"; then
        "$NOTIFY" prod-promoted "Promoted to prod" &
    fi
fi

exit 0
