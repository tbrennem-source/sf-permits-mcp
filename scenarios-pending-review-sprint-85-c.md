## SUGGESTED SCENARIO: new developer finds clean sprint-prompts directory
**Source:** Sprint 85-C stale file cleanup
**User:** expediter
**Starting state:** New developer clones the repo and opens sprint-prompts/ for context
**Goal:** Quickly understand current and recent sprint history without wading through obsolete files
**Expected outcome:** Only current/recent sprint prompts are visible (qs8-*, qs9-*, sprint-79 through sprint-82); no qs3-*, qs4-*, qs5-*, qs7-*, sprint-64 through sprint-69, or sprint-74 through sprint-78 files are present
**Edge cases seen in code:** Stale sprint files from 2+ generations back (qs3, sprint-64) were mixed in with active ones — cleanup needed explicit retention rules to avoid deleting current qs8/qs9/sprint-79-82 files
**CC confidence:** medium
**Status:** PENDING REVIEW
