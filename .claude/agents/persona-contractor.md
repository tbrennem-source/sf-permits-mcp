---
name: persona-contractor
description: "DEFERRED: Sprint 55+. Stub for contractor persona QA agent — tests workflows for licensed SF contractors using sfpermits.ai to track their own permit history, check inspection status, and verify license standing."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# Persona Agent: Contractor (DEFERRED)

## Status

**DEFERRED: Sprint 55+**

This agent is a stub. Do not invoke it for active QA work until it is fully specified.

## Planned Purpose

Simulate the workflow of a licensed SF contractor who uses sfpermits.ai to:
- Check status of permits they pulled
- Verify inspection scheduling and results
- Look up their own license history and standing
- Find permit history on a property before bidding on work

## Why Deferred

Contractor-specific workflows require:
- Contractor license lookup (CSLB integration or SF DBI contractor search)
- Inspection scheduling data (separate dataset from permit data)
- License standing verification (not yet in knowledge base)

These data sources are not currently ingested or exposed. Contractor persona QA cannot meaningfully test workflows that don't yet exist.

## To Activate

Before Sprint 55, the following must be built:
1. Contractor license lookup integrated into entity search
2. Inspection status exposed via permit_lookup or dedicated tool
3. Contractor-specific dashboard or filtered search view

Update this file and remove the DEFERRED status when the above are ready.

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
