/**
 * mcp-demo.js — MCP Demo Chat Transcript Animation
 * sfpermits.ai
 *
 * Scroll-triggered animated chat transcript showing Claude using sfpermits.ai tools.
 * Cycles through 3 demo conversations: What-If → Stuck Permit → Cost of Delay.
 *
 * Animation sequence per demo:
 *   1. User message fades in + slides up (0.5s)
 *   2. Tool call badges appear sequentially with 0.3s stagger, pulse once
 *   3. Claude response types line by line (tables render instantly)
 *   4. Pause 4s at end
 *   5. Fade out current (0.5s), fade in next
 */

(function () {
  'use strict';

  var DEMO_COUNT = 3;
  var PAUSE_BETWEEN = 4000;       // 4s pause at end of each demo
  var CHAR_DELAY = 40;            // 40ms per character for typed lines
  var MSG_FADE_IN = 500;          // user message fade-in duration
  var BADGE_STAGGER = 300;        // stagger between tool badges
  var LINE_MIN_DELAY = 200;       // minimum delay per typed line
  var TRANSITION_FADE = 500;      // fade transition between demos

  var currentSlide = 0;
  var autoTimer = null;
  var isAnimating = false;
  var hasStarted = false;
  var animationAborted = false;

  // DOM references (set on init)
  var section = null;
  var slides = [];
  var dots = [];
  var prevBtn = null;
  var nextBtn = null;

  /**
   * Initialize the demo component
   */
  function init() {
    section = document.getElementById('mcp-demo');
    if (!section) return;

    slides = section.querySelectorAll('.mcp-demo-slide');
    dots = section.querySelectorAll('.mcp-demo-dot');
    prevBtn = document.getElementById('mcp-demo-prev');
    nextBtn = document.getElementById('mcp-demo-next');

    if (slides.length === 0) return;

    // Set up navigation
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        goToSlide((currentSlide - 1 + DEMO_COUNT) % DEMO_COUNT);
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        goToSlide((currentSlide + 1) % DEMO_COUNT);
      });
    }

    dots.forEach(function (dot) {
      dot.addEventListener('click', function () {
        var idx = parseInt(dot.getAttribute('data-slide'), 10);
        if (!isNaN(idx)) goToSlide(idx);
      });
    });

    // Set up mobile expand/collapse
    setupMobileExpand();

    // Set up IntersectionObserver for scroll trigger
    setupScrollTrigger();
  }

  /**
   * Set up IntersectionObserver to trigger animation when section enters viewport
   */
  function setupScrollTrigger() {
    // Check for reduced motion preference
    var prefersReduced = window.matchMedia &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReduced) {
      // Show everything immediately without animation
      showAllImmediate();
      return;
    }

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting && !hasStarted) {
            hasStarted = true;
            observer.unobserve(entry.target);
            startAnimation();
          }
        });
      }, {
        threshold: 0.3
      });

      observer.observe(section);
    } else {
      // Fallback: start immediately if no IntersectionObserver
      startAnimation();
    }
  }

  /**
   * Show all content immediately (for reduced motion)
   */
  function showAllImmediate() {
    slides.forEach(function (slide, i) {
      if (i === 0) {
        slide.classList.add('active');
      }
      // Show all messages
      var msgs = slide.querySelectorAll('.mcp-msg');
      msgs.forEach(function (msg) { msg.classList.add('visible'); });

      // Show all badges
      var badges = slide.querySelectorAll('.mcp-tool-badge');
      badges.forEach(function (b) { b.classList.add('visible'); });

      // Show all typed lines
      var lines = slide.querySelectorAll('.mcp-typed-line');
      lines.forEach(function (l) { l.classList.add('visible'); });

      // Show all tables and stacked cards
      var tables = slide.querySelectorAll('.mcp-response-table, .mcp-stacked-cards');
      tables.forEach(function (t) { t.classList.add('visible'); });
    });
    hasStarted = true;
    // Still enable auto-advance
    scheduleNext();
  }

  /**
   * Start the animation sequence for the current slide
   */
  function startAnimation() {
    animateSlide(currentSlide);
  }

  /**
   * Animate a single slide's chat messages
   */
  function animateSlide(index) {
    if (isAnimating) return;
    isAnimating = true;
    animationAborted = false;

    var slide = slides[index];
    if (!slide) { isAnimating = false; return; }

    // Reset all elements in this slide
    resetSlide(slide);

    // Collect animation steps
    var delay = 0;
    var timeouts = [];

    // 1. User message fade-in
    var userMsg = slide.querySelector('.mcp-msg--user');
    if (userMsg) {
      timeouts.push(setTimeout(function () {
        if (animationAborted) return;
        userMsg.classList.add('visible');
      }, delay));
      delay += MSG_FADE_IN + 200;
    }

    // 2. Tool badges appear with stagger
    var badges = slide.querySelectorAll('.mcp-tool-badge');
    badges.forEach(function (badge, i) {
      timeouts.push(setTimeout(function () {
        if (animationAborted) return;
        badge.classList.add('visible');
        badge.classList.add('pulse');
      }, delay + (i * BADGE_STAGGER)));
    });
    if (badges.length > 0) {
      delay += (badges.length * BADGE_STAGGER) + 400;
    }

    // 3. Claude message container
    var claudeMsg = slide.querySelector('.mcp-msg--claude');
    if (claudeMsg) {
      timeouts.push(setTimeout(function () {
        if (animationAborted) return;
        claudeMsg.classList.add('visible');
      }, delay));
      delay += 200;
    }

    // 4. Animate typed lines and tables sequentially
    // NOTE: must target the Claude bubble specifically — the first .mcp-msg__bubble
    // is the user message bubble which contains no typed lines. Querying the user
    // bubble returns an empty NodeList so nothing animates.
    var bubble = slide.querySelector('.mcp-msg--claude .mcp-msg__bubble');
    if (bubble) {
      // Get all animatable children in order
      var children = bubble.querySelectorAll('.mcp-typed-line, .mcp-response-table, .mcp-stacked-cards');
      children.forEach(function (child) {
        if (child.classList.contains('mcp-typed-line')) {
          // Typed line: delay based on text length
          var textLen = child.textContent.length;
          var lineDelay = Math.max(LINE_MIN_DELAY, Math.min(textLen * CHAR_DELAY, 2000));
          timeouts.push(setTimeout(function () {
            if (animationAborted) return;
            child.classList.add('visible');
          }, delay));
          delay += lineDelay;
        } else {
          // Table or stacked cards: render instantly
          timeouts.push(setTimeout(function () {
            if (animationAborted) return;
            child.classList.add('visible');
          }, delay));
          delay += 300;
        }
      });
    }

    // 5. Schedule auto-advance after pause
    timeouts.push(setTimeout(function () {
      isAnimating = false;
      if (!animationAborted) {
        scheduleNext();
      }
    }, delay + PAUSE_BETWEEN));

    // Store timeouts for cleanup on manual navigation
    slide._timeouts = timeouts;
  }

  /**
   * Reset all animated elements in a slide
   */
  function resetSlide(slide) {
    // Clear any pending timeouts
    if (slide._timeouts) {
      slide._timeouts.forEach(function (t) { clearTimeout(t); });
      slide._timeouts = [];
    }

    var msgs = slide.querySelectorAll('.mcp-msg');
    msgs.forEach(function (msg) { msg.classList.remove('visible'); });

    var badges = slide.querySelectorAll('.mcp-tool-badge');
    badges.forEach(function (b) {
      b.classList.remove('visible');
      b.classList.remove('pulse');
    });

    var lines = slide.querySelectorAll('.mcp-typed-line');
    lines.forEach(function (l) { l.classList.remove('visible'); });

    var tables = slide.querySelectorAll('.mcp-response-table, .mcp-stacked-cards');
    tables.forEach(function (t) { t.classList.remove('visible'); });
  }

  /**
   * Schedule the next auto-advance
   */
  function scheduleNext() {
    clearAutoTimer();
    autoTimer = setTimeout(function () {
      var next = (currentSlide + 1) % DEMO_COUNT;
      goToSlide(next);
    }, 0); // Immediate — pause was already in animateSlide
  }

  /**
   * Navigate to a specific slide
   */
  function goToSlide(index) {
    if (index === currentSlide && isAnimating) return;

    clearAutoTimer();

    // Abort current animation
    animationAborted = true;
    isAnimating = false;
    if (slides[currentSlide] && slides[currentSlide]._timeouts) {
      slides[currentSlide]._timeouts.forEach(function (t) { clearTimeout(t); });
    }

    // Fade out current slide
    var oldSlide = slides[currentSlide];
    if (oldSlide) {
      oldSlide.classList.add('fading-out');
      oldSlide.classList.remove('active');
    }

    // Update dots
    dots.forEach(function (dot) { dot.classList.remove('active'); });
    if (dots[index]) dots[index].classList.add('active');

    currentSlide = index;

    // After fade-out, show new slide
    setTimeout(function () {
      if (oldSlide) {
        oldSlide.classList.remove('fading-out');
        resetSlide(oldSlide);
      }

      var newSlide = slides[currentSlide];
      if (newSlide) {
        newSlide.classList.add('active');
        // Start animation for the new slide
        animateSlide(currentSlide);
      }
    }, TRANSITION_FADE);
  }

  /**
   * Clear auto-advance timer
   */
  function clearAutoTimer() {
    if (autoTimer) {
      clearTimeout(autoTimer);
      autoTimer = null;
    }
  }

  /**
   * Set up mobile expand/collapse behavior
   */
  function setupMobileExpand() {
    var wrappers = document.querySelectorAll('.mcp-expand-wrapper[data-collapsible]');
    // On mobile, add collapsible class
    function checkMobile() {
      var isMobile = window.innerWidth <= 480;
      wrappers.forEach(function (w) {
        if (isMobile) {
          if (!w.classList.contains('expanded')) {
            w.classList.add('collapsible');
          }
        } else {
          w.classList.remove('collapsible');
        }
      });
    }

    checkMobile();
    window.addEventListener('resize', debounce(checkMobile, 200));
  }

  /**
   * Simple debounce utility
   */
  function debounce(fn, wait) {
    var timer;
    return function () {
      clearTimeout(timer);
      timer = setTimeout(fn, wait);
    };
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
