# Design Component Log — sfpermits.ai

> Running inventory of components discovered or created during sprints.
> Agents: append new entries when you create a component not in DESIGN_TOKENS.md.
> At Phase 2 governance checkpoints, good patterns get promoted to DESIGN_TOKENS.md; ad-hoc ones get deleted.

## Format

```
### [Component Name]
**Sprint:** [number]
**File:** [template or CSS file where it lives]
**Usage:** [where it's used, how many instances]
**Status:** NEW | PROMOTED (moved to DESIGN_TOKENS.md) | DEPRECATED (replaced by token component)
**HTML:**
[snippet]
**CSS:**
[snippet]
**Notes:** [any context on why it was created]
```

## Log

### Data Stale Warning
**Sprint:** QS9 (brief migration)
**File:** `web/templates/brief.html`
**Usage:** Brief page — shown when last data refresh was many hours ago
**Status:** NEW
**HTML:**
```html
<div class="data-stale-warning">
  ⚠ Data may be incomplete — last refresh was N hours ago.
</div>
```
**CSS:**
```css
.data-stale-warning {
  background: rgba(251, 191, 36, 0.08);
  border: 1px solid rgba(251, 191, 36, 0.25);
  border-radius: var(--radius-sm);
  padding: 10px var(--space-4);
  margin-bottom: var(--space-4);
  font-size: var(--text-sm);
  color: var(--signal-amber);
  font-family: var(--sans);
}
```
**Notes:** Amber tint on obsidian. Uses signal-amber for text. Amber rgba values (251,191,36) are derived from --signal-amber (#fbbf24) at reduced opacity — no raw hex, opacity-only variant acceptable.

---

### All Quiet Card
**Sprint:** QS9 (brief migration)
**File:** `web/templates/brief.html`
**Usage:** Brief page empty state when no activity in the selected lookback period
**Status:** NEW
**HTML:**
```html
<div class="all-quiet-card">
  <div class="all-quiet-icon">✅</div>
  <div class="all-quiet-title">All quiet on your watched items</div>
  <div class="all-quiet-body">No activity today. Try <a href="..." style="color:var(--accent);">last 7 days</a>.</div>
  <div style="margin-top: var(--space-4);">
    <a href="/" class="ghost-cta">Search for permits to watch →</a>
  </div>

---

### Risk Item
**Sprint:** QS8 report-token-migration
**File:** web/templates/report.html
**Usage:** Risk assessment and cross-reference sections (3+ instances per report)
**Status:** NEW
**HTML:**
```html
<div class="risk-item risk-item--high">
  <div class="risk-item__header">
    <span class="severity-chip severity-chip--high">High</span>
    <span class="risk-item__title">Open complaint</span>
  </div>
  <div class="risk-item__desc">Description of the risk.</div>
  <a href="#section-complaints" class="risk-item__xref">See §complaints</a>
</div>
```
**CSS:**
```css
.all-quiet-card {
  background: var(--accent-glow);
  border: 1px solid var(--accent-ring);
  border-radius: var(--radius-md);
  padding: var(--space-6);
  margin-bottom: var(--space-6);
  text-align: center;
}
.all-quiet-card .all-quiet-icon { font-size: var(--text-xl); margin-bottom: var(--space-2); }
.all-quiet-card .all-quiet-title { font-family: var(--sans); font-weight: 400; color: var(--text-primary); margin-bottom: var(--space-1); }
.all-quiet-card .all-quiet-body { color: var(--text-secondary); font-family: var(--sans); font-size: var(--text-sm); max-width: 480px; margin: 0 auto; }
```
**Notes:** Uses accent-glow/accent-ring for the subtle teal tint — consistent with the accent highlight pattern. Not for error/warning states, only for "nothing wrong, just quiet" states.

---

### Cache Freshness Row
**Sprint:** QS9 (brief migration)
**File:** `web/templates/brief.html`
**Usage:** Brief page header area — shows when cached data was last updated
**Status:** NEW
**HTML:**
```html
<div class="cache-freshness">
  <span class="status-dot status-dot--green" title="Cached"></span>
  <span class="cache-freshness__time">Updated 2026-02-27 08:30</span>
  <form method="post" action="..." style="display: inline;">
    <button type="submit" class="ghost-cta" style="font-size: var(--text-xs);">Refresh →</button>
  </form>

---

.risk-item { padding: var(--space-4); border-radius: var(--radius-sm); margin-bottom: var(--space-3); border-left: 2px solid; }
.risk-item--high     { background: rgba(248, 113, 113, 0.06); border-left-color: var(--signal-red); }
.risk-item--moderate { background: rgba(251, 191, 36, 0.06);  border-left-color: var(--signal-amber); }
.risk-item--low      { background: rgba(96, 165, 250, 0.06);  border-left-color: var(--signal-blue); }
.risk-item--none     { background: rgba(52, 211, 153, 0.06);  border-left-color: var(--signal-green); }
.risk-item__header { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); }
.risk-item__title { font-family: var(--sans); font-size: var(--text-base); font-weight: 400; color: var(--text-primary); }
.risk-item__desc { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); }
.risk-item__xref { font-family: var(--mono); font-size: var(--text-xs); color: var(--accent); text-decoration: none; display: inline-block; margin-top: var(--space-2); }
```
**Notes:** Extends the insight pattern with severity-specific left borders. Used for property-level risk items. Separate from `insight` (which is for callout boxes) — risk-item includes header with severity chip and optional KB citation links.

---

### Severity Chip
**Sprint:** QS8 report-token-migration
**File:** web/templates/report.html, web/templates/fragments/severity_badge.html
**Usage:** Inside risk-item__header; standalone severity badge fragment
**Status:** NEW
**HTML:**
```html
<span class="severity-chip severity-chip--high">High</span>
<span class="severity-chip severity-chip--critical">Critical</span>
<span class="severity-chip severity-chip--low">Low</span>
<span class="severity-chip severity-chip--clear">Clear</span>
```
**CSS:**
```css
.severity-chip { font-family: var(--mono); font-size: var(--text-xs); font-weight: 400; text-transform: uppercase; letter-spacing: 0.04em; padding: 1px 6px; border-radius: 3px; white-space: nowrap; }
.severity-chip--critical { color: var(--signal-red);   background: rgba(248, 113, 113, 0.12); }
.severity-chip--high     { color: var(--signal-amber);  background: rgba(251, 191, 36, 0.12); }
.severity-chip--moderate { color: var(--signal-amber);  background: rgba(251, 191, 36, 0.10); }
.severity-chip--medium   { color: var(--signal-amber);  background: rgba(251, 191, 36, 0.10); }
.severity-chip--low      { color: var(--signal-blue);   background: rgba(96, 165, 250, 0.10); }
.severity-chip--clear    { color: var(--signal-green);  background: rgba(52, 211, 153, 0.10); }
```
**Notes:** Replaces old pill-style severity badges that used `background-color: #f59e0b`. Uses signal colors semantically. The `--clear` variant used when no risks found.

---

### Status Chip
**Sprint:** QS8 report-token-migration
**File:** web/templates/report.html
**Usage:** Permit status, complaint status, violation status columns (many instances per report)
**Status:** NEW
**HTML:**
```html
<span class="status-chip status-chip--approved">Approved</span>
<span class="status-chip status-chip--expired">Expired</span>
<span class="status-chip status-chip--open">Open</span>
<span class="status-chip status-chip--default">Unknown</span>
```
**CSS:**
```css
.status-chip { font-family: var(--mono); font-size: var(--text-xs); font-weight: 400; text-transform: uppercase; letter-spacing: 0.04em; padding: 1px 6px; border-radius: 3px; white-space: nowrap; }
.status-chip--approved  { color: var(--signal-green);  background: rgba(52, 211, 153, 0.10); }
.status-chip--issued    { color: var(--signal-green);  background: rgba(52, 211, 153, 0.12); }
.status-chip--expired   { color: var(--signal-red);    background: rgba(248, 113, 113, 0.10); }
.status-chip--open      { color: var(--signal-amber);  background: rgba(251, 191, 36, 0.10); }
.status-chip--filed     { color: var(--signal-blue);   background: rgba(96, 165, 250, 0.10); }
.status-chip--default   { color: var(--text-secondary); background: var(--glass); border: 1px solid var(--glass-border); }
/* ... full variant list in report.html */
```
**Notes:** Replaces old `.status-badge .status-filed` etc. pattern that used `rgba(79, 143, 247, 0.15)` (non-token blue). Status Chip maps standard SF permit/complaint statuses to semantic token colors.

---

### CV Card (Complaint/Violation Card)
**Sprint:** QS8 report-token-migration
**File:** web/templates/report.html
**Usage:** Complaints section and violations section (1 per complaint/violation)
**Status:** NEW
**HTML:**
```html
<div class="cv-card">
  <div class="cv-header">
    <span class="cv-number"><a href="...">#{number}</a></span>
    <span class="status-chip status-chip--open">Open</span>
  </div>
  <div class="cv-meta">Filed Jan 15, 2024 · Market St</div>
  <div class="cv-desc">Description of the complaint or violation.</div>
</div>
```
**CSS:**
```css
.cache-freshness {
  display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-4);
}
.cache-freshness__time {
  font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary);
}
```
**Notes:** Uses status-dot (token component) + mono timestamp. Refresh button is ghost-cta at xs size. Entire row is conditional on brief.cached_at being set.

---

### Impact Badge
**Sprint:** QS9 (brief migration)
**File:** `web/templates/brief.html`
**Usage:** Regulatory watch section — shows impact level (high/moderate/low)
**Status:** NEW
**HTML:**
```html
<span class="impact-badge impact-high">high</span>
<span class="impact-badge impact-moderate">moderate</span>
<span class="impact-badge impact-low">low</span>
```
**CSS:**
```css
.impact-high { background: rgba(248,113,113,0.15); color: var(--signal-red); }
.impact-moderate { background: rgba(251,191,36,0.15); color: var(--signal-amber); }
.impact-low { background: var(--accent-glow); color: var(--accent); }
.impact-badge {
  font-family: var(--mono); font-size: var(--text-xs); padding: 1px 6px;
  border-radius: 3px; text-transform: uppercase; font-weight: 400;
}
```
**Notes:** Parallel to chip but with semantic color coding. rgba backgrounds derived from signal token hex values at 0.15 opacity. Should consider promoting to DESIGN_TOKENS.md alongside the status-badge pattern.

---

.cv-card { padding: var(--space-4); border-radius: var(--radius-sm); margin-bottom: var(--space-3); background: var(--glass); border: 1px solid var(--glass-border); }
.cv-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2); }
.cv-number { font-family: var(--mono); font-size: var(--text-sm); font-weight: 400; color: var(--text-primary); }
.cv-meta { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); }
.cv-desc { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); margin-top: var(--space-2); }
```
**Notes:** Replaces old `.cv-card` with `background: var(--surface-2)` (non-token). Now uses glass pattern for consistency with all other cards.
