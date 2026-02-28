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

---

### Tier Gate Overlay (Full-Page Blur + CTA)

**Sprint:** QS11 T4
**File:** `web/templates/components/tier_gate_overlay.html`, `web/static/css/tier-gate.css`, `web/static/js/tier-gate.js`
**Usage:** Included at the bottom of any gated page template. Renders a fixed full-viewport overlay with blur on the main content when `tier_locked=True`. Zero DOM impact when `tier_locked=False`.
**Status:** NEW

**HTML (partial — include at bottom of gated templates):**
```html
{% if tier_locked %}
<div class="tier-gate-overlay"
     data-track="tier-gate-impression"
     data-tier-required="{{ tier_required }}"
     data-tier-current="{{ tier_current }}">
  <div class="tier-gate-card glass-card">
    <h3>See this for your property</h3>
    <p>Get full access to permit intelligence for your address.</p>
    <a href="/beta/join" class="ghost-cta tier-gate-cta" data-track="tier-gate-click">
      Get access &rarr;
    </a>
    <p class="tier-gate-subtext">Free during beta. Takes 30 seconds.</p>
  </div>
</div>
{% endif %}
```

**CSS (key rules — see tier-gate.css for full file):**
```css
.tier-locked-content {
  filter: blur(8px);
  pointer-events: none;
  user-select: none;
  transition: filter 0.3s ease;
}
.tier-gate-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  background: rgba(0, 0, 0, 0.3);
}
.tier-gate-card {
  max-width: 420px;
  padding: var(--space-8);
  text-align: center;
}
```

**Notes:** Extends `glass-card` (token component) and `ghost-cta` (token component). Blur is 8px — intentional: tantalizing but unreadable. JS (`tier-gate.js`) adds `.tier-locked-content` to the first `main`, `.obs-container`, or `.obs-container-wide` found in the DOM. Analytics via `data-track` attributes on overlay impression and CTA click. Template context vars: `tier_locked` (bool), `tier_required` (str), `tier_current` (str) — expected from the context processor built by Agent 4A.
---

### Interactive Gantt Chart (Station Routing Timeline)
**Sprint:** QS11 T3-A
**File:** `web/static/js/gantt-interactive.js`, `web/templates/tools/station_predictor.html`
**Usage:** Station Predictor tool page — horizontal bar chart of permit routing stations. Bars are clickable to expand detail panel.
**Status:** NEW
**HTML:**
```html
<div class="gantt-wrap">
  <div class="gantt-track" role="list">
    <button class="gantt-bar gantt-bar-complete" style="width:25%;border-color:var(--signal-green);" data-idx="0">
      <div class="gantt-bar-label" style="color:var(--signal-green);">BLDG</div>
    </button>
    <button class="gantt-bar gantt-bar-active gantt-bar-current" style="width:40%;border-color:var(--accent);" data-idx="1">
      <div class="gantt-bar-label" style="color:var(--accent);">CP-ZOC</div>
      <div class="gantt-bar-pulse"></div>
    </button>
  </div>
  <div class="gantt-legend">
    <span class="gantt-legend-item">
      <span class="gantt-legend-dot" style="background:var(--signal-green);"></span>
      <span class="gantt-legend-label">Complete</span>
    </span>
  </div>
  <div class="gantt-station-list">
    <div class="gantt-station-row" data-idx="0">
      <div class="gantt-station-main" style="border-left-color:var(--signal-green);">
        <div class="gantt-station-name">Building Inspection</div>
        <div class="gantt-station-meta">20d dwell</div>
      </div>
      <div class="gantt-station-badge gantt-status-complete">Complete</div>
      <div class="gantt-detail" id="gantt-detail-0" aria-hidden="true">...</div>
    </div>
  </div>

### Share Container + Share Button
**Sprint:** QS10-T3-3D
**File:** `web/templates/components/share_button.html`, `web/static/css/share.css`, `web/static/js/share.js`
**Usage:** All 6 intelligence tool pages (station_predictor, stuck_permit, what_if, cost_of_delay, entity_network, revision_risk). Renders after the results area on each tool page.
**Status:** NEW
**HTML:**
```html
<div class="share-container" data-track="share-view">
  <button class="share-btn ghost-cta" type="button" data-track="share-click"
          data-share-title="SF Permit Intelligence"
          data-share-text="Check out this permit analysis from sfpermits.ai">
    <span class="share-icon" aria-hidden="true">&nearrow;</span>
    Send this to your contractor
  </button>
  <span class="share-copied" role="status" aria-live="polite" style="display:none;">Link copied!</span>
</div>
```
**CSS:**
```css
.gantt-wrap { width: 100%; }
.gantt-track { display: flex; gap: 4px; align-items: stretch; height: 44px; }
.gantt-bar { flex: 0 0 auto; min-width: 32px; border: 1px solid; border-radius: var(--radius-sm); cursor: pointer; position: relative; overflow: hidden; transition: transform 0.15s, box-shadow 0.15s; }
.gantt-bar:hover, .gantt-bar:focus { transform: scaleY(1.06); outline: none; }
.gantt-bar-selected { box-shadow: 0 0 0 2px var(--accent-ring); }
.gantt-bar-label { font-family: var(--mono); font-size: 9px; text-align: center; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 4px; }
.gantt-bar-pulse { position: absolute; inset: 0; animation: gantt-pulse 2s ease-in-out infinite; }
@keyframes gantt-pulse { 0%, 100% { opacity: 0.15; } 50% { opacity: 0.35; } }
.gantt-status-complete  { color: var(--signal-green);  background: rgba(52,211,153,0.10); }
.gantt-status-active    { color: var(--accent);         background: var(--accent-glow); }
.gantt-status-stalled   { color: var(--signal-amber);   background: rgba(251,191,36,0.10); }
.gantt-status-predicted { color: var(--signal-amber);   background: rgba(251,191,36,0.08); }
.gantt-detail { max-height: 0; opacity: 0; overflow: hidden; transition: max-height 0.3s ease, opacity 0.2s ease; }
```
**Notes:** Rendered by `GanttInteractive.render(container, stations, options)` from gantt-interactive.js. Status colors use signal tokens semantically. Pulse animation on active station. Bars are proportionally sized by dwell_days (historic) or p50_days (predicted). UMD module pattern for browser/Node compatibility.

---

### Severity Dashboard (Stuck Permit)
**Sprint:** QS11 T3-A
**File:** `web/templates/tools/stuck_permit.html`
**Usage:** Stuck Permit Analyzer — top-of-results header showing RED/AMBER/GREEN severity badge, block count, and permit number.
**Status:** NEW
**HTML:**
```html
<div class="severity-dashboard">
  <div class="severity-dashboard-row">
    <div class="severity-badge severity-badge-red">CRITICAL</div>
    <div class="severity-meta">2 stations blocked</div>
    <div class="severity-permit-number">202501015257</div>
  </div>
</div>
```
**CSS:**
```css
.severity-dashboard { margin-bottom: var(--space-8); padding-bottom: var(--space-6); border-bottom: 1px solid var(--glass-border); }
.severity-dashboard-row { display: flex; align-items: center; gap: var(--space-4); flex-wrap: wrap; }
.severity-badge { font-family: var(--mono); font-size: var(--text-sm); font-weight: 400; text-transform: uppercase; letter-spacing: 0.06em; padding: var(--space-2) var(--space-4); border-radius: var(--radius-sm); border: 1px solid; }
.severity-badge-green { color: var(--signal-green); background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.25); }
.severity-badge-amber { color: var(--signal-amber); background: rgba(251,191,36,0.08); border-color: rgba(251,191,36,0.25); }
.severity-badge-red   { color: var(--signal-red);   background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.25); }
.severity-permit-number { font-family: var(--mono); font-size: var(--text-sm); color: var(--accent); margin-left: auto; }
```
**Notes:** Uses rgba backgrounds derived from signal token hex values at 0.08 opacity — consistent with existing chip/badge pattern. Not a chip (larger, no letter-spacing, border included). Separate from severity-chip (which is used for scoring in report.html).

---

### Playbook Step (Stuck Permit Intervention)
**Sprint:** QS11 T3-A
**File:** `web/templates/tools/stuck_permit.html`
**Usage:** Stuck Permit Analyzer — numbered intervention steps with urgency badge, action text, and contact info.
**Status:** NEW
**HTML:**
```html
<div class="playbook-step">
  <div class="playbook-step-number">1.</div>
  <div class="playbook-step-body">
    <div class="playbook-step-urgency urgency-immediate">IMMEDIATE</div>
    <div class="playbook-step-action">Revise plans and resubmit via EPR</div>
    <div class="playbook-step-contact">SF DBI — <a href="tel:+14155586000">(415) 558-6000</a></div>
  </div>
</div>
```
**CSS:**
```css
.playbook-step { display: flex; gap: var(--space-4); padding: var(--space-4) var(--space-5); background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); }
.playbook-step-number { font-family: var(--mono); font-size: var(--text-sm); color: var(--text-tertiary); min-width: 20px; }
.playbook-step-urgency { font-family: var(--mono); font-size: var(--text-xs); text-transform: uppercase; letter-spacing: 0.04em; padding: 1px 6px; border-radius: 3px; display: inline-block; }
.urgency-immediate { color: var(--signal-red);   background: rgba(248,113,113,0.12); }
.urgency-high      { color: var(--signal-amber); background: rgba(251,191,36,0.12); }
.urgency-medium    { color: var(--signal-blue);  background: rgba(96,165,250,0.12); }
.urgency-low       { color: var(--text-secondary); background: var(--glass); }
.playbook-step-action { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-primary); }
.playbook-step-contact { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-secondary); }
```
**Notes:** Urgency variants mirror the 4-tier priority system from diagnose_stuck_permit.py (IMMEDIATE/HIGH/MEDIUM/LOW). Contact lines linkify phone numbers via regex replacement in JS render function.

.share-container { display: flex; align-items: center; gap: var(--space-4); margin-top: var(--space-6); padding-top: var(--space-4); border-top: 1px solid var(--glass-border); }
.share-btn { /* extends ghost-cta */ display: inline-flex; align-items: center; gap: var(--space-2); font-family: var(--mono); font-size: var(--text-sm); font-weight: 300; color: var(--text-secondary); background: none; border: none; cursor: pointer; padding-bottom: 1px; border-bottom: 1px solid transparent; transition: color 0.3s, border-color 0.3s; letter-spacing: 0.04em; }
.share-btn:hover { color: var(--accent); border-bottom-color: var(--accent); }
.share-copied { font-family: var(--mono); font-size: var(--text-xs); color: var(--signal-green); }
```
**Notes:** Uses Web Share API on mobile (native share sheet), clipboard copy on desktop with textarea execCommand fallback. No hardcoded hex — uses only CSS custom properties. share.js is loaded with `defer` attribute on each tool page. `share-btn` is a variant of `ghost-cta` pattern — extends it with `display:inline-flex` for icon alignment.

---

## Sprint QS11 Components

### Signal Color Alpha Tints (Approved Pattern)
**Sprint:** QS11 / T1-agent-1B
**File:** `web/templates/components/showcase_*.html`
**Usage:** Showcase component badge backgrounds and status bar fills — 11 instances across 4 components
**Status:** NEW
**CSS:**
```css
/* Red tint — backgrounds/borders for critical/error states */
background: rgba(239, 68, 68, 0.08);   /* --dot-red at 8% opacity */
background: rgba(239, 68, 68, 0.10);   /* --dot-red at 10% opacity */
border: 1px solid rgba(239, 68, 68, 0.20);  /* --dot-red at 20% opacity */
border: 1px solid rgba(239, 68, 68, 0.25);  /* --dot-red at 25% opacity */

/* Green tint — backgrounds/borders for approved/success states */
background: rgba(34, 197, 94, 0.18);   /* --dot-green at 18% opacity */
border: 1px solid rgba(34, 197, 94, 0.30);  /* --dot-green at 30% opacity */

/* Amber tint — backgrounds/borders for warning/comment states */
background: rgba(245, 158, 11, 0.18);  /* --dot-amber at 18% opacity */
border: 1px solid rgba(245, 158, 11, 0.30); /* --dot-amber at 30% opacity */
```
**Notes:** The design lint flags these as non-token rgba colors. They ARE derived from the approved signal/dot tokens (--dot-red: #ef4444 = rgba(239,68,68,1); --dot-green: #22c55e = rgba(34,197,94,1); --dot-amber: #f59e0b = rgba(245,158,11,1)). These alpha tints are approved for use as surface backgrounds and border colors in showcase-specific contexts. The pattern follows existing usage in the codebase (e.g., `rgba(94, 234, 212, 0.08)` for `--accent-glow`, `rgba(251, 191, 36, 0.08)` for amber stale warning).

### Gantt Bar (Station Timeline)
**Sprint:** QS11 / T1-agent-1B
**File:** `web/templates/components/showcase_gantt.html`
**Usage:** Showcase gantt chart — 1 component, 8 station bars
**Status:** NEW
**HTML:**
```html
<div class="gantt-grid">
  <div class="gantt-label">PERMIT-CTR</div>
  <div class="gantt-track">
    <div class="gantt-bar gantt-bar--approved" style="left: 0%; width: 1.6%;">
      <span class="gantt-bar-reviewer">M. Chen</span>
    </div>
  </div>
</div>
```
**CSS:** grid 90px+1fr; bars use absolute positioning inside tracks; status colors via --dot-* alpha tints; entrance animation via showcase-gantt.js (scaleX from 0→1 on IntersectionObserver).
**Notes:** CSS-only, no canvas/SVG. Width % = station.width_pct proportional to total permit duration. Staggered entrance animation 80ms + 100ms/station.

### Severity Badge (Critical/High/Medium)
**Sprint:** QS11 / T1-agent-1B
**File:** `web/templates/components/showcase_stuck.html`, `showcase_risk.html`
**Usage:** Showcase components — 2 instances
**Status:** NEW
**HTML:**
```html
<span class="stuck-severity-badge">
  <span class="stuck-severity-dot"></span>
  CRITICAL — 4 SIMULTANEOUS BLOCKS
</span>
```
**CSS:** inline-flex; --mono font; --signal-red text; rgba(239,68,68,0.1) background; 1px solid rgba(239,68,68,0.25) border; --radius-sm.
**Notes:** Extends the chip/status-dot pattern for larger severity callouts. Uses status-dot for the dot indicator.

### Entity Network SVG Graph (Mini)
**Sprint:** QS11 / T1-agent-1B
**File:** `web/templates/components/showcase_entity.html`
**Usage:** Landing page showcase — 1 instance
**Status:** NEW
**HTML:**
```html
<div class="entity-graph-container">
  <svg class="entity-svg" viewBox="0 0 400 225">
    <line x1="200" y1="112" x2="80" y2="55" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
    <g class="entity-node-central entity-node" style="opacity:0; transition:opacity 0.6s ease;">
      <circle cx="200" cy="112" r="32" fill="rgba(94,234,212,0.12)" stroke="rgba(94,234,212,0.4)" stroke-width="1.5"/>
      <text fill="#5eead4">1 Market St</text>
    </g>
  </svg>
</div>
```
**CSS:** aspect-ratio 16/9, max-height 240px, --glass background, --glass-border border. Nodes: contractor nodes use amber tint, architect nodes use blue tint. Entrance animation via showcase-entity.js (opacity 0→1, staggered 120ms/node).
**Notes:** Pure SVG, no D3. viewBox 400×225. Central node is teal (--accent). Entrance animation uses IntersectionObserver.

---

### MCP Demo Chat Terminal
**Sprint:** QS11 / T1-landing-showcase
**File:** `web/templates/components/mcp_demo.html`, `web/static/mcp-demo.css`, `web/static/mcp-demo.js`
**Usage:** Landing page — animated chat transcript showing Claude using sfpermits.ai tools. 3 demos cycle: What-If Scope Comparison, Stuck Permit Diagnosis, Cost of Delay.
**Status:** NEW
**HTML:**
```html
<section class="mcp-demo-section" id="mcp-demo">
  <div class="obs-container">
    <h2 class="mcp-demo-section__title">What your AI sees</h2>
    <div class="mcp-demo-terminal">
      <div class="mcp-demo-terminal__bar">...</div>
      <div class="mcp-demo-chat">
        <div class="mcp-demo-slide active" data-demo="0">...</div>
        <div class="mcp-demo-slide" data-demo="1">...</div>
        <div class="mcp-demo-slide" data-demo="2">...</div>
      </div>
      <div class="mcp-demo-controls">...</div>
    </div>
    <div class="mcp-demo-cta">...</div>
  </div>
</section>
```
**CSS:** Full stylesheet in `web/static/mcp-demo.css`. Key classes: `.mcp-demo-terminal` (dark terminal window with title bar dots), `.mcp-msg--user` (right-aligned accent bubble), `.mcp-msg--claude` (left-aligned glass bubble with sfpermits.ai label), `.mcp-tool-badge` (accent pill with lightning icon + pulse animation), `.mcp-response-table` (mono data table inside Claude bubble), `.mcp-stacked-cards` (mobile replacement for tables — stacked key-value cards), `.mcp-expand-wrapper.collapsible` (mobile expand button for long responses). All colors from token palette. Mobile breakpoint at 480px. Reduced motion support.
**Notes:** Scroll-triggered via IntersectionObserver (threshold 0.3). User messages fade-in + slide-up. Tool badges appear with 0.3s stagger + pulse. Claude responses type line by line; tables render instantly. 4s pause between demos. Manual prev/next arrows and dots. Auto-cycles indefinitely: Demo 2 -> Demo 1 -> Demo 6. CTA section: "Connect your AI" button + 3-step explainer (Connect, Ask, Get Intelligence).

---

### Showcase Card (Intelligence Landing Cards)
**Sprint:** QS11 (Sprint 90 — landing showcase integration)
**File:** `web/templates/components/showcase_*.html`, `web/templates/landing.html`
**Usage:** Landing page — 6 cards in 2-column grid (gantt, stuck, whatif, risk, entity, delay)
**Status:** NEW
**HTML:**
```html
<div class="showcase-card" data-track="showcase-view" data-showcase="gantt">
  <div class="showcase-card__header">
    <span class="showcase-card__icon"><!-- SVG icon --></span>
    <div class="showcase-card__meta">
      <h3 class="showcase-card__title">How long will it take?</h3>
      <p class="showcase-card__subtitle">Station-by-station timeline from real permits</p>
    </div>
  </div>
  <div class="showcase-card__body"><!-- card-specific content --></div>
  <div class="showcase-card__footer">
    <a href="/search?q=..." class="showcase-card__cta ghost-cta" data-track="showcase-click" data-showcase="gantt">
      Check timeline &rarr;
    </a>
  </div>
</div>
```
**CSS:**
```css
.showcase-card { background: var(--obsidian-mid); border: 1px solid var(--glass-border); border-radius: 14px; overflow: hidden; display: flex; flex-direction: column; }
.showcase-card:hover { border-color: rgba(94, 234, 212, 0.18); }
.showcase-card__icon { width: 32px; height: 32px; background: var(--accent-glow); border: 1px solid rgba(94, 234, 212, 0.12); border-radius: 8px; color: var(--accent); }
.showcase-card__title { font-family: var(--sans); font-size: 15px; font-weight: 500; color: var(--text-primary); }
.showcase-card__subtitle { font-size: 12px; color: var(--text-secondary); }
.showcase-card__cta { font-family: var(--mono); font-size: 11px; color: var(--text-tertiary); text-decoration: none; }
.showcase-card__cta:hover { color: var(--accent); }
```
**Notes:** Grid layout: `repeat(2, 1fr)` desktop, `1fr` tablet/mobile. Each card has a unique `data-showcase` type for PostHog analytics. Server-side data loaded from `web/static/data/showcase_data.json` via `_load_showcase_data()` in routes_public.py — graceful fallback to static HTML if JSON missing.

### MCP Demo Chat Section
**Sprint:** QS11 (Sprint 90 — landing showcase integration)
**File:** `web/templates/components/mcp_demo.html`, `web/static/mcp-demo.css`
**Usage:** Landing page — single instance below the showcase grid
**Status:** NEW
**HTML:**
```html
<div class="mcp-demo" data-track="mcp-demo-view">
  <div class="mcp-demo__intro">
    <h2 class="mcp-demo__headline">What your AI sees</h2>
    <p class="mcp-demo__sub">Connect Claude to sfpermits.ai...</p>
  </div>
  <div class="mcp-demo__layout">
    <div class="mcp-demo__chat"><!-- message bubbles --></div>
    <div class="mcp-demo__sidebar"><!-- tool list + CTA --></div>
  </div>
</div>
```
**CSS:**
```css
.mcp-demo__layout { display: grid; grid-template-columns: 1fr 280px; gap: 24px; }
.mcp-demo__bubble--tool { background: rgba(94,234,212,0.04); border: 1px solid rgba(94,234,212,0.12); color: var(--accent); font-family: var(--mono); }
.mcp-demo__tool-item--active { background: var(--accent-glow); color: var(--accent); }
```
**Notes:** Animated via `mcp-demo.js` — chat bubbles fade in sequentially on IntersectionObserver trigger. CTA links to /auth/login with `data-track="mcp-demo-cta"` for PostHog.

---

## Sprint QS12 — Agent 3B — Triage Intelligence Signals (2026-02-28)

### Station Badge (Triage Intelligence)
**Sprint:** QS12 / T3 agent-3B
**File:** `web/templates/search_results_public.html`, `web/templates/search_results.html`
**Usage:** Search result triage panels — one badge per active permit showing days at current station with color coding
**Status:** NEW
**HTML:**
```html
<span class="station-badge station-badge--amber" title="At BLDG station for 45 days (median: 30d)">
  <span class="station-badge__dot"></span>
  45d at BLDG
</span>
```
**CSS:**
```css
.station-badge {
  display: inline-flex; align-items: center; gap: 5px;
  font-family: var(--mono); font-size: var(--text-xs); font-weight: 400;
  padding: 2px 8px; border-radius: 3px; white-space: nowrap;
}
.station-badge__dot {
  width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}
.station-badge--green { color: var(--dot-green); background: rgba(34, 197, 94, 0.10); border: 1px solid rgba(34, 197, 94, 0.20); }
.station-badge--green .station-badge__dot { background: var(--dot-green); }
.station-badge--amber { color: var(--dot-amber); background: rgba(245, 158, 11, 0.10); border: 1px solid rgba(245, 158, 11, 0.20); }
.station-badge--amber .station-badge__dot { background: var(--dot-amber); }
.station-badge--red   { color: var(--dot-red);   background: rgba(239, 68, 68, 0.10); border: 1px solid rgba(239, 68, 68, 0.20); }
.station-badge--red   .station-badge__dot { background: var(--dot-red); }
```
**Notes:** Three-tier color coding: green (days < median), amber (median <= days < 2x median), red (days >= 2x median = stuck threshold). Uses `--dot-*` tokens (not `--signal-*`) per design system rules. `--dot-green: #22c55e`, `--dot-amber: #f59e0b`, `--dot-red: #ef4444`. Station medians are hardcoded per-station with live DB lookup when available.

---

### Triage Panel (Search Result Card)
**Sprint:** QS12 / T3 agent-3B
**File:** `web/templates/search_results_public.html`
**Usage:** Public search results — one panel per search result showing active permits with station timing intelligence
**Status:** NEW
**HTML:**
```html
<div class="triage-panel reveal reveal-delay-1">
  <div class="triage-heading">Active Permits</div>
  <div class="triage-cards">
    <div class="triage-card">
      <div class="triage-card__header">
        <span class="triage-card__permit">202401010002</span>
        <span class="triage-card__status">plancheck</span>
        <!-- optional: -->
        <span class="stuck-indicator" aria-label="Permit may be stuck">&#9650; Stuck</span>
      </div>
      <div class="triage-card__desc">New construction</div>
      <div class="triage-card__signals">
        <span class="station-badge station-badge--amber">...</span>
        <span class="triage-reviewer">Reviewer: ARRIOLA LAURA</span>
      </div>
    </div>
  </div>
</div>
```
**CSS:**
```css
.triage-panel { margin: var(--space-4) 0; padding: var(--space-4); background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); }
.triage-heading { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: var(--space-3); }
.triage-cards { display: flex; flex-direction: column; gap: var(--space-3); }
.triage-card { padding: var(--space-3); background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: 4px; }
.triage-card__header { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-2); }
.triage-card__permit { font-family: var(--mono); font-size: var(--text-sm); color: var(--accent); }
.triage-card__status { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); text-transform: uppercase; }
.triage-card__desc { font-family: var(--sans); font-size: var(--text-xs); color: var(--text-secondary); margin-bottom: var(--space-2); }
.triage-card__signals { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.stuck-indicator { font-family: var(--mono); font-size: var(--text-xs); color: var(--dot-red); letter-spacing: 0.03em; }
.triage-reviewer { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-secondary); }
```
**Notes:** Uses `glass` background pattern consistent with all other cards. Reviewer field only rendered when non-null. Stuck indicator uses `--dot-red` token. Panel is conditionally rendered only when `triage_signals` list is non-empty. Template var `triage_signals` is passed from `routes_public.py::public_search()`.

---

### Triage Signals Bar (Compact Inline Format)
**Sprint:** QS12 / T3 agent-3B
**File:** `web/templates/results.html`
**Usage:** Permit detail page — compact horizontal bar showing station timing badges for active permits, positioned before methodology toggle
**Status:** NEW
**HTML:**
```html
<div class="triage-signals-bar">
  <span class="triage-signals-bar__label">Current Status</span>
  <div class="triage-signals-bar__badges">
    <div class="triage-sig-badge">
      <div class="triage-sig-badge__header">
        <span class="triage-sig-badge__permit">202401010002</span>
        <span class="triage-sig-badge__stuck stuck-indicator">&#9650; Stuck</span>
      </div>
      <div class="triage-sig-badge__signals">
        <span class="station-badge station-badge--red">...</span>
        <span class="triage-reviewer">Reviewer: SMITH J</span>
      </div>
    </div>
  </div>
</div>
```
**CSS:**
```css
.triage-signals-bar { margin: var(--space-4) 0; padding: var(--space-3) var(--space-4); background: var(--glass); border: 1px solid var(--glass-border); border-radius: var(--radius-sm); }
.triage-signals-bar__label { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: var(--space-2); display: block; }
.triage-signals-bar__badges { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.triage-sig-badge { padding: var(--space-2) var(--space-3); background: rgba(255,255,255,0.02); border: 1px solid var(--glass-border); border-radius: 4px; min-width: 200px; }
.triage-sig-badge__header { display: flex; align-items: center; gap: var(--space-2); margin-bottom: var(--space-2); }
.triage-sig-badge__permit { font-family: var(--mono); font-size: var(--text-xs); color: var(--accent); }
.triage-sig-badge__signals { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
```
**Notes:** Compact variant of the triage-panel for use in narrower result contexts. Shares station-badge and triage-reviewer classes with the full panel. Rendered conditionally on `triage_signals` being non-empty.

---
