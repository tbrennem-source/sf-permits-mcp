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

### Auth Card Container
**Sprint:** QS9 / T3-auth-agent
**File:** `web/templates/auth_login.html`, `web/templates/beta_request.html`
**Usage:** Centered auth layout. Wordmark above, glass-card below, footer links below card.
**Status:** NEW
**HTML:**
```html
<div class="auth-container">
  <a href="/" class="auth-wordmark">sfpermits.ai</a>
  <div class="glass-card">...</div>
  <div class="auth-footer">...</div>
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

.auth-container { width: 100%; max-width: 380px; opacity: 0; animation: fadeUp 1.2s 0.2s cubic-bezier(0.16, 1, 0.3, 1) forwards; }
.auth-wordmark { font-family: var(--mono); font-size: var(--text-xs); font-weight: 300; letter-spacing: 0.35em; text-transform: uppercase; color: var(--text-tertiary); text-align: center; display: block; margin-bottom: var(--space-10); transition: color 0.3s; }
.auth-wordmark:hover { color: var(--accent); }
@keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
```
**Notes:** Minimal auth archetype — no nav bar, no ambient glow (DESIGN_TOKENS.md §9). Max-width 380px for login, 420px for beta request.

### Auth Inline Message
**Sprint:** QS9 / T3-auth-agent
**File:** `web/templates/auth_login.html`, `web/templates/beta_request.html`
**Usage:** Server-rendered flash messages replacing old `.flash` divs. Uses insight-style left border.
**Status:** NEW
**HTML:**
```html
<div class="auth-message auth-message--success">Message text</div>
<div class="auth-message auth-message--error">Error text</div>
```
**CSS:**
```css
.auth-message { padding: var(--space-3) var(--space-4); border-radius: var(--radius-sm); margin-top: var(--space-4); font-family: var(--sans); font-size: var(--text-sm); line-height: 1.4; }
.auth-message--success { background: rgba(52, 211, 153, 0.06); border-left: 2px solid var(--signal-green); color: var(--signal-green); }
.auth-message--error { background: rgba(248, 113, 113, 0.06); border-left: 2px solid var(--signal-red); color: var(--signal-red); }
```
**Notes:** Replaces `.message.success/.error` pattern from old auth templates. Uses same rgba/signal-* values as insight component.

### Auth Sent State
**Sprint:** QS9 / T3-auth-agent
**File:** `web/templates/auth_login.html`
**Usage:** Post-submit magic link confirmation state inside the auth glass-card.
**Status:** NEW
**HTML:**
```html
<div class="auth-sent" id="auth-sent">
  <div class="auth-sent__icon"><!-- SVG check --></div>
  <div class="auth-sent__title">Check your email</div>
  <div class="auth-sent__email" id="sent-email-addr">you@example.com</div>
  <div class="auth-sent__text">...</div>
  <div class="auth-sent__resend"><a href="#" class="ghost-cta">Use a different email →</a></div>
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

.auth-sent { display: none; text-align: center; }
.auth-sent.visible { display: block; }
.auth-sent__icon { width: 40px; height: 40px; border-radius: var(--radius-full); background: rgba(52, 211, 153, 0.10); border: 1px solid rgba(52, 211, 153, 0.25); display: flex; align-items: center; justify-content: center; margin: 0 auto var(--space-4); }
.auth-sent__title { font-family: var(--sans); font-size: var(--text-lg); font-weight: 300; color: var(--text-primary); }
.auth-sent__email { font-family: var(--mono); font-size: var(--text-sm); color: var(--accent); }
.auth-sent__text { font-family: var(--sans); font-size: var(--text-sm); font-weight: 300; color: var(--text-secondary); line-height: 1.55; }
```
**Notes:** Mirrors the golden mockup (`web/static/mockups/auth-login.html`). Hidden by default, shown via JS class toggle.

---

## Sprint 75-1 Dashboard Rebuild — agent-a1dbe24e (2026-02-27)

### .brief-card
```css
.brief-card { /* glass-card base */ }
.brief-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.brief-greeting { font-family: var(--sans); font-size: var(--text-sm); font-weight: 300; color: var(--text-secondary); line-height: 1.55; }
.brief-stats { display: flex; gap: var(--space-4); flex-shrink: 0; }
.brief-stat { text-align: right; }
.brief-stat-num { font-family: var(--mono); font-size: var(--text-2xl); font-weight: 400; color: var(--text-primary); display: block; }
.brief-stat-label { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.06em; }
```
**Notes:** Conditional card shown only when `watch_count > 0`. Replaces old stats row with zero-state issue. Stats only shown when meaningful.

### .onboard-card
```css
.onboard-card { /* glass-card base */ text-align: center; padding: var(--space-8) var(--space-6); }
.onboard-headline { font-family: var(--sans); font-size: var(--text-2xl); font-weight: 300; color: var(--text-primary); margin-bottom: var(--space-3); }
.onboard-body { font-family: var(--sans); font-size: var(--text-sm); font-weight: 300; color: var(--text-secondary); line-height: 1.6; max-width: 440px; margin: 0 auto var(--space-6); }
```
**Notes:** Shown when `watch_count == 0` (new users). Prompts user to watch their first property. No zero stats displayed.

### .dash-search-card
```css
.dash-search-card { /* glass-card base */ }
.dash-search-heading { font-family: var(--sans); font-size: var(--text-xl); font-weight: 300; color: var(--text-primary); margin-bottom: var(--space-4); }
.search-form { display: flex; gap: var(--space-2); align-items: stretch; }
.search-btn { font-family: var(--mono); font-size: var(--text-sm); padding: var(--space-2) var(--space-4); background: var(--accent); color: var(--bg-primary); border: none; border-radius: var(--radius-sm); cursor: pointer; flex-shrink: 0; transition: opacity 0.15s; }
.search-btn:hover { opacity: 0.85; }
```
**Notes:** Primary dashboard card. Search IS the action — no quick-action rows.

### .recent-chip (primary address variant)
```css
.recent-chip { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); background: transparent; border: 1px solid var(--glass-border); border-radius: var(--radius-full); padding: var(--space-1) var(--space-3); cursor: pointer; transition: color 0.15s, border-color 0.15s; white-space: nowrap; }
.recent-chip:hover { color: var(--accent); border-color: var(--accent); }
```
**Notes:** Used for recent search items AND for primary-address quick-chip. Clickable chip that populates search input.

---

### qa-review-panel (Admin Visual QA Accept/Reject/Note Panel)
**Sprint:** QS10 T2-B
**File:** `web/templates/fragments/feedback_widget.html`
**Usage:** Admin-only panel inside the feedback modal. Shown when `g.user.is_admin` is true. Allows Tim to Accept/Reject/Note pending visual QA items from `qa-results/pending-reviews.json`. Verdict buttons POST to `/admin/qa-decision` via HTMX.
**Status:** NEW
**HTML:**
```html
<div id="qa-review-panel" style="margin-bottom:var(--space-4);padding-bottom:var(--space-4);border-bottom:1px solid var(--glass-border);">
  <!-- Header row: label + pending badge -->
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-family:var(--mono);font-size:var(--text-xs);color:var(--text-secondary);text-transform:uppercase;letter-spacing:0.06em;">QA Reviews</span>
    <span id="qa-pending-badge" style="font-family:var(--mono);font-size:var(--text-xs);color:var(--accent);background:var(--accent-glow);border:1px solid var(--accent-ring);border-radius:3px;padding:1px 6px;">N pending</span>
  </div>
  <!-- Hidden fields + context display + note textarea -->
  <!-- Three verdict buttons: Accept (signal-green), Note (accent), Reject (signal-red) -->
  <!-- Result span #qa-result for HTMX swap -->
</div>
```
**CSS:** No new CSS classes — uses only existing token classes (`action-btn`, `form-input`) and inline CSS custom properties.
**Notes:** Pending badge count is passed via `qa_pending_count` template context variable (injected by the rendering route). `window.qaLoadItem(item)` global JS function populates hidden fields from a pending review item object. All three verdict buttons use `hx-include="#qa-review-panel"` to submit the full panel's hidden fields.

---

### Risk Gauge (Revision Risk tool)
**Sprint:** QS11-T3-3C
**File:** `web/templates/tools/revision_risk.html`
**Usage:** Single instance — primary output of the Revision Risk tool showing revision probability.
**Status:** NEW
**HTML:**
```html
<div class="gauge-card">
  <p class="gauge-card-title">Revision Probability</p>
  <div class="gauge-row">
    <div class="gauge-number risk-low">12<span>%</span></div>
    <div class="gauge-bar-area">
      <div class="gauge-bar-track">
        <div class="gauge-bar-fill risk-low" style="width:12%"></div>
      </div>
      <div class="gauge-labels">
        <span class="gauge-label">0%</span>
        <span class="gauge-label">25%</span>
        <span class="gauge-label">50%+</span>
      </div>
    </div>
  </div>
  <p class="gauge-verdict"><strong class="risk-low">Low risk</strong> — ...</p>
</div>
```
**CSS:**
```css
.gauge-number.risk-low    { color: var(--signal-green); }
.gauge-number.risk-medium { color: var(--signal-amber); }
.gauge-number.risk-high   { color: var(--signal-red); }
.gauge-bar-fill.risk-low    { background: var(--signal-green); }
.gauge-bar-fill.risk-medium { background: var(--signal-amber); }
.gauge-bar-fill.risk-high   { background: var(--signal-red); }
```
**Notes:** Three-zone colour coding: green < 15%, amber 15–25%, red > 25%. Bar animates via requestAnimationFrame after DOM settles. Gauge classes applied by JS based on probability value.

---

### Entity Type Chip (Entity Network tool)
**Sprint:** QS11-T3-3C
**File:** `web/templates/tools/entity_network.html`
**Usage:** Entity detail sidebar — one chip per selected node showing professional role.
**Status:** NEW
**HTML:**
```html
<span class="entity-type-chip architect">architect</span>
<span class="entity-type-chip contractor">contractor</span>
<span class="entity-type-chip engineer">engineer</span>
<span class="entity-type-chip owner">owner</span>
```
**CSS:**
```css
.entity-type-chip { display: inline-block; font-family: var(--mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; padding: 2px 7px; border-radius: 3px; margin-bottom: var(--space-4); }
.entity-type-chip.contractor  { color: var(--signal-amber);  background: rgba(251,191,36,0.12); }
.entity-type-chip.architect   { color: var(--accent);         background: var(--accent-glow); }
.entity-type-chip.engineer    { color: var(--signal-blue);    background: rgba(96,165,250,0.10); }
.entity-type-chip.owner       { color: var(--signal-green);   background: rgba(52,211,153,0.10); }
```
**Notes:** Parallel pattern to severity-chip and status-chip. Uses class name matching the entity type string returned from the API. rgba backgrounds derived from signal-* token hex values at reduced opacity.

---

### Tier Gate Inline Card (HTMX Fragment)

**Sprint:** 89-4B
**File:** `web/templates/fragments/tier_gate_teaser_inline.html`
**Usage:** Injected into HTMX swap targets (e.g., the search results panel for /ask).
Displays a beta upgrade teaser card that fits inside an existing page element.

```html
<div class="tier-gate-inline-card">
  <span class="tier-gate-inline-badge">Beta Feature</span>
  <h2 class="tier-gate-inline-title">AI consultation is available for Beta users</h2>
  <p class="tier-gate-inline-desc">...</p>
  <a href="/beta/join" class="tier-gate-inline-cta">Join Beta &rarr;</a>
  <p class="tier-gate-inline-current">Current plan: <span>free</span></p>
</div>
```

**CSS:** All custom properties. Badge uses `--signal-blue`, `--mono`. Title uses `--sans`, `--text-xl`. CTA uses `--accent`, `--obsidian`. Card uses `--obsidian-mid`, `--glass-border`, `--radius-md`.
**Notes:** Companion to `tier_gate_teaser.html` (full-page). This version has no DOCTYPE/html tags so it can be safely injected via HTMX `hx-swap="innerHTML"`. Used by routes_search.py /ask endpoint to gate AI synthesis intents.
