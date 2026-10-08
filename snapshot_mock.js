/* STATIC SNAPSHOT MOCK — re-implements the prototype server's rules in the browser, with seeded FICTIONAL data held in memory only.
   It is NOT the server: it cannot prove server-side authorization, signed tokens, SQLite persistence, append-only triggers or restart durability.
   Rules (patterns, FAQ, routes, transitions, limits) are generated from server.py's export_rules() at build time. */
(function () {
  'use strict';
  var R = /*__RULES__*/null;
  var REC = /*__REC__*/null, replay = null;  /* Pass 2: recorded key states from the real server (read-only replay) */
  var PTZ = 'America/Los_Angeles', MAXN = R.MAX, TEL = R.PHONE;
  var db, sess = { portal: null, office: null }, presenter = false, nid = {};
  function E(status, error, message, extra) { var e = new Error(message); e.status = status; e.data = Object.assign({ error: error, message: message }, extra || {}); return e; }
  function iso(ms) { return new Date(ms).toISOString().replace(/\.\d{3}Z$/, 'Z'); }
  function now() { return iso(Date.now()); }
  function ms(s) { return Date.parse(s); }
  function parts(t) { var o = {}; new Intl.DateTimeFormat('en-US', { timeZone: PTZ, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' }).formatToParts(new Date(t)).forEach(function (p) { o[p.type] = parseInt(p.value, 10); }); return o; }
  function tzOff(t) { var s = Math.floor(t / 1000) * 1000, p = parts(s); return (Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute, p.second) - s) / 60000; }
  function ptTime(y, m, d, h, mi) { var g = Date.UTC(y, m - 1, d, h, mi), r = g - tzOff(g) * 60000; r = g - tzOff(r) * 60000; return iso(r); }
  function ptDay(off, h, mi) { var p = parts(Date.now()), d = new Date(Date.UTC(p.year, p.month - 1, p.day + off)); return ptTime(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate(), h, mi || 0); }
  function dayStart() { return ptDay(0, 0, 0); }
  function two(n) { return ('0' + n).slice(-2); }
  function ptDate(t) { var p = parts(t === undefined ? Date.now() : t); return p.year + '-' + two(p.month) + '-' + two(p.day); }
  function fmtLong(s) { return new Intl.DateTimeFormat('en-US', { timeZone: PTZ, weekday: 'long', month: 'long', day: 'numeric' }).format(new Date(s)) + ' at ' + new Intl.DateTimeFormat('en-US', { timeZone: PTZ, hour: 'numeric', minute: '2-digit' }).format(new Date(s)) + ' PT'; }
  function cnt(s) { return Array.from(s).length; }
  function textField(v, field, max, required) {
    if (required === undefined) required = true;
    if ((v === null || v === undefined) && !required) return '';
    if (typeof v !== 'string') throw E(422, 'invalid', field + ' must be text.');
    v = v.replace(/\r\n/g, '\n').replace(/\r/g, '\n');
    if (v.indexOf('\u0000') >= 0) throw E(422, 'invalid', field + ' has characters we cannot store.');
    if (required && !v.trim()) throw E(422, 'empty', ['Your message', 'Your question', 'Reply', 'Draft', 'Note'].indexOf(field) >= 0 ? 'Please write something first \u2014 an empty message is not sent.' : field + ' is required.');
    var n = cnt(v); if (n > max) throw E(422, 'too_long', 'This is ' + n + ' characters; the limit is ' + max + '. Nothing was sent.', { length: n, max: max });
    return v;
  }
  function toDeadline(v, field, allowPast) {
    field = field || 'deadline'; if (typeof v !== 'string' || !v) throw E(422, 'invalid_date', field + ' is required.');
    var t; if (/^\d{4}-\d{2}-\d{2}$/.test(v)) { var a = v.split('-').map(Number); t = ms(ptTime(a[0], a[1], a[2], 17, 0)); } else t = Date.parse(v);
    if (isNaN(t)) throw E(422, 'invalid_date', field + ' is not a valid date.');
    if (!allowPast && t < Date.now() - 3600000) throw E(422, 'date_in_past', field + ' cannot be in the past.');
    return iso(t);
  }
  function rx(a) { var o = []; a.forEach(function (p) { try { o.push(new RegExp(p, 'i')); } catch (e) {} }); return o; }
  var RXE = rx(R.EMERGENCY), RXC = rx(R.CLINICAL), RXH = R.HUMAN_FIRST.map(function (x) { return [new RegExp(x[0], 'i'), x[1]]; }), RXF = R.FAQ.map(function (f) { return [f[0], rx(f[1]), f[2], f[3]]; });
  function triage(text) {
    var t = text.replace(/\u2019/g, "'");
    if (RXE.some(function (r) { return r.test(t); })) return { level: 'emergency' };
    if (RXC.some(function (r) { return r.test(t); })) return { level: 'clinical' };
    for (var i = 0; i < RXH.length; i++) if (RXH[i][0].test(t)) return { level: 'admin', category: RXH[i][1] };
    var hits = RXF.filter(function (f) { return f[1].some(function (r) { return r.test(t); }); });
    if (hits.length === 1) return { level: 'faq', faq: hits[0][0], answer: hits[0][2], source: hits[0][3] };
    return { level: 'unknown' };
  }
  var STATUSES = ['Received', 'Assigned', 'In Progress', 'Waiting', 'Resolved'];
  var TI = {}; R.TRANSITIONS.forEach(function (t) { TI[t.from + '>' + t.to] = t; });
  var CATKEYS = { scheduling: 'Scheduling', refill: 'Prescription refill request', billing: 'Billing question', medical: 'Medical question', records: 'Records question', other: 'Other' };
  var TEAMS = { front: 'Front desk', nurse: 'Nurse', clinical: 'Clinician', admin: 'Administrator' };
  var PR = ['patient', 'caregiver'], OFF = ['office', 'clinician', 'admin'];

  function seed() {
    var t0 = Date.now(), ago = function (h) { return iso(t0 - h * 3600000); }, ahead = function (h) { return iso(t0 + h * 3600000); };
    db = { patients: [], users: [], grants: [], cases: [], appts: [], instr: [], docs: [], tasks: [], msgs: [], notifs: [], events: [], drafts: {}, settings: { reply_target: '' }, idem: {}, intake: {} }; nid = { task: 0, msg: 0, notif: 0, ev: 0 };
    [[1, 'Alex Example', '(208) 555-0101'], [2, 'Jordan Sample', '(208) 555-0102'], [3, 'Casey Rivera', '(208) 555-0103'], [4, 'Morgan Lee', '(208) 555-0104'], [5, 'Taylor Quinn', '(208) 555-0105']].forEach(function (p) { db.patients.push({ id: p[0], name: p[1], phone: p[2], email: p[1].split(' ')[0].toLowerCase() + '@example.invalid', channel: 'text', phone_valid: 1 }); });
    [['alex', 'Alex Example', 'patient', null, 1, 'Patient \u00b7 new patient, MRI records still needed'], ['jordan', 'Jordan Sample', 'patient', null, 2, 'Patient \u00b7 second patient (isolation demo)'], ['riley', 'Riley Helper', 'caregiver', null, 1, 'Authorized helper for Alex \u00b7 sees only what Alex shared'],
     ['pat', 'Pat \u00b7 Front desk', 'office', 'front', null, 'Office staff \u00b7 front desk'], ['nina', 'Nina \u00b7 Nurse', 'office', 'nurse', null, 'Office staff \u00b7 nurse'], ['yakel', 'Dr. Yakel', 'clinician', 'clinical', null, 'Clinician \u00b7 Dr. Stefan Yakel, DO (fictional login)'], ['admin', 'Admin \u00b7 Practice manager', 'admin', 'admin', null, 'Administrator \u00b7 settings, reports, audit log']]
      .forEach(function (u) { db.users.push({ key: u[0], name: u[1], role: u[2], team: u[3], patient_id: u[4], blurb: u[5] }); });
    db.grants.push({ patient_id: 1, user_key: 'riley', scopes: { appointments: true, instructions: true, status: false, messages: false }, status: 'active' });
    [[1, 1, 'complete', 'requested', 'unknown', 'not_started', 'verified', ''], [2, 2, 'complete', 'reviewed', 'unavailable', 'completed', 'verified', 'Northside Imaging (fictional)'], [3, 3, 'complete', 'received', 'received', 'not_started', 'verified', 'Lakeshore Imaging (fictional)'], [4, 4, 'complete', 'reviewed', 'received', 'completed', 'verified', 'Lakeshore Imaging (fictional)'], [5, 5, 'complete', 'received', 'unknown', 'in_progress', 'uncertain', 'Unknown']]
      .forEach(function (c) { db.cases.push({ id: c[0], patient_id: c[1], referral_status: c[2], report_status: c[3], images_status: c[4], intake_status: c[5], identity_status: c[6], facility: c[7] }); });
    [[1, 1, 1, ptDay(10, 10, 30), 'Dr. Stefan Yakel, DO', 0], [2, 2, 2, ptDay(0, 15, 30), 'Sarah Frank, APRN', 1], [3, 3, 3, ptDay(0, 11, 15), 'Dr. Stefan Yakel, DO', 1], [4, 4, 4, ptDay(0, 10, 30), 'Dr. Stefan Yakel, DO', 1], [5, 5, 5, ptDay(0, 13, 0), 'Sarah Frank, APRN', 0]]
      .forEach(function (a) { db.appts.push({ id: a[0], patient_id: a[1], case_id: a[2], starts_at: a[3], clinician: a[4], location: R.ADDRESS, kind: 'New patient consultation', confirmed: a[5] }); });
    for (var c = 1; c <= 5; c++) R.EDU.forEach(function (e) { db.instr.push({ case_id: c, title: e[0], body: e[1], source: e[2] }); });
    [[1, 1, 1, 'referral', 'Referral letter (fictional placeholder)', 'Referring office (fictional)', 'received', 'Placeholder \u2014 no real document.'], [2, 1, 1, 'radiology_report', 'MRI lumbar report', 'not received yet', 'missing', 'Not received. Facility not yet known.'], [3, 2, 2, 'radiology_report', 'MRI cervical report (fictional placeholder)', 'Northside Imaging (fictional)', 'reviewed', 'Placeholder \u2014 no real report.'],
     [4, 2, 2, 'imaging_files', 'MRI cervical images', 'Northside Imaging (fictional)', 'unavailable', 'Facility says images are not available online; disc requested.'], [5, 3, 3, 'radiology_report', 'MRI lumbar report (fictional placeholder)', 'Lakeshore Imaging (fictional)', 'received', 'Placeholder \u2014 awaiting clinician review.'], [6, 5, 5, 'radiology_report', 'Outside MRI report \u2014 unmatched', 'Fax inbox (fictional)', 'unmatched', 'Name on the document does not match registration.']]
      .forEach(function (d) { db.docs.push({ id: d[0], case_id: d[1], patient_id: d[2], doc_type: d[3], title: d[4], source: d[5], status: d[6], note: d[7] }); });
    function T(o) { var t = Object.assign({ id: ++nid.task, case_id: null, patient_id: 0, type: '', category: null, source: 'case', origin: 'seed', blocked_step: '', reason: '', next_action: '', patient_label: null, owner: null, backup: null, deadline: null, status: 'Assigned', priority: 'normal', clinical_level: 0, waiting_on: null, follow_up_by: null, followup_due: 0, outcome: null, resolved_by: null, resolved_at: null, patient_visible: 0, last_verified_at: null, last_verified_source: null, ack_at: null, first_reply_at: null, dedupe_key: null, created_at: ago(24), updated_at: ago(3) }, o); db.tasks.push(t); return t; }
    T({ case_id: 1, patient_id: 1, type: 'records_request', blocked_step: 'MRI report not received \u2014 request not sent', reason: 'Patient has not told us where the MRI was done, so the request cannot be sent.', next_action: 'Wait for the patient to name the facility; call the patient if nothing by the follow-up date.', patient_label: 'Your MRI report', owner: 'pat', backup: 'nina', deadline: ahead(48), status: 'Waiting', waiting_on: 'Patient: the name of the imaging facility', follow_up_by: ahead(48), patient_visible: 1, last_verified_at: ago(20), last_verified_source: 'Pat \u00b7 Front desk', dedupe_key: 'records:1' });
    T({ case_id: 2, patient_id: 2, type: 'images_request', blocked_step: 'Report received, but images are unavailable', reason: 'Facility says the images are not available online; a disc was requested.', next_action: 'Call Northside Imaging (fictional) to confirm the disc was mailed.', patient_label: 'Your MRI images', owner: 'pat', backup: 'nina', deadline: ahead(24), status: 'Waiting', waiting_on: 'Northside Imaging (fictional): disc of images', follow_up_by: ahead(72), patient_visible: 1, last_verified_at: ago(30), last_verified_source: 'Pat \u00b7 Front desk', dedupe_key: 'images:2' });
    T({ case_id: 5, patient_id: 5, type: 'identity', blocked_step: 'Identity uncertain \u2014 document cannot be attached to a chart', reason: 'Name on the outside MRI report differs from registration (fictional).', next_action: 'Call the patient to verify identity, then match the document.', owner: 'pat', backup: 'nina', deadline: ahead(20), dedupe_key: 'identity:5' });
    T({ case_id: 3, patient_id: 3, type: 'reach_patient', blocked_step: 'Patient unreachable', reason: 'Three call attempts, voicemail full (fictional).', next_action: 'Try text and email, then send a letter.', owner: 'pat', backup: 'nina', deadline: ahead(6), status: 'In Progress', dedupe_key: 'reach:3', updated_at: ago(1) });
    T({ case_id: 3, patient_id: 3, type: 'intake_followup', blocked_step: 'Intake not completed \u2014 visit today', reason: 'Patient has not started intake.', next_action: 'Offer to complete intake by phone at check-in.', owner: 'pat', backup: 'nina', deadline: ahead(3), dedupe_key: 'intake:3' });
    T({ case_id: 3, patient_id: 3, type: 'records_review', blocked_step: 'MRI report received \u2014 clinician review needed', reason: 'Report arrived yesterday; a clinician must review before the visit.', next_action: 'Review the report and mark it reviewed.', owner: 'yakel', backup: 'nina', deadline: ahead(2), clinical_level: 2, dedupe_key: 'review:3' });
    var tj = T({ case_id: 2, patient_id: 2, type: 'message', category: 'Scheduling', source: 'patient', blocked_step: 'Patient message awaiting reply', reason: 'Scheduling question', next_action: 'Reply to the patient, or call.', owner: 'pat', backup: 'nina', deadline: ahead(18), patient_visible: 1, created_at: ago(3) });
    db.msgs.push({ id: ++nid.msg, task_id: tj.id, case_id: 2, patient_id: 2, author_key: 'jordan', author_role: 'patient', author_name: 'Jordan Sample', kind: 'patient_message', visibility: 'patient', body: 'Can I move my visit a little later this afternoon? I may be stuck in traffic.', created_at: ago(3) });
    db.notifs.push({ id: ++nid.notif, patient_id: 1, task_id: null, template: 'appt_reminder', channel: 'text', body: 'Premier Spine: please confirm your visit.', status: 'delivered', attempts: 1, max_attempts: 3, manual_retries: 0, action: 'confirm_appointment', last_error: null });
    log(null, 'system.seed', 'db', 'seed', null, null, null, { note: 'fictional seed data created (in this browser tab only)' });
  }
  function log(user, action, ot, oid, case_id, task_id, patient_id, detail) {
    db.events.push({ id: ++nid.ev, ts: now(), actor_key: user ? user.key : 'system', actor_role: user ? user.role : 'system', actor_name: user ? user.name : 'System (rule)', action: action, object_type: ot, object_id: oid === null || oid === undefined ? null : String(oid), case_id: case_id, task_id: task_id, patient_id: patient_id, detail: detail === null || detail === undefined ? null : JSON.stringify(detail) });
  }
  function U(k) { return db.users.filter(function (u) { return u.key === k; })[0] || null; }
  function uname(k) { var u = k && U(k); return u ? u.name : null; }
  function teamLabel(k) { var u = k && U(k); return TEAMS[u ? u.team : null] || 'Office'; }
  function task(id) { return db.tasks.filter(function (t) { return t.id === id; })[0] || null; }
  function pat(id) { return db.patients.filter(function (p) { return p.id === id; })[0]; }
  function kase(id) { return db.cases.filter(function (c) { return c.id === id; })[0]; }
  function overdue(t) { return t.status !== 'Resolved' && !!t.deadline && t.deadline < now(); }
  function stageInfo(c) {
    var steps = ['Referral received', 'Records requested', 'Records received & reviewed', 'Intake completed', 'Ready for appointment'];
    var done = [c.referral_status === 'complete', !!c.facility && c.facility !== 'Unknown' && c.report_status !== 'not_requested', c.report_status === 'reviewed' && (c.images_status === 'received' || c.images_status === 'waived'), c.intake_status === 'completed' && c.identity_status === 'verified'];
    done.push(done.every(Boolean)); var cur = done.indexOf(false); if (cur < 0) cur = 4; var missing = [];
    if (c.referral_status !== 'complete') missing.push('Referral incomplete');
    if (c.report_status === 'not_requested' || c.report_status === 'requested') missing.push('Radiology report not received'); else if (c.report_status === 'received') missing.push('Radiology report awaiting clinician review');
    if (c.images_status === 'unavailable') missing.push('Images unavailable'); else if (c.images_status === 'unknown' || c.images_status === 'requested') missing.push('Images not received');
    if (c.intake_status !== 'completed') missing.push('Intake not completed'); if (c.identity_status !== 'verified') missing.push('Identity not verified');
    return { steps: steps.map(function (s, i) { return { label: s, state: done[i] ? 'done' : (i === cur ? 'current' : 'todo') }; }), missing: missing, ready: done[4] };
  }
  function staffTask(t) {
    var p = pat(t.patient_id), first = db.msgs.filter(function (m) { return m.task_id === t.id && m.visibility === 'patient' && (m.kind === 'patient_message' || m.kind === 'patient_question'); })[0], d = {};
    ['id', 'case_id', 'patient_id', 'type', 'category', 'source', 'origin', 'blocked_step', 'reason', 'next_action', 'owner', 'backup', 'deadline', 'status', 'priority', 'clinical_level', 'waiting_on', 'follow_up_by', 'followup_due', 'outcome', 'resolved_by', 'resolved_at', 'ack_at', 'first_reply_at', 'last_verified_at', 'last_verified_source', 'created_at', 'updated_at'].forEach(function (k) { d[k] = t[k]; });
    d.patient_name = p ? p.name : '?'; d.owner_name = uname(t.owner); d.backup_name = uname(t.backup); d.overdue = overdue(t); d.acknowledged = !!t.ack_at; d.team = teamLabel(t.owner); d.resolved_by_name = uname(t.resolved_by);
    if (first) { var b = first.body; d.excerpt = cnt(b) <= 140 ? b : Array.from(b).slice(0, 140).join('') + '\u2026'; d.message_length = cnt(b); d.excerpt_truncated = cnt(b) > 140; }
    d.group = grp(t); d.waiting_since = t.status === 'Waiting' ? t.updated_at : null;   /* preview19 Prompt C: same grouping rule as the server (no booking/hold in the Pass 1 mock) */
    return d;
  }
  function grp(t) { if (t.status === 'Resolved') return 'done'; if (t.priority === 'urgent') return 'urgent'; if (overdue(t) || t.followup_due) return 'blocked'; if (t.status === 'Waiting') return 'waiting'; return 'now'; }
  function qualified(u) { return u.role === 'clinician' || u.team === 'nurse'; }
  function patientTask(t) {
    var team = teamLabel(t.owner), st = t.status, tgt = db.settings.reply_target;
    var txt = { 'Received': 'Received', 'Assigned': 'Received \u00b7 Assigned to ' + team, 'In Progress': 'Being worked on by ' + team, 'Waiting': t.waiting_on ? 'Waiting for ' + t.waiting_on : 'Waiting', 'Resolved': 'Closed' }[st];
    var d = { id: t.id, category: t.category, status: st, status_text: txt, team: team, created_at: t.created_at, updated_at: t.updated_at, acknowledged: !!t.ack_at, open: st !== 'Resolved', type: t.type, reply_target: tgt && st !== 'Resolved' ? 'We aim to reply ' + tgt : null };
    if (t.ack_at && st !== 'Resolved') d.ack_note = 'The office has acknowledged this. It is still open and a person is working on it.';
    return d;
  }
  function patientMsgs(tid) { return db.msgs.filter(function (m) { return m.task_id === tid && m.visibility === 'patient'; }).map(function (m) { return { id: m.id, author_role: m.author_role, author_name: m.author_name, kind: m.kind, body: m.body, created_at: m.created_at }; }); }
  function createTask(actor, o) {
    if (o.dedupe_key) { var ex = db.tasks.filter(function (t) { return t.dedupe_key === o.dedupe_key && t.status !== 'Resolved'; })[0]; if (ex) return [ex, false]; }
    var owner = o.owner || null, backup = o.backup || null, hours = o.hours || 24, lvl = 0;
    if (o.route) { owner = o.route[0]; backup = o.route[1]; hours = o.route[2]; lvl = o.route[4]; } if (o.clinical_level !== undefined && o.clinical_level !== null) lvl = o.clinical_level;
    var ts = now(), t = { id: ++nid.task, case_id: o.case_id, patient_id: o.patient_id, type: o.type, category: o.category || null, source: o.source || 'case', origin: 'live', blocked_step: o.blocked_step || '', reason: o.reason || '', next_action: o.next_action || '', patient_label: o.patient_label || null, owner: null, backup: null, deadline: null, status: 'Received', priority: o.priority || 'normal', clinical_level: lvl, waiting_on: null, follow_up_by: null, followup_due: 0, outcome: null, resolved_by: null, resolved_at: null, patient_visible: o.patient_visible || 0, last_verified_at: null, last_verified_source: null, ack_at: null, first_reply_at: null, dedupe_key: o.dedupe_key || null, created_at: ts, updated_at: ts };
    db.tasks.push(t); log(actor, 'task.received', 'task', t.id, t.case_id, t.id, t.patient_id, { type: o.type, category: o.category, priority: t.priority });
    if (owner) { t.owner = owner; t.backup = backup; t.deadline = iso(Date.now() + hours * 3600000); t.status = 'Assigned'; log(null, 'task.assigned', 'task', t.id, t.case_id, t.id, t.patient_id, { owner: owner, backup: backup, deadline: t.deadline, by: 'routing rule (prototype)' }); }
    return [t, true];
  }
  function queueNotif(pid, tid, template, body, action) { var p = pat(pid), n = { id: ++nid.notif, patient_id: pid, task_id: tid, template: template, channel: p ? p.channel : 'text', body: body, status: 'queued', attempts: 0, max_attempts: 3, manual_retries: 0, action: action || null, last_error: null }; db.notifs.push(n); log(null, 'notification.queued', 'notification', n.id, null, tid, pid, { template: template }); return n.id; }
  function notifDto(n) { var d = Object.assign({}, n); d.patient_name = pat(n.patient_id) ? pat(n.patient_id).name : '?'; d.can_retry = n.status === 'failed' && n.manual_retries < 2; return d; }
  function doTransition(user, t, to, o) {
    o = o || {}; var key = t.status + '>' + to; if (!TI[key]) throw E(409, 'invalid_transition', 'A task cannot go from ' + t.status + ' to ' + to + '.');
    var det = { from: t.status, to: to }, frm = t.status;
    if (to === 'Assigned' && frm === 'Received' && !(t.owner && t.backup && t.deadline)) throw E(422, 'assign_requires', 'Assigning needs an owner, a backup and a deadline.');
    var set = { status: to, updated_at: now() };
    if (to === 'Waiting') { var wo = textField(o.waiting_on, 'Waiting on', 200); var fu = toDeadline(o.follow_up_by, 'Follow-up date'); set.waiting_on = wo.trim(); set.follow_up_by = fu; set.followup_due = 0; det.waiting_on = set.waiting_on; det.follow_up_by = fu; }
    if (frm === 'Waiting' && to === 'In Progress') { set.waiting_on = null; set.follow_up_by = null; set.followup_due = 0; }
    if (frm === 'Waiting' && to === 'Assigned') set.followup_due = 1;
    if (to === 'Resolved') {
      if (o.system || !user) throw E(403, 'forbidden', 'Only a person can resolve a task.');
      var oc = textField(o.outcome, 'Outcome note', MAXN.outcome); if (oc.trim().length < 3) throw E(422, 'outcome_required', 'Resolving needs an outcome note.');
      if (t.clinical_level === 2 && user.role !== 'clinician') throw E(403, 'clinician_required', 'Only a clinician can resolve this task.');
      if (t.clinical_level === 1 && !(user.role === 'clinician' || user.team === 'nurse')) throw E(403, 'nurse_required', 'Only a nurse or clinician can resolve this clinical task.');
      set.outcome = oc.trim(); set.resolved_by = user.key; set.resolved_at = now(); set.waiting_on = null; set.follow_up_by = null; det.outcome = set.outcome;
    }
    if (frm === 'Resolved') { var rs = textField(o.reason, 'Reason for reopening', 500); set.outcome = null; set.resolved_by = null; set.resolved_at = null; det.reason = rs.trim(); }
    Object.assign(t, set); log(o.system ? null : user, 'task.transition', 'task', t.id, t.case_id, t.id, t.patient_id, det); return t;
  }
  function suggest(t) {
    var p = pat(t.patient_id), first = p ? p.name.split(' ')[0] : 'there', lead = 'Hi ' + first + ', thanks for reaching out to Premier Spine. ', cat = t.category || 'Other';
    var m = { 'Scheduling': 'We\u2019ve received your scheduling request. Nothing about your visit changes until we confirm the change with you. If you need something sooner, call ' + TEL + '.', 'Prescription refill request': 'We\u2019ve received your refill request and passed it to a nurse. If you\u2019re running out soon, please call ' + TEL + '.', 'Billing question': 'We\u2019ve received your billing question and it\u2019s with our front desk. You can also call ' + TEL + ' if it\u2019s easier to talk it through.', 'Medical question': 'Your message has gone to a nurse, who will review it. If this feels urgent, please call ' + TEL + ' now, or 911 in an emergency.', 'Call-back request': 'We\u2019ve received your call-back request. It is on our front desk\u2019s list.' };
    return lead + (m[cat] || 'We\u2019ve received your message and it is with our team. If it\u2019s urgent, call ' + TEL + '.');
  }
  function tick() {
    var out = { sent: 0, delivered: 0, retry: 0, failed: 0, followups_due: 0 }, was = db.notifs.filter(function (n) { return n.status === 'sent'; }).map(function (n) { return n.id; });
    db.notifs.filter(function (n) { return n.status === 'queued'; }).forEach(function (n) {
      var p = pat(n.patient_id);
      if (p && p.phone_valid) { n.status = 'sent'; n.attempts++; n.sent_at = now(); log(null, 'notification.sent', 'notification', n.id, null, n.task_id, n.patient_id, { note: 'handed to SIMULATED vendor' }); out.sent++; }
      else { var att = n.attempts + 1, err = 'Number not reachable (simulated vendor error)';
        if (att >= n.max_attempts) { n.status = 'failed'; n.attempts = att; n.last_error = err; log(null, 'notification.failed', 'notification', n.id, null, n.task_id, n.patient_id, { attempts: att, error: err }); out.failed++;
          createTask(null, { patient_id: n.patient_id, case_id: n.patient_id, type: 'exception', source: 'system', dedupe_key: 'notif:' + n.id, blocked_step: 'Notification failed after ' + att + ' attempts', reason: err + '. The patient may not know there is a new message.', next_action: 'Call the patient, confirm their number, then retry or close.', owner: 'pat', backup: 'nina', hours: 4 }); }
        else { n.attempts = att; n.last_error = err; log(null, 'notification.retry', 'notification', n.id, null, n.task_id, n.patient_id, { attempt: att, error: err }); out.retry++; } }
    });
    db.notifs.filter(function (n) { return n.status === 'sent' && was.indexOf(n.id) >= 0; }).forEach(function (n) { n.status = 'delivered'; n.delivered_at = now(); log(null, 'notification.delivered', 'notification', n.id, null, n.task_id, n.patient_id, { note: 'SIMULATED vendor delivery receipt' }); out.delivered++; });
    db.tasks.filter(function (t) { return t.status === 'Waiting' && t.follow_up_by && t.follow_up_by < now(); }).forEach(function (t) { doTransition(null, t, 'Assigned', { system: true }); out.followups_due++; });
    return out;
  }
  function markReceived(pid, tid, template) { db.notifs.forEach(function (n) { if (n.patient_id === pid && ['queued', 'sent', 'delivered'].indexOf(n.status) >= 0 && (tid === undefined || tid === null || n.task_id === tid) && (!template || n.template === template)) { n.status = 'received'; n.received_at = now(); log(null, 'notification.received', 'notification', n.id, null, tid, pid, { how: 'patient opened it in the portal' }); } }); }
  function setting(k) { return db.settings[k] || ''; }
  function pcase(pid) { return db.cases.filter(function (c) { return c.patient_id === pid; })[0]; }
  function scopes(u) {
    if (u.role === 'patient') return { appointments: true, instructions: true, status: true, messages: true };
    var g = db.grants.filter(function (x) { return x.user_key === u.key && x.patient_id === u.patient_id; })[0];
    if (!g || g.status !== 'active') throw E(403, 'access_stopped', 'Alex has not shared anything with you right now.'); return g.scopes;
  }
  function need(sc, n) { if (!sc[n]) throw E(403, 'not_shared', 'This has not been shared with you.'); }
  var TEAM = [{ name: 'Dr. Stefan Yakel, DO', role: 'Orthopedic spine surgeon', photo: 'assets/yakel.webp' }, { name: 'Sarah Frank, APRN', role: 'Nurse practitioner', photo: 'assets/frank.webp' }];
  function findDup(pid, body) { var cut = Date.now() - 20000; var m = db.msgs.filter(function (m) { return m.patient_id === pid && m.body === body && /^patient_/.test(m.kind) && ms(m.created_at) >= cut; }).pop(); return m ? task(m.task_id) : null; }
  function makeRequest(u, category, body, kind, tri, srcNote) {
    var pid = u.patient_id, dup = findDup(pid, body); if (dup) return [dup, false, null];
    var urgent = tri.level === 'emergency', rt, cat, prio = 'normal', note = null;
    if (urgent) { rt = R.URGENT_ROUTE; cat = 'Medical question'; prio = 'urgent'; }
    else { cat = category; if (tri.level === 'clinical' && cat !== 'Medical question' && cat !== 'Prescription refill request') { cat = 'Medical question'; note = 'We routed this to a nurse because it mentions symptoms or medicines.'; } rt = R.ROUTES[cat]; }
    var c = pcase(pid), n = cnt(body);
    var r = createTask(u, { patient_id: pid, case_id: c.id, type: kind === 'patient_message' ? 'message' : 'question', category: cat, source: 'patient', patient_visible: 1, blocked_step: urgent ? 'URGENT: patient message uses emergency wording' : kind === 'patient_message' ? 'Patient message awaiting reply' : 'Patient question the helper could not answer', reason: cat + ': patient wrote ' + n + ' characters' + (srcNote ? ' (' + srcNote + ')' : ''), next_action: urgent ? 'Review immediately and phone the patient' : 'Read the conversation and reply, or phone the patient', route: rt, priority: prio });
    var t = r[0]; db.msgs.push({ id: ++nid.msg, task_id: t.id, case_id: c.id, patient_id: pid, author_key: u.key, author_role: 'patient', author_name: u.name, kind: kind, visibility: 'patient', body: body, created_at: now() });
    log(u, 'message.created', 'message', t.id, c.id, t.id, pid, { length: n, category: cat, triage: tri.level }); return [t, true, note];
  }
  var routes = [];
  function route(method, pat_, app, roles, idem, fn) { routes.push({ method: method, rx: new RegExp('^' + pat_ + '$'), app: app, roles: roles, idem: idem, fn: fn }); }
  route('GET', '/api/health', null, null, false, function () { return { ok: true, banner: R.BANNER, time: now() }; });
  route('GET', '/api/personas', null, null, false, function (c) { var app = c.q.app || 'portal'; return { banner: R.BANNER, personas: db.users.filter(function (u) { return (OFF.indexOf(u.role) >= 0 ? 'office' : 'portal') === app; }).map(function (u) { return { key: u.key, name: u.name, role: u.role, blurb: u.blurb }; }) }; });
  route('POST', '/api/login', null, null, false, function (c) { var u = U(c.body.persona); if (!u) throw E(404, 'no_such_persona', 'Unknown demo persona.'); var app = OFF.indexOf(u.role) >= 0 ? 'office' : 'portal'; if (c.body.app !== app) throw E(403, 'wrong_audience', 'That persona cannot sign in here.'); sess[app] = u.key; log(u, 'session.login', 'session', u.key, null, null, null, { app: app, note: 'fictional demo login, no password' }); return { user: { key: u.key, name: u.name, role: u.role }, token_note: 'Static snapshot: there is no token at all. Sign-in state is a variable in this tab.' }; });
  route('GET', '/api/p/me', 'portal', PR, false, function (c) { var sc = scopes(c.user), p = pat(c.user.patient_id); return { user: { name: c.user.name, role: c.user.role }, patient_name: p.name, scopes: sc, banner: R.BANNER, limits: { message: MAXN.message, ask: MAXN.ask } }; });
  route('GET', '/api/p/rules', 'portal', PR, false, function () { return { emergency_patterns: R.EMERGENCY, emergency_message: R.EMERGENCY_LIVE || R.EMERGENCY_GUIDANCE, not_triage: R.NOT_TRIAGE }; });
  route('POST', '/api/p/logout', 'portal', PR, false, function () { sess.portal = null; return { ok: true }; });
  route('GET', '/api/p/home', 'portal', PR, false, function (c) {
    var sc = scopes(c.user), pid = c.user.patient_id, cs = pcase(pid), out = { shared_scopes: sc, viewer_role: c.user.role, team: TEAM, contact: { phone: R.PHONE, tel: 'tel:2087703536', address: R.ADDRESS }, reply_target: setting('reply_target') || null, banner: R.BANNER }, a = null;
    if (sc.appointments) { a = db.appts.filter(function (x) { return x.patient_id === pid && x.starts_at >= dayStart(); }).sort(function (x, y) { return x.starts_at < y.starts_at ? -1 : 1; })[0] || null; out.next_appointment = a; if (c.user.role === 'patient') markReceived(pid, null, 'appt_reminder'); }
    if (sc.status) { out.stage = stageInfo(cs).steps; out.waiting_on = db.tasks.filter(function (t) { return t.patient_id === pid && t.source === 'case' && t.patient_visible && t.status !== 'Resolved'; }).map(function (t) { return { id: t.id, label: t.patient_label || 'An update', status: t.status, waiting_on: t.waiting_on, next_check: t.follow_up_by, last_verified_at: t.last_verified_at, last_verified_source: t.last_verified_source }; }); }
    if (sc.instructions) out.instructions = db.instr.filter(function (i) { return i.case_id === cs.id; });
    if (c.user.role === 'patient') { var na;
      if (cs.intake_status !== 'completed') na = { key: 'intake', title: 'Finish your 2-minute intake', why: 'Your care team reads it before the visit so your time goes to you, not forms.' };
      else if (!cs.facility && (cs.report_status === 'not_requested' || cs.report_status === 'requested')) na = { key: 'imaging', title: 'Tell us where your MRI was done', why: 'We can\u2019t ask for your report until we know where it is.' };
      else if (a && !a.confirmed) na = { key: 'confirm', title: 'Confirm your appointment', why: 'One tap lets us know you\u2019re coming.' };
      else na = { key: 'none', title: 'Nothing needed from you right now', why: 'We\u2019ll show a new action here the moment there is one.' };
      out.next_action = na; out.open_requests = db.tasks.filter(function (t) { return t.patient_id === pid && t.source === 'patient' && t.status !== 'Resolved'; }).length; }
    return out;
  });
  route('GET', '/api/p/threads', 'portal', PR, false, function (c) {
    var sc = scopes(c.user); need(sc, 'messages');
    return { threads: db.tasks.filter(function (t) { return t.patient_id === c.user.patient_id && t.source === 'patient'; }).sort(function (a, b) { return a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : b.id - a.id; }).map(function (t) { var d = patientTask(t), ms_ = patientMsgs(t.id), f = ms_.filter(function (m) { return /^patient_/.test(m.kind); })[0]; d.preview = f ? (cnt(f.body) > 80 ? Array.from(f.body).slice(0, 80).join('') + '\u2026' : f.body) : ''; d.message_count = ms_.length; return d; }) };
  });
  route('GET', '/api/p/threads/(\\d+)', 'portal', PR, false, function (c) { var sc = scopes(c.user); need(sc, 'messages'); var t = task(+c.m[1]); if (!t || t.patient_id !== c.user.patient_id || t.source !== 'patient') throw E(404, 'not_found', 'No such conversation.'); if (c.user.role === 'patient') markReceived(t.patient_id, t.id); return { thread: patientTask(t), messages: patientMsgs(t.id) }; });
  route('POST', '/api/p/messages', 'portal', PR, true, function (c) {
    var sc = scopes(c.user); need(sc, 'messages'); var ck = c.body.category; if (!CATKEYS[ck]) throw E(422, 'bad_category', 'Please choose what the message is about.');
    var body = textField(c.body.body, 'Your message', MAXN.message), tri = triage(body), r = makeRequest(c.user, CATKEYS[ck], body, 'patient_message', tri), resp = { task: patientTask(r[0]), created: r[1], duplicate_suppressed: !r[1], routed_note: r[2], triage: { level: tri.level } };
    if (tri.level === 'emergency') resp.guidance = R.EMERGENCY_GUIDANCE; else if (tri.level === 'clinical') resp.guidance = R.CLINICAL_GUIDANCE; return resp;
  });
  route('POST', '/api/p/ask', 'portal', PR, true, function (c) {
    var sc = scopes(c.user); need(sc, 'messages'); var q = textField(c.body.question, 'Your question', MAXN.ask), tri = triage(q), pid = c.user.patient_id, base = { triage: { level: tri.level }, not_triage: R.NOT_TRIAGE };
    if (tri.level === 'faq') { var ans = tri.answer;
      if (ans === '@APPT@') { var a = db.appts.filter(function (x) { return x.patient_id === pid && x.starts_at >= dayStart(); }).sort(function (x, y) { return x.starts_at < y.starts_at ? -1 : 1; })[0]; ans = a ? 'Your next visit is ' + fmtLong(a.starts_at) + ' with ' + a.clinician + ' \u2014 it\u2019s also at the top of your Home page.' : 'I don\u2019t see a visit booked yet. It will appear at the top of Home when one is.'; }
      log(c.user, 'ask.answered', 'ask', tri.faq, pcase(pid).id, null, pid, { faq: tri.faq, length: cnt(q) }); return Object.assign(base, { kind: 'answer', answer: ans, source: tri.source, task: null }); }
    var cat = (tri.level === 'clinical' || tri.level === 'emergency') ? 'Medical question' : (tri.category || 'Question'), r = makeRequest(c.user, cat, q, 'patient_question', tri, (tri.level === 'unknown' || tri.level === 'admin') ? 'asked in Ask; no confident FAQ answer' : null);
    var kind = { emergency: 'emergency', clinical: 'clinical' }[tri.level] || 'handoff', msg = { emergency: R.EMERGENCY_GUIDANCE, clinical: R.CLINICAL_GUIDANCE, admin: 'That one needs a person. I\u2019ve sent it to our front desk \u2014 you can see its status below.', unknown: 'I couldn\u2019t answer that confidently, so I\u2019ve sent it to our front desk \u2014 you can see its status below.' }[tri.level];
    return Object.assign(base, { kind: kind, answer: msg, source: null, task: patientTask(r[0]), created: r[1], duplicate_suppressed: !r[1] });
  });
  /* preview19 Prompt A: the demo assistant is built on the server from structured records; the static snapshot honestly says it needs the server */
  function needsServer() { return E(409, 'needs_server', 'The demo assistant needs the local prototype server (python3 server.py). This static snapshot has no server, so it cannot read any records. Nothing was sent.'); }
  route('POST', '/api/p/assist', 'portal', PR, true, function () { throw needsServer(); });
  route('GET', '/api/o/priority-rules', 'office', OFF, false, function () { return R.PRIORITY; });   /* preview19 Prompt C: same rule text as the server */
  route('GET', '/api/p/reminders', 'portal', PR, false, function () { return { opted_out: false, reminders: [], can_change: false, note: 'Static snapshot: reminder texts need the local prototype server. Nothing is stored or sent here.' }; });
  route('GET', '/api/p/content/(\\d+)', 'portal', PR, false, function () { throw needsServer(); });
  route('POST', '/api/p/callback', 'portal', PR, true, function (c) {
    var sc = scopes(c.user); need(sc, 'messages'); var pid = c.user.patient_id, note = textField(c.body.note === undefined ? '' : c.body.note, 'Note', 300, false).trim() || 'Please call me back.', cs = pcase(pid);
    var r = createTask(c.user, { patient_id: pid, case_id: cs.id, type: 'callback', category: 'Call-back request', source: 'patient', patient_visible: 1, dedupe_key: 'callback:' + pid, blocked_step: 'Patient asked for a call back', reason: 'Call-back request', next_action: 'Phone the patient at the number on file', route: R.ROUTES['Call-back request'] });
    if (r[1]) { db.msgs.push({ id: ++nid.msg, task_id: r[0].id, case_id: cs.id, patient_id: pid, author_key: c.user.key, author_role: 'patient', author_name: c.user.name, kind: 'patient_message', visibility: 'patient', body: note, created_at: now() }); log(c.user, 'message.created', 'message', r[0].id, cs.id, r[0].id, pid, { length: cnt(note), category: 'Call-back request' }); }
    return { task: patientTask(r[0]), created: r[1], existing_open_request: !r[1] };
  });
  /* Pass 2 tell-us-once intake form (Pass 1 demo patients only; recorded scenarios replay the real server) */
  function iform(c) {
    if (c.user.role !== 'patient') throw E(403, 'not_shared', 'This part of the portal has not been shared with you.');
    var pid = c.user.patient_id, cs = pcase(pid), p = pat(pid), I = R.INTAKE, op = function (a) { return a.map(function (x) { return { value: x[0], label: x[1] }; }); };
    return { prefill: [{ key: 'name', label: 'Name', value: p.name }, { key: 'phone', label: 'Phone', value: p.phone }], ask_facility: !cs.facility || cs.facility === 'Unknown', matters: I.MATTERS, contact_prefs: op(I.CONTACT_PREFS), redflags: op(I.REDFLAGS),
      redflag_guidance: I.GUIDANCE, emergency_patterns: R.EMERGENCY, status: cs.intake_status, confirmed_by_patient: true, draft: (db.idrafts || {})[cs.id] ? db.idrafts[cs.id].a : null, draft_saved_at: (db.idrafts || {})[cs.id] ? db.idrafts[cs.id].at : null, draft_by: (db.idrafts || {})[cs.id] ? c.user.name : null,
      submitted_at: null, submitted_by: null, submitted_answers: null, viewer: 'patient', patient_first: p.name.split(' ')[0], safety_flagged: !!cs.flagged, medical_copy_note: 'Symptom wording is example text pending Dr. Yakel\u2019s review. This form is not a clinical triage system.' };
  }
  function iflag(c, cs, a) {
    var hit = a.other && RXE.some(function (r) { return r.test(a.other.replace(/\u2019/g, "'")); });
    if (!(a.redflags || []).length && !hit) return false; cs.flagged = true;
    createTask(c.user, { patient_id: cs.patient_id, case_id: cs.id, type: 'red_flag', category: 'Red flag', source: 'case', patient_visible: 1, dedupe_key: 'redflag:' + cs.id, priority: 'urgent', blocked_step: 'URGENT: red-flag symptom reported in intake', reason: 'Reported in the intake form (snapshot mock).', next_action: 'Phone the patient now. Only a nurse or clinician can clear it.', owner: 'nina', backup: 'yakel', hours: 2, clinical_level: 1 });
    return true;
  }
  route('GET', '/api/p/intake', 'portal', PR, false, function (c) { return iform(c); });
  route('PUT', '/api/p/intake/draft', 'portal', PR, false, function (c) {
    var f = iform(c), cs = pcase(c.user.patient_id); if (cs.intake_status === 'completed') throw E(409, 'already_submitted', 'This intake was already sent.');
    var a = c.body.answers || {}; db.idrafts = db.idrafts || {}; var at = now(); db.idrafts[cs.id] = { a: a, at: at }; var fl = iflag(c, cs, a);
    return { saved_at: at, red_flag: fl, guidance: fl ? R.INTAKE.GUIDANCE : null };
  });
  route('POST', '/api/p/intake', 'portal', ['patient'], true, function (c) {
    if (c.body.answers) {
      var f = iform(c), a = c.body.answers, cs = pcase(c.user.patient_id), conf = a.confirm || {};
      for (var i = 0; i < f.prefill.length; i++) if (!conf[f.prefill[i].key]) throw E(422, 'confirm_each', 'Please tell us whether \u201c' + f.prefill[i].label + '\u201d is right.', { field: f.prefill[i].key });
      if (!a.contact_pref) throw E(422, 'contact_required', 'Please choose how you prefer us to contact you.');
      if ((a.redflags || []).length && a.redflag_none) throw E(422, 'redflag_conflict', 'You ticked a symptom and also \u201cnone of these\u201d. Please check that question.');
      if (!(a.redflags || []).length && !a.redflag_none) throw E(422, 'redflag_required', 'Please answer the symptom question: tick any that apply, or \u201cNone of these\u201d.');
      if (a.confirmed !== true) throw E(422, 'confirm_required', 'Please confirm your answers are right.');
      var fl = iflag(c, cs, a); db.intake[cs.id] = a; cs.intake_status = 'completed'; log(c.user, 'case.intake_completed', 'case', cs.id, cs.id, null, cs.patient_id, { form: 'tell-us-once (snapshot mock)' });
      return { ok: true, saved_at: now(), red_flag: fl, guidance: fl ? R.INTAKE.GUIDANCE : null, needs_patient_confirmation: false };
    }
    var pid = c.user.patient_id, cs = pcase(pid); if (c.body.confirmed !== true) throw E(422, 'confirm_required', 'Please confirm your details are right.');
    var m = c.body.matters || []; if (!Array.isArray(m) || m.length > 8) throw E(422, 'invalid', 'Invalid choices.'); textField(c.body.note === undefined ? '' : c.body.note, 'Note', 500, false);
    db.intake[cs.id] = { matters: m, note: c.body.note }; cs.intake_status = 'completed'; log(c.user, 'case.intake_completed', 'case', cs.id, cs.id, null, pid, { fields: ['matters', 'note'] }); return { ok: true, saved_at: now() };
  });
  route('POST', '/api/p/imaging', 'portal', ['patient'], true, function (c) {
    var pid = c.user.patient_id, cs = pcase(pid), fac = textField(c.body.facility, 'Facility name', 120).trim(); cs.facility = fac; if (cs.report_status === 'not_requested') cs.report_status = 'requested';
    var r = createTask(c.user, { patient_id: pid, case_id: cs.id, type: 'records_request', dedupe_key: 'records:' + cs.id, patient_visible: 1, patient_label: 'Your MRI report', blocked_step: 'Records request ready to send', reason: 'Patient named the facility: ' + fac, next_action: 'Send the records request to ' + fac, route: ['pat', 'nina', 24, 'Front desk', 0] }), t = r[0];
    if (!r[1] && t.status !== 'Resolved') { t.blocked_step = 'Records request ready to send'; t.reason = 'Patient named the facility: ' + fac; t.next_action = 'Send the records request to ' + fac; t.updated_at = now(); if (t.status === 'Waiting') doTransition(null, t, 'In Progress', { system: true }); }
    log(c.user, 'case.facility_provided', 'case', cs.id, cs.id, t.id, pid, { facility: fac }); return { ok: true };
  });
  route('POST', '/api/p/appointments/(\\d+)/confirm', 'portal', ['patient'], true, function (c) {
    var a = db.appts.filter(function (x) { return x.id === +c.m[1]; })[0]; if (!a || a.patient_id !== c.user.patient_id) throw E(404, 'not_found', 'No such appointment.'); a.confirmed = 1;
    db.notifs.forEach(function (n) { if (n.patient_id === a.patient_id && n.action === 'confirm_appointment' && ['sent', 'delivered', 'received'].indexOf(n.status) >= 0) { n.status = 'accepted'; n.accepted_at = now(); log(c.user, 'notification.accepted', 'notification', n.id, null, null, a.patient_id, { action: 'confirm_appointment' }); } });
    log(c.user, 'appointment.confirmed', 'appointment', a.id, a.case_id, null, a.patient_id); return { ok: true };
  });
  route('GET', '/api/p/helper', 'portal', ['patient'], false, function (c) { var g = db.grants.filter(function (x) { return x.patient_id === c.user.patient_id; })[0]; return { helper: g ? { name: 'Riley Helper', status: g.status, scopes: g.scopes } : null }; });
  route('PUT', '/api/p/helper', 'portal', ['patient'], false, function (c) {
    var g = db.grants.filter(function (x) { return x.patient_id === c.user.patient_id; })[0]; if (!g) throw E(404, 'no_helper', 'No helper has been invited.'); var st = c.body.status || g.status;
    if (st !== 'active' && st !== 'stopped') throw E(422, 'invalid', 'Invalid choice.'); Object.keys(g.scopes).forEach(function (k) { if (c.body.scopes && k in c.body.scopes) { if (typeof c.body.scopes[k] !== 'boolean') throw E(422, 'invalid', 'Invalid choice.'); g.scopes[k] = c.body.scopes[k]; } }); g.status = st;
    log(c.user, 'grant.updated', 'grant', 1, null, null, g.patient_id, { scopes: g.scopes, status: st }); return { helper: { name: 'Riley Helper', status: st, scopes: g.scopes } };
  });
  function getTask(id) { var t = task(id); if (!t) throw E(404, 'not_found', 'No such task.'); return t; }
  route('GET', '/api/o/me', 'office', OFF, false, function (c) { var u = c.user; return { user: { key: u.key, name: u.name, role: u.role, team: u.team }, banner: R.BANNER, limits: { message: MAXN.message, draft: MAXN.draft, note: MAXN.note, outcome: MAXN.outcome }, can: { reports: u.role === 'admin' || u.role === 'clinician', audit: u.role === 'admin', settings: u.role === 'admin' } }; });
  route('POST', '/api/o/logout', 'office', OFF, false, function () { sess.office = null; return { ok: true }; });
  route('GET', '/api/o/staff', 'office', OFF, false, function () { return { staff: db.users.filter(function (u) { return OFF.indexOf(u.role) >= 0; }).map(function (u) { return { key: u.key, name: u.name, role: u.role, team: u.team }; }) }; });
  route('GET', '/api/o/queue', 'office', OFF, false, function (c) {
    var f = c.q.filter || 'open', me = c.user.key, ts = db.tasks.slice();
    if (f === 'mine') ts = ts.filter(function (t) { return t.status !== 'Resolved' && (t.owner === me || t.backup === me); }); else if (f === 'unowned') ts = ts.filter(function (t) { return t.status !== 'Resolved' && !t.owner; }); else if (f === 'overdue') ts = ts.filter(overdue); else if (f === 'waiting') ts = ts.filter(function (t) { return t.status === 'Waiting'; }); else if (f === 'resolved') ts = ts.filter(function (t) { return t.status === 'Resolved'; }); else if (f !== 'all') ts = ts.filter(function (t) { return t.status !== 'Resolved'; });
    ts.sort(function (a, b) { var ka = [a.status === 'Resolved', a.priority !== 'urgent', !overdue(a), a.deadline || '9999'], kb = [b.status === 'Resolved', b.priority !== 'urgent', !overdue(b), b.deadline || '9999']; for (var i = 0; i < 4; i++) { if (ka[i] < kb[i]) return -1; if (ka[i] > kb[i]) return 1; } return 0; });
    var counts = {}; STATUSES.forEach(function (s) { counts[s] = db.tasks.filter(function (t) { return t.status === s; }).length; });
    var pinned = db.tasks.filter(function (t) { return t.status !== 'Resolved' && t.priority === 'urgent'; }).map(staffTask), q = qualified(c.user);
    var mine = db.tasks.filter(function (t) { return t.status !== 'Resolved' && t.owner === me && t.priority !== 'urgent'; }), nx = q && pinned.length ? pinned[0] : (mine.filter(function (t) { return t.status !== 'Waiting'; })[0] || mine[0]);
    return { filter: f, tasks: ts.map(staffTask), counts: counts, pinned: pinned, groups: [], next_up: nx ? nx.id : null, next_up_task: nx ? (nx.patient_name ? nx : staffTask(nx)) : null, next_up_kind: nx && nx.priority === 'urgent' ? 'urgent' : 'routine', can_act_on_urgent: q,
      urgent_notice: pinned.length && !q ? { count: pinned.length, text: pinned.length + ' urgent clinical item(s) open. A nurse or clinician handles them \u2014 nothing for you to do on them.', items: pinned.map(function (d) { return { id: d.id, patient_name: d.patient_name, attention: d.blocked_step, owner_name: d.owner_name || 'Unassigned' }; }) } : null };
  });
  route('GET', '/api/o/calls-avoided', 'office', OFF, false, function () {   /* Pass 1 mock: same labels as the server; counts from this tab's made-up data */
    var n = function (a) { return db.events.filter(function (e) { return e.action === a; }).length; };
    return { lines: [['Times patients checked \u201cwhere things stand\u201d in the portal while something was pending', n('status.viewed')], ['Automatic follow-ups sent to outside offices and insurers (simulated)', n('chase.sent')],
      ['Intake reminders sent automatically (simulated text)', n('intake.reminder_sent')], ['Intake forms completed in the portal instead of by phone', n('case.intake_completed')], ['Post-op check-ins answered in the portal', n('checkin.answered')],
      ['Follow-ups that got stuck and needed a person (these still became calls)', n('chase.stuck')]], label: 'EXAMPLE COUNTS ONLY \u2014 counted from this demo\u2019s fictional data.',
      note: 'Each line is something a patient or office might otherwise have phoned about. It is not a measured reduction in calls, and it says nothing about staff time or cost. (Static snapshot: counted in your browser.)' };
  });
  route('GET', '/api/o/tasks/(\\d+)', 'office', OFF, false, function (c) {
    var t = getTask(+c.m[1]); log(c.user, 'task.view', 'task', t.id, t.case_id, t.id, t.patient_id); var cs = kase(t.case_id), p = pat(t.patient_id);
    var conv = db.msgs.filter(function (m) { return m.task_id === t.id; }).map(function (m) { return { id: m.id, author_role: m.author_role, author_name: m.author_name, kind: m.kind, visibility: m.visibility, body: m.body, created_at: m.created_at }; });
    var hist = db.events.filter(function (e) { return (e.task_id === t.id || (e.case_id === t.case_id && /^(case|document)\./.test(e.action))) && e.action !== 'task.view'; });
    var d = db.drafts[t.id + ':' + c.user.key], draft = null;
    if (t.source === 'patient' && t.status !== 'Resolved') draft = d ? { body: d.body, source: 'saved', saved_at: d.updated_at } : { body: suggest(t), source: 'suggestion', saved_at: null, label: 'Suggested draft \u00b7 canned template, simulated AI \u00b7 never sent automatically' };
    var nxt = Object.keys(TI).map(function (k) { return k.split('>'); }).filter(function (k) { return k[0] === t.status && !(k[0] === 'Waiting' && k[1] === 'Assigned'); }).map(function (k) { return k[1]; }), lvl = t.clinical_level;
    var canRes = lvl === 0 || (lvl === 1 && (c.user.role === 'clinician' || c.user.team === 'nurse')) || (lvl === 2 && c.user.role === 'clinician');
    return { task: staffTask(t), case: Object.assign({}, cs, stageInfo(cs)), patient: { id: p.id, name: p.name, phone: p.phone, email: p.email, channel: p.channel, phone_valid: p.phone_valid }, conversation: conv, history: hist, documents: db.docs.filter(function (x) { return x.case_id === t.case_id; }), notifications: db.notifs.filter(function (n) { return n.task_id === t.id; }).map(notifDto), draft: draft,
      allowed: { next: nxt, can_resolve: canRes, resolve_note: canRes ? null : (lvl === 2 ? 'Only a clinician can resolve this.' : 'Only a nurse or clinician can resolve this.'), can_reply: t.source === 'patient' && t.status !== 'Received' && t.status !== 'Resolved', reply_note: t.source === 'patient' ? null : 'This task has no patient conversation. Use the notes, or phone the patient.' }, limits: { message: MAXN.message, draft: MAXN.draft } };
  });
  route('POST', '/api/o/tasks/(\\d+)/assign', 'office', OFF, true, function (c) {
    var t = getTask(+c.m[1]); if (t.status === 'Resolved') throw E(409, 'task_resolved', 'Reopen the task before changing who owns it.'); var ow = c.body.owner, bk = c.body.backup, ok = db.users.filter(function (u) { return OFF.indexOf(u.role) >= 0; }).map(function (u) { return u.key; });
    if (ok.indexOf(ow) < 0 || ok.indexOf(bk) < 0) throw E(422, 'bad_staff', 'Owner and backup must be staff members.'); if (ow === bk) throw E(422, 'same_person', 'The backup must be a different person from the owner.'); var dl = toDeadline(c.body.deadline);
    var before = { owner: t.owner, backup: t.backup, deadline: t.deadline }; t.owner = ow; t.backup = bk; t.deadline = dl; t.updated_at = now(); log(c.user, 'task.assigned', 'task', t.id, t.case_id, t.id, t.patient_id, { before: before, after: { owner: ow, backup: bk, deadline: dl } });
    if (t.status === 'Received') doTransition(c.user, t, 'Assigned'); return { task: staffTask(t) };
  });
  route('POST', '/api/o/tasks/(\\d+)/transition', 'office', OFF, true, function (c) {
    var t = getTask(+c.m[1]), to = c.body.to; if (STATUSES.indexOf(to) < 0) throw E(422, 'bad_status', 'Unknown status.'); if (t.status === 'Waiting' && to === 'Assigned') throw E(403, 'system_only', 'Only the system moves a task back to Assigned when a follow-up date passes.');
    doTransition(c.user, t, to, c.body); return { task: staffTask(t) };
  });
  route('POST', '/api/o/tasks/(\\d+)/reply', 'office', OFF, true, function (c) {
    var t = getTask(+c.m[1]); if (t.source !== 'patient') throw E(409, 'no_patient_thread', 'This task has no patient conversation.'); if (t.status === 'Received') throw E(409, 'assign_first', 'Assign an owner, backup and deadline first.'); if (t.status === 'Resolved') throw E(409, 'task_resolved', 'Reopen the task before replying.');
    var body = textField(c.body.body, 'Reply', MAXN.message), kind = c.body.kind === 'ack' ? 'ack' : 'reply';
    var m = { id: ++nid.msg, task_id: t.id, case_id: t.case_id, patient_id: t.patient_id, author_key: c.user.key, author_role: c.user.role, author_name: c.user.name, kind: 'staff_' + kind, visibility: 'patient', body: body, created_at: now() }; db.msgs.push(m);
    if (kind === 'ack') t.ack_at = t.ack_at || now(); else t.first_reply_at = t.first_reply_at || now(); t.updated_at = now();
    log(c.user, kind === 'ack' ? 'task.acknowledged' : 'message.reply', 'message', m.id, t.case_id, t.id, t.patient_id, { length: cnt(body), status_unchanged: t.status }); if (t.status === 'Assigned') doTransition(c.user, t, 'In Progress');
    var n_ = queueNotif(t.patient_id, t.id, kind, kind === 'ack' ? 'Premier Spine: we received your request. Open your portal for details.' : 'Premier Spine: you have a new message in your portal.'); delete db.drafts[t.id + ':' + c.user.key];
    return { task: staffTask(t), message_id: m.id, notification_id: n_, still_open: t.status !== 'Resolved', note: 'Sent in the portal. The task is still open.' };
  });
  route('POST', '/api/o/tasks/(\\d+)/note', 'office', OFF, true, function (c) {
    var t = getTask(+c.m[1]); if (t.status === 'Resolved') throw E(409, 'task_resolved', 'Reopen the task first.'); var body = textField(c.body.body, 'Note', MAXN.note);
    var m = { id: ++nid.msg, task_id: t.id, case_id: t.case_id, patient_id: t.patient_id, author_key: c.user.key, author_role: c.user.role, author_name: c.user.name, kind: 'staff_note', visibility: 'staff', body: body, created_at: now() }; db.msgs.push(m);
    log(c.user, 'task.note', 'message', m.id, t.case_id, t.id, t.patient_id, { length: cnt(body) }); if (t.status === 'Assigned') doTransition(c.user, t, 'In Progress'); return { message_id: m.id };
  });
  route('POST', '/api/o/tasks/(\\d+)/verify', 'office', OFF, true, function (c) {
    var t = getTask(+c.m[1]); if (t.status === 'Resolved') throw E(409, 'task_resolved', 'Reopen the task first.'); var src = textField(c.body.source_note === undefined ? '' : c.body.source_note, 'Source', 120, false).trim(), label = c.user.name + (src ? ' \u2014 ' + src : '');
    t.last_verified_at = now(); t.last_verified_source = label; t.updated_at = now(); log(c.user, 'task.verified_update', 'task', t.id, t.case_id, t.id, t.patient_id, { source: label }); return { task: staffTask(t) };
  });
  route('PUT', '/api/o/tasks/(\\d+)/draft', 'office', OFF, false, function (c) {
    var t = getTask(+c.m[1]); if (t.source !== 'patient' || t.status === 'Resolved') throw E(409, 'no_draft', 'This task cannot have a reply draft.'); var body = textField(c.body.body === undefined ? '' : c.body.body, 'Draft', MAXN.draft, false), ts = now();
    db.drafts[t.id + ':' + c.user.key] = { body: body, updated_at: ts }; return { saved_at: ts, length: cnt(body) };
  });
  route('GET', '/api/o/appointments/today', 'office', OFF, false, function () {
    var today = ptDate(), out = []; db.appts.slice().sort(function (a, b) { return a.starts_at < b.starts_at ? -1 : 1; }).forEach(function (a) {
      if (ptDate(ms(a.starts_at)) !== today) return; var cs = kase(a.case_id), si = stageInfo(cs);
      var tk = db.tasks.filter(function (t) { return t.case_id === cs.id && t.status !== 'Resolved'; }).sort(function (x, y) { return (x.deadline || '9999') < (y.deadline || '9999') ? -1 : 1; })[0];
      out.push({ id: a.id, starts_at: a.starts_at, patient_name: pat(a.patient_id).name, clinician: a.clinician, kind: a.kind, missing: si.missing, ready: si.ready, task_id: tk ? tk.id : null });
    }); return { date: today, appointments: out };
  });
  route('POST', '/api/o/docs/(\\d+)/review', 'office', ['clinician'], true, function (c) {
    var d = db.docs.filter(function (x) { return x.id === +c.m[1]; })[0]; if (!d) throw E(404, 'not_found', 'No such document.'); if (d.doc_type !== 'radiology_report' || d.status !== 'received') throw E(409, 'not_reviewable', 'Only a received radiology report can be marked reviewed.');
    d.status = 'reviewed'; d.reviewed_by = c.user.key; kase(d.case_id).report_status = 'reviewed'; log(c.user, 'document.reviewed', 'document', d.id, d.case_id, null, d.patient_id, { type: d.doc_type });
    var t = db.tasks.filter(function (x) { return x.case_id === d.case_id && x.type === 'records_review' && x.status !== 'Resolved'; })[0]; if (t && t.status !== 'Received') doTransition(c.user, t, 'Resolved', { outcome: 'Report reviewed by ' + c.user.name + '.' });
    return { ok: true, note: 'Report reviewed. Image availability is tracked separately and was not changed.' };
  });
  route('POST', '/api/o/cases/(\\d+)/images', 'office', OFF, true, function (c) {
    var cs = kase(+c.m[1]); if (!cs) throw E(404, 'not_found', 'No such case.'); var st = c.body.images_status; if (['unknown', 'requested', 'received', 'unavailable', 'waived'].indexOf(st) < 0) throw E(422, 'bad_status', 'Unknown image status.');
    if (st === 'waived' && c.user.role !== 'clinician') throw E(403, 'clinician_required', 'Only a clinician can proceed without images.'); var note = textField(c.body.note === undefined ? '' : c.body.note, 'Note', 300, st === 'waived').trim();
    var from = cs.images_status; cs.images_status = st; log(c.user, 'case.images_status', 'case', cs.id, cs.id, null, cs.patient_id, { from: from, to: st, note: note }); return { ok: true, report_status: cs.report_status, images_status: st, note: 'Report status and image status are separate; only image status changed.' };
  });
  route('GET', '/api/o/notifications', 'office', OFF, false, function () { return { notifications: db.notifs.slice().reverse().slice(0, 100).map(notifDto), max_attempts: 3 }; });
  route('POST', '/api/o/notifications/(\\d+)/retry', 'office', OFF, true, function (c) {
    var n = db.notifs.filter(function (x) { return x.id === +c.m[1]; })[0]; if (!n) throw E(404, 'not_found', 'No such notification.'); if (n.status !== 'failed') throw E(409, 'not_failed', 'Only a failed notification can be retried.'); if (n.manual_retries >= 2) throw E(409, 'retry_limit', 'Retry limit reached (2). Phone the patient instead.');
    n.status = 'queued'; n.attempts = 0; n.manual_retries++; n.last_error = null; log(c.user, 'notification.manual_retry', 'notification', n.id, null, n.task_id, n.patient_id, { manual_retries: n.manual_retries }); return { ok: true };
  });
  route('POST', '/api/o/patients/(\\d+)/contact', 'office', OFF, true, function (c) { var p = pat(+c.m[1]); if (!p) throw E(404, 'not_found', 'No such patient.'); p.phone = textField(c.body.phone, 'Phone', 30).trim(); p.phone_valid = c.body.phone_valid ? 1 : 0; log(c.user, 'patient.contact_updated', 'patient', p.id, null, null, p.id, { phone_valid: !!c.body.phone_valid }); return { ok: true }; });
  function median(a) { a = a.slice().sort(function (x, y) { return x - y; }); var n = a.length; return n ? (n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2) : null; }
  route('GET', '/api/o/reports', 'office', ['admin', 'clinician'], false, function () {
    var ts = db.tasks, live = ts.filter(function (t) { return t.origin === 'live'; }), by = {}; STATUSES.forEach(function (s) { by[s] = ts.filter(function (t) { return t.status === s; }).length; });
    var mins = function (a, b) { return (ms(b) - ms(a)) / 60000; }, ack = live.filter(function (t) { return t.ack_at; }).map(function (t) { return mins(t.created_at, t.ack_at); }), rep = live.filter(function (t) { return t.first_reply_at; }).map(function (t) { return mins(t.created_at, t.first_reply_at); });
    var staffEv = function (e) { return OFF.indexOf(e.actor_role) >= 0 && e.action !== 'task.view'; }, resl = live.filter(function (t) { return t.status === 'Resolved'; }), tl = resl.map(function (t) { return db.events.filter(function (e) { return e.task_id === t.id && staffEv(e); }).length; });
    var r1 = function (v) { return v === null ? null : Math.round(v * 10) / 10; }, nt = {}; ['queued', 'sent', 'delivered', 'received', 'accepted', 'failed'].forEach(function (k) { nt[k] = db.notifs.filter(function (n) { return n.status === k; }).length; });
    return { measured_from: 'this prototype database only', tasks_total: ts.length, tasks_by_status: by, seeded_tasks: ts.length - live.length, live_tasks: live.length, overdue_open: ts.filter(overdue).length, unowned_open: ts.filter(function (t) { return t.status !== 'Resolved' && !t.owner; }).length,
      status_changes: db.events.filter(function (e) { return e.action === 'task.transition'; }).length, staff_touches_total: db.events.filter(staffEv).length, touches_per_resolved_live_task: { n: tl.length, mean: tl.length ? r1(tl.reduce(function (a, b) { return a + b; }, 0) / tl.length) : null },
      minutes_to_first_acknowledgment: { n: ack.length, median: r1(median(ack)) }, minutes_to_first_reply: { n: rep.length, median: r1(median(rep)) }, notifications: nt, open_exception_tasks: ts.filter(function (t) { return t.type === 'exception' && t.status !== 'Resolved'; }).length,
      notes: ['Only values counted from this database are shown. Nothing here is estimated.', 'Seeded example tasks are excluded from timing and touch measures (they were created by the seed script, not by work).', 'Released staff time is not payroll savings. Hours freed only become savings if staffing or paid hours actually change.', 'A tiny sample (a few clicks in a demo) is not evidence of anything.'] };
  });
  route('GET', '/api/o/audit', 'office', ['admin'], false, function (c) { var lim = Math.min(parseInt(c.q.limit || '200', 10) || 200, 500); return { events: db.events.slice().reverse().slice(0, lim) }; });
  route('GET', '/api/o/settings', 'office', OFF, false, function () { return { patient_reply_target: setting('reply_target') }; });
  route('PUT', '/api/o/settings', 'office', ['admin'], false, function (c) { var v = textField(c.body.patient_reply_target === undefined ? '' : c.body.patient_reply_target, 'Reply target', 80, false).trim(); db.settings.reply_target = v; log(c.user, 'settings.updated', 'settings', 'patient_reply_target', null, null, null, { value: v }); return { patient_reply_target: v }; });
  function needP() { if (!presenter) throw E(403, 'presenter_off', 'Turn on Presenter mode first.'); }
  route('POST', '/api/presenter/enter', null, null, false, function () { presenter = true; return { presenter: true }; });
  route('POST', '/api/presenter/leave', null, null, false, function () { presenter = false; return { presenter: false }; });
  route('POST', '/api/presenter/reset', null, null, false, function () { needP(); seed(); sess.portal = sess.office = null; return { ok: true, note: 'Browser memory re-created from the fictional seed. All sign-ins ended.' }; });
  route('POST', '/api/presenter/tick', null, null, false, function () { needP(); return tick(); });
  route('GET', '/api/presenter/state', null, null, false, function () { needP(); var c = {}; ['patients', 'tasks', 'msgs', 'notifs', 'events'].forEach(function (k) { c[{ msgs: 'messages', notifs: 'notifications' }[k] || k] = db[k].length; }); c.drafts = Object.keys(db.drafts).length; c.idempotency = Object.keys(db.idem).length; return { tables: c, notifications: db.notifs.slice().reverse().slice(0, 10).map(function (n) { return { id: n.id, patient_id: n.patient_id, template: n.template, status: n.status, attempts: n.attempts, last_error: n.last_error }; }), db: 'in-browser memory', banner: R.BANNER }; });
  route('POST', '/api/presenter/scenario', null, null, false, function (c) {
    needP(); var name = c.body.name, msg;
    if (name === 'bad_phone_jordan') { pat(2).phone_valid = 0; log(null, 'scenario.bad_phone', 'patient', 2, null, null, 2, { note: 'presenter set Jordan\u2019s number to unreachable' }); msg = 'Jordan\u2019s number is now unreachable (simulated). Reply to Jordan in the office view, then run the delivery step three times: the notification fails and an exception task appears.'; }
    else if (name === 'good_phone_jordan') { pat(2).phone_valid = 1; log(null, 'scenario.good_phone', 'patient', 2, null, null, 2); msg = 'Jordan\u2019s number works again.'; }
    else if (name === 'report_arrives_alex') {
      var cs = kase(1); if (cs.report_status === 'received' || cs.report_status === 'reviewed') throw E(409, 'already', 'The report has already arrived.'); if (!cs.facility) cs.facility = 'Lakeshore Imaging (fictional)'; cs.report_status = 'received';
      var d = db.docs.filter(function (x) { return x.id === 2; })[0]; d.status = 'received'; d.source = 'Lakeshore Imaging (fictional)'; d.note = 'Placeholder \u2014 awaiting clinician review.'; log(null, 'document.received', 'document', 2, 1, null, 1, { note: 'presenter simulated the report arriving by fax; images NOT included' });
      var t = db.tasks.filter(function (x) { return x.case_id === 1 && x.type === 'records_request' && x.status !== 'Resolved'; })[0]; if (t && t.status === 'Waiting') doTransition(null, t, 'In Progress', { system: true });
      createTask(null, { patient_id: 1, case_id: 1, type: 'records_review', source: 'case', dedupe_key: 'review:1', blocked_step: 'MRI report received \u2014 clinician review needed', reason: 'Report arrived by fax (simulated). Images were not included.', next_action: 'Review the report and mark it reviewed.', owner: 'yakel', backup: 'nina', hours: 24, clinical_level: 2 });
      msg = 'Alex\u2019s MRI report arrived (simulated). The images did not \u2014 image availability is tracked separately.';
    } else throw E(422, 'unknown_scenario', 'Unknown scenario.'); return { ok: true, message: msg };
  });
  /* preview19 publish: a recorded state can't change; say so calmly and honestly (shared.js shows it as a demo notice, not an error) */
  function RO() { return E(409, 'demo_recording', 'Demo recording: in the full version this saves to the server. Nothing was sent or saved here.'); }
  function replayCall(method, path, body) {
    var app = path.indexOf('/api/p/') === 0 ? 'portal' : path.indexOf('/api/o/') === 0 ? 'office' : null, K = REC.keys[replay];
    if (path === '/api/presenter/scenarios' && method === 'GET') { if (!presenter) throw E(403, 'presenter_off', 'Turn on Presenter mode first.'); return { scenarios: REC.scenarios }; }
    if (!app) return undefined;
    if (method === 'PUT' && path === '/api/p/intake/draft') return { saved_at: now(), demo: true };   /* kept on the page only; SAVED_WHERE says so */
    if (method === 'POST' && path === '/api/p/assist' && K.assist) {   /* recorded answers to the four example questions */
      var ra = body && body.intent && K.assist[body.intent]; if (ra) return Object.assign({}, ra, { answered_at: now(), demo_recording: true });
      throw E(409, 'demo_recording', 'Demo recording: only the four example questions above have recorded answers for this example patient. In the full version you can type your own question. Nothing was sent.'); }
    if (method !== 'GET') { if (/\/logout$/.test(path)) { replay = null; try { if (window.__PS_EXIT) setTimeout(window.__PS_EXIT, 0); } catch (e) {} return { ok: true }; } throw RO(); }
    var hit = K.get[app + ' ' + path];
    if (!hit) throw E(409, 'not_recorded', 'This screen isn\u2019t part of this demo recording. Nothing was changed.');
    var hb = typeof hit[1] === 'number' ? REC.blobs[hit[1]] : hit[1];   /* published build: identical responses are stored once */
    if (hit[0] >= 400) throw E(hit[0], hb.error, hb.message);
    return hb;
  }
  function setReplay(k) { replay = k; }
  function call(method, path, body, o) {
    return new Promise(function (resolve, reject) {
      setTimeout(function () {
        try {
          if (REC && path === '/api/presenter/scenario/load' && method === 'POST') {
            if (!presenter) throw E(403, 'presenter_off', 'Turn on Presenter mode first.');
            /* a recording slot: key, plus :step, @office persona and +helper when they differ from the key state */
            var k = body && body.key; if (!REC.keys[k]) throw E(422, 'unknown_scenario', 'Unknown scenario.');
            k = k + ((body.step || 'key') !== 'key' ? ':' + body.step : '') + (body.office_as ? '@' + body.office_as : '') + (body.as_helper ? '+helper' : ''); var K = REC.keys[k];
            if (!K) throw E(409, 'not_recorded', 'Only each scenario\u2019s KEY STATE is recorded in the static snapshot. To start a scenario from the beginning, run the local server.');
            replay = k; try { if (window.__PS_RELOAD) setTimeout(function () { window.__PS_RELOAD('Showing scenario ' + K.n + ' (' + K.title + ') \u2014 ' + K.message); }, 0); } catch (e) {}
            return resolve({ ok: true, message: K.message, portal_as: K.portal_as, office_as: K.office_as });
          }
          if (REC && path === '/api/presenter/scenario/advance') throw E(409, 'not_recorded', 'Simulated events need the local server; the snapshot only replays recorded key states.');
          if (replay && path === '/api/login') replay = null;
          if (replay) { var rr = replayCall(method, path.split('#')[0], body); if (rr !== undefined) return resolve(JSON.parse(JSON.stringify(rr))); }
          if (REC && path === '/api/presenter/scenarios') { if (!presenter) throw E(403, 'presenter_off', 'Turn on Presenter mode first.'); return resolve(JSON.parse(JSON.stringify({ scenarios: REC.scenarios }))); }
          var qi = path.indexOf('?'), p = qi < 0 ? path : path.slice(0, qi), q = {}; if (qi >= 0) path.slice(qi + 1).split('&').forEach(function (kv) { var a = kv.split('='); q[decodeURIComponent(a[0])] = decodeURIComponent(a[1] || ''); });
          var r = null, m = null; for (var i = 0; i < routes.length; i++) { if (routes[i].method === method) { m = routes[i].rx.exec(p); if (m) { r = routes[i]; break; } } }
          if (!r) throw E(404, 'not_found', 'Not found.');
          var user = null;
          if (r.app) { var k = sess[r.app]; if (!k) throw E(401, 'unauthenticated', 'Please sign in.'); user = U(k); if (r.roles.indexOf(user.role) < 0) throw E(403, 'forbidden', 'Your role cannot do this.'); }
          var hsh = null, ik = null;
          if (r.idem) { if (!o || !o.key) throw E(400, 'idempotency_key_required', 'Idempotency-Key header (1-80 chars) is required for this request.'); hsh = method + p + JSON.stringify(body); ik = o.key + '|' + (user ? user.key : ''); var prev = db.idem[ik];
            if (prev) { if (prev.h !== hsh) throw E(422, 'idempotency_key_reuse', 'That Idempotency-Key was already used for a different request.'); return resolve(JSON.parse(prev.resp)); } }
          var res = r.fn({ user: user, body: body || {}, q: q, m: m }); if (r.idem) db.idem[ik] = { h: hsh, resp: JSON.stringify(res) }; resolve(JSON.parse(JSON.stringify(res)));
        } catch (e) { reject(e); }
      }, 30);
    });
  }
  /* preview19 publish: recordings are moved forward to TODAY (whole days, Pacific wall-clock kept), so "tomorrow's visit" stays tomorrow
     whenever the online demo is opened.  Only demo recordings carry recorded_day; the local snapshot is unchanged. */
  function shiftRecordings() {
    if (!REC || !REC.recorded_day || !REC.blobs) return;
    var F = new Intl.DateTimeFormat('en-US', { timeZone: PTZ, hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric' });
    function off(t) { var o = {}; F.formatToParts(new Date(t)).forEach(function (p) { o[p.type] = parseInt(p.value, 10); }); return (Date.UTC(o.year, o.month - 1, o.day, o.hour, o.minute, o.second) - Math.floor(t / 1000) * 1000) / 60000; }
    var days = Math.round((Date.parse(ptDate() + 'T12:00:00Z') - Date.parse(REC.recorded_day + 'T12:00:00Z')) / 86400000);
    REC.shift_days = days; if (days <= 0) return;
    var D = days * 86400000, cache = {};
    function sIso(s) { if (cache[s]) return cache[s]; var t = Date.parse(s); var u = t + D + (off(t) - off(t + D)) * 60000; return (cache[s] = iso(u)); }
    function sDay(s) { var a = s.split('-').map(Number), d = new Date(Date.UTC(a[0], a[1] - 1, a[2]) + D); return d.getUTCFullYear() + '-' + two(d.getUTCMonth() + 1) + '-' + two(d.getUTCDate()); }
    var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], LONG = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    var y0 = parseInt(REC.recorded_day.slice(0, 4), 10), RX = /\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)([a-z]*) (\d{1,2})\b/g;
    function sText(s) { return s.replace(RX, function (m, mo, rest, d) { var i = MON.indexOf(mo); if (rest && LONG[i] !== mo + rest) return m; var x = new Date(Date.UTC(y0, i, parseInt(d, 10)) + D); return (rest ? LONG : MON)[x.getUTCMonth()] + ' ' + x.getUTCDate(); }); }
    var ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(\.\d+)?Z$/, DAY = /^\d{4}-\d{2}-\d{2}$/;
    function walk(o, key) {
      if (typeof o === 'string') return ISO.test(o) ? sIso(o) : (DAY.test(o) && (key === 'default' || key === 'date')) ? sDay(o) : RX.test(o) ? (RX.lastIndex = 0, sText(o)) : o;
      if (Array.isArray(o)) { for (var i = 0; i < o.length; i++) o[i] = walk(o[i], key); return o; }
      if (o && typeof o === 'object') { Object.keys(o).forEach(function (k) { o[k] = walk(o[k], k); }); return o; }
      return o;
    }
    walk(REC.blobs, ''); Object.keys(REC.keys).forEach(function (k) { walk(REC.keys[k].assist || {}, ''); });
  }
  shiftRecordings();
  seed(); setInterval(function () { try { tick(); } catch (e) {} }, 2500);
  window.__PS_MOCK = { call: call, seed: seed, replay: setReplay, kind: 'static snapshot mock', banner: (REC && REC.banner) || null,
    rec: function (k) { var K = REC && REC.keys[k]; return K ? { open_task: K.open_task, n: K.n, title: K.title, portal_as: K.portal_as, office_as: K.office_as } : null; } };
})();
