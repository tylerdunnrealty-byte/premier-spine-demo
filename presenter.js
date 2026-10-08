/* Presenter-only controls: persona switching, scenario seeding, simulated-vendor tick, reset.
   These exist only for demonstrations; they are not part of the patient or office products. */
(function () {
  'use strict';
  PS.app = 'presenter';
  var h = PS.h, $ = PS.$, main = $('#main'), on = false;
  $('#banner').textContent = PS.BANNER + ' \u00b7 presenter controls';
  function render() {
    PS.clear(main);
    var tog = h('button', { type: 'button', class: 'btn' + (on ? ' gold' : ''), id: 'pm-toggle', 'aria-pressed': String(on) }, 'Presenter mode: ' + (on ? 'ON' : 'OFF'));
    tog.addEventListener('click', function () { PS.api('POST', on ? '/api/presenter/leave' : '/api/presenter/enter', {}).then(function () { on = !on; render(); }).catch(function (e) { PS.status($('#pm-st'), PS.errText(e), 'bad'); }); });
    main.appendChild(h('div', {}, h('h1', { text: 'Presenter mode' }),
      h('div', { class: 'card gold' }, h('p', { text: 'These controls are for people running a demo. They change the fictional data and let you switch between made-up people. They are not shown to patients or office staff.' }), h('div', { class: 'row' }, tog), PS.statusEl('pm-st')),
      h('div', { id: 'panels' })));
    if (on) panels();
  }
  function out(msg, kind) { PS.status($('#pn-st'), msg, kind); }
  function panels() {
    var box = $('#panels'); PS.clear(box); var st = PS.statusEl('pn-st');
    /* Pass 2: eight referral scenarios, each loadable at its start or jumped to its key state */
    box.appendChild(tourCard());
    var sbox = h('div', { class: 'scen', id: 'scen-list' }, h('p', { text: 'Loading scenarios\u2026' })), sst = PS.statusEl('sc-st');
    box.appendChild(h('section', { class: 'card presenter-only', 'aria-labelledby': 'pp-flow' }, h('h2', { id: 'pp-flow', text: 'Referral scenarios (Pass 2)' }),
      h('p', { class: 'small', text: 'Each button re-creates that one fictional patient, runs the steps through the same server actions staff would use, and signs this browser in to the portal and the office as the right people. Faxes, texts and insurance answers are simulated.' }),
      h('p', { class: 'row' }, h('a', { class: 'btn ghost sm', href: 'portal.html', target: '_blank', id: 'open-portal', text: 'Open patient portal (new tab)' }), h('a', { class: 'btn ghost sm', href: 'office.html', target: '_blank', id: 'open-office', text: 'Open office workspace (new tab)' })), sst, sbox));
    loadScenarios(sbox, sst);
    /* personas */
    ['portal', 'office'].forEach(function (app) {
      var list = h('div', { class: 'row' });
      PS.api('GET', '/api/personas?app=' + app).then(function (r) { r.personas.forEach(function (p) { list.appendChild(h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { PS.api('POST', '/api/login', { persona: p.key, app: app }).then(function () { out('This browser is now signed in to the ' + (app === 'portal' ? 'patient portal' : 'office workspace') + ' as ' + p.name + '. Reload that page or use the side-by-side view.', 'ok'); reloadFrames(); }).catch(function (e) { out(PS.errText(e), 'bad'); }); } }, p.name + ' (' + p.role + ')')); }); });
      box.appendChild(h('section', { class: 'card presenter-only', 'aria-labelledby': 'pp-' + app }, h('h2', { id: 'pp-' + app, text: 'Switch persona \u2014 ' + (app === 'portal' ? 'patient portal' : 'office workspace') }), h('p', { class: 'small', text: 'Fictional login picker. Signing in as one person ends the previous person’s session for this browser only.' }), list));
    });
    /* scenarios */
    var sc = [['bad_phone_jordan', 'Make Jordan’s phone unreachable'], ['good_phone_jordan', 'Make Jordan’s phone reachable again'], ['report_arrives_alex', 'Alex’s MRI report arrives by fax (images do not)']];
    var sr = h('div', { class: 'row' });
    sc.forEach(function (s) { sr.appendChild(h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { PS.api('POST', '/api/presenter/scenario', { name: s[0] }).then(function (r) { out(r.message, 'ok'); state(); }).catch(function (e) { out(PS.errText(e), 'bad'); }); } }, s[1])); });
    sr.appendChild(h('button', { type: 'button', class: 'btn sm', onclick: function () { PS.api('POST', '/api/presenter/tick', {}).then(function (r) { out('Simulated vendor / worker step ran: ' + JSON.stringify(r), 'ok'); state(); }).catch(function (e) { out(PS.errText(e), 'bad'); }); } }, 'Run simulated delivery step now'));
    box.appendChild(h('section', { class: 'card presenter-only', 'aria-labelledby': 'pp-sc' }, h('h2', { id: 'pp-sc', text: 'Scenarios' }), h('p', { class: 'small', text: 'The server also runs the delivery step by itself every few seconds; the button just does it right now.' }), sr));
    var rb = h('button', { type: 'button', class: 'btn ghost sm' }, 'Reset all fictional data');
    rb.addEventListener('click', function () { if (rb.dataset.arm !== '1') { rb.dataset.arm = '1'; rb.textContent = 'Press again to confirm reset'; return; } PS.api('POST', '/api/presenter/reset', {}).then(function (r) { out(r.note + ' You must sign in again.', 'ok'); rb.dataset.arm = ''; rb.textContent = 'Reset all fictional data'; state(); reloadFrames(); }).catch(function (e) { out(PS.errText(e), 'bad'); }); });
    box.appendChild(h('section', { class: 'card presenter-only', 'aria-labelledby': 'pp-rs' }, h('h2', { id: 'pp-rs', text: 'Reset' }), h('div', { class: 'row' }, rb)));
    box.appendChild(st);
    box.appendChild(h('section', { class: 'card', 'aria-labelledby': 'pp-state' }, h('h2', { id: 'pp-state', text: 'Server state (counts)' }), h('div', { id: 'state-box' })));
    var vb = h('button', { type: 'button', class: 'btn ghost', 'aria-expanded': 'false' }, 'Show portal and office side by side');
    vb.addEventListener('click', function () { var open = vb.getAttribute('aria-expanded') === 'true'; vb.setAttribute('aria-expanded', String(!open)); vb.textContent = open ? 'Show portal and office side by side' : 'Hide side-by-side view'; var f = $('#frames'); PS.clear(f); if (!open) { f.appendChild(h('div', { class: 'grid2' }, h('div', {}, h('h3', { text: 'Patient portal' }), h('iframe', { class: 'split-frame', id: 'fr-portal', src: 'portal.html', title: 'Patient portal view' })), h('div', {}, h('h3', { text: 'Office workspace' }), h('iframe', { class: 'split-frame', id: 'fr-office', src: 'office.html', title: 'Office workspace view' })))); } });
    if (!PS.snapshot) box.appendChild(h('section', { class: 'card', 'aria-labelledby': 'pp-fr' }, h('h2', { id: 'pp-fr', text: 'Side-by-side view' }), h('div', { class: 'row' }, vb), h('div', { id: 'frames' })));
    state();
  }
  var DAYS = ['days_pass', 'Simulate: the follow-up date passes (automatic follow-up, simulated)'];
  var ADV = { missing: [['records_arrive_missing', 'Simulate: office notes and MRI report arrive (images do not)'], DAYS], nointake: [['reminder_due_drew', 'Simulate: next reminder goes out']], auth: [DAYS], surgery: [DAYS] };
  /* ---------- Spotlight tour: the four office-streamlining stops, in order ---------- */
  var TOUR = [
    { n: '1', title: 'Fewer phone calls', show: 'Patient Home answers \u201cwhere are things?\u201d: what we\u2019re waiting on, who has it, the next step. Then the office queue: \u201cPhone calls the portal may have saved\u201d \u2014 example counts only.',
      steps: [{ id: '1', label: 'Set up stop 1 (Blake: records outstanding)', key: 'missing', step: 'key', portal: '#/home', office: '#/queue' }] },
    { n: '2', title: 'Automatic chasing (prior auth + records)', show: 'Cameron\u2019s prior auth is Waiting. Press \u201cfollow-up date passes\u201d: follow-up 1, then 2 (simulated) \u2014 no staff work. A third press: STUCK, and it lands with the front desk to phone.',
      steps: [{ id: '2', label: 'Set up stop 2 (Cameron: prior auth waiting)', key: 'auth', step: 'key', portal: '#/home', office: 'task' }], days: 'auth' },
    { n: '3', title: 'Pre-filled intake + visit-ready summary', show: '3a: the intake arrives pre-filled from the (simulated) referral, each item showing its source, a hint and \u201cWhy we ask\u201d \u2014 the patient only confirms or corrects. 3b: Dr. Yakel\u2019s visit-ready summary, labelled DRAFT, with a clinician-only \u201cMark draft reviewed\u201d.',
      steps: [{ id: '3a', label: '3a: Avery\u2019s pre-filled intake', key: 'clean', step: 'intake', portal: '#/intake', office: 'task' }, { id: '3b', label: '3b: visit summary as Dr. Yakel', key: 'clean', step: 'key', office_as: 'yakel', portal: '#/home', office: 'task' }] },
    { n: '4', title: 'Surgery prep + post-op check-ins', show: '4a: pre-op checklist with owners; clearance auto-chased. 4b: after surgery, the day-2 check-in. 4c: \u201cSomething worries me\u201d becomes an URGENT nurse task \u2014 the portal gives no medical advice.',
      steps: [{ id: '4a', label: '4a: pre-op checklist', key: 'surgery', step: 'key', portal: '#/home', office: 'task' }, { id: '4b', label: '4b: after surgery (check-in due)', key: 'surgery', step: 'postop', portal: '#/home', office: 'task' },
        { id: '4c', label: '4c: a concern reaches the nurse', key: 'surgery', step: 'postop_concern', office_as: 'nina', portal: '#/home', office: 'task' }] }];
  function tourCard() {
    var st = PS.statusEl('tour-st'), ol = h('ol', { class: 'tour', id: 'tour' });
    TOUR.forEach(function (stop) {
      var row = h('div', { class: 'row' }), links = h('p', { class: 'row', id: 'tour-' + stop.n + '-links' });
      stop.steps.forEach(function (sp) {
        var b = h('button', { type: 'button', class: 'btn sm', id: 'tour-' + sp.id + '-go' }, sp.label);
        b.addEventListener('click', function () {
          b.disabled = true; PS.status(st, 'Setting up ' + sp.label + '\u2026', '');
          PS.api('POST', '/api/presenter/scenario/load', { key: sp.key, step: sp.step, office_as: sp.office_as || null }).then(function (x) {
            b.disabled = false; PS.clear(links);
            links.appendChild(h('a', { class: 'btn ghost sm', href: 'portal.html' + sp.portal, target: '_blank', id: 'tour-' + stop.n + '-portal', text: 'Open portal as ' + x.portal_as + ' (new tab)' }));
            links.appendChild(h('a', { class: 'btn ghost sm', href: 'office.html' + (sp.office === 'task' && x.open_task ? '#/task/' + x.open_task : '#/queue'), target: '_blank', id: 'tour-' + stop.n + '-office', text: 'Open office as ' + x.office_as + ' (new tab)' }));
            PS.status(st, 'Stop ' + stop.n + ' ready. ' + x.message, 'ok'); reloadFrames(); state();
          }).catch(function (e) { b.disabled = false; PS.status(st, PS.errText(e), 'bad'); });
        });
        row.appendChild(b);
      });
      if (stop.days) {
        var db = h('button', { type: 'button', class: 'btn sm ghost', id: 'tour-' + stop.n + '-days' }, 'Simulate: follow-up date passes');
        db.addEventListener('click', function () { db.disabled = true; PS.api('POST', '/api/presenter/scenario/advance', { event: 'days_pass', key: stop.days }).then(function (x) { db.disabled = false; PS.status(st, x.message, 'ok'); reloadFrames(); }).catch(function (e) { db.disabled = false; PS.status(st, PS.errText(e), 'bad'); }); });
        row.appendChild(db);
      }
      ol.appendChild(h('li', { class: 'card', id: 'tour-' + stop.n }, h('h3', { text: 'Stop ' + stop.n + ': ' + stop.title }), h('p', { class: 'small', text: stop.show }), row, links));
    });
    return h('section', { class: 'card gold presenter-only', id: 'tour-card', 'aria-labelledby': 'pp-tour' }, h('h2', { id: 'pp-tour', text: 'Spotlight tour \u2014 4 stops, in order' }),
      h('p', { class: 'small', text: 'Each stop resets one fictional patient to the right moment and signs this browser in as the right people. Everything outside this computer (faxes, texts, insurer messages, follow-ups) is simulated. Counts are example counts from fictional data.' }), st, ol);
  }
  function loadScenarios(sbox, sst) {
    PS.api('GET', '/api/presenter/scenarios').then(function (r) {
      PS.clear(sbox);
      r.scenarios.forEach(function (sc) {
        function load(step, helper, btn) {
          btn.disabled = true; PS.status(sst, 'Loading scenario ' + sc.n + '\u2026', '');
          PS.api('POST', '/api/presenter/scenario/load', { key: sc.key, step: step, as_helper: !!helper }).then(function (x) { btn.disabled = false; PS.status(sst, x.message + ' Portal: ' + x.portal_as + '. Office: ' + x.office_as + '.', 'ok'); reloadFrames(); state(); loadScenarios(sbox, sst); })
            .catch(function (e) { btn.disabled = false; PS.status(sst, PS.errText(e), 'bad'); });
        }
        var row = h('div', { class: 'row' });
        [['start', 'Load at start'], ['key', 'Jump to key state']].forEach(function (b) { var bt = h('button', { type: 'button', class: 'btn sm' + (b[0] === 'start' ? ' ghost' : ''), id: 'sc-' + sc.key + '-' + b[0] }, b[1]); bt.addEventListener('click', function () { load(b[0], false, bt); }); row.appendChild(bt); });
        if (sc.helper) { var hb = h('button', { type: 'button', class: 'btn sm ghost', id: 'sc-' + sc.key + '-helper' }, 'Fill in intake live as helper (' + sc.helper + ')'); hb.addEventListener('click', function () { load('intake', true, hb); }); row.appendChild(hb); }
        else if (sc.key === 'redflag' || sc.key === 'nointake') { var ib = h('button', { type: 'button', class: 'btn sm ghost', id: 'sc-' + sc.key + '-intake' }, sc.key === 'redflag' ? 'Fill in intake live (tick a symptom)' : 'Intake just sent (no reminders yet)'); ib.addEventListener('click', function () { load('intake', false, ib); }); row.appendChild(ib); }
        if (sc.key === 'surgery') [['postop', 'After surgery: check-in due'], ['postop_concern', 'Post-op concern sent']].forEach(function (b) { var pb = h('button', { type: 'button', class: 'btn sm ghost', id: 'sc-surgery-' + b[0] }, b[1]); pb.addEventListener('click', function () { load(b[0], false, pb); }); row.appendChild(pb); });
        (ADV[sc.key] || []).forEach(function (a) { var ab = h('button', { type: 'button', class: 'btn sm ghost', id: 'adv-' + a[0] + (a[0] === 'days_pass' ? '-' + sc.key : '') }, a[1]); ab.addEventListener('click', function () { ab.disabled = true; PS.api('POST', '/api/presenter/scenario/advance', { event: a[0], key: sc.key }).then(function (x) { ab.disabled = false; PS.status(sst, x.message, 'ok'); reloadFrames(); loadScenarios(sbox, sst); }).catch(function (e) { ab.disabled = false; PS.status(sst, PS.errText(e), 'bad'); }); }); row.appendChild(ab); });
        sbox.appendChild(h('article', { class: 'card', 'aria-labelledby': 'sch-' + sc.key }, h('h3', { id: 'sch-' + sc.key, text: sc.n + '. ' + sc.title }),
          h('p', { class: 'small' }, h('span', { class: 'chip info', text: 'Now: ' + (sc.state || '\u2014') })),
          h('dl', { class: 'kv' }, h('dt', { text: 'Key state' }), h('dd', { text: sc.key_state }), h('dt', { text: 'Owner' }), h('dd', { text: sc.owner }), h('dt', { text: 'Human step' }), h('dd', { text: sc.human }),
            h('dt', { text: 'Patient sees' }), h('dd', { text: sc.patient_sees }), h('dt', { text: 'Office sees' }), h('dd', { text: sc.office_sees }), h('dt', { text: 'Signs in as' }), h('dd', { text: 'Portal: ' + sc.portal_persona + ' \u00b7 Office: ' + sc.office_persona })), row));
      });
    }).catch(function (e) { PS.clear(sbox); sbox.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); });
  }
  function reloadFrames() { ['fr-portal', 'fr-office'].forEach(function (id) { var f = document.getElementById(id); if (f) f.contentWindow.location.reload(); }); }
  function state() {
    PS.api('GET', '/api/presenter/state').then(function (r) {
      var b = $('#state-box'); if (!b) return; PS.clear(b);
      b.appendChild(h('p', { text: Object.keys(r.tables).map(function (k) { return k + ': ' + r.tables[k]; }).join(' \u00b7 ') }));
      b.appendChild(h('h3', { text: 'Recent notifications (simulated vendor)' }));
      b.appendChild(r.notifications.length ? h('ul', {}, r.notifications.map(function (n) { return h('li', { text: '#' + n.id + ' ' + n.template + ' \u2192 patient ' + n.patient_id + ': ' + n.status + ' (attempts ' + n.attempts + ')' + (n.last_error ? ' \u2014 ' + n.last_error : '') }); })) : h('p', { text: 'None.' }));
    }).catch(function () {});
  }
  render();
})();
