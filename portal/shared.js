/* Shared client helpers.  The ONLY thing this code keeps in browser storage is the "Larger text" preference
   (localStorage key "ps.largeText", value "1", removed when turned off).  No health data, names or messages are ever stored there.
   The session token lives in an httpOnly cookie set by the server (the page never sees it).
   In the static snapshot, PS.api is routed to an in-browser mock instead of fetch(). */
(function () {
  'use strict';
  var PS = window.PS = {};
  var MOCK = null;
  try { if (window.parent !== window && window.parent.__PS_MOCK) MOCK = window.parent.__PS_MOCK; } catch (e) {}
  PS.snapshot = !!MOCK;
  PS.published = !!(MOCK && MOCK.banner);   /* the online demo (recordings, no server) */
  PS.BANNER = PS.snapshot && MOCK.banner ? MOCK.banner : PS.snapshot ? 'Static snapshot \u00b7 server rules simulated in your browser \u00b7 fictional data \u00b7 not production' : 'Prototype server \u00b7 fictional data \u00b7 not production \u00b7 not HIPAA-compliant';
  PS.uuid = function () { return (window.crypto && crypto.randomUUID) ? crypto.randomUUID() : 'k' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10); };
  PS.api = function (method, path, body, o) {
    o = o || {};
    /* preview19 publish: a write that a demo recording cannot do is reported calmly (see PS.status), never as a fake success */
    if (MOCK) return MOCK.call(method, path, body, { key: o.key, app: PS.app }).then(function (r) { PS._demoAt = 0; return r; }, function (e) { if (PS.isDemo(e)) { PS._demoAt = Date.now(); PS._demoMsg = e.message; } throw e; });
    var headers = { 'Content-Type': 'application/json', 'X-PS-Client': '1' };
    if (o.key) headers['Idempotency-Key'] = o.key;
    return fetch(path, { method: method, headers: headers, body: body === undefined ? undefined : JSON.stringify(body), credentials: 'same-origin', cache: 'no-store' }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (data) {
        if (!res.ok) { var e = new Error((data && data.message) || 'Request failed'); e.status = res.status; e.data = data || {}; throw e; }
        return data;
      });
    });
  };
  /* tiny element builder: text is always inserted as text (never HTML) */
  PS.h = function (tag, attrs) {
    var el = document.createElement(tag); attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k]; if (v === null || v === undefined || v === false) return;
      if (k === 'class') el.className = v; else if (k === 'text') el.textContent = v; else if (k.slice(0, 2) === 'on') el.addEventListener(k.slice(2), v);
      else if (k === 'value') el.value = v; else el.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) PS.add(el, arguments[i]);
    return el;
  };
  PS.add = function (el, c) { if (c === null || c === undefined || c === false) return; if (Array.isArray(c)) c.forEach(function (x) { PS.add(el, x); }); else el.appendChild(c.nodeType ? c : document.createTextNode(String(c))); };
  PS.clear = function (el) { while (el.firstChild) el.removeChild(el.firstChild); return el; };
  PS.$ = function (s, c) { return (c || document).querySelector(s); };
  var TZ = 'America/Los_Angeles';
  function fmt(iso, opts) { if (!iso) return ''; return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: TZ }, opts)).format(new Date(iso)); }
  PS.fmtDate = function (iso) { return fmt(iso, { weekday: 'long', month: 'long', day: 'numeric' }); };
  PS.fmtTime = function (iso) { return fmt(iso, { hour: 'numeric', minute: '2-digit' }) + ' PT'; };
  PS.fmtDT = function (iso) { return fmt(iso, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) + ' PT'; };
  PS.fmtDay = function (iso) { return fmt(iso, { month: 'short', day: 'numeric' }); };
  PS.count = function (s) { return Array.from(s || '').length; };      /* code points: same rule as the server */
  PS.n = function (n) { return new Intl.NumberFormat('en-US').format(n); };

  /* ---- inline SVG icons (hand-drawn 24x24 strokes; no icon library) ---- */
  var ICONS = {
    home: ['M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z'],
    visits: ['M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z', 'M8 2.5V6', 'M16 2.5V6', 'M4 10h16', 'M8 14h3'],
    messages: ['M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H10l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z'],
    records: ['M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z', 'M14 3v5h5', 'M9 13h6', 'M9 17h6'],
    settings: ['M4 7h9', 'M17 7h3', 'M15 5v4', 'M4 17h3', 'M11 17h9', 'M9 15v4'],
    phone: ['M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z'],
    check: ['M5 12.5l4.5 4.5L19 7.5'],
    chevron: ['M9 6l6 6-6 6'],
    back: ['M15 6l-6 6 6 6'],
    clock: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z', 'M12 7v5l3 2'],
    alert: ['M12 3 2 20h20z', 'M12 9v5', 'M12 17.2v.3'],
    text: ['M4 7V5h10v2', 'M9 5v14', 'M7 19h4', 'M14 13v-1h6v1', 'M17 12v7', 'M15.5 19h3'],
    signout: ['M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3', 'M10 16l-4-4 4-4', 'M6 12h10'],
    clipboard: ['M9 3h6v3H9z', 'M7 4.5H6a1 1 0 0 0-1 1V20a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V5.5a1 1 0 0 0-1-1h-1', 'M9 12h6', 'M9 16h4'],
    pulse: ['M3 12h4l2-5 4 10 2-5h6'],
    board: ['M4 4h4v16H4z', 'M10 4h4v10h-4z', 'M16 4h4v13h-4z'],
    bell: ['M6 16v-5a6 6 0 0 1 12 0v5l2 2H4z', 'M10 20a2 2 0 0 0 4 0'],
    chart: ['M4 20V10', 'M10 20V4', 'M16 20v-7', 'M3 20h18'],
    list: ['M9 6h11', 'M9 12h11', 'M9 18h11', 'M4.5 6h.01', 'M4.5 12h.01', 'M4.5 18h.01'],
    people: ['M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M2 21a7 7 0 0 1 14 0', 'M16 3.5a4 4 0 0 1 0 7', 'M18 14a6 6 0 0 1 4 7'],
    flag: ['M5 21V4', 'M5 4h11l-2 4 2 4H5'],
    sparkle: ['M12 3v4', 'M12 17v4', 'M3 12h4', 'M17 12h4', 'M6 6l2.5 2.5', 'M15.5 15.5 18 18', 'M18 6l-2.5 2.5', 'M8.5 15.5 6 18'],
    map: ['M12 21s-7-6.2-7-12a7 7 0 0 1 14 0c0 5.8-7 12-7 12z', 'M12 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z'],
    play: ['M7 4l13 8-13 8z'],
    person: ['M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z', 'M4 21a8 8 0 0 1 16 0']
  };
  PS.icon = function (name, cls) {
    var NS = 'http://www.w3.org/2000/svg', s = document.createElementNS(NS, 'svg');
    s.setAttribute('viewBox', '0 0 24 24'); s.setAttribute('class', 'ic' + (cls ? ' ' + cls : '')); s.setAttribute('aria-hidden', 'true'); s.setAttribute('focusable', 'false');
    (ICONS[name] || []).forEach(function (d) { var p = document.createElementNS(NS, 'path'); p.setAttribute('d', d); s.appendChild(p); });
    return s;
  };
  PS.checkSvg = function () { var s = PS.icon('check'); s.setAttribute('class', ''); return s; };
  /* ---- "Larger text": remembered on this device (localStorage holds only this preference) ---- */
  PS.LS_KEY = 'ps.largeText';
  function lsGet() { try { return window.localStorage.getItem(PS.LS_KEY); } catch (e) { return null; } }
  function lsSet(on) { try { if (on) window.localStorage.setItem(PS.LS_KEY, '1'); else window.localStorage.removeItem(PS.LS_KEY); return true; } catch (e) { return false; } }
  if (lsGet() === '1') document.documentElement.classList.add('big');
  PS.isBig = function () { return document.documentElement.classList.contains('big'); };
  PS.setBig = function (on) {
    document.documentElement.classList.toggle('big', !!on); var saved = lsSet(!!on);
    Array.prototype.forEach.call(document.querySelectorAll('[data-textsize]'), function (b) { b.setAttribute('aria-pressed', on ? 'true' : 'false'); });
    Array.prototype.forEach.call(document.querySelectorAll('input[data-ts]'), function (r) { r.checked = (r.value === 'large') === !!on; });
    return saved;
  };
  PS.bindTextSize = function (btn) {
    if (!btn) return; btn.setAttribute('data-textsize', ''); btn.setAttribute('aria-pressed', PS.isBig() ? 'true' : 'false');
    btn.addEventListener('click', function () { PS.setBig(!PS.isBig()); });
  };
  /* preview19: an explicit two-choice text-size control ("Standard" / "Larger") instead of a bare toggle */
  PS.textSizeControl = function (fs, prefix) {
    PS.clear(fs); fs.classList.add('textsize');
    fs.appendChild(PS.h('legend', { text: 'Text size' }));
    var row = PS.h('div', { class: 'chips' });
    [['standard', 'Standard', 'Aa'], ['large', 'Larger', 'Aa']].forEach(function (o) {
      var r = PS.h('input', { type: 'radio', name: prefix + '-ts', id: prefix + '-ts-' + o[0], value: o[0], 'data-ts': '' }); r.checked = (o[0] === 'large') === PS.isBig();
      r.addEventListener('change', function () { if (r.checked) PS.setBig(o[0] === 'large'); });
      row.appendChild(PS.h('label', { class: 'choice chipc ts-' + o[0], for: r.id }, r, PS.h('span', { class: 'tick', 'aria-hidden': 'true' }, PS.checkSvg()), PS.h('span', { class: 'aa', 'aria-hidden': 'true', text: o[2] }), o[1]));
    });
    fs.appendChild(row);
    fs.appendChild(PS.h('p', { class: 'small muted', text: '“Larger” makes all writing in the portal bigger on this device. You can change it back at any time.' }));
    return fs;
  };
  /* preview19: keep the focused field (and its error) visible above the on-screen keyboard and the phone tab bar.
     Uses visualViewport where the browser has it; html.kb-open hides the fixed tab bar while the keyboard is up. */
  PS.keepInView = function (el) {
    if (!el || !el.getBoundingClientRect) return;
    var vv = window.visualViewport, top = vv ? vv.offsetTop : 0, hgt = vv ? vv.height : window.innerHeight;
    var nav = document.querySelector('nav.tabbar'), cover = 0;
    if (nav && !nav.hidden && getComputedStyle(nav).position === 'fixed' && getComputedStyle(nav).display !== 'none') cover = nav.getBoundingClientRect().height;
    var r = el.getBoundingClientRect(), err = el.getAttribute('aria-describedby'), bottom = r.bottom;
    if (err) err.split(/\s+/).forEach(function (id) { var e = document.getElementById(id); if (e && e.offsetParent !== null) { var q = e.getBoundingClientRect(); if (q.bottom > bottom && q.bottom - r.top < hgt * 0.8) bottom = q.bottom; } });
    var visTop = top + 8, visBottom = top + hgt - cover - 12;
    if (r.top < visTop || bottom > visBottom) window.scrollBy(0, r.top < visTop ? r.top - visTop : Math.min(bottom - visBottom, r.top - visTop));
  };
  (function () {
    var vv = window.visualViewport, t = null;
    function kb() { if (!vv) return; var open = window.innerHeight - vv.height > 120; document.documentElement.classList.toggle('kb-open', open); }
    function later(el) { clearTimeout(t); t = setTimeout(function () { kb(); PS.keepInView(el); }, 320); }
    document.addEventListener('focusin', function (e) { var el = e.target; if (el && el.matches && el.matches('input:not([type=radio]):not([type=checkbox]), textarea, select')) later(el); });
    document.addEventListener('focusout', function () { setTimeout(kb, 200); });
    if (vv) vv.addEventListener('resize', function () { kb(); var a = document.activeElement; if (a && a.matches && a.matches('input, textarea, select')) later(a); });
  })();
  document.addEventListener('DOMContentLoaded', function () {
    Array.prototype.forEach.call(document.querySelectorAll('[data-icon]'), function (el) { if (!el.querySelector('svg.ic')) el.insertBefore(PS.icon(el.getAttribute('data-icon')), el.firstChild); });
  });
  /* inline, non-blocking status message (aria-live) — replaces toasts */
  PS.DEMO_SAVE = 'Demo recording: in the full version this saves to the server. Nothing was sent or saved here.';
  PS.isDemo = function (e) { return !!(e && e.data && e.data.error === 'demo_recording'); };
  PS.status = function (el, text, kind) {
    if (kind === 'bad' && PS._demoAt && Date.now() - PS._demoAt < 3000) { el.className = 'istatus demo'; el.textContent = PS._demoMsg || PS.DEMO_SAVE; return; }
    el.className = 'istatus' + (kind ? ' ' + kind : ''); el.textContent = text || ''; };
  PS.statusEl = function (id) { return PS.h('p', { id: id, class: 'istatus', role: 'status', 'aria-live': 'polite' }); };
  /* counter bound to a textarea/input, same counting rule as the server */
  PS.bindCounter = function (field, counterEl, max, sendBtn) {
    function upd() { var n = PS.count(field.value); var over = n > max;
      counterEl.textContent = over ? PS.n(n) + ' characters \u2014 ' + PS.n(n - max) + ' over the ' + PS.n(max) + ' limit. Shorten it to send.' : PS.n(n) + ' of ' + PS.n(max) + ' characters';
      counterEl.className = 'counter' + (over ? ' over' : ''); field.setAttribute('aria-invalid', over ? 'true' : 'false'); if (sendBtn) sendBtn.disabled = over || (sendBtn.dataset.busy === '1'); return !over; }
    field.addEventListener('input', upd); upd(); return upd;
  };
  PS.errText = function (e) {
    if (e && !e.status && !(e.data && e.data.message) && /fetch|network|load failed/i.test(String(e.message || ''))) return 'We couldn\u2019t reach the server (check your internet connection).';   /* preview19 Prompt D: no raw "Failed to fetch" */
    return (e && e.data && e.data.message) || (e && e.message) || 'Something went wrong.';
  };
  PS.chipFor = function (status) { return { 'Received': 'info', 'Assigned': 'info', 'In Progress': 'warn', 'Waiting': 'warn', 'Resolved': 'ok' }[status] || ''; };
  PS.statusMark = { 'Received': '\u25cb ', 'Assigned': '\u25d4 ', 'In Progress': '\u25d1 ', 'Waiting': '\u23f3 ', 'Resolved': '\u2713 ' };
  /* compact bottom sheet using native <dialog>: modal, focus trap, Esc closes, focus returns to opener */
  PS.openSheet = function (dlg, opener) {
    if (!dlg.showModal) { dlg.setAttribute('open', ''); return; }
    dlg.showModal(); var h = dlg.querySelector('h2'); if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
    dlg.addEventListener('close', function () { if (opener && opener.focus) opener.focus(); }, { once: true });
    dlg.addEventListener('keydown', function (e) {                       /* explicit focus trap (Tab / Shift+Tab wrap inside the sheet) */
      if (e.key !== 'Tab') return;
      var f = Array.prototype.filter.call(dlg.querySelectorAll('a[href],button:not([disabled]),input,select,textarea,[tabindex]:not([tabindex="-1"])'), function (x) { return x.offsetParent !== null; });
      if (!f.length) return; var first = f[0], last = f[f.length - 1];
      if (e.shiftKey && (document.activeElement === first || document.activeElement === dlg.querySelector('h2'))) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  };
  PS.header = function (opts) {
    var bar = PS.h('div', { class: 'site' + (opts.presenter ? ' presbar' : '') }, PS.h('div', { class: 'wrap' },
      PS.h('img', { class: 'logo', src: 'assets/logo-light.png', alt: 'Premier Spine', width: '170', height: '40' }),
      PS.h('span', { class: 'appname', text: opts.title }), opts.right || null));
    return bar;
  };
  PS.proto = function (extra) { return PS.h('div', { class: 'protobar', role: 'region', 'aria-label': 'Prototype notice', text: PS.BANNER + (extra ? ' \u00b7 ' + extra : '') }); };
  /* In the srcdoc iframes of the static snapshot, a bare "#..." link would resolve against the OUTER file's URL, so handle in-page links here. */
  if (PS.snapshot) document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[href^="#"]'); if (!a) return; e.preventDefault();
    var href = a.getAttribute('href'); if (href === '#main') { var m = document.getElementById('main'); if (m) m.focus(); } else location.hash = href;
  });
  /* DEMO notice: always present, never dismissible, in normal page flow (never fixed/sticky, so it cannot cover content or controls).
     The pages ship it in their HTML; this only re-adds it if a page somehow lacks it. */
  PS.DEMO = 'Demo \u2014 example data only, not a real patient portal';
  document.addEventListener('DOMContentLoaded', function () {
    if (!document.getElementById('demobar')) { var d = PS.h('div', { class: 'demobar', id: 'demobar', role: 'region', 'aria-label': 'Demo notice' }, PS.h('span', { class: 'demotag', 'aria-hidden': 'true', text: 'DEMO' }), ' ', PS.h('span', { id: 'demotext', text: PS.DEMO })); document.body.insertBefore(d, document.body.firstChild); }
    if (!/^DEMO/.test(document.title)) document.title = 'DEMO \u00b7 ' + document.title;
  });
  document.addEventListener('DOMContentLoaded', function () { var b = document.getElementById('banner'); if (b) b.textContent = PS.BANNER + (PS.app === 'presenter' ? ' \u00b7 presenter controls' : ''); });

  /* Phone tab bar: fixed to the bottom only while it stays small. With very large text it would cover a big
     part of the screen, so it drops back into the page flow (html.tabbar-static). The body padding always
     equals the bar's real height, so it never covers content. */
  PS.fitTabbar = function () {
    var nav = document.querySelector('nav.tabbar'), root = document.documentElement;
    var want = false, hv = '';
    if (nav && !nav.hidden && window.innerWidth < 860) {
      var hgt = nav.getBoundingClientRect().height;   /* same grid layout in both modes, so this is the bar's real height */
      if (hgt > Math.min(110, window.innerHeight * 0.16)) want = true; else hv = Math.ceil(hgt) + 'px';
    }
    if (root.classList.contains('tabbar-static') !== want) root.classList.toggle('tabbar-static', want);
    if (root.style.getPropertyValue('--tabbar-h') !== hv) { if (hv) root.style.setProperty('--tabbar-h', hv); else root.style.removeProperty('--tabbar-h'); }
  };
  document.addEventListener('DOMContentLoaded', function () {
    var nav = document.querySelector('nav.tabbar'); if (!nav) return;
    var busy = false, run = function () { if (busy) return; busy = true; requestAnimationFrame(function () { PS.fitTabbar(); busy = false; }); };
    if (window.ResizeObserver) { var ro = new ResizeObserver(run); ro.observe(nav); ro.observe(document.documentElement); }
    window.addEventListener('resize', run);
    new MutationObserver(run).observe(nav, { attributes: true, attributeFilter: ['hidden'] });
    new MutationObserver(run).observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'style'] });
    run();
  });
})();
