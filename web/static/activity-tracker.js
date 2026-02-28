/**
 * sfpermits.ai — Client-side activity tracker
 * Tracks: dead clicks, time to first action, session events
 * Batches events → POST /api/activity/track every 5s
 */
(function() {
    'use strict';

    // Session ID via sessionStorage
    var SESSION_KEY = 'sfp_session_id';
    var sessionId = sessionStorage.getItem(SESSION_KEY);
    if (!sessionId) {
        sessionId = 'ses_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 6);
        sessionStorage.setItem(SESSION_KEY, sessionId);
    }

    var queue = [];
    var firstActionLogged = false;
    var pageLoadTime = performance.now();

    function enqueue(event, data) {
        queue.push({
            event: event,
            data: data || {},
            session_id: sessionId,
            ts: new Date().toISOString()
        });
    }

    // Dead click detection: click on non-interactive elements
    document.addEventListener('click', function(e) {
        var tag = e.target.tagName.toLowerCase();
        var isInteractive = (tag === 'a' || tag === 'button' || tag === 'input' ||
                           tag === 'select' || tag === 'textarea' || tag === 'label' ||
                           e.target.closest('a') || e.target.closest('button') ||
                           e.target.closest('[hx-get]') || e.target.closest('[hx-post]'));
        if (!isInteractive) {
            enqueue('dead_click', {
                tag: tag,
                classes: (e.target.className || '').toString().substr(0, 100),
                text: (e.target.textContent || '').substr(0, 50).trim(),
                path: location.pathname
            });
        }
    });

    // Time to first action: first form submit or HTMX request
    function logFirstAction(trigger) {
        if (firstActionLogged) return;
        firstActionLogged = true;
        var elapsed = Math.round(performance.now() - pageLoadTime);
        enqueue('first_action', {
            elapsed_ms: elapsed,
            trigger: trigger,
            path: location.pathname
        });
    }

    document.addEventListener('submit', function() { logFirstAction('form_submit'); });
    document.body.addEventListener('htmx:beforeRequest', function() { logFirstAction('htmx_request'); });

    // Flush queue every 5s
    function flush() {
        if (queue.length === 0) return;
        var batch = queue.splice(0, queue.length);
        var body = JSON.stringify({ events: batch });
        // Use sendBeacon for reliability, fallback to fetch
        if (navigator.sendBeacon) {
            navigator.sendBeacon('/api/activity/track', new Blob([body], {type: 'application/json'}));
        } else {
            fetch('/api/activity/track', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('meta[name="csrf-token"]')?.content || ''
                },
                body: body,
                keepalive: true
            }).catch(function() {}); // silent fail
        }
    }

    setInterval(flush, 5000);
    // Flush on page unload
    document.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') flush();
    });
})();
