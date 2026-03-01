#!/usr/bin/env bash
# Sprint pre-flight — runs git cleanup, test baseline, and health checks in parallel.
# Output: sprint-prompts/<sprint-id>-preflight-report.md
#
# Usage: bash scripts/sprint_preflight.sh <sprint-id>
#   e.g.: bash scripts/sprint_preflight.sh qs15
#
# T0 launches this in the background, then immediately starts reading specs
# and writing prompts. The test baseline (~4 min) runs without blocking.

set -uo pipefail

SPRINT_ID="${1:?Usage: sprint_preflight.sh <sprint-id>}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT="$REPO_ROOT/sprint-prompts/${SPRINT_ID}-preflight-report.md"
TMPDIR=$(mktemp -d)
START_TIME=$(date +%s)

cd "$REPO_ROOT"

# ── Job 1: Git cleanup ──────────────────────────────────────────────
(
  exec 2>/dev/null
  {
    echo "## Git"
    echo ""

    git checkout main >/dev/null 2>&1
    git pull origin main >/dev/null 2>&1
    echo "- Branch: main"
    echo "- HEAD: $(git log --oneline -1)"
    echo ""

    # Worktree prune
    BEFORE=$(git worktree list | wc -l | tr -d ' ')
    git worktree prune 2>/dev/null

    # Delete merged worktree/claude branches
    DELETED=0
    for branch in $(git branch --merged main 2>/dev/null | grep -E 'worktree-|claude/' | tr -d ' *+'); do
      git branch -d "$branch" 2>/dev/null && DELETED=$((DELETED + 1)) || true
    done

    AFTER=$(git worktree list | wc -l | tr -d ' ')
    echo "- Worktrees: $BEFORE -> $AFTER (pruned)"
    echo "- Merged branches deleted: $DELETED"

    # Report unmerged worktree branches
    UNMERGED=$(git branch --no-merged main 2>/dev/null | grep -E 'worktree-|claude/' | tr -d ' *+')
    if [ -n "$UNMERGED" ]; then
      echo "- Unmerged branches (kept):"
      echo "$UNMERGED" | while read -r b; do echo "  - $b"; done
    fi
    echo ""
  } > "$TMPDIR/git.md"
) &
PID_GIT=$!

# ── Job 2: Test baseline (the ~4 min bottleneck) ────────────────────
(
  {
    echo "## Tests"
    echo ""

    source "$REPO_ROOT/.venv/bin/activate" 2>/dev/null
    JOB_START=$(date +%s)
    # macOS has no `timeout` — use perl alarm or just run directly
    TEST_OUT=$(python -m pytest tests/ \
      --ignore=tests/test_tools.py --ignore=tests/e2e \
      -q --tb=no 2>&1 | tail -5)
    TEST_EXIT=$?
    JOB_END=$(date +%s)
    DURATION=$((JOB_END - JOB_START))

    echo "\`\`\`"
    echo "$TEST_OUT"
    echo "\`\`\`"
    echo ""
    echo "- Duration: ${DURATION}s"
    echo "- Exit code: $TEST_EXIT"

    PASSED=$(echo "$TEST_OUT" | grep -oE '[0-9]+ passed' | head -1)
    FAILED=$(echo "$TEST_OUT" | grep -oE '[0-9]+ failed' | head -1)
    echo "- Passed: ${PASSED:-unknown}"
    [ -n "$FAILED" ] && echo "- **FAILED: $FAILED**"
    echo ""
  } > "$TMPDIR/tests.md"
) &
PID_TESTS=$!

# ── Job 3: Health checks (prod + staging + MCP) ─────────────────────
(
  {
    echo "## Health"
    echo ""

    # Prod
    PROD=$(curl -s --max-time 15 \
      https://sfpermits-ai-production.up.railway.app/health 2>/dev/null)
    PROD_STATUS=$(echo "$PROD" | python3 -c \
      "import sys,json; print(json.load(sys.stdin).get('status','error'))" 2>/dev/null || echo "unreachable")
    PROD_TABLES=$(echo "$PROD" | python3 -c \
      "import sys,json; print(json.load(sys.stdin).get('table_count','?'))" 2>/dev/null || echo "?")
    echo "- Prod: $PROD_STATUS ($PROD_TABLES tables)"

    # Staging
    STAGING_CODE=$(curl -s -o /dev/null --max-time 10 -w "%{http_code}" \
      https://sfpermits-ai-staging-production.up.railway.app/health 2>/dev/null || echo "000")
    echo "- Staging: HTTP $STAGING_CODE"

    # MCP API
    MCP_CODE=$(curl -s -o /dev/null --max-time 10 -w "%{http_code}" \
      https://sfpermits-mcp-api-production.up.railway.app/health 2>/dev/null || echo "000")
    echo "- MCP API: HTTP $MCP_CODE"

    # Cron heartbeat
    CRON_AGE=$(echo "$PROD" | python3 -c \
      "import sys,json; print(round(json.load(sys.stdin).get('cron_heartbeat_age_minutes',999)))" 2>/dev/null || echo "?")
    echo "- Cron heartbeat: ${CRON_AGE}m ago"
    echo ""
  } > "$TMPDIR/health.md"
) &
PID_HEALTH=$!

# ── Job 4: Codebase snapshot ────────────────────────────────────────
(
  {
    echo "## Codebase"
    echo ""

    # Recent commits
    echo "### Recent Commits"
    echo "\`\`\`"
    git log --oneline -5
    echo "\`\`\`"
    echo ""

    # Counts
    ROUTES=$(grep -rcn '@bp.route\|@app.route' web/ --include='*.py' 2>/dev/null | wc -l | tr -d ' ')
    TEMPLATES=$(find web/templates -name '*.html' 2>/dev/null | wc -l | tr -d ' ')
    # Count test functions without running pytest (avoids contention with Job 2)
    TESTS_COLLECTED=$(grep -rcE 'def test_' tests/ --include='*.py' 2>/dev/null | \
      awk -F: '{sum+=$2} END{print sum}')
    SRC_FILES=$(find src/ web/ -name '*.py' 2>/dev/null | wc -l | tr -d ' ')

    echo "- Routes: $ROUTES"
    echo "- Templates: $TEMPLATES"
    echo "- Tests collected: $TESTS_COLLECTED"
    echo "- Python source files: $SRC_FILES"
    echo ""

    # Key function locations (for codebase audit)
    echo "### Key Functions"
    echo "\`\`\`"
    grep -n "def compute_triage_signals" web/helpers.py 2>/dev/null | head -1
    grep -n "def analyze(" web/routes_public.py 2>/dev/null | head -1
    grep -n "def index(" web/routes_public.py 2>/dev/null | head -1
    grep -n "def get_morning_brief" web/brief.py 2>/dev/null | head -1
    grep -n "def get_property_report" web/report.py 2>/dev/null | head -1
    echo "\`\`\`"
    echo ""
  } > "$TMPDIR/codebase.md"
) &
PID_CODEBASE=$!

# ── Wait + assemble ─────────────────────────────────────────────────
echo "Pre-flight running (4 parallel jobs)..."

wait $PID_GIT     && echo "  [1/4] Git cleanup done"
wait $PID_HEALTH  && echo "  [2/4] Health checks done"
wait $PID_CODEBASE && echo "  [3/4] Codebase snapshot done"
wait $PID_TESTS   && echo "  [4/4] Test baseline done"

END_TIME=$(date +%s)
TOTAL=$((END_TIME - START_TIME))

{
  echo "# Pre-Flight Report: $SPRINT_ID"
  echo ""
  echo "**Generated:** $(date -u '+%Y-%m-%d %H:%M UTC') (${TOTAL}s)"
  echo ""
  cat "$TMPDIR/git.md"
  cat "$TMPDIR/health.md"
  cat "$TMPDIR/tests.md"
  cat "$TMPDIR/codebase.md"
  echo "---"
  echo "Pre-flight complete. T0 may proceed with prompt generation."
} > "$REPORT"

# Notify
bash "$REPO_ROOT/scripts/notify.sh" agent-done "Pre-flight complete (${TOTAL}s)" 2>/dev/null || true

echo ""
echo "Report: $REPORT (${TOTAL}s)"
echo ""
cat "$REPORT"

rm -rf "$TMPDIR"
