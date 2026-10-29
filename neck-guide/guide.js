'use strict';
(() => {
  const goalOptions = [
    ['walking', 'Walking & getting around'], ['sleep', 'Rest & sleep'],
    ['work', 'Work & daily tasks'], ['family', 'Time with family'],
    ['other', 'Something else I’ll discuss at my visit']
  ];
  const questionOptions = [
    ['understand', 'What might explain what I’m experiencing?'],
    ['evaluation', 'What can we learn from my examination or existing records?'],
    ['options', 'What options could we discuss, and what are their benefits and risks?'],
    ['daily', 'What should I know about my usual activities while we make a plan?'],
    ['next', 'What happens next, and who should I contact with questions?']
  ];
  const names = ['Understand', 'Reflect', 'Prepare', 'Take away'];
  const selections = {goals: new Set(), questions: new Set()};
  let step = 0;
  function makeChoices(target, options, className) {
    const container = document.getElementById(target);
    options.forEach(([value, label]) => {
      const row = document.createElement('label');
      row.className = className;
      const input = document.createElement('input');
      input.type = 'checkbox'; input.value = value; input.name = target;
      // Explicitly clear restored form state; selections exist in memory only.
      input.checked = false; input.autocomplete = 'off';
      input.addEventListener('change', () => {
        if (input.checked) selections[target].add(value);
        else selections[target].delete(value);
        renderSummary();
      });
      const text = document.createElement('span'); text.textContent = label;
      row.append(input, text); container.append(row);
    });
  }
  function list(id, options, selected, fallback) {
    const container = document.getElementById(id); container.replaceChildren();
    const values = options.filter(([key]) => selected.has(key)).map(([, label]) => label);
    (values.length ? values : [fallback]).forEach(value => {
      const item = document.createElement('li'); item.textContent = value; container.append(item);
    });
  }
  function renderSummary() {
    list('summary-goals', goalOptions, selections.goals, 'I can share what matters to me during my visit.');
    list('summary-questions', questionOptions, selections.questions, 'What should I understand about my situation, and what happens next?');
  }
  function goTo(next) {
    if (!Number.isInteger(next) || next < 0 || next > 3) return;
    step = next; renderSummary();
    document.querySelectorAll('.step').forEach((panel, index) => { panel.hidden = index !== step; });
    document.querySelectorAll('.progress li').forEach((item, index) => {
      if (index === step) item.setAttribute('aria-current', 'step');
      else item.removeAttribute('aria-current');
    });
    document.getElementById('step-status').textContent = `Step ${step + 1} of 4 · ${names[step]}`;
    const heading = document.getElementById(`title-${step}`);
    heading.focus({preventScroll: true});
    heading.scrollIntoView({block: 'start', behavior: 'auto'});
  }
  makeChoices('goals', goalOptions, 'choice');
  makeChoices('questions', questionOptions, 'question');
  document.querySelectorAll('.next').forEach(button => button.addEventListener('click', () => goTo(step + 1)));
  document.querySelectorAll('.back').forEach(button => button.addEventListener('click', () => goTo(step - 1)));
  document.querySelectorAll('[data-go]').forEach(button => button.addEventListener('click', () => goTo(Number(button.dataset.go))));
  document.getElementById('restart').addEventListener('click', () => {
    selections.goals.clear(); selections.questions.clear();
    document.querySelectorAll('input[type="checkbox"]').forEach(input => { input.checked = false; });
    goTo(0);
  });
  document.getElementById('print').addEventListener('click', () => { renderSummary(); window.print(); });
  window.addEventListener('beforeprint', renderSummary);
  renderSummary();
  document.getElementById('interactive').hidden = false;
})();
