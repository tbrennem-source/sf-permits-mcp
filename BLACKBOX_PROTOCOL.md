# BLACKBOX_PROTOCOL.md — Autonomous Build Session Protocol

**Owner:** dforge
**Version:** 1.3
**Last Updated:** 2026-02-26

---

## What This File Is

This is the executable protocol for autonomous Claude Code build sessions. It is not advisory. It is not a template to customize. CC reads this file and follows it literally.

Every repo that uses the Black Box pattern includes this line in its CLAUDE.md:

```
## Black Box Protocol: active
See BLACKBOX_PROTOCOL.md for the mandatory session structure.
```

CC must read this file at session start. If this file is not present, CC must stop and ask where it is before building anything.

---

## Session Structure

Every Black Box session has exactly two stages. Both are mandatory. Neither can be skipped.

### Swarm Execution (MANDATORY for multi-agent sprints)

**When a sprint has 2+ parallel agents, the orchestrator MUST use the Task tool to spawn them from a single CC session.** Do not use separate CC terminals. This is the core throughput mechanism.

```
CC0 (Opus orchestrator) — single session
├── Pre-flight: git pull, verify prod state, read manifest
├── Spawn ALL agents IN PARALLEL via Task tool:
│   Task(subagent_type="general-purpose", model="sonnet", isolation="worktree", prompt="...")
│   (each agent gets an isolated worktree, runs Stage 1 independently)
├── Collect results from all agents
├── Merge worktree branches in dependency order (Fast Merge Protocol)
├── Single test run after ALL merges (not between each)
├── Push to main
├── Stateful Deployment Protocol (if schema/ingest changes)
├── Generate DeskRelay prompt
└── Report summary table
```

**Task parameters for each agent:**
- `subagent_type: "general-purpose"` — full tool access
- `model: "sonnet"` — build agents use Sonnet
- `isolation: "worktree"` — isolated git worktree per agent
- `prompt:` — self-contained instructions (must NOT reference external files; inline everything)

**Every agent prompt must start with:**
```
You are ALREADY in a git worktree. Do NOT use EnterWorktree. Do NOT run git checkout main.
Your working directory is your isolated worktree copy of the repo.
```

**Agents commit to their worktree branch. The orchestrator merges to main. Agents NEVER merge themselves.**

For single-agent sessions, the regular single-terminal flow applies (no Task tool needed).

### Stage 1: termCC (Terminal Claude Code)

Runs in terminal. For swarm sprints, each agent is a Task subagent running in parallel. For single-agent sessions, runs directly.

**Phase order is fixed. Do not reorder. Do not skip phases.**

```
READ → BUILD → TEST → SCENARIOS → QA → CHECKCHAT
```

#### READ

1. Read this file (BLACKBOX_PROTOCOL.md)
2. Read the repo's CLAUDE.md
3. Read the repo's DEPLOYMENT_MANIFEST.yaml (location declared in CLAUDE.md)
4. Read the mission prompt (the task you were given)
5. Read any spec files referenced in the mission prompt

**Gate:** Do not proceed to BUILD until you can state:
- What topology this repo uses (from manifest)
- What URLs you will verify against (from manifest)
- How many DeskRelay prompts you must generate (from manifest)

#### BUILD

Build what the mission prompt says. Follow the repo's PRINCIPALS.md and CLAUDE.md rules.

**Rules during BUILD:**
- No curl/fetch against prod URLs. Staging only.
- No database mutations against prod. Staging only.
- If the manifest says `topology: two-branch`, all remote operations target staging until DeskRelay-staging passes and promotion occurs.

#### TEST

Run the repo's test suite. All tests must pass.

```bash
# Standard pattern — repo may override in CLAUDE.md
pytest tests/ -v
```

**Gate:** Do not proceed to SCENARIOS if tests fail. Fix failures first. After 3 failed fix attempts, mark as BLOCKED and proceed to CHECKCHAT with BLOCKED status.

#### SCENARIOS

Append suggested scenarios to `scenarios-pending-review.md` in the repo root. Create the file if it doesn't exist.

**Rules:**
- CC does NOT modify `scenario-design-guide.md` or any authoritative scenario file
- Scenarios go to the staging file only
- Use the format defined in the repo's CLAUDE.md
- Aim for 2-5 scenarios per session
- Tag each with CC confidence: high / medium / low

#### QA (termRelay)

Spawn QA subagents using headless Playwright. Each subagent:
- Navigates to the **staging URL** (from manifest, never prod)
- Takes screenshots to `qa-results/screenshots/{sprint-id}/`
- Writes PASS/FAIL results to `qa-results/{sprint-id}-staging-results.md`

**Subagent categories** (spawn what's relevant, skip what isn't):
- **Public:** Landing page, search, unauthenticated features
- **Auth:** Login flow, authenticated features
- **Admin:** Admin-only features, cron endpoints
- **API:** Health checks, data endpoints

**Gate:** All relevant subagent categories must PASS before proceeding to CHECKCHAT. After 3 failed fix attempts per category, mark as BLOCKED.

#### CHECKCHAT

Session close protocol. Six steps, all mandatory.

**Step 1 — VERIFY:** Confirm QA gate status. List any BLOCKED items.

**Step 2 — DOCUMENT:** Update STATUS.md and CHANGELOG.md in the repo.

**Step 3 — CAPTURE:** Confirm scenarios were appended to `scenarios-pending-review.md`.

**Step 4 — SHIP:** Push to the repo's development branch (usually `main`). Update Chief if the repo uses Chief Hub Protocol.

**Step 5 — GENERATE DESKRELAY PROMPT:** This is mandatory. Read the DEPLOYMENT_MANIFEST.yaml and generate the DeskRelay prompt file.

> **This step is not optional. This step cannot be skipped. If you close a session without generating a DeskRelay prompt, the session is incomplete.**

See [DeskRelay Prompt Generation](#deskrelay-prompt-generation) below for the exact rules.

**Step 6 — BLOCKED ITEMS REPORT:** List anything that couldn't be completed, with root cause and suggested next step.

Output the CHECKCHAT summary to the terminal. Include the line:

```
DESKRELAY PROMPT: qa-drop/{sprint-id}-deskrelay-prompt.md
```

---

### Stage 2: DeskCC (Desktop Claude Code)

Runs in Desktop Claude Code. Visual verification only. No code changes except the promotion ceremony.

DeskCC receives the DeskRelay prompt file generated by Stage 1. It executes the parts sequentially (staging checks → promotion → prod checks). When done, it runs a lightweight CHECKCHAT: commit QA artifacts, push, note any follow-ups.

**DeskCC rules:**
- No code changes (except git promotion commands if specified in the prompt)
- Only produces QA artifacts (screenshots, results files)
- If a visual check fails, document the failure — do NOT attempt to fix code

---

### Stage 2 Escalation Criteria

Stage 2 (DeskRelay) is **mandatory** when the sprint includes:
- Visual/UI changes (CSS, templates, layout modifications)
- New pages or significant page restructuring
- Responsive/mobile fixes
- Branding or design system changes

Stage 2 is **optional** (can be skipped) when the sprint is:
- Backend-only changes (API, database, cron jobs)
- Documentation updates
- Test-only changes
- Configuration or environment changes

When Stage 2 is skipped, the CHECKCHAT Visual QA Checklist section should state:
"Visual QA SKIPPED — backend/docs only sprint, no visual changes."

---

## DeskRelay Prompt Generation

This is the most important section of this protocol. Getting this wrong means prod goes unverified.

### Read the Manifest

The repo's `DEPLOYMENT_MANIFEST.yaml` declares the topology. The topology determines the DeskRelay prompt structure.

All topologies generate **one file:** `qa-drop/{sprint-id}-deskrelay-prompt.md`. Sequential steps go in one file — never split across multiple files.

### Topology: `no-deploy`

Library or tool with no deployment. No DeskRelay prompt needed. Skip Step 5.

### Topology: `single-branch`

One environment, one branch, one URL.

**Generate 1 file:** `qa-drop/{sprint-id}-deskrelay-prompt.md`

Contents:
1. `cd {repo_path}` (from manifest)
2. Visual checks against the single environment URL
3. Screenshots to `qa-results/screenshots/{sprint-id}-deskrelay/`
4. Results to `qa-results/{sprint-id}-deskrelay-results.md`
5. Lightweight CHECKCHAT (commit, push)

### Topology: `two-branch`

Two environments (staging + prod), two branches, promotion ceremony between them.

**Generate 1 file:** `qa-drop/{sprint-id}-deskrelay-prompt.md`

The file has sequential parts — staging verification, then promotion, then prod verification. DeskCC executes them in order within a single session.

**Part 1 — Staging Checks:**
1. `cd {repo_path}`
2. Visual checks against `staging_url` (from manifest)
3. Screenshots to `qa-results/screenshots/{sprint-id}-deskrelay-staging/`

**Part 2 — Promotion Ceremony** (only if staging checks PASS):
4. Run the promotion command:
   ```
   {promotion_command}
   ```
   (Exact command from manifest. Do not improvise.)
5. Wait for prod deploy (manifest specifies `deploy_wait_seconds`)
6. Run any `post_promotion_commands` from manifest (migrations, data loads, etc.)

**Part 3 — Prod Checks:**
7. Visual checks against `prod_url` (from manifest)
8. Same check categories as staging
9. Screenshots to `qa-results/screenshots/{sprint-id}-deskrelay-prod/`

**Part 4 — Close:**
10. Write results to `qa-results/{sprint-id}-deskrelay-results.md` (both staging + prod results)
11. Lightweight CHECKCHAT (commit, push, update Chief if applicable)

### What Every DeskRelay Prompt Must Contain

Regardless of topology, every generated DeskRelay prompt must include:

1. **Repo path** — `cd` command at the top
2. **Context** — brief summary of what was built this sprint
3. **Target URL(s)** — which environment(s) to verify
4. **Health check** — hit the health endpoint, verify response
5. **Visual checks** — numbered steps with explicit PASS/FAIL criteria
6. **Screenshot paths** — where to save evidence
7. **Results file path** — where to write the report
8. **No-code-changes rule** — explicit statement that DeskCC must not modify code
9. **Lightweight CHECKCHAT** — commit QA artifacts, push

For `two-branch`, the file must have clearly labeled sequential parts (staging → promotion → prod) so DeskCC executes them in order.

### DeskRelay Prompt Template (single-branch)

```markdown
# {sprint-id} — DeskRelay Verification

## Context
{Brief summary of what was built}

## Setup
cd {repo_path}

## Rules
- NO code changes. QA artifacts only.
- If a check fails, document it. Do NOT attempt fixes.

## Visual Checks
Target: {url}

1. [ ] Health endpoint — curl -s {url}/health | python3 -m json.tool
2. [ ] Landing page loads — title contains expected text
3. [ ] {additional checks from termRelay HANDOFF section}

Screenshots to: qa-results/screenshots/{sprint-id}-deskrelay/
Results to: qa-results/{sprint-id}-deskrelay-results.md

## Close
Lightweight CHECKCHAT: commit, push, note follow-ups.
```

### DeskRelay Prompt Template (two-branch)

```markdown
# {sprint-id} — DeskRelay: Staging → Promotion → Prod

## Context
{Brief summary of what was built}

## Setup
cd {repo_path}

## Rules
- NO code changes. QA artifacts only.
- If a check fails, document it. Do NOT attempt fixes.

---

## Part 1: Staging Checks
Target: {staging_url}

1. [ ] Health endpoint returns 200 with expected data
2. [ ] Landing page loads without errors
3. [ ] {feature-specific checks}

Screenshots to: qa-results/screenshots/{sprint-id}-deskrelay-staging/

---

## Part 2: Promotion Ceremony
(Only if all staging checks PASS)

{promotion_command}

Wait {deploy_wait_seconds}s for prod deploy.
{post_promotion_commands if any}

---

## Part 3: Prod Checks
Target: {prod_url}

4. [ ] Health endpoint returns 200 with expected data
5. [ ] Landing page loads without errors
6. [ ] {same feature-specific checks as staging}

Screenshots to: qa-results/screenshots/{sprint-id}-deskrelay-prod/

---

## Part 4: Close
Results to: qa-results/{sprint-id}-deskrelay-results.md
Lightweight CHECKCHAT: commit, push, update Chief.
```

---

## Stateful Deployment Protocol

**Added:** v1.2, Sprint 55 post-mortem
**Trigger:** Any sprint that adds schema changes, cron endpoints, or data ingest pipelines

### The Problem This Solves

Code deploying successfully does NOT mean the system is ready. When a sprint adds database tables, migrations, or ingest pipelines, the system requires post-deploy operations before it's functional. The base protocol (push → deploy → DeskRelay visual checks) skips this entirely, leaving DeskRelay to discover missing tables, broken auth, and failed ingest — issues it can document but cannot fix.

### When This Protocol Activates

CC must run the Stateful Deployment Protocol when ANY of these are true:
- Sprint modifies `postgres_schema.sql` or adds tables
- Sprint adds or modifies `run_prod_migrations.py` entries
- Sprint adds new `/cron/ingest-*` endpoints
- Sprint modifies `_PgConnWrapper` or SQL translation logic
- Deployment manifest has `ingest_runbook` entries for this sprint

### Phase Order

Run these steps AFTER tests pass and code is pushed, BEFORE writing CHECKCHAT.

```
TEST (pass) → PUSH → DEPLOY VERIFY → SCHEMA GATE → AUTH SMOKE → STAGED INGEST → CHECKCHAT
```

#### Step 1: Deploy Verification

Confirm the push triggered a staging build.

```bash
# Check Railway deployment list
railway service link {staging_service}
railway deployment list | head -5
```

**Expected:** A deployment with status BUILDING or SUCCESS timestamped after your push.

**If no deployment appears within 3 minutes:**
1. Push an empty commit: `git commit --allow-empty -m "chore: trigger staging redeploy" && git push`
2. Wait 30s, check again
3. If still nothing after 2 attempts, flag as BLOCKED — do not proceed

**Wait for SUCCESS status before continuing.** Check with:
```bash
railway deployment list | head -3
# Look for SUCCESS, not BUILDING
```

#### Step 2: Schema Gate

Verify all new tables exist on staging.

```bash
curl -s {staging_url}/health | python3 -c "
import sys, json
d = json.load(sys.stdin)
tables = d.get('tables', {})
for name in {expected_new_tables}:
    count = tables.get(name, 'MISSING')
    status = 'OK' if count != 'MISSING' else 'FAIL'
    print(f'{status}: {name} = {count}')
"
```

**If any table is MISSING:**
- Check Railway logs: `railway logs -n 30`
- Look for SQL errors during startup (schema.sql runs at import time)
- Common cause: DDL that fails on existing data (UNIQUE constraints, NOT NULL on populated columns)
- Fix the schema, push, wait for redeploy, re-run this gate
- **Max 3 fix-redeploy cycles.** After 3, mark BLOCKED.

#### Step 3: Auth Smoke Test

Verify cron endpoints accept the auth token.

```bash
# Get the ACTUAL secret value (Railway CLI may wrap long values across lines)
railway variables list | grep -A1 CRON_SECRET

# Verify length matches what the app expects
# (64 chars for this project — check _check_api_auth if unsure)

# Hit a lightweight endpoint
curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer {full_secret}" \
  {staging_url}/health
```

**If 403:**
1. Check logs: `railway logs -n 5` — look for `API auth failed: token_len=X expected_len=Y`
2. If token_len < expected_len: the secret is truncated. Use `od -c` or `wc -c` on the Railway CLI output to get the full value.
3. If token_len > expected_len: trailing whitespace. Verify `.strip()` is applied in `_check_api_auth()`.
4. **Do not proceed to ingest until auth works.** All ingest endpoints use the same auth.

#### Step 4: Staged Ingest Runbook

Run ingest endpoints in size order — smallest first. This catches SQL bugs on cheap datasets before committing to multi-minute large ingests.

**Read the manifest's `ingest_runbook`** (or the sprint spec) for dataset ordering. If no runbook exists, sort by estimated row count ascending.

**Tier 1 — Small datasets (<10K rows):**
Run all small datasets sequentially. Verify each returns `"ok": true` and rows appear in /health.

```bash
curl -s -X POST -H "Authorization: Bearer {secret}" \
  "{staging_url}/cron/ingest-{dataset}" | python3 -m json.tool
```

**If any Tier 1 ingest fails:**
- Check logs for SQL errors (ON CONFLICT, type mismatches, column count)
- Fix, push, wait for redeploy, re-run from Step 1
- **These failures indicate systemic issues** (e.g., missing ON CONFLICT handling) that will affect all datasets

**Tier 2 — Medium datasets (10K-100K rows):**
Run sequentially after Tier 1 passes. Same verification.

**Tier 3 — Large datasets (>100K rows):**
Before running:
1. Check timeout budget: `estimated_rows / batch_rate` vs gunicorn timeout
2. Verify the ingest function commits per-batch (not one big transaction)
3. If timeout budget is tight, flag for DeskRelay (runs as post-promotion command with monitoring)

Run in background and monitor:
```bash
# Start ingest
curl -s -X POST -H "Authorization: Bearer {secret}" \
  "{staging_url}/cron/ingest-{dataset}" &

# Monitor progress via logs (if streaming)
railway logs -n 5  # Check periodically for batch flush messages
```

**If a large ingest times out:**
1. Check /health — did partial data land? (Incremental commits should preserve batches)
2. If zero rows: the function isn't committing per-batch. Fix and redeploy.
3. If partial rows: re-running the endpoint should be safe if it does DELETE-then-INSERT or ON CONFLICT
4. Consider bumping gunicorn timeout if within safe limits

**Max 3 fix-redeploy cycles across all tiers.** After 3, mark remaining ingests as BLOCKED for DeskRelay.

### Fix-Redeploy Loop

When a staging issue requires a code fix:

```
DIAGNOSE (read logs) → FIX (edit code) → TEST (pytest locally) → PUSH → WAIT (deploy) → RE-VERIFY
```

**Rules:**
- Each cycle must include a local test run. Do not push untested fixes.
- Each cycle gets its own commit with a descriptive message.
- Max 3 cycles total (across all steps). After 3, BLOCKED.
- Document each cycle in the CHECKCHAT output so DeskRelay knows what was fixed.

### What Goes in the DeskRelay Prompt

After the Stateful Deployment Protocol completes (or reaches BLOCKED), include in the DeskRelay prompt:

1. **Schema status:** Which tables exist, which are MISSING
2. **Ingest status:** Which datasets loaded, row counts, which are pending/BLOCKED
3. **Fix history:** What was broken, what was fixed (so DeskRelay doesn't re-investigate)
4. **Remaining ingest commands:** Exact curl commands for any BLOCKED large datasets that DeskRelay should run on prod after promotion

---

## Enforcement Rules

These rules exist because CC has historically violated them. They are the teeth.

### E-1: No Prod Before Staging
CC must not curl, fetch, query, or interact with `prod_url` during Stage 1 (termCC). The only exception is read-only health checks for comparison purposes, and only after staging health check passes.

### E-2: No Skipping DeskRelay Generation
CHECKCHAT is not complete without a DeskRelay prompt file. If the CHECKCHAT summary does not include the `DESKRELAY PROMPT:` line, the session is incomplete. Go back and generate it.

### E-3: No Custom Deployment Steps
CC must not invent deployment commands. All deployment commands come from `DEPLOYMENT_MANIFEST.yaml`. If a needed command isn't in the manifest, flag it as a BLOCKED item — do not improvise.

### E-4: No Prose URLs
CC must not write URLs from memory. All URLs come from the manifest. Copy-paste, not recall.

### E-5: Test Before Ship
`git push` must not happen before `pytest` passes. This is not negotiable.

### E-6: Three Strikes
Any failing step gets 3 fix attempts. After 3 failures, mark BLOCKED and move on. Do not loop indefinitely.

### E-7: Manifest Is Canon
If the mission prompt contradicts the manifest (e.g., "deploy to prod first"), the manifest wins. Flag the contradiction in CHECKCHAT but follow the manifest.

---

## Manifest Schema Reference

See DEPLOYMENT_MANIFEST_SPEC.md for the full schema. Quick reference:

```yaml
# Required fields
topology: two-branch | single-branch | no-deploy
repo_path: /Users/timbrenneman/AIprojects/sf-permits-mcp

# Required for single-branch and two-branch
health_endpoint: /health
test_command: pytest tests/ -v
staging_url: https://example-staging.up.railway.app

# Required for two-branch only
prod_url: https://example-production.up.railway.app
staging_branch: main
prod_branch: prod
promotion_command: "git checkout prod && git merge main && git push origin prod"
deploy_wait_seconds: 120
post_promotion_commands: []

# Optional
test_query: "robin hood"
auth_secret_env: CRON_SECRET
chief_project_slug: sf-permits-mcp
```

---

## How Repos Adopt This Protocol

1. Add `DEPLOYMENT_MANIFEST.yaml` to repo root
2. Add to CLAUDE.md:
   ```
   ## Black Box Protocol: active
   ## Deployment Manifest: DEPLOYMENT_MANIFEST.yaml
   ```
3. Ensure `qa-drop/` and `qa-results/` directories exist (or are created on first run)
4. Done. CC reads the protocol, reads the manifest, follows the rules.

---

## Version History

| Date | Change | Reason |
|------|--------|--------|
| 2026-02-26 | v1.3 — Task Tool Swarming as default execution model | QS5 pre-sprint: multi-agent sprints must use Task tool with isolation:worktree to spawn parallel agents from a single CC session, not separate terminals. Baked into Session Structure as mandatory. |
| 2026-02-25 | v1.2 — Stateful Deployment Protocol | Sprint 55 post-mortem: 5 bugs escaped to staging because protocol assumed deploy = ready. New section handles schema gates, auth smoke tests, staged ingest runbooks, and fix-redeploy loops. |
| 2026-02-25 | v1.1 — Single DeskRelay file for all topologies | Sequential steps (staging → promote → prod) belong in one file. Two-branch no longer generates 2 separate files. |
| 2026-02-25 | v1.0 — Initial protocol | Sprint 54 post-mortem: CC skipped staging verification, generated single DeskRelay for two-branch topology, wrote prod URLs from memory instead of manifest |
