/**
 * mcp-demo.js — Animated MCP chat demo
 * Created by Agent 1C; this stub ensures no 404 if Agent 1C's version hasn't merged yet.
 * The real version animates the chat bubbles sequentially on scroll.
 */
(function () {
  'use strict';

  function initMcpDemo() {
    var container = document.getElementById('mcp-demo-container');
    if (!container) return;

    var messages = [
      document.getElementById('mcp-tool-call'),
      document.getElementById('mcp-tool-result'),
      document.getElementById('mcp-assistant-msg'),
    ].filter(Boolean);

    // All visible by default for no-JS fallback; JS adds animation class
    messages.forEach(function (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      el.style.transition = 'opacity 0.5s ease, transform 0.5s ease';
    });

    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          messages.forEach(function (el, i) {
            setTimeout(function () {
              el.style.opacity = '1';
              el.style.transform = 'translateY(0)';
            }, 300 + i * 400);
          });
          obs.unobserve(entry.target);
        }
      });
    }, { threshold: 0.25 });

    obs.observe(container);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initMcpDemo);
  } else {
    initMcpDemo();
  }
})();
