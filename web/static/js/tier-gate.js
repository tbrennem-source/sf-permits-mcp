/**
 * tier-gate.js — Blur main content when tier gate overlay is active.
 *
 * When .tier-gate-overlay is present in the DOM, this script finds the main
 * content container and adds .tier-locked-content which applies an 8px blur.
 *
 * 8px blur calibration: tantalizing but unreadable. The user can see page
 * structure (shapes, colors, layout) but cannot read text or data values.
 * This creates desire without hostile frustration. Do NOT exceed 8px.
 *
 * The blur is applied to the first matching element:
 *   main > .obs-container > .obs-container-wide
 * in that priority order, since all gated pages use one of these containers.
 */
document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.querySelector('.tier-gate-overlay');
  if (!overlay) return;

  // Find the main content container in priority order
  const main = document.querySelector('main, .obs-container, .obs-container-wide');
  if (main) {
    main.classList.add('tier-locked-content');
  }
});
