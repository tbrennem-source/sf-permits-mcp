#!/usr/bin/env bash
# =============================================================================
# setup_staging.sh — Provision sfpermits.ai staging on Railway via CLI
# =============================================================================
# Requires: railway CLI installed and authenticated (railway login)
# Run from: ~/AIprojects/sf-permits-mcp
# =============================================================================

set -euo pipefail

PROJECT_DIR="$HOME/AIprojects/sf-permits-mcp"
SERVICE_NAME="sfpermits-ai-staging"
REPO="tbrennem-source/sf-permits-mcp"
PROD_SERVICE="sfpermits-ai"

cd "$PROJECT_DIR"

echo "=== Step 1: Link to Railway project ==="
railway link 2>/dev/null || true

echo ""
echo "=== Step 2: Read prod env vars ==="
# Link to prod service to read its variables
railway service link "$PROD_SERVICE"

PROD_VARS_JSON=$(railway variable list --json 2>/dev/null || echo "{}")

# Extract vars we need from prod
get_var() {
    echo "$PROD_VARS_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('$1',''))" 2>/dev/null
}

PROD_DB_URL=$(get_var DATABASE_URL)
PROD_CRON=$(get_var CRON_SECRET)
PROD_ANTHROPIC=$(get_var ANTHROPIC_API_KEY)
PROD_OPENAI=$(get_var OPENAI_API_KEY)
PROD_ADMIN=$(get_var ADMIN_EMAIL)

echo "  DATABASE_URL: ${PROD_DB_URL:0:30}..."
echo "  CRON_SECRET: ${PROD_CRON:+set}"
echo "  ANTHROPIC_API_KEY: ${PROD_ANTHROPIC:+set}"
echo "  OPENAI_API_KEY: ${PROD_OPENAI:+set}"
echo "  ADMIN_EMAIL: $PROD_ADMIN"

echo ""
echo "=== Step 3: Generate secrets ==="
TEST_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
FLASK_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "  TEST_LOGIN_SECRET: $TEST_SECRET"

echo ""
echo "=== Step 4: Create staging service ==="
railway add \
    --service "$SERVICE_NAME" \
    --repo "$REPO" \
    --variables "ENVIRONMENT=staging" \
    --variables "TESTING=true" \
    --variables "TEST_LOGIN_SECRET=$TEST_SECRET" \
    --variables "FLASK_SECRET_KEY=$FLASK_SECRET"

echo ""
echo "=== Step 5: Set remaining env vars on staging ==="
railway service link "$SERVICE_NAME"

# Set vars one at a time (skip-deploys to avoid multiple restarts)
railway variable set "DATABASE_URL=$PROD_DB_URL" --skip-deploys
railway variable set "CRON_SECRET=$PROD_CRON" --skip-deploys
railway variable set "ANTHROPIC_API_KEY=$PROD_ANTHROPIC" --skip-deploys
railway variable set "OPENAI_API_KEY=$PROD_OPENAI" --skip-deploys
railway variable set "ADMIN_EMAIL=$PROD_ADMIN"

echo ""
echo "=== Step 6: Generate domain ==="
railway domain --service "$SERVICE_NAME"

echo ""
echo "=================================================================="
echo "  STAGING PROVISIONED"
echo "=================================================================="
echo ""
echo "  TEST_LOGIN_SECRET=$TEST_SECRET"
echo ""
echo "  Save this secret — needed for termRelay authentication."
echo "  Wait ~2 min for deploy, then verify:"
echo "    curl -s https://<staging-domain>/health | python3 -m json.tool"
echo ""
echo "  SECURITY: NEVER set TESTING or TEST_LOGIN_SECRET on production."
echo "=================================================================="

# Save secret for Task 3
echo "$TEST_SECRET" > /tmp/test_login_secret.txt
echo "(Secret also saved to /tmp/test_login_secret.txt)"
