#!/usr/bin/env bash
# Mechanism 4: Descope Warning
# PostToolUse hook on Write. Warns when descoping language is detected in QA results or CHECKCHAT files.
#
# Input (stdin): JSON with fields including:
#   - tool_input.file_path: path of the file written
#   - tool_input.content: content written to the file

set -euo pipefail

# Read the tool output from stdin (JSON with tool_input containing file_path and content)
INPUT=$(cat)

# Extract file path from the tool input (try tool_input first, fall back to input)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('file_path', ''))
" 2>/dev/null || echo "")

# Only check files in qa-results/ or files containing CHECKCHAT
IS_QA_FILE=false
if echo "$FILE_PATH" | grep -q "qa-results/"; then
    IS_QA_FILE=true
fi

# Extract file content
CONTENT=$(echo "$INPUT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
ti = d.get('tool_input', d.get('input', {}))
print(ti.get('content', ''))
" 2>/dev/null || echo "")

if echo "$CONTENT" | grep -q "## CHECKCHAT"; then
    IS_QA_FILE=true
fi

# Skip if not a relevant file
if [ "$IS_QA_FILE" = false ]; then
    exit 0
fi

# Check for descoping language
DESCOPE_PATTERNS="descoped|deferred|out of scope|dropped|removed from scope|moved to sprint"
if echo "$CONTENT" | grep -i -E "$DESCOPE_PATTERNS" > /dev/null 2>&1; then
    echo "WARNING: Descoping language detected. You MUST get user approval via the ask tool before closing this session. Descoped items without approval will be blocked at CHECKCHAT." >&2
fi

exit 0
