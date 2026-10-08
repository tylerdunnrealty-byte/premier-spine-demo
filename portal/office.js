/* Office workspace client.  Staff-only.  Reply drafts are kept per item in a draft store (memory) and autosaved
   to the server's draft endpoint, so unrelated clicks, tab switches and refreshes never erase typing.
   No localStorage/sessionStorage; the session token is an httpOnly cookie the page cannot read. */
(function () {
  'use strict';
  PS.app = 'office';
  var h = PS.h, $ = PS.$, main = $('#main');
  var S = { me: null, staff: [], sm: {}, filter: 'open', sel: null, detail: null, drafts: {}, keys: {}, poll: null, built: null };
  $('#banner').textContent = PS.BANNER;
  function keyFor(name, sig) { var k = S.keys[name]; if (!k || k.sig !== sig) k = S.keys[name] = { id: PS.uuid(), sig: sig }; return k.id; }
  function done(name) { delete S.keys[name]; }
  function nm(k) { return k ? (S.sm[k] || k) : 'nobody yet'; }
  function ymd(offset) { var d = new Date(Date.now() + offset * 864e5); return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' }).format(d); }
  function authFail(e) { if (e && e.status === 401) { stopPoll(); S.me = null; showLogin('Your session ended. Please sign in again.'); return true; } return false; }

  PS.bindTextSize($('#textsize'));
  $('#signout').addEventListener('click', function () { flushAll().finally(function () { PS.api('POST', '/api/o/logout', {}).finally(function () { stopPoll(); S.me = null; S.drafts = {}; showLogin('You have signed out.'); }); }); });
  $('#nav').addEventListener('click', function (e) { var b = e.target.closest('button[data-view]'); if (b) location.hash = '#/' + b.dataset.view; });
  window.addEventListener('hashchange', function () { route(false); });

  /* ---------- sign in ---------- */
  function showLogin(msg) {
    $('#nav').hidden = true; $('#signout').hidden = true; $('#who').textContent = ''; PS.clear(main); document.title = 'DEMO · Sign in · Office workspace (prototype)';
    var list = h('div', {}, h('p', { text: 'Loading demo staff…' }));
    main.appendChild(h('div', {}, h('h1', { text: 'Demo sign-in: office workspace' }), h('p', { class: 'demonote', id: 'login-demo', text: 'DEMO \u2014 example data only, not a real patient portal or office system. Every patient and staff member below is made up.' }), msg ? h('p', { class: 'istatus warn', role: 'status', text: msg }) : null,
      h('div', { class: 'card gold' }, h('h2', { text: 'Demo sign-in (fictional staff)' }), h('p', { text: 'No passwords in this prototype. Pick a made-up staff member. What you can do depends on the role the server gives that person.' }), list)));
    PS.api('GET', '/api/personas?app=office').then(function (r) {
      PS.clear(list);
      r.personas.forEach(function (p) { list.appendChild(h('button', { type: 'button', class: 'qitem', onclick: function () { PS.api('POST', '/api/login', { persona: p.key, app: 'office' }).then(boot).catch(function (e) { list.appendChild(h('p', { class: 'istatus bad', role: 'alert', text: PS.errText(e) })); }); } }, h('span', { class: 't' }, h('b', { text: p.name }), h('span', { class: 'chip', text: p.role })), h('span', { class: 'm', text: p.blurb }))); });
    }).catch(function (e) { PS.clear(list); list.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); });
  }
  function boot() {
    return PS.api('GET', '/api/o/me').then(function (me) {
      S.me = me; $('#who').textContent = '\u00b7 ' + me.user.name + ' (' + me.user.role + ')'; $('#signout').hidden = false; $('#nav').hidden = false;
      $('#nav-reports').hidden = !me.can.reports; $('#nav-audit').hidden = !me.can.audit; $('#nav-settings').hidden = !me.can.settings;
      return PS.api('GET', '/api/o/staff');
    }).then(function (r) { S.staff = r.staff; S.sm = {}; r.staff.forEach(function (u) { S.sm[u.key] = u.name; }); if (!location.hash || location.hash === '#/') location.hash = '#/queue'; route(true); })
      .catch(function (e) { if (e.status === 401) showLogin(); else { PS.clear(main); main.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); } });
  }
  PS.api('GET', '/api/o/me').then(boot).catch(function (e) { showLogin(e.status === 401 ? '' : 'The prototype server did not answer: ' + PS.errText(e)); });

  /* ---------- routing ---------- */
  function stopPoll() { if (S.poll) { clearInterval(S.poll); S.poll = null; } }
  function route(first) {
    if (!S.me) return;
    var m = (location.hash || '#/queue').replace(/^#\//, '').split('/'), v = m[0] || 'queue';
    saveNowAll();
    stopPoll();
    var nav = v === 'task' ? 'queue' : v;
    Array.prototype.forEach.call(document.querySelectorAll('#nav button'), function (b) { if (b.dataset.view === nav) b.setAttribute('aria-current', 'page'); else b.removeAttribute('aria-current'); });
    if (v === 'queue' || v === 'task') { showQueue(v === 'task' ? parseInt(m[1], 10) : null, first); }
    else { S.built = null; ({ notifications: pageNotifs, reports: pageReports, audit: pageAudit, settings: pageSettings }[v] || pageNotifs)(); }
    if (!first) main.focus();
  }

  /* ---------- queue + detail ---------- */
  var FILTERS = [['open', 'Open'], ['mine', 'Mine'], ['urgent', 'Urgent'], ['decisions', 'Clinician decisions'], ['referrals', 'Referral pipeline'], ['overdue', 'Overdue'], ['waiting', 'Waiting'], ['resolved', 'Resolved'], ['all', 'All']];
  function showQueue(id, first) {
    document.title = 'DEMO · Work queue · Office workspace (prototype)';
    if (S.built !== 'queue') {
      PS.clear(main); S.built = 'queue'; S.detailId = null;
      var fl = h('div', { class: 'seg', role: 'group', 'aria-label': 'Filter the queue', id: 'filters' });
      FILTERS.forEach(function (f) { fl.appendChild(h('button', { type: 'button', class: 'btn sm', 'data-f': f[0], 'aria-pressed': String(S.filter === f[0]), onclick: function () { S.filter = f[0]; Array.prototype.forEach.call(fl.children, function (b) { b.setAttribute('aria-pressed', String(b.dataset.f === S.filter)); }); loadQueue(true); } }, f[1])); });
      main.appendChild(h('div', {}, h('p', { class: 'kicker', text: 'Office workspace' }), h('h1', { text: 'Work queue' }),
        h('div', { class: 'split', id: 'split' },
          h('section', { class: 'listcol', 'aria-labelledby': 'h-q' },
            h('div', { id: 'board-top', class: 'qhead' }, h('h2', { id: 'h-q', text: 'Everything that needs a person' }),
              h('p', { class: 'muted small', text: 'Urgent clinical items are pinned first. Then: needs action now, waiting on someone else, overdue or blocked.' }),
              h('details', { class: 'more', id: 'prio-how' }, h('summary', { text: 'How this list is ordered' }), h('div', { id: 'prio-how-body' }, h('p', { text: 'Loading\u2026' })))),
            h('div', { id: 'nextup' }),
            h('div', { class: 'qtools' }, fl,
              h('button', { type: 'button', class: 'btn sm ghost', id: 'refresh', onclick: function () { loadQueue(true); loadToday(); if (S.sel) loadDetail(S.sel, false, true); } }, PS.icon('clock'), ' Refresh now'), h('span', { class: 'ind', id: 'upd', role: 'status' })),
            h('p', { class: 'istatus', id: 'q-st', role: 'status', 'aria-live': 'polite' }),
            h('div', { id: 'qlist' }, h('p', { text: 'Loading\u2026' }))),
          h('section', { class: 'detailcol', id: 'detail', 'aria-label': 'Selected item' })),
        h('div', { class: 'topcards' },
          h('section', { class: 'card', 'aria-labelledby': 'h-today' }, h('h2', { id: 'h-today', text: 'Today’s appointments and missing prep' }), h('div', { id: 'today' }, h('p', { text: 'Loading\u2026' }))),
          h('section', { class: 'card calls', id: 'calls', 'aria-labelledby': 'h-calls' }, h('h2', { id: 'h-calls', text: 'Phone calls the portal may have saved' }), h('div', { id: 'calls-body' }, h('p', { text: 'Loading\u2026' }))))));
      loadToday(); loadCalls();
      PS.api('GET', '/api/o/priority-rules').then(function (r) { var b = $('#prio-how-body'); if (!b) return; PS.clear(b); b.appendChild(h('p', { class: 'small istatus warn', text: r.status }));
        b.appendChild(h('ol', { class: 'priolist small' }, r.rules.map(function (x) { return h('li', {}, h('b', { text: x.id + '. ' }), x.rule); }))); }).catch(function () {});
    }
    S.sel = id; $('#split').classList.toggle('has-detail', !!id);
    loadQueue(false);
    if (id) loadDetail(id, true); else { S.detailId = null; PS.clear($('#detail')); $('#detail').appendChild(h('p', { class: 'muted', text: 'Choose an item to see the whole conversation, documents and history.' })); }
    S.poll = setInterval(function () { if (document.hidden) return; loadQueue(false); loadToday(); if (S.sel) loadDetail(S.sel, false, true); }, 15000);
  }
  function loadToday() {
    PS.api('GET', '/api/o/appointments/today').then(function (r) {
      var box = $('#today'); if (!box) return; PS.clear(box);
      if (!r.appointments.length) { box.appendChild(h('p', { class: 'muted', text: 'No appointments today.' })); return; }
      var st = h('div', { class: 'strip' });
      r.appointments.forEach(function (a) {
        st.appendChild(h('div', { class: 'appt' + (a.ready ? '' : ' needs') }, h('p', {}, h('b', { text: PS.fmtTime(a.starts_at) + ' \u00b7 ' + a.patient_name })), h('p', { class: 'small', text: a.clinician + ' \u00b7 ' + a.kind }),
          a.ready ? h('span', { class: 'chip', text: '\u2713 Ready' }) : h('div', {}, h('span', { class: 'chip bad', text: 'Missing prep' }), h('ul', { class: 'small' }, a.missing.map(function (m) { return h('li', { text: m }); }))),
          a.task_id ? h('p', {}, h('a', { href: '#/task/' + a.task_id, text: 'Open related item' })) : null));
      });
      box.appendChild(st);
    }).catch(function (e) { authFail(e); });
  }
  function loadCalls() {
    PS.api('GET', '/api/o/calls-avoided').then(function (r) {
      var box = $('#calls-body'); if (!box) return; PS.clear(box);
      box.appendChild(h('p', { class: 'demonote', id: 'calls-label', text: r.label }));
      box.appendChild(h('ul', { class: 'plain callslist' }, r.lines.map(function (l) { return h('li', {}, h('b', { class: 'num', text: String(l[1]) }), ' ' + l[0]); })));
      box.appendChild(h('p', { class: 'fine', text: r.note }));
    }).catch(function (e) { authFail(e); });
  }
  /* ---------- preview19 Prompt C: one task card = patient, what needs attention, owner (or Unassigned), due / waiting time, ONE next action.
     Everything else (badges, reasons, quotes, chase counts) is inside "More". The server decides the group for every task. ---------- */
  function chipsFor(t) {
    var c = [h('span', { class: 'chip', text: PS.statusMark[t.status] + t.status })];
    if (t.priority === 'urgent') c.push(h('span', { class: 'chip bad', text: 'URGENT' }));
    if (t.overdue) c.push(h('span', { class: 'chip bad', text: 'Overdue' }));
    if (t.followup_due && t.status !== 'Resolved') c.push(h('span', { class: 'chip warn', text: 'Follow-up due' }));
    if (t.acknowledged && t.status !== 'Resolved') c.push(h('span', { class: 'chip', text: 'Acknowledged \u00b7 still open' }));
    if (t.stuck && t.status !== 'Resolved') c.push(h('span', { class: 'chip bad', text: 'Stuck \u2014 needs a phone call' }));
    else if (t.chases && t.status === 'Waiting') c.push(h('span', { class: 'chip', text: 'Auto-chasing ' + t.chases + ' of ' + t.max_chases + ' (simulated)' }));
    else if (t.max_chases && t.status === 'Waiting') c.push(h('span', { class: 'chip', text: 'Auto-chase on (simulated)' }));
    if (t.case_state_label) c.push(h('span', { class: 'chip' + (t.case_state === 'urgent' ? ' bad' : ''), text: 'Referral: ' + t.case_state_label }));
    return c;
  }
  var GROUPS = [['now', 'Needs action now', 'Someone here can do the next step'], ['waiting', 'Waiting on someone else', 'The patient, another office or an insurer'],
    ['blocked', 'Overdue or blocked', 'Past due, stuck, follow-up date passed, or on hold'], ['done', 'Completed', 'Resolved']];
  function ago(iso) { var m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000)); return m < 1 ? 'under 1 min' : m < 60 ? m + ' min' : m < 2880 ? Math.round(m / 60) + ' h' : Math.round(m / 1440) + ' days'; }
  function whenText(t) {
    if (t.status === 'Resolved') return 'Closed ' + (t.resolved_at ? PS.fmtDT(t.resolved_at) : '');
    if (t.status === 'Waiting' && t.waiting_since) return 'Waiting ' + ago(t.waiting_since) + (t.follow_up_by ? ' \u00b7 check by ' + PS.fmtDay(t.follow_up_by) : '');
    if (t.deadline) return (t.overdue ? 'Overdue \u2014 was due ' : 'Due ') + PS.fmtDT(t.deadline);
    return 'Open ' + ago(t.created_at);
  }
  function card(t, pre, pinned) {
    var ro = pinned && !S.canUrgent;
    var more = h('details', { class: 'more tmore', id: pre + '-more-' + t.id }, h('summary', { text: 'More' }),
      h('p', { class: 'badge-row' }, [].concat(chipsFor(t)).filter(function (c) { return c && !(pinned && c.textContent === 'URGENT'); })),   /* the URGENT badge is already on the card face */
      t.reason ? h('p', { class: 'small', text: 'Why: ' + t.reason }) : null,
      t.next_action ? h('p', { class: 'small', text: 'Next step: ' + t.next_action }) : null,
      t.excerpt ? h('p', { class: 'small quote', text: '\u201c' + t.excerpt + '\u201d' + (t.excerpt_truncated ? ' (first 140 of ' + PS.n(t.message_length) + ' characters \u2014 open to read all)' : '') }) : null,
      t.backup_name ? h('p', { class: 'small', text: 'Backup: ' + t.backup_name }) : null,
      t.reminders && t.reminders.length ? h('p', { class: 'small', id: pre + '-rem-' + t.id, text: 'Automatic reminders (simulated): ' + t.reminders.map(function (r) { return r.status === 'active' ? 'on \u00b7 ' + r.sent + ' of ' + r.max + ' sent \u00b7 next ' + PS.fmtDay(r.next_due_at) : 'stopped \u2014 ' + r.stop_text; }).join('; ') }) : null);
    var cls = 'qrow tcard' + (pinned ? ' act-urgent pinned' : t.group === 'blocked' ? ' act-stuck' : '');
    return h('div', { class: cls, id: pre + '-card-' + t.id },
      h('a', { class: 'qitem', href: '#/task/' + t.id, 'aria-current': S.sel === t.id ? 'true' : null },
        h('span', { class: 't' }, h('b', { text: t.patient_name }), pinned ? h('span', { class: 'chip bad', text: 'URGENT' }) : null),
        h('span', { class: 'm attn', text: (t.blocked_step || t.category || t.type).replace(pinned ? /^URGENT:\s*/ : /^$/, '') }),
        h('span', { class: 'm meta' }, PS.icon('people'), ' ' + (t.owner_name || 'Unassigned'), ' \u00b7 ', PS.icon('clock'), ' ' + whenText(t))),
      ro ? h('p', { class: 'small ro', id: pre + '-ro-' + t.id, text: 'A nurse or clinician handles this. Nothing for you to do on it.' })
        : t.held_by ? h('p', { class: 'small held', id: pre + '-held-' + t.id, text: t.held_by.text })
        : qAct(t, pre),
      more);
  }
  function loadQueue(manual) {
    var focusHref = document.activeElement && document.activeElement.getAttribute && document.activeElement.closest && document.activeElement.closest('#qlist') ? document.activeElement.getAttribute('href') : null;
    var openMore = Array.prototype.map.call(document.querySelectorAll('#qlist details.tmore[open]'), function (d) { return d.id; });
    PS.api('GET', '/api/o/queue?filter=' + S.filter).then(function (r) {
      var box = $('#qlist'); if (!box) return; PS.clear(box); if (manual !== undefined) loadCalls();
      S.nextUp = r.next_up; S.canUrgent = r.can_act_on_urgent; renderNextUp(r);
      /* pinned: every open urgent item, whatever the filter or role */
      if (r.pinned.length) box.appendChild(h('section', { class: 'pinned', id: 'pinned', 'aria-labelledby': 'h-pinned' },
        h('h3', { id: 'h-pinned' }, PS.icon('alert'), ' Urgent \u2014 pinned (' + r.pinned.length + ')'),
        h('p', { class: 'small', text: r.can_act_on_urgent ? 'Do these first. They stay here under every filter.' : 'Shown to everyone so nothing is missed. A nurse or clinician owns and handles them.' }),
        r.pinned.map(function (t) { return card(t, 'pin', true); })));
      var rest = r.tasks.filter(function (t) { return t.group !== 'urgent'; });
      if (!rest.length && !r.pinned.length) box.appendChild(h('div', { class: 'card emptyall' }, h('span', { class: 'donecheck', 'aria-hidden': 'true' }, PS.checkSvg()), h('p', { text: 'Nothing in this list.' })));
      else {
        var g = {}; GROUPS.forEach(function (x) { g[x[0]] = []; }); rest.forEach(function (t) { (g[t.group] || g.now).push(t); });
        var recentOnly = !g.done.length; if (recentOnly) g.done = r.recent_done || [];
        var board = h('div', { class: 'board groups four', id: 'board' });
        GROUPS.forEach(function (c) {
          var list = g[c[0]];
          board.appendChild(h('section', { class: 'col ' + c[0], id: 'grp-' + c[0], 'aria-labelledby': 'grp-h-' + c[0] },
            h('header', {}, h('span', { class: 'dot', 'aria-hidden': 'true' }), h('div', {}, h('h3', { id: 'grp-h-' + c[0], text: c[1] }), h('span', { class: 'sub', text: c[0] === 'done' && recentOnly ? 'Most recent 5. Use the Resolved filter for all.' : c[2] })), h('span', { class: 'count', 'aria-label': list.length + ' items', text: String(list.length) })),
            list.length ? list.map(function (t) { return card(t, 'q', false); }) : h('p', { class: 'empty', text: c[0] === 'blocked' ? 'Nothing overdue or blocked.' : c[0] === 'done' ? 'Nothing completed yet.' : 'Nothing here.' })));
        });
        box.appendChild(board);
      }
      openMore.forEach(function (id) { var d = document.getElementById(id); if (d) d.open = true; });
      var u = $('#upd'); if (u) u.textContent = 'Updated ' + new Intl.DateTimeFormat('en-US', { timeZone: 'America/Los_Angeles', hour: 'numeric', minute: '2-digit', second: '2-digit' }).format(new Date()) + ' PT \u00b7 ' + (rest.length + r.pinned.length) + ' shown';
      if (focusHref) { var f = box.querySelector('a[href="' + focusHref + '"]'); if (f) f.focus(); }
    }).catch(function (e) { if (!authFail(e)) { var u = $('#upd'); if (u) u.textContent = 'Could not refresh: ' + PS.errText(e) + ' \u2014 the list below may be out of date.'; } });
  }
  /* Do next: urgent first (P1-P3).  Front desk / admin get an awareness line first, never a clinical action. */
  function renderNextUp(r) {
    var nu = $('#nextup'); if (!nu) return; PS.clear(nu);
    var all = r.pinned.concat(r.tasks), nt = r.next_up_task || all.filter(function (x) { return x.id === r.next_up; })[0];   /* the server sends the item itself, so Do next works under any filter */
    var sec = h('section', { class: 'nextup' + (r.next_up_kind === 'urgent' ? ' urgent' : ''), id: 'nextup-card', 'aria-labelledby': 'h-nextup' }, h('p', { class: 'kicker', text: 'Do next' }));
    if (r.urgent_notice) sec.appendChild(h('div', { class: 'nu-urgent', id: 'nu-urgent', role: 'note' }, h('p', {}, h('b', { text: 'Urgent first: ' }), r.urgent_notice.text),
      h('ul', { class: 'plain small' }, r.urgent_notice.items.map(function (x) { return h('li', {}, h('a', { href: '#/task/' + x.id, text: x.patient_name }), ' \u2014 ' + x.attention + ' \u00b7 owner: ' + x.owner_name); }))));
    if (nt) {
      sec.appendChild(h('h3', { id: 'h-nextup', text: r.next_up_kind === 'urgent' ? 'Urgent \u2014 do this first' : (r.urgent_notice ? 'Then, your next item' : 'Next up for you') }));
      sec.appendChild(h('p', { id: 'nu-what' }, h('b', { text: nt.patient_name }), ' \u00b7 ' + (nt.blocked_step || nt.next_action)));
      sec.appendChild(qAct(nt, 'nu'));
    } else sec.appendChild(h('h3', { id: 'h-nextup', text: r.urgent_notice ? 'Nothing else for you right now' : 'Nothing for you right now' }));
    nu.appendChild(sec);
  }

  /* ----- one-click work: the server says what the next action is; inputs only when a person must supply them.
     A failed action stays visible on the card with "Try again" (same idempotency key, so a retry can never double-act). ----- */
  S.fails = {};
  function qAct(t, pre) {
    var pa = t.primary_action, box = h('div', { class: 'qact', id: pre + '-qact-' + t.id });
    if (!pa) { box.appendChild(h('p', { class: 'small muted', text: 'Next: ' + (t.next_action || 'open the item') })); return box; }
    if (!pa.allowed) { box.appendChild(h('p', { class: 'small muted', text: 'Next: ' + pa.label + ' \u2014 ' + pa.why_not })); return box; }
    if (pa.needs_input) { box.appendChild(h('a', { class: 'btn sm ghost', href: '#/task/' + t.id, id: pre + '-open-' + t.id, text: pa.label })); }
    else {
      var b = h('button', { type: 'button', class: 'btn sm', id: pre + '-act-' + t.id }, pa.label);
      b.addEventListener('click', function () { runAct(t.id, pa.key, {}, b, null, box); });
      box.appendChild(b);
    }
    if (pa.simulated) box.appendChild(h('span', { class: 'tag', text: 'Simulated' }));
    var f = S.fails[t.id + ':' + pa.key]; if (f && pa.allowed && !pa.needs_input) box.appendChild(failBox(t.id, pa.key, f, box));
    return box;
  }
  function failBox(tid, key, f, box) {
    var rb = h('button', { type: 'button', class: 'btn sm', id: 'retry-' + tid }, 'Try again');
    rb.addEventListener('click', function () { runAct(tid, key, f.body, rb, null, box); });
    /* a server refusal changed nothing; a lost connection might have reached the server, so say so (the retry re-uses the same key, so it can't run twice) */
    if (f.demo) return h('div', { class: 'istatus demo actfail', role: 'status', id: 'fail-' + tid }, h('p', { text: f.msg }));   /* preview19 publish */
    var txt = f.net ? 'Not confirmed: the server could not be reached, so we can\u2019t tell if this was done. Trying again is safe \u2014 it won\u2019t be done twice.' : 'Not done: ' + f.msg + ' Nothing was changed.';
    return h('div', { class: 'istatus bad actfail', role: 'alert', id: 'fail-' + tid }, h('p', { text: txt + ' ' }), rb);
  }
  function runAct(tid, key, body, btn, st, box) {
    var payload = Object.assign({ action: key }, body); if (btn) btn.disabled = true; if (st) PS.status(st, 'Working\u2026', '');
    var old = box && box.querySelector('.actfail'); if (old) old.remove();
    return PS.api('POST', '/api/o/tasks/' + tid + '/act', payload, { key: keyFor('act' + tid + key, JSON.stringify(payload)) }).then(function (r) {
      done('act' + tid + key); delete S.fails[tid + ':' + key]; S.lastAct = { tid: tid, msg: r.message, at: Date.now() };
      if (st) PS.status(st, 'Done: ' + r.message, 'ok'); else PS.status($('#q-st'), 'Done: ' + r.message, 'ok');
      loadQueue(false); if (S.sel) loadDetail(S.sel, false, true); return r;
    }).catch(function (e) {
      if (btn) btn.disabled = false; if (authFail(e)) return;
      var f = S.fails[tid + ':' + key] = { msg: PS.errText(e), body: body, net: !(e && e.status), demo: PS.isDemo(e) };
      if (st) { PS.status(st, f.net ? 'Not confirmed: the server could not be reached. Press the button again \u2014 it won\u2019t be done twice.' : 'Not done: ' + f.msg + ' Nothing was changed. Press the button again to retry.', 'bad'); }
      if (box) box.appendChild(failBox(tid, key, f, box));
    });
  }
  function fieldEl(f, id) {
    var lab = h('label', { for: id, text: f.label + (f.required === false ? ' (optional)' : '') }), el;
    if (f.type === 'textarea') el = h('textarea', { id: id, rows: '3', maxlength: String(f.maxlen || 500) });
    else if (f.type === 'select') { el = h('select', { id: id }, h('option', { value: '', text: 'Choose\u2026' })); f.options.forEach(function (o) { el.appendChild(h('option', { value: o.value, text: o.label })); }); }
    else if (f.type === 'checkbox') { el = h('input', { type: 'checkbox', id: id }); el.checked = !!f.default; return h('label', { class: 'choice', for: id }, el, f.label); }
    else if (f.type === 'checklist') { var fs = h('fieldset', { id: id }, h('legend', { text: f.label })); f.options.forEach(function (o, i) { var c = h('input', { type: 'checkbox', id: id + '-' + i, value: o.value }); c.checked = (f.default || []).indexOf(o.value) >= 0; fs.appendChild(h('label', { class: 'choice', for: id + '-' + i }, c, o.label)); }); return fs; }
    else el = h('input', { type: f.type === 'date' ? 'date' : f.type === 'time' ? 'time' : 'text', id: id, maxlength: f.type === 'text' ? String(f.maxlen || 200) : null });
    if (f.default !== undefined && f.type !== 'checkbox') el.value = f.default;
    return h('div', { class: 'field' }, lab, el);
  }
  function fieldVal(f, id) {
    if (f.type === 'checkbox') return $('#' + id).checked;
    if (f.type === 'checklist') return Array.prototype.map.call(document.querySelectorAll('#' + id + ' input:checked'), function (x) { return x.value; });
    return $('#' + id).value;
  }
  function updateDoNext(d) {
    var box = $('#d-do'), pipe = $('#d-pipe'); var acts = d.actions || [];
    box.hidden = !d.case_view; pipe.hidden = !d.case_view; if (!d.case_view) return;
    var sig = d.task.status + '|' + acts.map(function (a) { return a.key + a.label + a.allowed; }).join(',');
    if (box.dataset.sig === sig && document.activeElement && box.contains(document.activeElement)) { renderPipe(d); return; }
    box.dataset.sig = sig; var st = PS.statusEl('do-st'), nodes = [st];
    if (d.allowed.urgent_readonly) {   /* preview19 Prompt C (P2): front desk / admin are never prompted to act on an urgent clinical item */
      replaceIn('d-do', [h('div', { class: 'istatus warn', id: 'd-urgent-ro', role: 'note' }, h('p', {}, h('b', { text: 'Read only for you. ' }), d.allowed.urgent_note)),
        S.nextUp && S.nextUp !== d.task.id ? h('p', {}, h('a', { class: 'btn sm ghost', href: '#/task/' + S.nextUp, id: 'goto-next', text: 'Go to your next item \u2192' })) : null]); renderPipe(d); return;
    }
    if (S.lastAct && S.lastAct.tid === d.task.id && Date.now() - S.lastAct.at < 60000) { st.textContent = 'Done: ' + S.lastAct.msg; st.className = 'istatus ok'; }
    if (!acts.length) {
      nodes.push(h('p', { text: d.task.status === 'Resolved' ? 'This item is finished.' : 'No quick action for this item \u2014 use \u201cAssign and change status\u201d below.' }));
      if (S.nextUp && S.nextUp !== d.task.id) nodes.push(h('p', {}, h('a', { class: 'btn sm', href: '#/task/' + S.nextUp, id: 'goto-next', text: 'Go to your next item \u2192' })));
    }
    var list = h('div', { class: 'actlist' });
    acts.forEach(function (a) {
      var wrap = h('div', {}), btn = h('button', { type: 'button', class: 'btn sm' + (a.primary ? '' : ' ghost'), id: 'do-' + a.key, 'data-act': a.key }, a.label);
      var row = h('div', { class: 'row' }, btn, a.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null); wrap.appendChild(row);
      if (a.note) wrap.appendChild(h('p', { class: 'why', text: a.note }));
      if (!a.allowed) { btn.disabled = true; wrap.appendChild(h('p', { class: 'why', id: 'why-' + a.key, text: a.why_not })); btn.setAttribute('aria-describedby', 'why-' + a.key); list.appendChild(wrap); return; }
      if (!a.fields.length) { btn.addEventListener('click', function () { runAct(d.task.id, a.key, {}, btn, st, wrap); }); list.appendChild(wrap); return; }
      var form = h('form', { class: 'dofields', id: 'dof-' + a.key, hidden: true, novalidate: true });
      a.fields.forEach(function (f) { form.appendChild(fieldEl(f, 'f-' + a.key + '-' + f.name)); });
      var go2 = h('button', { type: 'submit', class: 'btn sm', id: 'dosub-' + a.key }, 'Save: ' + a.label.replace(/\u2026$/, ''));
      form.appendChild(h('div', { class: 'row' }, go2, h('button', { type: 'button', class: 'btn sm ghost', onclick: function () { form.hidden = true; btn.setAttribute('aria-expanded', 'false'); btn.focus(); } }, 'Cancel')));
      form.addEventListener('submit', function (e) { e.preventDefault(); var body = {}; a.fields.forEach(function (f) { body[f.name] = fieldVal(f, 'f-' + a.key + '-' + f.name); }); runAct(d.task.id, a.key, body, go2, st, form); });
      btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', 'dof-' + a.key);
      btn.addEventListener('click', function () { var open = form.hidden; Array.prototype.forEach.call(list.querySelectorAll('form.dofields'), function (x) { x.hidden = true; }); Array.prototype.forEach.call(list.querySelectorAll('button[aria-expanded]'), function (x) { x.setAttribute('aria-expanded', 'false'); }); form.hidden = !open; btn.setAttribute('aria-expanded', String(open)); if (open) { var fi = form.querySelector('input,textarea,select'); if (fi) fi.focus(); } });
      wrap.appendChild(form); list.appendChild(wrap);
    });
    nodes.push(list); replaceIn('d-do', nodes); renderPipe(d);
  }
  function renderPipe(d) {
    var v = d.case_view, r = v.referral || {}, ph = $('#d-pipe-h');
    var pc = $('#d-pipe'); if (pc && document.activeElement && pc.contains(document.activeElement) && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if (ph) ph.textContent = v.surgery ? 'Surgery checklist (example pathway)' : 'Referral checklist';
    if (v.surgery) return renderSurgery(d, v);
    var tr = h('ul', { class: 'plain tracks' }, v.tracks.map(function (x) {
      return h('li', { class: 'track ' + (x.done ? 'done' : x.waiting_on ? 'wait' : 'todo') }, h('p', {}, h('b', { text: x.label }), ' ', x.done ? h('span', { class: 'chip ok', text: 'Done' }) : x.waiting_on ? h('span', { class: 'chip warn', text: 'Waiting on: ' + x.waiting_on }) : h('span', { class: 'chip', text: 'Later' }), x.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null),
        h('p', { class: 'small', text: x.office_text + (x.owner_team && !x.done ? ' \u00b7 Owner: ' + x.owner_team : '') + (x.next_check && !x.done ? ' \u00b7 check again by ' + PS.fmtDay(x.next_check) : '') }),
        (x.task_id && x.task_id !== d.task.id && !x.done) ? h('p', { class: 'small' }, h('a', { href: '#/task/' + x.task_id, text: 'Open that item' })) : null);
    }));
    replaceIn('d-pipe', [h('p', {}, h('span', { class: 'chip ' + (v.state === 'urgent' ? 'bad' : v.ready ? 'ok' : 'info'), text: v.state_label })),
      kv([['Referred by', (r.referring_provider || '') + ', ' + (r.referring_office || '')], ['Reason given', r.reason || '\u2014'], ['Received', (r.received_at ? PS.fmtDT(r.received_at) : '') + (r.received_via ? ' via ' + r.received_via : '')]]),
      tr, h('p', { class: 'fine', text: 'The patient sees the same checklist in plain words (no staff-only notes). Fax, text and insurance steps are simulated in this prototype.' })]);
  }

  function renderSurgery(d, v) {
    var sv = v.surgery, st = PS.statusEl('po-st');
    var items = h('ul', { class: 'plain tracks', id: 'po-items' }, sv.items.map(function (it) {
      var acts = h('div', { class: 'row' });
      (it.actions || []).forEach(function (a) {
        var id = 'po-' + it.key + '-' + a.status, b = h('button', { type: 'button', class: 'btn sm' + (a.status === 'waived' ? ' ghost' : ''), id: id }, a.label);
        if (!a.allowed) { b.disabled = true; acts.appendChild(h('span', {}, b, h('span', { class: 'why', text: ' ' + a.why_not }))); return; }
        if (a.note) {
          var inp = h('input', { type: 'text', id: id + '-n', maxlength: '300', 'aria-label': a.note + ' for: ' + a.label, placeholder: a.note });
          b.addEventListener('click', function () { periopAct(it.id, a.status, inp.value, b, st); });
          acts.appendChild(h('span', { class: 'poform' }, inp, b));
        } else { b.addEventListener('click', function () { periopAct(it.id, a.status, '', b, st); }); acts.appendChild(b); }
      });
      return h('li', { class: 'track ' + (it.done ? 'done' : it.waiting_on ? 'wait' : 'todo'), id: 'po-item-' + it.key },
        h('p', {}, h('b', { text: it.label }), ' ', it.done ? h('span', { class: 'chip ok', text: it.status === 'waived' ? 'Not needed' : 'Done' }) : h('span', { class: 'chip warn', text: ({ todo: 'Not started', requested: 'Requested', received: 'Received \u2014 needs review' }[it.status] || it.status) }), it.simulated ? h('span', { class: 'tag', text: 'Simulated' }) : null),
        h('p', { class: 'small', text: 'Owner: ' + it.owner_team + (it.waiting_on && !it.done ? ' \u00b7 waiting on ' + it.waiting_on : '') + (it.next_check ? ' \u00b7 automatic follow-up by ' + PS.fmtDay(it.next_check) : '') + (it.note ? ' \u00b7 note: ' + it.note : '') }),
        it.done ? null : acts);
    }));
    var cks = sv.checkins && sv.checkins.length ? [h('h3', { text: 'Post-op check-ins (days are placeholders \u2014 surgeon to decide)' }), h('ul', { class: 'plain', id: 'po-checkins' }, sv.checkins.map(function (k) {
      return h('li', {}, h('b', { text: 'Day ' + k.day + ': ' }), k.status + (k.answer ? ' \u2014 ' + ({ ok: 'doing okay', question: 'question for a nurse', concern: 'CONCERN' }[k.answer] || k.answer) : '') + (k.note ? ' \u2014 \u201c' + k.note + '\u201d' : ''));
    }))] : [];
    replaceIn('d-pipe', [h('p', {}, h('span', { class: 'chip ' + (v.state === 'urgent' ? 'bad' : 'info'), text: v.state_label }), ' ', h('span', { class: 'small', text: (sv.postop ? 'Surgery was ' : 'Surgery planned for ') + PS.fmtDate(sv.surgery_at) + ' (example date)' })),
      items, st].concat(cks).concat([h('p', { class: 'fine', text: 'Checklist items are a prototype placeholder list \u2014 the office defines the real one. Instruction content is NOT in this demo: the surgical team provides it. Clearance and lab steps are simulated.' })]));
  }
  function periopAct(id, status, note, btn, st) {
    btn.disabled = true; PS.status(st, 'Saving\u2026', '');
    PS.api('POST', '/api/o/periop/' + id, { status: status, note: note }, { key: keyFor('po' + id + status, note) }).then(function (r) { done('po' + id + status); S.lastAct = { tid: S.sel, msg: r.message, at: Date.now() }; PS.status(st, 'Done: ' + r.message, 'ok'); if (document.activeElement) document.activeElement.blur(); loadDetail(S.sel, false, true); })
      .catch(function (e) { btn.disabled = false; if (!authFail(e)) PS.status(st, PS.errText(e), 'bad'); });
  }
  function renderSummary(d) {
    var box = $('#d-sum'); if (!box) return; box.hidden = !d.summary; if (!d.summary) return;
    var sm = d.summary, st = PS.statusEl('sum-st'), isC = S.me.user.role === 'clinician';
    var rv = sm.reviewed ? h('p', { class: 'chip ' + (sm.reviewed.changed_since ? 'warn' : 'ok'), id: 'sum-reviewed', text: (sm.reviewed.changed_since ? 'Changed since it was reviewed by ' : 'Reviewed by ') + sm.reviewed.by + ' \u00b7 ' + PS.fmtDT(sm.reviewed.at) }) : h('p', { class: 'chip warn', id: 'sum-reviewed', text: 'Not reviewed by a clinician yet' });
    var btn = h('button', { type: 'button', class: 'btn sm', id: 'sum-review', disabled: !isC || (sm.reviewed && !sm.reviewed.changed_since) }, 'Mark draft reviewed');
    btn.addEventListener('click', function () { btn.disabled = true; PS.api('POST', '/api/o/cases/' + d.case.id + '/summary/review', {}, { key: keyFor('sum' + d.case.id, sm.hash) }).then(function () { done('sum' + d.case.id); PS.status(st, 'Marked reviewed. If the data changes later, this card will say so.', 'ok'); loadDetail(S.sel, false, true); }).catch(function (e) { btn.disabled = false; if (!authFail(e)) PS.status(st, 'Not saved: ' + PS.errText(e) + ' Press the button again to retry.', 'bad'); }); });
    /* preview19 Prompt C: every fact links to its source; statements are verbatim and kept apart from what was extracted from records */
    function srcEl(s) {
      if (!s) return null; var lab = 'Source: ' + s.label + (s.at ? ' \u00b7 ' + PS.fmtDT(s.at) : '');
      if (s.doc_id) return h('button', { type: 'button', class: 'linkbtn small srclink', 'data-doc': String(s.doc_id), onclick: function () { var el = $('#doc-' + s.doc_id); if (el) { el.scrollIntoView({ block: 'center' }); el.focus(); } } }, lab);
      if (s.task_id) return h('a', { class: 'small srclink', href: '#/task/' + s.task_id, text: lab });
      return h('span', { class: 'small muted src', text: lab });
    }
    var flags = sm.flags.length ? h('ul', { class: 'plain sumflags', id: 'sum-flags' }, sm.flags.map(function (f) {
      return h('li', { class: 'flag ' + f.kind }, h('span', { class: 'chip ' + (f.kind === 'conflict' ? 'bad' : 'warn'), text: f.kind === 'conflict' ? 'Conflict' : 'Missing' }), ' ' + f.text, ' ', srcEl(f.source)); }))
      : h('p', { id: 'sum-flags', class: 'small', text: 'Nothing missing or conflicting was found in the records this draft uses.' });
    var stl = sm.statements.length ? h('ul', { class: 'plain', id: 'sum-statements' }, sm.statements.map(function (x) {
      return h('li', { class: 'stmt' }, h('p', { class: 'small' }, h('b', { text: x.topic }), ' ', h('span', { class: 'chip ' + (x.status === 'confirmed' ? 'ok' : 'warn'), text: x.status_text })),
        h('blockquote', { class: 'verbatim', text: x.text }), srcEl(x.source)); }))
      : h('p', { id: 'sum-statements', class: 'small', text: 'No statements from the patient yet (no intake or check-in notes).' });
    var ckl = (sm.checked || []).length ? h('dl', { class: 'kv srckv', id: 'sum-checked' }) : h('p', { id: 'sum-checked', class: 'small', text: 'No pre-filled details for this referral.' });
    (sm.checked || []).forEach(function (x) { ckl.appendChild(h('dt', { text: x.topic })); ckl.appendChild(h('dd', {}, h('span', { text: x.value + ' ' }), h('span', { class: 'chip ' + (x.status === 'confirmed' ? 'ok' : 'warn'), text: x.status_text }), ' ', srcEl(x.source))); });
    var exl = h('dl', { class: 'kv srckv', id: 'sum-extracted' }); sm.extracted.forEach(function (x) { exl.appendChild(h('dt', { text: x.topic })); exl.appendChild(h('dd', {}, h('span', { text: x.value }), ' ', srcEl(x.source))); });
    replaceIn('d-sum', [h('p', { class: 'draftbanner', id: 'sum-label', text: sm.label }), h('p', { class: 'small', id: 'sum-note', text: sm.note }), rv,
      h('h3', { text: 'Missing or conflicting' }), flags,
      h('h3', { text: 'What the patient said (word for word)' }), stl,
      h('h3', { text: 'From the referral and records' }), exl,
      h('h3', { text: 'Pre-filled details: who checked them' }), ckl,
      h('h3', { text: 'Still open' }), h('p', { id: 'sum-open', text: sm.open_items.length ? sm.open_items.join(' \u00b7 ') : 'Nothing \u2014 every gate is satisfied.' }),
      h('div', { class: 'row' }, btn, isC ? null : h('span', { class: 'why', text: 'Only a clinician (Dr. Yakel or Sarah Frank, APRN) can mark it reviewed.' })), st]);
  }

  /* ----- draft store ----- */
  function ds(id) { return S.drafts[id] || (S.drafts[id] = { text: null, dirty: false, timer: null, kind: 'reply', origin: 'suggestion', saving: false, savedAt: null, err: null }); }
  function indText(d) {
    if (d.err) return ['Could not save the draft: ' + d.err + ' Your text is still here; trying again.', 'bad'];
    if (d.saving) return ['Saving draft to the server\u2026', ''];
    if (d.dirty) return ['Unsaved changes \u2014 saving shortly\u2026', ''];
    if (d.savedAt) return ['Draft saved on the server at ' + PS.fmtDT(d.savedAt) + '. Not sent.', ''];
    return ['Suggestion only \u2014 nothing has been saved or sent yet.', ''];
  }
  function showInd(id) { var el = $('#draft-ind'); if (!el || S.detailId !== id) return; var t = indText(ds(id)); el.textContent = t[0]; el.className = 'ind ' + t[1]; }
  function scheduleSave(id) { var d = ds(id); clearTimeout(d.timer); d.timer = setTimeout(function () { saveNow(id); }, 700); }
  function saveNow(id) {
    var d = ds(id); clearTimeout(d.timer); if (!d.dirty || d.saving || d.text === null) return Promise.resolve();
    var sent = d.text; d.saving = true; d.err = null; showInd(id);
    return PS.api('PUT', '/api/o/tasks/' + id + '/draft', { body: sent }).then(function (r) { d.saving = false; d.savedAt = r.saved_at; if (d.text === sent) d.dirty = false; else scheduleSave(id); showInd(id); })
      .catch(function (e) { d.saving = false; d.err = PS.errText(e); showInd(id); if (e.status !== 401 && e.status !== 409 && e.status !== 422) d.timer = setTimeout(function () { saveNow(id); }, 5000); });
  }
  function saveNowAll() { Object.keys(S.drafts).forEach(function (id) { if (S.drafts[id].dirty) saveNow(id); }); }
  function flushAll() { return Promise.all(Object.keys(S.drafts).map(function (id) { return saveNow(id); })); }
  document.addEventListener('visibilitychange', function () { if (document.hidden) saveNowAll(); });
  window.addEventListener('pagehide', saveNowAll);

  /* ----- detail ----- */
  function loadDetail(id, initial, quiet) {
    PS.api('GET', '/api/o/tasks/' + id).then(function (d) {
      if (S.sel !== id) return;
      S.detail = d;
      if (S.detailId !== id) buildDetail(d); else updateDetail(d);
    }).catch(function (e) {
      if (authFail(e) || S.sel !== id) return;
      var box = $('#detail'); if (!box || quiet) return; PS.clear(box);
      box.appendChild(h('div', {}, h('p', { class: 'istatus bad', role: 'alert', text: e.status === 404 ? 'That item does not exist.' : 'Could not open it: ' + PS.errText(e) }), h('a', { class: 'btn', href: '#/queue', text: 'Back to queue' })));
    });
  }
  function secCard(id, title, extra) { return h('section', { class: 'card', id: id, 'aria-labelledby': id + '-h' }, h('h2', { id: id + '-h', text: title }), extra || null); }
  function buildDetail(d) {
    var box = $('#detail'); PS.clear(box); S.detailId = d.task.id; document.title = 'DEMO · ' + d.patient.name + ' · Office workspace (prototype)';
    box.appendChild(h('p', {}, h('a', { class: 'btn ghost sm backlink', href: '#/queue' }, PS.icon('back'), ' Back to queue')));
    box.appendChild(h('div', { id: 'd-head' }));
    box.appendChild(secCard('d-do', 'Do next'));
    box.appendChild(secCard('d-pipe', 'Referral checklist'));
    box.appendChild(secCard('d-sum', 'Visit-ready summary for Dr. Yakel (DRAFT)'));
    box.appendChild(secCard('d-facts', 'This item'));
    box.appendChild(secCard('d-convo', 'Conversation'));
    box.appendChild(secCard('d-composer', 'Reply to the patient'));
    box.appendChild(secCard('d-actions', 'Assign and change status'));
    box.appendChild(secCard('d-notes', 'Internal note (staff only)'));
    box.appendChild(secCard('d-docs', 'Source documents'));
    box.appendChild(secCard('d-notifs', 'Notifications to the patient'));
    box.appendChild(secCard('d-hist', 'Action history'));
    buildComposer(d); buildNotes(d); updateDetail(d);
    var hh = $('#d-head h1'); if (hh && document.activeElement === document.body) { /* leave focus alone */ }
  }
  function kv(pairs) { var dl = h('dl', { class: 'kv' }); pairs.forEach(function (p) { dl.appendChild(h('dt', { text: p[0] })); dl.appendChild(h('dd', {}, p[1])); }); return dl; }
  function replaceIn(id, nodes) { var c = $('#' + id); var keep = c.firstChild; while (c.lastChild !== keep) c.removeChild(c.lastChild); PS.add(c, nodes); }
  function updateDetail(d) {
    var t = d.task, c = d.case, p = d.patient;
    var head = $('#d-head'); PS.clear(head);
    head.appendChild(h('h1', { text: p.name })); head.appendChild(h('p', {}, h('span', { class: 'badge-row' }, chipsFor(t)), ' ', h('span', { class: 'muted', text: 'Request #' + t.id + ' \u00b7 ' + (t.category || String(t.type || '').replace(/_/g, ' ')) + ' \u00b7 created '   /* preview19 publish: no raw type codes */ + PS.fmtDT(t.created_at) })));
    replaceIn('d-facts', [kv([
      ['Blocked step', t.blocked_step], ['Reason', t.reason], ['Next action', t.next_action],
      ['Owner', t.owner_name || 'Nobody yet'], ['Backup', t.backup_name || 'None'], ['Deadline', t.deadline ? PS.fmtDT(t.deadline) + (t.overdue ? ' \u2014 OVERDUE' : '') : 'Not set'],
      ['Status', t.status + (t.status === 'Waiting' ? ' on ' + t.waiting_on + ' \u00b7 follow up by ' + PS.fmtDT(t.follow_up_by) : '') + (t.status === 'Resolved' ? ' \u2014 ' + t.outcome + ' (by ' + (t.resolved_by_name || '?') + ')' : '')],
      ['Last verified update', t.last_verified_at ? PS.fmtDT(t.last_verified_at) + ' \u00b7 ' + t.last_verified_source : 'None recorded'],
      ['Acknowledged', t.acknowledged ? 'Yes, at ' + PS.fmtDT(t.ack_at) + ' \u2014 acknowledging does not close the request' : 'Not yet'],
      ['Case readiness', c.ready ? 'Ready for appointment' : 'Not ready: ' + c.missing.join('; ')]]),
      h('p', { class: 'small muted', text: 'Phone on file: ' + p.phone + (p.phone_valid ? '' : ' (marked unreachable)') + ' \u00b7 prefers ' + p.channel })]);
    /* conversation: full bodies, never truncated */
    var cv = []; if (!d.conversation.length) cv.push(h('p', { text: 'No conversation. This item was created by the office or the system.' }));
    d.conversation.forEach(function (m) {
      var cls = m.kind === 'staff_note' ? 'note' : m.kind === 'staff_ack' ? 'ack' : m.kind === 'staff_reply' ? 'me' : '';
      var lab = m.kind === 'staff_note' ? m.author_name + ' \u00b7 INTERNAL NOTE \u2014 the patient cannot see this' : m.kind === 'staff_ack' ? m.author_name + ' \u00b7 acknowledgment sent to patient' : m.kind === 'staff_reply' ? m.author_name + ' \u00b7 reply sent to patient' : m.author_name + ' \u00b7 patient wrote';
      cv.push(h('div', { class: 'msg ' + cls }, h('span', { class: 'who', text: lab }), h('time', { text: PS.fmtDT(m.created_at) + ' \u00b7 ' + PS.n(PS.count(m.body)) + ' characters' }), h('div', { class: 'body', text: m.body })));
    });
    replaceIn('d-convo', cv);
    updateComposerState(d); updateActions(d); updateDoNext(d); renderSummary(d);
    var docs = d.documents.length ? h('ul', { class: 'plain' }, d.documents.map(function (x) {
      return h('li', { id: 'doc-' + x.id, tabindex: '-1' }, h('b', { text: x.title }), ' ', h('span', { class: 'chip ' + (x.status === 'reviewed' ? 'ok' : x.status === 'received' ? 'info' : 'warn'), text: x.status }),
        h('p', { class: 'small', text: (x.source ? 'Source: ' + x.source + '. ' : '') + (x.note || '') + ' (Placeholder \u2014 no real file in this prototype.)' }),
        (S.me.user.role === 'clinician' && x.doc_type === 'radiology_report' && x.status === 'received') ? h('button', { type: 'button', class: 'btn sm', onclick: function () { docAction(x.id); } }, 'Mark report reviewed') : null);
    })) : h('p', { text: 'No documents.' });
    var img = h('div', { class: 'field' }, h('p', { class: 'small' }, 'Report status: ', h('b', { text: c.report_status }), ' \u00b7 Image status: ', h('b', { text: c.images_status }), '. These are tracked separately: a reviewed report does not mean the images arrived.'));
    var sel = h('select', { id: 'img-sel' }); ['unknown', 'requested', 'received', 'unavailable'].concat(S.me.user.role === 'clinician' ? ['waived'] : []).forEach(function (s) { var o = h('option', { value: s, text: s === 'waived' ? 'proceed without images (clinician decision)' : s }); if (s === c.images_status) o.selected = true; sel.appendChild(o); });
    var inote = h('input', { type: 'text', id: 'img-note', maxlength: '300' }), ist = PS.statusEl('img-st');
    img.appendChild(h('label', { for: 'img-sel', text: 'Set image status' })); img.appendChild(sel); img.appendChild(h('label', { for: 'img-note', text: 'Note (required to proceed without images)' })); img.appendChild(inote);
    img.appendChild(h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn sm ghost', onclick: function () { PS.api('POST', '/api/o/cases/' + c.id + '/images', { images_status: sel.value, note: inote.value }, { key: keyFor('img', sel.value + inote.value) }).then(function (r) { done('img'); PS.status(ist, r.note, 'ok'); loadDetail(t.id, false, true); }).catch(function (e) { PS.status(ist, PS.errText(e), 'bad'); }); } }, 'Save image status'))); img.appendChild(ist);
    if (d.case_view) img = h('p', { class: 'small muted', text: 'Records for this referral are handled with the \u201cDo next\u201d actions above (report and images are tracked separately).' });
    var dd = $('#d-docs'); if (!dd.querySelector('#img-sel') || true) { if (!(document.activeElement && dd.contains(document.activeElement))) replaceIn('d-docs', [docs, img]); }
    replaceIn('d-notifs', d.notifications.length ? h('ul', { class: 'plain' }, d.notifications.map(function (n) { return notifLi(n, t.id); })) : h('p', { text: 'No notifications sent for this item yet.' }));
    replaceIn('d-hist', h('ol', { class: 'hist plain' }, d.history.map(function (e) { return h('li', {}, h('b', { text: PS.fmtDT(e.ts) }), ' \u00b7 ' + e.actor_name + ' \u00b7 ' + histText(e)); })));
  }
  function notifLi(n, tid) {
    var cls = n.status === 'failed' ? 'bad' : (n.status === 'accepted' || n.status === 'received') ? 'ok' : 'info';
    return h('li', {}, h('span', { class: 'chip ' + cls, text: n.status }), ' ' + n.template + ' to ' + n.patient_name + ' via ' + n.channel + ' \u00b7 attempts ' + n.attempts + '/' + n.max_attempts,
      n.last_error ? h('p', { class: 'small', text: n.last_error }) : null,
      n.status === 'failed' ? (n.can_retry ? [h('button', { type: 'button', class: 'btn sm', onclick: function () { var out = PS.$('#retry-st-' + n.id); PS.api('POST', '/api/o/notifications/' + n.id + '/retry', {}, { key: keyFor('retry' + n.id, String(n.manual_retries)) }).then(function () { done('retry' + n.id); if (S.sel) loadDetail(S.sel, false, true); else pageNotifs(); }).catch(function (e) { PS.status(out, PS.errText(e), 'bad'); }); } }, 'Retry sending'), PS.statusEl('retry-st-' + n.id)] : h('p', { class: 'small', text: 'Retry limit reached. Phone the patient instead.' })) : null);
  }
  var HA = { 'task.created': 'Request created', 'task.assigned': 'Assignment changed', 'task.transition': 'Status changed', 'message.created': 'Patient message received', 'message.reply': 'Reply sent to patient (task stays open)', 'task.acknowledged': 'Acknowledgment sent (task stays open)', 'task.note': 'Internal note added',
    'task.verified_update': 'Verified update recorded', 'notification.queued': 'Notification queued', 'notification.sent': 'Notification sent to simulated vendor', 'notification.delivered': 'Simulated delivery receipt', 'notification.received': 'Patient opened it in the portal',
    'notification.failed': 'Notification FAILED', 'notification.retry': 'Automatic retry', 'notification.manual_retry': 'Manual retry', 'notification.accepted': 'Patient acted on it', 'case.facility_provided': 'Patient named the imaging facility', 'case.images_status': 'Image status changed',
    'document.reviewed': 'Report marked reviewed', 'document.received': 'Document received', 'case.intake_completed': 'Intake sent', 'appointment.confirmed': 'Patient confirmed the appointment',
    'referral.received': 'Referral received', 'referral.question_sent': 'Question sent to the referring office (simulated fax)', 'records.request_sent': 'Records request sent (simulated fax)', 'document.arrived': 'Document arrived (simulated fax) \u2014 needs a match check',
    'insurance.checked': 'Eligibility checked (simulated)', 'insurance.auth_submitted': 'Prior-auth request submitted (simulated)', 'insurance.decision_recorded': 'Insurer decision recorded by staff', 'intake.invited': 'Intake form sent (simulated text)',
    'intake.reminder_sent': 'Intake reminder sent (simulated text)', 'intake.call_logged': 'Phone call logged', 'intake.confirmed': 'Patient confirmed helper-entered intake', 'case.red_flag': 'RED FLAG reported \u2014 urgent task', 'case.ready': 'Referral ready for appointment',
    'case.not_ready': 'Referral no longer ready', 'appointment.booked': 'Visit booked', 'presenter.script_step': 'Presenter script step (demo)', 'presenter.advance': 'Presenter simulated event (demo)', 'patient.contact_updated': 'Contact details updated',
    'chase.sent': 'Automatic follow-up sent (SIMULATED)', 'chase.stuck': 'STUCK after automatic follow-ups \u2014 handed to a person', 'surgery.item': 'Surgery checklist updated', 'surgery.planned': 'Surgical pathway started (example)',
    'surgery.done': 'Surgery date passed (demo script)', 'surgery.clearance_requested': 'Clearance requested (simulated fax)', 'checkin.answered': 'Post-op check-in answered', 'checkin.missed': 'Post-op check-in missed', 'summary.reviewed': 'Visit summary draft reviewed by a clinician' };
  function histText(e) {
    var base = HA[e.action] || e.action, d = null; try { d = e.detail ? JSON.parse(e.detail) : null; } catch (x) {} if (!d) return base;
    if (e.action === 'task.transition') return base + ': ' + d.from + ' \u2192 ' + d.to + (d.waiting_on ? ' (waiting on ' + d.waiting_on + ')' : '') + (d.outcome ? ' \u2014 outcome: ' + d.outcome : '') + (d.reason ? ' \u2014 reason: ' + d.reason : '');
    if (e.action === 'task.assigned' && d.after) return base + ': owner ' + nm(d.after.owner) + ', backup ' + nm(d.after.backup);
    if (d.length) return base + ' (' + PS.n(d.length) + ' characters)';
    var s = Object.keys(d).map(function (k) { return k + ': ' + (typeof d[k] === 'object' ? JSON.stringify(d[k]) : d[k]); }).join('; '); return base + (s ? ' \u2014 ' + s.slice(0, 160) : '');
  }
  function docAction(id) { PS.api('POST', '/api/o/docs/' + id + '/review', {}, { key: keyFor('doc' + id, '') }).then(function () { done('doc' + id); loadDetail(S.sel, false, true); }); }

  /* ----- composer (built once per opened item; never re-rendered by refresh) ----- */
  function buildComposer(d) {
    var id = d.task.id, st = ds(id), box = $('#d-composer');
    if (!d.allowed.can_reply) { box.appendChild(h('p', { class: 'istatus', text: d.allowed.reply_note || (d.task.status === 'Received' ? 'Assign an owner, backup and deadline first.' : d.task.status === 'Resolved' ? 'This request is resolved. Reopen it to reply.' : 'Replies are not available.') })); return; }
    if (st.text === null) { st.text = d.draft ? d.draft.body : ''; st.origin = d.draft ? d.draft.source : 'suggestion'; st.savedAt = d.draft && d.draft.source === 'saved' ? d.draft.saved_at : null; st.suggestion = d.draft && d.draft.source === 'suggestion' ? d.draft.body : (st.suggestion || null); st.label = d.draft && d.draft.label; }
    var lab = h('p', { class: 'tag', id: 'draft-label' });
    var ta = h('textarea', { id: 'reply-body', rows: '8', 'aria-describedby': 'reply-c draft-ind' }); ta.value = st.text;
    var cnt = h('p', { class: 'counter', id: 'reply-c' }), ind = h('p', { class: 'ind', id: 'draft-ind', role: 'status', 'aria-live': 'polite' });
    var send = h('button', { type: 'button', class: 'btn', id: 'reply-send' }, 'Send to patient'), sst = PS.statusEl('reply-st');
    var up = PS.bindCounter(ta, cnt, S.me.limits.message, send);
    function setLabel() {
      var edited = st.suggestion !== null && st.suggestion !== undefined && st.text !== st.suggestion;
      lab.textContent = st.origin === 'saved' && !st.suggestion ? 'Your saved draft' : (st.suggestion && !edited && st.origin !== 'own' ? 'Suggested draft \u00b7 canned template, simulated AI \u00b7 never sent automatically' : 'Your draft' + (st.suggestion ? ' (started from the canned suggestion)' : ''));
    }
    setLabel();
    ta.addEventListener('input', function () { st.text = ta.value; st.dirty = true; st.err = null; setLabel(); showInd(id); scheduleSave(id); });
    var kind = h('fieldset', {}, h('legend', { text: 'What kind of message is this?' }),
      h('label', { class: 'choice', for: 'k-reply' }, h('input', { type: 'radio', name: 'k', id: 'k-reply', value: 'reply' }), 'An answer or update'),
      h('label', { class: 'choice', for: 'k-ack' }, h('input', { type: 'radio', name: 'k', id: 'k-ack', value: 'ack' }), 'Acknowledgment only (“we got it”) \u2014 the request stays open'));
    kind.querySelector('#k-' + st.kind).checked = true; kind.addEventListener('change', function (e) { st.kind = e.target.value; });
    var own = h('button', { type: 'button', class: 'btn ghost', id: 'reply-own', onclick: function () { st.origin = 'own'; setLabel(); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length); PS.status(sst, 'This is now your own draft. The suggested wording is kept in the box so you can edit it \u2014 nothing was sent.', ''); } }, 'Write my own');
    var quote = h('button', { type: 'button', class: 'btn ghost', id: 'reply-quote', onclick: function () {
      var pm = (S.detail.conversation || []).filter(function (m) { return m.kind === 'patient_message' || m.kind === 'patient_question'; }).pop(); if (!pm) return;
      var q = pm.body.split('\n').map(function (l) { return '> ' + l; }).join('\n') + '\n\n'; ta.value = ta.value ? ta.value.replace(/\s*$/, '') + '\n\n' + q : q; ta.dispatchEvent(new Event('input')); ta.focus(); } }, 'Quote the patient’s message');
    send.addEventListener('click', function () {
      if (!ta.value.trim()) { PS.status(sst, 'Write a message first. An empty message can’t be sent.', 'bad'); ta.focus(); return; }
      if (!up()) { PS.status(sst, 'This message is too long to send. Shorten it.', 'bad'); return; }
      send.dataset.busy = '1'; send.disabled = true; clearTimeout(st.timer);
      var body = ta.value, k = st.kind;
      PS.api('POST', '/api/o/tasks/' + id + '/reply', { body: body, kind: k }, { key: keyFor('reply' + id, k + '\u0000' + body) }).then(function (r) {
        done('reply' + id); delete S.drafts[id]; ta.value = ''; send.dataset.busy = ''; up(); st.dirty = false; st.text = ''; st.suggestion = null;
        PS.status(sst, (k === 'ack' ? 'Acknowledgment sent. ' : 'Reply sent. ') + 'The request is still open (' + r.task.status + '). Close it with an outcome note when the need is met. A notification is queued (#' + r.notification_id + ').', 'ok');
        $('#draft-ind').textContent = 'Nothing pending.'; loadDetail(id, false, true); loadQueue(false);
      }).catch(function (e) { send.dataset.busy = ''; up(); if (!authFail(e)) PS.status(sst, 'Not sent: ' + PS.errText(e) + ' Your text is still here.', 'bad'); });
    });
    box.appendChild(h('div', { class: 'draftbox' }, lab, kind, h('label', { for: 'reply-body', text: 'Message the patient will see (exactly this text)' }), ta, cnt, ind, h('div', { class: 'row' }, send, own, quote), sst,
      h('p', { class: 'fine', text: 'Nothing is ever sent automatically. Sending a reply or acknowledgment does not resolve the request.' })));
    showInd(id);
  }
  function updateComposerState(d) { /* composer is intentionally untouched on refresh; only rebuild if it could not exist before */
    var box = $('#d-composer'); if (!box.querySelector('#reply-body') && d.allowed.can_reply) { while (box.children.length > 1) box.removeChild(box.lastChild); buildComposer(d); }
    else if (box.querySelector('#reply-body') && !d.allowed.can_reply) { while (box.children.length > 1) box.removeChild(box.lastChild); box.appendChild(h('p', { class: 'istatus', text: d.allowed.reply_note || (d.task.status === 'Resolved' ? 'This request is resolved. Reopen it to reply.' : 'Replies are not available right now.') })); }
  }
  function buildNotes(d) {
    var id = d.task.id, box = $('#d-notes'), ta = h('textarea', { id: 'note-body', rows: '3' }), c = h('p', { class: 'counter', id: 'note-c' }), b = h('button', { type: 'button', class: 'btn sm ghost' }, 'Add internal note'), st = PS.statusEl('note-st');
    var up = PS.bindCounter(ta, c, S.me.limits.note || 2000, b);
    b.addEventListener('click', function () { if (!ta.value.trim()) { PS.status(st, 'Write the note first.', 'bad'); return; } b.disabled = true; PS.api('POST', '/api/o/tasks/' + id + '/note', { body: ta.value }, { key: keyFor('note' + id, ta.value) }).then(function () { done('note' + id); ta.value = ''; up(); PS.status(st, 'Note added. The patient cannot see it.', 'ok'); loadDetail(id, false, true); }).catch(function (e) { PS.status(st, PS.errText(e), 'bad'); }).finally(function () { b.disabled = false; }); });
    box.appendChild(h('div', {}, h('label', { for: 'note-body', text: 'Staff-only note' }), ta, c, h('div', { class: 'row' }, b), st));
  }
  function updateActions(d) {
    var t = d.task, sig = [t.status, t.owner, t.backup, t.deadline, d.allowed.next.join(','), d.allowed.can_resolve].join('|'); var box = $('#d-actions');
    if (box.dataset.sig === sig) return;
    if (box.contains(document.activeElement) && box.dataset.sig) return;           /* never rebuild under the user's cursor */
    box.dataset.sig = sig; replaceIn('d-actions', []);
    var st = PS.statusEl('act-st');
    if (d.allowed.urgent_readonly) { box.appendChild(h('p', { class: 'small', id: 'act-ro', text: 'Status: ' + t.status + '. ' + d.allowed.urgent_note + ' You can still add an internal note below.' })); return; }
    if (t.status !== 'Resolved') {
      var ow = h('select', { id: 'as-owner' }), bk = h('select', { id: 'as-backup' }), dl = h('input', { type: 'date', id: 'as-dl', value: t.deadline ? new Intl.DateTimeFormat('en-CA', { timeZone: 'America/Los_Angeles' }).format(new Date(t.deadline)) : ymd(1) });
      S.staff.forEach(function (u) { [ow, bk].forEach(function (s, i) { var o = h('option', { value: u.key, text: u.name + ' (' + (u.team || u.role) + ')' }); if ((i === 0 ? t.owner : t.backup) === u.key) o.selected = true; s.appendChild(o); }); });
      box.appendChild(h('details', {}, h('summary', { class: 'btn ghost sm', text: 'Change owner, backup or deadline' }), h('div', { class: 'field' }, h('label', { for: 'as-owner', text: 'Owner' }), ow), h('div', { class: 'field' }, h('label', { for: 'as-backup', text: 'Backup (must be someone else)' }), bk), h('div', { class: 'field' }, h('label', { for: 'as-dl', text: 'Internal deadline (5 PM PT that day)' }), dl),
        h('button', { type: 'button', class: 'btn sm', onclick: function () { PS.api('POST', '/api/o/tasks/' + t.id + '/assign', { owner: ow.value, backup: bk.value, deadline: dl.value }, { key: keyFor('assign' + t.id, ow.value + bk.value + dl.value) }).then(function () { done('assign' + t.id); PS.status(st, 'Assignment saved.', 'ok'); box.dataset.sig = ''; loadDetail(t.id, false, true); loadQueue(false); }).catch(function (e) { PS.status(st, PS.errText(e), 'bad'); }); } }, 'Save assignment')));
    }
    var row = h('div', { class: 'row' }), form = h('div', { id: 'st-form' });
    function trans(to, body, ok) { return PS.api('POST', '/api/o/tasks/' + t.id + '/transition', Object.assign({ to: to }, body), { key: keyFor('tr' + t.id, to + JSON.stringify(body)) }).then(function () { done('tr' + t.id); PS.status(st, ok, 'ok'); box.dataset.sig = ''; loadDetail(t.id, false, true); loadQueue(false); }).catch(function (e) { PS.status(st, PS.errText(e), 'bad'); }); }
    function open(title, fields, submitText, onSubmit) { PS.clear(form); var wrap = h('div', { class: 'card' }, h('h3', { text: title })); fields.forEach(function (f) { wrap.appendChild(f); }); var b = h('button', { type: 'button', class: 'btn' }, submitText); b.addEventListener('click', function () { b.disabled = true; Promise.resolve(onSubmit()).finally(function () { b.disabled = false; }); }); wrap.appendChild(b); form.appendChild(wrap); var f0 = wrap.querySelector('input,textarea'); if (f0) f0.focus(); }
    function fld(label, el, id) { el.id = id; return h('div', { class: 'field' }, h('label', { for: id, text: label }), el); }
    d.allowed.next.forEach(function (to) {
      if (to === 'Assigned') return;
      if (to === 'In Progress' && t.status === 'Resolved') row.appendChild(h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { var r = h('textarea', { rows: '2' }); open('Reopen this request', [fld('Why is it being reopened?', r, 'f-reopen')], 'Reopen', function () { return trans('In Progress', { reason: r.value }, 'Reopened.'); }); } }, 'Reopen\u2026'));
      else if (to === 'In Progress') row.appendChild(h('button', { type: 'button', class: 'btn sm', onclick: function () { trans('In Progress', {}, 'Marked In Progress.'); } }, t.status === 'Waiting' ? 'Resume work' : 'Start work'));
      else if (to === 'Waiting') row.appendChild(h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { var w = h('input', { type: 'text', maxlength: '200' }), fd = h('input', { type: 'date', value: ymd(3) }); open('Mark as waiting', [fld('Waiting on whom or what?', w, 'f-wo'), fld('Follow up by (date)', fd, 'f-wd')], 'Mark waiting', function () { return trans('Waiting', { waiting_on: w.value, follow_up_by: fd.value }, 'Marked Waiting. The patient sees what we are waiting on.'); }); } }, 'Mark waiting\u2026'));
      else if (to === 'Resolved') { var rb = h('button', { type: 'button', class: 'btn ghost sm', onclick: function () { var o = h('textarea', { rows: '3' }); var c = h('p', { class: 'counter' }); open('Resolve this request', [h('p', { class: 'small', text: 'Resolving closes the request. Sending a reply or acknowledgment does not. You will be recorded as the person who resolved it.' }), fld('Outcome: what was done or decided?', o, 'f-outcome'), c], 'Resolve with this outcome', function () { return trans('Resolved', { outcome: o.value }, 'Resolved.'); }); PS.bindCounter(o, c, 1000); } }, 'Resolve\u2026'); if (!d.allowed.can_resolve) { rb.setAttribute('aria-disabled', 'true'); rb.disabled = true; } row.appendChild(rb); }
    });
    box.appendChild(h('p', { class: 'small' }, 'Status: ', h('b', { text: t.status }), '. Possible next steps:'));
    box.appendChild(row); if (!d.allowed.can_resolve && t.status !== 'Resolved') box.appendChild(h('p', { class: 'small', text: d.allowed.resolve_note })); box.appendChild(form);
    if (t.status !== 'Resolved') { var vs = h('input', { type: 'text', id: 'ver-src', maxlength: '120' }); box.appendChild(h('div', { class: 'field' }, h('label', { for: 'ver-src', text: 'Record a verified update (what did you check, and with whom?)' }), vs,
      h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn sm ghost', onclick: function () { PS.api('POST', '/api/o/tasks/' + t.id + '/verify', { source_note: vs.value }, { key: keyFor('ver' + t.id, vs.value) }).then(function () { done('ver' + t.id); PS.status(st, 'Verified update recorded with your name and the time. The patient sees it as “Last verified update”.', 'ok'); box.dataset.sig = ''; loadDetail(t.id, false, true); }).catch(function (e) { PS.status(st, PS.errText(e), 'bad'); }); } }, 'Record verified update')))); }
    box.appendChild(st);
  }

  /* ---------- other pages ---------- */
  function pageNotifs() {
    document.title = 'DEMO · Notifications · Office workspace (prototype)'; PS.clear(main); S.built = null;
    var box = h('div', {}, h('p', { text: 'Loading\u2026' }));
    main.appendChild(h('div', {}, h('h1', { text: 'Notifications to patients' }), h('p', { text: 'States: queued \u2192 sent \u2192 delivered \u2192 received (patient opened it) \u2192 accepted (patient acted). “Delivered” comes from a simulated vendor. A failure after the retry limit creates an exception task in the queue.' }), h('div', { class: 'card' }, box)));
    PS.api('GET', '/api/o/notifications').then(function (r) {
      PS.clear(box); if (!r.notifications.length) { box.appendChild(h('p', { text: 'None yet.' })); return; }
      box.appendChild(h('ul', { class: 'plain' }, r.notifications.map(function (n) { return notifLi(n, n.task_id); })));
    }).catch(function (e) { authFail(e); });
  }
  function pageReports() {
    document.title = 'DEMO · Reports · Office workspace (prototype)'; PS.clear(main);
    var box = h('div', {}, h('p', { text: 'Loading\u2026' })); main.appendChild(h('div', {}, h('h1', { text: 'Reports' }), box));
    PS.api('GET', '/api/o/reports').then(function (r) {
      PS.clear(box); var m = function (label, v, note) { return h('tr', {}, h('th', { scope: 'row', text: label }), h('td', { text: v }), h('td', { class: 'small muted', text: note || '' })); };
      var med = function (o) { return o.n ? o.median + ' min (n=' + o.n + ')' : 'No measurements yet'; };
      box.appendChild(h('p', { class: 'istatus', text: 'Measured from this prototype database only (' + r.measured_from + '). Nothing here is estimated or invented.' }));
      box.appendChild(h('div', { class: 'card tablewrap' }, h('table', {}, h('caption', { class: 'sr', text: 'Measured values' }), h('thead', {}, h('tr', {}, h('th', { scope: 'col', text: 'Measure' }), h('th', { scope: 'col', text: 'Value' }), h('th', { scope: 'col', text: 'Notes' }))), h('tbody', {},
        m('Requests (all)', String(r.tasks_total), r.seeded_tasks + ' are seeded examples, ' + r.live_tasks + ' were created by use'),
        m('By status', Object.keys(r.tasks_by_status).map(function (k) { return k + ' ' + r.tasks_by_status[k]; }).join(' \u00b7 ')),
        m('Overdue open requests', String(r.overdue_open)), m('Open requests with no owner', String(r.unowned_open)),
        m('Status changes', String(r.status_changes), 'Counted from the audit log'), m('Staff touches (all)', String(r.staff_touches_total), 'Replies, notes, assignments, status changes; viewing is not counted'),
        m('Touches per resolved live request', r.touches_per_resolved_live_task.n ? r.touches_per_resolved_live_task.mean + ' (n=' + r.touches_per_resolved_live_task.n + ')' : 'No resolved live requests yet'),
        m('Time to first acknowledgment', med(r.minutes_to_first_acknowledgment), 'Live requests only'), m('Time to first reply', med(r.minutes_to_first_reply), 'Live requests only'),
        m('Notifications', Object.keys(r.notifications).map(function (k) { return k + ' ' + r.notifications[k]; }).join(' \u00b7 ')), m('Open exception tasks', String(r.open_exception_tasks))))));
      box.appendChild(h('div', { class: 'card gold' }, h('h2', { text: 'How to read these' }), h('ul', {}, r.notes.map(function (n) { return h('li', { text: n }); }))));
    }).catch(function (e) { if (!authFail(e)) { PS.clear(box); box.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); } });
  }
  function pageAudit() {
    document.title = 'DEMO · Audit log · Office workspace (prototype)'; PS.clear(main);
    var box = h('div', { class: 'tablewrap' }, h('p', { text: 'Loading\u2026' })); main.appendChild(h('div', {}, h('h1', { text: 'Audit log' }), h('p', { text: 'Append-only: the database refuses edits and deletes. Newest first, last 200 events. Viewing a request is also logged.' }), h('div', { class: 'card' }, box)));
    PS.api('GET', '/api/o/audit?limit=200').then(function (r) {
      PS.clear(box); box.appendChild(h('table', {}, h('caption', { class: 'sr', text: 'Audit events' }), h('thead', {}, h('tr', {}, ['When', 'Who', 'What', 'Detail'].map(function (x) { return h('th', { scope: 'col', text: x }); }))),
        h('tbody', {}, r.events.map(function (e) { return h('tr', {}, h('td', { text: PS.fmtDT(e.ts) }), h('td', { text: e.actor_name + ' (' + e.actor_role + ')' }), h('td', { text: e.action }), h('td', { class: 'small', text: (e.detail || '').slice(0, 200) })); }))));
    }).catch(function (e) { if (!authFail(e)) { PS.clear(box); box.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); } });
  }
  function pageSettings() {
    document.title = 'DEMO · Settings · Office workspace (prototype)'; PS.clear(main);
    var inp = h('input', { type: 'text', id: 'rt', maxlength: '80' }), st = PS.statusEl('rt-st');
    main.appendChild(h('div', {}, h('h1', { text: 'Settings' }), h('div', { class: 'card' }, h('h2', { text: 'Patient reply target' }), h('p', { text: 'If you set a target, patients see “We aim to reply …” on open requests. If this is empty, patients are told no time is promised. Set it only when the office can keep it.' }),
      h('label', { for: 'rt', text: 'Target wording, for example: within 1 business day' }), inp, h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn', onclick: function () { PS.api('PUT', '/api/o/settings', { patient_reply_target: inp.value }).then(function (r) { PS.status(st, r.patient_reply_target ? 'Patients will now see: “We aim to reply ' + r.patient_reply_target + '”.' : 'Target cleared. Patients are told no time is promised.', 'ok'); }).catch(function (e) { PS.status(st, PS.errText(e), 'bad'); }); } }, 'Save target')), st)));
    /* preview19 Prompt B: post-op call-back wording - EMPTY by default, so patients are never promised a call or a response time */
    var cbi = h('input', { type: 'text', id: 'cbp', maxlength: '160' }), cbst = PS.statusEl('cbp-st');
    main.appendChild(h('div', { class: 'card', id: 'set-cbp' }, h('h2', { text: 'After-surgery call-back wording' }),
      h('p', { text: 'Empty (the default): patients are NOT told anyone will call them or how fast. Only fill this in when the practice has decided it and can keep it. It is shown word for word after a post-op check-in.' }),
      h('label', { for: 'cbp', text: 'Wording shown to patients (example only: “A nurse aims to call you the same business day.”)' }), cbi,
      h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn', id: 'cbp-save', onclick: function () { PS.api('PUT', '/api/o/settings', { postop_callback_promise: cbi.value }).then(function (r) { PS.status(cbst, r.postop_callback_promise ? 'Patients will now see: “' + r.postop_callback_promise + '”' : 'Cleared. Patients are not promised a call or a time.', 'ok'); }).catch(function (e) { PS.status(cbst, PS.errText(e), 'bad'); }); } }, 'Save wording')), cbst));
    /* preview19 Prompt C: wording shown when the portal would otherwise say "we will call you" - EMPTY by default (patients get the phone number instead) */
    var cxi = h('input', { type: 'text', id: 'cxp', maxlength: '160' }), cxst = PS.statusEl('cxp-st');
    main.appendChild(h('div', { class: 'card', id: 'set-callexp' }, h('h2', { text: 'Call-back expectation (outside surgery)' }),
      h('p', { text: 'Empty (the default): patients are asked to call us and are never told that someone will call them. Fill this in only when the practice has decided it and can keep it.' }),
      h('label', { for: 'cxp', text: 'Wording shown to patients (example only: \u201cOur front desk will call you to arrange this.\u201d)' }), cxi,
      h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn', id: 'cxp-save', onclick: function () { PS.api('PUT', '/api/o/settings', { patient_call_expectation: cxi.value }).then(function (r) { PS.status(cxst, r.patient_call_expectation ? 'Patients will now see: \u201c' + r.patient_call_expectation + '\u201d' : 'Cleared. Patients are asked to call us instead.', 'ok'); }).catch(function (e) { PS.status(cxst, PS.errText(e), 'bad'); }); } }, 'Save wording')), cxst));
    var prio = h('div', { id: 'prio-rules' }, h('p', { text: 'Loading\u2026' }));
    main.appendChild(h('div', { class: 'card', id: 'set-prio' }, h('h2', { text: 'Work-queue priority rules (read only)' }), prio));
    PS.api('GET', '/api/o/priority-rules').then(function (r) {
      PS.clear(prio); prio.appendChild(h('p', { class: 'istatus warn', id: 'prio-status', text: r.status }));
      prio.appendChild(h('ol', { class: 'priolist', id: 'prio-list' }, r.rules.map(function (x) { return h('li', {}, h('b', { text: x.id + '. ' }), x.rule, h('p', { class: 'small muted', text: x.basis })); })));
    }).catch(function (e) { PS.clear(prio); prio.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); });
    var rules = h('div', { id: 'esc-rules' }, h('p', { text: 'Loading…' }));
    main.appendChild(h('div', { class: 'card', id: 'set-esc' }, h('h2', { text: 'Post-op escalation rules (read only)' }), rules));
    PS.api('GET', '/api/o/settings').then(function (r) { inp.value = r.patient_reply_target || ''; cbi.value = r.postop_callback_promise || ''; cxi.value = r.patient_call_expectation || ''; });
    PS.api('GET', '/api/o/escalation-rules').then(function (r) {
      PS.clear(rules);
      rules.appendChild(h('p', { class: 'istatus warn', id: 'esc-status', text: r.status + (r.approved_by ? '' : ' Approved by: nobody yet.') }));
      rules.appendChild(h('div', { class: 'tablewrap' }, h('table', { class: 'tbl', id: 'esc-table' }, h('thead', {}, h('tr', {}, ['Rule', 'Looks at', 'Match', 'Level', 'Why'].map(function (x) { return h('th', { scope: 'col', text: x }); }))),
        h('tbody', {}, r.rules.map(function (x) { return h('tr', {}, h('td', { text: x.id }), h('td', { text: x.applies_to }), h('td', { class: 'mono small', text: x.match }), h('td', { text: x.level }), h('td', { text: x.why })); })))));
      rules.appendChild(h('p', { class: 'small', text: 'Levels: ' + r.levels.map(function (l) { return l.key + ' = ' + l.label; }).join('; ') + '. The highest matching level wins; nothing can lower it.' }));
    }).catch(function (e) { PS.clear(rules); rules.appendChild(h('p', { class: 'istatus bad', text: PS.errText(e) })); });
  }
})();
