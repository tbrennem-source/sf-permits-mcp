# QA Script: Design Token Migration — results.html + Content Pages

**Session:** design-token-migration (results + content pages)
**Files migrated:** results.html, methodology.html, about_data.html, demo.html
**Lint score:** 5/5 (0 violations, up from 130)

---

## Prerequisites

- App running: `source .venv/bin/activate && python -m web.app`
- Playwright available for browser steps
- No credentials needed for public pages (/methodology, /about-data, /demo)

---

## 1. Design Token Compliance

```
- [ ] Run: python scripts/design_lint.py --files web/templates/results.html web/templates/methodology.html web/templates/about_data.html web/templates/demo.html --quiet
- [ ] PASS: Score 5/5, 0 violations
- [ ] No --font-display or --font-body references remain in any of the 4 files
- [ ] No --bg-deep, --bg-surface, --bg-elevated, --signal-cyan variables remain
- [ ] No non-token hex colors (#E8ECF4, #8B95A8, #5A6478, etc.)
```

---

## 2. Methodology Page (/methodology)

```
- [ ] Page loads without errors (200 OK)
- [ ] Logo renders as monospaced wordmark (not large bold colored text)
- [ ] Hero h1 "How It Works" renders in --sans at weight 300 (not JetBrains Mono bold)
- [ ] Section headings (01 //, 02 //, etc.) render in --mono uppercase
- [ ] Body paragraphs render in --sans (readable prose font)
- [ ] Data table headers render in --mono uppercase
- [ ] Stat pills show numbers in --mono, labels in --sans
- [ ] Flow steps render with teal (--accent) step-num labels
- [ ] Example boxes use left-border accent pattern (not blue left border)
- [ ] Limitations card uses red left border (insight--red pattern)
- [ ] Footer links are teal (--accent), not cyan (#22D3EE)
- [ ] Mobile (375px): flowchart hides, flow-list shows, hero h1 ≤ 1.6rem
```

---

## 3. About the Data Page (/about-data)

```
- [ ] Page loads without errors (200 OK)
- [ ] Hero h1 "About the Data" in --sans weight 300
- [ ] Data inventory table: column headers in --mono uppercase 10px
- [ ] Highlighted cells (dataset names) render in --mono teal (--accent)
- [ ] Four tier cards render in obsidian-light background
- [ ] Tier numbers ("Tier 1") render in --mono uppercase teal
- [ ] Pipeline schedule: time values in --mono teal
- [ ] Stat pills: 18.4M, 22, 59, 2.05 GB — numbers in --mono
- [ ] Mobile (375px): tier-grid collapses to single column
```

---

## 4. Demo Page (/demo)

```
- [ ] Page loads without errors (200 OK, requires demo address data)
- [ ] "Live Demo" badge renders in amber tones (not blue background)
- [ ] Logo renders as monospaced small-caps wordmark
- [ ] Address renders in --mono (data font)
- [ ] Subtitle renders in --sans (prose font)
- [ ] Callout annotations render in teal with accent-glow background
- [ ] Stat pills: values in --mono, labels in --sans
- [ ] Permit table: column headers in --mono 10px uppercase
- [ ] Status badges (Issued, Filed, Complete, Expired) use chip pattern
- [ ] Severity badges render correctly in all 5 tiers
- [ ] Routing progress bars: station names in --mono, bars use signal colors
- [ ] Entity list: names in --sans, role/permit-count in --mono
- [ ] Alert items (violation/complaint) use left-border insight pattern
- [ ] CTA "Get Started →" renders as ghost-cta (underline on hover, not solid blue button)
- [ ] Architecture numbers (30, 1M, 576K, 3.9M) in --mono teal
- [ ] Mobile (375px): demo-grid collapses to single column
```

---

## 5. Results Tabs (requires authenticated search)

```
- [ ] Methodology card summary renders in --mono, not hardcoded #888
- [ ] Methodology card summary hover turns teal (--accent)
- [ ] Methodology body background is obsidian-light with left accent border
- [ ] Formula steps render in --mono font
- [ ] Station breakdown table headers render in --mono uppercase
- [ ] Coverage gaps text is --signal-amber (not #f0ad4e)
- [ ] Cost-of-delay box: amber left border, amber title text
- [ ] Cost-of-delay table headers in --mono uppercase
- [ ] Share bar uses dark theme (dark background, teal border on hover)
- [ ] Share email modal: dark obsidian background (not white)
- [ ] Email inputs in share modal: dark theme, --mono font, teal focus ring
- [ ] Send/Cancel buttons: dark action-btn style
- [ ] "Loading similar projects..." uses centered --sans text (not hardcoded #888)
```

---

## DESIGN TOKEN COMPLIANCE

- [ ] Run: python scripts/design_lint.py --changed --quiet
- [ ] Score: 5/5
- [ ] No inline colors outside DESIGN_TOKENS.md palette
- [ ] Font families: --mono for data, --sans for prose (spot check 3 elements per page)
- [ ] Components use token classes (glass-card, obs-table, ghost-cta, etc.)
- [ ] Status dots use --dot-* not --signal-* colors
- [ ] Interactive text uses --text-secondary or higher (not --text-tertiary)
- [ ] New components logged in DESIGN_COMPONENT_LOG.md: N/A (no new components — existing patterns applied)
