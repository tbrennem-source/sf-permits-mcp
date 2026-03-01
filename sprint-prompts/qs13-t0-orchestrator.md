# QS13 T0 — Orchestrator Prompt

**Sprint:** QS13 — Honeypot Launch + MCP Directory Pipeline
**Sprints:** 98-101
**Agents:** 12 across 4 terminals
**Merge order:** T1 → T2 → T3 → T4

## Pre-Flight Checklist

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
git checkout main && git pull origin main
git worktree list  # should be clean
source .venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q  # baseline
curl -s https://sfpermits-ai-production.up.railway.app/health | python3 -m json.tool
curl -s -w "%{http_code}" https://sfpermits-mcp-api-production.up.railway.app/health
```

**Verify pre-sprint safety (already done 2026-02-28):**
- [x] FLASK_SECRET_KEY on prod + staging (64 chars, not default)
- [x] TESTING not set on prod or staging
- [x] TEST_LOGIN_SECRET not set on prod or staging
- [x] MCP_AUTH_TOKEN set on sfpermits-mcp-api (bearer token auth working)

## Launch Sequence

Launch T1 and T2 in parallel (zero file overlap except db.py different sections).
Wait for both to complete.
Launch T3 (depends on T2 OAuth for docs accuracy).
Wait for T3.
Launch T4 (validates everything).

Each terminal is a single Task agent with `isolation: "worktree"` that runs its 3 sub-agents sequentially.

## Merge Ceremony

After all terminals complete:

```bash
cd /Users/timbrenneman/AIprojects/sf-permits-mcp
# Merge in order: T1 → T2 → T3 → T4
git merge <t1-branch> --no-edit
git merge <t2-branch> --no-edit
git merge <t3-branch> --no-edit
git merge <t4-branch> --no-edit

# Single test run (Fast Merge Protocol)
source .venv/bin/activate
pytest tests/ --ignore=tests/test_tools.py --ignore=tests/e2e -x -q

# Design lint on changed templates
python scripts/design_lint.py --changed --quiet

# Push
git push origin main
```

## Post-Sprint

1. Tim design review on staging (~15 min): /join-beta, /join-beta/thanks, /docs, /privacy, /terms
2. Hotfix if needed
3. Promote: `git checkout prod && git merge main && git push origin prod`
4. Set `HONEYPOT_MODE=1` on sfpermits-ai (prod) in Railway
5. Remove MCP_AUTH_TOKEN from sfpermits-mcp-api (OAuth replaces it)
6. Tim re-adds sfpermits connector in c.ai (now with OAuth)
7. Submit to Anthropic directory using docs/DIRECTORY_SUBMISSION.md
