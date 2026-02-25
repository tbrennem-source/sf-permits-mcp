#!/usr/bin/env bash
# Mechanism 3: Build/Verify Separation
# PreToolUse hook on Bash. Blocks Playwright execution commands in main agent.
# Subagents (detected by CLAUDE_SUBAGENT=true or worktree CWD) are allowed through.

set -euo pipefail

# Read the tool input from stdin (JSON with "command" field)
INPUT=$(cat)

# Extract the command being run
COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',d.get('input',{})).get('command',''))" 2>/dev/null || echo "$INPUT")

# --- Subagent bypass ---
# If CLAUDE_SUBAGENT is set, allow everything
if [ "${CLAUDE_SUBAGENT:-}" = "true" ]; then
    exit 0
fi

# If CWD is inside a worktree subfolder (nested agent worktree), allow
if echo "${PWD:-}" | grep -q ".claude/worktrees/.*/\.claude/worktrees/"; then
    exit 0
fi

# --- Blocked patterns ---
# Only block actual Playwright EXECUTION commands, not installation or pytest
BLOCKED_PATTERNS=(
    "playwright"
    "chromium.launch"
    "browser.new_context"
    "page\.goto"
    "page\.screenshot"
    "page\.click"
    "expect(page"
    "sync_playwright"
)

# --- Allowed patterns (override blocked) ---
# These are OK even if they contain blocked words
ALLOWED_PATTERNS=(
    "pytest"
    "python -m pytest"
    "pip install"
    "pip3 install"
    "grep"
    "cat "
    "git "
    "curl "
    "head "
    "tail "
    "wc "
    "ls "
    "echo "
)

# First check if it matches an allowed pattern
for allowed in "${ALLOWED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -q "$allowed"; then
        exit 0
    fi
done

# Then check for blocked patterns
for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -q -i "$pattern"; then
        echo "BLOCKED: Playwright commands must run in QA subagents. Use the Task tool to spawn a QA agent." >&2
        exit 2
    fi
done

exit 0
