/* Admin QA Tour — guided walkthrough of recent fixes
   Activates with ?admin=1&tour=1 in the URL.
   Loads tour stops from /api/qa-tour or inline data.
   Each stop: element selector, feedback quote, fix description.
*/
(function() {
  var params = new URLSearchParams(window.location.search);
  if (!params.has('admin') || !params.has('tour')) return;

  // Tour stops — each one highlights an element and shows the feedback
  var stops = [];

  // Try to load from server, fall back to inline
  fetch('/api/qa-tour?page=' + encodeURIComponent(window.location.pathname))
    .then(function(r) { return r.ok ? r.json() : null; })
    .then(function(data) {
      if (data && data.stops && data.stops.length) {
        stops = data.stops;
      } else {
        stops = getInlineStops();
      }
      if (stops.length) initTour();
    })
    .catch(function() {
      stops = getInlineStops();
      if (stops.length) initTour();
    });

  function getInlineStops() {
    // Hardcoded stops for landing page — generated from QA feedback
    if (window.location.pathname !== '/') return [];
    return [
      {
        selector: '.scroll-cue',
        feedback: '"down button needs to be brighter" / "down arrow needs to be more visible"',
        fix: 'Changed to accent teal color. Now clickable — scrolls to first capability section.',
        action: 'Look at the bottom of the hero — the arrow and text should be teal.'
      },
      {
        selector: '.below-search__watched',
        feedback: '"return+watch clicks on properties come back to this page" / "beta+watch properties just come back to this page"',
        fix: 'Property links now navigate to /search?q={address}. "view all" and "N watching" go to /portfolio.',
        action: 'Switch to "Returning + Watching" or "Beta + Watching" persona and click a property name.'
      },
      {
        selector: '.below-search__context',
        feedback: '"we basically have two Do I need a permit for links — redundant"',
        fix: 'Renamed context row link from "do I need a permit for..." to "common permit questions" to differentiate from the sub row anchor link.',
        action: 'Compare the sub row (scrolls to section) vs context row (hover dropdown).'
      },
      {
        selector: '.state-toggle',
        feedback: '"BETA should be BETA Tester — more personal and descriptive"',
        fix: 'Renamed all toggle labels: New Visitor, Beta Tester, Beta + Watching, Returning, Returning + Watching, Power User.',
        action: 'Check the toggle buttons in the bottom-right corner.'
      }
    ];
  }

  var currentStop = 0;
  var overlay, spotlight, tooltip;

  function initTour() {
    // Inject styles
    var style = document.createElement('style');
    style.textContent = [
      '#tour-overlay { position: fixed; inset: 0; z-index: 10000; pointer-events: none; }',
      '#tour-spotlight {',
      '  position: absolute; border-radius: 8px;',
      '  box-shadow: 0 0 0 9999px rgba(0,0,0,0.7);',
      '  transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1);',
      '  pointer-events: none;',
      '}',
      '#tour-tooltip {',
      '  position: absolute; z-index: 10001; width: 360px; max-width: calc(100vw - 48px);',
      '  background: #12121a; border: 1px solid rgba(94,234,212,0.25);',
      '  border-radius: 12px; padding: 20px; pointer-events: auto;',
      '  box-shadow: 0 8px 32px rgba(0,0,0,0.5);',
      '  font-family: "IBM Plex Sans", sans-serif;',
      '}',
      '#tour-tooltip .tour-quote {',
      '  font-family: "JetBrains Mono", monospace; font-size: 12px; font-weight: 300;',
      '  color: #fbbf24; font-style: italic; line-height: 1.5;',
      '  padding: 10px 14px; margin-bottom: 12px;',
      '  background: rgba(251,191,36,0.06); border-left: 2px solid rgba(251,191,36,0.3);',
      '  border-radius: 0 6px 6px 0;',
      '}',
      '#tour-tooltip .tour-fix {',
      '  font-size: 13px; font-weight: 300; color: rgba(255,255,255,0.75);',
      '  line-height: 1.5; margin-bottom: 8px;',
      '}',
      '#tour-tooltip .tour-action {',
      '  font-family: "JetBrains Mono", monospace; font-size: 11px;',
      '  color: #5eead4; margin-bottom: 16px;',
      '}',
      '#tour-tooltip .tour-nav {',
      '  display: flex; justify-content: space-between; align-items: center;',
      '}',
      '#tour-tooltip .tour-counter {',
      '  font-family: "JetBrains Mono", monospace; font-size: 10px; color: rgba(255,255,255,0.25);',
      '}',
      '#tour-tooltip .tour-btns { display: flex; gap: 8px; }',
      '.tour-btn {',
      '  font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 300;',
      '  padding: 6px 14px; border-radius: 6px; cursor: pointer;',
      '  transition: all 0.2s; border: 1px solid rgba(255,255,255,0.06);',
      '  background: rgba(255,255,255,0.04); color: rgba(255,255,255,0.55);',
      '}',
      '.tour-btn:hover { border-color: rgba(94,234,212,0.3); color: #5eead4; }',
      '.tour-btn--primary {',
      '  background: rgba(94,234,212,0.08); border-color: rgba(94,234,212,0.25);',
      '  color: #5eead4;',
      '}',
      '.tour-btn--primary:hover { background: rgba(94,234,212,0.15); }',
    ].join('\n');
    document.head.appendChild(style);

    // Create elements
    overlay = document.createElement('div');
    overlay.id = 'tour-overlay';
    spotlight = document.createElement('div');
    spotlight.id = 'tour-spotlight';
    overlay.appendChild(spotlight);
    document.body.appendChild(overlay);

    tooltip = document.createElement('div');
    tooltip.id = 'tour-tooltip';
    document.body.appendChild(tooltip);

    showStop(0);

    // Keyboard nav
    document.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowRight' || e.key === 'Enter') nextStop();
      if (e.key === 'ArrowLeft') prevStop();
      if (e.key === 'Escape') endTour();
    });
  }

  function showStop(idx) {
    if (idx < 0 || idx >= stops.length) return;
    currentStop = idx;
    var stop = stops[idx];

    // Find element
    var el = document.querySelector(stop.selector);
    if (el) {
      // Scroll into view if needed
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });

      setTimeout(function() {
        var rect = el.getBoundingClientRect();
        var pad = 8;
        spotlight.style.left = (rect.left - pad + window.scrollX) + 'px';
        spotlight.style.top = (rect.top - pad + window.scrollY) + 'px';
        spotlight.style.width = (rect.width + pad * 2) + 'px';
        spotlight.style.height = (rect.height + pad * 2) + 'px';

        // Position tooltip below or above element
        var tooltipTop = rect.bottom + window.scrollY + 16;
        var tooltipLeft = Math.max(24, Math.min(rect.left + window.scrollX, window.innerWidth - 384));
        if (tooltipTop + 250 > window.scrollY + window.innerHeight) {
          tooltipTop = rect.top + window.scrollY - 250;
        }
        tooltip.style.left = tooltipLeft + 'px';
        tooltip.style.top = tooltipTop + 'px';
      }, 400);
    } else {
      // Element not found — position tooltip centered
      spotlight.style.width = '0';
      spotlight.style.height = '0';
      tooltip.style.left = '50%';
      tooltip.style.top = '40%';
      tooltip.style.transform = 'translate(-50%, -50%)';
    }

    tooltip.innerHTML =
      '<div class="tour-quote">' + stop.feedback + '</div>' +
      '<div class="tour-fix">' + stop.fix + '</div>' +
      '<div class="tour-action">' + stop.action + '</div>' +
      '<div class="tour-nav">' +
        '<span class="tour-counter">' + (idx + 1) + ' / ' + stops.length + '</span>' +
        '<div class="tour-btns">' +
          (idx > 0 ? '<button class="tour-btn" onclick="document.dispatchEvent(new Event(\'tour-prev\'))">← Back</button>' : '') +
          (idx < stops.length - 1
            ? '<button class="tour-btn tour-btn--primary" onclick="document.dispatchEvent(new Event(\'tour-next\'))">Next →</button>'
            : '<button class="tour-btn tour-btn--primary" onclick="document.dispatchEvent(new Event(\'tour-end\'))">Done ✓</button>') +
        '</div>' +
      '</div>';
  }

  function nextStop() { if (currentStop < stops.length - 1) showStop(currentStop + 1); else endTour(); }
  function prevStop() { if (currentStop > 0) showStop(currentStop - 1); }
  function endTour() {
    if (overlay) overlay.remove();
    if (tooltip) tooltip.remove();
  }

  document.addEventListener('tour-next', nextStop);
  document.addEventListener('tour-prev', prevStop);
  document.addEventListener('tour-end', endTour);
})();
