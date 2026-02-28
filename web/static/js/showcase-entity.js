/**
 * showcase-entity.js — Entrance animation for the Entity Network Mini-Graph component.
 * Nodes fade in on scroll using IntersectionObserver. Float animations are CSS-driven.
 */
(function () {
  'use strict';

  function initEntityAnimations() {
    var entityContainers = document.querySelectorAll('.showcase-entity');

    if (!entityContainers.length) return;

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateEntityGraph(entry.target);
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.25, rootMargin: '0px 0px -30px 0px' }
    );

    entityContainers.forEach(function (container) {
      // Pre-hide all nodes and edges
      var nodes = container.querySelectorAll('.entity-node');
      var edges = container.querySelectorAll('line');

      nodes.forEach(function (node) {
        node.style.opacity = '0';
        // Pause float animations until entrance completes
        node.style.animationPlayState = 'paused';
      });

      edges.forEach(function (edge) {
        edge.style.opacity = '0';
        edge.style.transition = 'opacity 0.5s ease';
      });

      observer.observe(container);
    });
  }

  function animateEntityGraph(container) {
    var edges = container.querySelectorAll('line');

    // Fade in central node first
    var centralNode = container.querySelector('.entity-node-central');
    if (centralNode) {
      setTimeout(function () {
        centralNode.style.transition = 'opacity 0.6s ease';
        centralNode.style.opacity = '1';
      }, 100);
    }

    // Fade in edges slightly after central node
    edges.forEach(function (edge, index) {
      setTimeout(function () {
        edge.style.opacity = String(parseFloat(edge.getAttribute('opacity') || '1'));
      }, 400 + index * 80);
    });

    // Fade in secondary nodes in sequence, then start float animations
    var secondaryNodes = container.querySelectorAll('.entity-node-secondary');
    secondaryNodes.forEach(function (node, index) {
      var delay = 600 + index * 120;
      setTimeout(function () {
        node.style.transition = 'opacity 0.5s ease';
        node.style.opacity = '1';
      }, delay);
      // Start float after node has fully appeared
      setTimeout(function () {
        node.style.animationPlayState = 'running';
      }, delay + 600);
    });
  }

  // Initialize on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEntityAnimations);
  } else {
    initEntityAnimations();
  }
})();
