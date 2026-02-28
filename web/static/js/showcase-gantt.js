/**
 * showcase-gantt.js — Entrance animation for the Station Timeline Gantt component.
 * Bars grow from left on scroll using IntersectionObserver.
 */
(function () {
  'use strict';

  function initGanttAnimations() {
    var ganttContainers = document.querySelectorAll('.showcase-gantt');

    if (!ganttContainers.length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateGantt(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.2, rootMargin: '0px 0px -40px 0px' }
    );

    ganttContainers.forEach(function (container) {
      // Set bars to scale(0) initially via transform
      var bars = container.querySelectorAll('.gantt-bar');
      bars.forEach(function (bar) {
        bar.style.transform = 'scaleX(0)';
        bar.style.transformOrigin = 'left center';
        bar.style.transitionProperty = 'transform';
        bar.style.transitionDuration = '0s';
        bar.style.transitionTimingFunction = 'cubic-bezier(0.16, 1, 0.3, 1)';
      });

      observer.observe(container);
    });
  }

  function animateGantt(container) {
    var bars = container.querySelectorAll('.gantt-bar');

    bars.forEach(function (bar, index) {
      var delay = 80 + index * 100; // stagger each bar by 100ms
      var duration = 900 + index * 60; // slightly longer for later bars

      setTimeout(function () {
        bar.style.transitionDuration = duration + 'ms';
        bar.style.transform = 'scaleX(1)';
      }, delay);
    });
  }

  // Initialize on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initGanttAnimations);
  } else {
    initGanttAnimations();
  }
})();
