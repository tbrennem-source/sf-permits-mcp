# Documentation Update Checklist

When committing changes, review and update these files as relevant:

## Always Update
1. **`CHANGELOG.md`** — Add entry for what changed (reverse chronological)
2. **Chief brain state `projects/sf-permits-mcp/STATUS.md`** — Via `chief_write_file` MCP tool

## Update If Affected
3. **`README.md`** — If tools, architecture, setup, or key numbers change
4. **`CLAUDE.md`** — If project structure, key numbers, or current state changes
5. **`docs/ARCHITECTURE.md`** — If data flow, schema, or web UI architecture changes
6. **`docs/DECISIONS.md`** — If a significant design decision was made

## After Commit
10. **QA checklist for user** — Present a concise list of things the user should manually test based on the commit. Focus on user-facing behavior, edge cases, and anything automated tests can't cover (visual layout, UX flow, cross-browser, mobile).

## Rarely Changed
7. **`data/knowledge/SOURCES.md`** — Only if knowledge base files change
8. **`data/knowledge/GAPS.md`** — Only if gaps are resolved or discovered
9. **`data/knowledge/INGESTION_LOG.md`** — Only if data ingestion occurs
