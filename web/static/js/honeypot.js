/**
 * Honeypot mode JS — rewires CTAs to /join-beta when data-honeypot="true" on body.
 * Fires on DOMContentLoaded. PostHog events sent when posthog is available.
 */
(function () {
  'use strict';

  function getRef(el) {
    // Derive a ref slug from the element context
    var href = el.getAttribute('href') || el.getAttribute('action') || '';
    if (href.includes('/tools')) return 'tools';
    if (href.includes('/portfolio')) return 'portfolio';
    if (href.includes('/dashboard')) return 'dashboard';
    if (href.includes('/login') || href.includes('/signin') || href.includes('/auth')) return 'auth';
    if (href.includes('/signup') || href.includes('/register')) return 'auth';
    var cls = el.className || '';
    if (cls.includes('showcase') || cls.includes('tool-')) {
      var match = cls.match(/tool-([a-z\-]+)/);
      return match ? 'tool-' + match[1] : 'showcase';
    }
    return 'site';
  }

  function trackEvent(name, props) {
    if (window.posthog && typeof window.posthog.capture === 'function') {
      window.posthog.capture(name, props || {});
    }
  }

  function rewriteLink(el, ref) {
    var url = '/join-beta?ref=' + encodeURIComponent(ref);
    el.setAttribute('href', url);
    el.addEventListener('click', function () {
      trackEvent('honeypot_cta_click', { ref: ref });
    });
  }

  function setupScrollDepth() {
    var depths = [25, 50, 75, 100];
    var fired = {};
    window.addEventListener('scroll', function () {
      var pct = Math.round(
        ((window.scrollY + window.innerHeight) / document.documentElement.scrollHeight) * 100
      );
      depths.forEach(function (d) {
        if (pct >= d && !fired[d]) {
          fired[d] = true;
          trackEvent('honeypot_scroll_depth', { depth: d });
        }
      });
    }, { passive: true });
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (document.body.dataset.honeypot !== 'true') return;

    trackEvent('honeypot_page_view');
    setupScrollDepth();

    // Intercept search form
    var searchForms = document.querySelectorAll('form[action="/search"], form.search-form, form[data-search]');
    searchForms.forEach(function (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = form.querySelector('input[name="q"], input[type="search"], input[type="text"]');
        var q = input ? encodeURIComponent(input.value) : '';
        var url = '/join-beta?ref=search' + (q ? '&q=' + q : '');
        trackEvent('honeypot_cta_click', { ref: 'search', q: q });
        window.location.href = url;
      });
    });

    // Rewrite nav and CTA links
    var linkSelectors = [
      'a[href*="/tools"]',
      'a[href*="/portfolio"]',
      'a[href*="/dashboard"]',
      'a[href*="/login"]',
      'a[href*="/signin"]',
      'a[href*="/signup"]',
      'a[href*="/auth"]',
      'a[href*="/register"]',
      '.showcase-cta',
      '.tool-cta',
      '[data-honeypot-cta]',
    ];

    document.querySelectorAll(linkSelectors.join(', ')).forEach(function (el) {
      if (el.tagName === 'A') {
        var ref = getRef(el);
        rewriteLink(el, ref);
      }
    });

    // Also catch "Try it yourself" style CTAs
    document.querySelectorAll('a').forEach(function (el) {
      var text = el.textContent.trim().toLowerCase();
      if (
        text.includes('try it') ||
        text.includes('get started') ||
        text.includes('sign up') ||
        text.includes('sign in') ||
        text.includes('create account')
      ) {
        var href = el.getAttribute('href') || '';
        // Don't rewrite if already pointing to /join-beta or external
        if (!href.startsWith('/join-beta') && !href.startsWith('http') && href.startsWith('/')) {
          var ref = getRef(el);
          rewriteLink(el, ref);
        }
      }
    });
  });
})();
