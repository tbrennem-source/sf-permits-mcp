/**
 * gantt-interactive.js — Station routing Gantt chart renderer
 *
 * Renders a horizontal Gantt chart from station prediction data.
 * Designed for the /tools/station-predictor page.
 *
 * Usage:
 *   GanttInteractive.render(container, stations, options)
 *
 * stations: Array of { label, station, status, dwell_days, arrive, probability,
 *                      p50_days, p25_days, p75_days, isCurrentStation }
 *
 * CSS variables consumed (must be present on :root):
 *   --accent, --accent-ring, --accent-glow
 *   --signal-green, --signal-amber, --signal-red
 *   --glass, --glass-border, --glass-hover
 *   --obsidian-mid, --obsidian-light
 *   --text-primary, --text-secondary, --text-tertiary
 *   --mono, --sans
 */
(function (root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    root.GanttInteractive = factory();
  }
}(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ── Color helpers ──────────────────────────────────────────────────────────

  /**
   * Return a CSS color for a station status.
   * status: 'complete' | 'active' | 'stalled' | 'predicted' | 'pending'
   */
  function statusColor(status) {
    var map = {
      complete:  'var(--signal-green)',
      active:    'var(--accent)',
      stalled:   'var(--signal-amber)',
      critical:  'var(--signal-red)',
      predicted: 'var(--signal-amber)',
      pending:   'rgba(255,255,255,0.12)',
    };
    return map[status] || map.pending;
  }

  function statusBg(status) {
    var map = {
      complete:  'rgba(52,211,153,0.08)',
      active:    'rgba(94,234,212,0.08)',
      stalled:   'rgba(251,191,36,0.08)',
      critical:  'rgba(248,113,113,0.08)',
      predicted: 'rgba(251,191,36,0.06)',
      pending:   'rgba(255,255,255,0.02)',
    };
    return map[status] || map.pending;
  }

  function statusLabel(status) {
    var map = {
      complete:  'Complete',
      active:    'In review',
      stalled:   'Stalled',
      critical:  'Critical',
      predicted: 'Predicted',
      pending:   'Pending',
    };
    return map[status] || 'Unknown';
  }

  // ── Bar width calculation ──────────────────────────────────────────────────

  /**
   * Compute relative bar widths.
   * For historic stations: use dwell_days or 1 as weight.
   * For predicted stations: use p50_days or 30 as weight.
   * Returns array of percentages (summing to 100).
   */
  function computeBarWidths(stations) {
    var weights = stations.map(function (s) {
      if (s.status === 'complete' || s.status === 'active' || s.status === 'stalled' || s.status === 'critical') {
        return Math.max(s.dwell_days || 1, 1);
      }
      return Math.max(s.p50_days || 30, 7);
    });

    var total = weights.reduce(function (a, b) { return a + b; }, 0) || 1;
    return weights.map(function (w) {
      return Math.max((w / total) * 100, 3); // minimum 3% for visibility
    });
  }

  // ── Detail panel builder ───────────────────────────────────────────────────

  function buildDetailPanel(s) {
    var lines = [];
    lines.push('<div class="gantt-detail-inner">');
    lines.push('<div class="gantt-detail-title">' + esc(s.label || s.station) + '</div>');

    if (s.station) {
      lines.push('<div class="gantt-detail-code">' + esc(s.station) + '</div>');
    }

    lines.push('<div class="gantt-detail-rows">');

    if (s.arrive) {
      lines.push(detailRow('Arrived', esc(s.arrive.slice(0, 10))));
    }
    if (s.status === 'complete' && s.finish_date) {
      lines.push(detailRow('Finished', esc(s.finish_date.slice(0, 10))));
    }
    if (s.dwell_days != null) {
      lines.push(detailRow('Dwell', s.dwell_days + ' days'));
    }
    if (s.probability != null) {
      lines.push(detailRow('Probability', Math.round(s.probability * 100) + '%'));
    }
    if (s.p50_days != null) {
      var range = '';
      if (s.p25_days != null && s.p75_days != null) {
        range = ' (' + Math.round(s.p25_days) + '–' + Math.round(s.p75_days) + 'd range)';
      }
      lines.push(detailRow('Typical wait', Math.round(s.p50_days) + 'd' + range));
    }
    if (s.review_results) {
      lines.push(detailRow('Review result', esc(s.review_results)));
    }
    if (s.addenda_number != null && s.addenda_number > 0) {
      lines.push(detailRow('Revision round', 'Round ' + s.addenda_number));
    }

    lines.push('</div>'); // gantt-detail-rows
    lines.push('<div class="gantt-detail-status-badge gantt-status-' + esc(s.status) + '">' + statusLabel(s.status) + '</div>');
    lines.push('</div>'); // gantt-detail-inner
    return lines.join('');
  }

  function detailRow(label, value) {
    return '<div class="gantt-detail-row">'
      + '<span class="gantt-detail-label">' + esc(label) + '</span>'
      + '<span class="gantt-detail-value">' + value + '</span>'
      + '</div>';
  }

  // ── Main render ────────────────────────────────────────────────────────────

  /**
   * Render a Gantt chart into the given container element.
   *
   * @param {HTMLElement} container - Target element to render into
   * @param {Array}       stations  - Station data objects (see file header)
   * @param {Object}      options   - Optional config
   * @param {string}      options.permitNumber  - Displayed permit number
   * @param {string}      options.currentStation - Station code for current stop
   */
  function render(container, stations, options) {
    if (!container || !stations || !stations.length) {
      container.innerHTML = '<p class="gantt-empty">No station data to display.</p>';
      return;
    }

    options = options || {};
    var widths = computeBarWidths(stations);
    var activeIdx = -1;
    stations.forEach(function (s, i) {
      if (s.isCurrentStation) activeIdx = i;
    });

    var html = [];
    html.push('<div class="gantt-wrap">');

    // ── Track: horizontal bar chart ──────────────────────────────────────────
    html.push('<div class="gantt-track" role="list" aria-label="Station routing timeline">');

    stations.forEach(function (s, i) {
      var width = widths[i].toFixed(1);
      var color = statusColor(s.status);
      var bg = statusBg(s.status);
      var isActive = s.isCurrentStation || false;
      var barClass = 'gantt-bar gantt-bar-' + s.status + (isActive ? ' gantt-bar-current' : '');

      html.push('<button class="' + barClass + '" '
        + 'style="width:' + width + '%;border-color:' + color + ';background:' + bg + ';" '
        + 'data-idx="' + i + '" '
        + 'aria-label="' + esc(s.label || s.station) + ' station" '
        + 'role="listitem" tabindex="0">');

      // Bar interior: label (only when wide enough)
      html.push('<div class="gantt-bar-label" style="color:' + color + ';">'
        + esc(s.station || '')
        + '</div>');

      if (isActive) {
        html.push('<div class="gantt-bar-pulse" style="background:' + color + ';opacity:0.25;"></div>');
      }

      html.push('</button>');
    });

    html.push('</div>'); // gantt-track

    // ── Legend ────────────────────────────────────────────────────────────────
    html.push('<div class="gantt-legend">');
    var legendItems = [
      { status: 'complete',  label: 'Complete' },
      { status: 'active',    label: 'In review' },
      { status: 'stalled',   label: 'Stalled' },
      { status: 'predicted', label: 'Predicted' },
    ];
    legendItems.forEach(function (li) {
      html.push('<span class="gantt-legend-item">'
        + '<span class="gantt-legend-dot" style="background:' + statusColor(li.status) + ';"></span>'
        + '<span class="gantt-legend-label">' + li.label + '</span>'
        + '</span>');
    });
    html.push('</div>'); // gantt-legend

    // ── Station list: click-to-expand detail ─────────────────────────────────
    html.push('<div class="gantt-station-list">');
    stations.forEach(function (s, i) {
      var color = statusColor(s.status);
      var isActive = s.isCurrentStation || false;
      html.push('<div class="gantt-station-row' + (isActive ? ' gantt-station-row-current' : '') + '" data-idx="' + i + '">');

      html.push('<div class="gantt-station-main" style="border-left-color:' + color + ';">');
      html.push('<div class="gantt-station-name">' + esc(s.label || s.station) + '</div>');

      var meta = [];
      if (s.dwell_days != null) meta.push(s.dwell_days + 'd dwell');
      if (s.probability != null) meta.push(Math.round(s.probability * 100) + '% likely');
      if (s.p50_days != null) meta.push('~' + Math.round(s.p50_days) + 'd typical');
      if (meta.length) {
        html.push('<div class="gantt-station-meta">' + meta.join(' · ') + '</div>');
      }
      html.push('</div>'); // gantt-station-main

      html.push('<div class="gantt-station-badge gantt-status-' + esc(s.status) + '">' + statusLabel(s.status) + '</div>');

      // Expandable detail panel
      html.push('<div class="gantt-detail" id="gantt-detail-' + i + '" aria-hidden="true">');
      html.push(buildDetailPanel(s));
      html.push('</div>');

      html.push('</div>'); // gantt-station-row
    });
    html.push('</div>'); // gantt-station-list

    html.push('</div>'); // gantt-wrap

    container.innerHTML = html.join('');
    attachEvents(container, stations);
  }

  // ── Event handlers ─────────────────────────────────────────────────────────

  function attachEvents(container, stations) {
    var openIdx = -1;

    // Bar clicks
    var bars = container.querySelectorAll('.gantt-bar');
    bars.forEach(function (bar) {
      bar.addEventListener('click', function () {
        var idx = parseInt(bar.getAttribute('data-idx'), 10);
        toggleDetail(container, idx, openIdx, stations);
        openIdx = openIdx === idx ? -1 : idx;
      });
      bar.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          var idx = parseInt(bar.getAttribute('data-idx'), 10);
          toggleDetail(container, idx, openIdx, stations);
          openIdx = openIdx === idx ? -1 : idx;
        }
      });
    });

    // Station row clicks
    var rows = container.querySelectorAll('.gantt-station-row');
    rows.forEach(function (row) {
      row.addEventListener('click', function () {
        var idx = parseInt(row.getAttribute('data-idx'), 10);
        toggleDetail(container, idx, openIdx, stations);
        openIdx = openIdx === idx ? -1 : idx;
      });
    });
  }

  function toggleDetail(container, idx, openIdx, stations) {
    // Close previously open panel
    if (openIdx >= 0 && openIdx !== idx) {
      var prev = container.querySelector('#gantt-detail-' + openIdx);
      if (prev) {
        prev.setAttribute('aria-hidden', 'true');
        prev.style.maxHeight = '0';
        prev.style.opacity = '0';
      }
      var prevRow = container.querySelector('[data-idx="' + openIdx + '"].gantt-station-row');
      if (prevRow) prevRow.classList.remove('gantt-station-row-open');
      var prevBar = container.querySelector('.gantt-bar[data-idx="' + openIdx + '"]');
      if (prevBar) prevBar.classList.remove('gantt-bar-selected');
    }

    var panel = container.querySelector('#gantt-detail-' + idx);
    var row = container.querySelector('[data-idx="' + idx + '"].gantt-station-row');
    var bar = container.querySelector('.gantt-bar[data-idx="' + idx + '"]');
    if (!panel) return;

    var isOpen = panel.getAttribute('aria-hidden') === 'false';
    if (isOpen) {
      panel.setAttribute('aria-hidden', 'true');
      panel.style.maxHeight = '0';
      panel.style.opacity = '0';
      if (row) row.classList.remove('gantt-station-row-open');
      if (bar) bar.classList.remove('gantt-bar-selected');
    } else {
      panel.setAttribute('aria-hidden', 'false');
      panel.style.maxHeight = '400px';
      panel.style.opacity = '1';
      if (row) row.classList.add('gantt-station-row-open');
      if (bar) bar.classList.add('gantt-bar-selected');
    }
  }

  // ── Utility ────────────────────────────────────────────────────────────────

  function esc(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Public API ─────────────────────────────────────────────────────────────

  return {
    render: render,
    statusColor: statusColor,
    statusLabel: statusLabel,
    _computeBarWidths: computeBarWidths,  // exported for unit testing
  };
}));
