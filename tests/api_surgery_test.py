#!/usr/bin/env python3
"""preview19 Prompt B API tests: before / after surgery.  Verified procedure facts only ('Not added yet' otherwise), patient vs team tasks,
approved instructions or the exact missing text, no readiness inference, verbatim check-in notes, example escalation rule table (levels only go up),
server receipts + history, no call-back promise unless configured.  Own server on 127.0.0.1:8785, temp DB, --no-worker.  Fictional data only."""
import http.client, json, os, re, signal, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8785")); DB = os.path.join(tempfile.mkdtemp(), "tsurg.db")
RES = []; proc = None
def start(env=None):
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=open("/tmp/apisurg_srv.log", "a"), stderr=subprocess.STDOUT,
                            env=dict(os.environ, **(env or {})))
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
         "contact_pref": "text", "redflags": [], "redflag_none": True, "confirmed": True}
    a.update(over); return a
def summary_raw(pname, office="yakel"):
    t = tasks(pname)[0]; s, d = O(office, "GET", f"/tasks/{t['id']}"); assert s == 200, (s, d); return json.dumps(d.get("summary"), ensure_ascii=False)

import sqlite3
open("/tmp/apisurg_srv.log", "w").close()
def db1(sql, a=()):
    d = sqlite3.connect(DB); r = d.execute(sql, a).fetchall(); d.close(); return r
def dbx(sql, a=()):
    d = sqlite3.connect(DB); d.execute(sql, a); d.commit(); d.close()
def sv(who="harper"): return home(who)["pipeline"]["surgery"]
def due(): return sv()["checkin_due"]
def CI(answer, note=None, key=None, **extra):
    k = due(); b = dict({"answer": answer}, **extra)
    if note is not None: b["note"] = note
    return P("harper", "POST", f"/checkin/{k['id']}", b, key)
PROMISE = re.compile(r"(will (phone|call) you|nurse will|call you back|within \d|same (business )?day|we.ll call)", re.I)
start()
print("--- A. call-back promise: empty by default, admin-only, shown verbatim only when configured")
s, j = O("admin", "GET", "/settings"); check("A1 postop_callback_promise exists and is EMPTY by default", s == 200 and j["postop_callback_promise"] == "", j)
s, j = req("PUT", "/api/o/settings", {"postop_callback_promise": "x"}, tok("pat", "office"))[:2]; check("A2 front desk cannot set it (403)", s == 403, (s, j))
s, j = req("PUT", "/api/o/settings", {"postop_callback_promise": "x"}, tok("yakel", "office"))[:2]; check("A3 clinician cannot set it either (admin only)", s == 403, (s, j))
srcs = open(os.path.join(ROOT, "server.py")).read() + open(os.path.join(ROOT, "portal.js")).read()
check("A4 the old promises are gone from the code ('A nurse will phone you', 'goes to a nurse, who will phone you', 'please call me', 'the office will call you')",
      not re.search(r"A nurse will phone you|who will phone you|please call me'|Missed \\\\u2014 the office will call", srcs), "")
load("surgery", "postop"); h = home("harper")
check("A5 post-op next action makes no call-back / response-time promise", not PROMISE.search(h["next_action"]["why"]), h["next_action"]["why"])
check("A6 portal payload carries callback_promise = null when not configured", sv()["callback_promise"] is None)

print("--- B. before surgery: verified facts, who-does-what, no readiness inference")
load("surgery", "start"); v = sv(); pr = v["procedure"]
check("B1 procedure label is labelled example; date present; NOT verified yet at the start (date item open)", pr["label"] == "Spine surgery (example)" and pr["date"] and pr["date_verified"] is False and pr["verified_by"] is None, pr)
check("B2 surgeon / location / arrival time are null (shown as 'Not added yet', never guessed)", pr["surgeon"] is None and pr["location"] is None and pr["arrival_time"] is None, pr)
load("surgery", "key"); v = sv(); pr = v["procedure"]
check("B3 after the front desk confirms the date: verified_by + verified_at come from the checklist record", pr["date_verified"] and pr["verified_by"] and pr["verified_at"], pr)
check("B4 checklist split: patient task = written-instructions acknowledgement; team tasks = date, consent, clearance, labs, insurance", v["patient_tasks"] == ["instructions"] and set(v["team_tasks"]) == {"date", "consent", "clearance", "labs", "insurance"}, (v["patient_tasks"], v["team_tasks"]))
check("B5 no readiness / clearance field in the patient payload ('ready' and 'checklist_complete' absent)", "ready" not in v and "checklist_complete" not in v, sorted(v))
blob = json.dumps(home("harper"), ensure_ascii=False).lower()
check("B6 nothing in the patient Home payload says 'cleared for surgery' or 'ready for surgery'", "cleared for surgery" not in blob and "ready for surgery" not in blob and "you are cleared" not in blob, "")
check("B7 approved pre-op instructions: none -> status 'missing' (portal shows the exact sentence)", v["approved_instructions"]["status"] == "missing" and v["approved_instructions"]["slot"] == "preop", v["approved_instructions"])
load("surgery", "postop"); v = sv()
check("B8 even with every pre-op item done, the patient payload still has no readiness/clearance flag", all(i["done"] for i in v["items"]) and "ready" not in v and "checklist_complete" not in v, [(i["key"], i["done"]) for i in v["items"]])
load("surgery", "key")
dbx("INSERT INTO approved_content(case_id,patient_id,slot,title,body,version,status,approved_by,approved_at,review_by,example,created_at) VALUES(18,18,'preop','Before your surgery (EXAMPLE \u2014 fictional approved content)','EXAMPLE \u2014 fictional placeholder, not real guidance.',1,'approved','Example approval record (fictional) \u2014 not a real clinician','2026-10-01T16:00:00Z','2027-01-01T00:00:00Z',1,'2026-10-01T16:00:00Z')")
ai = sv()["approved_instructions"]
check("B9 with an approved (example) pre-op record: status verified, original linked, body verbatim", ai["status"] == "verified" and ai["records"][0]["href"].startswith("#/content/") and ai["records"][0]["body"].startswith("EXAMPLE"), ai)
dbx("INSERT INTO approved_content(case_id,patient_id,slot,title,body,version,status,approved_by,approved_at,review_by,example,created_at) VALUES(18,18,'preop','Before your surgery (EXAMPLE v2)','EXAMPLE \u2014 a different fictional placeholder.',2,'approved','Example approval record (fictional) \u2014 not a real clinician','2026-10-02T16:00:00Z','2027-01-01T00:00:00Z',1,'2026-10-02T16:00:00Z')")
check("B10 two approved versions that differ -> 'conflict' (portal warns, never picks one)", sv()["approved_instructions"]["status"] == "conflict")
load("surgery", "key"); check("B11 reloading the scenario clears the extra records again (back to 'missing')", sv()["approved_instructions"]["status"] == "missing")

print("--- C. escalation rule table (EXAMPLE, needs Dr. Yakel's approval): levels only go up")
s, er = O("pat", "GET", "/escalation-rules")
check("C1 GET /escalation-rules: marked NEEDS DR. YAKEL'S APPROVAL, approved_by null, 4 levels, >= 9 rules", s == 200 and "NEEDS DR. YAKEL" in er["status"] and er["approved_by"] is None and len(er["levels"]) == 4 and len(er["rules"]) >= 9, er.get("status"))
s, j = req("GET", "/api/o/escalation-rules", None, tok("harper", "portal"))[:2]; check("C2 patients cannot read the office rule table", s in (401, 403), s)
sys.path.insert(0, ROOT); import server as SV
CASES = [("ok", "", "record_only"), ("ok", "Sleeping better (example)", "record_only"), ("question", "Can I shower yet? (example)", "staff_review"),
         ("concern", "I feel fine actually, nothing wrong", "urgent_review"), ("ok", "I have a fever tonight", "urgent_review"), ("ok", "the incision is red and leaking", "urgent_review"),
         ("question", "some bleeding on the dressing", "urgent_review"), ("ok", "new numbness in my left foot", "urgent_review"), ("question", "my calf is swollen", "urgent_review"),
         ("ok", "I can't feel my legs", "emergency"), ("concern", "lost control of my bladder", "emergency")]
bad = [(a, n, SV.escalate(a, n)) for a, n, want in CASES if SV.escalate(a, n)[0] != want]
check(f"C3 {len(CASES)} example inputs land on the expected level (worry words escalate even with 'I'm doing okay')", not bad, bad)
check("C4 'concern' is never lowered by reassuring words ('I feel fine actually')", SV.escalate("concern", "I feel fine actually, nothing wrong")[0] == "urgent_review")

print("--- D. the four fictional examples, receipts, verbatim notes")
load("surgery", "postop"); n0 = len(tasks("Harper", "postop_concern"))
s, r = CI("ok", "Sleeping better and walking to the mailbox (example).")
rc = r["receipt"]
check("D1 ORDINARY check-in: saved, NO staff task, receipt from the server (ref CI-n, time, level record_only)", s == 200 and not r["task_created"] and rc["ref"].startswith("CI-") and rc["sent_at"] and rc["level"] == "record_only" and rc["task_ref"] is None, r)
check("D2 ... the message is honest: 'saved in your record', 'did not create a task', no promise", "did not create a task" in r["message"] and not PROMISE.search(r["message"]), r["message"])
check("D3 ... no staff task was created", len(tasks("Harper", "postop_concern")) == n0)
load("surgery", "postop"); note = "  Can I shower yet?\nThe leaflet says \"wait\" \u2014 I\u2019m not sure (example).  "
key = K(); s, r = CI("question", note, key=key); rc = r["receipt"]
check("D4 REQUEST FOR HELP: staff_review, task created, receipt shows the task ref and team", s == 200 and r["task_created"] and rc["level"] == "staff_review" and rc["task_ref"] and rc["routed_to"] == "Nurse", r)
check("D5 the patient's words are kept VERBATIM (spaces, newline, quotes) in the receipt and the stored check-in", rc["note"] == note and db1("SELECT note FROM checkins WHERE id=?", (due_id := int(rc["ref"][3:]),))[0][0] == note, (rc["note"], note))
t = [x for x in tasks("Harper", "postop_concern")][0]; s, td = O("nina", "GET", f"/tasks/{t['id']}")
rs = db1("SELECT reason FROM tasks WHERE id=?", (t["id"],))[0][0]
check("D6 ... and verbatim in the office task (the nurse reads exactly what was written)", ("\u201c" + note + "\u201d") in rs, rs[:200])
check("D7 'reached the care team' wording only because a task exists; normal priority for a question", "reached the care team" in r["message"] and t["priority"] == "normal", (r["message"], t["priority"]))
s2, r2 = P("harper", "POST", f"/checkin/{due_id}", {"answer": "question", "note": note}, key)
check("D8 retry with the SAME key -> same receipt replayed, still one task", s2 == 200 and r2["receipt"]["ref"] == rc["ref"] and len(tasks("Harper", "postop_concern")) == 1, (s2, r2.get("receipt")))
s3, r3 = P("harper", "POST", f"/checkin/{due_id}", {"answer": "question", "note": note}, K())
check("D9 a NEW key after it was answered -> 409 not_open (no second submission)", s3 == 409, (s3, r3))
load("surgery", "postop")
s, r = CI("concern", "The wound area looks different today and I am worried (example).", level="record_only", priority="normal")
rc = r["receipt"]; t = tasks("Harper", "postop_concern")
check("D10 CONCERN requiring staff review: urgent_review + URGENT nurse task; client-sent level/priority ignored", rc["level"] == "urgent_review" and t and t[0]["priority"] == "urgent", (rc, t[:1]))
check("D11 ... receipt says it reached the care team with the task ref; still no call-back promise", "reached the care team" in r["message"] and rc["task_ref"] == f"#{t[0]['id']}" and not PROMISE.search(r["message"]), r["message"])
load("surgery", "postop"); s, r = CI("ok", "Feeling okay but I have a fever and chills (example).")
check("D12 'I'm doing okay' + fever words -> still escalated to urgent_review (the choice cannot downgrade)", r["receipt"]["level"] == "urgent_review" and r["task_created"], r["receipt"])
load("surgery", "postop"); s, r = CI("question", "I suddenly can't feel my legs (example)")
check("D13 emergency wording -> level emergency, 911 guidance in the response, urgent task", r["emergency"] and "911" in r["emergency_guidance"] and r["receipt"]["level"] == "emergency" and tasks("Harper", "postop_concern")[0]["priority"] == "urgent", r)

print("--- E. failed submissions leave nothing half-done")
load("surgery", "postop"); k = due()
s, j = req("POST", f"/api/p/checkin/{k['id']}", {"answer": "ok"}, tok("harper", "portal"))[:2]; check("E1 no Idempotency-Key -> refused", s in (400, 428), (s, j))
s, j = CI("maybe", "x"); check("E2 invalid answer -> 422", s == 422, (s, j))
s, j = CI("question", "   "); check("E3 question without words -> 422 note_required", s == 422 and j["error"] == "note_required", j)
s, j = CI("question", "x" * 1001); check("E4 too long -> 422", s == 422, j)
check("E5 after the failures the check-in is still open, with no receipt and no task", due() and due()["id"] == k["id"] and not db1("SELECT 1 FROM checkin_receipts WHERE checkin_id=?", (k["id"],)) and not tasks("Harper", "postop_concern"), "")
load("clean", "key"); s, j = P("avery", "POST", f"/checkin/{k['id']}", {"answer": "ok"}); check("E6 another patient cannot answer Harper's check-in (404)", s == 404, (s, j))

print("--- F. history + configured promise")
load("surgery", "postop_concern"); v = sv(); hist = [x for x in v["checkins"] if x["status"] == "answered"]
check("F1 history: answered check-in with the patient's own words and its server receipt (ref, level, task ref)", hist and hist[0]["note"] and hist[0]["receipt"]["ref"] and hist[0]["receipt"]["task_ref"], hist)
s, j = O("admin", "PUT", "/settings", {"postop_callback_promise": "EXAMPLE setting (fictional): a nurse aims to call the same business day."})
check("F2 admin can set the wording; the reply target is untouched", s == 200 and j["postop_callback_promise"].startswith("EXAMPLE") and j["patient_reply_target"] == "", j)
load("surgery", "postop"); h = home("harper")
check("F3 configured -> shown word for word in the check-in prompt and the portal payload", "EXAMPLE setting (fictional)" in h["next_action"]["why"] and sv()["callback_promise"].startswith("EXAMPLE"), h["next_action"]["why"])
s, r = CI("question", "When can I drive? (example)")
check("F4 ... and after a check-in that created a task", "EXAMPLE setting (fictional)" in r["message"] and r["callback_promise"], r["message"])
load("surgery", "postop"); s, r = CI("ok", "")
check("F5 ... but NOT after a check-in with no task (nobody was asked to call)", "EXAMPLE setting" not in r["message"], r["message"])
O("admin", "PUT", "/settings", {"postop_callback_promise": ""}); s, j = O("admin", "GET", "/settings"); check("F6 clearing it works", j["postop_callback_promise"] == "", j)

s, j = req("GET", "/api/health")[:2]; check("server healthy at the end", s == 200, j)
srv_log = open("/tmp/apisurg_srv.log").read(); check("no server errors logged", "server error" not in srv_log and srv_log.count("Traceback") == srv_log.count("BrokenPipeError"), srv_log[-600:])
stop()
ok = sum(1 for r in RES if r[1]); print(f"\nDONE api_surgery_test: {ok}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_surgery_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(RES) else 1)
