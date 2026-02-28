/**
 * showcase-entity.js — Entity network graph animation
 * Enhanced by Agent 1B; this stub ensures no 404 if Agent 1B's version hasn't merged yet.
 */
(function () {
  'use strict';

  function initEntityShowcase() {
    var container = document.getElementById('showcase-entity');
    if (!container) return;

    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          container.classList.add('showcase-entity--visible');
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });

    obs.observe(container);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEntityShowcase);
  } else {
    initEntityShowcase();
  }
})();
