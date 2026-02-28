## Sprint 94 — T1-C: Visual-First Showcase Card Redesign

### Changed

**showcase_whatif.html** — Complete visual redesign (Simulation Intelligence)
- Replaced data table (9-row comparison) with two tinted side-by-side columns
- Left column: green tint, "Kitchen remodel", bold "2 weeks", "$1,200 · OTC"
- Right column: amber tint, "Kitchen + Bath + Wall", bold "5 months", "$6,487 · In-house"
- Horizontal progress bars below each column show relative timeline magnitude
- Added "Simulation Intelligence" label (--text-tertiary, mono, uppercase)
- Updated CTA to "Compare your project →" → /tools/what-if?demo=kitchen-vs-full
- Design lint: 5/5 clean after fixing rgba tint to use --signal-amber derived values

**showcase_risk.html** — Complete visual redesign (Predictive Intelligence)
- Replaced linear gauge bar + triggers list + impact table with circular SVG arc gauge
- SVG gauge: 120x120, circle r=50, stroke-dasharray=314, dashoffset=237 (fills to 24.6%)
- Large "24.6%" text centered in gauge (mono, 20px, --text-primary)
- Arc stroke uses --dot-amber for correct semantic color at small sizes
- Context label: "Restaurant alterations in the Mission"
- Ghost link: "5 common triggers" → /tools/revision-risk?demo=restaurant-mission
- Added "Predictive Intelligence" label
- Updated CTA to "Check your risk →"
- Design lint: 5/5 clean

**showcase_entity.html** — Visual redesign (Network Intelligence)
- Replaced static SVG with animated node graph: 4 satellite nodes, 6 edges in --accent (teal)
- Added CSS float animations (4 independent keyframes, 3.8–5.1s periods, alternating up/down)
- Cross-edges between node pairs for richer network topology
- Node sizing: Arb Inc (r=22), Pribuss Engineering (r=16), Hathaway Dinwiddie (r=13), Gensler (r=10)
- Stats line below: "63 permits · 12,674 connected projects"
- Added "Network Intelligence" label
- Updated CTA to "Explore network →" → /tools/entity-network?address=1+MARKET
- Design lint: 5/5 clean

**showcase_delay.html** — Complete visual redesign (Financial Intelligence)
- Replaced monthly-cost input row + warning badge + scenario table with hero number display
- "$500" in clamp(2.5rem, 5vw, 3rem) mono amber text — visual first, reads in 1 second
- "/day" unit in --text-secondary beside the hero number
- "Expected total: $41,375" on next line (mono, --text-primary)
- "Based on $15K/mo carrying cost" as supporting context (--text-tertiary)
- Added "Financial Intelligence" label
- Updated CTA to "Calculate your cost →" → /tools/cost-of-delay?demo=restaurant-15k
- Design lint: 5/5 clean

**showcase-entity.js** — Updated for new node structure
- Preserved IntersectionObserver entrance animation logic
- Updated to handle animationPlayState (pauses CSS float animations until nodes fade in)
- Added edge opacity restoration respecting per-edge opacity attribute values
- Removed edge label fade-in (edge labels removed from new design)

### Tests Added

**tests/test_showcase_cards_redesign.py** — 32 new tests (Sprint 94 visual-first design)
- 7 tests for What-If: renders, label, two columns, big numbers, sub costs, bars, CTA link
- 8 tests for Risk: renders, label, SVG gauge, 24.6% value, amber color, context, triggers link, CTA
- 9 tests for Entity: renders, label, SVG, central node, secondary nodes, teal edges, float, stats, CTA
- 8 tests for Delay: renders, label, $500 hero, /day unit, expected total, basis text, amber class, CTA

**tests/test_showcase_components.py** — 12 existing tests updated
- Updated WhatIf tests: removed "KITCHEN ONLY"/"KITCHEN + BATH + WALL" label assertions (removed from visual design), updated strategy callout check, added visual column class assertions
- Updated Risk tests: removed severity badge "HIGH" and "21,596" sample size and top triggers (grease interceptor/ventilation) — all removed from visual-first card; replaced with gauge and label checks
- Updated Delay tests: removed $15,000 monthly cost, scenario table (Best case/Typical/Conservative/Worst case), cost values table, SFFD-HQ warning, p75 recommendation — replaced with hero number, expected total, and Financial Intelligence label checks

All 74 showcase tests passing. Full suite: 4453 passed, 6 skipped, 17 xfailed.
Design token lint: 5/5 clean across all 4 modified files.
