# dforge — AI-Native Development Framework

dforge is a methodology framework for building production software with AI agents. It provides the specifications, governance, and quality gates that turn "AI can write code" into "AI can build production systems." Born from 21+ sprints of real development on [sfpermits.ai](https://sfpermits-ai-production.up.railway.app), where every pattern was battle-tested before being generalized.

## The Problem

AI development without methodology is chaos.

AI agents can write code. They can write a lot of code, very fast. But without specifications they don't know what to build. Without governance they make inconsistent decisions. Without quality gates they produce code that works in demos but breaks in production. Without behavioral scenarios they can't distinguish "done" from "deployed."

The gap between "developer uses AI tools" and "AI builds production systems" is entirely a methodology gap.

## Core Concepts

### Five Levels of AI-Native Development

| Level | Name | Description |
|-------|------|-------------|
| 0 | Manual | Developer writes all code, AI unused |
| 1 | Assisted | AI autocomplete, chat-based help |
| 2 | Delegated | AI writes functions/files from prompts |
| 3 | Specified | Behavioral specs drive AI builds, QA gates enforce quality |
| 4 | Autonomous | Multi-agent swarms, self-coordinating builds, spec-to-deploy |
| 5 | Dark Factory | Specs in, software out — human sets intent, AI handles everything else |

Most teams are at Level 1-2. dforge provides the infrastructure to operate at Level 3-4.

### Black Box Protocol

The build pipeline that makes autonomous development reliable:

1. **READ** — Agent reads CLAUDE.md, STATUS.md, relevant specs
2. **BUILD** — Implement the feature
3. **TEST** — Run pytest, fix failures
4. **SCENARIOS** — Propose behavioral scenarios for the feature
5. **QA** — Run Playwright-based browser tests, capture screenshots
6. **CHECKCHAT** — Verify, document, capture, ship, prep next

Every step is enforced by hooks. Incomplete deliverables are blocked.

### Behavioral Scenarios

Scenarios define what the system MUST do — not how, but what outcomes users see:

```
SCENARIO: Hold signal produces AT_RISK regardless of other permit signals
User: expediter
Starting state: Property has a permit with a DBI hold
Goal: View property health assessment
Expected outcome: Property shows AT_RISK status, hold signal is primary factor
```

Scenarios are the quality contract between the planning layer (human + Claude.ai) and the execution layer (Claude Code agents). Build agents propose scenarios. The planning layer reviews and approves them. QA enforces them.

### Governance Documents

Three documents control agent behavior:

- **CANON.md** — What the project KNOWS and how much to trust each source. 7-tier hierarchy from live data (T0) to unverified community (T6). Prevents agents from hallucinating facts.
- **PRINCIPALS.md** — Behavioral rules and explicit non-behaviors. The project's constitution. Defines what the system must NOT do, which is often more important than what it should do.
- **SCENARIOS.md** — Behavioral scenarios that define quality. The acceptance criteria for every feature.

### Multi-Agent Swarm Coordination

For complex sprints, dforge coordinates 4+ parallel Claude Code agents:

- Each agent owns an isolated file domain (no conflicts)
- Agents build in worktree branches
- Orchestrator validates file ownership boundaries
- Sequential merge with full test suite between each step
- Shared file protocol for the rare cases where agents touch the same file

## Templates (12)

| Template | Purpose |
|----------|---------|
| CANON.md | Knowledge trust hierarchy |
| PRINCIPALS.md | Behavioral rules and constraints |
| STATUS.md | Project health tracker |
| Black Box Protocol | 3-stage build pipeline |
| Swarm Coordination | Multi-agent build patterns |
| Sprint Close Gate | End-of-sprint checklist |
| Prod Push Gate | Pre-production promotion checklist |
| Retrospective | Post-sprint learning capture |
| Weekly Update | Progress tracking |
| Monthly Review | Strategic review |
| SOP Documentation | Documentation update procedures |
| Newsletter Extraction | Learning capture from external sources |

## Frameworks (3)

| Framework | Purpose |
|-----------|---------|
| AI-Native Development | Five Levels maturity model, Specification Architect, Maturity Diagnostic, Org Redesign |
| Project Intake Interview | 8-step interview to bootstrap CANON, PRINCIPALS, SCENARIOS, CLAUDE.md |
| Project Framework Meta-Spec | Master specification for dforge itself |

## Lessons Learned (16)

Accumulated wisdom from production development:

- **"Deployed != Landed"** — Code on production doesn't mean the feature works for users
- **"The Agent That Builds Cannot Grade QA"** — Separation of build and verification is non-negotiable
- **"Schema Migrations in Startup = Time Bomb"** — DDL in application startup creates race conditions under multi-worker deployment
- **"Confidence Without Completeness is Dangerous"** — An AI that sounds certain about partial information is worse than one that says "I don't know"
- **"CC Authoring Its Own Scenarios Grades Its Own Homework"** — Build agents proposing and verifying their own scenarios defeats the purpose

## Built From

- 21+ sprints of production development on sfpermits.ai
- 3,327 automated tests
- 29 MCP tools across 7 domains
- 73 behavioral scenarios (reviewed from 102 candidates)
- 16 postmortem lessons
- 4 critical-severity incidents resolved

## Getting Started

1. **Run the intake interview**: `run_intake(project_name="your-project", project_type="greenfield")` — generates CANON.md, PRINCIPALS.md, SCENARIOS.md, and CLAUDE.md
2. **Audit an existing project**: `audit_project(project_name="your-project")` — scores across 8 health dimensions
3. **Browse templates**: `list_templates()` then `get_template(slug)` for any template
4. **Read lessons**: `list_lessons()` then `get_lesson(slug)` for accumulated wisdom

## MCP Server

dforge is available as an MCP server for integration with Claude.ai and Claude Code:

```
Tools: list_templates, get_template, list_frameworks, get_framework,
       run_intake, audit_project, list_lessons, get_lesson, portfolio_status
```

## License

[License to be determined]
