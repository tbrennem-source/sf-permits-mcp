## SUGGESTED SCENARIO: Admin reviews stale task inventory
**Source:** QS5-D task hygiene diagnostic sweep
**User:** admin
**Starting state:** Admin has access to Chief brain state with 50+ open tasks accumulated over multiple sprints
**Goal:** Review infrastructure tasks to determine which are completed, superseded, or still needed
**Expected outcome:** Stale tasks are closed with evidence, current tasks are updated with accurate descriptions, and new focused follow-ups are created for items needing verification on prod/staging
**Edge cases seen in code:** Tasks may reference features that were built under different task numbers (e.g., #207 "orphaned test files" was wrong — source files exist). Task descriptions may be stale while the underlying work was completed in a different sprint.
**CC confidence:** high
**Status:** PENDING REVIEW
