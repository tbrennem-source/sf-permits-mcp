/**
 * showcase-entity.js — Entrance animation for the Entity Network Mini-Graph component.
 * Nodes fade in and connect sequentially on scroll using IntersectionObserver.
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
      });

      edges.forEach(function (edge) {
        edge.style.opacity = '0';
        edge.style.transition = 'opacity 0.5s ease';
      });

      observer.observe(container);
    });
  }

  function animateEntityGraph(container) {
    var nodes = container.querySelectorAll('.entity-node');
    var edges = container.querySelectorAll('line');
    var edgeLabels = container.querySelectorAll('.entity-edge-label');

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
        edge.style.opacity = '1';
      }, 400 + index * 80);
    });

    // Fade in edge labels with edges
    edgeLabels.forEach(function (label, index) {
      label.style.opacity = '0';
      label.style.transition = 'opacity 0.5s ease';
      setTimeout(function () {
        label.style.opacity = '1';
      }, 500 + index * 80);
    });

    // Fade in secondary nodes in sequence
    var secondaryNodes = container.querySelectorAll('.entity-node-secondary');
    secondaryNodes.forEach(function (node, index) {
      setTimeout(function () {
        node.style.transition = 'opacity 0.5s ease ' + (index * 0.12) + 's';
        node.style.opacity = '1';
      }, 600 + index * 120);
    });
  }

  // Initialize on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initEntityAnimations);
  } else {
    initEntityAnimations();
  }
})();
