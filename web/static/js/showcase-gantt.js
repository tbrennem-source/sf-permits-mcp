/**
 * showcase-gantt.js — Animated Gantt bar reveal on scroll
 * Enhanced by Agent 1B; this stub ensures no 404 if Agent 1B's version hasn't merged yet.
 */
(function () {
  'use strict';

  function initGanttShowcase() {
    var container = document.getElementById('showcase-gantt');
    if (!container) return;

    var bars = container.querySelectorAll('.showcase-gantt__bar');

    // Animate bars to their data-widths on scroll-into-view
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          bars.forEach(function (bar, i) {
            setTimeout(function () {
              bar.style.opacity = '1';
            }, i * 80);
          });
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.2 });

    obs.observe(container);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGanttShowcase);
  } else {
    initGanttShowcase();
  }
})();
