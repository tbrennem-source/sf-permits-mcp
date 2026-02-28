/* Admin QA Feedback Widget
   Only activates when ?admin=1 is in the URL.
   Floating panel: type feedback, hit Enter, get a new box.
   All feedback saved to localStorage + POST to /api/qa-feedback (if endpoint exists).
*/
(function() {
  if (!new URLSearchParams(window.location.search).has('admin')) return;

  var feedbackItems = JSON.parse(localStorage.getItem('qa-feedback') || '[]');

  // Create panel
  var panel = document.createElement('div');
  panel.id = 'qa-panel';
  panel.innerHTML = `
    <div class="qa-panel__header">
      <span class="qa-panel__title">QA Feedback</span>
      <span class="qa-panel__count" id="qa-count">${feedbackItems.length}</span>
      <button class="qa-panel__toggle" id="qa-toggle">−</button>
    </div>
    <div class="qa-panel__body" id="qa-body">
      <div class="qa-panel__history" id="qa-history"></div>
      <div class="qa-panel__input-row">
        <input type="text" class="qa-panel__input" id="qa-input" placeholder="Type feedback, press Enter..." autocomplete="off">
      </div>
      <div class="qa-panel__actions">
        <button class="qa-panel__btn" id="qa-export">Export JSON</button>
        <button class="qa-panel__btn qa-panel__btn--danger" id="qa-clear">Clear all</button>
      </div>
    </div>
  `;
  document.body.appendChild(panel);

  // Styles
  var style = document.createElement('style');
  style.textContent = `
    #qa-panel {
      position: fixed; bottom: 80px; right: 24px; z-index: 9999;
      width: 340px; max-height: 500px;
      background: #12121a; border: 1px solid rgba(255,255,255,0.1);
      border-radius: 12px; overflow: hidden;
      font-family: 'IBM Plex Sans', sans-serif;
      box-shadow: 0 8px 32px rgba(0,0,0,0.4);
    }
    .qa-panel__header {
      display: flex; align-items: center; gap: 8px;
      padding: 10px 16px; border-bottom: 1px solid rgba(255,255,255,0.06);
      cursor: pointer;
    }
    .qa-panel__title {
      font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 400;
      color: rgba(255,255,255,0.55); letter-spacing: 0.06em; text-transform: uppercase;
      flex: 1;
    }
    .qa-panel__count {
      font-family: 'JetBrains Mono', monospace; font-size: 10px;
      color: #5eead4; background: rgba(94,234,212,0.08);
      border: 1px solid rgba(94,234,212,0.2);
      padding: 1px 6px; border-radius: 9999px;
    }
    .qa-panel__toggle {
      background: none; border: none; color: rgba(255,255,255,0.3);
      font-size: 16px; cursor: pointer; padding: 0 4px;
    }
    .qa-panel__body { padding: 8px; }
    .qa-panel__body.collapsed { display: none; }
    .qa-panel__history {
      max-height: 280px; overflow-y: auto; margin-bottom: 8px;
      scrollbar-width: thin; scrollbar-color: rgba(255,255,255,0.06) transparent;
    }
    .qa-panel__item {
      padding: 8px 10px; margin-bottom: 4px;
      background: rgba(255,255,255,0.03); border-radius: 6px;
      font-size: 12px; color: rgba(255,255,255,0.75); line-height: 1.4;
    }
    .qa-panel__item-meta {
      font-family: 'JetBrains Mono', monospace; font-size: 9px;
      color: rgba(255,255,255,0.2); margin-top: 4px;
      display: flex; gap: 8px;
    }
    .qa-panel__input-row { padding: 0 0 8px; }
    .qa-panel__input {
      width: 100%; padding: 10px 12px;
      font-family: 'JetBrains Mono', monospace; font-size: 12px; font-weight: 300;
      color: rgba(255,255,255,0.92); background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.06); border-radius: 6px; outline: none;
      transition: border-color 0.2s;
    }
    .qa-panel__input:focus { border-color: rgba(94,234,212,0.3); }
    .qa-panel__input::placeholder { color: rgba(255,255,255,0.2); }
    .qa-panel__actions {
      display: flex; gap: 6px; padding: 4px 0;
    }
    .qa-panel__btn {
      font-family: 'JetBrains Mono', monospace; font-size: 10px;
      color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.06); border-radius: 4px;
      padding: 4px 10px; cursor: pointer; transition: color 0.2s, border-color 0.2s;
    }
    .qa-panel__btn:hover { color: #5eead4; border-color: rgba(94,234,212,0.3); }
    .qa-panel__btn--danger:hover { color: #f87171; border-color: rgba(248,113,113,0.3); }
  `;
  document.head.appendChild(style);

  // Elements
  var input = document.getElementById('qa-input');
  var history = document.getElementById('qa-history');
  var count = document.getElementById('qa-count');
  var toggle = document.getElementById('qa-toggle');
  var body = document.getElementById('qa-body');
  var exportBtn = document.getElementById('qa-export');
  var clearBtn = document.getElementById('qa-clear');

  function renderHistory() {
    history.innerHTML = feedbackItems.map(function(item, i) {
      return '<div class="qa-panel__item">' +
        item.text +
        '<div class="qa-panel__item-meta">' +
          '<span>' + item.page + '</span>' +
          '<span>' + item.viewport + '</span>' +
          '<span>' + item.time + '</span>' +
        '</div>' +
      '</div>';
    }).join('');
    count.textContent = feedbackItems.length;
    history.scrollTop = history.scrollHeight;
  }

  function saveFeedback(text) {
    var item = {
      text: text,
      url: window.location.href,
      page: window.location.pathname,
      viewport: window.innerWidth + 'x' + window.innerHeight,
      scrollY: Math.round(window.scrollY),
      timestamp: new Date().toISOString(),
      time: new Date().toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'}),
      userAgent: navigator.userAgent.slice(0, 80)
    };
    feedbackItems.push(item);
    localStorage.setItem('qa-feedback', JSON.stringify(feedbackItems));
    renderHistory();

    // POST to server (non-blocking)
    try {
      fetch('/api/qa-feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
      }).then(function(r) {
        if (r.ok) {
          item.synced = true;
          localStorage.setItem('qa-feedback', JSON.stringify(feedbackItems));
        }
      }).catch(function() {});
    } catch(e) {}
  }

  // Enter to submit
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && input.value.trim()) {
      saveFeedback(input.value.trim());
      input.value = '';
    }
  });

  // Toggle collapse
  toggle.addEventListener('click', function(e) {
    e.stopPropagation();
    body.classList.toggle('collapsed');
    toggle.textContent = body.classList.contains('collapsed') ? '+' : '−';
  });
  document.querySelector('.qa-panel__header').addEventListener('click', function() {
    body.classList.toggle('collapsed');
    toggle.textContent = body.classList.contains('collapsed') ? '+' : '−';
  });

  // Export
  exportBtn.addEventListener('click', function() {
    var blob = new Blob([JSON.stringify(feedbackItems, null, 2)], {type: 'application/json'});
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'qa-feedback-' + new Date().toISOString().slice(0,10) + '.json';
    a.click();
    URL.revokeObjectURL(url);
  });

  // Clear
  clearBtn.addEventListener('click', function() {
    if (confirm('Clear all feedback?')) {
      feedbackItems = [];
      localStorage.setItem('qa-feedback', '[]');
      renderHistory();
    }
  });

  // Initial render
  renderHistory();

  // Sync any unsynced items from localStorage to server on load
  feedbackItems.forEach(function(item) {
    if (!item.synced) {
      fetch('/api/qa-feedback', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(item)
      }).then(function(r) {
        if (r.ok) {
          item.synced = true;
          localStorage.setItem('qa-feedback', JSON.stringify(feedbackItems));
        }
      }).catch(function() {});
    }
  });

  // Focus shortcut: Ctrl+Shift+F to focus the feedback input
  document.addEventListener('keydown', function(e) {
    if (e.ctrlKey && e.shiftKey && e.key === 'F') {
      e.preventDefault();
      input.focus();
    }
  });
})();
