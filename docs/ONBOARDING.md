# Developer Onboarding

Welcome to SF Permits MCP. This doc gets you from zero to running locally and making your first contribution.

## What This Project Is

An AI-powered San Francisco building permit assistant. It has:
- **MCP server** (20 tools) — queries permit data, entity networks, knowledge base, AI vision analysis
- **Flask web UI** — search, plan analysis, morning briefs, admin tools
- **PostgreSQL + pgvector** on Railway (production)
- **DuckDB** for local entity resolution
- **4-tier knowledge base** of curated SF permitting rules

The live site: https://sfpermits-ai-production.up.railway.app

## Prerequisites

- Python 3.11+
- Git
- GitHub account (you'll be added as a collaborator)
- Claude Code CLI (`npm install -g @anthropic-ai/claude-code`)

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/tbrennem-source/sf-permits-mcp.git
cd sf-permits-mcp

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies (including dev/test tools)
pip install -e ".[dev]"

# 4. Run the tests — this is your first sanity check
pytest tests/ -v

# 5. Run the web UI locally
python -m web.app
# Opens at http://localhost:5001
```

**Note:** The production database (PostgreSQL on Railway) is not accessible from your local machine. The app auto-detects local mode and uses DuckDB or mock data where needed. You don't need any API keys or env vars to run tests.

For full local functionality (AI features, vision analysis), ask Tim for the `.env` file with API keys. Never commit this file.

## Project Structure (Key Files)

```
src/server.py           — MCP server entry point (20 tools registered here)
src/tools/              — One file per tool group (start here to understand features)
src/vision/             — AI vision modules (Claude Vision API)
src/knowledge.py        — Knowledge base loader + semantic search
web/app.py              — Flask routes (the biggest file — ~2000 lines)
web/templates/          — Jinja2 + HTMX templates
data/knowledge/tier1/   — Curated JSON knowledge files
tests/                  — 1,033+ tests
CHANGELOG.md            — Session-by-session history of what was built
docs/ARCHITECTURE.md    — Data flow, schema, design decisions
```

## How We Work

### Agentic Coding with Claude Code

This project is built primarily using Claude Code — an AI coding assistant that runs in your terminal. You'll use it too. The workflow:

1. Start Claude Code in the project directory: `claude`
2. Describe what you want to build or fix
3. Claude reads the codebase, makes changes, runs tests
4. You review what it did, iterate, then commit

**Tips for working with Claude Code:**
- Read `CLAUDE.md` first — it's the project context file that Claude loads every session
- Be specific in your prompts. "Fix the bug in plan analysis where thumbnails don't load" is better than "fix bugs"
- Always review the changes Claude makes before committing. It's your responsibility.
- Run `pytest tests/ -v` after every change — don't trust that it works without tests passing

### Git Workflow

```bash
# 1. Start from latest main
git checkout main
git pull

# 2. Create a feature branch
git checkout -b steven/description-of-change

# 3. Make your changes (with Claude Code or manually)

# 4. Run tests
pytest tests/ -v

# 5. Commit with a clear message
git add <specific files>
git commit -m "feat: short description of what and why"

# 6. Push and open a PR
git push -u origin steven/description-of-change
gh pr create
```

**Branch naming:** Use `steven/` prefix (e.g., `steven/fix-thumbnail-loading`, `steven/add-search-filters`).

**Commit messages:** Start with a type: `feat:`, `fix:`, `docs:`, `test:`, `chore:`. Focus on *why*, not *what*.

### Pull Request Process

Every change goes through a PR that Tim reviews. The PR template will auto-populate — fill it out completely:

1. **What changed?** — 2-3 sentences
2. **How do you know it works?** — Screenshots, test output, or description of manual testing
3. **Tests** — Paste `pytest` output
4. **Checklist** — All items checked

Keep PRs small. One feature or one fix per PR. If a task is big, break it into multiple PRs.

### What "Done" Looks Like

A PR is ready for review when:
- All existing tests pass (`pytest tests/ -v`)
- New tests are added for new functionality
- You've manually tested in the local web UI
- CHANGELOG.md is updated
- The PR template is filled out with evidence

## Key Concepts to Understand

### The Knowledge Base (data/knowledge/)
- **tier1/** — Curated JSON files. These are the "source of truth" for permit rules.
- **tier2/** — Raw text from DBI info sheets (OCR'd PDFs)
- **tier3/** — Administrative bulletins
- **tier4/** — Full code corpus (Planning Code, Building Code). Gitignored due to size.
- **semantic-index.json** — Maps concepts to their authoritative sources. This is how the system knows *which file* answers a question.

### The Tool System (src/tools/)
Each tool is a function that Claude (or the web UI) can call. Read `src/server.py` to see all 20 tools registered. Then look at the individual tool files to understand what each does.

### The Web UI (web/)
Flask + HTMX. Most interactivity is done via HTMX partial page updates rather than a full SPA framework. Templates are in `web/templates/`. The main route file is `web/app.py`.

### Vision / Plan Analysis (src/vision/)
Uses Claude's Vision API to analyze architectural drawings. This is the most complex subsystem — read `docs/ARCHITECTURE.md` section on vision before diving in.

## Things to Never Do

- **Never commit `.env`, API keys, or secrets.** Check `git diff --staged` before every commit.
- **Never push directly to `main`.** Always use a PR.
- **Never run `railway up` or `railway deploy`.** Deployment is automatic via GitHub.
- **Never modify production data directly.** The Railway database is internal-only for a reason.

## Getting Help

- Read `CLAUDE.md` — it's the most up-to-date project reference
- Read `CHANGELOG.md` — understand what was built and when
- Read `docs/ARCHITECTURE.md` — understand why things are designed the way they are
- Ask Tim — he reviews every PR and can point you in the right direction
- Use Claude Code — it knows the codebase and can explain any file
