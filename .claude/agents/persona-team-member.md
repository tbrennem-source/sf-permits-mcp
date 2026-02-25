---
name: persona-team-member
description: "DEFERRED: Sprint 55+. Stub for team member persona QA agent — tests workflows for internal team members (architects, planners) collaborating on shared projects via sfpermits.ai."
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---

# Persona Agent: Team Member (DEFERRED)

## Status

**DEFERRED: Sprint 55+**

This agent is a stub. Do not invoke it for active QA work until it is fully specified.

## Planned Purpose

Simulate the workflow of a team member within an architecture or development firm who uses sfpermits.ai collaboratively:
- Shares saved searches or property watches with colleagues
- Reviews permit activity on shared projects
- Assigns follow-up tasks based on permit changes
- Views colleagues' notes on permit history

## Why Deferred

Team/collaboration workflows require:
- Team or organization model (multi-user shared state)
- Shared watch lists or project workspaces
- Comment/annotation layer on permits or properties
- Role-based access within a team (owner vs. member)

None of these features currently exist. Team member persona QA cannot meaningfully test collaboration workflows that don't yet exist.

## To Activate

Before Sprint 55, the following must be built:
1. Organization/team model in user schema
2. Shared watch lists or project workspaces
3. Team member invitation and role assignment
4. Activity feed scoped to team

Update this file and remove the DEFERRED status when the above are ready.

## Worktree Isolation Rule
All build agents MUST run in isolated worktrees. Never modify files outside your owned file list.
