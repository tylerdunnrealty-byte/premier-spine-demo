/* Premier Spine portal — online demo shell.  Picks a demo recording (fictional patients), shows the real portal/office screens in frames,
   and runs a short guided tour.  No network requests beyond these static files, no storage, no tracking. */
(function () {
  'use strict';
  var M = window.__PS_MOCK, $ = function (s) { return document.querySelector(s); };
  var PATIENTS = [
    ['clean:booked', 'Avery', 'Ready for a first visit, and the visit is booked', '#/home'],
    ['clean:intake', 'Avery', 'Checking an intake form that arrived pre-filled', '#/intake'],
    ['missing', 'Blake', 'Waiting on records from other offices', '#/home'],
    ['auth', 'Cameron', 'Waiting on an insurance approval', '#/home'],
    ['nointake', 'Drew', 'Hasn’t started the intake form yet', '#/home'],
    ['caregiver+helper', 'Emery (with Frankie)', 'A family member helping — seen as Frankie', '#/home'],
    ['notfit', 'Finley', 'Referral being reviewed by Dr. Yakel', '#/home'],
    ['redflag', 'Gray', 'Reported an urgent symptom on the intake form', '#/home'],
    ['surgery', 'Harper', 'Getting ready for surgery', '#/home'],
    ['surgery:postop', 'Harper', 'After surgery: the day-2 check-in', '#/home']];
  var OFFICE = [
    ['redflag', 'Nina · Nurse', 'Urgent items first, then everything else that needs a person', '#/queue'],
    ['redflag@pat', 'Pat · Front desk', 'Sees urgent items and who owns them; routine booking waits', '#/queue'],
    ['clean@yakel', 'Dr. Yakel', 'A new patient’s visit-ready summary (draft for review)', 'task', '#d-sum'],
    ['redflag@admin', 'Practice manager', 'Rules, settings and reports the practice controls', '#/settings']];
  var TOUR = [
    { k: 'Fewer phone calls', h: 'Patients can see where things stand', p: 'Blake’s Home answers the questions patients usually call about: what we’re waiting on, who has it, and whether he needs to do anything.', slot: 'missing', side: 'portal', pr: '#/home', or: '#/queue' },
    { k: 'Automatic chasing', h: 'Follow-ups go out on time', p: 'Cameron’s insurer hadn’t replied by the follow-up date, so a follow-up went out automatically (simulated here). A person is only asked to step in if it gets stuck.', slot: 'auth:chased', side: 'office', pr: '#/home', or: 'task' },
    { k: 'Pre-filled intake', h: 'Patients confirm instead of retyping', p: 'Avery’s intake arrives pre-filled from the referral. She only confirms or corrects each item, and each one shows where it came from.', slot: 'clean:intake', side: 'portal', pr: '#/intake', or: '#/queue' },
    { k: 'Visit-ready summary', h: 'Dr. Yakel starts the visit prepared', p: 'A one-page summary marked “Draft — clinician review required”, with the patient’s own words kept apart from extracted facts and their sources.', slot: 'clean@yakel', side: 'office', pr: '#/home', or: 'task', of: '#d-sum' },
    { k: 'Surgery prep and post-op', h: 'Clear steps before and after surgery', p: 'Before surgery: a checklist showing who does what. After: short check-ins, using instructions the practice has approved.', slot: 'surgery:postop', side: 'portal', pr: '#/home', or: '#/queue' },
    { k: 'Urgent first', h: 'A worry reaches the nurse first', p: 'When Harper says something worries her, it becomes an urgent nurse task pinned above all routine work, with no medical advice given by the portal.', slot: 'surgery:postop_concern@nina', side: 'office', pr: '#/home', or: '#/queue' }];
  var STEP_MS = 10000, wide = window.matchMedia('(min-width: 1100px)'), reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  var cur = null, side = 'portal', tour = { on: false, i: 0, playing: false, t: null, start: 0 }, n = 0;

  function rec(slot) { return M && M.rec ? M.rec(slot) : null; }
  function el(tag, attrs, kids) { var e = document.createElement(tag); Object.keys(attrs || {}).forEach(function (k) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); }); (kids || []).forEach(function (c) { if (c) e.appendChild(c); }); return e; }

  /* ---------- start screen ---------- */
  function pickList(ul, rows, kind) {
    rows.forEach(function (r) {
      var b = el('button', { type: 'button', class: 'pick', id: 'pick-' + kind + '-' + r[0].replace(/[^a-z]/gi, '-') }, [el('span', { class: 'pn', text: r[1] }), el('span', { class: 'ps', text: r[2] }), el('span', { class: 'chev', 'aria-hidden': 'true' })]);
      b.addEventListener('click', function () { go('#/' + kind + '/' + encodeURIComponent(r[0])); });
      ul.appendChild(el('li', {}, [b]));
    });
  }
  pickList($('#plist'), PATIENTS, 'patient'); pickList($('#olist'), OFFICE, 'office');
  function toggle(btn, box, other, otherBtn) {
    var open = btn.getAttribute('aria-expanded') !== 'true'; btn.setAttribute('aria-expanded', String(open)); box.hidden = !open;
    if (open) { otherBtn.setAttribute('aria-expanded', 'false'); other.hidden = true; var f = box.querySelector('button'); box.scrollIntoView({ block: 'nearest', behavior: reduce.matches ? 'auto' : 'smooth' }); if (f) setTimeout(function () { f.focus({ preventScroll: true }); }, 50); }
  }
  $('#go-patient').addEventListener('click', function () { toggle(this, $('#pick-patient'), $('#pick-office'), $('#go-office')); });
  $('#go-office').addEventListener('click', function () { toggle(this, $('#pick-office'), $('#pick-patient'), $('#go-patient')); });
  $('#go-tour').addEventListener('click', function () { go('#/tour/1'); });
  $('#app-back').addEventListener('click', function () { go('#/'); });
  window.__PS_EXIT = function () { go('#/'); };   /* "Sign out" inside a frame returns to the demo start */

  /* ---------- the app view ---------- */
  function officeRoute(r, slot) { var K = rec(slot); return r === 'task' ? (K && K.open_task ? '#/task/' + K.open_task : '#/queue') : r; }
  function load(slot, pr, or) {
    M.replay(slot); n++;
    $('#f-portal').src = 'portal.html?r=' + n + (pr || '#/home');
    $('#f-office').src = 'office.html?r=' + n + officeRoute(or || '#/queue', slot);
    cur = slot;
  }
  /* bring a part of the office screen into view once it has rendered (e.g. the visit summary) */
  function reveal(sel) {
    if (!sel) return; var f = $('#f-office'), tries = 0, my = n;
    (function look() { if (my !== n) return; var d = f.contentDocument, e = d && d.querySelector(sel);
      if (e && e.textContent.trim()) { var w = f.contentWindow; w.scrollTo({ top: e.getBoundingClientRect().top + w.scrollY - 12, behavior: reduce.matches ? 'auto' : 'smooth' }); return; }   /* scroll only inside the frame */
      if (++tries < 40) setTimeout(look, 150); })();
  }
  function setSide(s) {
    if (s === 'both' && !wide.matches) s = 'portal';
    side = s;
    $('#fw-portal').hidden = !(s === 'portal' || s === 'both'); $('#fw-office').hidden = !(s === 'office' || s === 'both');
    $('#frames').className = 'frames' + (s === 'both' ? ' both' : ' one-' + s);
    Array.prototype.forEach.call(document.querySelectorAll('#seg button'), function (b) { b.setAttribute('aria-pressed', String(b.dataset.side === s)); });
  }
  $('#seg').addEventListener('click', function (e) { var b = e.target.closest('button'); if (b) setSide(b.dataset.side); });
  wide.addEventListener && wide.addEventListener('change', function () { if (!wide.matches && side === 'both') setSide('portal'); });
  function show(v) {
    $('#v-start').hidden = v !== 'start'; $('#v-app').hidden = v !== 'app';
    document.body.classList.toggle('in-app', v === 'app'); $('#foot').hidden = v === 'app'; $('#site').hidden = v === 'app';
  }
  function openApp(kind, slot) {
    var rows = kind === 'patient' ? PATIENTS : OFFICE, r = rows.filter(function (x) { return x[0] === slot; })[0], K = rec(slot); if (!K) { go('#/'); return; }
    if (!r) { var t = TOUR.filter(function (x) { return x.slot === slot; })[0]; r = [slot, kind === 'patient' ? K.portal_as : K.office_as, t ? t.k : K.title, kind === 'patient' ? (t ? t.pr : '#/home') : (t ? t.or : '#/queue')]; }   /* a tour moment opened directly */
    stopTour(); show('app'); $('#tourbar').hidden = true;
    $('#h-app').textContent = r[1] + ' · ' + r[2];
    document.title = 'DEMO · ' + r[1] + ' · Premier Spine Patient Portal (example data)';
    load(slot, kind === 'patient' ? r[3] : '#/home', kind === 'office' ? r[3] : '#/queue'); if (kind === 'office') reveal(r[4]);
    setSide(wide.matches ? 'both' : kind === 'patient' ? 'portal' : 'office');
    $('#h-app').setAttribute('tabindex', '-1'); $('#h-app').focus({ preventScroll: true }); window.scrollTo(0, 0);
  }

  /* ---------- the tour ---------- */
  var dots = $('#tb-dots'); TOUR.forEach(function () { dots.appendChild(el('span', {})); });
  function stopTimer() { clearTimeout(tour.t); tour.t = null; var b = $('#tb-bar'); b.style.transition = 'none'; b.style.width = '0'; }
  function runTimer() {
    stopTimer(); if (!tour.playing) return;
    var b = $('#tb-bar'); void b.offsetWidth; if (!reduce.matches) { b.style.transition = 'width ' + STEP_MS + 'ms linear'; b.style.width = '100%'; }
    tour.t = setTimeout(function () { if (tour.i < TOUR.length - 1) go('#/tour/' + (tour.i + 2)); else { tour.playing = false; syncPlay(); } }, STEP_MS);
  }
  function syncPlay() { var b = $('#tb-play'); b.textContent = tour.playing ? 'Pause' : 'Play'; b.setAttribute('aria-pressed', String(tour.playing)); if (!tour.playing) stopTimer(); }
  function openTour(i) {
    if (!tour.on) { tour.on = true; tour.playing = !reduce.matches; }
    tour.i = i; var s = TOUR[i]; show('app'); $('#tourbar').hidden = false; document.body.classList.add('touring');
    $('#tb-k').textContent = 'Tour · ' + (i + 1) + ' of ' + TOUR.length + ' · ' + s.k; $('#tb-h').textContent = s.h; $('#tb-p').textContent = s.p;
    $('#h-app').textContent = 'Guided tour';
    document.title = 'DEMO · Tour ' + (i + 1) + ' of ' + TOUR.length + ' · Premier Spine Patient Portal (example data)';
    Array.prototype.forEach.call(dots.children, function (d, j) { d.className = j === i ? 'on' : j < i ? 'done' : ''; });
    $('#tb-prev').disabled = i === 0; $('#tb-next').textContent = i === TOUR.length - 1 ? 'Finish' : 'Next';
    load(s.slot, s.pr, s.or); setSide(wide.matches ? 'both' : s.side); reveal(s.of); syncPlay(); runTimer();
  }
  function stopTour() { tour.on = false; tour.playing = false; stopTimer(); document.body.classList.remove('touring'); }
  $('#tb-prev').addEventListener('click', function () { if (tour.i > 0) { tour.playing = false; go('#/tour/' + tour.i); } });
  $('#tb-next').addEventListener('click', function () { tour.playing = false; if (tour.i < TOUR.length - 1) go('#/tour/' + (tour.i + 2)); else go('#/'); });
  $('#tb-play').addEventListener('click', function () { tour.playing = !tour.playing; syncPlay(); runTimer(); });
  $('#tb-exit').addEventListener('click', function () { go('#/'); });

  /* ---------- routing (#/, #/patient/<slot>, #/office/<slot>, #/tour/<n>) so Back works and a view can be linked ---------- */
  function go(h) { if (location.hash === h) route(); else location.hash = h; }
  function route() {
    var m = (location.hash || '#/').replace(/^#\/?/, '').split('/');
    if ((m[0] === 'patient' || m[0] === 'office') && m[1]) return openApp(m[0], decodeURIComponent(m[1]));
    if (m[0] === 'tour') { var i = Math.max(1, Math.min(TOUR.length, parseInt(m[1], 10) || 1)) - 1; return openTour(i); }
    stopTour(); show('start'); cur = null; $('#f-portal').removeAttribute('src'); $('#f-office').removeAttribute('src');
    document.title = 'DEMO · Premier Spine Patient Portal — example data only';
  }
  window.addEventListener('hashchange', route);
  route();
})();
