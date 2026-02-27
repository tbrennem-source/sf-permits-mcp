# Design Canon — sfpermits.ai

> The immutable design identity. What doesn't change sprint to sprint.

## Identity

**Obsidian Intelligence.** sfpermits.ai is a dark, quiet instrument that makes San Francisco's permit bureaucracy legible. It doesn't shout. It doesn't sell. It distills 18 million government records into calm, precise answers.

The aesthetic is a polished obsidian surface — nearly black, with a single teal accent that glows where attention is needed. Data is the content. The design gets out of the way.

## Emotional Register

| Attribute | What it means | What it is NOT |
|-----------|---------------|----------------|
| **Precision** | Every number, every label, every spacing choice is deliberate | Not approximate or sloppy |
| **Calm authority** | Confident without being loud. The data speaks. | Not aggressive, not salesy |
| **Editorial** | Content is curated and presented, not dumped | Not a data dump or spreadsheet |
| **Terminal intelligence** | Monospace data evokes the precision of a command line | Not retro-terminal cosplay |
| **Quiet luxury** | Premium through restraint, not decoration | Not minimalist-for-minimalism |

## Core Constraints

These are load-bearing walls. Do not violate them.

1. **Dark-first.** There is no light mode. The obsidian palette is the product identity, not a preference toggle.

2. **One accent color.** Teal `#5eead4`. It means "look here." If everything is teal, nothing is. Use it for: active states, links, focus rings, status-green, data highlights. That's it.

3. **Two typefaces, strict roles.** IBM Plex Sans for headlines, prose, labels, descriptions, body copy. JetBrains Mono for data, numbers, addresses, inputs, CTAs, the wordmark. Never swap them.

4. **Weight 300 is the signature.** Light weight on IBM Plex Sans headlines is what makes this site distinctive. Most sites use 600+. We use 300. It reads as refined, editorial, quietly confident.

5. **No filled buttons.** Primary CTAs are ghost text — monospace, tertiary color, underline on hover, arrow suffix (`→`). The interface invites; it does not demand.

6. **Glass cards, not boxes.** Containers use transparent-tinted backgrounds with barely-visible borders (`rgba(255,255,255, 0.06)`). Content floats on obsidian. No harsh edges, no drop shadows, no solid backgrounds.

7. **Data is monospace. Prose is sans.** This split is non-negotiable. Permit numbers, addresses, dates, costs, status values, inputs, CTAs — JetBrains Mono. Headlines, descriptive text, navigation, explanations — IBM Plex Sans.

8. **Narrow focus.** Public pages max at 1000px. Admin pages at 1200px. We do not stretch to fill widescreen monitors. Focused reading width > visual sprawl.

9. **Signal colors are semantic.** Green (`#34d399`) = on track. Amber (`#fbbf24`) = warning/stalled. Red (`#f87171`) = alert/violation. Blue (`#60a5fa`) = informational. These are the ONLY non-teal colors allowed, and only for their semantic purpose.

10. **Animation serves comprehension.** Scroll reveals help users parse sections sequentially. Count-up stats create engagement. Ambient glow sets mood on landing. None of these are decorative — they all serve information hierarchy or emotional framing.

## What This Is Not

- Not a SaaS dashboard (no sidebar nav, no breadcrumbs, no nested modals)
- Not a government website (no blue/red, no serif fonts, no institutional feel)
- Not a startup landing page (no gradient CTAs, no testimonial carousels, no pricing tables)
- Not a terminal emulator (monospace is for precision, not nostalgia)

## The Test

When evaluating any design decision, ask: **"Does this feel like a polished obsidian instrument?"** If it feels like a SaaS dashboard, a government form, or a marketing page — it's wrong.
