## Sprint 90 — T1 Landing Showcase (MCP Demo)

### Added
- **MCP Demo Chat Transcript Component** — animated chat section for landing page showing Claude using sfpermits.ai tools
  - 3 demo conversations cycle: What-If Scope Comparison (leads), Stuck Permit Diagnosis, Cost of Delay
  - Scroll-triggered animation via IntersectionObserver (threshold 0.3)
  - User messages fade-in + slide-up, tool call badges pulse with stagger, Claude responses type line by line
  - Tables render as pre-built HTML blocks (instant, not typed)
  - 4s pause between demos, auto-cycles indefinitely
  - Manual prev/next arrows and navigation dots
  - Dark terminal-style window with red/amber/green title bar dots
  - CTA section: "Connect your AI" button + 3-step explainer (Connect, Ask, Get Intelligence)
- **Mobile treatment (480px breakpoint)**
  - Tables collapse to stacked key-value cards (e.g., "Kitchen Only" card, "Kitchen + Bath + Wall" card)
  - Long Claude responses capped at 300px with "See full analysis" expand button
  - Tool badges wrap to 2 lines max
- **Reduced motion support** — all animations disabled, content shown immediately
- **43 tests** covering template rendering, demo presence, rotation order, tool badges, CTA, mobile CSS, JS structure, navigation, transcript accuracy

### Files Created
- `web/templates/components/mcp_demo.html` — component template with all 3 demos inline
- `web/static/mcp-demo.css` — styling, animations, mobile breakpoints, reduced motion
- `web/static/mcp-demo.js` — scroll trigger, typing animation, auto-advance, manual controls
- `tests/test_mcp_demo.py` — 43 tests across 10 test classes
