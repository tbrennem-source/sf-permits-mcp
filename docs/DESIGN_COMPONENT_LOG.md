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
