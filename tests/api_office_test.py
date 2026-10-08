#!/usr/bin/env python3
"""preview19 Prompt C API tests: office priorities, urgent pinning + role enforcement, the booking hold, task cards/groups,
reminder dedupe + stop rules (fulfilled / opt-out / staff take-over / limit), one shared record for patient and staff, and the visit-ready summary draft.
Starts its own server on 127.0.0.1:8787 with a temp DB and --no-worker (the worker tick is driven explicitly through presenter endpoints)."""
import http.client, json, os, re, signal, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8787")); DB = os.path.join(tempfile.mkdtemp(), "toff.db")
RES = []; proc = None
def start():
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=open("/tmp/apioff_srv.log", "w"), stderr=subprocess.STDOUT)
    for _ in range(60):
        try: http.client.HTTPConnection("127.0.0.1", PORT, timeout=1).request("GET", "/api/health"); return
        except Exception: time.sleep(0.1)
    raise SystemExit("server did not start")
def _port_free():
    import socket; s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try: s.bind(("127.0.0.1", PORT)); return True
    except OSError: return False
    finally: s.close()
if not _port_free(): raise SystemExit(f"port {PORT} is busy (a stale server?) - refusing to test against it")
def stop():
    if proc and proc.poll() is None: proc.send_signal(signal.SIGTERM); proc.wait(10)
import atexit; atexit.register(stop)
def req(method, path, body=None, token=None, key=None, cookie=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=15); h = {"Host": f"127.0.0.1:{PORT}", "X-PS-Client": "1"}
    if token: h["Authorization"] = "Bearer " + token
    if key: h["Idempotency-Key"] = key
    if cookie: h["Cookie"] = cookie
    data = None
    if body is not None: data = json.dumps(body, ensure_ascii=False).encode(); h["Content-Type"] = "application/json"
    c.request(method, path, data, h); r = c.getresponse(); b = r.read(); hd = r.getheaders(); c.close()
    try: j = json.loads(b)
    except Exception: j = None
    return r.status, j, hd
def check(name, cond, info=""):
    RES.append((name, bool(cond), str(info)[:300])); print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  <-- " + str(info)[:300]), flush=True)
def K(): return uuid.uuid4().hex
TOK = {}
def tok(who, app):
    if (who, app) not in TOK:
        s, j, hd = req("POST", "/api/login", {"persona": who, "app": app}); assert s == 200, (who, app, s, j)
        TOK[(who, app)] = [v for k, v in hd if k == "Set-Cookie"][0].split(";")[0].split("=", 1)[1]
    return TOK[(who, app)]
def P(who, m, p, b=None, key=None): return req(m, "/api/p" + p, b, tok(who, "portal"), key or (K() if m == "POST" else None))[:2]
def O(who, m, p, b=None, key=None): return req(m, "/api/o" + p, b, tok(who, "office"), key or (K() if m == "POST" else None))[:2]
def presenter(path, body=None): return req("POST", path, body or {}, cookie="ps_presenter=1")[:2]
def load(key, step="start", **kw):
    s, j = presenter("/api/presenter/scenario/load", dict({"key": key, "step": step}, **kw)); assert s == 200, (key, step, s, j); TOK.clear(); return j
def tasks(pname, typ=None, open_only=True):
    s, q = O("pat", "GET", "/queue?filter=all")
    return [t for t in q["tasks"] if t["patient_name"].startswith(pname) and (typ is None or t["type"] == typ) and (not open_only or t["status"] != "Resolved")]
def task(pname, typ):
    ts = tasks(pname, typ); assert ts, (pname, typ, [(t["type"], t["status"]) for t in tasks(pname, None, False)]); return ts[0]
def act(who, tid, action, **body): return O(who, "POST", f"/tasks/{tid}/act", dict({"action": action}, **body))
def home(who): s, j = P(who, "GET", "/home"); assert s == 200, (who, s, j); return j
def pv(who): return home(who)["pipeline"]
def track(v, key): return next((t for t in v["tracks"] if t["key"] == key or t["key"].startswith(key)), None)
def full(form, **over):
    a = {"confirm": {x["key"]: "ok" for x in form["prefill"]}, "corrections": {}, "matters": ["Walking"], "medicines": "Example: none (fictional)", "allergies": "", "other": "",
         "contact_pref": form["contact_prefs"][0]["value"], "redflags": [], "redflag_none": True, "confirmed": True}
    if form["ask_facility"]: a["facility"] = ""
    a.update(over); return a
def events(cid):
    import sqlite3; d = sqlite3.connect(DB); r = [x[0] for x in d.execute("SELECT action FROM events WHERE case_id=? ORDER BY id", (cid,))]; d.close(); return r
TOMORROW = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400 * 9))
def advance(event, **kw): return presenter("/api/presenter/scenario/advance", dict({"event": event}, **kw))
def periop(v, key): return next(i for i in (v["surgery"] if "surgery" in v else v)["items"] if i["key"] == key)

import sqlite3
def q(who, f="open"):
    s, j = O(who, "GET", "/queue?filter=" + f); assert s == 200, (who, f, s, j); return j
def sq(sql, *a):
    d = sqlite3.connect(DB); d.row_factory = sqlite3.Row; r = [dict(x) for x in d.execute(sql, a)]; d.close(); return r
def pid_of(pname): return sq("SELECT id FROM patients WHERE name LIKE ?", pname + "%")[0]["id"]
def reminders(pid, req=None): return [r for r in sq("SELECT * FROM reminders WHERE patient_id=? ORDER BY id", pid) if req is None or r["requirement"] == req]
def notifs(pid, tmpl): return sq("SELECT * FROM notifications WHERE patient_id=? AND template=? ORDER BY id", pid, tmpl)
def due(pid): return presenter("/api/presenter/reminders/due", {"patient_id": pid})
def ptick(): return presenter("/api/presenter/tick")
def urgent_ids(): return {t["id"] for t in q("nina", "all")["tasks"] if t["group"] == "urgent"}
def detail(who, tid): s, j = O(who, "GET", f"/tasks/{tid}"); assert s == 200, (s, j); return j
def resolve(who, tid, note="Example outcome: phoned the patient (fictional)."):
    t = detail(who, tid)["task"]
    if t["status"] == "Received":
        O(who, "POST", f"/tasks/{tid}/assign", {"owner": "nina", "backup": "yakel", "deadline": TOMORROW})
    st = detail(who, tid)["task"]["status"]
    if st == "Assigned": O(who, "POST", f"/tasks/{tid}/transition", {"to": "In Progress"})
    return O(who, "POST", f"/tasks/{tid}/transition", {"to": "Resolved", "outcome": note})
def strip_vol(x):
    """Drop values that change on every read (view counters / 'now' stamps) so two reads of an unchanged record compare equal."""
    if isinstance(x, dict): return {k: strip_vol(v) for k, v in x.items() if k not in ("generated_at", "now", "viewed_at", "server_time", "answered_at")}
    if isinstance(x, list): return [strip_vol(v) for v in x]
    return x
FILTERS = ["open", "mine", "unowned", "overdue", "waiting", "resolved", "urgent", "decisions", "referrals", "all"]
EMERG = "Example (fictional): I suddenly can't control my bladder and my legs are numb"

start()
presenter("/api/presenter/reset")
s, rules = O("pat", "GET", "/priority-rules")
check("R0 priority rules published, marked EXAMPLE + need Dr. Yakel's approval", s == 200 and "EXAMPLE" in rules["status"] and "DR. YAKEL" in rules["status"].upper() and len(rules["rules"]) == 7, rules.get("status"))
check("R0 clinical criteria are the practice's R1-R9 table (reused, not invented)", [r["id"] for r in rules["clinical_rules"]] == [f"R{i}" for i in range(1, 10)] and "APPROV" in rules["clinical_status"].upper(), rules.get("clinical_rules"))
check("R0 groups are now / waiting / blocked / done", [g["key"] for g in rules["groups"]] == ["now", "waiting", "blocked", "done"], rules["groups"])

# ======================================================== 1. the priority bug: booking never ahead of urgent
print("--- 1. booking can't outrank an unresolved urgent item")
load("clean", "key"); load("missing", "key")
book = task("Avery", "schedule_visit"); j = q("pat")
check("P-pre Avery is ready; the booking task belongs to the front desk and is offered as a routine action", book["owner"] == "pat" and book["primary_action"]["key"] == "book" and book["primary_action"]["allowed"], book.get("primary_action"))
s, m = P("avery", "POST", "/messages", {"category": "medical", "body": EMERG})
check("P1 Avery's emergency-wording message makes an urgent task", s == 200 and m["triage"]["level"] == "emergency", (s, m.get("triage")))
ut = [t for t in q("nina", "all")["pinned"] if t["patient_name"].startswith("Avery")]
check("P1 the urgent task is pinned and routed to the nurse (qualified role)", len(ut) == 1 and ut[0]["owner"] == "nina", ut)
uid = ut[0]["id"]
for who in ("pat", "admin", "nina", "yakel", "frank"):
    j = q(who); ts = j["tasks"]; book_now = next(t for t in ts if t["id"] == book["id"])
    check(f"P2 [{who}] Do next is never the booking while Avery's urgent item is open", j["next_up"] != book["id"], (j["next_up"], j["next_up_kind"]))
    first_routine = next((i for i, t in enumerate(ts) if t["group"] != "urgent"), len(ts)); last_urgent = max([i for i, t in enumerate(ts) if t["group"] == "urgent"] or [-1])
    check(f"P2 [{who}] in the list every urgent task comes before every routine task", last_urgent < first_routine, [(t["id"], t["group"]) for t in ts[:6]])
    check(f"P2 [{who}] the booking card is held (blocked group, booking not allowed, says why)", book_now["group"] == "blocked" and book_now["held_by"] and book_now["held_by"]["id"] == uid and not book_now["primary_action"]["allowed"], (book_now["group"], book_now.get("held_by"), book_now.get("primary_action")))
jn = q("nina"); check("P3 nurse's Do next = the urgent item (kind urgent)", jn["next_up"] == uid and jn["next_up_kind"] == "urgent", (jn["next_up"], jn["next_up_kind"]))
jp = q("pat"); check("P3 front desk gets the urgent notice first (count, patient, owner) and a routine Do next", jp["urgent_notice"] and any(i["id"] == uid and i["owner_name"] for i in jp["urgent_notice"]["items"]) and jp["next_up_kind"] in ("routine", None), jp.get("urgent_notice"))
check("P3 qualified roles get no 'nothing for you to do' notice", q("nina")["urgent_notice"] is None and q("yakel")["urgent_notice"] is None)
s, j = act("pat", book["id"], "book", date=TOMORROW, time="10:30", clinician="Dr. Stefan Yakel, DO")
check("P4 server refuses the booking while the urgent item is open (409 urgent_hold)", s == 409 and j["error"] == "urgent_hold", (s, j))
check("P4 refused booking created no appointment", not sq("SELECT * FROM appointments WHERE patient_id=?", pid_of("Avery")))
s, j = resolve("nina", uid); check("P5 nurse closes the urgent item", s == 200 and j["task"]["status"] == "Resolved", (s, j))
b2 = next(t for t in q("pat")["tasks"] if t["id"] == book["id"])
check("P5 hold lifts: booking allowed again, back in 'needs action now'", not b2.get("held_by") and b2["primary_action"]["allowed"] and b2["group"] == "now", (b2["group"], b2.get("held_by")))
check("P5 the front desk's Do next can now be the booking (routine)", q("pat")["next_up"] is not None)
s, j = act("pat", book["id"], "book", date=TOMORROW, time="10:30", clinician="Dr. Stefan Yakel, DO")
check("P6 booking succeeds after the hold lifts", s == 200, (s, j))

# ======================================================== 2. urgent can't be hidden by filters or permissions
print("--- 2. urgent pinned under every filter, for every role")
load("redflag", "key"); s, m = P("blake", "POST", "/messages", {"category": "medical", "body": EMERG})
U = urgent_ids(); check("U0 two open urgent items (Gray red flag, Blake emergency wording)", len(U) == 2, U)
for who in ("pat", "admin", "nina", "yakel"):
    for f in FILTERS:
        j = q(who, f); pin = {t["id"] for t in j["pinned"]}
        check(f"U1 [{who}/{f}] every open urgent item is pinned", U <= pin, (U, pin))
for who in ("pat", "admin"):
    j = q(who, "mine"); n = j["urgent_notice"]
    check(f"U2 [{who}] non-clinical role sees that urgent items exist and who owns them", n and n["count"] == 2 and all(i["owner_name"] for i in n["items"]) and "nothing for you to do" in n["text"], n)
    check(f"U2 [{who}] queue says it cannot act on urgent", j["can_act_on_urgent"] is False)
check("U2 nurse can act on urgent", q("nina")["can_act_on_urgent"] is True)

# ======================================================== 3. role enforcement on urgent items (server, not just the screen)
print("--- 3. a front-desk/admin user can't clinically clear an urgent concern")
gid = next(t["id"] for t in q("nina")["pinned"] if t["patient_name"].startswith("Gray")); bid = next(t["id"] for t in q("nina")["pinned"] if t["patient_name"].startswith("Blake"))
for who in ("pat", "admin"):
    d = detail(who, gid)
    check(f"E1 [{who}] urgent detail is read-only (no next statuses, no resolve, no reply)", d["allowed"]["urgent_readonly"] and d["allowed"]["next"] == [] and not d["allowed"]["can_resolve"] and not d["allowed"]["can_reply"], d["allowed"])
    check(f"E1 [{who}] every quick action is disallowed, with the owner named", d["actions"] and all(not a["allowed"] for a in d["actions"]) and all("Nothing for you to do" in (a["why_not"] or "") for a in d["actions"]), [(a["key"], a["allowed"]) for a in d["actions"]])
    for a in ("log_contact", "clear_flag"):
        s, j = act(who, gid, a, note="Example: front desk trying to clear (fictional)")
        check(f"E2 [{who}] server refuses '{a}' on the urgent red flag (403)", s == 403 and j["error"] == "clinical_role_required", (s, j))
    s, j = O(who, "POST", f"/tasks/{bid}/transition", {"to": "Resolved", "outcome": "Example: closing it (fictional)"}); check(f"E3 [{who}] server refuses to resolve/transition the urgent message (403)", s == 403, (s, j))
    s, j = O(who, "POST", f"/tasks/{bid}/reply", {"body": "Example reply (fictional)"}); check(f"E3 [{who}] server refuses a patient reply on the urgent message (403)", s == 403, (s, j))
    s, j = O(who, "POST", f"/tasks/{bid}/assign", {"owner": who, "backup": "nina", "deadline": TOMORROW}); check(f"E3 [{who}] server refuses reassigning the urgent item (403)", s == 403, (s, j))
    s, j = O(who, "POST", f"/tasks/{bid}/note", {"body": "Example internal note: patient's partner phoned (fictional)"}); check(f"E4 [{who}] can still add an internal note (information only)", s == 200, (s, j))
s, j = O("nina", "POST", f"/tasks/{bid}/assign", {"owner": "pat", "backup": "nina", "deadline": TOMORROW}); check("E5 even the nurse can't hand an urgent item to the front desk (422)", s == 422 and j["error"] == "clinical_owner_required", (s, j))
s, j = act("nina", gid, "log_contact", note="Example: phoned Gray, advised per protocol (fictional)"); check("E6 nurse can act on the urgent item", s == 200, (s, j))
check("E6 urgent item still open + pinned after a contact log (only a clear closes it)", gid in {t["id"] for t in q("pat")["pinned"]})
s, j = act("nina", gid, "clear_flag", note="Example clinical outcome (fictional)"); check("E7 nurse clears the red-flag hold", s == 200, (s, j))
check("E7 cleared item leaves the pinned list for everyone", gid not in {t["id"] for t in q("pat")["pinned"]} and gid not in {t["id"] for t in q("admin")["pinned"]})

# ======================================================== 4. groups + card fields
print("--- 4. groups and task cards")
j = q("pat", "all"); G = {"urgent", "now", "waiting", "blocked", "done"}
check("G1 every task carries one server-computed group", all(t["group"] in G for t in j["tasks"]), {t["group"] for t in j["tasks"]})
check("G2 resolved -> done; Waiting (not overdue, not held) -> waiting", all(t["group"] == "done" for t in j["tasks"] if t["status"] == "Resolved") and all(t["group"] in ("waiting", "blocked", "urgent") for t in j["tasks"] if t["status"] == "Waiting"))
check("G3 overdue/stuck open routine tasks -> blocked", all(t["group"] in ("blocked", "urgent") for t in j["tasks"] if t["status"] != "Resolved" and (t["overdue"] or t["followup_due"])))
check("G4 recent_done = at most 5 completed tasks", len(q("pat")["recent_done"]) <= 5 and all(t["status"] == "Resolved" for t in q("pat")["recent_done"]) and q("pat")["recent_done"])
op = [t for t in j["tasks"] if t["status"] != "Resolved"]
check("C1 every open card has patient + what needs attention", all(t["patient_name"] and (t["blocked_step"] or t["category"]) for t in op))
check("C2 owner is a name or null (shown as 'Unassigned')", all(t["owner_name"] or not t["owner"] for t in op))
check("C3 due date or time waiting is supplied when known", all((t["deadline"] or t["waiting_since"] or t["status"] == "Received") for t in op), [(t["id"], t["status"]) for t in op if not (t["deadline"] or t["waiting_since"])])
check("C4 each routine card has one next action (a quick action, an explicit hold, or a written next step)", all((t.get("primary_action") or t.get("held_by") or t["next_action"]) for t in op if t["group"] != "urgent"), [(t["id"], t["type"], t["source"], t["status"]) for t in op if t["group"] != "urgent" and not (t.get("primary_action") or t.get("held_by") or (t["source"] == "patient" and t["next_action"]))])

# ======================================================== 5. no duplicate tasks or reminders; reminders stop
print("--- 5. dedupe and reminder stop rules")
load("nointake", "intake"); drew = pid_of("Drew"); dt = task("Drew", "intake_followup")
check("D1 intake invite starts exactly one reminder record (patient + requirement key)", len(reminders(drew, "intake")) == 1 and reminders(drew, "intake")[0]["dedupe_key"] == f"p{drew}:intake", reminders(drew))
d0 = len(notifs(drew, "intake_reminder")); ptick(); ptick(); ptick()
check("D2 repeated worker ticks before the gap send nothing", len(notifs(drew, "intake_reminder")) == d0, (d0, len(notifs(drew, "intake_reminder"))))
due(drew); ptick(); ptick()
n1 = notifs(drew, "intake_reminder"); check("D3 one automatic reminder when due; extra ticks don't double-send", len(n1) == d0 + 1 and "reminder 1 of 3" in n1[-1]["body"], [x["body"] for x in n1])
s, j = act("pat", dt["id"], "send_reminder"); n2 = notifs(drew, "intake_reminder")
check("D4 staff reminder shares the counter (reminder 2 of 3, not a second 'reminder 1')", s == 200 and "reminder 2 of 3" in n2[-1]["body"], [x["body"] for x in n2])
check("D4 still one reminder record", len(reminders(drew, "intake")) == 1 and reminders(drew, "intake")[0]["sent"] == 2)
k = K(); s1, j1 = O("pat", "POST", f"/tasks/{dt['id']}/act", {"action": "send_reminder"}, key=k); s2, j2 = O("pat", "POST", f"/tasks/{dt['id']}/act", {"action": "send_reminder"}, key=k)
n3 = notifs(drew, "intake_reminder"); check("D5 double-click (same idempotency key) sends one reminder", s1 == 200 and s2 == 200 and len(n3) == len(n2) + 1, (s1, s2, len(n2), len(n3)))
r = reminders(drew, "intake")[0]; check("D6 limit reached -> reminders stop by themselves", r["status"] == "stopped" and r["stop_reason"] == "limit_reached", r)
due(drew); ptick(); check("D6 no reminder after the limit", len(notifs(drew, "intake_reminder")) == len(n3))
acts = [a["key"] for a in detail("pat", dt["id"])["actions"]]; check("D6 'send reminder' is no longer offered; phoning is", "send_reminder" not in acts and "log_call" in acts, acts)
s, j = act("pat", dt["id"], "send_reminder"); check("D6 server refuses a 4th reminder", s >= 400, (s, j))
# opt-out
load("nointake", "intake"); drew = pid_of("Drew"); dt = task("Drew", "intake_followup"); base = len(notifs(drew, "intake_reminder"))
s, j = P("drew", "PUT", "/reminders", {"opt_out": True}); r = reminders(drew, "intake")[0]
check("D7 patient opts out -> reminder stops (opted_out)", s == 200 and j["opted_out"] and r["status"] == "stopped" and r["stop_reason"] == "opted_out", (s, r))
due(drew); ptick(); check("D7 no reminder after opt-out", len(notifs(drew, "intake_reminder")) == base)
d = detail("pat", dt["id"]); acts = [a["key"] for a in d["actions"]]
check("D7 staff see the opt-out: no 'send reminder', phone is primary", "send_reminder" not in acts and next(a for a in d["actions"] if a["key"] == "log_call")["primary"] and "turned reminder texts off" in d["task"]["next_action"], (acts, d["task"]["next_action"]))
check("D7 staff task card shows the opt-out", next(t for t in q("pat", "all")["tasks"] if t["id"] == dt["id"])["reminders_opted_out"] is True)
s, j = P("drew", "PUT", "/reminders", {"opt_out": False}); check("D8 opting back in restarts the still-open reminder", s == 200 and reminders(drew, "intake")[0]["status"] == "active", reminders(drew))
s, j = P("drew", "PUT", "/reminders", {"opt_out": "yes"}); check("D8 bad opt-out value rejected (422)", s == 422, (s, j))
s2, j2 = req("PUT", "/api/p/reminders", {"opt_out": True}, tok("pat", "office"))[:2]
check("D8 office session can't change a patient's opt-out", s2 in (401, 403), (s2, j2))
# staff take-over
s, j = act("pat", dt["id"], "stop_reminders", note="Example: I'll phone Drew this afternoon (fictional)"); r = reminders(drew, "intake")[0]
check("D9 staff take over -> reminders stop (staff_took_over), task in progress with a phone next step", s == 200 and r["status"] == "stopped" and r["stop_reason"] == "staff_took_over" and detail("pat", dt["id"])["task"]["status"] == "In Progress", (s, r))
due(drew); ptick(); check("D9 no reminder after staff take-over", len(notifs(drew, "intake_reminder")) == base)
# fulfilled
load("clean", "intake"); av = pid_of("Avery"); s, f = P("avery", "GET", "/intake")
check("D10 Avery has an active intake reminder before finishing", reminders(av, "intake") and reminders(av, "intake")[0]["status"] == "active", reminders(av))
s, j = P("avery", "POST", "/intake", {"answers": full(f)}); r = reminders(av, "intake")[0]
check("D10 finishing the intake stops the reminder (fulfilled)", s == 200 and r["status"] == "stopped" and r["stop_reason"] == "fulfilled", (s, r))
b0 = len(notifs(av, "intake_reminder")); due(av); ptick(); check("D10 no reminder after it's done", len(notifs(av, "intake_reminder")) == b0)
bk = task("Avery", "schedule_visit"); s, j = act("pat", bk["id"], "book", date=TOMORROW, time="10:30", clinician="Dr. Stefan Yakel, DO")
rc = reminders(av, "confirm_appointment"); check("D11 booking starts ONE confirm-the-visit reminder", s == 200 and len(rc) == 1 and rc[0]["status"] == "active", rc)
due(av); ptick(); ptick(); check("D11 one confirm reminder sent when due", len(notifs(av, "confirm_appointment_reminder")) == 1, notifs(av, "confirm_appointment_reminder"))
ap = sq("SELECT * FROM appointments WHERE patient_id=?", av)[0]; s, j = P("avery", "POST", f"/appointments/{ap['id']}/confirm", {})
r = reminders(av, "confirm_appointment")[0]; check("D11 patient confirms -> reminder stops (fulfilled)", s == 200 and r["status"] == "stopped" and r["stop_reason"] == "fulfilled", (s, r))
due(av); ptick(); check("D11 no confirm reminder after confirming", len(notifs(av, "confirm_appointment_reminder")) == 1)
s, j = P("avery", "GET", "/reminders"); check("D12 patient sees the same reminder records (simulated, with stop reasons)", s == 200 and {x["requirement"] for x in j["reminders"]} == {"intake", "confirm_appointment"} and all(x["simulated"] and x["stop_text"] for x in j["reminders"]), j)
load("caregiver", "key"); s, j = P("frankie", "GET", "/reminders"); s2, j2 = P("frankie", "PUT", "/reminders", {"opt_out": True})
check("D13 helper can see reminder status but can't opt the patient out (403)", s == 200 and j["can_change"] is False and s2 == 403, (s, s2))
# task dedupe
s1, c1 = P("avery", "POST", "/callback", {"note": "Example: afternoons please (fictional)"}); s2, c2 = P("avery", "POST", "/callback", {"note": "Example: afternoons please (fictional)"})
check("D14 a second call-back request doesn't make a second task", s1 == 200 and s2 == 200 and c1["created"] and not c2["created"] and c1["task"]["id"] == c2["task"]["id"], (c1.get("created"), c2.get("created")))
dup = sq("SELECT dedupe_key, COUNT(*) n FROM tasks WHERE status!='Resolved' AND dedupe_key IS NOT NULL GROUP BY dedupe_key HAVING n>1")
check("D15 no open duplicate follow-up tasks anywhere (dedupe key per patient + requirement)", not dup, dup)
dupr = sq("SELECT dedupe_key, COUNT(*) n FROM reminders GROUP BY dedupe_key HAVING n>1"); check("D15 no duplicate reminder records anywhere", not dupr, dupr)
check("D15 the database enforces both (unique indexes)", sq("SELECT name FROM sqlite_master WHERE name='tasks_open_dedupe'") and "UNIQUE" in sq("SELECT sql FROM sqlite_master WHERE name='reminders'")[0]["sql"].upper())

# ======================================================== 6. one record: staff and patient views; other patients untouched
print("--- 6. same record for patient + staff; other patients unchanged")
presenter("/api/presenter/reset"); TOK.clear()
for k in ("clean", "missing", "auth"): load(k, "key")
others_before = {w: strip_vol(home(w)["pipeline"]) for w in ("avery", "cameron")}
rt = task("Blake", "records_request"); before = home("blake")["pipeline"]; trb = track(before, "records")
d = detail("pat", rt["id"]); items = next(a for a in d["actions"] if a["key"] == "mark_received")["fields"][0]["options"]
s, j = act("pat", rt["id"], "mark_received", items=[items[0]["value"]]); after = home("blake")["pipeline"]
check("S1 staff marks one Blake record received", s == 200, (s, j))
dv = detail("pat", rt["id"])["case_view"]
pt = {x["key"]: (x["state"] if "state" in x else x.get("done"), x["patient_text"]) for x in after["tracks"]}; st_ = {x["key"]: (x["state"] if "state" in x else x.get("done"), x["patient_text"]) for x in dv["tracks"]}
check("S2 Blake's portal changed after the staff action", strip_vol(before) != strip_vol(after))
check("S3 patient view and staff view show the SAME status + patient wording for every step (one record)", pt == st_, {k: (pt.get(k), st_.get(k)) for k in set(pt) | set(st_) if pt.get(k) != st_.get(k)})
check("S4 Avery's and Cameron's portals are unchanged", all(strip_vol(home(w)["pipeline"]) == others_before[w] for w in others_before), "changed")
s, m = P("blake", "POST", "/messages", {"category": "billing", "body": "Example billing question (fictional)"}); mt = m["task"]["id"]
O("pat", "POST", f"/tasks/{mt}/assign", {"owner": "pat", "backup": "admin", "deadline": TOMORROW}); O("pat", "POST", f"/tasks/{mt}/reply", {"body": "Example reply from the front desk (fictional)."})
s, j = P("blake", "GET", "/threads"); stv = {t["id"]: t["status"] for t in q("pat", "all")["tasks"]}
check("S5 every request Blake sees has the same status as the staff record", s == 200 and j["threads"] and all(stv.get(t["id"]) == t["status"] for t in j["threads"]), [(t["id"], t["status"], stv.get(t["id"])) for t in j.get("threads", [])])
s, j = resolve("pat", mt, "Example: answered the billing question (fictional).")
s, th = P("blake", "GET", f"/threads/{mt}")
check("S6 completing Blake's request shows as Closed in Blake's portal (same row)", s == 200 and th["thread"]["status"] == "Resolved" and th["thread"]["status_text"] == "Closed" and any(x["body"].startswith("Example reply from the front desk") for x in th["messages"]), (s, th.get("thread")))
s, oth = P("avery", "GET", f"/threads/{mt}"); check("S7 another patient can't see Blake's request (404/403)", s in (403, 404), s)
check("S8 Avery's and Cameron's portals still unchanged", all(strip_vol(home(w)["pipeline"]) == others_before[w] for w in others_before))

# ======================================================== 7. visit-ready summary draft
print("--- 7. visit-ready summary")
load("caregiver", "key"); ct = task("Emery", None); sm = detail("yakel", ct["id"])["summary"]
check("V1 label is exactly 'Draft — clinician review required'", sm and sm["label"] == "Draft \u2014 clinician review required", sm and sm.get("label"))
check("V2 patient statements are separate from extracted facts", isinstance(sm["statements"], list) and isinstance(sm["extracted"], list) and sm["statements"] and sm["extracted"])
check("V3 every extracted fact names its source", all(x["source"] and x["source"]["label"] for x in sm["extracted"]), [x["topic"] for x in sm["extracted"] if not x["source"].get("label")])
check("V4 every statement has a status (confirmed / unconfirmed) and a source", all(x["status"] in ("confirmed", "unconfirmed") and x["source"]["label"] for x in sm["statements"]))
check("V5 helper-entered answers are marked NOT confirmed by the patient", any(x["status"] == "unconfirmed" and "NOT confirmed" in x["status_text"] for x in sm["statements"]), [(x["topic"], x["status"]) for x in sm["statements"]])
sub = sq("SELECT answers FROM intake WHERE case_id=(SELECT case_id FROM tasks WHERE id=?)", ct["id"])
if sub:
    a = json.loads(sub[0]["answers"]); vs = {x["topic"]: x["text"] for x in sm["statements"]}
    check("V6 statements are verbatim (same text as submitted)", (not a.get("other") or vs.get("In their own words") == a["other"]) and (not a.get("medicines") or vs.get("Medicines they added") == a["medicines"]), (a.get("other"), vs))
check("V7 missing/conflicting items are flagged", isinstance(sm["flags"], list) and all(f["kind"] in ("missing", "conflict") for f in sm["flags"]))
bad = [w for w in ("diagnos", "likely", "recommend", "suggests", "consistent with", "rule out", "indicat") if w in json.dumps(sm).lower()]
check("V8 no clinical conclusions in the summary text", not bad, bad)
load("redflag", "key"); gt = next(t for t in q("nina")["pinned"] if t["patient_name"].startswith("Gray")); sg = detail("nina", gt["id"])["summary"]
check("V9 red-flag answer appears as the patient's own statement with its source", sg and any(x["topic"] == "Safety question" for x in sg["statements"]), sg and sg["statements"])
check("V9 missing intake is flagged", sg and any(f["kind"] == "missing" for f in sg["flags"]))

# ======================================================== 8. patient wording + staff detail
print("--- 8. wording and staff detail on the patient side")
presenter("/api/presenter/reset"); TOK.clear()
for k in ("clean", "missing", "auth", "nointake", "caregiver", "notfit", "redflag"): load(k, "key")
PATS = ("avery", "blake", "cameron", "drew", "emery", "finley", "gray")
promise = re.compile(r"(we|team member|front desk|nurse|someone)[^.]{0,30}\b(will|\u2019ll|'ll) (call|phone|ring) you", re.I)
for w in PATS:
    hh = json.dumps(home(w)); m_ = promise.search(hh)
    check(f"W1 [{w}] no 'we'll call you' promise without a configured expectation", not m_, m_ and hh[max(0, m_.start() - 80):m_.end() + 40])
    check(f"W2 [{w}] no staff name or fax note in the patient's 'last verified' source", not re.search(r'"last_verified_source": "[^"]*(Pat|Nina|Front desk \u00b7|fax)', hh), re.findall(r'"last_verified_source": "[^"]*"', hh)[:3])
s, j = O("admin", "PUT", "/settings", {"patient_call_expectation": "Example wording set by the office (fictional): our front desk will call you."})
check("W3 admin can configure a call expectation", s == 200 and j["patient_call_expectation"].startswith("Example"), (s, j))
check("W3 ...and only then does it appear to the patient", "Example wording set by the office" in json.dumps(home("avery")), "")
s, j = O("pat", "PUT", "/settings", {"patient_call_expectation": "x"}); check("W3 front desk can't change it (403)", s == 403, s)
O("admin", "PUT", "/settings", {"patient_call_expectation": ""}); check("W4 cleared again -> gone", "Example wording set by the office" not in json.dumps(home("avery")))

# ======================================================== cross-cutting
s, j = req("GET", "/api/health")[:2]; check("server healthy at the end", s == 200, j)
srv_log = open("/tmp/apioff_srv.log").read(); tb = srv_log.count("Traceback") - srv_log.count("BrokenPipeError")   # the start-up health probe hangs up without reading: harmless BrokenPipe
check("no server errors logged", "server error" not in srv_log and tb == 0, srv_log[-400:])
stop()
ok = sum(1 for r in RES if r[1]); print(f"\nDONE api_office_test: {ok}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_office_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(RES) else 1)
