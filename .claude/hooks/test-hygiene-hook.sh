#!/usr/bin/env bash
# Mechanism 5: Test Hygiene Warning
# PostToolUse hook on Write. Fires when an agent writes to tests/.
# Warns on anti-patterns that cause cross-contamination and env leaks.
# Non-blocking (exit 0, warning to stderr).
#
# Input (stdin): JSON with fields including:
#   - tool_input.file_path: path of the file written
#   - tool_input.content: content written to the file

set -euo pipefail

# Read the tool output from stdin
INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('file_path', ''))
" 2>/dev/null || echo "")

# Only check files in tests/
if ! echo "$FILE_PATH" | grep -q "/tests/"; then
    exit 0
fi

# Only check .py files
if ! echo "$FILE_PATH" | grep -q "\.py$"; then
    exit 0
fi

# Extract file content
CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('content', ''))
" 2>/dev/null || echo "")

WARNINGS=()

# Check 1: os.environ[] assignment (not .get/.pop/.setdefault, not in monkeypatch lines)
if echo "$CONTENT" | grep -n 'os\.environ\[' | grep -v 'monkeypatch' | grep -v '\.get\|\.pop\|\.setdefault' > /dev/null 2>&1; then
    WARNINGS+=("os.environ[] assignment detected — use monkeypatch.setenv() instead to prevent cross-test contamination")
fi

# Check 2: sys.path.insert
if echo "$CONTENT" | grep -q 'sys\.path\.insert'; then
    WARNINGS+=("sys.path.insert detected — this breaks module isolation. Use proper package imports instead")
fi

# Check 3: importlib.reload without obvious restore
if echo "$CONTENT" | grep -q 'importlib\.reload'; then
    WARNINGS+=("importlib.reload detected — ensure a restore fixture reverts the module state after the test")
fi

# Check 4: bare "from app import" (dual module bug)
if echo "$CONTENT" | grep -q '^from app import'; then
    WARNINGS+=("bare 'from app import' detected — use 'from web.app import' to avoid the dual module bug")
fi

# Report warnings
if [ ${#WARNINGS[@]} -gt 0 ]; then
    echo "TEST HYGIENE WARNING in $(basename "$FILE_PATH"):" >&2
    for w in "${WARNINGS[@]}"; do
        echo "  ⚠ $w" >&2
    done
fi

# Always exit 0 — warnings only, never block
exit 0
