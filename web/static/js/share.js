/**
 * share.js — Web Share API on mobile, copy-to-clipboard on desktop.
 * Applied to all .share-btn elements on the page.
 * Sprint QS10-T3-3D
 */
(function () {
  'use strict';

  function initShareButtons() {
    document.querySelectorAll('.share-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var url = window.location.href;
        var title = btn.dataset.shareTitle || 'SF Permit Intelligence';
        var text = btn.dataset.shareText || 'Check out this permit analysis from sfpermits.ai';
        var container = btn.closest('.share-container');
        var copied = container ? container.querySelector('.share-copied') : null;

        if (navigator.share) {
          // Mobile: native share sheet
          navigator.share({ title: title, text: text, url: url })
            .catch(function (e) {
              if (e.name !== 'AbortError') {
                console.error('Share failed:', e);
              }
            });
        } else {
          // Desktop: copy to clipboard
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(url)
              .then(function () {
                showCopiedConfirmation(btn, copied);
              })
              .catch(function () {
                fallbackCopy(url, btn, copied);
              });
          } else {
            fallbackCopy(url, btn, copied);
          }
        }
      });
    });
  }

  function showCopiedConfirmation(btn, copiedEl) {
    if (copiedEl) {
      copiedEl.style.display = 'inline';
      setTimeout(function () {
        copiedEl.style.display = 'none';
      }, 2000);
    }
    // Briefly update button text to confirm
    var originalText = btn.innerHTML;
    btn.innerHTML = '<span class="share-icon" aria-hidden="true">&#10003;</span> Copied!';
    setTimeout(function () {
      btn.innerHTML = originalText;
    }, 2000);
  }

  function fallbackCopy(url, btn, copiedEl) {
    // Textarea fallback for older browsers
    try {
      var ta = document.createElement('textarea');
      ta.value = url;
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      ta.style.left = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      showCopiedConfirmation(btn, copiedEl);
    } catch (e) {
      console.error('Clipboard fallback failed:', e);
    }
  }

  // Run after DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initShareButtons);
  } else {
    initShareButtons();
  }
})();
