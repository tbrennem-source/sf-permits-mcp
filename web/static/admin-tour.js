/* Admin QA Tour — guided walkthrough of recent fixes
   Activates with ?admin=1&tour=1 (sets cookies for persistence).
   Loads tour stops from /api/qa-tour or inline data.
   Each stop: element selector, feedback quote, fix description.
*/
(function() {
  var params = new URLSearchParams(window.location.search);
  // Set cookies if params present
  if (params.has('admin')) document.cookie = 'qa_admin=1;path=/;max-age=86400';
  // Clear any stale qa_tour cookie — tour only runs when ?tour=1 is in the URL
  document.cookie = 'qa_tour=;path=/;max-age=0';
  // tour cookie intentionally not persisted — tour only runs when ?tour=1 is in the URL
  // Check URL params OR cookies (admin persists, tour does not)
  var isAdmin = params.has('admin') || document.cookie.split(';').some(function(c) { return c.trim().startsWith('qa_admin='); });
  var isTour = params.has('tour');
  if (!isAdmin || !isTour) return;

  // Tour stops — each one highlights an element and shows the feedback
  var stops = [];

  // Load stops, then filter out already-accepted ones
  var allStops = [];

  function loadAndFilter() {
    // Get inline stops first
    allStops = getInlineStops();
    if (!allStops.length) return;

    // Fetch existing verdicts from DB to filter out accepted
    fetch('/api/qa-tour-verdicts?page=' + encodeURIComponent(window.location.pathname))
      .then(function(r) { return r.ok ? r.json() : null; })
      .then(function(data) {
        if (data && data.accepted && data.accepted.length) {
          // Filter out stops whose feedback text matches an accepted verdict
          stops = allStops.filter(function(stop) {
            return !data.accepted.some(function(accepted) {
              return accepted.indexOf(stop.feedback.slice(0, 40)) !== -1;
            });
          });
        } else {
          stops = allStops;
        }
        if (stops.length) {
          initTour();
        } else {
          // All stops accepted — show a brief "all clear" message
          showAllClear();
        }
      })
      .catch(function() {
        stops = allStops;
        if (stops.length) initTour();
      });
  }

  function showAllClear() {
    var msg = document.createElement('div');
    msg.style.cssText = 'position:fixed;bottom:80px;right:24px;z-index:10001;background:#12121a;border:1px solid rgba(52,211,153,0.25);border-radius:12px;padding:16px 24px;font-family:"IBM Plex Sans",sans-serif;font-size:13px;color:rgba(255,255,255,0.75);box-shadow:0 8px 32px rgba(0,0,0,0.4);';
    msg.innerHTML = '<span style="color:#34d399;">✓</span> All tour stops accepted — no open items on this page.';
    document.body.appendChild(msg);
    setTimeout(function() { msg.style.opacity = '0'; msg.style.transition = 'opacity 0.5s'; setTimeout(function() { msg.remove(); }, 600); }, 3000);
  }

  loadAndFilter();

  function getInlineStops() {
    var pathname = window.location.pathname;

    // Landing page stops
    if (pathname === '/') return [
      {
        selector: '.scroll-cue',
        feedback: '"down button needs to be brighter" / "down arrow needs to be more visible"',
        fix: 'Bigger arrow (20px), heavier stroke, brighter animation (0.5→1.0 opacity).',
        action: 'Look at the bottom of the hero — arrow should be clearly visible.'
      },
      {
        selector: '.below-search__sub',
        feedback: '"we basically have two Do I need a permit for links — redundant"',
        fix: 'Sub row shortened to "Permits · Timeline · Track · Hire" — no longer duplicates capability card headers.',
        action: 'Check sub row below search — should be short anchor links, not full questions.'
      },
      {
        selector: '#beta-badge',
        feedback: '"BETA should be BETA Tester — more personal and descriptive"',
        fix: 'Badge text changed from "beta" to "beta tester".',
        action: 'Toggle to a beta state and check the badge next to sfpermits.ai wordmark.'
      }
    ];

    // Tool pages (QS10 T3 — new this sprint)
    if (pathname === '/tools/station-predictor') return [
      {
        selector: 'h1, .page-title, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Station predictor tool page. Enter a permit number to see predicted next review stations.',
        action: 'Check layout, try a permit number (e.g. 202301015555), verify HTMX submission works.'
      }
    ];
    if (pathname === '/tools/stuck-permit') return [
      {
        selector: 'h1, .page-title, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Stuck permit analyzer. Enter a permit number to diagnose delays.',
        action: 'Check layout, try a permit number, verify results render correctly.'
      }
    ];
    if (pathname === '/tools/what-if') return [
      {
        selector: 'h1, .page-title, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'What-if simulator. Add scenarios and compare outcomes.',
        action: 'Check form layout, add a scenario, verify CSRF and HTMX work.'
      }
    ];
    if (pathname === '/tools/cost-of-delay') return [
      {
        selector: 'h1, .page-title, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Cost of delay calculator. Enter monthly carrying cost + permit type.',
        action: 'Check form inputs, submit a calculation, verify results render.'
      }
    ];

    // Onboarding pages (QS10 T4 — new this sprint)
    if (pathname === '/beta/onboarding/welcome') return [
      {
        selector: 'h1, .onb-headline, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Beta onboarding step 1: welcome page. Should show 3-step progress indicator.',
        action: 'Check progress indicator, CTA button links to add-property step.'
      }
    ];
    if (pathname === '/beta/onboarding/add-property') return [
      {
        selector: 'h1, .onb-headline, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Beta onboarding step 2: add first property. Form with address input.',
        action: 'Check form layout, progress indicator shows step 2, CSRF token present.'
      }
    ];
    if (pathname === '/beta/onboarding/severity-preview') return [
      {
        selector: 'h1, .onb-headline, h2',
        feedback: 'QS10 Sprint — new page. First review.',
        fix: 'Beta onboarding step 3: severity preview. 3-card signal grid.',
        action: 'Check 3-card layout, CTA links to dashboard, mobile stack at 375px.'
      }
    ];

    return [];
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
      '.tour-verdict { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }',
      '.tour-btn--accept {',
      '  background: rgba(52,211,153,0.08); border-color: rgba(52,211,153,0.25); color: #34d399;',
      '}',
      '.tour-btn--accept:hover { background: rgba(52,211,153,0.15); border-color: #34d399; }',
      '.tour-btn--reject {',
      '  background: rgba(248,113,113,0.08); border-color: rgba(248,113,113,0.25); color: #f87171;',
      '}',
      '.tour-btn--reject:hover { background: rgba(248,113,113,0.15); border-color: #f87171; }',
      '.tour-comment {',
      '  flex: 1; padding: 6px 10px;',
      '  font-family: "JetBrains Mono", monospace; font-size: 11px; font-weight: 300;',
      '  color: rgba(255,255,255,0.75); background: rgba(255,255,255,0.04);',
      '  border: 1px solid rgba(255,255,255,0.06); border-radius: 4px; outline: none;',
      '  transition: border-color 0.2s;',
      '}',
      '.tour-comment:focus { border-color: rgba(94,234,212,0.3); }',
      '.tour-comment::placeholder { color: rgba(255,255,255,0.2); }',
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
      // Don't hijack Enter when typing in comment
      if (e.target.classList && e.target.classList.contains('tour-comment')) {
        if (e.key === 'Enter') {
          e.preventDefault();
          console.log('[tour] Enter in comment — pendingVerdict:', pendingVerdict);
          verdictStop(pendingVerdict || 'accept');
        }
        return;
      }
      if (e.key === 'ArrowRight') nextStop();
      if (e.key === 'ArrowLeft') prevStop();
      if (e.key === 'Escape') endTour();
    });
  }

  function showStop(idx) {
    if (idx < 0 || idx >= stops.length) return;
    currentStop = idx;
    var stop = stops[idx];

    // Find element — skip to next if not found
    var el = document.querySelector(stop.selector);
    if (!el) {
      if (idx < stops.length - 1) { showStop(idx + 1); } else { endTour(); }
      return;
    }
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
      '<div class="tour-verdict">' +
        '<button class="tour-btn tour-btn--accept" onclick="verdictStop(\'accept\')">Accept ✓</button>' +
        '<button class="tour-btn tour-btn--reject" onclick="verdictStop(\'reject\')">Reject ✗</button>' +
        '<input type="text" class="tour-comment" id="tour-comment-' + idx + '" placeholder="Comment (optional, Enter to save)">' +
      '</div>' +
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

  var pendingVerdict = null;

  window.verdictStop = function(verdict) {
    console.log('[tour] verdictStop called:', verdict, 'currentStop:', currentStop, 'totalStops:', stops.length);
    var stop = stops[currentStop];
    var commentEl = document.getElementById('tour-comment-' + currentStop);
    var comment = commentEl ? commentEl.value.trim() : '';
    console.log('[tour] comment:', JSON.stringify(comment));

    // Require a note on reject — stash the verdict so Enter submits it
    if (verdict === 'reject' && !comment) {
      console.log('[tour] reject without comment — prompting');
      pendingVerdict = 'reject';
      if (commentEl) {
        commentEl.placeholder = 'Please add a note — what needs fixing?';
        commentEl.style.borderColor = '#f87171';
        commentEl.focus();
      }
      return;
    }
    pendingVerdict = null;

    stop.verdict = verdict;
    stop.comment = comment;

    // Visual feedback on the button
    try {
      var btns = tooltip.querySelectorAll('.tour-btn--accept, .tour-btn--reject');
      btns.forEach(function(b) { b.style.opacity = '0.3'; });
      var activeBtn = verdict === 'accept'
        ? tooltip.querySelector('.tour-btn--accept')
        : tooltip.querySelector('.tour-btn--reject');
      if (activeBtn) {
        activeBtn.style.opacity = '1';
        activeBtn.style.borderColor = verdict === 'accept' ? '#34d399' : '#f87171';
      }
    } catch(e) {}

    // Save to DB (fire and forget — never blocks advance)
    try {
      var csrfMeta = document.querySelector('meta[name="csrf-token"]');
      var csrfToken = csrfMeta ? csrfMeta.content : '';
      fetch('/api/qa-feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken },
        body: JSON.stringify({
          text: '[TOUR ' + verdict.toUpperCase() + '] ' + stop.feedback + (comment ? ' — ' + comment : ''),
          url: window.location.href,
          page: window.location.pathname,
          viewport: window.innerWidth + 'x' + window.innerHeight,
          scrollY: Math.round(window.scrollY),
          tourStop: currentStop,
          verdict: verdict,
          selector: stop.selector
        })
      }).catch(function() {});
    } catch(e) {}

    // Auto-advance after brief pause — always fires
    console.log('[tour] scheduling nextStop in 600ms');
    setTimeout(function() {
      console.log('[tour] nextStop firing — currentStop:', currentStop, 'total:', stops.length);
      nextStop();
    }, 600);
  };

  function nextStop() {
    console.log('[tour] nextStop — currentStop:', currentStop, 'total:', stops.length);
    if (currentStop < stops.length - 1) { showStop(currentStop + 1); } else { console.log('[tour] endTour (last stop)'); endTour(); }
  }
  function prevStop() { if (currentStop > 0) showStop(currentStop - 1); }
  function endTour() {
    console.log('[tour] endTour called');
    if (overlay) overlay.remove();
    if (tooltip) tooltip.remove();
  }

  document.addEventListener('tour-next', nextStop);
  document.addEventListener('tour-prev', prevStop);
  document.addEventListener('tour-end', endTour);
})();
