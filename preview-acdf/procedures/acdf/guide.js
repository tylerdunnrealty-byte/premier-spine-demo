/* A view switch, not a questionnaire. No storage, network, or patient input. */
(() => {
  'use strict';
  const buttons = Array.from(document.querySelectorAll('[data-view]'));
  const panels = Array.from(document.querySelectorAll('.visual-panel'));
  if (buttons.length !== 3 || panels.length !== 3) return;
  function select(name) {
    if (!panels.some(panel => panel.id === `view-${name}`)) return;
    buttons.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === name)));
    panels.forEach(panel => { panel.hidden = panel.id !== `view-${name}`; });
  }
  buttons.forEach(button => button.addEventListener('click', () => select(button.dataset.view)));
  select('anatomy');
  document.querySelector('.visual-controls').hidden = false;
})();
