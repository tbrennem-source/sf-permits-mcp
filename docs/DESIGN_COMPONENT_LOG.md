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
.auth-sent { display: none; text-align: center; }
.auth-sent.visible { display: block; }
.auth-sent__icon { width: 40px; height: 40px; border-radius: var(--radius-full); background: rgba(52, 211, 153, 0.10); border: 1px solid rgba(52, 211, 153, 0.25); display: flex; align-items: center; justify-content: center; margin: 0 auto var(--space-4); }
.auth-sent__title { font-family: var(--sans); font-size: var(--text-lg); font-weight: 300; color: var(--text-primary); }
.auth-sent__email { font-family: var(--mono); font-size: var(--text-sm); color: var(--accent); }
.auth-sent__text { font-family: var(--sans); font-size: var(--text-sm); font-weight: 300; color: var(--text-secondary); line-height: 1.55; }
```
**Notes:** Mirrors the golden mockup (`web/static/mockups/auth-login.html`). Hidden by default, shown via JS class toggle.
