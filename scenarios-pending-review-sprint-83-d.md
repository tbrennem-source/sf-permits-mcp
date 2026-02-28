## SUGGESTED SCENARIO: Post-sprint cleanup removes all merged worktree branches

**Source:** Sprint 83-D branch cleanup task
**User:** admin
**Starting state:** Repository has accumulated stale worktree branches from multiple sprints that have since been merged into main; some branches have active worktree directories, some do not
**Goal:** Remove all stale merged worktree branches to reduce repo clutter without disrupting any active work sessions
**Expected outcome:** Branches that are merged into main AND have no active worktree checked out are deleted; branches currently checked out in active worktrees are not deleted (git prevents this); unmerged sprint branches are reported but not deleted; git worktree prune clears stale admin references
**Edge cases seen in code:** A branch can be merged into main but still have an active worktree checked out (git will refuse deletion with `+` prefix marker in --merged output); prunable worktrees (nested inside other worktrees) are flagged but only cleared by prune, not by branch deletion
**CC confidence:** medium
**Status:** PENDING REVIEW
