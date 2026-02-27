# Design Migration Manifest — sfpermits.ai

> All 86 templates categorized by migration status. This is the task list for swarm agents.
>
> **Authority:** `docs/DESIGN_TOKENS.md` defines the target state. Every template should end up using `fragments/head_obsidian.html` and CSS custom properties from the tokens bible.

## Migration Status Key

| Status | Meaning |
|--------|---------|
| **Migrated** | Uses `head_obsidian.html` include. Tokens bible compliant. No action. |
| **Partial** | Uses some obsidian tokens but not `head_obsidian.html`. Needs cleanup. |
| **Self-contained** | Has its own full `<style>` block defining vars from scratch. Needs extraction to shared system. |
| **Legacy** | Uses old `style.css` with no obsidian tokens. Full migration needed. |
| **Email** | Inline CSS. Different rules — do not migrate to design-system.css. |
| **Fragment** | Partial template included by others. Inherits parent's CSS. Audit tokens only. |

---

## Summary

| Category | Count | Action | Sprint Priority |
|----------|-------|--------|-----------------|
| Already migrated | 10 | None | — |
| Email templates | 9 | Keep inline. Update palette only. | Low |
| Fragments (obsidian tokens) | 18 | Audit token names | Low |
| Fragments (needs tokens) | 6 | Minor cleanup | Low |
| Public pages (self-contained) | 9 | Extract styles → head_obsidian | **Sprint 1** |
| Auth pages (partial/legacy) | 15 | Swap to head_obsidian, clean styles | **Sprint 2** |
| Admin pages (partial/legacy) | 9 | Same as Sprint 2 | **Sprint 3** |
| Large complex templates | 3 | Dedicated migration task each | **Sprint 2–3** |

**Total: 86 templates. 10 done. 9 emails (separate path). 67 need migration work.**

---

## Already Migrated (10) — No Action

These include `{% include "fragments/head_obsidian.html" %}` and use tokens bible CSS vars.

| Template | Lines | Notes |
|----------|-------|-------|
| `index.html` | 2,091 | Main authenticated dashboard. 32 script tags. Complex but migrated. |
| `account.html` | 300 | User settings, watches, points. |
| `brief.html` | 820 | Morning brief dashboard. |
| `welcome.html` | 326 | Post-signup onboarding. |
| `admin_activity.html` | 246 | Activity log. Dual-mode (full page + fragment). |
| `admin_costs.html` | 310 | API cost tracking. |
| `admin_feedback.html` | 165 | Feedback list. Dual-mode. |
| `admin_metrics.html` | 194 | Usage metrics. |
| `admin_ops.html` | 217 | Operational controls. |
| `admin_perf.html` | 302 | Performance metrics. |

---

## Email Templates (9) — Separate Path

Inline CSS, table-based layout. Do NOT use design-system.css. Update palette to match obsidian tokens where colors differ. No structural migration.

| Template | Lines | Type |
|----------|-------|------|
| `brief_email.html` | 422 | Full email: morning brief |
| `report_email.html` | 526 | Full email: property report |
| `triage_report_email.html` | 262 | Full email: nightly triage |
| `notification_email.html` | 101 | Full email: single permit change |
| `notification_digest_email.html` | 103 | Full email: permit change digest |
| `invite_email.html` | 95 | Full email: magic-link invite |
| `emails/beta_approved.html` | 136 | Full email: beta approval |
| `analysis_email.html` | 132 | Fragment: plan analysis results |
| `plan_analysis_email.html` | 65 | Fragment: async analysis completion |

---

## Fragments (24) — Audit Only

These inherit CSS from their parent template. Migration = ensure they use `var(--token)` not hardcoded hex. No `head_obsidian` needed.

### Already using obsidian tokens (18) — Quick audit

| Fragment | Lines | Notes |
|----------|-------|-------|
| `fragments/head_obsidian.html` | 30 | IS the system. Update with any new tokens. |
| `fragments/nav.html` | 440 | Complex. Already obsidian. Review for tokens bible alignment. |
| `fragments/account_admin.html` | 178 | HTMX loaded. Uses `--accent`, `--glass-border`. |
| `fragments/account_settings.html` | 326 | HTMX loaded. Has own `<style>`. |
| `fragments/admin_intel.html` | 187 | Uses `--text-muted`, nonce styles. |
| `fragments/admin_quality.html` | 151 | Data quality grid. Nonce styles. |
| `fragments/analysis_grouping.html` | 464 | Macros + obsidian vars. |
| `fragments/discover_results.html` | 71 | Uses `var(--surface-2)`, `var(--border)`. |
| `fragments/feedback_widget.html` | 235 | FAB button + modal. |
| `fragments/import_confirmation.html` | ~10 | Uses `var(--success)`. |
| `fragments/inspection_timeline.html` | 43 | Uses `var(--border)`. |
| `fragments/intel_preview.html` | 122 | Sprint 69. Obsidian vars. |
| `fragments/knowledge_quiz.html` | 55 | Uses `var(--surface)`, `var(--text)`. |
| `fragments/primary_address_prompt.html` | ~12 | Uses `var(--accent)`. |
| `fragments/similar_projects.html` | 98 | Uses `var(--text-muted)`. |
| `fragments/tag_editor.html` | 26 | Uses `var(--border)`. |
| `fragments/watch_button.html` | ~15 | HTMX watch action. |
| `fragments/watch_confirmation.html` | 15 | Watch active state. |

### Needs token cleanup (6)

| Fragment | Lines | Issue |
|----------|-------|-------|
| `fragments/brief_prompt.html` | 23 | No CSS vars used. Add tokens. |
| `fragments/login_prompt.html` | ~5 | Bare `<a>` tag. Minimal. |
| `fragments/prep_checklist.html` | ~30 | Own `<style>` block with hardcoded values. |
| `fragments/prep_item.html` | 34 | No CSS vars. `data-status` patterns. |
| `fragments/prep_progress.html` | ~15 | Progress bar. Needs token check. |
| `fragments/severity_badge.html` | 35 | Own `<style>` with hardcoded colors. |

---

## Sprint 1: Public Pages (9 templates)

**Goal:** Every page a visitor can see without logging in uses `head_obsidian.html` and tokens bible CSS.

**Migration pattern for self-contained pages:**
1. Replace bespoke `<style>` block with `{% include "fragments/head_obsidian.html" %}`
2. Map hardcoded hex values to CSS custom properties
3. Remove duplicate font imports (already in head_obsidian)
4. Add `class="reveal"` to content sections
5. Test at 375px and 768px

| Template | Lines | Current Status | Complexity | Swarm Agent |
|----------|-------|----------------|------------|-------------|
| `landing.html` | 743 | Partial (loads design-system.css directly, not via head_obsidian) | Complex | A |
| `auth_login.html` | 158 | Self-contained (own `--accent` vars) | Simple | A |
| `beta_request.html` | 87 | Legacy (style.css only) | Simple | A |
| `error.html` | 109 | Self-contained | Simple | A |
| `search_results_public.html` | 672 | Self-contained (large `<style>`) | Complex | B |
| `demo.html` | 717 | Self-contained (no external CSS) | Complex | B |
| `about_data.html` | 495 | Self-contained (no external CSS) | Medium | C |
| `methodology.html` | 994 | Self-contained (no external CSS) | Complex | C |
| `adu_landing.html` | 281 | Self-contained | Medium | C |

**File ownership for parallel agents:**
- **Agent A:** Landing + auth flow (landing.html, auth_login.html, beta_request.html, error.html)
- **Agent B:** Search + demo (search_results_public.html, demo.html)
- **Agent C:** Content pages (about_data.html, methodology.html, adu_landing.html)

---

## Sprint 2: Authenticated User Pages (15 templates)

**Goal:** All pages a logged-in user interacts with use the obsidian system consistently.

### Partial → Full migration (swap mobile.css for head_obsidian, clean bespoke styles)

| Template | Lines | Complexity | Notes |
|----------|-------|------------|-------|
| `results.html` | 416 | Complex | HTMX fragment injected into index.html. Keep `<style nonce>` pattern. |
| `search_results.html` | 299 | Medium | HTMX fragment. Keep nonce pattern. |
| `report.html` | 968 | Complex | Property report. 4 script tags. |
| `portfolio.html` | 334 | Medium | Portfolio PWA dashboard. |
| `permit_prep.html` | 374 | Complex | Permit prep checklist. |
| `account_prep.html` | 196 | Medium | Onboarding prep form. |
| `consultants.html` | 447 | Complex | Consultant finder. 12 script tags. |
| `analysis_history.html` | 1,568 | Complex | Plan analysis history. 10 script tags. |
| `analysis_compare.html` | 1,183 | Complex | Side-by-side analysis. |
| `plan_processing_page.html` | 54 | Simple | Wrapper page. |
| `plan_results_page.html` | 60 | Simple | Wrapper page. |
| `velocity_dashboard.html` | 740 | Complex | Station routing charts. Dual-mode. |
| `voice_calibration.html` | 409 | Medium | Voice calibration scenarios. |

### Legacy → Full migration

| Template | Lines | Complexity | Notes |
|----------|-------|------------|-------|
| `project_detail.html` | 218 | Medium | Uses style.css. No obsidian. |
| `projects.html` | 117 | Simple | Uses style.css. No obsidian. |
| `analysis_shared.html` | 331 | Medium | Public shareable link. style.css. |

### Dedicated task: Large complex template

| Template | Lines | Notes |
|----------|-------|-------|
| `analyze_plans_results.html` | 2,726 | Largest template. Massive bespoke `<style>`. Treat as own sprint task. |

---

## Sprint 3: Admin Pages (9 templates)

**Goal:** Admin pages match the same obsidian aesthetic at 1200px container width.

### Already migrated (6) — in Group 1 above. No action.

### Needs migration (9 remaining)

| Template | Lines | Current Status | Complexity |
|----------|-------|----------------|------------|
| `admin_beta_requests.html` | 80 | Legacy (style.css) | Simple |
| `admin_pipeline.html` | 357 | Self-contained | Medium |
| `admin_qa.html` | 142 | Self-contained | Simple |
| `admin_qa_detail.html` | 171 | Self-contained | Simple |
| `admin_regulatory_watch.html` | 294 | Partial (mobile.css) | Medium |
| `admin_sources.html` | 371 | Partial (mobile.css) | Medium |
| `admin_voice_calibration.html` | 319 | Partial (mobile.css) | Medium |

Plus 2 HTMX fragments that need token audit:
| `analyze_plans_processing.html` | 149 | Partial | Medium |
| `analyze_plans_stale.html` | 16 | Self-contained (hardcoded) | Simple |

---

## Migration Checklist Per Template

For each template being migrated, the agent must:

1. [ ] Replace CSS source with `{% include "fragments/head_obsidian.html" %}`
2. [ ] Map all hardcoded hex colors to `var(--token)` references
3. [ ] Map all hardcoded font-family to `var(--mono)` or `var(--sans)`
4. [ ] Map all hardcoded font sizes to `var(--text-*)` scale
5. [ ] Remove duplicate Google Fonts `<link>` tags (already in head_obsidian)
6. [ ] Remove duplicate `mobile.css` / `style.css` links (subsumed by design-system)
7. [ ] Add `class="reveal"` to content sections
8. [ ] Ensure `body` has no old class overrides conflicting with obsidian
9. [ ] Add `prefers-reduced-motion` respect (handled by design-system.css)
10. [ ] Test at 375px (phone) and 768px (tablet)
11. [ ] Verify ghost CTAs, not filled buttons, for primary navigation
12. [ ] Run through Agent Implementation Checklist (DESIGN_TOKENS.md Section 14)

---

## Key Architectural Decisions

### HTMX fragments (results.html, search_results.html, etc.)
These have no `<!DOCTYPE>` — they're injected into `index.html`'s DOM via HTMX swap. They inherit design-system.css from their parent. Their `<style nonce>` blocks are **additive, not replacement** — this pattern is correct and should be preserved. Migration = audit tokens in the nonce styles, not restructure.

### landing.html anomaly
Loads `design-system.css` directly (not via `head_obsidian.html`). Also loads `style.css` and `mobile.css`. Should switch to `head_obsidian.html` include so PWA meta, font weights, and new tokens stay in sync.

### Sprint 69 content pages (about_data, demo, methodology)
Fully self-contained with zero shared CSS. Most disconnected from the system. Good candidates for parallel migration since they share no dependencies.

### analyze_plans_results.html (2,726 lines)
The largest template. Has a massive bespoke `<style>` block. Treat as its own sprint task — do not bundle with other migrations. Needs careful regression testing of the plan analysis viewer UI.

### design-system.css reconciliation
Before any template migration, `web/static/design-system.css` itself must be updated to match the tokens bible. Current file uses the old palette (`#0B0F19` navy, `#22D3EE` cyan). This is the **prerequisite** for all migration work.

---

## Prerequisite: Update design-system.css

Before Sprint 1, update `web/static/design-system.css` to match `docs/DESIGN_TOKENS.md`:

| Token | Current Value | Target Value |
|-------|--------------|--------------|
| `--bg-deep` | `#0B0F19` | `#0a0a0f` (rename to `--obsidian`) |
| `--bg-surface` | `#131825` | `#12121a` (rename to `--obsidian-mid`) |
| `--bg-elevated` | `#1A2035` | `#1a1a26` (rename to `--obsidian-light`) |
| `--signal-cyan` | `#22D3EE` | `#5eead4` (rename to `--accent`) |
| `--text-primary` | `#E8ECF4` | `rgba(255,255,255,0.92)` |
| `--text-secondary` | `#8B95A8` | `rgba(255,255,255,0.55)` |
| `--text-tertiary` | `#5A6478` | `rgba(255,255,255,0.30)` |
| (new) `--text-ghost` | — | `rgba(255,255,255,0.15)` |
| `--font-display` | JetBrains Mono (headings) | IBM Plex Sans (headings) |
| `--font-body` | IBM Plex Sans | IBM Plex Sans (unchanged) |

**Add legacy aliases** so already-migrated templates don't break:
```css
/* Legacy aliases — remove after full migration */
--bg-deep: var(--obsidian);
--bg-surface: var(--obsidian-mid);
--bg-elevated: var(--obsidian-light);
--signal-cyan: var(--accent);
```
