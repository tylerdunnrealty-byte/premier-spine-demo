/* Patient portal client.  Everything shown comes from the server API (or the in-browser mock in the static snapshot).
   Unsent text is held in memory only while you move around.  The only browser-storage item is the "Larger text" preference (see shared.js). */
(function () {
  'use strict';
  PS.app = 'portal';
  var h = PS.h, $ = PS.$, main = $('#main');
  var S = { me: null, rules: null, view: 'home', mem: { ask: '', msg: '', cat: '', cb: '' }, keys: {} };
  var CATS = [['scheduling', 'Scheduling or changing a visit'], ['refill', 'A prescription refill'], ['billing', 'A bill or insurance question'], ['medical', 'A medical question or symptom'], ['records', 'My records or documents'], ['other', 'Something else']];
  function keyFor(name, sig) { var k = S.keys[name]; if (!k || k.sig !== sig) k = S.keys[name] = { id: PS.uuid(), sig: sig }; return k.id; }
  function done(name) { delete S.keys[name]; }

  /* ---------- chrome (preview19: visible "Call us", one labelled Account menu, one "About this demo" sheet) ---------- */
  var dlg = $('#whocall'), acct = $('#account'), about = $('#about');
  function openWho(e) { PS.openSheet(dlg, e.currentTarget); }
  function openAbout(e) {
    var from = e && e.currentTarget; if (acct.open) { acct.close(); from = $('#account-btn'); }
    PS.openSheet(about, from);
  }
  $('#whocall-open-2').addEventListener('click', openWho);
  $('#wc-close').addEventListener('click', function () { dlg.close(); });
  [dlg, acct, about].forEach(function (d) { d.addEventListener('click', function (e) { if (e.target === d) d.close(); }); });
  ['#about-open', '#about-open-2', '#acct-about'].forEach(function (s) { $(s).addEventListener('click', openAbout); });
  $('#about-close').addEventListener('click', function () { about.close(); });
  if (PS.published) $('#about-snap').textContent = 'You are looking at the online demo: recordings of the working prototype, made with fictional patients. There is no server here, so nothing you do is sent or saved.';
  else if (PS.snapshot) $('#about-snap').textContent = 'You are looking at the static snapshot. There is no server here: anything you do is kept only in this browser tab, and it proves nothing about how the real server behaves.';
  PS.textSizeControl($('#acct-ts'), 'acct');
  $('#account-btn').addEventListener('click', function (e) {
    $('#acct-who').textContent = S.me ? 'Signed in as ' + S.me.user.name + (S.me.user.role === 'caregiver' ? ' (helper)' : '') + ' \u2014 a made-up demo person.' : 'Not signed in. This demo has no passwords.';
    $('#signout').hidden = !S.me; $('#acct-settings').hidden = !S.me; PS.openSheet(acct, e.currentTarget);
  });
  $('#acct-close').addEventListener('click', function () { acct.close(); });
  $('#acct-settings').addEventListener('click', function () { acct.close(); go('settings'); });
  $('#signout').addEventListener('click', function () { acct.close(); PS.api('POST', '/api/p/logout', {}).finally(function () { S.me = null; S.mem = { ask: '', msg: '', cat: '', cb: '' }; showLogin('You have signed out.'); }); });
  $('#nav').addEventListener('click', function (e) { var b = e.target.closest('button[data-view]'); if (b) go(b.dataset.view); });
  window.addEventListener('hashchange', function () { route(false); });

  function go(v) { location.hash = '#/' + v; }
  function setNav(view) {
    Array.prototype.forEach.call(document.querySelectorAll('#nav button'), function (b) { if (b.dataset.view === view) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
  }
  /* focus mode: the intake form hides the bottom tab bar, so the keyboard, the last field and Send are never covered */
  function chrome(on, focus) { $('#nav').hidden = !on || !!focus; document.body.classList.toggle('tabbar-on', !!on && !focus); document.body.classList.toggle('focusmode', !!focus); }
  function authFail(e) { if (e && e.status === 401) { S.me = null; showLogin('Your session ended. Please choose a demo person to sign in again.'); return true; } return false; }
  var TZ = 'America/Los_Angeles';
  function part(iso, o) { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: TZ }, o)).format(new Date(iso)); }

  /* ---------- sign in (fictional personas; no password, not real authentication) ---------- */
  function showLogin(msg) {
    chrome(false); PS.clear(main); document.title = 'DEMO · Sign in · Premier Spine patient portal (prototype)';
    var list = h('div', { 'aria-live': 'polite' }, h('p', { text: 'Loading demo people…' }));
    main.appendChild(h('div', {}, h('h1', { text: 'Demo sign-in: patient portal' }), h('p', { class: 'demonote', id: 'login-demo', text: 'DEMO \u2014 example data only, not a real patient portal. Every person below is made up. Do not enter real health information.' }),
      msg ? h('p', { class: 'istatus warn', role: 'status', text: msg }) : null,
      h('div', { class: 'card gold' }, h('h2', { text: 'Demo sign-in (fictional people)' }),
        h('p', { text: 'Pick a made-up person to see the portal as they would. There are no passwords in this demo.' }), list),
      h('div', { class: 'card' }, h('h2', { text: 'Can’t use the portal?' }), h('p', { text: 'Call (208) 770-3536 and we’ll do this with you over the phone.' }), h('a', { class: 'btn', href: 'tel:2087703536', text: 'Call (208) 770-3536' }))));
    PS.api('GET', '/api/personas?app=portal').then(function (r) {
      PS.clear(list);
      r.personas.forEach(function (p) {
        list.appendChild(h('button', { type: 'button', class: 'qitem', onclick: function () { login(p.key, list); } }, h('span', { class: 't' }, h('b', { text: p.name }), h('span', { class: 'chip', text: p.role === 'caregiver' ? 'Helper (limited access)' : 'Patient' })), h('span', { class: 'm', text: p.blurb })));
      });
    }).catch(function (e) { PS.clear(list); list.appendChild(h('p', { class: 'istatus bad', text: 'Could not load demo people: ' + PS.errText(e) })); });
  }
  function login(key, list) {
    PS.api('POST', '/api/login', { persona: key, app: 'portal' }).then(boot).catch(function (e) { list.appendChild(h('p', { class: 'istatus bad', role: 'alert', text: PS.errText(e) })); });
  }

  function boot() {
    return PS.api('GET', '/api/p/me').then(function (me) {
      S.me = me; chrome(true); $('#nav-messages').hidden = false;
      return PS.api('GET', '/api/p/rules').then(function (r) { S.rules = r; S.emRx = r.emergency_patterns.map(function (p) { try { return new RegExp(p, 'i'); } catch (e) { return null; } }).filter(Boolean); }).catch(function () { S.emRx = []; });
    }).then(function () { if (!location.hash || location.hash === '#/' ) location.hash = '#/home'; route(true); }).catch(function (e) { if (e.status === 401) showLogin(); else { PS.clear(main); main.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); } });
  }

  function route(first) {
    if (!S.me) return;
    var m = (location.hash || '#/home').replace(/^#\//, '').split('/'); var v = m[0] || 'home';
    S.view = v; setNav(v === 'thread' ? 'messages' : v === 'intake' ? 'records' : (v === 'assist' || v === 'content') ? 'home' : v); chrome(true, v === 'intake');
    if (v === 'messages' && m[1]) return renderThread(parseInt(m[1], 10));
    if (v === 'content') return renderContent(parseInt(m[1], 10) || 0);
    ({ home: renderHome, visits: renderVisits, records: renderRecords, messages: renderMessages, settings: renderSettings, intake: renderIntake, assist: renderAssist }[v] || renderHome)();
    if (!first) { main.focus({ preventScroll: false }); }
  }

  /* ---------- Home (preview19): three questions — What is happening? Do I need to do anything? How do I get help? ---------- */
  function loadHome(title, build) {
    document.title = 'DEMO · ' + title + ' · Premier Spine patient portal (prototype)';
    PS.api('GET', '/api/p/home').then(function (d) { PS.clear(main); S.home = d; build(d, S.me.user.role === 'patient', S.me.patient_name.split(' ')[0]); })
      .catch(function (e) { if (!authFail(e)) { PS.clear(main);   /* preview19 Prompt D: the error state offers a retry */
        var again = h('button', { type: 'button', class: 'btn', id: 'load-retry' }, 'Try again'); again.addEventListener('click', function () { again.disabled = true; again.textContent = 'Loading\u2026'; route(); });
        main.appendChild(h('div', { class: 'card', id: 'load-error' }, h('p', { class: 'istatus bad', role: 'alert', text: 'We couldn’t load this page: ' + PS.errText(e) + ' Nothing was changed. You can still call (208) 770-3536.' }), again)); } });
  }
  function helperNote(fn) {
    var canIntake = S.me.scopes && S.me.scopes.intake;
    return h('p', { class: 'istatus', id: 'helper-note', text: 'You are signed in as ' + S.me.user.name + ', a helper. You see only what ' + fn + ' chose to share.' + (canIntake ? ' You can fill in the intake form for ' + fn + '; they will be asked to confirm it.' : ' You can’t send messages or change anything.') });
  }
  function renderHome() {
    loadHome('Home', function (d, isP, fn) {
      main.appendChild(h('h1', { class: 'hello', text: isP ? 'Hello, ' + fn : 'Viewing what ' + fn + ' shared with you' }));
      if (!isP) main.appendChild(helperNote(fn));
      var sv = d.pipeline && d.pipeline.surgery, urgent = d.next_action && d.next_action.key === 'urgent';
      if (sv && sv.postop && !urgent && d.shared_scopes.status) { main.removeChild(main.lastChild); if (!isP) main.removeChild(main.lastChild); postopHome(d, isP, fn); return; }
      main.appendChild(statusCard(d, isP, fn));
      if (sv && !urgent && d.shared_scopes.status) {   /* before surgery: verified facts, who-does-what, approved instructions only */
        main.appendChild(surgeryFactsCard(sv)); main.appendChild(preopSplitCard(sv, isP, fn));
        if (d.shared_scopes.instructions) main.appendChild(approvedInstrCard(sv, 'preop-instr', 'Your pre-op instructions'));
      } else if (d.shared_scopes.status) { var ck = checklistCard(d, false); if (ck) main.appendChild(ck); }
      main.appendChild(helpCard(d, isP));
    });
  }
  function renderVisits() {
    loadHome('Visits', function (d, isP, fn) {
      main.appendChild(h('h1', { text: 'Visits' }));
      if (!isP) main.appendChild(helperNote(fn));
      if (d.shared_scopes.appointments) main.appendChild(apptCard(d));
      else main.appendChild(h('p', { class: 'istatus', text: 'Appointments have not been shared with you.' }));
      var sv = d.pipeline && d.pipeline.surgery;
      if (sv && sv.checkins && sv.checkins.length) main.appendChild(h('section', { class: 'card', 'aria-labelledby': 'h-vck' }, h('h2', { id: 'h-vck', text: 'Check-ins after surgery' }), checkinList(sv, 'v-checkins')));
      if (d.shared_scopes.instructions && d.instructions && d.instructions.length) {
        var sec = h('section', { class: 'card', 'aria-labelledby': 'h-ins' }, h('h2', { id: 'h-ins', text: 'Before your visit' }));
        d.instructions.forEach(function (i) { sec.appendChild(h('div', { class: 'field' }, h('h3', { text: i.title }), h('p', { text: i.body }), h('span', { class: 'tag', text: 'Source: ' + i.source }))); });
        main.appendChild(sec);
      }
      var team = h('section', { class: 'card', 'aria-labelledby': 'h-team' }, h('h2', { id: 'h-team', text: 'Your care team' }), h('div', { class: 'team' }));
      d.team.forEach(function (p) { team.lastChild.appendChild(h('div', { class: 'person' }, h('img', { src: p.photo, alt: '', width: '60', height: '64' }), h('div', {}, h('b', { text: p.name }), h('span', { class: 'small muted', text: p.role })))); });
      main.appendChild(team);
    });
  }
  function renderRecords() {
    loadHome('Records', function (d, isP, fn) {
      main.appendChild(h('h1', { text: 'Records' }));
      if (!isP) main.appendChild(helperNote(fn));
      if (!d.shared_scopes.status) { main.appendChild(h('p', { class: 'istatus', text: 'Status updates have not been shared with you.' })); return; }
      var ck = checklistCard(d, true); if (ck) main.appendChild(ck);
      var it = d.pipeline && d.pipeline.tracks.filter(function (t) { return t.key === 'intake'; })[0];
      if (it) main.appendChild(h('section', { class: 'card', 'aria-labelledby': 'h-rin' }, h('h2', { id: 'h-rin', text: 'Your intake form' }), h('p', { text: it.patient_text }),
        h('a', { class: 'btn ghost', href: '#/intake', id: 'rec-intake' }, PS.icon('clipboard'), it.done ? 'View your intake form' : 'Open your intake form')));
      main.appendChild(h('p', { class: 'fine', text: 'Copies of record files are not shown in this demo. Every person, office and document here is fictional.' }));
    });
  }

  /* --- What is happening (card 1). Everything here comes from the server: state, tracks, next_action, next_appointment. --- */
  var HEAD = { fit_review: 'Your referral is being reviewed', gathering: 'Getting ready for your first visit', ready: 'Ready to schedule your first visit', booked: 'Your first visit is booked',
    routed: 'Please call us about next steps', surgery: 'Your surgery is being planned', postop: 'Recovering after surgery' };
  var US = 'Premier Spine (our team)';
  function isYou(t, fn) { return t.waiting_on === 'You' || (fn && t.waiting_on === fn); }
  function factRow(dl, label, value, id, extra) { dl.appendChild(h('div', { class: 'fact', id: id || null }, h('dt', { text: label }), h('dd', {}, value, extra || null))); }
  function lastChecked(t) {   /* preview19 Prompt C: the Home card shows WHEN only; who checked it is under Details (team name, never a staff name or fax note) */
    return h('p', { class: 'small muted lastcheck' }, t.last_verified_at ? 'Last verified update: ' + PS.fmtDT(t.last_verified_at) : 'Last verified update: none yet \u2014 the office has not checked this since it was opened.');
  }
  /* records / insurance / review the OFFICE is handling: say so plainly, with the verified status and when it was last checked */
  function officeWaits(pv, fn) {
    if (!pv || pv.surgery) return [];
    return pv.tracks.filter(function (t) { return !t.done && t.waiting_on && !isYou(t, fn) && t.key !== 'appointment' && t.key !== 'safety'; });
  }
  function ownerOf(t) { return t.owner_team === 'Clinician' ? 'our clinical team' : t.owner_team && t.owner_team !== 'Office' ? 'our ' + t.owner_team.toLowerCase() + ' team' : 'our team'; }
  function waitsBox(ws, plain) {
    var owners = []; ws.forEach(function (t) { var o = plain ? 'our team' : ownerOf(t); if (owners.indexOf(o) < 0) owners.push(o); });
    var many = ws.length > 1, who = owners.join(' and ');
    return h('div', { class: 'owaits', id: 'hero-waits' }, h('p', { class: 'wlead' }, h('b', { text: 'We\u2019re waiting on' + (many ? ' ' + ws.length + ' things:' : ':') })),
      h('ul', { class: 'owlist' }, ws.map(function (t) {
        var party = t.waiting_on && t.waiting_on !== US && (t.label || '').indexOf(t.waiting_on) < 0 ? ' \u2014 from ' + t.waiting_on : '';
        return h('li', { id: 'hero-wait-' + String(t.key || t.id).replace(/[^a-z0-9]+/gi, '-') }, h('p', { class: 'wlabel' }, h('b', { text: t.label + party }), t.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null), lastChecked(t));
      })),
      h('p', { class: 'owner', id: 'hero-owner' }, h('b', { text: who.charAt(0).toUpperCase() + who.slice(1) + (owners.length > 1 || who === 'our team' ? ' are' : ' is') + ' handling ' + (many ? 'these' : 'this') + '.' }), ' You don\u2019t need to chase ' + (many ? 'them' : 'it') + '.'));
  }
  function statusCard(d, isP, fn) {
    var pv = d.pipeline, na = d.next_action, a = d.shared_scopes.appointments ? d.next_appointment : null, sv = pv && pv.surgery, st = PS.statusEl('na-status'), form = h('div', { id: 'na-form' });
    if (na && na.key === 'urgent') return urgentCard(na, st, pv);
    var state = pv ? pv.state : null, waits = officeWaits(pv, fn);
    var head = pv ? (HEAD[state] || pv.state_label) : (a ? 'Your next visit is booked' : 'Your care at Premier Spine');
    if (state === 'gathering' && waits.length) head = waits.some(function (t) { return /^records/.test(t.key); }) ? 'We\u2019re collecting your records' : waits.some(function (t) { return t.key === 'insurance'; }) ? 'We\u2019re checking with your insurance' : head;
    var card = h('section', { class: 'card hero status s-' + (state || 'basic'), 'aria-labelledby': 'h-na', id: 'hero' },
      h('p', { class: 'kicker', text: 'What\u2019s happening' }), h('h2', { id: 'h-na', text: head }));
    if (pv) card.appendChild(h('p', { class: 'lead', id: 'pipe-summary', text: pv.patient_summary }));
    var facts = h('dl', { class: 'facts', id: 'hero-facts' });
    if (a) {
      factRow(facts, 'When', PS.fmtDate(a.starts_at) + ' \u00b7 ' + PS.fmtTime(a.starts_at), 'f-when');
      factRow(facts, 'With', a.clinician, 'f-with'); factRow(facts, 'Where', a.location, 'f-where');
      factRow(facts, 'Status', a.confirmed ? h('span', { class: 'chip ok', text: '\u2713 You confirmed this visit' }) : h('span', { class: 'chip warn', text: 'Not confirmed yet' }), 'f-conf');
    } else if (sv && sv.surgery_at) factRow(facts, sv.postop ? 'Surgery date' : 'Planned surgery date', PS.fmtDate(sv.surgery_at) + ' ', 'surg-date', h('span', { class: 'tag', text: 'Example date' }));
    if (facts.firstChild) card.appendChild(facts);
    if (waits.length) card.appendChild(waitsBox(waits, false));
    else if (!pv && d.waiting_on && d.waiting_on.length) card.appendChild(waitsBox(d.waiting_on.filter(function (w) { return !/^Patient/.test(w.waiting_on || ''); }), true));
    card.appendChild(youDo(d, isP, fn, na, state, a, st, form));
    card.appendChild(form); card.appendChild(st); return card;
  }
  /* --- Do you need to do anything? One dominant action, only when the patient really has one. --- */
  function youDo(d, isP, fn, na, state, a, st, form) {
    var box = h('div', { class: 'youdo', id: 'youdo' }, h('h3', { id: 'h-youdo', text: 'Do you need to do anything?' }));
    function yes(title, why) { box.classList.add('yes'); box.appendChild(h('p', { class: 'ans', id: 'youdo-ans' }, h('b', { text: 'Yes \u2014 ' + title })));
      if (why) box.appendChild(h('p', { class: 'small', text: why })); }
    function no(text, why) { box.classList.add('no'); box.appendChild(h('p', { class: 'ans', id: 'youdo-ans' }, h('span', { class: 'nomark', 'aria-hidden': 'true' }, PS.icon('check')), h('span', {}, h('b', { text: 'No. ' }), text)));
      if (why) box.appendChild(h('p', { class: 'small muted', text: why })); }
    var key = na ? na.key : 'none';
    if (key === 'intake') { yes(isP ? 'finish your intake form' : 'help ' + fn + ' finish the intake form', na.why);
      box.appendChild(h('a', { class: 'btn big', href: '#/intake', id: 'na-intake' }, PS.icon('clipboard'), /saved as you go/.test(na.why) ? 'Continue your intake form' : 'Start your intake form')); }
    else if (key === 'attest') { yes('check the answers entered for you', na.why); box.appendChild(h('a', { class: 'btn big', href: '#/intake', id: 'na-attest' }, 'Check the answers')); }
    else if (key === 'imaging') { yes('tell us where your MRI was done', na.why);
      box.appendChild(h('button', { type: 'button', class: 'btn big', id: 'na-imaging', 'aria-expanded': 'false', 'aria-controls': 'na-form', onclick: function (e) { toggleForm(e.currentTarget, form, imagingForm); } }, 'Tell us where')); }
    else if (key === 'confirm') { yes('please confirm your visit', 'One tap lets the office know you\u2019re coming. If the time doesn\u2019t work, call us.');
      box.appendChild(h('button', { type: 'button', class: 'btn big', id: 'na-confirm', onclick: function (e) { confirmAppt(e.currentTarget, st); } }, 'Confirm I\u2019m coming')); }
    else if (key === 'checkin') { yes(na.title.replace(/^Day-(\d+) check-in: /, 'answer your day-$1 check-in: '), na.why); checkinForm(box); }
    else if (key === 'preop_ack') { yes('tell us you have your written pre-op instructions', 'Your surgical team gives them to you. One tap lets them know.');
      box.appendChild(h('button', { type: 'button', class: 'btn big', id: 'preop-ack', onclick: function (e) { preopAck(e.currentTarget, st); } }, 'I have my written instructions'));
      box.appendChild(h('p', { class: 'small' }, 'Don\u2019t have them? ', h('a', { href: 'tel:2087703536', text: 'Call us at (208) 770-3536' }), '.')); }
    else if (state === 'ready') {
      /* ready to schedule: there is no scheduling system, so we never show times. The action is to call, or to ask for a call. */
      box.classList.add('maybe');
      box.appendChild(h('p', { class: 'ans', id: 'youdo-ans' }, h('b', { text: 'Yes, when you\u2019re ready: ' }), 'call us to book your first visit. We can\u2019t show open times here.'));   /* preview19 Prompt C: no "we will call you" promise */
      box.appendChild(h('a', { class: 'btn big', href: 'tel:2087703536', id: 'ready-call', 'aria-label': 'Call us to book, (208) 770-3536' }, PS.icon('phone'), h('span', { class: 'btnstack' }, h('span', { text: 'Call us to book' }), h('span', { class: 'num', text: '(208) 770-3536' }))));
      if (isP && d.shared_scopes.messages) { var rs = PS.statusEl('ready-cb-status'), rb = h('button', { type: 'button', class: 'btn ghost', id: 'ready-cb' }, 'Ask us to call you instead');
        rb.addEventListener('click', function () { requestCallback(rb, rs, null); }); box.appendChild(h('div', { class: 'row' }, rb)); box.appendChild(rs); }
    }
    else if (!na) no('There is nothing for you to do in the portal right now.', null);
    else if (/^Nothing needed/.test(na.title)) no(a && a.confirmed ? 'You\u2019re all set for this visit.' : 'Nothing is needed from you right now.', state === 'gathering' || state === 'fit_review' ? 'We\u2019ll show it here if that changes.' : null);
    else { box.classList.add('no'); box.appendChild(h('p', { class: 'ans', id: 'youdo-ans' }, h('b', { text: na.title + '. ' }), na.why)); }
    return box;
  }
  function urgentCard(na, st, pv) {
    var card = h('section', { class: 'card hero urgent', role: 'alert', 'aria-labelledby': 'h-na', id: 'hero' }, h('div', { class: 'heroicon' }, PS.icon('alert')), h('p', { class: 'kicker', text: 'Please read now' }), h('h2', { id: 'h-na', text: na.title }), h('p', { text: na.why }),
      pv ? h('p', { class: 'small', id: 'pipe-summary', text: pv.patient_summary }) : null);
    card.appendChild(h('div', { class: 'row' }, h('a', { class: 'btn danger big', href: 'tel:911', text: 'Call 911' }), h('a', { class: 'btn', href: 'tel:2087703536', text: 'Call the office (208) 770-3536' })));
    card.appendChild(h('p', { class: 'fine', text: 'MEDICAL COPY \u2014 example wording pending Dr. Yakel\u2019s review. This portal is not a clinical triage system.' }));
    card.appendChild(st); return card;
  }
  /* --- compact checklist: items run in parallel, so no connected line; the detail (fax history, who has it) is one tap away --- */
  function checklistRows(d) {
    var pv = d.pipeline, fn = S.me.patient_name.split(' ')[0], sv = pv && pv.surgery;
    if (sv && sv.postop && sv.checkins && sv.checkins.length) return sv.checkins.map(function (k) {   /* after surgery the check-ins ARE the checklist */
      var m = { answered: ['done', 'Answered'], sent: ['you', S.me.user.role === 'patient' ? 'Your turn' : 'Waiting on ' + fn], scheduled: ['later', 'Coming up ' + PS.fmtDay(k.due_at)], missed: ['wait', 'Missed \u2014 call us if you need us'] }[k.status] || ['later', k.status];
      return { key: 'checkin-' + k.day, label: 'Day ' + k.day + ' check-in', s: m[0], txt: m[1] };
    });
    if (pv) return pv.tracks.map(function (t) {
      var s, txt;
      if (t.done) { s = 'done'; txt = 'Done'; }
      else if (isYou(t, fn)) { s = 'you'; txt = S.me.user.role === 'patient' ? 'Your turn' : 'Waiting on ' + fn; }
      else if (t.key === 'appointment' && pv.state === 'ready') { s = 'you'; txt = 'Ready to book'; }
      else if (t.waiting_on === US) { s = 'wait'; txt = 'Our team is on it'; }
      else if (t.waiting_on) { s = 'wait'; txt = (t.label || '').indexOf(t.waiting_on) >= 0 ? 'Waiting on reply' : 'Waiting on ' + t.waiting_on; }
      else { s = 'later'; txt = 'Later'; }
      return { key: t.key, label: t.label, s: s, txt: txt };
    });
    var steps = trackerSteps(d); if (!steps) return null;
    return steps.map(function (x) { return { key: x.l.toLowerCase(), label: x.l, s: x.s === 'done' ? 'done' : x.s === 'current' ? 'wait' : 'later', txt: x.s === 'done' ? 'Done' : x.s === 'current' ? 'In progress' : 'Later' }; });
  }
  var CKICON = { done: 'check', you: 'chevron', wait: 'clock', later: null };
  function checklistCard(d, full) {
    var pv = d.pipeline, sv = pv && pv.surgery, rows = checklistRows(d); if (!rows) return null;
    var n = rows.filter(function (r) { return r.s === 'done'; }).length;
    var sec = h('section', { class: 'card', 'aria-labelledby': 'h-pipe', id: 'pipe' }, h('h2', { id: 'h-pipe', text: sv ? (sv.postop ? 'Your check-ins after surgery' : 'Your surgery checklist') : 'Your checklist' }),
      h('p', { class: 'small muted', id: 'ck-count', text: n + ' of ' + rows.length + ' done. Items can finish in any order.' }));
    sec.appendChild(h('ul', { class: 'checklist', id: 'checklist', 'aria-labelledby': 'h-pipe' }, rows.map(function (r) {
      return h('li', { class: 'ck s-' + r.s, id: 'ck-' + r.key.replace(/[^a-z0-9]+/gi, '-') }, h('span', { class: 'ckmark', 'aria-hidden': 'true' }, CKICON[r.s] ? PS.icon(CKICON[r.s]) : null),
        h('span', { class: 'cklabel', text: r.label }), h('span', { class: 'ckstate', text: r.txt }));
    })));
    /* details: who is handling each item, next follow-up, last verified update, fax / reminder history */
    var more = h('details', { class: 'more', id: 'pipe-more' }, h('summary', { text: full ? 'Details for each item' : 'Details: who is handling each item' }));
    if (full) more.open = true;
    if (pv) {
      more.appendChild(h('p', { class: 'small', id: 'pipe-why', text: 'This answers the usual phone questions: what we\u2019re waiting on, who has it, and what happens next.' }));
      if (sv) more.appendChild(h('p', { class: 'istatus', id: 'surg-note', text: sv.instruction_note }));
      if (sv && sv.postop) more.appendChild(h('h3', { text: 'Before your surgery' }));
      var open = pv.tracks.filter(function (t) { return !t.done && t.waiting_on; });
      if (open.length) { more.appendChild(h('h3', { text: 'What we\u2019re waiting on' })); more.appendChild(h('ul', { class: 'plain tracks', id: 'pipe-waiting' }, open.map(trackLi))); }
      var rest = pv.tracks.filter(function (t) { return t.done || !t.waiting_on; });
      if (rest.length) { if (!(sv && sv.postop)) more.appendChild(h('h3', { text: open.length ? 'Everything else' : 'Checklist' })); more.appendChild(h('ul', { class: 'plain tracks', id: 'pipe-rest' }, rest.map(trackLi))); }
    } else more.appendChild(waitingList(d));
    var hasSim = Array.prototype.some.call(more.querySelectorAll('.tag'), function (x) { return /Simulated/.test(x.textContent); });
    more.appendChild(h('p', { class: 'fine' }, 'Lines change only when a person on our team, or a recorded event, changes them. ' + (hasSim ? 'Items marked \u201cSimulated\u201d did not really happen. ' : ''), h('button', { type: 'button', class: 'linkbtn', onclick: openAbout }, 'About this demo')));
    sec.appendChild(more);
    return sec;
  }
  /* package-style tracker: Referral, Records, Insurance, Intake, Visit (surgery: Consult, Pre-op, Surgery, Recovery) */
  function trackerSteps(d) {
    var pv = d.pipeline, st = d.stage || [];
    if (pv && pv.surgery) {
      var sv = pv.surgery, items = sv.items || [], n = items.filter(function (i) { return i.done; }).length;
      return [{ l: 'Consult', s: 'done' }, { l: 'Pre-op ' + n + '/' + items.length, s: sv.postop ? 'done' : 'current' }, { l: 'Surgery', s: sv.postop ? 'done' : 'todo' }, { l: 'Recovery', s: sv.postop ? 'current' : 'todo' }];
    }
    if (pv && st.length === 5) {
      var appt = pv.tracks.filter(function (t) { return t.key === 'appointment'; })[0], L = ['Referral', 'Records', 'Insurance', 'Intake', 'Visit'];
      return st.map(function (x, i) { var s = i < 4 ? x.state : (appt && appt.done ? 'done' : (x.state === 'done' ? 'current' : 'todo')); return { l: L[i], s: s, stop: pv.state === 'urgent' && s === 'current' }; });
    }
    if (st.length === 5) {
      var rec = st[1].state === 'done' && st[2].state === 'done' ? 'done' : (st[1].state === 'current' || st[2].state === 'current' ? 'current' : 'todo');
      return [{ l: 'Referral', s: st[0].state }, { l: 'Records', s: rec }, { l: 'Intake', s: st[3].state }, { l: 'Visit', s: st[4].state === 'done' ? 'done' : st[4].state }];
    }
    return null;
  }
  function apptCard(d) {
    var a = d.next_appointment, sv = d.pipeline && d.pipeline.surgery;
    var sec = h('section', { class: 'card', 'aria-labelledby': 'h-appt', id: 'appt-card' }, h('p', { class: 'kicker', text: a ? 'Next appointment' : sv ? 'Your surgery (example)' : 'Next appointment' }), h('h2', { id: 'h-appt', class: 'sr', text: 'Your next appointment' }));
    function cal(iso) { return h('div', { class: 'cal', 'aria-hidden': 'true' }, h('b', { text: part(iso, { month: 'short' }) }), h('span', { text: part(iso, { day: 'numeric' }) })); }
    if (a) sec.appendChild(h('div', { class: 'apptline' }, cal(a.starts_at), h('div', {},
      h('p', { class: 'bigdate', text: PS.fmtDate(a.starts_at) + ' · ' + PS.fmtTime(a.starts_at) }),
      h('p', {}, h('b', { text: a.clinician }), ' · ' + a.kind), h('p', { class: 'muted', text: a.location }),
      h('p', {}, a.confirmed ? h('span', { class: 'chip ok', text: '\u2713 You confirmed this visit' }) : h('span', { class: 'chip warn', text: 'Not confirmed yet' })),
      h('p', { id: 'appt-change', text: (a.confirmed || location.hash.indexOf('visits') < 0 ? '' : 'You can confirm this visit on Home. ') + 'To change or cancel, call (208) 770-3536.' }),   /* preview19 Prompt D */
      h('a', { class: 'btn ghost sm', target: '_blank', rel: 'noopener', href: 'https://www.google.com/maps/search/?api=1&query=850+W+Ironwood+Dr+Coeur+d%27Alene+ID' }, PS.icon('map'), 'Get directions (opens Google Maps)'))));
    else if (sv) sec.appendChild(h('div', { class: 'apptline' }, cal(sv.surgery_at), h('div', {}, h('p', { class: 'bigdate', text: PS.fmtDate(sv.surgery_at) }),
      h('p', {}, h('span', { class: 'tag', text: 'Example date' }), ' ', sv.postop ? 'Your surgery date.' : 'Planned surgery date.'),
      h('p', { class: 'small muted', text: 'Questions about times or follow-up visits: call (208) 770-3536.' }))));
    else { var pv = d.pipeline; sec.appendChild(h('p', { id: 'appt-none', text: pv && pv.state === 'ready' ? 'No visit is booked yet. You’re ready: call us at (208) 770-3536 to book, or ask us to call you from Home.' : pv ? 'No visit is booked yet. We’ll book your first visit once the items on your checklist are done.' : 'No visit is booked yet. To book one, call (208) 770-3536.' })); }
    return sec;
  }
  function preopAck(btn, st) {
    btn.disabled = true;
    PS.api('POST', '/api/p/preop/instructions', {}, { key: keyFor('preop', 'x') }).then(function () { done('preop'); PS.status(st, 'Thank you. Your surgical team can see that you have the instructions.', 'ok'); setTimeout(renderHome, 1200); })
      .catch(function (e) { btn.disabled = false; if (!authFail(e)) PS.status(st, PS.errText(e), 'bad'); });
  }
  /* ---------- preview19 Prompt B: before / after surgery ---------- */
  var NOT_ADDED = 'Not added yet';
  function surgeryFactsCard(sv) {
    var pr = sv.procedure || {}, dl = h('dl', { class: 'facts', id: 'surg-facts' });
    factRow(dl, 'Procedure', (pr.label || NOT_ADDED) + ' ', 'sf-proc', h('span', { class: 'tag', text: 'Example' }));
    factRow(dl, 'Date', pr.date ? PS.fmtDate(pr.date) + ' ' : NOT_ADDED, 'sf-date', pr.date ? h('span', { class: 'tag', text: 'Example date' }) : null);
    factRow(dl, 'Date checked', pr.date_verified ? 'Confirmed by ' + (pr.verified_by || 'our team') + ' \u00b7 ' + PS.fmtDT(pr.verified_at) : 'Not confirmed with you yet', 'sf-ver');
    factRow(dl, 'Surgeon', pr.surgeon || NOT_ADDED, 'sf-surgeon'); factRow(dl, 'Where', pr.location || NOT_ADDED, 'sf-where'); factRow(dl, 'Arrival time', pr.arrival_time || NOT_ADDED, 'sf-arrive');
    return h('section', { class: 'card', id: 'surg-card', 'aria-labelledby': 'h-surg' }, h('h2', { id: 'h-surg', text: 'Your surgery' }), dl,
      h('p', { class: 'small muted', text: 'Only details your team has entered are shown. \u201cNot added yet\u201d means nobody has entered it \u2014 we never guess.' }));
  }
  function preopSplitCard(sv, isP, fn) {
    var by = {}; sv.items.forEach(function (i) { by[i.key] = i; });
    function li(i, mine) {
      var chip = i.done ? ['ok', '\u2713 Done'] : mine ? ['warn', isP ? 'Your turn' : 'Waiting on ' + fn] : ['info', i.status === 'todo' ? 'Not started' : 'In progress'];
      return h('li', { id: 'po-' + i.key }, h('p', {}, h('b', { text: i.label }), ' ', h('span', { class: 'chip ' + chip[0], text: chip[1] }), i.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null),
        i.done ? null : h('p', { class: 'small', text: i.patient_text }), mine ? null : h('p', { class: 'small muted', text: 'Handled by: ' + i.owner_team }));
    }
    var you = sv.patient_tasks.map(function (k) { return by[k]; }).filter(Boolean), team = sv.team_tasks.map(function (k) { return by[k]; }).filter(Boolean);
    return h('section', { class: 'card', id: 'preop-split', 'aria-labelledby': 'h-split' }, h('h2', { id: 'h-split', text: 'Before surgery: who does what' }),
      h('h3', { text: isP ? 'Your tasks' : fn + '\u2019s tasks' }), you.length ? h('ul', { class: 'plain tracks', id: 'preop-you' }, you.map(function (i) { return li(i, true); })) : h('p', { id: 'preop-you', text: 'Nothing for you right now.' }),
      h('h3', { text: 'What our team is handling' }), h('ul', { class: 'plain tracks', id: 'preop-team' }, team.map(function (i) { return li(i, false); })),
      h('p', { class: 'small', id: 'preop-noclear', text: 'This list tracks paperwork. Ticks here do not mean you are cleared or ready for surgery \u2014 only your surgical team decides that.' }));
  }
  function approvedInstrCard(sv, id, title) {
    var ai = sv.approved_instructions || { status: 'missing', records: [] }, sec = h('section', { class: 'card', id: id, 'aria-labelledby': id + '-h', 'data-status': ai.status }, h('h2', { id: id + '-h', text: title }));
    if (ai.status === 'missing') { sec.appendChild(h('p', { id: id + '-missing', class: 'lead', text: 'Your team has not added these instructions yet.' }));
      sec.appendChild(h('p', { class: 'small', text: 'Questions? Call (208) 770-3536. This portal does not give medical advice.' })); return sec; }
    if (ai.status === 'conflict') sec.appendChild(h('p', { class: 'istatus warn', id: id + '-warn', text: 'There are two approved versions that don\u2019t match. Please check with the team before relying on either. Call (208) 770-3536.' }));
    if (ai.status === 'stale') sec.appendChild(h('p', { class: 'istatus warn', id: id + '-warn', text: 'These were due for review and haven\u2019t been re-approved, so they may be out of date. Please check with the team.' }));
    ai.records.forEach(function (r, i) {
      sec.appendChild(h('div', { class: 'field' }, h('h3', { text: r.title }), r.example ? h('p', { class: 'tag', text: 'Example \u2014 fictional' }) : null,
        ai.status === 'verified' ? h('blockquote', { class: 'approved', id: id + '-body', text: r.body }) : null,
        h('p', { class: 'small muted', text: 'Version ' + r.version + ' \u00b7 approved ' + PS.fmtDT(r.approved_at) + ' \u00b7 ' + r.approved_by }),
        h('a', { class: 'btn ghost sm', href: r.href, id: id + '-orig-' + i, text: 'Open the original' })));
    });
    return sec;
  }
  function urgentHelpBox() {   /* static: never depends on anything being sent */
    return h('section', { class: 'card urgenthelp', id: 'ck-911', 'aria-labelledby': 'h-911' }, h('h2', { id: 'h-911', text: 'Urgent help' }),
      h('p', { text: 'In an emergency, call 911. For an urgent problem after surgery, call the office.' }),
      h('div', { class: 'row' }, h('a', { class: 'btn danger', href: 'tel:911', id: 'ck-call911' }, 'Call 911'), h('a', { class: 'btn ghost', href: 'tel:2087703536', id: 'ck-calloffice' }, PS.icon('phone'), 'Call the office')),
      h('p', { class: 'fine', text: 'MEDICAL COPY \u2014 example wording pending Dr. Yakel\u2019s review.' }));
  }
  function receiptBox(rc, emergency, guidance, cb) {
    var reached = !!rc.task_ref;
    return h('div', { class: 'receipt', id: 'ck-receipt', tabindex: '-1', 'aria-labelledby': 'ck-receipt-h' },
      h('h3', { id: 'ck-receipt-h' }, PS.icon('check'), reached ? 'Your check-in reached the care team' : 'Your check-in is saved'),
      h('p', { id: 'ck-receipt-ref' }, h('b', { text: 'Reference ' + rc.ref }), ' \u00b7 received by the server ' + PS.fmtDT(rc.sent_at)),
      h('p', {}, h('span', { class: 'muted', text: 'You answered: ' }), rc.answer_label),
      rc.note ? h('div', {}, h('p', { class: 'muted small', text: 'Your words, exactly as sent:' }), h('blockquote', { class: 'draft', id: 'ck-receipt-note', text: rc.note })) : null,
      h('p', { id: 'ck-receipt-level' }, h('b', { text: 'What happened: ' }), rc.level_label + (reached ? ' (task ' + rc.task_ref + (rc.routed_to ? ', ' + rc.routed_to : '') + ')' : '') + '.'),
      emergency ? h('p', { class: 'istatus bad', role: 'alert', text: guidance }) : null,
      h('p', { class: 'small', id: 'ck-receipt-cb', text: cb ? cb : (reached ? 'No call-back time has been promised. If it can\u2019t wait, call (208) 770-3536, or 911 in an emergency.' : 'It did not create a task for the care team. If you need anyone, call (208) 770-3536.') }));
  }
  function checkinCard(sv, isP, fn) {
    var k = sv.checkin_due, sec = h('section', { class: 'card hero', id: 'ck-card', 'aria-labelledby': 'h-ck' });
    if (!k) {
      sec.appendChild(h('h2', { id: 'h-ck', text: 'No check-in is due right now' }));
      sec.appendChild(h('p', { text: sv.next_checkin ? 'Next check-in: day ' + sv.next_checkin.day + ', ' + PS.fmtDay(sv.next_checkin.due_at) + '. You can still call or message the team any time.' : 'You can call or message the team any time.' }));
      return sec;
    }
    sec.appendChild(h('h2', { id: 'h-ck', text: 'Day ' + k.day + ': how are you doing?' }));
    if (!isP) { sec.appendChild(h('p', { text: 'Waiting for ' + fn + ' to answer. Only ' + fn + ' can send it.' })); return sec; }
    checkinForm(sec, sv);
    return sec;
  }
  function checkinForm(card, sv) {
    sv = sv || (S.home && S.home.pipeline && S.home.pipeline.surgery); var k = sv && sv.checkin_due; if (!k) return;
    var fs = h('fieldset', { id: 'ck-form' }, h('legend', { class: 'sr', text: 'How are you doing today?' }));
    [['ok', 'I\u2019m doing okay'], ['question', 'I have a question'], ['concern', 'Something worries me']].forEach(function (o) {
      fs.appendChild(h('label', { class: 'choice', for: 'ck-' + o[0] }, h('input', { type: 'radio', name: 'ck', value: o[0], id: 'ck-' + o[0] }), o[1]));
    });
    var note = h('textarea', { id: 'ck-note', rows: '2', 'aria-describedby': 'ck-hint ck-c' }), cnt = h('p', { class: 'counter', id: 'ck-c' }), em = h('div', { id: 'ck-em', role: 'alert', class: 'istatus' });
    var send = h('button', { type: 'button', class: 'btn big', id: 'ck-send' }, 'Send my check-in'), st = PS.statusEl('ck-st'), up = PS.bindCounter(note, cnt, 1000, send);
    wireEmergency(note, em);
    var box = h('div', { id: 'ck-box' }, fs, h('div', { class: 'field' }, h('label', { for: 'ck-note', text: 'In your own words \u2014 needed for a question or a worry' }), note, cnt), em, h('div', { class: 'row' }, send),
      h('p', { class: 'small muted', id: 'ck-hint', text: 'Sent exactly as you write it. Nobody sees it instantly.' + (sv.callback_promise ? ' ' + sv.callback_promise : '') }), st);
    send.addEventListener('click', function () {
      var c = fs.querySelector('input[name=ck]:checked'); if (!c) { PS.status(st, 'Please choose one of the answers.', 'bad'); return; }
      if (c.value !== 'ok' && !note.value.trim()) { PS.status(st, 'Please add a few words, so the care team knows what it is about.', 'bad'); note.focus(); return; }
      if (!up()) { PS.status(st, 'This is too long. Please shorten it.', 'bad'); return; }
      var all = box.querySelectorAll('input,textarea'); Array.prototype.forEach.call(all, function (x) { x.disabled = true; });
      send.disabled = true; send.setAttribute('aria-busy', 'true'); send.dataset.busy = '1'; send.textContent = 'Sending\u2026'; PS.status(st, 'Sending\u2026 not sent yet.', '');
      PS.api('POST', '/api/p/checkin/' + k.id, { answer: c.value, note: note.value }, { key: keyFor('ck' + k.id, c.value + '\u0000' + note.value) }).then(function (r) {
        if (!r || !r.receipt || !r.receipt.ref) throw Object.assign(new Error('The server did not confirm the check-in.'), { status: 0 });
        done('ck' + k.id); PS.clear(box); var rb = receiptBox(r.receipt, r.emergency, r.emergency_guidance, r.callback_promise); box.appendChild(rb); rb.focus({ preventScroll: false });
        if (S.home) loadHistory();
      }).catch(function (e) {
        if (authFail(e)) return;
        Array.prototype.forEach.call(all, function (x) { x.disabled = false; });
        send.disabled = false; send.removeAttribute('aria-busy'); send.dataset.busy = ''; send.textContent = 'Try again';
        PS.status(st, (e.status === 422 ? PS.errText(e) + ' ' : 'Not sent. ' + (e.status ? PS.errText(e) + ' ' : 'We couldn\u2019t reach the server. ')) + 'Your answers are still here. Press \u201cTry again\u201d, or call (208) 770-3536. In an emergency, call 911.', 'bad');
        st.appendChild(h('div', { class: 'row' }, h('a', { class: 'btn danger sm', href: 'tel:911', id: 'ck-fail-911' }, 'Call 911'), h('a', { class: 'btn ghost sm', href: 'tel:2087703536' }, 'Call the office')));
        st.setAttribute('data-failed', '1'); st.setAttribute('tabindex', '-1'); st.focus();
      });
    });
    card.appendChild(box);
  }
  function historyCard(sv) {
    var sec = h('section', { class: 'card', id: 'ck-history-card', 'aria-labelledby': 'h-ckh' }, h('h2', { id: 'h-ckh', text: 'Your check-ins' }));
    var done_ = (sv.checkins || []).filter(function (k) { return k.status === 'answered'; });
    if (!done_.length) { sec.appendChild(h('p', { id: 'ck-history', text: 'None sent yet.' })); return sec; }
    sec.appendChild(h('ul', { class: 'plain facts', id: 'ck-history' }, done_.map(function (k) {
      var rc = k.receipt || {};
      return h('li', { id: 'ckh-' + k.day }, h('p', {}, h('b', { text: 'Day ' + k.day }), ' \u00b7 ' + PS.fmtDT(k.answered_at) + (rc.ref ? ' \u00b7 Ref ' + rc.ref : '')),
        h('p', { text: 'You answered: ' + (rc.answer_label || k.answer) }), k.note ? h('blockquote', { class: 'draft', text: k.note }) : null,
        rc.level_label ? h('p', { class: 'small', text: rc.level_label + (rc.task_ref ? ' \u00b7 task ' + rc.task_ref + (rc.task_status ? ' \u00b7 ' + rc.task_status : '') : '') }) : null);
    })));
    return sec;
  }
  function loadHistory() {
    PS.api('GET', '/api/p/home').then(function (d) { var sv = d.pipeline && d.pipeline.surgery, old = $('#ck-history-card'); if (sv && old) old.replaceWith(historyCard(sv)); }).catch(function () {});
  }
  function postopHome(d, isP, fn) {
    var sv = d.pipeline.surgery;
    main.appendChild(h('h1', { class: 'hello', text: isP ? 'Hello, ' + fn : 'Viewing what ' + fn + ' shared with you' }));
    if (!isP) main.appendChild(helperNote(fn));
    main.appendChild(checkinCard(sv, isP, fn));
    main.appendChild(urgentHelpBox());
    main.appendChild(helpCard(d, isP));
    if (isP) main.appendChild(historyCard(sv));
    main.appendChild(h('p', { class: 'small', id: 'pipe-summary', text: d.pipeline.patient_summary }));
    main.appendChild(approvedInstrCard(sv, 'postop-instr', 'Your after-surgery instructions'));
    var ck = checklistCard(d, false); if (ck) main.appendChild(ck);
  }
  function toggleForm(btn, box, build) {
    var open = btn.getAttribute('aria-expanded') === 'true'; btn.setAttribute('aria-expanded', open ? 'false' : 'true'); PS.clear(box);
    if (!open) { build(box); var f = box.querySelector('input,textarea'); if (f) f.focus(); }
  }
  function confirmAppt(btn, st) {
    if (btn.disabled) return; btn.disabled = true;   /* preview19 Prompt D: disable at the first click (a double-click sent two requests) */
    PS.api('GET', '/api/p/home').then(function (d) {
      return PS.api('POST', '/api/p/appointments/' + d.next_appointment.id + '/confirm', {}, { key: keyFor('confirm', d.next_appointment.id) });
    }).then(function () { done('confirm'); PS.status(st, 'Thank you. The office can see that you confirmed.', 'ok'); setTimeout(renderHome, 900); }).catch(function (e) { btn.disabled = false; if (!authFail(e)) PS.status(st, 'That did not go through: ' + PS.errText(e), 'bad'); });
  }
  function imagingForm(box) {
    var inp = h('input', { type: 'text', id: 'im-fac', autocomplete: 'off', maxlength: '120' }), st = PS.statusEl('im-status'), send = h('button', { type: 'button', class: 'btn' }, 'Send to the office');
    send.addEventListener('click', function () {
      send.disabled = true;
      PS.api('POST', '/api/p/imaging', { facility: inp.value }, { key: keyFor('imaging', inp.value) }).then(function () { done('imaging'); PS.status(st, 'Thank you. The office will ask that place for your report. We’ll show the status under “What we’re waiting on”.', 'ok'); setTimeout(renderHome, 1200); })
        .catch(function (e) { send.disabled = false; if (!authFail(e)) PS.status(st, PS.errText(e), 'bad'); });
    });
    box.appendChild(h('div', {}, h('div', { class: 'field' }, h('label', { for: 'im-fac', text: 'Name of the place where your MRI was done' }), inp), send, st));
  }

  /* --- How do I get help? Always easy to find, never the biggest button. --- */
  function requestCallback(btn, st, noteEl) {
    var note = noteEl ? noteEl.value : '';
    btn.dataset.busy = '1'; btn.disabled = true;
    PS.api('POST', '/api/p/callback', { note: note }, { key: keyFor('cb', note) }).then(function (r) {
      done('cb'); S.mem.cb = ''; if (noteEl) noteEl.value = '';
      var t = r.task; PS.status(st, (r.created ? 'Your call-back request is in. ' : 'You already have a call-back request open, so we did not add a second one. ') + 'Status: ' + t.status_text + '. ' + (t.reply_target || 'The office has not set a target time for call-backs, so we can’t promise one. If it can’t wait, call (208) 770-3536.'), 'ok');
    }).catch(function (e) { if (!authFail(e)) PS.status(st, 'Your request did not go through: ' + PS.errText(e) + ' Please call (208) 770-3536.', 'bad'); }).finally(function () { btn.dataset.busy = ''; btn.disabled = false; });
  }
  function helpCard(d, isP) {
    var st = PS.statusEl('cb-status'), can = d.shared_scopes.messages && isP;
    var note = h('input', { type: 'text', id: 'cb-note', autocomplete: 'off', maxlength: '300', value: S.mem.cb });
    note.addEventListener('input', function () { S.mem.cb = note.value; });
    var cb = h('button', { type: 'button', class: 'btn ghost', id: 'cb-btn' }, PS.icon('phone'), 'Request a call back');
    cb.addEventListener('click', function () { requestCallback(cb, st, note); });
    return h('section', { class: 'card help', 'aria-labelledby': 'h-reach', id: 'help' }, h('h2', { id: 'h-reach', text: 'Need help?' }),
      h('div', { class: 'helpgrid' }, h('a', { class: 'btn ghost', href: 'tel:2087703536', id: 'help-call' }, PS.icon('phone'), 'Call us \u00b7 (208) 770-3536'),
        can ? h('a', { class: 'btn ghost', href: '#/messages', id: 'help-msg' }, PS.icon('messages'), 'Send a message') : null, can ? cb : null,
        h('a', { class: 'btn ghost', href: '#/assist', id: 'help-assist' }, PS.icon('clipboard'), 'Ask about your visit')),
      can ? h('details', { class: 'more', id: 'cb-more' }, h('summary', { text: 'Add a best time or number for the call back (optional)' }), h('div', { class: 'field' }, h('label', { for: 'cb-note', text: 'Best time or number to call' }), note)) : null, st,
      h('p', { class: 'small' }, 'Can’t use the portal? Call (208) 770-3536 and we’ll do this with you. In an emergency, call 911.'),
      h('p', { class: 'small whorow' }, h('button', { type: 'button', class: 'linkbtn', onclick: openWho }, 'Who do I call?')));
  }
  function waitingList(d) {
    if (!d.waiting_on || !d.waiting_on.length) return h('p', { text: 'Nothing is waiting on anyone right now. If that changes, it will show here.' });
    return h('ul', { class: 'plain', id: 'pipe-waiting' }, d.waiting_on.map(function (w) {
      return h('li', {}, h('p', {}, h('b', { text: w.label }), ' ', h('span', { class: 'chip ' + PS.chipFor(w.status), text: PS.statusMark[w.status] + w.status })),
        w.waiting_on ? h('p', { class: 'small', text: 'Waiting for: ' + w.waiting_on }) : null,
        w.next_check ? h('p', { class: 'small', text: 'We plan to check again by ' + PS.fmtDay(w.next_check) + '.' }) : null, lastChecked(w));
    }));
  }

  function checkinList(sv, id) {
    return h('ul', { class: 'plain tracks', id: id }, sv.checkins.map(function (k) {
      var lab = { scheduled: 'Coming up ' + PS.fmtDay(k.due_at), sent: 'Waiting for your answer', answered: 'Answered \u2014 thank you', missed: 'Missed \u2014 call (208) 770-3536 if you need us' }[k.status] || k.status;
      return h('li', { class: 'track ' + (k.status === 'answered' ? 'done' : k.status === 'sent' ? 'wait' : 'todo') }, h('p', {}, h('span', { class: 'tmark', 'aria-hidden': 'true' }, k.status === 'answered' ? PS.icon('check') : k.status === 'sent' ? PS.icon('clock') : ''), h('b', { text: 'Day ' + k.day + ' check-in' }), ' ', h('span', { class: 'chip' + (k.status === 'answered' ? ' ok' : k.status === 'sent' ? ' warn' : ''), text: lab })));
    }));
  }
  function trackLi(t) {
    return h('li', { class: 'track ' + (t.done ? 'done' : (t.waiting_on ? 'wait' : 'todo')) },
      h('p', {}, h('span', { class: 'tmark', 'aria-hidden': 'true' }, t.done ? PS.icon('check') : (t.waiting_on ? PS.icon('clock') : '')), h('b', { text: t.label }), ' ',
        t.done ? h('span', { class: 'chip ok', text: 'Done' }) : (t.waiting_on ? h('span', { class: 'chip warn', text: 'Waiting on: ' + t.waiting_on }) : h('span', { class: 'chip', text: 'Later' })),
        t.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null),
      h('p', { class: 'small', text: t.patient_text }),
      (!t.done && t.waiting_on) ? h('p', { class: 'small who' }, h('b', { text: 'Who\u2019s handling it: ' }), (t.owner_team ? t.owner_team + ' at Premier Spine' : 'Premier Spine team')) : null,
      (!t.done && t.next_step) ? h('p', { class: 'small nextstep', text: t.next_step }) : null,
      (!t.done && t.next_check) ? h('p', { class: 'small', text: 'We plan to check again by ' + PS.fmtDay(t.next_check) + '.' }) : null,
      (!t.done && t.waiting_on) ? h('p', { class: 'small muted', text: t.last_verified_at ? 'Last verified update: ' + PS.fmtDT(t.last_verified_at) + ' \u00b7 ' + t.last_verified_source : 'Last verified update: none yet.' }) : null);
  }

  /* ---------- Tell-us-once intake (preview19): short steps, one progress indicator, inline errors, review, clear result ----------
     Answers are autosaved as a SERVER draft (real save-and-return). In the static snapshot the "draft" lives only in the browser tab and says so. */
  var IN = { timer: null, form: null, saving: false, dirty: false };
  var SAVED_WHERE = function () { return PS.snapshot ? 'on this page only (demo: in the full version this saves to the server)' : 'on the server'; };
  function renderIntake() {
    document.title = 'DEMO · Intake · Premier Spine patient portal (prototype)'; PS.clear(main);
    main.appendChild(h('p', { text: 'Loading your intake\u2026' }));
    PS.api('GET', '/api/p/intake').then(function (f) {
      IN.form = f; PS.clear(main); var isP = f.viewer === 'patient', fn = f.patient_first;
      main.appendChild(h('div', { class: 'wiz-top' }, h('a', { class: 'toplink', href: '#/home', id: 'in-home' }, PS.icon('back'), 'Home'), h('h1', { text: isP ? 'Your intake form' : 'Intake form for ' + fn })));
      if (!isP) main.appendChild(h('p', { class: 'istatus', id: 'in-helper', text: 'You are filling this in for ' + fn + ' as their authorized helper. ' + fn + ' will be asked to check and confirm the answers before the office relies on them.' }));
      if (f.status === 'completed') return intakeDone(f, isP);
      buildIntakeForm(f, isP);
    }).catch(function (e) { if (authFail(e)) return; PS.clear(main); main.appendChild(h('div', {}, h('h1', { text: 'Intake form' }), h('p', { class: e.status === 409 ? 'istatus' : 'istatus bad', role: 'status', text: PS.errText(e) }), h('a', { class: 'btn', href: '#/home', text: 'Back to Home' }))); });
  }
  function intakeDone(f, isP) {
    if (f.confirmed_by_patient) { main.appendChild(h('div', { class: 'card' }, h('div', { class: 'donecheck', 'aria-hidden': 'true' }, PS.checkSvg()), h('h2', { text: 'Received' }), h('p', { text: 'The office has your intake' + (f.submitted_at ? ' (sent ' + PS.fmtDT(f.submitted_at) + (f.submitted_by ? ' by ' + f.submitted_by : '') + ')' : '') + '. If something changes, message the team or call (208) 770-3536.' }), h('a', { class: 'btn ghost', href: '#/home', text: 'Back to Home' }))); return; }
    if (!isP) { main.appendChild(h('div', { class: 'card' }, h('h2', { text: 'Sent \u2014 waiting for ' + f.patient_first + ' to confirm' }), h('p', { text: f.patient_first + ' can confirm in the portal, or by phone with the office.' }), h('a', { class: 'btn ghost', href: '#/home', text: 'Back to Home' }))); return; }
    var a = f.submitted_answers || {}, st = PS.statusEl('att-st'), dl = h('dl', { class: 'kv', id: 'att-summary' }), FS = f.field_status || {};
    function kvp(k, v) { dl.appendChild(h('dt', { text: k })); dl.appendChild(h('dd', { text: v || '\u2014' })); }
    f.prefill.forEach(function (x) { var c = (a.confirm || {})[x.key], s = FS[x.key] || {};
      kvp(x.label, (c === 'change' ? 'Change to: ' + ((a.corrections || {})[x.key] || '') : x.value) + (s.by_role === 'caregiver' ? ' \u2014 checked by ' + (s.by_name || 'your helper') + ', not by you yet' : '')); });
    kvp('What matters most', (a.matters || []).join(', ')); kvp('Medicines', a.medicines); kvp('Allergies', a.allergies);
    kvp('How to contact you', ((f.contact_prefs.filter(function (o) { return o.value === a.contact_pref; })[0]) || {}).label);
    kvp('Symptoms from the safety question', (a.redflags || []).length ? a.redflags.map(function (k) { return (f.redflags.filter(function (o) { return o.value === k; })[0] || {}).label; }).join('; ') : 'None of these');
    var btn = h('button', { type: 'button', class: 'btn big', id: 'att-btn' }, 'These answers are right');
    btn.addEventListener('click', function () { btn.disabled = true; PS.api('POST', '/api/p/intake/attest', {}, { key: keyFor('attest', 'x') }).then(function () { done('attest'); PS.status(st, 'Thank you. The office can see that you confirmed these answers.', 'ok'); setTimeout(function () { go('home'); }, 1200); }).catch(function (e) { btn.disabled = false; if (!authFail(e)) PS.status(st, PS.errText(e), 'bad'); }); });
    main.appendChild(h('section', { class: 'card gold', 'aria-labelledby': 'h-att' }, h('h2', { id: 'h-att', text: (f.submitted_by || 'Your helper') + ' filled this in for you' }), h('p', { text: 'Please check each answer. The office uses them only after you confirm.' }), dl,
      btn, h('p', { class: 'small' }, 'Something wrong? ', h('a', { href: 'tel:2087703536', text: 'Call (208) 770-3536' }), ' and we\u2019ll fix it with you.'), st));
  }
  function helpBits(id, why, hint) {
    return h('div', { class: 'help', id: id + '-help' }, hint ? h('p', { class: 'small hint', id: id + '-hint', text: hint }) : null,
      why ? h('details', { class: 'whyask' }, h('summary', { text: 'Why we ask' }), h('p', { class: 'small', text: why })) : null);
  }
  function tickSpan() { return h('span', { class: 'tick', 'aria-hidden': 'true' }, PS.checkSvg()); }
  function chipLabel(inp, text) { return h('label', { class: 'choice chipc', for: inp.id }, inp, tickSpan(), text); }
  function errP(id) { return h('p', { class: 'ferr', id: id, hidden: true }); }
  function buildIntakeForm(f, isP) {
    var d = f.draft || {}, conf = d.confirm || {}, corr = d.corrections || {}, FS = f.field_status || {}, fn = f.patient_first;
    var HL = f.help || {}, hb = function (k) { return HL[k] ? helpBits('q-' + k, HL[k].why, HL[k].hint) : null; };
    var ind = h('p', { class: 'ind', id: 'in-ind', role: 'status', 'aria-live': 'polite', text: f.draft_saved_at ? 'Draft saved ' + SAVED_WHERE() + ' ' + PS.fmtDT(f.draft_saved_at) + (f.draft_by ? ' by ' + f.draft_by : '') + '. Not sent to the office yet.' : 'Your answers are saved ' + SAVED_WHERE() + ' as you go. Nothing is sent to the office until you press Send.' });
    var form = h('form', { id: 'intake', novalidate: true });
    var GROUPS = [{ t: 'About you', keys: ['name', 'dob', 'phone'] }, { t: 'Referral and insurance', keys: ['referrer', 'reason', 'insurance', 'imaging'] }, { t: 'Medicines and allergies', keys: ['meds', 'allergies'] },
      { t: 'Contact and goals', keys: [] }, { t: 'Safety question', keys: [] }, { t: 'Review and send', keys: [] }];
    f.prefill.forEach(function (x) { if (!GROUPS.some(function (g) { return g.keys.indexOf(x.key) >= 0; })) GROUPS[0].keys.push(x.key); });
    var N = GROUPS.length, cur = 1, steps = [];
    function stepBox(n, intro) {
      var hd = h('h2', { class: 'h2like', id: 'in-step-' + n + '-h', tabindex: '-1', text: GROUPS[n - 1].t });
      var fs = h('fieldset', { class: 'card step', id: 'in-step-' + n, 'data-step': String(n), 'aria-labelledby': 'in-step-' + n + '-h' }, hd, intro ? h('p', { class: 'small muted stepintro', text: intro }) : null);
      steps.push(fs); form.appendChild(fs); return fs;
    }
    /* one pre-filled value: shown as data from the referral, NEVER as already confirmed; the person answers per field */
    function stText(k) {
      var c = form.querySelector('input[name="pf-' + k + '"]:checked'), s = FS[k] || {};
      if (!c) return ['Not confirmed yet', ''];
      if (c.value === 'change') return ['You asked us to change this', 'warn'];
      if (s.by_role === 'caregiver' && isP && s.state === 'confirmed') return ['Checked by ' + (s.by_name || 'your helper') + ' (helper) \u2014 please check it yourself', 'warn'];
      return [isP ? '\u2713 You confirmed this' : '\u2713 You checked this \u2014 ' + fn + ' will be asked to confirm', 'ok'];
    }
    function pfItem(x) {
      var k = x.key, g = h('div', { class: 'pf', role: 'group', 'aria-labelledby': 'pf-l-' + k, id: 'pf-' + k });
      var cin = h('input', { type: 'text', id: 'pf-c-' + k, maxlength: '200', value: corr[k] || '', 'aria-describedby': (x.hint ? 'pf-h-' + k + ' ' : '') + 'pf-cerr-' + k });
      var cbox = h('div', { class: 'field corr', id: 'pf-c-wrap-' + k, hidden: conf[k] !== 'change' }, h('label', { for: 'pf-c-' + k, text: 'What should it say?' }), x.hint ? h('p', { class: 'small hint', id: 'pf-h-' + k, text: x.hint }) : null, cin, errP('pf-cerr-' + k));
      g.appendChild(h('p', { class: 'pfl', id: 'pf-l-' + k, text: x.label }));
      g.appendChild(h('p', { class: 'pfv' }, h('b', { text: x.value }), h('span', { class: 'okmark', 'aria-hidden': 'true' }, PS.checkSvg())));
      var stp = h('p', { class: 'pfst', id: 'pf-st-' + k }); g.appendChild(stp);
      var r = h('div', { class: 'chips', role: 'radiogroup', id: 'pf-rg-' + k, 'aria-label': 'Is this right? ' + x.label, 'aria-describedby': 'pf-st-' + k + ' pf-err-' + k });
      [['ok', 'Yes, this is right'], ['change', 'No, change it']].forEach(function (o) {
        var inp = h('input', { type: 'radio', name: 'pf-' + k, value: o[0], id: 'pf-' + k + '-' + o[0], 'aria-describedby': 'pf-err-' + k }); if (conf[k] === o[0]) inp.checked = true;
        inp.addEventListener('change', function () { cbox.hidden = o[0] !== 'change'; g.classList.toggle('confirmed', o[0] === 'ok'); setSt(k); clearErr('pf-err-' + k, r); if (o[0] === 'change') cin.focus(); });
        r.appendChild(chipLabel(inp, o[1]));
      });
      if (conf[k] === 'ok') g.classList.add('confirmed');
      g.appendChild(r); g.appendChild(errP('pf-err-' + k)); g.appendChild(cbox);
      if (x.source || x.why) g.appendChild(h('details', { class: 'whyask', id: 'pf-' + k + '-help' }, h('summary', { text: 'Where this came from' }),
        x.source ? h('p', { class: 'small src', id: 'pf-src-' + k }, h('span', { class: 'tag', text: 'Simulated source' }), ' ' + x.source) : null, x.why ? h('p', { class: 'small', text: 'Why we ask: ' + x.why }) : null));
      cin.addEventListener('input', function () { if (cin.value.trim()) clearErr('pf-cerr-' + k, cin); });
      return g;
    }
    function setSt(k) { var el = $('#pf-st-' + k); if (!el) return; var t = stText(k); el.textContent = t[0]; el.className = 'pfst ' + t[1]; }
    var byKey = {}; f.prefill.forEach(function (x) { byKey[x.key] = x; });
    var hasMeds = !!byKey.meds, hasAll = !!byKey.allergies;
    /* steps 1-3: what we already have (confirm or change) */
    [0, 1, 2].forEach(function (gi) {
      var fs = stepBox(gi + 1, gi === 0 ? 'We filled these in from your referral. Please check each one.' : gi === 1 ? (f.ask_facility ? 'From your referral, plus one question.' : 'From your referral.') : null);
      if (gi === 0) fs.querySelector('p.stepintro').id = 'pf-note';
      GROUPS[gi].keys.forEach(function (k) { if (byKey[k]) fs.appendChild(pfItem(byKey[k])); });
      if (gi === 1 && f.ask_facility) fs.appendChild(h('div', { class: 'field' }, h('label', { for: 'in-fac', text: 'Where was your MRI done? (leave empty if you haven\u2019t had one)' }), hb('facility'), h('input', { type: 'text', id: 'in-fac', maxlength: '120', value: d.facility || '', 'aria-describedby': 'q-facility-hint' })));
      if (gi === 2) {
        fs.appendChild(h('div', { class: 'field' }, h('label', { for: 'in-med', text: hasMeds ? 'Any other medicines not listed above? (optional)' : 'Medicines you take now (optional)' }), hasMeds ? hb('extra_meds') : helpBits('q-med', 'Your care team checks your medicines before suggesting any treatment.', 'Example: \u201cibuprofen, 2 tablets at night\u201d.'), h('textarea', { id: 'in-med', rows: '3', maxlength: '1000', 'aria-describedby': hasMeds ? 'q-extra_meds-hint' : 'q-med-hint' })));
        fs.appendChild(h('div', { class: 'field' }, h('label', { for: 'in-all', text: hasAll ? 'Any other allergies not listed above? (optional)' : 'Allergies (optional)' }), h('textarea', { id: 'in-all', rows: '2', maxlength: '1000' })));
      }
    });
    /* step 4: contact + what matters (tap-to-pick chips); the required question comes first */
    var s4 = stepBox(4, null);
    var cp = h('fieldset', { id: 'cp-set', 'aria-describedby': 'cp-err' }, h('legend', { id: 'cp-leg', text: 'How should we contact you?' }), hb('contact')), cpc = h('div', { class: 'chips' }); cp.appendChild(cpc);
    f.contact_prefs.forEach(function (o) { var c = h('input', { type: 'radio', name: 'cp', value: o.value, id: 'cp-' + o.value, 'aria-describedby': 'cp-err' }); if (d.contact_pref === o.value) c.checked = true; c.addEventListener('change', function () { clearErr('cp-err', cp); }); cpc.appendChild(chipLabel(c, o.label)); });
    cp.appendChild(errP('cp-err')); s4.appendChild(cp);
    var mt = h('fieldset', {}, h('legend', { text: 'What matters most to you right now? (optional \u2014 choose any)' }), hb('matters')), mtc = h('div', { class: 'chips' }); mt.appendChild(mtc);
    f.matters.forEach(function (m, i) { var c = h('input', { type: 'checkbox', value: m, name: 'matters', id: 'mt-' + i }); if ((d.matters || []).indexOf(m) >= 0) c.checked = true; mtc.appendChild(chipLabel(c, m)); });
    s4.appendChild(mt);
    /* step 5: safety question */
    var rfBox = h('div', { id: 'rf-alert', role: 'alert', class: 'urgentbox', hidden: true }, h('p', { class: 'b', id: 'rf-text', text: f.redflag_guidance }), h('div', { class: 'row' }, h('a', { class: 'btn danger', href: 'tel:911', text: 'Call 911' }), h('a', { class: 'btn', href: 'tel:2087703536', text: 'Call the office (208) 770-3536' })), h('p', { class: 'small', id: 'rf-task' }));
    var s5 = stepBox(5, 'Since your referral, have you had any of these? Tick any that apply, or \u201cNone of these\u201d.');
    var rfSet = h('div', { id: 'rf-set', role: 'group', 'aria-labelledby': 'in-step-5-h', 'aria-describedby': 'rf-err' }, hb('safety')); s5.appendChild(rfSet);
    f.redflags.forEach(function (o) { var c = h('input', { type: 'checkbox', value: o.value, name: 'rf', id: 'rf-' + o.value, 'aria-describedby': 'rf-err' }); if ((d.redflags || []).indexOf(o.value) >= 0) c.checked = true; rfSet.appendChild(h('label', { class: 'choice', for: 'rf-' + o.value }, c, o.label)); });
    var none = h('input', { type: 'checkbox', id: 'rf-none', 'aria-describedby': 'rf-err' }); if (d.redflag_none) none.checked = true; rfSet.appendChild(h('label', { class: 'choice', for: 'rf-none' }, none, 'None of these'));
    rfSet.appendChild(errP('rf-err')); rfSet.appendChild(rfBox);
    s5.appendChild(h('div', { class: 'field' }, h('label', { for: 'in-other', text: 'Anything else you want us to know? (optional)' }), hb('other'), h('textarea', { id: 'in-other', rows: '3', maxlength: '1000', 'aria-describedby': 'q-other-hint' })));
    var emBox = h('div', { id: 'in-em', role: 'alert', class: 'istatus' }); s5.appendChild(emBox);
    s5.appendChild(h('p', { class: 'fine', text: f.medical_copy_note }));
    /* step 6: review, then send */
    var cc = h('input', { type: 'checkbox', id: 'in-confirm', 'aria-describedby': 'cc-err' }), review = h('div', { class: 'review', id: 'in-review' });
    var s6 = stepBox(6, isP ? 'Please check everything once. Use \u201cChange\u201d to fix anything.' : fn + ' will be asked to check these answers before the office relies on them.');
    s6.appendChild(review); s6.appendChild(h('label', { class: 'choice', for: 'in-confirm' }, cc, isP ? 'These answers are right' : 'These answers are right, as far as I know')); s6.appendChild(errP('cc-err'));
    cc.addEventListener('change', function () { if (cc.checked) clearErr('cc-err', cc); });
    /* header: ONE progress indicator with meaningful names (step list tucked into "All steps") */
    var stepn = h('p', { class: 'wiz-now', id: 'in-stepn' }), nextn = h('p', { class: 'wiz-next small muted', id: 'in-nextname' });
    var bar = h('div', { class: 'wiz-bar seg', role: 'progressbar', id: 'in-bar', 'aria-label': 'Intake progress', 'aria-valuemin': '1', 'aria-valuemax': String(N) });
    for (var bi = 0; bi < N; bi++) bar.appendChild(h('span', {}));
    var sbtns = h('ol', { class: 'wiz-steps', id: 'in-steps', 'aria-label': 'Intake steps' });
    GROUPS.forEach(function (g, i) { var n = i + 1; sbtns.appendChild(h('li', {}, h('button', { type: 'button', id: 'in-stepbtn-' + n, onclick: function () { allSteps.open = false; show(n, true); } }, h('span', { class: 'n', text: String(n) }), h('span', { class: 'lab', text: g.t }), h('span', { class: 'sr', id: 'in-stepsr-' + n })))); });
    var allSteps = h('details', { class: 'wiz-all', id: 'in-allsteps' }, h('summary', { text: 'All steps' }), sbtns);
    var head = h('div', { class: 'wiz-head', id: 'in-head' }, stepn, bar, h('div', { class: 'wiz-sub' }, nextn, allSteps));
    var back = h('button', { type: 'button', class: 'btn ghost', id: 'in-back' }, PS.icon('back'), 'Back'), next = h('button', { type: 'button', class: 'btn', id: 'in-next' }, 'Next', PS.icon('chevron'));
    var send = h('button', { type: 'submit', class: 'btn', id: 'in-send' }, isP ? 'Send my intake' : 'Send for ' + fn + ' to confirm'), st = h('p', { id: 'in-st', class: 'istatus', role: 'alert' });
    var foot = h('div', { class: 'card wiz-foot', id: 'in-foot' }, h('div', { class: 'row' }, back, h('span', { class: 'spacer' }), next, send), st, ind,
      h('p', { class: 'small' }, h('a', { href: '#/home', id: 'in-later' }, 'Finish later'), ' \u2014 your answers stay saved.'));
    form.insertBefore(head, form.firstChild); form.appendChild(foot);
    back.addEventListener('click', function () { PS.status(st, '', ''); show(cur - 1, true); });
    next.addEventListener('click', function () { if (checkStep(cur, true)) show(cur + 1, true); });
    main.appendChild(form);
    ['in-med', 'in-all', 'in-other'].forEach(function (id) { var k = { 'in-med': 'medicines', 'in-all': 'allergies', 'in-other': 'other' }[id]; $('#' + id).value = d[k] || ''; });
    f.prefill.forEach(function (x) { setSt(x.key); });
    function q(sel) { return form.querySelectorAll(sel); }
    /* ---- inline errors: text next to the field, aria-invalid + aria-describedby, focus moves to the first error ---- */
    function showErr(id, ctl, msg) { var e = $('#' + id); e.textContent = msg; e.hidden = false; if (ctl) ctl.setAttribute('aria-invalid', 'true'); }
    function clearErr(id, ctl) { var e = $('#' + id); if (e) { e.hidden = true; e.textContent = ''; } if (ctl) ctl.removeAttribute('aria-invalid'); }
    function problems(n) {   /* [{err, ctl, focus, msg}] for step n */
      var out = [], fs = steps[n - 1];
      if (n <= 3) Array.prototype.forEach.call(fs.querySelectorAll('.pf'), function (g) {
        var k = g.id.slice(3), c = g.querySelector('input[type=radio]:checked'), rg = $('#pf-rg-' + k);
        if (!c) out.push({ err: 'pf-err-' + k, ctl: rg, focus: g.querySelector('input[type=radio]'), msg: 'Please choose \u201cYes, this is right\u201d or \u201cNo, change it\u201d for ' + byKey[k].label.replace(/ \(.*\)$/, '').toLowerCase() + '.' });
        else if (c.value === 'change' && !$('#pf-c-' + k).value.trim()) out.push({ err: 'pf-cerr-' + k, ctl: $('#pf-c-' + k), focus: $('#pf-c-' + k), msg: 'Please type what it should say, or choose \u201cYes, this is right\u201d.' });
      });
      if (n === 4 && !form.querySelector('input[name=cp]:checked')) out.push({ err: 'cp-err', ctl: cp, focus: form.querySelector('input[name=cp]'), msg: 'Please choose how we should contact you.' });
      if (n === 5) { if (!rfOn() && !none.checked) out.push({ err: 'rf-err', ctl: rfSet, focus: form.querySelector('input[name=rf]') || none, msg: 'Please tick any that apply, or \u201cNone of these\u201d.' });
        else if (rfOn() && none.checked) out.push({ err: 'rf-err', ctl: rfSet, focus: none, msg: 'You ticked a symptom and also \u201cNone of these\u201d. Please check this question.' }); }
      if (n === 6 && !cc.checked) out.push({ err: 'cc-err', ctl: cc, focus: cc, msg: 'Please tick \u201c' + (isP ? 'These answers are right' : 'These answers are right, as far as I know') + '\u201d to send.' });
      return out;
    }
    function checkStep(n, focus) {
      var ps = problems(n);
      ps.forEach(function (p) { showErr(p.err, p.ctl, p.msg); });
      if (ps.length) {
        PS.status(st, (ps.length === 1 ? 'One answer needs' : ps.length + ' answers need') + ' your attention on this step. ' + (ps.length === 1 ? 'It is' : 'They are') + ' marked in red.', 'bad');
        if (focus) { var el = ps[0].focus; if (el) { el.focus({ preventScroll: true }); var box = el.closest('.pf, fieldset:not(.step), .field, #rf-set, label') || el; box.scrollIntoView({ block: 'center' }); setTimeout(function () { PS.keepInView(el); }, 50); } }
        return false;
      }
      PS.status(st, '', ''); return true;
    }
    function stepDone(n) {
      if (n <= 3) { var pfs = steps[n - 1].querySelectorAll('.pf'); return (!!pfs.length || n < cur) && !problems(n).length; }
      return !problems(n).length;
    }
    function marks() {
      for (var n = 1; n <= N; n++) {
        var b = $('#in-stepbtn-' + n), dn = stepDone(n), was = b.classList.contains('done'), ns = b.querySelector('.n');
        if (dn && !was) { b.classList.add('done'); PS.clear(ns).appendChild(PS.checkSvg()); } else if (!dn && was) { b.classList.remove('done'); PS.clear(ns).textContent = String(n); }
        $('#in-stepsr-' + n).textContent = ' \u2014 step ' + n + (dn ? ', done' : '') + (n === cur ? ', current' : '');
        bar.children[n - 1].className = n < cur || (dn && n !== cur) ? 'done' : n === cur ? 'cur' : '';
      }
    }
    function show(n, focus) {
      cur = Math.max(1, Math.min(N, n)); steps.forEach(function (fs, i) { fs.hidden = i !== cur - 1; });
      var name = GROUPS[cur - 1].t; bar.setAttribute('aria-valuenow', String(cur)); bar.setAttribute('aria-valuetext', 'Step ' + cur + ' of ' + N + ': ' + name);
      stepn.textContent = 'Step ' + cur + ' of ' + N + ': ' + name; nextn.textContent = cur < N ? 'Next: ' + GROUPS[cur].t : 'Last step';
      for (var k = 1; k <= N; k++) { var b = $('#in-stepbtn-' + k); if (k === cur) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current'); }
      back.hidden = cur === 1; next.hidden = cur === N; send.hidden = cur !== N;
      if (cur === N) renderReview();
      marks();
      if (focus) { var hd = $('#in-step-' + cur + '-h'); head.scrollIntoView({ block: 'start' }); if (hd) hd.focus({ preventScroll: true }); }
    }
    function labelOf(list, v) { return ((list.filter(function (o) { return o.value === v; })[0]) || {}).label; }
    function renderReview() {
      var a = collect(); PS.clear(review);
      function sect(n, rows) {
        var dl = h('dl', { class: 'kv' }); rows.forEach(function (r) { dl.appendChild(h('dt', { text: r[0] })); dl.appendChild(h('dd', { class: r[2] || null, text: r[1] || '\u2014' })); });
        review.appendChild(h('div', { class: 'sumsec' }, h('div', { class: 'sumhead' }, h('h3', { text: GROUPS[n - 1].t }), h('button', { type: 'button', class: 'btn ghost sm', id: 'in-edit-' + n, 'aria-label': 'Change ' + GROUPS[n - 1].t, onclick: function () { show(n, true); } }, 'Change')), dl));
      }
      [0, 1, 2].forEach(function (gi) {
        var rows = GROUPS[gi].keys.filter(function (k) { return byKey[k]; }).map(function (k) { var x = byKey[k], c = a.confirm[k]; return [x.label, c === 'change' ? 'Change to: ' + (a.corrections[k] || '(not filled in yet)') : c === 'ok' ? x.value + ' \u2713' : 'Not checked yet \u2014 ' + x.value, c ? null : 'todo']; });
        if (gi === 1 && f.ask_facility) rows.push(['Where your MRI was done', a.facility]);
        if (gi === 2) { rows.push([hasMeds ? 'Other medicines' : 'Medicines', a.medicines]); rows.push([hasAll ? 'Other allergies' : 'Allergies', a.allergies]); }
        if (rows.length) sect(gi + 1, rows);
      });
      sect(4, [['How to contact you', labelOf(f.contact_prefs, a.contact_pref) || 'Not chosen yet', a.contact_pref ? null : 'todo'], ['What matters most', (a.matters || []).join(', ')]]);
      sect(5, [['Symptoms from the safety question', a.redflags.length ? a.redflags.map(function (k) { return labelOf(f.redflags, k); }).join('; ') : (a.redflag_none ? 'None of these' : 'Not answered yet'), a.redflags.length || a.redflag_none ? null : 'todo'], ['Anything else', a.other]]);
    }
    function rfOn() { return Array.prototype.some.call(q('input[name=rf]'), function (x) { return x.checked; }); }
    function emOn() { var v = $('#in-other').value; return (f.emergency_patterns || []).some(function (p) { try { return new RegExp(p, 'i').test(v.replace(/\u2019/g, "'")); } catch (e) { return false; } }); }
    function showRf() { rfBox.hidden = !rfOn(); if (emOn()) { emBox.className = 'istatus bad'; emBox.textContent = f.redflag_guidance; } else { emBox.className = 'istatus'; emBox.textContent = ''; } }
    if (f.safety_flagged) $('#rf-task').textContent = 'An urgent task for our nurse team already exists for this.';
    showRf(); cc.checked = !!d.confirmed;
    function collect() {
      var a = { confirm: {}, corrections: {}, matters: [], redflags: [] };
      f.prefill.forEach(function (x) { var c = form.querySelector('input[name="pf-' + x.key + '"]:checked'); if (c) a.confirm[x.key] = c.value; if (c && c.value === 'change') a.corrections[x.key] = $('#pf-c-' + x.key).value; });
      Array.prototype.forEach.call(q('input[name=matters]:checked'), function (x) { a.matters.push(x.value); });
      Array.prototype.forEach.call(q('input[name=rf]:checked'), function (x) { a.redflags.push(x.value); });
      a.redflag_none = none.checked; a.medicines = $('#in-med').value; a.allergies = $('#in-all').value; a.other = $('#in-other').value;
      var c = form.querySelector('input[name=cp]:checked'); a.contact_pref = c ? c.value : null; if (f.ask_facility) a.facility = $('#in-fac').value; a.confirmed = cc.checked; return a;
    }
    function save(now) {
      clearTimeout(IN.timer); IN.dirty = true; ind.className = 'ind'; ind.textContent = 'Unsaved changes \u2014 saving shortly\u2026';
      IN.timer = setTimeout(function () {
        IN.saving = true; ind.textContent = 'Saving\u2026';
        PS.api('PUT', '/api/p/intake/draft', { answers: collect() }).then(function (r) { IN.saving = false; IN.dirty = false; ind.className = 'ind'; ind.textContent = 'Draft saved ' + SAVED_WHERE() + ' at ' + PS.fmtDT(r.saved_at) + '. Not sent to the office yet.';
          if (r.field_status) { FS = r.field_status; f.prefill.forEach(function (x) { setSt(x.key); }); }
          if (r.red_flag) $('#rf-task').textContent = 'Saved. An urgent task for our nurse team was created at ' + PS.fmtDT(r.saved_at) + '. This does not reach anyone instantly \u2014 please call if you need help now.'; })
          .catch(function (e) { IN.saving = false; if (!authFail(e)) { ind.textContent = 'Could not save the draft: ' + PS.errText(e) + ' Your answers are still on this page.'; ind.className = 'ind bad'; } });
      }, now ? 0 : 800);
    }
    form.addEventListener('keydown', function (e) { if (e.key === 'Enter' && e.target.tagName === 'INPUT' && e.target.type === 'text' && cur < N) { e.preventDefault(); if (checkStep(cur, true)) show(cur + 1, true); } });
    form.addEventListener('input', function (e) {
      if (e.target.name === 'rf' && e.target.checked) none.checked = false; if (e.target === none && none.checked) Array.prototype.forEach.call(q('input[name=rf]'), function (x) { x.checked = false; });
      if (e.target.name === 'rf' || e.target === none) { if (rfOn() || none.checked) clearErr('rf-err', rfSet); }
      showRf(); marks(); save(e.target.name === 'rf' && e.target.checked);
    });
    form.addEventListener('change', function (e) { if (e.target.type === 'radio' || e.target.type === 'checkbox') { showRf(); marks(); } });
    /* ---- send: checked on this device first, then the SERVER validates again; button disabled + idempotency key (server-enforced) ---- */
    var sending = false;
    form.addEventListener('submit', function (e) {
      e.preventDefault(); if (sending) return;
      for (var n = 1; n <= N; n++) if (problems(n).length) { if (n !== cur) show(n, false); checkStep(n, true); return; }
      clearTimeout(IN.timer); sending = true; send.disabled = true; send.setAttribute('aria-busy', 'true'); send.textContent = 'Sending\u2026'; PS.status(st, 'Sending your intake\u2026', '');
      var a = collect();
      PS.api('POST', '/api/p/intake', { answers: a }, { key: keyFor('intake2', JSON.stringify(a)) }).then(function (r) {
        done('intake2'); showSent(r, f, isP);
      }).catch(function (e) {
        sending = false; send.disabled = false; send.removeAttribute('aria-busy'); send.textContent = isP ? 'Try sending again' : 'Try again';
        if (authFail(e)) return;
        if (e.status === 409 && e.data && e.data.error === 'already_submitted') { showSent({ already: true }, f, isP); return; }
        var fk = e.data && e.data.field, map = { contact_required: 4, redflag_required: 5, redflag_conflict: 5, confirm_required: 6 }, step = fk ? (byKey[fk] ? +$('#pf-' + fk).closest('fieldset.step').dataset.step : 0) : (map[e.data && e.data.error] || 0);
        if (e.status === 422 && step) { show(step, false); if (!checkStep(step, true)) return; }
        PS.status(st, (e.status === 422 ? PS.errText(e) + ' ' : 'We couldn\u2019t send your intake' + (e.status ? ' (the server answered ' + e.status + ')' : ' (no answer from the server)') + '. ') +
          'Nothing was lost \u2014 your answers are still here' + (PS.snapshot ? '.' : ' and saved as a draft.') + ' Please try again, or call (208) 770-3536.', 'bad');
        st.setAttribute('tabindex', '-1'); st.focus();
      });
    });
    /* start on the first screen that still needs an answer */
    var first = 1; while (first < N && stepDone(first)) first++;
    show(f.draft ? first : 1, false);
  }
  function showSent(r, f, isP) {
    PS.clear(main); var fn = f.patient_first;
    var card = h('section', { class: 'card sent', id: 'in-done', 'aria-labelledby': 'in-done-h' }, h('div', { class: 'donecheck', 'aria-hidden': 'true' }, PS.checkSvg()),
      h('h1', { id: 'in-done-h', tabindex: '-1', text: r.already ? 'Your intake was already sent' : r.needs_patient_confirmation ? 'Sent \u2014 ' + fn + ' will be asked to confirm' : 'Your intake was sent' }),
      h('p', { text: r.already ? 'The office already has it, so nothing was sent twice.' : 'The office received it' + (r.saved_at ? ' at ' + PS.fmtDT(r.saved_at) : '') + '.' }));
    if (r.red_flag) card.appendChild(h('div', { class: 'urgentbox', role: 'alert' }, h('p', { class: 'b', text: r.guidance }), h('div', { class: 'row' }, h('a', { class: 'btn danger', href: 'tel:911', text: 'Call 911' }), h('a', { class: 'btn', href: 'tel:2087703536', text: 'Call the office (208) 770-3536' }))));
    card.appendChild(h('h2', { class: 'h3like', text: 'What happens next' }));
    card.appendChild(h('p', { text: isP ? 'Our team reads it before your first visit. You don\u2019t need to do anything else for the intake. Home shows anything still open.' : fn + ' will see your answers and can confirm them in the portal, or by phone with the office.' }));
    card.appendChild(h('a', { class: 'btn big', href: '#/home', id: 'in-done-home' }, 'Back to Home'));
    main.appendChild(card); $('#in-done-h').focus(); window.scrollTo(0, 0);
  }

  /* ---------- Messages ---------- */
  function emergencyMatch(text) { return (S.emRx || []).some(function (r) { return r.test(text); }); }
  function wireEmergency(field, box) {
    function chk() { if (emergencyMatch(field.value)) { box.className = 'istatus bad'; box.textContent = S.rules ? S.rules.emergency_message : 'If this is an emergency, call 911.'; } else { box.className = 'istatus'; box.textContent = ''; } }
    field.addEventListener('input', chk); chk();
  }
  function renderMessages() {
    document.title = 'DEMO · Messages · Premier Spine patient portal (prototype)';
    if (!S.me.scopes.messages) { PS.clear(main); main.appendChild(h('div', {}, h('h1', { text: 'Messages' }), h('p', { class: 'istatus warn', text: 'Messages have not been shared with you. Ask the patient to turn this on in their settings.' }))); return; }
    PS.clear(main);
    var isP = S.me.user.role === 'patient';
    /* message */
    var cat = h('fieldset', {}, h('legend', { text: 'What is this about?' }));
    CATS.forEach(function (c) { var r = h('input', { type: 'radio', name: 'cat', value: c[0], id: 'cat-' + c[0] }); if (S.mem.cat === c[0]) r.checked = true; r.addEventListener('change', function () { S.mem.cat = c[0]; }); cat.appendChild(h('label', { class: 'choice', for: 'cat-' + c[0] }, r, c[1])); });
    var body = h('textarea', { id: 'msg-body', rows: '6', 'aria-describedby': 'msg-c' }); body.value = S.mem.msg;
    var cnt = h('p', { class: 'counter', id: 'msg-c' }), send = h('button', { type: 'button', class: 'btn', id: 'msg-send' }, 'Send message'), mst = PS.statusEl('msg-status'), em = h('div', { id: 'msg-em', role: 'alert', class: 'istatus' });
    var upMsg = PS.bindCounter(body, cnt, S.me.limits.message, send); body.addEventListener('input', function () { S.mem.msg = body.value; }); wireEmergency(body, em);
    send.addEventListener('click', function () { doSend(cat, body, send, mst, em, upMsg); });
    var list = h('div', { id: 'threads' }, h('p', { text: 'Loading your conversations…' }));
    main.appendChild(h('div', {}, h('h1', { text: 'Messages' }),
      isP ? [   /* preview19 Prompt C: the old "Ask a quick question" card is merged into "Ask about your visit" (one assistant, scripted, no AI model) */
        h('section', { class: 'card', id: 'ask-card', 'aria-labelledby': 'h-ask' }, h('h2', { id: 'h-ask', text: 'Have a quick question?' }),
          h('p', { class: 'small', text: 'Ask about your visit: what happens next, what you still need to do, where your instructions are, office details, or help writing to the team. Scripted answers from your portal data \u2014 no AI model, not a person.' }),
          h('a', { class: 'btn', href: '#/assist', id: 'msg-assist' }, 'Ask about your visit'),
          h('p', { class: 'fine', text: S.rules ? S.rules.not_triage : '' })),
        h('section', { class: 'card', 'aria-labelledby': 'h-msg' }, h('h2', { id: 'h-msg', text: 'Message the care team' }), cat,
          h('div', { class: 'field' }, h('label', { for: 'msg-body', text: 'Your message' }), body, cnt), em, h('div', { class: 'row' }, send), mst,
          h('p', { class: 'fine', text: 'Sending creates a request that goes to a named person at the office. Unsent text stays here while you move around the portal, but it is not saved if you close or reload the page.' }))] : null,
      h('section', { class: 'card', 'aria-labelledby': 'h-th' }, h('h2', { id: 'h-th', text: 'Your conversations' }), list)));
    loadThreads(list);
  }
  function loadThreads(list) {
    PS.api('GET', '/api/p/threads').then(function (r) {
      PS.clear(list);
      if (!r.threads.length) { list.appendChild(h('p', { text: 'No conversations yet.' })); return; }
      r.threads.forEach(function (t) {
        list.appendChild(h('a', { class: 'qitem', href: '#/messages/' + t.id }, h('span', { class: 't' }, h('b', { text: t.category || 'Message' }), h('span', { class: 'chip ' + PS.chipFor(t.status), text: PS.statusMark[t.status] + t.status_text })),
          h('span', { class: 'm', text: t.preview }), h('span', { class: 'm', text: 'Last update ' + PS.fmtDT(t.updated_at) })));
      });
    }).catch(function (e) { if (authFail(e)) return; PS.clear(list);   /* preview19 publish: the list error offers a retry */
      var again = h('button', { type: 'button', class: 'btn ghost', id: 'threads-retry' }, 'Try again'); again.addEventListener('click', function () { again.disabled = true; PS.clear(list); list.appendChild(h('p', { text: 'Loading\u2026' })); loadThreads(list); });
      list.appendChild(h('div', { id: 'threads-error' }, h('p', { class: 'istatus bad', role: 'alert', text: 'We couldn\u2019t load your conversations: ' + PS.errText(e) + ' Nothing was changed.' }), again)); });
  }
  function doSend(cat, body, send, st, em, up) {
    var c = cat.querySelector('input:checked'); if (!c) { PS.status(st, 'Please choose what this is about.', 'bad'); return; }
    if (!body.value.trim()) { PS.status(st, 'Please write a message first. An empty message can’t be sent.', 'bad'); body.focus(); return; }
    if (!up()) { PS.status(st, 'This message is too long to send. Please shorten it.', 'bad'); return; }
    send.dataset.busy = '1'; send.disabled = true; PS.status(st, 'Sending\u2026', '');
    PS.api('POST', '/api/p/messages', { category: c.value, body: body.value }, { key: keyFor('msg', c.value + '\u0000' + body.value) }).then(function (r) {
      done('msg'); S.mem.msg = ''; body.value = ''; send.textContent = 'Send message'; up();
      var t = r.task;
      PS.status(st, (r.duplicate_suppressed ? 'We already have this exact message, so we did not create a second request. ' : 'Sent. ') + 'Status: ' + t.status_text + '. ' + (t.reply_target || 'The office has not set a reply time target, so we can’t promise one.') + (r.routed_note ? ' ' + r.routed_note : '') + (r.guidance ? ' ' + r.guidance : ''), r.triage.level === 'emergency' ? 'warn' : 'ok');
      loadThreads($('#threads'));
    }).catch(function (e) { if (authFail(e)) return;   /* preview19 Prompt D: network failure is "not confirmed", not "did not send"; the button says Try again */
        if (e.status === 422 || PS.isDemo(e)) { PS.status(st, PS.errText(e), 'bad'); return; }
        send.textContent = 'Try sending again';
        PS.status(st, e.status ? 'Your message was not sent: ' + PS.errText(e) + ' Your text is still here. You can try again or call (208) 770-3536.' : 'Not confirmed: ' + PS.errText(e) + ' We can’t tell if your message arrived. Your text is still here. Trying again is safe — it won’t be sent twice. Or call (208) 770-3536.', 'bad'); })
      .finally(function () { send.dataset.busy = ''; up(); });
  }
  /* preview19 Prompt C: doAsk (the old quick-question card) was removed; questions go through "Ask about your visit". The /api/p/ask route stays for older clients. */
  function renderThread(id) {
    document.title = 'DEMO · Conversation · Premier Spine patient portal (prototype)';
    PS.api('GET', '/api/p/threads/' + id).then(function (r) {
      PS.clear(main); var t = r.thread;
      main.appendChild(h('div', {}, h('p', {}, h('a', { class: 'btn ghost sm', href: '#/messages', text: '\u2190 All messages' })), h('h1', { text: t.category || 'Conversation' }),
        h('div', { class: 'card' }, h('p', {}, h('span', { class: 'chip ' + PS.chipFor(t.status), text: PS.statusMark[t.status] + t.status_text })),
          t.ack_note ? h('p', { class: 'istatus', text: t.ack_note }) : null,
          h('p', { class: 'small muted', text: t.open ? (t.reply_target || 'The office has not set a reply time target, so we don’t promise a time. If it can’t wait, call (208) 770-3536.') : 'This request is closed. If you still need help, send a new message or call (208) 770-3536.' })),
        h('section', { 'aria-label': 'Messages in this conversation', id: 'conv' }), h('p', {}, h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { renderThread(id); } }, 'Check for new replies'))));
      var conv = $('#conv');
      r.messages.forEach(function (m) {
        var mine = m.author_role === 'patient' || m.author_role === 'caregiver';
        conv.appendChild(h('div', { class: 'msg ' + (mine ? 'me' : m.kind === 'staff_ack' ? 'ack' : '') }, h('span', { class: 'who', text: (mine ? 'You' : m.author_name) + (m.kind === 'staff_ack' ? ' \u00b7 acknowledgment (not an answer yet)' : '') }), h('time', { text: PS.fmtDT(m.created_at) }), h('div', { class: 'body', text: m.body })));
      });
    }).catch(function (e) { if (!authFail(e)) { PS.clear(main); main.appendChild(h('div', {}, h('p', { class: 'istatus bad', role: 'alert', text: 'We couldn’t open that conversation. ' + PS.errText(e) }), h('a', { class: 'btn', href: '#/messages', text: 'Back to messages' }))); } });
  }

  /* ---------- Ask about your visit (preview19 Prompt A): DEMO assistant. Scripted and deterministic — NO AI model, no keys, no outside calls.
     Answers are built on the server from this patient's own records. Messages and documents are never read as instructions. ---------- */
  var AS_LABEL = 'Demo assistant: scripted answers from your portal data, no AI model connected';
  var AS_SUGG = [['next', 'What happens next?'], ['todo', 'What do I still need to complete?'], ['instructions', 'Where can I find my visit instructions?'], ['contact', 'Can you help me contact the team?']];
  var AS_TEAMS = [['scheduling', 'Scheduling', 'Front desk'], ['billing', 'Billing', 'Front desk'], ['medical', 'Clinical team', 'Nurse'], ['records', 'Records', 'Front desk']];
  var AS_DRAFTS = { scheduling: 'Hello, I have a question about scheduling my visit: ', billing: 'Hello, I have a billing or insurance question: ', medical: 'Hello, I have a question for the clinical team: ', records: 'Hello, I have a question about my records: ' };
  function asTeam(k) { return AS_TEAMS.filter(function (t) { return t[0] === k; })[0]; }
  function contactPremier(canMsg) {
    return h('section', { class: 'card contactbar', id: 'as-contact', 'aria-labelledby': 'h-as-contact' }, h('h2', { id: 'h-as-contact', text: 'Contact Premier' }),
      h('div', { class: 'helpgrid' }, h('a', { class: 'btn ghost', href: 'tel:2087703536', id: 'as-call' }, PS.icon('phone'), 'Call us \u00b7 (208) 770-3536'),
        canMsg ? h('a', { class: 'btn ghost', href: '#/messages', id: 'as-msg' }, PS.icon('messages'), 'Message the team') : null),
      h('p', { class: 'small', text: 'In an emergency, call 911.' }));
  }
  function renderAssist() {
    document.title = 'DEMO \u00b7 Ask about your visit \u00b7 Premier Spine patient portal (prototype)';
    PS.clear(main); window.scrollTo(0, 0); var canMsg = !!S.me.scopes.messages && S.me.user.role === 'patient';
    var out = h('div', { id: 'as-out', 'aria-live': 'polite' });
    var q = h('input', { type: 'text', id: 'as-q', autocomplete: 'off', enterkeyhint: 'send', value: S.mem.as || '' }), qc = h('p', { class: 'counter', id: 'as-c' }),
      qb = h('button', { type: 'button', class: 'btn', id: 'as-btn' }, 'Ask'), qem = h('div', { id: 'as-em', role: 'alert', class: 'istatus' });
    var upQ = PS.bindCounter(q, qc, (S.me.limits && S.me.limits.ask) || 300, qb);
    q.addEventListener('input', function () { S.mem.as = q.value; }); wireEmergency(q, qem);
    var sugg = h('div', { class: 'assist-sugg', id: 'as-sugg', role: 'group', 'aria-labelledby': 'h-as-q' });
    AS_SUGG.forEach(function (s) {
      sugg.appendChild(h('button', { type: 'button', class: 'qitem as-s', id: 'as-s-' + s[0], 'data-intent': s[0], onclick: function (e) { askAssist({ intent: s[0] }, s[1], e.currentTarget, out); } }, h('span', { class: 't' }, h('b', { text: s[1] }))));
    });
    function typed() {
      if (!q.value.trim()) { PS.clear(out); out.appendChild(h('p', { class: 'istatus bad', text: 'Please type a question first, or pick one above.' })); return; }
      if (!upQ()) return;
      askAssist({ question: q.value }, q.value, qb, out, function () { q.value = ''; q.dispatchEvent(new Event('input')); upQ(); });
    }
    qb.addEventListener('click', typed);
    q.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); typed(); } });
    main.appendChild(h('div', { class: 'assist' }, h('h1', { text: 'Ask about your visit' }),
      h('p', { class: 'assist-label', id: 'as-label' }, PS.icon('clipboard'), h('span', { text: AS_LABEL })),
      h('p', { class: 'small', id: 'as-notperson', text: 'Not a person \u2014 not Dr. Yakel, not Sarah Frank, not a nurse and not any staff member. It only reads your portal records. It can\u2019t give medical advice.' }),
      h('section', { class: 'card', 'aria-labelledby': 'h-as-q', id: 'as-ask' }, h('h2', { id: 'h-as-q', text: 'Pick a question' }), sugg,
        h('div', { class: 'field' }, h('label', { for: 'as-q', text: 'Or type a short question' }), q, qc), qem, h('div', { class: 'row' }, qb)),
      out, contactPremier(canMsg),
      h('p', { class: 'fine', text: 'Answers are scripted from your portal records. It does not diagnose, read imaging, change medicines or decide about surgery \u2014 your care team does.' })));
  }
  function askAssist(body, asked, btn, out, onOk) {
    btn.dataset.busy = '1'; btn.disabled = true; btn.setAttribute('aria-busy', 'true');
    PS.clear(out); out.appendChild(h('p', { class: 'istatus', role: 'status', text: 'Looking in your records\u2026' }));
    PS.api('POST', '/api/p/assist', body, { key: PS.uuid() }).then(function (r) {
      if (onOk) onOk(); PS.clear(out); var c = answerCard(r, asked); out.appendChild(c); c.focus({ preventScroll: true }); c.scrollIntoView({ block: 'start', behavior: 'smooth' });
    }).catch(function (e) {
      if (authFail(e)) return; PS.clear(out);
      if (PS.isDemo(e)) { out.appendChild(h('p', { class: 'istatus demo', role: 'status', id: 'as-err', text: PS.errText(e) })); return; }   /* preview19 publish */
      out.appendChild(h('p', { class: 'istatus bad', role: 'alert', id: 'as-err', text: 'The demo assistant could not answer: ' + PS.errText(e) + ' Your question is still in the box. You can call (208) 770-3536.' }));
    }).finally(function () { btn.dataset.busy = ''; btn.disabled = false; btn.removeAttribute('aria-busy'); });
  }
  var AS_CHIP = { answer: null, contact: null, emergency: ['bad', 'Emergency wording'], refusal: ['warn', 'Needs a person'], uncertain: ['warn', 'Not certain \u2014 check with a person'], missing: ['warn', 'Not added yet'], unknown: ['warn', 'No answer in your records'], handoff: ['warn', 'Needs a person'], unavailable: ['warn', 'Assistant not available'] };
  function answerCard(r, asked) {
    var canMsg = !!S.me.scopes.messages && S.me.user.role === 'patient', chip = AS_CHIP[r.kind];
    var card = h('section', { class: 'card answer kind-' + r.kind, id: 'as-answer', tabindex: '-1', 'aria-labelledby': 'h-as-a', 'data-kind': r.kind, 'data-status': r.status || '' },
      h('p', { class: 'as-who', id: 'as-who' }, h('span', { class: 'tag', text: 'Demo assistant' }), ' scripted answer \u00b7 not a person' + (r.demo_recording ? ' \u00b7 demo recording of the prototype\u2019s answer' : '')),
      h('h2', { id: 'h-as-a', class: 'as-q' }, h('span', { class: 'muted', text: 'You asked: ' }), asked),
      chip ? h('p', {}, h('span', { class: 'chip ' + chip[0], id: 'as-chip', text: chip[1] })) : null);
    if (r.kind === 'emergency') {
      var em = r.emergency || {}, t = em.task;
      card.appendChild(h('div', { class: 'istatus bad', id: 'as-emergency', role: 'alert' }, h('p', { text: r.short }),
        h('div', { class: 'row' }, h('a', { class: 'btn danger', href: 'tel:911', id: 'as-911' }, 'Call 911'), h('a', { class: 'btn ghost', href: 'tel:2087703536' }, 'Call the office'))));
      if (t && em.created) card.appendChild(h('p', { class: 'small', id: 'as-urgent-task', text: 'Because of the words you used, an urgent request was also created for our nurse team at ' + PS.fmtTime(t.created_at) + ' (reference #' + t.id + '). It does not reach anyone instantly \u2014 please don\u2019t wait for a reply.' }));
      else if (t) card.appendChild(h('p', { class: 'small', id: 'as-urgent-task', text: 'You already have an open urgent request with these words (reference #' + t.id + '), so we did not add another. Please don\u2019t wait for a reply.' }));
      return card;
    }
    card.appendChild(h('p', { class: 'as-short', id: 'as-short', text: r.short }));
    (r.links || []).forEach(function (l, i) { card.appendChild(h('p', {}, h('a', { class: 'btn ghost sm', href: l.href, id: 'as-link-' + i, text: l.label }))); });
    var facts = r.detail || [];
    if (facts.length || r.verbatim) {
      var d = h('details', { class: 'more', id: 'as-more' }, h('summary', { text: 'More detail' }));
      if (r.verbatim) d.appendChild(h('div', { class: 'field' }, h('p', { class: 'small', text: 'Exact approved wording (not explained or changed):' }), h('blockquote', { class: 'approved', id: 'as-verbatim', text: r.verbatim })));
      d.appendChild(h('ul', { class: 'plain facts', id: 'as-facts' }, facts.map(function (f) {
        return h('li', { class: f.stale ? 'stale' : null }, h('p', { text: f.text }),
          h('p', { class: 'small muted' }, 'Source: ' + f.source + ' \u00b7 ' + (f.updated_at ? 'Last update ' + PS.fmtDT(f.updated_at) : 'No update time on record')),
          f.stale ? h('p', { class: 'small', text: 'This was last checked a while ago and may be out of date.' }) : null);
      })));
      card.appendChild(d);
    }
    if (r.handoff || r.kind === 'contact') {
      if (canMsg) card.appendChild(composer(r.handoff || {}, r.kind));
      else card.appendChild(h('p', { class: 'istatus', id: 'as-call-only', text: 'Please call (208) 770-3536 to talk to a person.' }));
    }
    return card;
  }
  /* hand-off: the patient picks the team, edits the draft, reviews it, then confirms.  "Sent" only after the server says the request was created. */
  function composer(hf, kind) {
    var wrap = h('div', { class: 'compose', id: 'as-compose' }), team = hf.team || '';
    var fs = h('fieldset', { id: 'as-teams' }, h('legend', { text: kind === 'contact' ? 'Who do you want to contact?' : 'Want to send this to a person? Choose who:' }));
    var ta = h('textarea', { id: 'as-draft', rows: '4', 'aria-describedby': 'as-draft-c' }); ta.value = hf.draft || (team ? AS_DRAFTS[team] : '');
    var cnt = h('p', { class: 'counter', id: 'as-draft-c' }), st = PS.statusEl('as-send-status'), em = h('div', { class: 'istatus', role: 'alert', id: 'as-draft-em' });
    var review = h('button', { type: 'button', class: 'btn', id: 'as-review' }, 'Check my message'), panel = h('div', { id: 'as-panel' });
    var up = PS.bindCounter(ta, cnt, (S.me.limits && S.me.limits.message) || 2000, review); wireEmergency(ta, em);
    AS_TEAMS.forEach(function (t) {
      var r = h('input', { type: 'radio', name: 'as-team', value: t[0], id: 'as-team-' + t[0] }); if (t[0] === team) r.checked = true;
      r.addEventListener('change', function () { var old = team; team = t[0]; if (!ta.value.trim() || (old && ta.value === AS_DRAFTS[old])) ta.value = AS_DRAFTS[team]; up(); PS.clear(panel); });
      fs.appendChild(h('label', { class: 'choice', for: 'as-team-' + t[0] }, r, t[1] + ' (' + t[2] + ')'));
    });
    ta.addEventListener('input', function () { PS.clear(panel); PS.status(st, '', ''); });
    review.addEventListener('click', function () {
      if (!team) { PS.status(st, 'Please choose who should get it.', 'bad'); return; }
      if (!ta.value.trim()) { PS.status(st, 'Please write a message first.', 'bad'); ta.focus(); return; }
      if (!up()) { PS.status(st, 'This message is too long to send. Please shorten it.', 'bad'); return; }
      PS.status(st, '', ''); showReview();
    });
    function showReview() {
      var tm = asTeam(team), text = ta.value;
      var send = h('button', { type: 'button', class: 'btn', id: 'as-send' }, 'Send to ' + tm[1]), edit = h('button', { type: 'button', class: 'btn ghost', id: 'as-edit' }, 'Edit');
      PS.clear(panel);
      panel.appendChild(h('div', { class: 'review', id: 'as-reviewbox' }, h('p', {}, h('b', { text: 'Nothing has been sent yet. ' }), 'Please check it. It will go to ' + tm[1] + ' (' + tm[2] + ') through your portal messages.'),
        h('blockquote', { class: 'draft', id: 'as-review-text', text: text }), h('div', { class: 'row' }, send, edit)));
      edit.addEventListener('click', function () { PS.clear(panel); ta.focus(); });
      send.addEventListener('click', function () { doAssistSend(team, text, send, edit, st, wrap); });
      panel.scrollIntoView({ block: 'nearest' }); send.focus({ preventScroll: true });
    }
    wrap.appendChild(fs); wrap.appendChild(h('div', { class: 'field' }, h('label', { for: 'as-draft', text: 'Your message (you can change anything)' }), ta, cnt)); wrap.appendChild(em);
    wrap.appendChild(h('div', { class: 'row' }, review)); wrap.appendChild(panel); wrap.appendChild(st);
    return wrap;
  }
  function doAssistSend(team, text, send, edit, st, wrap) {
    var tm = asTeam(team), key = keyFor('as-send', team + '\u0000' + text);   /* same draft + same team => same key, so a retry can never create a duplicate */
    send.disabled = true; edit.disabled = true; send.dataset.busy = '1'; send.setAttribute('aria-busy', 'true'); send.textContent = 'Sending\u2026';
    PS.status(st, 'Sending\u2026 not sent yet.', '');
    PS.api('POST', '/api/p/messages', { category: team, body: text, via: 'assistant' }, { key: key }).then(function (r) {
      var t = r.task;
      if (!t || !t.id) throw Object.assign(new Error('The server did not confirm the message.'), { status: 0 });
      done('as-send'); wrap.classList.add('sent');
      Array.prototype.forEach.call(wrap.querySelectorAll('input,textarea,button'), function (x) { x.disabled = true; });
      st.className = 'istatus ' + (r.created ? 'ok' : 'warn'); st.textContent = '';
      st.appendChild(h('span', { id: 'as-sent', text: (r.created ? 'Sent at ' + PS.fmtTime(r.sent_at || t.created_at) + ' \u00b7 Reference #' + t.id + ' \u00b7 Routed to ' + (t.team || tm[2]) + '. '
        : 'We already have this exact message (reference #' + t.id + '), so it was not sent twice. ') + 'Status: ' + t.status_text + '. ' + (t.reply_target || 'No reply time has been promised.') + ' ' }));
      st.appendChild(h('a', { href: '#/messages/' + t.id, id: 'as-open-thread', text: 'Open the conversation' }));
      if (r.guidance) st.appendChild(h('p', { class: 'small', text: r.guidance }));
    }).catch(function (e) {
      if (authFail(e)) return;
      send.dataset.busy = ''; send.removeAttribute('aria-busy'); send.disabled = false; edit.disabled = false; send.textContent = 'Try again';
      PS.status(st, (e.status === 422 ? PS.errText(e) + ' ' : 'Not sent. ' + (e.status ? PS.errText(e) + ' ' : 'We couldn\u2019t reach the server. ')) + 'Your message is still here. Press \u201cTry again\u201d, or call (208) 770-3536.', 'bad');
      st.id = 'as-send-status'; st.setAttribute('data-failed', '1');
    });
  }
  /* the ORIGINAL approved-content record (own records only; the server returns 404 for anyone else's) */
  function renderContent(id) {
    document.title = 'DEMO \u00b7 Approved instructions \u00b7 Premier Spine patient portal (prototype)';
    PS.api('GET', '/api/p/content/' + id).then(function (r) {
      var c = r.content; PS.clear(main); window.scrollTo(0, 0);
      var warn = r.slot_status === 'conflict' ? 'There is more than one approved version of these instructions and they don\u2019t match. Please check with the team before relying on this one.'
        : c.stale ? 'These were due for review on ' + PS.fmtDay(c.review_by) + ' and haven\u2019t been re-approved. They may be out of date.' : null;
      main.appendChild(h('div', {}, h('p', {}, h('a', { class: 'btn ghost sm', href: '#/assist', text: '\u2190 Ask about your visit' })), h('h1', { text: c.title }),
        h('section', { class: 'card', 'aria-label': 'Approved instructions' }, c.example ? h('p', { class: 'demonote', id: 'ct-example', text: 'EXAMPLE \u2014 fictional approved-content record. No real clinician approved this.' }) : null,
          warn ? h('p', { class: 'istatus warn', id: 'ct-warn', text: warn }) : null,
          h('blockquote', { class: 'approved', id: 'ct-body', text: c.body }),
          h('dl', { class: 'facts' }, h('div', { class: 'fact' }, h('dt', { text: 'Version' }), h('dd', { text: String(c.version) })), h('div', { class: 'fact' }, h('dt', { text: 'Approved by' }), h('dd', { text: c.approved_by || 'Not recorded' })),
            h('div', { class: 'fact' }, h('dt', { text: 'Approved' }), h('dd', { text: c.approved_at ? PS.fmtDT(c.approved_at) : 'Not recorded' })), h('div', { class: 'fact' }, h('dt', { text: 'Review due' }), h('dd', { text: c.review_by ? PS.fmtDay(c.review_by) : 'Not set' })))),
        contactPremier(!!S.me.scopes.messages && S.me.user.role === 'patient')));
    }).catch(function (e) { if (!authFail(e)) { PS.clear(main); main.appendChild(h('div', {}, h('h1', { text: 'Instructions' }), h('p', { class: 'istatus bad', role: 'alert', id: 'ct-err', text: 'We couldn\u2019t find those instructions. ' + PS.errText(e) }), contactPremier(!!S.me.scopes.messages && S.me.user.role === 'patient'))); } });
  }

  /* ---------- Settings ---------- */
  function renderSettings() {
    document.title = 'DEMO · Settings · Premier Spine patient portal (prototype)';
    PS.clear(main); var isP = S.me.user.role === 'patient';
    main.appendChild(h('h1', { text: 'Settings' }));
    var ts = h('fieldset', { id: 'set-ts' }); PS.textSizeControl(ts, 'set');
    main.appendChild(h('section', { class: 'card', 'aria-label': 'Text size' }, ts, h('p', { class: 'fine', text: 'This device remembers your choice. It is the only thing this portal keeps in your browser\u2019s storage \u2014 no health information.' })));
    if (isP) {
      var box = h('section', { class: 'card', 'aria-labelledby': 'h-help' }, h('h2', { id: 'h-help', text: 'Your helper' }), h('p', { text: 'Loading\u2026' })); main.appendChild(box);
      PS.api('GET', '/api/p/helper').then(function (r) {
        PS.clear(box); box.appendChild(h('h2', { id: 'h-help', text: 'Your helper' }));
        if (!r.helper) { box.appendChild(h('p', { text: 'You have not invited a helper.' })); return; }
        var hp = r.helper, st = PS.statusEl('help-status'), fs = h('fieldset', {}, h('legend', { text: hp.name + ' (family helper) can see:' }));
        var L = { appointments: 'My appointments', instructions: 'My care instructions', status: 'What we’re waiting on', messages: 'My messages with the office' };
        Object.keys(L).forEach(function (k) { var c = h('input', { type: 'checkbox', id: 'sc-' + k, value: k }); c.checked = !!hp.scopes[k]; fs.appendChild(h('label', { class: 'choice', for: 'sc-' + k }, c, L[k])); });
        function save(status) { var sc = {}; Object.keys(L).forEach(function (k) { sc[k] = $('#sc-' + k).checked; });
          PS.api('PUT', '/api/p/helper', { scopes: sc, status: status }).then(function (x) { PS.status(st, x.helper.status === 'stopped' ? 'Sharing with ' + hp.name + ' is stopped. They can’t see anything now.' : 'Your sharing choices were updated on the server.', 'ok'); }).catch(function (e) { if (!authFail(e)) PS.status(st, PS.errText(e), 'bad'); }); }
        box.appendChild(h('p', { class: 'small', text: 'Status: ' + (hp.status === 'active' ? 'sharing is on' : 'sharing is stopped') + '. Your helper never sees what you don’t tick here.' }));
        box.appendChild(fs); box.appendChild(h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn', onclick: function () { save('active'); } }, 'Save my choices'), h('button', { type: 'button', class: 'btn ghost', onclick: function () { save('stopped'); } }, 'Stop all sharing'))); box.appendChild(st);
      }).catch(function (e) { authFail(e); });
    }
    /* preview19 Prompt C: automatic reminder texts (simulated) - the patient can turn them off; the office sees the same record */
    var rbox = h('section', { class: 'card', id: 'set-rem', 'aria-labelledby': 'h-rem' }, h('h2', { id: 'h-rem', text: 'Reminder texts' }), h('p', { text: 'Loading\u2026' })); main.appendChild(rbox);
    function drawRem(r) {
      PS.clear(rbox); rbox.appendChild(h('h2', { id: 'h-rem', text: 'Reminder texts' }));
      rbox.appendChild(h('p', { id: 'rem-state', text: r.opted_out ? 'Off. We won\u2019t send automatic reminders. Our team may phone you instead if something is still needed.' : 'On. We send a few reminders (at most ' + (r.reminders[0] ? r.reminders[0].max : 3) + ' for each thing) only while something is still needed, and they stop as soon as it\u2019s done.' }));
      if (r.reminders.length) rbox.appendChild(h('ul', { class: 'plain small', id: 'rem-list' }, r.reminders.map(function (x) {
        return h('li', {}, h('b', { text: x.label + ': ' }), x.status === 'active' ? 'reminders on \u00b7 ' + x.sent + ' of ' + x.max + ' sent' : 'stopped \u2014 ' + x.stop_text); })));
      rbox.appendChild(h('p', { class: 'fine', text: r.note }));
      if (r.can_change) {
        var rst = PS.statusEl('rem-st'), b = h('button', { type: 'button', class: 'btn ' + (r.opted_out ? '' : 'ghost'), id: 'rem-toggle' }, r.opted_out ? 'Turn reminder texts back on' : 'Turn reminder texts off');
        b.addEventListener('click', function () { b.disabled = true; PS.api('PUT', '/api/p/reminders', { opt_out: !r.opted_out }).then(function (x) { x.can_change = true; x.note = r.note; drawRem(x); PS.status($('#rem-st'), x.opted_out ? 'Saved. Reminder texts are off.' : 'Saved. Reminder texts are on again.', 'ok'); })
          .catch(function (e) { b.disabled = false; if (!authFail(e)) PS.status(rst, 'Not saved: ' + PS.errText(e) + ' Nothing changed. Try again.', 'bad'); }); });
        rbox.appendChild(h('div', { class: 'row' }, b)); rbox.appendChild(rst);
      } else rbox.appendChild(h('p', { class: 'small', text: 'Only the patient can change this.' }));
    }
    PS.api('GET', '/api/p/reminders').then(drawRem).catch(function (e) { if (!authFail(e)) { PS.clear(rbox); rbox.appendChild(h('p', { class: 'istatus bad', text: 'Could not load: ' + PS.errText(e) })); } });
    main.appendChild(h('section', { class: 'card', 'aria-labelledby': 'h-demo' }, h('h2', { id: 'h-demo', text: 'About this demo' }), h('p', { text: 'What is real, what is simulated, and what is not built yet \u2014 all in one place.' }),
      h('button', { type: 'button', class: 'btn ghost', id: 'set-about', onclick: openAbout }, 'Open \u201cAbout this demo\u201d')));
  }

  /* ---------- start ---------- */
  PS.api('GET', '/api/p/me').then(function () { return boot(); }).catch(function (e) { showLogin(e.status === 401 ? '' : 'The prototype server did not answer: ' + PS.errText(e)); });
})();
