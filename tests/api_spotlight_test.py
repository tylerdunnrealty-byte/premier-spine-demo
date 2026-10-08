#!/usr/bin/env python3
"""Pass 2b API tests: the four office-streamlining SPOTLIGHTS (fewer calls, automatic chasing, pre-filled intake + visit summary, surgery prep + post-op check-ins)
Each scenario is reset to its START with the presenter shortcut, then every step is done with the same endpoints the screens use,
signed in as the right fictional person.  Starts its own server on 127.0.0.1:8771 with a temp DB and --no-worker."""
import http.client, json, os, re, signal, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8777")); DB = os.path.join(tempfile.mkdtemp(), "t3.db")
RES = []; proc = None
def start():
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=open("/tmp/api3_srv.log", "w"), stderr=subprocess.STDOUT)
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

start()
presenter("/api/presenter/reset")

# ======================================================== spotlight 1: fewer phone calls
print("--- spotlight 1: fewer phone calls (status page + calls-avoided example counts)")
load("missing", "key"); h = home("blake"); v = h["pipeline"]
rec = [t for t in v["tracks"] if t["key"].startswith("records:") and not t["done"]]
check("SP1 every open item says WHAT we wait on and WHO has it", rec and all(t["waiting_on"] for t in rec) and all(t["owner_team"] for t in rec if t["task_id"]), [(t["label"], t["waiting_on"], t["owner_team"]) for t in rec])
check("SP1 every waiting item has a plain 'Next step' line", all((t.get("next_step") or "").startswith("Next step:") for t in v["tracks"] if not t["done"] and t["waiting_on"]), [t.get("next_step") for t in v["tracks"]])
check("SP1 outside-party next step promises an automatic follow-up (simulated), not a date guess", any("automatically (simulated)" in (t.get("next_step") or "") for t in rec), [t.get("next_step") for t in rec])
s, ca = O("pat", "GET", "/calls-avoided")
check("SP1 calls-avoided endpoint answers for office staff", s == 200 and len(ca["lines"]) >= 5, (s, ca))
check("SP1 calls-avoided is labelled EXAMPLE COUNTS ONLY and 'not a measured reduction'", "EXAMPLE COUNTS ONLY" in ca["label"] and "not a measured reduction" in ca["note"], ca)
check("SP1 calls-avoided makes no time or cost claim", not re.search(r"\$|minutes|hours saved|% ", json.dumps(ca)), ca)
n0 = dict((l[0][:30], l[1]) for l in ca["lines"]); home("blake")
s, ca2 = O("pat", "GET", "/calls-avoided"); n1 = dict((l[0][:30], l[1]) for l in ca2["lines"])
k = next(k for k in n0 if k.startswith("Times patients checked"))
check("SP1 a patient opening Home while items are pending is counted once (deduped, not per refresh)", n1[k] == n0[k] and n0[k] >= 1, (n0[k], n1[k]))
check("SP1 patients cannot see the calls-avoided counts (office only)", req("GET", "/api/o/calls-avoided", token=tok("blake", "portal"))[0] == 403)

# ======================================================== spotlight 2: automatic chasing
print("--- spotlight 2: automatic chasing of records and prior auth")
load("auth", "key"); pa = task("Cameron", "prior_auth")
check("SP2 start: prior-auth task Waiting on the insurer, no follow-ups yet", pa["status"] == "Waiting" and pa["chases"] == 0 and pa["max_chases"] == 2 and not pa["stuck"], pa)
s, j = advance("days_pass", key="auth"); pa = task("Cameron", "prior_auth")
check("SP2 follow-up date passes -> automatic follow-up 1 of 2 (simulated); task stays Waiting, no staff work", s == 200 and pa["status"] == "Waiting" and pa["chases"] == 1 and "simulated" in j["message"].lower(), (s, j, pa["status"], pa["chases"]))
check("SP2 the follow-up is logged as SIMULATED in the audit trail", "chase.sent" in events(13))
v = pv("cameron"); t = track(v, "insurance")
check("SP2 patient sees 'we followed up automatically 1 time (simulated)'", "followed up automatically 1 time (simulated)" in t["patient_text"], t["patient_text"])
s, od = O("pat", "GET", f"/tasks/{pa['id']}"); ot = track(od["case_view"], "insurance")   # preview19: office wording comes from the OFFICE view only
check("SP2 office row says auto-chasing 1 of 2", "Auto-chasing: 1 of 2" in ot["office_text"], ot["office_text"])
check("SP2 (preview19) the patient's payload carries no office wording", "office_text" not in t, sorted(t))
s, q = O("pat", "GET", "/queue?filter=open"); check("SP2 while auto-chasing, the task is NOT the front desk's next-up", q["next_up"] != pa["id"], q["next_up"])
advance("days_pass", key="auth"); pa = task("Cameron", "prior_auth"); check("SP2 second pass -> follow-up 2 of 2, still Waiting", pa["chases"] == 2 and pa["status"] == "Waiting", pa)
s, j = advance("days_pass", key="auth"); pa = task("Cameron", "prior_auth")
check("SP2 no answer after the limit -> STUCK: back to Assigned for a person to phone", pa["status"] == "Assigned" and pa["stuck"] and "STUCK" in pa["blocked_step"] and "Phone" in pa["next_action"], pa)
check("SP2 stuck is logged", "chase.stuck" in events(13))
t = track(pv("cameron"), "insurance"); check("SP2 patient told plainly a team member is following up by phone (no blame, no date guess)", "following up by phone" in t["patient_text"], t["patient_text"])
s, j = advance("days_pass", key="auth"); check("SP2 nothing Waiting any more -> presenter told so (409)", s == 409, (s, j))
s, j = act("pat", pa["id"], "record_decision", decision="approved", reference="EX-AUTH-7 (example)"); check("SP2 staff record the insurer's decision once they get through", s == 200 and pv("cameron")["gates"]["insurance"], (s, j))
load("missing", "key"); rr = tasks("Blake", "records_request")
advance("days_pass", key="missing"); rr2 = tasks("Blake", "records_request")
check("SP2 records requests to BOTH outside parties are chased automatically", len(rr) == 2 and all(t["chases"] == 1 and t["status"] == "Waiting" for t in rr2), [(t["status"], t["chases"]) for t in rr2])
advance("days_pass", key="missing"); advance("days_pass", key="missing"); rr3 = tasks("Blake", "records_request")
check("SP2 records requests go STUCK after 2 follow-ups and land with the front desk", all(t["stuck"] and t["owner"] == "pat" for t in rr3), [(t["status"], t["stuck"]) for t in rr3])
s, q = O("pat", "GET", "/queue?filter=open"); check("SP2 stuck items rise above routine work in the front desk's queue (after urgent/overdue) and become next-up", q["next_up"] in [t["id"] for t in rr3], (q["next_up"], [(t["id"], t["type"], t.get("stuck")) for t in q["tasks"][:5]]))
load("clean", "key"); load("missing", "key")
s, j = req("POST", "/api/presenter/tick", {}, cookie="ps_presenter=1")[:2]
check("SP2 a normal worker tick does not chase anything that is not yet due", s == 200 and j.get("chased", 0) == 0, j)

# ======================================================== spotlight 3: pre-filled intake + visit-ready summary
print("--- spotlight 3: pre-filled intake (sources labelled simulated) + visit-ready summary (DRAFT)")
load("clean", "intake"); s, f = P("avery", "GET", "/intake")
keys = [x["key"] for x in f["prefill"]]
check("SP3 intake arrives PRE-FILLED (name, DOB, phone, referrer, reason, insurance, imaging, medicines, allergies)", s == 200 and all(k in keys for k in ("name", "dob", "phone", "referrer", "reason", "insurance", "imaging", "meds", "allergies")), keys)
check("SP3 every pre-filled item names its source and the source says SIMULATED", all(x["source"] and "simulated" in x["source"].lower() and x["simulated"] for x in f["prefill"]), [x["source"] for x in f["prefill"]])
check("SP3 every pre-filled item has 'why we ask' and a hint/example", all(x["why"] and x["hint"] for x in f["prefill"]), [(x["key"], x["why"][:20], x["hint"][:20]) for x in f["prefill"]])
check("SP3 question-level help exists for matters / contact / other / safety (safety marked MEDICAL COPY)", all(k in f["help"] for k in ("matters", "contact", "other", "safety")) and "MEDICAL COPY" in f["help"]["safety"]["hint"], list(f["help"]))
check("SP3 pre-filled medicines are fictional examples", all("fictional" in x["value"].lower() or "example" in x["value"].lower() for x in f["prefill"] if x["key"] in ("meds", "allergies")), [x["value"] for x in f["prefill"] if x["key"] in ("meds", "allergies")])
a = full(f); a["confirm"]["meds"] = "change"; a["corrections"] = {"meds": "Stopped ibuprofen; now acetaminophen (example)"}
s, j = P("avery", "POST", "/intake", {"answers": a}); check("SP3 patient confirms most items with one tap and corrects one", s == 200 and j["ok"], (s, j))
check("SP3 the correction becomes a registration-update task (tell us once)", task("Avery", "registration_update"))
_, fr = P("avery", "GET", "/home"); fr = task("Avery", "registration_update")
s, sm = O("pat", "GET", f"/cases/11/summary")
# preview19 Prompt C: the summary is now statements (verbatim) / extracted facts with sources / pre-filled checks / missing-or-conflicting flags; label is "Draft — clinician review required"
check("SP3 visit-ready summary is assembled for the case", s == 200 and sm["statements"] and sm["extracted"] and sm["checked"] and isinstance(sm["flags"], list), (s, list(sm.keys())))
check("SP3 summary is labelled 'Draft — clinician review required', not a clinical note", sm["draft"] and sm["label"] == "Draft \u2014 clinician review required" and "Not a clinical note" in sm["note"], sm["label"])
raw = json.dumps(sm, ensure_ascii=False)
check("SP3 summary shows the patient's correction (verbatim) and flags it against what the referral said", any(x["topic"].startswith("Correction") and "acetaminophen" in x["text"] for x in sm["statements"]) and any(f["kind"] == "conflict" for f in sm["flags"]), "")   # preview19 Prompt C
check("SP3 summary states questionnaires (ODI / NDI / PROMIS) are NOT collected and are an office decision", "Not collected in this demo" in raw and "ODI" in raw, "")
check("SP3 summary lists what is still open (not ready yet: insurance/intake etc.)", isinstance(sm["open_items"], list), sm["open_items"])
s, j = O("pat", "POST", "/cases/11/summary/review"); check("SP3 front desk cannot mark the summary reviewed (403)", s == 403, (s, j))
s, j = O("nina", "POST", "/cases/11/summary/review"); check("SP3 nurse cannot mark it reviewed either (clinician only)", s == 403, (s, j))
s, j = O("yakel", "POST", "/cases/11/summary/review"); check("SP3 Dr. Yakel marks the draft reviewed (who + when recorded)", s == 200 and j["reviewed"]["by"].startswith("Dr.") and not j["reviewed"]["changed_since"], (s, j.get("reviewed")))
check("SP3 review is audited", "summary.reviewed" in events(11))
act("pat", fr["id"], "done", note="Registration updated (example).")
load("clean", "key"); s, sm = O("yakel", "GET", "/cases/11/summary")
check("SP3 reloading the scenario clears the review (new data -> not reviewed)", sm["reviewed"] is None, sm.get("reviewed"))
s, j = O("yakel", "POST", "/cases/11/summary/review"); P("avery", "GET", "/home")
s, j = presenter("/api/presenter/scenario/load", {"key": "clean", "step": "key"}); TOK.clear()
s, d = O("pat", "GET", f"/tasks/{task('Avery', 'schedule_visit')['id']}"); check("SP3 the summary also rides along on the office task detail", d.get("summary") and d["summary"]["draft"], list(d))
s, j = O("pat", "GET", "/cases/999/summary"); check("SP3 summary for a missing case -> 404", s == 404, (s, j))
s, j = req("GET", "/api/o/cases/11/summary", token=tok("avery", "portal"))[:2]; check("SP3 patients cannot read the staff summary (403)", s == 403, (s, j))

# ======================================================== spotlight 4: surgery prep + post-op
print("--- spotlight 4: surgery prep (pre-op checklist, clearance tracking) + post-op check-ins")
load("surgery", "start"); v = pv("harper")
check("SP4 start: surgical pathway with a pre-op checklist (6 items), nothing done yet", v["state"] == "surgery" and len(v["surgery"]["items"]) == 6 and not any(i["done"] for i in v["surgery"]["items"]), [(i["key"], i["status"]) for i in v["surgery"]["items"]])
check("SP4 every checklist item has an owner team", all(i["owner_team"] for i in v["surgery"]["items"]))
check("SP4 instructions slot says the surgical team provides them; the portal gives no medical advice", "does not give medical advice" in v["surgery"]["instruction_note"], v["surgery"]["instruction_note"])
ct = task("Harper", "clearance_request"); check("SP4 a clearance-request task exists for the front desk", ct["owner"] == "pat" and ct["primary_action"]["key"] == "send_clearance", ct.get("primary_action"))
s, j = act("pat", ct["id"], "send_clearance", follow_up_by=TOMORROW); check("SP4 front desk sends the clearance request (simulated fax) -> Waiting", s == 200 and task("Harper", "clearance_request")["status"] == "Waiting", (s, j))
check("SP4 patient sees the clearance item waiting on their primary-care clinic", periop(pv("harper"), "clearance")["waiting_on"].startswith("Sample Primary Care"), periop(pv("harper"), "clearance"))
advance("days_pass", key="surgery"); check("SP4 the clearance request is auto-chased like records (1 of 2, simulated)", task("Harper", "clearance_request")["chases"] == 1)
check("SP4 patient wording mentions the automatic follow-up", "automatically 1 time" in periop(pv("harper"), "clearance")["patient_text"], periop(pv("harper"), "clearance")["patient_text"])
s, d = O("pat", "GET", f"/tasks/{ct['id']}"); sv = d["case_view"]["surgery"]
cons = periop(d["case_view"], "consent"); cid_item = cons["id"]
check("SP4 office checklist offers per-item actions; consent is clinician-only", cons["actions"] and cons["actions"][0]["roles"] == "clinician" and not cons["actions"][0]["allowed"], cons["actions"])
s, j = O("pat", "POST", f"/periop/{cid_item}", {"status": "done", "note": "x"}); check("SP4 front desk cannot record the consent discussion (403)", s == 403, (s, j))
s, j = O("yakel", "POST", f"/periop/{cid_item}", {"status": "done"}); check("SP4 consent needs a note (422)", s == 422, (s, j))
s, j = O("yakel", "POST", f"/periop/{cid_item}", {"status": "done", "note": "Discussed in clinic (example)."}); check("SP4 Dr. Yakel records the consent discussion", s == 200 and periop(j["surgery"], "consent")["done"], (s, j.get("message")))
s, j = O("yakel", "POST", f"/periop/{cid_item}", {"status": "done", "note": "again"}); check("SP4 a completed item cannot be changed again (409)", s == 409, (s, j))
ins = periop(pv("harper"), "insurance"); s, j = O("pat", "POST", f"/periop/{ins['id']}", {"status": "done", "note": ""}); check("SP4 insurance approval needs a reference (422)", s == 422, (s, j))
s, j = act("pat", task("Harper", "clearance_request")["id"], "clearance_received"); check("SP4 clearance arrives (simulated) -> 'received', waiting for a clinician's review", s == 200 and periop(pv("harper"), "clearance")["status"] == "received", (s, j))
clr = periop(pv("harper"), "clearance"); s, j = O("nina", "POST", f"/periop/{clr['id']}", {"status": "done", "note": "ok"}); check("SP4 only a clinician can sign off the clearance (nurse -> 403)", s == 403, (s, j))
h = home("harper"); check("SP4 patient's next step is to confirm they have the written pre-op instructions", h["next_action"]["key"] == "preop_ack", h["next_action"])
s, j = P("harper", "POST", "/preop/instructions"); check("SP4 patient confirms in one tap", s == 200 and periop(pv("harper"), "instructions")["done"], (s, j))
s, j = P("harper", "POST", "/preop/instructions"); check("SP4 confirming twice -> 409", s == 409, (s, j))
load("surgery", "key"); v = pv("harper")
check("SP4 KEY STATE: pre-op midway, clearance waiting with 1 automatic follow-up", v["state"] == "surgery" and periop(v, "consent")["done"] and task("Harper", "clearance_request")["chases"] == 1, [(i["key"], i["status"]) for i in v["surgery"]["items"]])
load("surgery", "postop"); h = home("harper"); v = h["pipeline"]
check("SP4 post-op: state postop, day-2 check-in waiting for the patient", v["state"] == "postop" and v["surgery"]["checkin_due"] and v["surgery"]["checkin_due"]["day"] == 2, v["surgery"]["checkin_due"])
check("SP4 post-op: home next step is the check-in", h["next_action"]["key"] == "checkin" and "911" in h["next_action"]["why"], h["next_action"])
kid = v["surgery"]["checkin_due"]["id"]
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "concern"}); check("SP4 a concern needs a few words (422)", s == 422, (s, j))
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "maybe"}); check("SP4 unknown answer -> 422", s == 422, (s, j))
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "ok"}); check("SP4 'I'm doing okay' -> thanks, no task", s == 200 and not j["task_created"] and not tasks("Harper", "postop_concern"), (s, j))
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "ok"}); check("SP4 answering a closed check-in -> 409", s == 409, (s, j))
load("surgery", "postop"); kid = pv("harper")["surgery"]["checkin_due"]["id"]
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "question", "note": "When can I shower? (example)"})
pc = task("Harper", "postop_concern"); # preview19 Prompt B: the old "a nurse will phone you" promise was removed (no call-back promise unless the practice configures one)
check("SP4 a question goes to the NURSE team (normal priority); the patient is told it reached the care team, with NO call-back promise", s == 200 and j["task_created"] and pc["owner"] == "nina" and pc["priority"] == "normal" and "reached the care team" in j["message"] and not re.search(r"will (phone|call) you", j["message"]), (j, pc["owner"], pc["priority"]))
check("SP4 the portal does not answer the clinical question itself", "shower" not in j["message"].lower(), j["message"])
load("surgery", "postop_concern"); pc = task("Harper", "postop_concern")
check("SP4 KEY STATE post-op concern -> URGENT nurse task with the patient's words", pc["priority"] == "urgent" and pc["owner"] == "nina" and "worried" in pc["reason"], pc)
s, j = act("pat", pc["id"], "close_concern", note="x"); check("SP4 front desk cannot close a clinical concern (403)", s == 403, (s, j))
s, j = act("nina", pc["id"], "close_concern", note="Called the patient; Dr. Yakel saw them same day (example)."); check("SP4 nurse closes it with an outcome note", s == 200, (s, j))
load("surgery", "postop"); kid = pv("harper")["surgery"]["checkin_due"]["id"]
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "question", "note": "I can't feel my legs since this morning (example)"})
check("SP4 emergency wording in a check-in -> 911 guidance + URGENT task", s == 200 and j["emergency"] and "911" in j["message"] and task("Harper", "postop_concern")["priority"] == "urgent", (s, j))
s, j = P("harper", "POST", f"/checkin/{kid}", {"answer": "ok"}); check("SP4 helpers/others cannot double-answer", s == 409, (s, j))
s, j = req("POST", f"/api/p/checkin/{kid}", {"answer": "ok"}, tok("blake", "portal"), K())[:2]; check("SP4 another patient cannot answer Harper's check-in (404)", s == 404, (s, j))
import sqlite3
load("surgery", "postop"); d = sqlite3.connect(DB); d.execute("UPDATE checkins SET due_at=? WHERE case_id=18 AND status='sent'", (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3 * 86400)),)); d.commit(); d.close()
req("POST", "/api/presenter/tick", {}, cookie="ps_presenter=1"); m = task("Harper", "postop_missed")
check("SP4 an unanswered check-in becomes a front-desk call task (no silent drop)", m["owner"] == "pat" and m["primary_action"]["key"] == "done", m)
check("SP4 check-in events are audited", "checkin.missed" in events(18))
s, j = presenter("/api/presenter/scenario/load", {"key": "clean", "step": "postop"}); check("SP4 surgery steps only exist for the surgery scenario (422)", s == 422, (s, j))

# ======================================================== cross-cutting
print("--- cross-cutting")
s, sc = req("GET", "/api/presenter/scenarios", cookie="ps_presenter=1")[:2]
check("presenter lists 8 scenarios incl. surgery", len(sc["scenarios"]) == 8 and sc["scenarios"][-1]["key"] == "surgery", [x["key"] for x in sc["scenarios"]])
raw = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
check("chase cadence/limit and check-in days are marked as placeholders in code", "prototype placeholder - office to decide" in raw and "prototype placeholder - surgeon to decide" in raw)
s, j = req("GET", "/api/health")[:2]; check("server healthy at the end", s == 200, j)
srv_log = open("/tmp/api3_srv.log").read(); check("no server errors logged", "server error" not in srv_log, srv_log[-300:])
stop()
ok = sum(1 for r in RES if r[1]); print(f"\nDONE api_spotlight_test: {ok}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_spotlight_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(RES) else 1)
