/* toast.js — sfpermits.ai
 * Standalone toast notification component.
 * From docs/DESIGN_TOKENS.md §5 Toast / Notification.
 *
 * Usage:
 *   showToast('Watch added');
 *   showToast('Something failed', { type: 'error' });
 *   showToast('Watch added', { action: () => undoWatch(), actionLabel: 'Undo' });
 *
 * Options:
 *   type        — 'success' | 'error' | 'info'  (default: 'success')
 *   action      — function to call when action link is clicked
 *   actionLabel — label for the action link  (default: 'Undo')
 *   duration    — ms before auto-dismiss  (default: 5000)
 */
function showToast(message, opts) {
  var options = opts || {};
  var type = options.type || 'success';
  var action = options.action || null;
  var actionLabel = options.actionLabel || 'Undo';
  var duration = options.duration !== undefined ? options.duration : 5000;

  var icon = type === 'success' ? '&#10003;' : type === 'error' ? '!' : 'i';

  var toast = document.createElement('div');
  toast.className = 'toast toast--' + type;
  toast.setAttribute('role', 'status');
  toast.setAttribute('aria-live', 'polite');
  toast.innerHTML =
    '<span class="toast__icon">' + icon + '</span>' +
    '<span class="toast__message">' + message + '</span>' +
    (action ? '<a href="#" class="toast__action">' + actionLabel + '</a>' : '') +
    '<button class="toast__dismiss" aria-label="Dismiss">&times;</button>';

  document.body.appendChild(toast);

  var timer = setTimeout(function() { dismiss(); }, duration);

  toast.addEventListener('mouseenter', function() { clearTimeout(timer); });
  toast.addEventListener('mouseleave', function() {
    timer = setTimeout(function() { dismiss(); }, duration);
  });

  toast.querySelector('.toast__dismiss').addEventListener('click', function(e) {
    e.preventDefault();
    dismiss();
  });

  if (action) {
    toast.querySelector('.toast__action').addEventListener('click', function(e) {
      e.preventDefault();
      action();
      dismiss();
    });
  }

  function dismiss() {
    clearTimeout(timer);
    toast.classList.add('toast--exit');
    setTimeout(function() {
      if (toast.parentNode) { toast.parentNode.removeChild(toast); }
    }, 250);
  }
}
