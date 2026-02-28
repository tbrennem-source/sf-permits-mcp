<!-- LAUNCH: Paste into any CC terminal (fresh or reused from a previous sprint):
     "Read sprint-prompts/sprint-69-session4-portfolio-pwa.md and execute it" -->

# Sprint 69 — Session 4: Portfolio Artifacts + PWA + Showcase Polish

You are a build agent for Sprint 69 of sfpermits.ai, following the **Black Box Protocol**.

## SETUP — Session Bootstrap

Before doing anything else, ensure you are on a clean worktree branched from latest main:

1. **Navigate to the main repo root** (escape any old worktree):
   ```
   cd /Users/timbrenneman/AIprojects/sf-permits-mcp
   ```
2. **Pull latest main** (includes all prior sprint merges):
   ```
   git checkout main && git pull origin main
   ```
3. **Create your worktree:**
   Use EnterWorktree with name `sprint-69-s4`

If EnterWorktree fails because a worktree with that name already exists, remove it first:
```
git worktree remove .claude/worktrees/sprint-69-s4 --force 2>/dev/null; true
```
Then retry EnterWorktree.

---

## PHASE 1: READ

Before writing any code, read these files:
1. `CLAUDE.md` — project structure, key numbers, full architecture
2. `STATUS.md` or Chief STATUS
3. `CHANGELOG.md` — sprint history (understand the project trajectory)
4. `README.md` — current public-facing description
5. `web/routes_public.py` — where you'll add the /robots.txt enhancement
6. `web/templates/landing.html` — understand current landing page
7. `data/knowledge/SOURCES.md` — data source inventory for portfolio brief
8. `docs/TIMELINE_ESTIMATION.md` — methodology for portfolio brief
9. `scenario-design-guide.md` — understand the project's behavioral scenarios
10. Read a few lesson files from dforge if the MCP tools are available (list_lessons, get_lesson) — understand Tim's methodology framework

---

## PHASE 2: BUILD

### Task 1: Portfolio Brief (`docs/portfolio-brief.md`)

This is the document a hiring manager, potential client, or partner reads in 5 minutes to understand Tim's work. It must be specific, honest, and impressive.

**Structure:**

```markdown
# Tim Brenneman — AI-Native Software Development

## What I Built
sfpermits.ai: San Francisco building permit intelligence platform analyzing
18.4M records across 22 government data sources. Live at sfpermits.ai.

## The Numbers
[Pull REAL numbers from CLAUDE.md, STATUS.md, and the codebase]
- X sprints of production development (count from CHANGELOG.md)
- 3,329 automated tests
- 29 MCP tools across 7 functional domains
- 1.8M contacts resolved into 1M entities via 5-step cascade
- 3.9M routing records with station velocity baselines
- AI vision plan analysis with EPR compliance checking
- Nightly pipeline: SODA API → change detection → velocity → RAG → morning briefs

## Technical Architecture
[Describe the actual stack: Flask + DuckDB + PostgreSQL + Claude Vision + HTMX]
[Mention: Blueprint-organized routes (142), 59 Postgres tables, 4-tier knowledge base]

## How I Built It
Specification-driven AI-native development using dforge methodology:
- Black Box Protocol: spec in → working software out → QA gate → deploy
- Multi-agent swarm builds: 4+ parallel Claude Code agents per sprint
- Behavioral scenarios as quality gates (73 in design guide)
- Intent engineering: CANON.md, PRINCIPALS.md, SCENARIOS.md govern agent behavior

## What This Demonstrates
[Be specific about skills, not generic]
- Complex data pipeline engineering (22 SODA API sources, entity resolution, graph analysis)
- AI integration into production workflows (not demos)
- Methodology design for human-AI collaboration
- Domain expertise in municipal permitting systems

## The Framework: dforge
[Describe dforge — templates, frameworks, lessons, audit system]
[Link to dforge repo if public, or describe what it does]

## Contact
[Leave placeholder for Tim to fill]
```

**Read the actual codebase** to get the right numbers. Don't guess — verify. Count sprints from CHANGELOG.md. Count tools from server.py. Count tests by running pytest if possible.

### Task 2: LinkedIn Update (`docs/linkedin-update.md`)

Write the updated LinkedIn profile sections:

**Headline** (~120 chars):
Something like: "Building AI-native software that builds itself | Creator of dforge | [X] sprints of production agentic development"

**About section** (3-4 paragraphs):
- Paragraph 1: What sfpermits.ai is and why it matters
- Paragraph 2: The dforge methodology — what it is, why it exists
- Paragraph 3: The thesis — AI development needs methodology the same way software development needed Agile
- Paragraph 4: What's next

**Experience entry:**
- Title, period, bullet points of concrete accomplishments
- Specific numbers, not vague claims

### Task 3: dforge Public README (`docs/dforge-public-readme.md`)

Write a README suitable for a public GitHub repo:
- What dforge is (1 paragraph)
- The problem it solves ("AI development without methodology = chaos")
- Core concepts: 5 Levels of AI-Native Development, Black Box Protocol, Behavioral Scenarios, CANON/PRINCIPALS
- Template and framework inventory (list what's available)
- "Born from [X] sprints of production development on sfpermits.ai"
- Getting started section

### Task 4: Model Release Probes (`docs/model-release-probes.md`)

Create 12-15 domain-specific prompts to run against every new Claude release:

For each probe:
- **Prompt text** — the exact prompt to send
- **Expected capability** — what a good model should produce
- **What "better" looks like** — how a newer model could improve
- **Baseline** — what current Claude produces (brief note)

Categories:
1. **Permit prediction** (3 probes) — given a project description, predict permits needed
2. **Vision analysis** (2 probes) — given a plan set description, identify EPR issues
3. **Multi-source synthesis** (3 probes) — combine data from multiple sources into a coherent answer
4. **Entity reasoning** (2 probes) — reason about entity networks and relationships
5. **Specification quality** (2 probes) — evaluate whether a behavioral scenario is well-formed
6. **Domain knowledge** (2 probes) — answer SF-specific permitting questions

### Task 5: PWA Manifest

Create `web/static/manifest.json`:
```json
{
  "name": "sfpermits.ai",
  "short_name": "SF Permits",
  "description": "San Francisco Building Permit Intelligence",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0B0F19",
  "theme_color": "#22D3EE",
  "icons": [
    { "src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Create placeholder icon files (simple colored squares at 192x192 and 512x512 — can be replaced later with real branding).

Add to `web/routes_public.py`:
- `<link rel="manifest" href="/static/manifest.json">` — add this to the landing.html `<head>` (Session 1 owns landing.html, so instead add it via a note in CHECKCHAT)
- Add Apple meta tags for iOS home screen: `<meta name="apple-mobile-web-app-capable" content="yes">`

**Actually, since Session 1 owns landing.html, do NOT modify it.** Instead:
- Create manifest.json and icon placeholders
- Document in CHECKCHAT what needs to be added to templates (Session 1 can pick it up, or it gets added in merge)

### Task 6: robots.txt Enhancement

Modify `/robots.txt` route (find it in routes_public.py or routes_misc.py) to:
- Allow all crawlers on public pages
- Disallow /admin/, /cron/, /api/, /auth/, /demo
- Add sitemap reference

If robots.txt is currently a static file, convert it to a dynamic route.

---

## PHASE 3: TEST

Write `tests/test_sprint69_s4.py`:
- docs/portfolio-brief.md exists and has >500 words
- docs/linkedin-update.md exists and has headline + about sections
- docs/dforge-public-readme.md exists and mentions dforge
- docs/model-release-probes.md exists and has >10 probes
- web/static/manifest.json exists and has valid JSON
- manifest.json has correct theme_color (#22D3EE)
- Icon placeholder files exist (192 and 512)
- robots.txt disallows /admin/
- robots.txt allows /search
- Portfolio brief contains accurate test count (verify against pytest output)
- Portfolio brief mentions entity resolution

Target: 12+ new tests.

Run `pytest tests/ --ignore=tests/test_tools.py -q` after each task.

---

## PHASE 4: SCENARIOS

Append 3-5 scenarios to `scenarios-pending-review.md`:
- "Portfolio brief contains accurate project statistics derived from actual codebase"
- "Model release probes cover all 6 capability categories"
- "PWA manifest enables add-to-homescreen on iOS and Android"

---

## PHASE 5: QA (termRelay)

Write `qa-drop/sprint69-s4-portfolio-pwa-qa.md`.

**Checks:**
1. Verify docs/portfolio-brief.md contains "Tim Brenneman" and real numbers
2. Verify docs/linkedin-update.md has headline and about sections
3. Verify docs/model-release-probes.md has >10 probe entries
4. Verify web/static/manifest.json is valid JSON
5. Navigate to /robots.txt — verify 200 and contains Disallow: /admin/
6. Navigate to /static/manifest.json — verify 200 and valid JSON
7. Count words in portfolio-brief.md — must be >500
8. Verify portfolio-brief.md mentions the correct test count
9. Verify dforge README mentions behavioral scenarios

Write results to `qa-results/sprint69-s4-results.md`

---

## PHASE 6: CHECKCHAT

### DeskRelay HANDOFF
- [ ] Portfolio brief: would a hiring manager reading this in 5 minutes understand what Tim built?
- [ ] LinkedIn update: is the headline compelling? Does the about section tell a story?
- [ ] dforge README: would a developer reading this want to try dforge?

### MERGE NOTES
- Session 1 owns `landing.html` — the manifest.json link tag needs to be added there after merge
- If Session 1 has already merged, add the link tag. If not, document it for the merge ceremony.

---

## File Ownership (Session 4 ONLY)
- `docs/portfolio-brief.md` (NEW)
- `docs/linkedin-update.md` (NEW)
- `docs/dforge-public-readme.md` (NEW)
- `docs/model-release-probes.md` (NEW)
- `web/static/manifest.json` (NEW)
- `web/static/icon-192.png` (NEW — placeholder)
- `web/static/icon-512.png` (NEW — placeholder)
- `tests/test_sprint69_s4.py` (NEW)
- `qa-drop/sprint69-s4-portfolio-pwa-qa.md` (NEW)
- `qa-results/sprint69-s4-results.md` (NEW)

Do NOT touch: `web/templates/landing.html`, `web/templates/search_results_public.html`, `web/templates/methodology.html`, `web/static/design-system.css`, `web/static/style.css`, `web/routes_search.py`, `web/routes_misc.py` (except robots.txt if it's there), `web/routes_api.py`, `src/`
