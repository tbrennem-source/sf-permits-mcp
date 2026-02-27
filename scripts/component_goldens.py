#!/usr/bin/env python3
"""Component golden test script — 26 token components, capture + diff modes.

Renders each design-system component in isolation using Playwright headless
Chromium, stores PNG golden baselines, and compares on subsequent runs.

Usage:
    python scripts/component_goldens.py --capture               # Generate all golden baselines
    python scripts/component_goldens.py --diff                   # Compare current against goldens
    python scripts/component_goldens.py --capture --component glass-card  # Single component

Output:
    qa-results/component-goldens/<name>.png    golden baselines
    qa-results/component-goldens/diff-<name>.png  diff images (--diff mode)
    qa-results/component-goldens-results.md    diff report
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# CSS path resolution
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
MOCKUP_CSS = REPO_ROOT / "web" / "static" / "mockups" / "obsidian-tokens.css"
OUTPUT_DIR = REPO_ROOT / "qa-results" / "component-goldens"

# ---------------------------------------------------------------------------
# Component registry
# Each entry has:
#   html      — the component HTML snippet (matches DESIGN_TOKENS.md exactly)
#   width     — viewport/container width for the screenshot
#   height    — viewport height (auto-cropped to content)
#   extra_css — optional per-component CSS overrides (positioning, etc.)
# ---------------------------------------------------------------------------

COMPONENTS: dict[str, dict] = {
    "glass-card": {
        "html": """
<div class="glass-card" style="max-width: 400px;">
  <h3 style="font-family: var(--sans); font-size: var(--text-lg); color: var(--text-primary); margin-bottom: 12px;">Card Title</h3>
  <p style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Card content goes here. This is the primary container across all pages.</p>
</div>
""",
        "width": 460,
        "height": 200,
    },

    "search-input": {
        "html": """
<div class="search-bar" style="max-width: 500px; position: relative;">
  <input type="text" class="search-input" placeholder="Search any SF address" autocomplete="off">
  <span class="kbd-hint" style="position: absolute; right: 36px; top: 50%; transform: translateY(-50%); font-family: var(--mono); font-size: 11px; color: var(--text-tertiary); background: var(--glass); border: 1px solid var(--glass-border); border-radius: 3px; padding: 1px 5px;">/</span>
  <svg class="search-icon" style="position: absolute; right: 14px; top: 50%; transform: translateY(-50%);" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
</div>
""",
        "width": 560,
        "height": 100,
    },

    "ghost-cta": {
        "html": """
<div style="display: flex; gap: 24px; align-items: center; padding: 8px 0;">
  <a href="#" class="ghost-cta">Full property intelligence →</a>
  <a href="#" class="ghost-cta">View timeline →</a>
</div>
""",
        "width": 460,
        "height": 80,
    },

    "action-btn": {
        "html": """
<div style="display: flex; gap: 12px; align-items: center; padding: 8px 0; flex-wrap: wrap;">
  <button class="action-btn">Upload plans</button>
  <button class="action-btn">Save changes</button>
  <button class="action-btn action-btn--danger">Delete</button>
</div>
""",
        "width": 420,
        "height": 80,
    },

    "status-dot-green": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 12px; padding: 8px 0;">
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--green" title="On track"></span>
    <span class="status-text--green" style="font-family: var(--mono); font-size: var(--text-sm);">3 in review</span>
  </div>
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--green"></span>
    <span class="status-text--green" style="font-family: var(--mono); font-size: var(--text-sm);">On track</span>
  </div>
</div>
""",
        "width": 300,
        "height": 100,
    },

    "status-dot-amber": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 12px; padding: 8px 0;">
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--amber" title="Stalled 12 days"></span>
    <span class="status-text--amber" style="font-family: var(--mono); font-size: var(--text-sm);">PPC pending</span>
  </div>
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--amber"></span>
    <span class="status-text--amber" style="font-family: var(--mono); font-size: var(--text-sm);">4–7 months</span>
  </div>
</div>
""",
        "width": 300,
        "height": 100,
    },

    "status-dot-red": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 12px; padding: 8px 0;">
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--red" title="2 active complaints"></span>
    <span class="status-text--red" style="font-family: var(--mono); font-size: var(--text-sm);">2 complaints</span>
  </div>
  <div style="display: flex; align-items: center; gap: 8px;">
    <span class="status-dot status-dot--red"></span>
    <span class="status-text--red" style="font-family: var(--mono); font-size: var(--text-sm);">Overdue</span>
  </div>
</div>
""",
        "width": 300,
        "height": 100,
    },

    "chip": {
        "html": """
<div style="display: flex; gap: 8px; flex-wrap: wrap; padding: 8px 0; align-items: center;">
  <span class="chip">Commercial</span>
  <span class="chip">Kitchen remodel</span>
  <span class="chip">Structural</span>
  <span class="chip">ADU</span>
</div>
""",
        "width": 460,
        "height": 80,
    },

    "data-row": {
        "html": """
<div style="max-width: 440px;">
  <div class="data-row">
    <span class="data-row__label">Active permits</span>
    <span class="data-row__value status-text--green">3 in review</span>
  </div>
  <div class="data-row">
    <span class="data-row__label">Est. remaining</span>
    <span class="data-row__value status-text--amber">4–7 months</span>
  </div>
  <div class="data-row">
    <span class="data-row__label">Complaints</span>
    <span class="data-row__value status-text--red">2 active</span>
  </div>
  <div class="data-row" style="border-bottom: none;">
    <span class="data-row__label">Parcel area</span>
    <span class="data-row__value">2,800 sq ft</span>
  </div>
</div>
""",
        "width": 500,
        "height": 230,
    },

    "stat-counter": {
        "html": """
<div style="display: flex; gap: 40px; align-items: flex-start; padding: 8px 0;">
  <div class="stat-item">
    <div class="stat-number">1,137,816</div>
    <div class="stat-label">Permits tracked</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">576K</div>
    <div class="stat-label">Relationships mapped</div>
  </div>
  <div class="stat-item">
    <div class="stat-number">47</div>
    <div class="stat-label">Data sources</div>
  </div>
</div>
""",
        "width": 560,
        "height": 120,
    },

    "progress-bar": {
        "html": """
<div style="max-width: 440px; display: flex; flex-direction: column; gap: 20px;">
  <div>
    <div class="progress-label" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
      <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Plan review</span>
      <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-tertiary);">5 / 8 stations</span>
    </div>
    <div class="progress-track">
      <div class="progress-fill" style="width: 62%;"></div>
    </div>
  </div>
  <div>
    <div class="progress-label" style="display: flex; justify-content: space-between; margin-bottom: 8px;">
      <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Inspection routing</span>
      <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-tertiary);">2 / 6 stations</span>
    </div>
    <div class="progress-track">
      <div class="progress-fill" style="width: 33%;"></div>
    </div>
  </div>
</div>
""",
        "width": 500,
        "height": 140,
    },

    "dropdown": {
        "html": """
<div class="dropdown" style="max-width: 320px; width: 320px;">
  <div class="dropdown__label">Recent searches</div>
  <div class="dropdown__item">
    <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-primary);">487 Noe St</span>
  </div>
  <div class="dropdown__item">
    <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-primary);">2550 Van Ness Ave</span>
  </div>
  <div class="dropdown__label">Suggestions</div>
  <div class="dropdown__item">
    <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-secondary);">Search by permit number</span>
  </div>
  <div class="dropdown__item">
    <span style="font-family: var(--mono); font-size: var(--text-sm); color: var(--text-secondary);">Browse by neighborhood</span>
  </div>
</div>
""",
        "width": 380,
        "height": 220,
    },

    "section-divider": {
        "html": """
<div style="max-width: 440px; display: flex; flex-direction: column; gap: 16px; padding: 8px 0;">
  <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Content above divider</span>
  <hr class="section-divider">
  <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Content below divider</span>
  <hr class="section-divider">
  <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Another section</span>
</div>
""",
        "width": 500,
        "height": 140,
    },

    "skeleton-heading": {
        "html": """
<div class="glass-card" style="max-width: 400px;">
  <div class="skeleton skeleton--heading" style="width: 60%;"></div>
  <div class="skeleton skeleton--text" style="width: 100%; margin-top: 12px;"></div>
  <div class="skeleton skeleton--text" style="width: 85%; margin-top: 8px;"></div>
  <div class="skeleton skeleton--text" style="width: 70%; margin-top: 8px;"></div>
</div>
""",
        "width": 460,
        "height": 160,
    },

    "skeleton-text": {
        "html": """
<div style="max-width: 400px; display: flex; flex-direction: column; gap: 8px;">
  <div class="skeleton-row">
    <div class="skeleton skeleton--text" style="width: 120px;"></div>
    <div class="skeleton skeleton--text" style="width: 80px;"></div>
  </div>
  <div class="skeleton-row">
    <div class="skeleton skeleton--text" style="width: 140px;"></div>
    <div class="skeleton skeleton--text" style="width: 60px;"></div>
  </div>
  <div class="skeleton-row" style="border-bottom: none;">
    <div class="skeleton skeleton--text" style="width: 100px;"></div>
    <div class="skeleton skeleton--text" style="width: 90px;"></div>
  </div>
</div>
""",
        "width": 460,
        "height": 160,
    },

    "skeleton-dot": {
        "html": """
<div style="display: flex; gap: 16px; align-items: center; padding: 12px 0;">
  <div class="skeleton skeleton--dot"></div>
  <div class="skeleton skeleton--text" style="width: 160px;"></div>
  <div style="margin-left: auto;">
    <div class="skeleton skeleton--text" style="width: 60px;"></div>
  </div>
</div>
""",
        "width": 400,
        "height": 80,
    },

    "obs-table": {
        "html": """
<div class="obs-table-wrap" style="max-width: 560px;">
  <table class="obs-table">
    <thead>
      <tr>
        <th></th>
        <th>Address</th>
        <th>Type</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="status-dot status-dot--green"></span></td>
        <td class="obs-table__mono">487 Noe St</td>
        <td>Kitchen remodel</td>
        <td class="obs-table__mono status-text--green">On track</td>
      </tr>
      <tr>
        <td><span class="status-dot status-dot--amber"></span></td>
        <td class="obs-table__mono">2550 Van Ness Ave</td>
        <td>New construction</td>
        <td class="obs-table__mono status-text--amber">Stalled</td>
      </tr>
      <tr>
        <td><span class="status-dot status-dot--red"></span></td>
        <td class="obs-table__mono">1899 Mission St</td>
        <td>Demolition</td>
        <td class="obs-table__mono status-text--red">2 complaints</td>
      </tr>
    </tbody>
  </table>
</div>
""",
        "width": 620,
        "height": 200,
    },

    "form-input": {
        "html": """
<div style="max-width: 360px; display: flex; flex-direction: column; gap: 16px;">
  <div>
    <label class="form-label" for="project-cost">Estimated cost</label>
    <input class="form-input" id="project-cost" type="text" placeholder="e.g. $85,000">
  </div>
  <div>
    <label class="form-label" for="permit-num">Permit number</label>
    <input class="form-input" id="permit-num" type="text" placeholder="202401015555">
  </div>
</div>
""",
        "width": 420,
        "height": 180,
    },

    "form-check": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 4px; padding: 8px 0;">
  <label class="form-check">
    <input type="checkbox" class="form-check__input" checked>
    <span class="form-check__box"></span>
    <span class="form-check__label">Include structural engineer letter</span>
  </label>
  <label class="form-check">
    <input type="checkbox" class="form-check__input">
    <span class="form-check__box"></span>
    <span class="form-check__label">Email notifications</span>
  </label>
  <label class="form-check">
    <input type="checkbox" class="form-check__input" checked>
    <span class="form-check__box"></span>
    <span class="form-check__label">Subscribe to weekly brief</span>
  </label>
</div>
""",
        "width": 400,
        "height": 150,
    },

    "form-toggle": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 4px; padding: 8px 0;">
  <label class="form-toggle">
    <input type="checkbox" class="form-toggle__input" checked>
    <span class="form-toggle__track"><span class="form-toggle__thumb"></span></span>
    <span class="form-toggle__label">Email notifications</span>
  </label>
  <label class="form-toggle">
    <input type="checkbox" class="form-toggle__input">
    <span class="form-toggle__track"><span class="form-toggle__thumb"></span></span>
    <span class="form-toggle__label">SMS alerts</span>
  </label>
  <label class="form-toggle">
    <input type="checkbox" class="form-toggle__input" checked>
    <span class="form-toggle__track"><span class="form-toggle__thumb"></span></span>
    <span class="form-toggle__label">Morning brief</span>
  </label>
</div>
""",
        "width": 380,
        "height": 150,
    },

    "form-select": {
        "html": """
<div style="max-width: 320px; display: flex; flex-direction: column; gap: 16px;">
  <div>
    <label class="form-label" for="permit-type">Permit type</label>
    <select class="form-select" id="permit-type">
      <option value="">Select...</option>
      <option>Alterations</option>
      <option>New construction</option>
      <option>Demolition</option>
    </select>
  </div>
  <div>
    <label class="form-label" for="neighborhood">Neighborhood</label>
    <select class="form-select" id="neighborhood">
      <option value="">All neighborhoods</option>
      <option>Mission</option>
      <option>Castro</option>
      <option>SoMa</option>
    </select>
  </div>
</div>
""",
        "width": 380,
        "height": 180,
    },

    "form-upload": {
        "html": """
<div style="max-width: 400px;">
  <label class="form-upload">
    <input type="file" class="form-upload__input">
    <span class="form-upload__zone">
      <span class="form-upload__icon">↑</span>
      <span class="form-upload__text">Drop plans here or click to browse</span>
      <span class="form-upload__hint">PDF up to 250MB · EPR format recommended</span>
    </span>
  </label>
</div>
""",
        "width": 460,
        "height": 160,
    },

    "toast-success": {
        "html": """
<div style="position: relative; height: 80px;">
  <div class="toast toast--success" style="position: static; transform: none; left: auto; top: auto; margin: 0;">
    <span class="toast__icon">✓</span>
    <span class="toast__message">Watch added</span>
    <a href="#" class="toast__action">Undo</a>
    <button class="toast__dismiss" aria-label="Dismiss">×</button>
  </div>
</div>
""",
        "width": 480,
        "height": 80,
    },

    "toast-error": {
        "html": """
<div style="position: relative; height: 80px;">
  <div class="toast toast--error" style="position: static; transform: none; left: auto; top: auto; margin: 0;">
    <span class="toast__icon">!</span>
    <span class="toast__message">Failed to save changes. Please try again.</span>
    <button class="toast__dismiss" aria-label="Dismiss">×</button>
  </div>
</div>
""",
        "width": 480,
        "height": 80,
    },

    "toast-info": {
        "html": """
<div style="position: relative; height: 80px;">
  <div class="toast toast--info" style="position: static; transform: none; left: auto; top: auto; margin: 0;">
    <span class="toast__icon">i</span>
    <span class="toast__message">Data refreshed nightly from SODA API</span>
    <button class="toast__dismiss" aria-label="Dismiss">×</button>
  </div>
</div>
""",
        "width": 480,
        "height": 80,
    },

    "modal": {
        "html": """
<div style="position: relative; width: 460px; height: 280px; display: flex; align-items: center; justify-content: center;">
  <div class="modal" style="position: static; transform: none; animation: none; width: 440px; max-width: 440px;">
    <div class="modal__header">
      <h3 class="modal__title" id="modal-title">Delete this watch?</h3>
      <button class="modal__close" aria-label="Close">×</button>
    </div>
    <div class="modal__body">
      <p>This will remove 487 Noe St from your watched properties. You can re-add it later.</p>
    </div>
    <div class="modal__footer">
      <button class="action-btn">Cancel</button>
      <button class="action-btn action-btn--danger">Delete</button>
    </div>
  </div>
</div>
""",
        "width": 520,
        "height": 300,
    },

    "insight-green": {
        "html": """
<div style="max-width: 480px;">
  <div class="insight insight--green">
    <div class="insight__label">On track</div>
    <div class="insight__body">This permit is progressing faster than 78% of similar projects in the Mission. Estimated completion in 3–5 months.</div>
  </div>
</div>
""",
        "width": 540,
        "height": 120,
    },

    "insight-amber": {
        "html": """
<div style="max-width: 480px;">
  <div class="insight insight--amber">
    <div class="insight__label">Things to know</div>
    <div class="insight__body">This permit has been in plan review for 47 days longer than the neighborhood median. Consider contacting the assigned plan checker.</div>
  </div>
</div>
""",
        "width": 540,
        "height": 120,
    },

    "insight-red": {
        "html": """
<div style="max-width: 480px;">
  <div class="insight insight--red">
    <div class="insight__label">Action required</div>
    <div class="insight__body">2 active complaints filed at this parcel. Unresolved complaints can delay permit issuance and trigger additional inspections.</div>
  </div>
</div>
""",
        "width": 540,
        "height": 120,
    },

    "insight-info": {
        "html": """
<div style="max-width: 480px;">
  <div class="insight insight--info">
    <div class="insight__label">Did you know</div>
    <div class="insight__body">Projects with ADU components in the Mission typically take 20% longer at the planning stage due to neighborhood notification requirements.</div>
  </div>
</div>
""",
        "width": 540,
        "height": 120,
    },

    "expandable": {
        "html": """
<div style="max-width: 460px;">
  <details class="expandable" open>
    <summary class="expandable__summary">
      <span class="expandable__title">Why in-house review?</span>
      <span class="expandable__arrow">▾</span>
    </summary>
    <div class="expandable__body">
      <p>Estimated cost exceeds $50,000 and the project includes structural modifications, triggering mandatory DBI in-house review per Administrative Bulletin 003.</p>
    </div>
  </details>
  <details class="expandable">
    <summary class="expandable__summary">
      <span class="expandable__title">What documents are required?</span>
      <span class="expandable__arrow">▾</span>
    </summary>
    <div class="expandable__body">
      <p>Structural calculations, energy compliance report, and soils report are required for this project type.</p>
    </div>
  </details>
</div>
""",
        "width": 520,
        "height": 220,
    },

    "risk-flag": {
        "html": """
<div style="display: flex; flex-direction: column; gap: 4px; padding: 8px 0;">
  <div class="risk-flag risk-flag--high">
    <span class="risk-flag__dot"></span>
    <span class="risk-flag__text">2 active complaints at this parcel</span>
  </div>
  <div class="risk-flag risk-flag--medium">
    <span class="risk-flag__dot"></span>
    <span class="risk-flag__text">Plan review stalled 47 days above median</span>
  </div>
  <div class="risk-flag risk-flag--low">
    <span class="risk-flag__dot"></span>
    <span class="risk-flag__text">Minor discrepancy in parcel area records</span>
  </div>
</div>
""",
        "width": 460,
        "height": 140,
    },

    "action-prompt": {
        "html": """
<div style="max-width: 460px;">
  <div class="action-prompt">
    <span class="action-prompt__context">Based on 3,412 similar permits in your neighborhood</span>
    <a href="#" class="ghost-cta">Full property intelligence →</a>
  </div>
</div>
""",
        "width": 520,
        "height": 100,
    },

    "tabs": {
        "html": """
<div style="max-width: 500px;">
  <nav class="tabs" role="tablist">
    <button class="tab tab--active" role="tab" aria-selected="true">Active <span class="tab__count">12</span></button>
    <button class="tab" role="tab" aria-selected="false">Completed <span class="tab__count">34</span></button>
    <button class="tab" role="tab" aria-selected="false">Expired <span class="tab__count">7</span></button>
  </nav>
  <div class="tab-panel" role="tabpanel" style="padding-top: 16px;">
    <span style="font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary);">Active permits tab content</span>
  </div>
</div>
""",
        "width": 560,
        "height": 140,
    },

    "load-more": {
        "html": """
<div style="max-width: 440px;">
  <div class="load-more">
    <span class="load-more__count">Showing 20 of 142</span>
    <button class="ghost-cta load-more__btn">Show more →</button>
  </div>
</div>
""",
        "width": 500,
        "height": 120,
    },
}

# ---------------------------------------------------------------------------
# HTML page builder
# ---------------------------------------------------------------------------

def build_html_page(component_html: str, css_path: Path) -> str:
    """Wrap a component snippet in a minimal standalone HTML page."""
    css_content = css_path.read_text(encoding="utf-8") if css_path.exists() else ""

    # Inline component CSS from DESIGN_TOKENS.md (supplement obsidian-tokens.css)
    component_css = """
/* Component-specific CSS from DESIGN_TOKENS.md */
.glass-card {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  padding: var(--space-8);
  transition: border-color 0.3s;
}
.glass-card:hover { border-color: var(--glass-hover); }

.search-input {
  width: 100%;
  padding: 16px 22px;
  padding-right: 50px;
  font-family: var(--mono);
  font-size: 14px;
  font-weight: 300;
  color: var(--text-primary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color 0.4s, background 0.4s, box-shadow 0.4s;
}
.search-input::placeholder { color: var(--text-tertiary); font-weight: 300; }
.search-input:focus {
  border-color: var(--accent-ring);
  background: rgba(255, 255, 255, 0.06);
  box-shadow: 0 0 40px var(--accent-glow);
}

.ghost-cta {
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 300;
  color: var(--text-secondary);
  background: none;
  border: none;
  cursor: pointer;
  padding-bottom: 1px;
  border-bottom: 1px solid transparent;
  transition: color 0.3s, border-color 0.3s;
  letter-spacing: 0.04em;
  text-decoration: none;
  display: inline-block;
}
.ghost-cta:hover { color: var(--accent); border-bottom-color: var(--accent); }

.action-btn {
  font-family: var(--mono);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-secondary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-sm);
  padding: 8px 16px;
  cursor: pointer;
  transition: border-color 0.3s, color 0.3s, background 0.3s;
}
.action-btn:hover {
  border-color: var(--glass-hover);
  color: var(--text-primary);
  background: var(--obsidian-light);
}
.action-btn--danger:hover {
  border-color: rgba(248, 113, 113, 0.3);
  color: var(--signal-red);
}

.status-dot {
  width: 6px; height: 6px;
  border-radius: var(--radius-full);
  display: inline-block;
}
.status-dot--green { background: var(--dot-green); }
.status-dot--amber { background: var(--dot-amber); }
.status-dot--red   { background: var(--dot-red); }
.status-text--green { color: var(--signal-green); }
.status-text--amber { color: var(--signal-amber); }
.status-text--red   { color: var(--signal-red); }

.chip {
  font-family: var(--mono);
  font-size: var(--text-xs);
  font-weight: 400;
  color: var(--text-tertiary);
  background: var(--glass);
  border: 1px solid var(--glass-border);
  padding: 1px 7px;
  border-radius: 3px;
  white-space: nowrap;
}

.data-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 0; border-bottom: 1px solid var(--glass-border);
}
.data-row__label { font-family: var(--sans); font-size: var(--text-base); color: var(--text-secondary); }
.data-row__value { font-family: var(--mono); font-size: var(--text-sm); color: var(--text-primary); }

.stat-number {
  font-family: var(--mono);
  font-size: clamp(22px, 3vw, 36px);
  font-weight: 300;
  line-height: 1;
  color: var(--text-primary);
}
.stat-label {
  font-family: var(--sans);
  font-size: var(--text-sm);
  font-weight: 400;
  color: var(--text-tertiary);
  margin-top: var(--space-2);
}

.progress-track {
  height: 2px;
  background: var(--glass);
  border-radius: 1px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--accent), rgba(94, 234, 212, 0.4));
  border-radius: 1px;
  transition: width 1.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.dropdown {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
  overflow-y: auto; max-height: 380px;
  scrollbar-width: thin; scrollbar-color: var(--glass-border) transparent;
}
.dropdown__item {
  padding: 9px 22px; cursor: pointer;
  display: flex; align-items: center; gap: 10px;
  transition: background 0.12s;
}
.dropdown__item:hover { background: var(--glass); }
.dropdown__label {
  font-family: var(--mono); font-size: var(--text-xs); font-weight: 400;
  letter-spacing: 0.15em; text-transform: uppercase; color: var(--text-tertiary);
  padding: 10px 22px 4px;
}

.section-divider {
  border: none; border-top: 1px solid var(--glass-border); margin: 0;
}

.skeleton {
  background: var(--glass);
  border-radius: var(--radius-sm);
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
.skeleton--heading { height: 20px; }
.skeleton--text { height: 12px; }
.skeleton--dot { width: 6px; height: 6px; border-radius: var(--radius-full); }
.skeleton-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 14px 0; border-bottom: 1px solid var(--glass-border);
}
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.04; }
  50% { opacity: 0.08; }
}

.obs-table {
  width: 100%; border-collapse: collapse;
  font-family: var(--sans); font-size: var(--text-sm);
}
.obs-table th {
  font-family: var(--mono); font-size: 10px; font-weight: 400;
  letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-secondary); text-align: left;
  padding: 6px var(--space-3); border-bottom: 1px solid var(--glass-border);
}
.obs-table td {
  padding: 9px var(--space-3); color: var(--text-secondary);
  border-bottom: 1px solid var(--glass-border);
}
.obs-table tr { transition: background 0.12s; cursor: pointer; }
.obs-table tr:hover { background: var(--glass); }
.obs-table__mono { font-family: var(--mono); font-weight: 300; color: var(--text-primary); }
.obs-table tr:hover .obs-table__mono:first-of-type { color: var(--accent); }
.obs-table__empty {
  text-align: center; padding: var(--space-8) var(--space-4);
  color: var(--text-tertiary); font-family: var(--sans); font-size: var(--text-sm);
}

.form-label {
  display: block; font-family: var(--mono); font-size: var(--text-xs); font-weight: 400;
  letter-spacing: 0.06em; text-transform: uppercase; color: var(--text-tertiary);
  margin-bottom: var(--space-2);
}
.form-input {
  width: 100%; padding: 10px 14px;
  font-family: var(--mono); font-size: var(--text-sm); font-weight: 300;
  color: var(--text-primary); background: var(--glass);
  border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
  outline: none; transition: border-color 0.3s, box-shadow 0.3s;
  box-sizing: border-box;
}
.form-input:focus {
  border-color: var(--accent-ring);
  box-shadow: 0 0 0 3px rgba(94, 234, 212, 0.1);
}

.form-check {
  display: flex; align-items: center; gap: var(--space-3);
  cursor: pointer; padding: 6px 0;
}
.form-check__input { display: none; }
.form-check__box {
  width: 16px; height: 16px; border-radius: 3px; flex-shrink: 0;
  border: 1px solid var(--glass-border); background: var(--glass);
  transition: border-color 0.2s, background 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.form-check__input:checked + .form-check__box {
  border-color: var(--accent); background: var(--accent-glow);
}
.form-check__input:checked + .form-check__box::after {
  content: '✓'; font-size: 10px; color: var(--accent);
}
.form-check__label { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); }

.form-toggle {
  display: flex; align-items: center; gap: var(--space-3);
  cursor: pointer; padding: 6px 0;
}
.form-toggle__input { display: none; }
.form-toggle__track {
  width: 28px; height: 14px; border-radius: 7px; flex-shrink: 0;
  background: var(--glass-border); position: relative; transition: background 0.2s;
}
.form-toggle__input:checked + .form-toggle__track { background: var(--accent); }
.form-toggle__thumb {
  width: 10px; height: 10px; border-radius: var(--radius-full);
  background: var(--text-tertiary);
  position: absolute; top: 2px; left: 2px;
  transition: left 0.2s, background 0.2s;
}
.form-toggle__input:checked + .form-toggle__track .form-toggle__thumb {
  left: 16px; background: var(--obsidian);
}
.form-toggle__label { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); }

.form-select {
  width: 100%; padding: 10px 14px;
  font-family: var(--mono); font-size: var(--text-sm); font-weight: 300;
  color: var(--text-primary); background: var(--glass);
  border: 1px solid var(--glass-border); border-radius: var(--radius-sm);
  outline: none; appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.3)' stroke-width='2' xmlns='http://www.w3.org/2000/svg'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat; background-position: right 14px center;
  cursor: pointer; transition: border-color 0.3s; box-sizing: border-box;
}
.form-select:focus { border-color: var(--accent-ring); }

.form-upload__input { display: none; }
.form-upload__zone {
  display: flex; flex-direction: column; align-items: center;
  gap: var(--space-2); padding: var(--space-8) var(--space-6);
  border: 1px dashed var(--glass-border); border-radius: var(--radius-md);
  cursor: pointer; text-align: center;
  transition: border-color 0.3s, background 0.3s;
}
.form-upload__zone:hover {
  border-color: var(--accent-ring); background: var(--accent-glow);
}
.form-upload__icon { font-size: 20px; color: var(--text-tertiary); }
.form-upload__text { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); }
.form-upload__hint { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); }

.toast {
  display: flex; align-items: center; gap: var(--space-3);
  padding: 10px var(--space-5);
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  backdrop-filter: blur(12px);
  max-width: min(420px, calc(100vw - 32px));
}
.toast--success { border-left: 2px solid var(--signal-green); }
.toast--error   { border-left: 2px solid var(--signal-red); }
.toast--info    { border-left: 2px solid var(--signal-blue); }
.toast__icon { font-size: var(--text-sm); }
.toast--success .toast__icon { color: var(--signal-green); }
.toast--error .toast__icon   { color: var(--signal-red); }
.toast--info .toast__icon    { color: var(--signal-blue); }
.toast__message { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-primary); }
.toast__action {
  font-family: var(--mono); font-size: var(--text-xs); color: var(--accent);
  text-decoration: none; margin-left: var(--space-2); white-space: nowrap;
}
.toast__action:hover { text-decoration: underline; }
.toast__dismiss {
  background: none; border: none; color: var(--text-tertiary);
  font-size: 16px; cursor: pointer; padding: 0 0 0 var(--space-2);
  transition: color 0.2s; margin-left: auto;
}
.toast__dismiss:hover { color: var(--text-primary); }

.modal {
  background: var(--obsidian-mid);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  max-width: 440px; width: calc(100vw - 32px);
  overflow-y: auto;
}
.modal__header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-6) var(--space-6) 0;
}
.modal__title {
  font-family: var(--sans); font-size: var(--text-lg); font-weight: 400;
  color: var(--text-primary); margin: 0;
}
.modal__close {
  background: none; border: none; color: var(--text-tertiary);
  font-size: 20px; cursor: pointer; padding: 0; transition: color 0.2s;
}
.modal__close:hover { color: var(--text-primary); }
.modal__body {
  padding: var(--space-4) var(--space-6);
  font-family: var(--sans); font-size: var(--text-sm);
  color: var(--text-secondary); line-height: 1.5;
}
.modal__footer {
  display: flex; justify-content: flex-end; gap: var(--space-3);
  padding: 0 var(--space-6) var(--space-6);
}

.insight {
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-sm);
  margin-bottom: var(--space-4);
  border-left: 2px solid;
}
.insight--green { background: rgba(52, 211, 153, 0.06); border-left-color: var(--signal-green); }
.insight--amber { background: rgba(251, 191, 36, 0.06); border-left-color: var(--signal-amber); }
.insight--red   { background: rgba(248, 113, 113, 0.06); border-left-color: var(--signal-red); }
.insight--info  { background: rgba(96, 165, 250, 0.06); border-left-color: var(--signal-blue); }
.insight__label {
  font-family: var(--mono); font-size: var(--text-xs); font-weight: 400;
  text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px;
}
.insight--green .insight__label { color: var(--signal-green); }
.insight--amber .insight__label { color: var(--signal-amber); }
.insight--red .insight__label   { color: var(--signal-red); }
.insight--info .insight__label  { color: var(--signal-blue); }
.insight__body {
  font-family: var(--sans); font-size: var(--text-sm); font-weight: 300;
  color: var(--text-secondary); line-height: 1.5;
}

.expandable { border-bottom: 1px solid var(--glass-border); }
.expandable__summary {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-3) 0; cursor: pointer; list-style: none;
}
.expandable__summary::-webkit-details-marker { display: none; }
.expandable__title {
  font-family: var(--mono); font-size: var(--text-sm); font-weight: 400;
  color: var(--text-secondary); transition: color 0.2s;
}
.expandable__summary:hover .expandable__title { color: var(--accent); }
.expandable__arrow { font-size: 10px; color: var(--text-tertiary); transition: transform 0.3s; }
.expandable[open] .expandable__arrow { transform: rotate(180deg); }
.expandable__body {
  padding: 0 0 var(--space-4);
  font-family: var(--sans); font-size: var(--text-sm); font-weight: 300;
  color: var(--text-secondary); line-height: 1.5;
}

.risk-flag { display: flex; align-items: center; gap: var(--space-2); padding: 4px 0; }
.risk-flag__dot { width: 6px; height: 6px; border-radius: var(--radius-full); flex-shrink: 0; }
.risk-flag--high .risk-flag__dot   { background: var(--dot-red); }
.risk-flag--medium .risk-flag__dot { background: var(--dot-amber); }
.risk-flag--low .risk-flag__dot    { background: var(--dot-green); }
.risk-flag__text { font-family: var(--sans); font-size: var(--text-sm); color: var(--text-secondary); }

.action-prompt { display: flex; flex-direction: column; gap: var(--space-2); padding: var(--space-4) 0; }
.action-prompt__context { font-family: var(--sans); font-size: var(--text-xs); color: var(--text-tertiary); }

.tabs { display: flex; gap: var(--space-6); border-bottom: 1px solid var(--glass-border); margin-bottom: var(--space-6); }
.tab {
  font-family: var(--mono); font-size: var(--text-sm); font-weight: 400;
  color: var(--text-tertiary); background: none; border: none;
  padding: var(--space-3) 0; cursor: pointer; position: relative; transition: color 0.2s;
}
.tab:hover { color: var(--text-secondary); }
.tab--active { color: var(--text-primary); }
.tab--active::after {
  content: ''; position: absolute; bottom: -1px; left: 0; right: 0;
  height: 2px; background: var(--accent); border-radius: 1px;
}
.tab__count { font-size: var(--text-xs); color: var(--text-tertiary); margin-left: var(--space-2); }
.tab--active .tab__count { color: var(--accent); }

.load-more {
  display: flex; flex-direction: column; align-items: center;
  gap: var(--space-3); padding: var(--space-6) 0;
}
.load-more__count { font-family: var(--mono); font-size: var(--text-xs); color: var(--text-tertiary); }

/* Dot colors (high saturation for small sizes) */
:root {
  --dot-green: #22c55e;
  --dot-amber: #f59e0b;
  --dot-red:   #ef4444;
}
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Component Golden</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500&family=IBM+Plex+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
  <style>
{css_content}
{component_css}
    /* Page chrome: dark background, tight padding */
    body {{
      background: #0a0a0f;
      margin: 0;
      padding: 20px;
      min-height: 100vh;
      display: flex;
      align-items: flex-start;
      justify-content: flex-start;
    }}
  </style>
</head>
<body>
  {component_html}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Pixel comparison
# ---------------------------------------------------------------------------

def compare_images(
    current_path: Path,
    golden_path: Path,
    diff_path: Path,
    *,
    threshold_pct: float = 2.0,
    pixel_tolerance: int = 30,
) -> tuple[str, float, Optional[str]]:
    """Compare two PNG files pixel-by-pixel.

    Returns (status, diff_pct, diff_path_or_none).
    status is one of: 'UNCHANGED', 'CHANGED', 'NEW'.
    """
    try:
        from PIL import Image
    except ImportError:
        print("  [warn] Pillow not installed — skipping pixel diff. pip install Pillow")
        return "UNKNOWN", 0.0, None

    if not golden_path.exists():
        return "NEW", 0.0, None

    current_img = Image.open(current_path).convert("RGB")
    golden_img = Image.open(golden_path).convert("RGB")

    # Resize golden to match current if sizes differ
    if current_img.size != golden_img.size:
        golden_img = golden_img.resize(current_img.size, Image.LANCZOS)

    w, h = current_img.size
    total_pixels = w * h
    if total_pixels == 0:
        return "UNCHANGED", 0.0, None

    current_data = current_img.load()
    golden_data = golden_img.load()

    diff_count = 0
    diff_img = Image.new("RGB", (w, h), (0, 0, 0))
    diff_data = diff_img.load()

    for y in range(h):
        for x in range(w):
            cr, cg, cb = current_data[x, y]
            gr, gg, gb = golden_data[x, y]
            if (
                abs(cr - gr) > pixel_tolerance
                or abs(cg - gg) > pixel_tolerance
                or abs(cb - gb) > pixel_tolerance
            ):
                diff_count += 1
                diff_data[x, y] = (255, 0, 80)  # hot pink for changed pixels
            else:
                diff_data[x, y] = (cr // 3, cg // 3, cb // 3)  # dimmed original

    diff_pct = (diff_count / total_pixels) * 100

    if diff_pct > threshold_pct:
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_img.save(str(diff_path))
        return "CHANGED", diff_pct, str(diff_path)

    return "UNCHANGED", diff_pct, None


# ---------------------------------------------------------------------------
# Playwright screenshot runner
# ---------------------------------------------------------------------------

def screenshot_component(
    name: str,
    spec: dict,
    output_path: Path,
    css_path: Path,
) -> None:
    """Render a single component and save a screenshot."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  [error] playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    html_content = build_html_page(spec["html"], css_path)
    width = spec.get("width", 1280)
    height = spec.get("height", 400)

    # Write temp HTML file (data URLs with fonts don't load in Playwright)
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(html_content)
        tmp_path = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": width + 40, "height": height + 40},
            )
            page = context.new_page()
            page.goto(f"file://{tmp_path}", wait_until="networkidle", timeout=15000)
            # Wait for fonts (Google Fonts may be blocked — that's fine, fallbacks work)
            page.wait_for_timeout(300)

            # Screenshot just the component wrapper (body padding = 20px each side)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(output_path),
                clip={"x": 0, "y": 0, "width": width + 40, "height": height + 40},
            )
            browser.close()
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def write_report(
    results: list[dict],
    output_path: Path,
) -> None:
    """Write a markdown diff report."""
    lines = [
        "# Component Goldens — Diff Report",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
    ]

    unchanged = [r for r in results if r["status"] == "UNCHANGED"]
    changed = [r for r in results if r["status"] == "CHANGED"]
    new = [r for r in results if r["status"] == "NEW"]
    unknown = [r for r in results if r["status"] == "UNKNOWN"]

    lines.append(f"**Summary:** {len(unchanged)} UNCHANGED / {len(changed)} CHANGED / {len(new)} NEW")
    if unknown:
        lines.append(f"**Skipped (no Pillow):** {len(unknown)}")
    lines.append("")
    lines.append("| Component | Status | Diff % | Diff Image |")
    lines.append("|-----------|--------|--------|------------|")

    for r in results:
        status = r["status"]
        diff_pct = f"{r.get('diff_pct', 0.0):.2f}%"
        diff_img = r.get("diff_path") or "—"
        lines.append(f"| {r['name']} | {status} | {diff_pct} | {diff_img} |")

    lines.append("")
    if changed:
        lines.append("## CHANGED Components")
        lines.append("")
        for r in changed:
            lines.append(f"### {r['name']} ({r.get('diff_pct', 0):.2f}% pixels differ)")
            if r.get("diff_path"):
                lines.append(f"Diff image: `{r['diff_path']}`")
            lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"\nReport written to: {output_path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Component golden test script — capture baselines and diff renders."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--capture", action="store_true", help="Generate golden baselines")
    mode.add_argument("--diff", action="store_true", help="Compare current renders against stored goldens")
    parser.add_argument(
        "--component", metavar="NAME",
        help="Only process this component (e.g. glass-card). Omit for all 26.",
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Directory for golden PNGs (default: {OUTPUT_DIR})",
    )
    parser.add_argument(
        "--threshold", type=float, default=2.0,
        help="Pixel diff threshold %% to flag CHANGED (default: 2.0)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve CSS path
    css_path = MOCKUP_CSS
    if not css_path.exists():
        print(f"[warn] obsidian-tokens.css not found at {css_path} — using inline CSS only")
        css_path = Path("/dev/null")  # empty file fallback

    # Filter components
    if args.component:
        if args.component not in COMPONENTS:
            print(f"[error] Unknown component: {args.component!r}")
            print(f"Available: {', '.join(sorted(COMPONENTS.keys()))}")
            sys.exit(1)
        components = {args.component: COMPONENTS[args.component]}
    else:
        components = COMPONENTS

    print(f"Mode: {'CAPTURE' if args.capture else 'DIFF'}")
    print(f"Components: {len(components)}")
    print(f"Output dir: {output_dir}")
    print()

    results = []

    for name, spec in components.items():
        golden_path = output_dir / f"{name}.png"

        if args.capture:
            print(f"  Capturing: {name} ...", end=" ", flush=True)
            screenshot_component(name, spec, golden_path, css_path)
            print(f"-> {golden_path.name}")

        elif args.diff:
            # Render to a temp file, compare against golden
            import tempfile
            tmp_png = Path(tempfile.mktemp(suffix=".png"))
            try:
                print(f"  Diffing:   {name} ...", end=" ", flush=True)
                screenshot_component(name, spec, tmp_png, css_path)

                diff_png = output_dir / f"diff-{name}.png"
                status, diff_pct, diff_path = compare_images(
                    tmp_png, golden_path, diff_png, threshold_pct=args.threshold
                )
                print(f"{status} ({diff_pct:.2f}%)")
                results.append({
                    "name": name,
                    "status": status,
                    "diff_pct": diff_pct,
                    "diff_path": diff_path,
                })
            finally:
                if tmp_png.exists():
                    tmp_png.unlink()

    if args.diff:
        report_path = output_dir.parent / "component-goldens-results.md"
        write_report(results, report_path)

        changed = [r for r in results if r["status"] == "CHANGED"]
        new_baselines = [r for r in results if r["status"] == "NEW"]

        print()
        print(f"UNCHANGED: {sum(1 for r in results if r['status'] == 'UNCHANGED')}")
        print(f"CHANGED:   {len(changed)}")
        print(f"NEW:       {len(new_baselines)}")

        if changed:
            print("\nChanged components:")
            for r in changed:
                print(f"  - {r['name']}: {r['diff_pct']:.2f}% pixels differ")
            sys.exit(1)  # Non-zero exit if regressions found

    print("\nDone.")


if __name__ == "__main__":
    main()
