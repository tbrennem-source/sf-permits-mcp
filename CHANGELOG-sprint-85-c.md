# CHANGELOG — Sprint 85-C: Stale File Cleanup

## Summary

Deleted 45 stale/obsolete files accumulated from Sprints 3-78, plus prototype artifacts.

## Files Deleted

### sprint-prompts/ — 40 stale sprint prompt files

**qs3-* (4 files):**
- sprint-prompts/qs3-a-permit-prep.md
- sprint-prompts/qs3-b-ops-hardening.md
- sprint-prompts/qs3-c-testing.md
- sprint-prompts/qs3-d-analytics.md

**qs4-* (4 files):**
- sprint-prompts/qs4-a-metrics-ui.md
- sprint-prompts/qs4-b-performance.md
- sprint-prompts/qs4-c-obsidian-migration.md
- sprint-prompts/qs4-d-security-polish.md

**qs5-* (5 files):**
- sprint-prompts/qs5-a-parcels.md
- sprint-prompts/qs5-b-backfill.md
- sprint-prompts/qs5-c-bridges.md
- sprint-prompts/qs5-d-hygiene.md
- sprint-prompts/qs5-swarm.md

**qs7-* (5 files):**
- sprint-prompts/qs7-spec-v2.md
- sprint-prompts/qs7-t0-orchestrator.md
- sprint-prompts/qs7-t1-speed.md
- sprint-prompts/qs7-t2-public-templates.md
- sprint-prompts/qs7-t3-auth-templates.md
- sprint-prompts/qs7-t4-testing.md

**sprint-64 through sprint-67 (4 files):**
- sprint-prompts/sprint-64-reliability.md
- sprint-prompts/sprint-65-data.md
- sprint-prompts/sprint-66-intelligence.md
- sprint-prompts/sprint-67-ux-testing.md

**sprint-68-* (4 files):**
- sprint-prompts/sprint-68a-scenario-drain.md
- sprint-prompts/sprint-68b-reliability.md
- sprint-prompts/sprint-68c-cron-brief.md
- sprint-prompts/sprint-68d-cleanup-docs.md

**sprint-69-* (5 files):**
- sprint-prompts/sprint-69-hotfix-search.md
- sprint-prompts/sprint-69-session1-design-landing.md
- sprint-prompts/sprint-69-session2-search-intel.md
- sprint-prompts/sprint-69-session3-content-pages.md
- sprint-prompts/sprint-69-session4-portfolio-pwa.md

**sprint-74 through sprint-78 (8 files):**
- sprint-prompts/sprint-74-perf.md
- sprint-prompts/sprint-75-ux-beta.md
- sprint-prompts/sprint-76-intelligence.md
- sprint-prompts/sprint-77-e2e-testing.md
- sprint-prompts/sprint-78-design-migration.md
- sprint-prompts/sprint-78-foundation.md
- sprint-prompts/sprint-78-spec-v3.md
- sprint-prompts/sprint-78-spec.md

### Other stale artifacts (5 files)

- `.claude/hooks/.stop_hook_fired` — hook state artifact (ephemeral, should not persist)
- `scenarios-reviewed-sprint69.md` — Sprint 69 reviewed scenarios (stale, already incorporated)
- `web/static/landing-v5.html` — prototype landing page (superseded by mockups/landing.html)
- `scripts/public_qa_checks.py` — Sprint 69 QA script (no Python imports found)
- `scripts/sprint69_visual_qa.py` — Sprint 69 visual QA script (no Python imports found)

## Retained (current/recent)

sprint-prompts/ now contains only:
- qs8-* (6 files) — current quad sprint
- qs9-* (7 files) — active sprint
- sprint-79-* through sprint-82-* (4 files) — recent sprints

## Verification

- `ls sprint-prompts/qs3-* sprint-prompts/sprint-68* sprint-prompts/sprint-69-* 2>/dev/null | wc -l` → 0
- `test -f web/static/landing-v5.html` → DELETED
- No Python imports found for deleted scripts (grep confirmed)
