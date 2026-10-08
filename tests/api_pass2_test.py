#!/usr/bin/env python3
"""Pass 2 API tests: the seven referral scenarios walked END TO END through the real HTTP API (stdlib only, no external network).
Each scenario is reset to its START with the presenter shortcut, then every step is done with the same endpoints the screens use,
signed in as the right fictional person.  Starts its own server on 127.0.0.1:8771 with a temp DB and --no-worker."""
import http.client, json, os, re, signal, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8771")); DB = os.path.join(tempfile.mkdtemp(), "t2.db")
RES = []; proc = None
def start():
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=open("/tmp/api2_srv.log", "w"), stderr=subprocess.STDOUT)
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

start()
presenter("/api/presenter/reset")
check("presenter is required for scenario shortcuts (no cookie -> 403)", req("POST", "/api/presenter/scenario/load", {"key": "clean"})[0] == 403)
s, sc = req("GET", "/api/presenter/scenarios", cookie="ps_presenter=1")[:2]
check("eight scenarios are listed with owner / human step / patient sees / office sees", s == 200 and len(sc["scenarios"]) == 8 and all(x["owner"] and x["human"] and x["patient_sees"] and x["office_sees"] for x in sc["scenarios"]), sc)
check("all scenario patients are labelled example / fictional", all("Example" in x["portal_persona"] for x in sc["scenarios"]), [x["portal_persona"] for x in sc["scenarios"]])

# ======================================================== 1. clean referral
print("--- scenario 1: clean referral")
load("clean"); v = pv("avery")
check("S1 start: state is fit_review (a clinician must look first)", v["state"] == "fit_review", v["state"])
check("S1 start: patient told the clinical team is reviewing, waiting on our team", track(v, "referral")["waiting_on"] == "Premier Spine (our team)", track(v, "referral"))
s, j = P("avery", "GET", "/intake"); check("S1 start: intake is not open before the referral is accepted (409)", s == 409 and j["error"] == "intake_not_sent", (s, j))
ft = task("Avery", "fit_review")
check("S1 queue: fit review shows a one-click primary action 'Accept referral'", ft["primary_action"]["key"] == "accept" and not ft["primary_action"]["needs_input"], ft["primary_action"])
check("S1 queue: front desk sees the accept action as NOT allowed (with the reason)", not ft["primary_action"]["allowed"] and "clinician" in ft["primary_action"]["why_not"], ft["primary_action"])
s, j = act("pat", ft["id"], "accept"); check("S1 front desk cannot accept a referral (403)", s == 403, (s, j))
s, j = act("nina", ft["id"], "accept"); check("S1 nurse cannot accept a referral (403)", s == 403, (s, j))
s, d = O("yakel", "GET", f"/api/o/tasks/{ft['id']}".replace("/api/o", ""))
check("S1 office detail returns the shared case view and server-defined actions", s == 200 and d["case_view"]["state"] == "fit_review" and [a["key"] for a in d["actions"]] == ["accept", "need_info", "route_elsewhere"], (s, d and d.get("actions")))
s, j = act("yakel", ft["id"], "accept", reviewed_report=True); check("S1 clinician accepts in one click (with 'I reviewed the attached MRI report')", s == 200, (s, j))
v = pv("avery"); check("S1 after accept: records done (report reviewed with acceptance, images received)", track(v, "records")["done"], v["tracks"])
it = task("Avery", "insurance_check"); check("S1 insurance check task appears for the front desk, labelled simulated", it["primary_action"]["simulated"] and it["primary_action"]["allowed"], it["primary_action"])
s, j = act("pat", it["id"], "run_check"); check("S1 simulated eligibility check: no prior auth needed", s == 200 and "no prior authorization" in j["message"], j)
v = pv("avery"); ins = track(v, "insurance"); check("S1 patient sees insurance done AND marked simulated", ins["done"] and ins["simulated"] and "simulated" in ins["patient_text"], ins)
h = home("avery"); check("S1 patient's one next action is the intake", h["next_action"]["key"] == "intake", h["next_action"])
s, f = P("avery", "GET", "/intake")
check("S1 tell-us-once: intake pre-fills name, DOB, phone, referrer, reason, insurance, imaging place", s == 200 and {x["key"] for x in f["prefill"]} >= {"name", "dob", "phone", "referrer", "reason", "insurance", "imaging"} and not f["ask_facility"], f and [x["key"] for x in f["prefill"]])
s, j = P("avery", "PUT", "/intake/draft", {"answers": {"confirm": {"name": "ok"}, "matters": ["Sleeping"]}}); check("S1 partial draft autosaves on the server", s == 200 and j["saved_at"] and not j["red_flag"], (s, j))
s, f2 = P("avery", "GET", "/intake"); check("S1 draft comes back after reload (server-side, not browser storage)", f2["draft"]["matters"] == ["Sleeping"] and f2["draft"]["confirm"] == {"name": "ok"}, f2["draft"])
s, j = P("avery", "POST", "/intake", {"answers": full(f, confirm={"name": "ok"})}); check("S1 submit without confirming every pre-filled fact -> 422 naming the field", s == 422 and j["error"] == "confirm_each" and j.get("field"), (s, j))
s, j = P("avery", "POST", "/intake", {"answers": full(f, redflag_none=False)}); check("S1 submit without answering the symptom question -> 422", s == 422 and j["error"] == "redflag_required", (s, j))
s, j = P("avery", "POST", "/intake", {"answers": full(f, redflags=["severe_pain"], redflag_none=True)}); check("S1 symptom ticked AND 'none of these' -> 422 (no silent guess)", s == 422 and j["error"] == "redflag_conflict", (s, j))
k = K(); s, j = P("avery", "POST", "/intake", {"answers": full(f)}, key=k); check("S1 patient submits intake", s == 200 and not j["needs_patient_confirmation"], (s, j))
s2, j2 = P("avery", "POST", "/intake", {"answers": full(f)}, key=k); check("S1 replaying the same submit (same Idempotency-Key) is safe", s2 == 200, (s2, j2))
v = pv("avery"); check("S1 KEY STATE: ready for appointment, every gate green", v["state"] == "ready" and all(v["gates"].values()), (v["state"], v["gates"]))
check("S1 patient sees 'You're ready' and that the office will call to book", "ready" in track(v, "appointment")["patient_text"].lower(), track(v, "appointment"))
sv = task("Avery", "schedule_visit"); check("S1 office gets ONE 'Book the visit' task (needs date/time input)", sv["primary_action"]["key"] == "book" and sv["primary_action"]["needs_input"] and len(tasks("Avery")) == 1, [(t["type"], t["status"]) for t in tasks("Avery")])
s, j = act("pat", sv["id"], "book", date="2020-01-01", time="10:00", clinician="Dr. Stefan Yakel, DO"); check("S1 booking in the past -> 422", s == 422, (s, j))
s, j = act("pat", sv["id"], "book", date=TOMORROW, time="10:30", clinician="Dr. Stefan Yakel, DO"); check("S1 front desk books the visit", s == 200, (s, j))
h = home("avery"); check("S1 after booking: state booked and the patient's next appointment shows", h["pipeline"]["state"] == "booked" and h.get("next_appointment"), (h["pipeline"]["state"], h.get("next_appointment")))
ev = events(11); check("S1 audit trail: referral.received -> case.ready -> appointment.booked (append-only events)", ev.index("referral.received") < ev.index("case.ready") < ev.index("appointment.booked"), ev)

# ======================================================== 2. missing records / imaging
print("--- scenario 2: missing imaging / records")
load("missing")
rr = tasks("Blake", "records_request"); check("S2 one records-request task per source is created at referral receipt (2)", len(rr) == 2, [(t["blocked_step"]) for t in rr])
act("yakel", task("Blake", "fit_review")["id"], "accept", reviewed_report=False)
v = pv("blake"); check("S2 not ready: gathering", v["state"] == "gathering", v["state"])
w = [t for t in v["tracks"] if t["key"].startswith("records:")]
check("S2 patient sees each missing source by name (before requests: our team is about to ask)", len(w) == 2 and all(t["waiting_on"] == "Premier Spine (our team)" for t in w), w)
for t in rr:
    s, j = act("pat", t["id"], "send_request"); check(f"S2 send records request (simulated fax, default follow-up date) -> Waiting [{t['id']}]", s == 200 and "simulated" in j["message"] and j["task"]["status"] == "Waiting" and j["task"]["follow_up_by"], (s, j))
v = pv("blake"); w = [t for t in v["tracks"] if t["key"].startswith("records:")]
check("S2 patient now sees 'waiting on <imaging center> / <referring office>' with the request date and a simulated label", {t["waiting_on"] for t in w} == {"Example Family Clinic (fictional)", "Lakeshore Imaging (fictional)"} and all(t["simulated"] and "simulated" in t["patient_text"] for t in w), w)
check("S2 patient view never guesses a date: shows 'check again by' from the staff follow-up date", all(t["next_check"] for t in w), w)
s, j = presenter("/api/presenter/scenario/advance", {"event": "records_arrive_missing"}); check("S2 simulated fax: office notes + MRI report arrive, images do not", s == 200 and "did NOT" in j["message"], j)
for t in tasks("Blake", "records_request"):
    s, d = O("pat", "GET", f"/tasks/{t['id']}"); a = {x["key"]: x for x in d["actions"]}
    if "mark_received" in a:
        arrived = [o["value"] for o in a["mark_received"]["fields"][0]["options"] if "arrived" in o["label"]]
        s, j = act("pat", t["id"], "mark_received", items=arrived); check(f"S2 staff confirms the arrived fax matches the patient (checklist) [{t['id']}]", s == 200 and arrived, (s, j, arrived))
v = pv("blake"); check("S2 images still outstanding after the report arrived (report and images tracked separately)", any("MRI images" in t["patient_text"] for t in v["tracks"] if not t["done"]), v["tracks"])
rv = task("Blake", "records_review"); s, j = act("pat", rv["id"], "mark_reviewed"); check("S2 front desk cannot mark the MRI report reviewed (403)", s == 403, (s, j))
s, j = act("pat", rv["id"], "waive_images", note="x"); check("S2 front desk cannot waive images (403)", s == 403, (s, j))
s, j = act("yakel", rv["id"], "mark_reviewed"); check("S2 clinician marks the MRI report reviewed", s == 200, (s, j))
v = pv("blake"); check("S2 still NOT ready: images missing even though the report is reviewed", v["state"] == "gathering" and not v["gates"]["records"], v["gates"])
s, j = act("yakel", task("Blake", "records_review")["id"], "waive_images", note=""); check("S2 waiving images needs a clinical reason (422)", s == 422, (s, j))
s, j = act("yakel", task("Blake", "records_review")["id"], "waive_images", note="Report is enough for the first visit (example)."); check("S2 clinician decides to proceed without images (reason recorded)", s == 200, (s, j))
check("S2 open records request for the images was closed as no longer needed", not tasks("Blake", "records_request"), tasks("Blake", "records_request"))
act("pat", task("Blake", "insurance_check")["id"], "run_check")
s, f = P("blake", "GET", "/intake"); P("blake", "POST", "/intake", {"answers": full(f)})
v = pv("blake"); check("S2 end: ready once records, insurance and intake are all done", v["state"] == "ready", (v["state"], v["gates"]))
load("missing", "key"); v = pv("blake")
check("S2 KEY STATE (presenter jump): waiting on the imaging center and the referring office", v["state"] == "gathering" and {t["waiting_on"] for t in v["tracks"] if t["key"].startswith("records:")} == {"Example Family Clinic (fictional)", "Lakeshore Imaging (fictional)"}, v["tracks"])

# ======================================================== 3. prior auth
print("--- scenario 3: insurance needs prior auth")
load("auth"); act("yakel", task("Cameron", "fit_review")["id"], "accept", reviewed_report=True)
s, j = act("pat", task("Cameron", "insurance_check")["id"], "run_check"); check("S3 simulated eligibility check says prior auth is required", s == 200 and "required" in j["message"], j)
pa = task("Cameron", "prior_auth"); check("S3 prior-auth task: one-click 'Submit prior-auth request (simulated)'", pa["primary_action"]["key"] == "submit_auth" and pa["primary_action"]["simulated"], pa["primary_action"])
v = pv("cameron"); check("S3 patient sees their plan must approve first (no dates promised)", "approve" in track(v, "insurance")["patient_text"] and not track(v, "insurance")["done"], track(v, "insurance"))
s, j = act("pat", pa["id"], "submit_auth"); check("S3 submit prior auth -> Waiting on the insurer", s == 200 and j["task"]["status"] == "Waiting" and "Sample Insurance" in j["task"]["waiting_on"], j)
v = pv("cameron"); ins = track(v, "insurance")
check("S3 patient sees 'waiting on Sample Insurance Co.' and 'can't predict when'", ins["waiting_on"].startswith("Sample Insurance") and "can\u2019t predict" in ins["patient_text"] and ins["simulated"], ins)
s, f = P("cameron", "GET", "/intake"); P("cameron", "POST", "/intake", {"answers": full(f)})
v = pv("cameron"); check("S3 not ready while the insurer has not decided (intake done)", v["state"] == "gathering" and not v["gates"]["insurance"] and v["gates"]["intake"], v["gates"])
s, j = act("pat", pa["id"], "record_decision", decision="approved", reference=""); check("S3 recording an insurer decision requires a reference (422)", s == 422, (s, j))
s, j = act("pat", pa["id"], "record_decision", decision="maybe", reference="x"); check("S3 unknown decision value -> 422", s == 422, (s, j))
s, j = act("pat", pa["id"], "record_decision", decision="more_info", reference="Call ref EX-001 (example)"); check("S3 insurer asks for more info -> task back In Progress, not approved", s == 200 and j["task"]["status"] == "In Progress" and not j["case_view"]["gates"]["insurance"], j)
act("pat", pa["id"], "submit_auth")
s, j = act("pat", pa["id"], "record_decision", decision="approved", reference="Auth EX-12345 (example)"); check("S3 staff record approval with reference -> insurance gate passes -> ready", s == 200 and j["case_view"]["state"] == "ready", j and j.get("case_view", {}).get("state"))
load("auth", "key"); v = pv("cameron")
check("S3 KEY STATE (presenter jump): waiting on the insurer's decision", track(v, "insurance")["waiting_on"].startswith("Sample Insurance") and v["state"] == "gathering", track(v, "insurance"))
s, j = act("pat", task("Cameron", "prior_auth")["id"], "record_decision", decision="denied", reference="Denial EX-9 (example)")
check("S3 denial -> a person-call task, nothing automatic", s == 200 and task("Cameron", "auth_denied")["owner"] in ("pat", "nina"), (s, j))
v = pv("cameron"); check("S3 patient asked to call us about options, no unconfigured 'we will call you' promise (no auto-cancel)", "call us" in track(v, "insurance")["patient_text"].lower() and "will call" not in track(v, "insurance")["patient_text"] and v["state"] == "gathering", track(v, "insurance"))   # preview19 Prompt C

# ======================================================== 4. intake never completed
print("--- scenario 4: patient never completes intake")
load("nointake"); act("yakel", task("Drew", "fit_review")["id"], "accept", reviewed_report=True); act("pat", task("Drew", "insurance_check")["id"], "run_check")
it = task("Drew", "intake_followup"); check("S4 intake invitation sent (simulated text): task Waiting on the patient", it["status"] == "Waiting" and "Patient" in it["waiting_on"], it)
for n in (1, 2, 3):
    s, j = act("pat", it["id"], "send_reminder"); check(f"S4 reminder {n} of 3 (simulated text)", s == 200 and f"{n} of 3" in j["message"], (s, j))
s, j = act("pat", it["id"], "send_reminder"); check("S4 a 4th reminder is refused (409): the limit is 3", s == 409 and j["error"] == "action_not_available", (s, j))
it = task("Drew", "intake_followup"); check("S4 after 3 reminders the primary action becomes 'Log a phone call' (a person)", it["primary_action"]["key"] == "log_call" and it["followup_due"], it["primary_action"])
v = pv("drew"); check("S4 patient sees 'Waiting on you' and how many (simulated) reminders were sent", track(v, "intake")["waiting_on"] == "You" and "3 reminders" in track(v, "intake")["patient_text"], track(v, "intake"))
s, j = act("pat", it["id"], "log_call", outcome="no_answer", note="Example call"); check("S4 log a call: no answer -> stays open for another try", s == 200 and j["task"]["status"] == "In Progress", j)
s, j = act("pat", it["id"], "log_call", outcome="maybe"); check("S4 unknown call outcome -> 422", s == 422, (s, j))
s, j = act("pat", it["id"], "close_unreachable", note=""); check("S4 closing as unreachable needs a note (422)", s == 422, (s, j))
s, j = act("pat", it["id"], "log_call", outcome="reached_by_phone", note="Went through the questions by phone (example)."); check("S4 reached -> intake completed by phone, task resolved", s == 200 and j["task"]["status"] == "Resolved", j)
v = pv("drew"); check("S4 end: ready after the phone intake", v["state"] == "ready", (v["state"], v["gates"]))
load("nointake", "key"); v = pv("drew"); it = task("Drew", "intake_followup")
check("S4 KEY STATE (presenter jump): 3 reminders sent, phone-call task", it["primary_action"]["key"] == "log_call" and "3 reminders" in track(v, "intake")["patient_text"], (it["primary_action"], track(v, "intake")))
s, j = presenter("/api/presenter/scenario/advance", {"event": "reminder_due_drew"}); check("S4 presenter 'next reminder' at the limit is refused, not sent (409)", s == 409, (s, j))

# ======================================================== 5. caregiver completes intake
print("--- scenario 5: caregiver completes intake for the patient")
s, j = P("riley", "GET", "/intake"); check("S5 a helper WITHOUT the intake permission gets 403 (Riley for Alex)", s == 403, (s, j))
load("caregiver", "intake")
s, f = P("frankie", "GET", "/intake"); check("S5 helper with permission opens the intake for Emery (viewer = caregiver)", s == 200 and f["viewer"] == "caregiver" and f["patient_first"] == "Emery", (s, f and f.get("viewer")))
h = home("frankie"); check("S5 helper home shows the intake as the next step and Emery's checklist", h["next_action"]["key"] == "intake" and "Emery" in track(h["pipeline"], "intake")["patient_text"], (h.get("next_action"), track(h["pipeline"], "intake")))
s, j = P("frankie", "POST", "/intake", {"answers": full(f, confirm=dict({x["key"]: "ok" for x in f["prefill"]}, phone="change"), corrections={"phone": "(208) 555-0199 (example)"})})
check("S5 helper submits -> needs the patient's confirmation", s == 200 and j["needs_patient_confirmation"], (s, j))
v = pv("emery"); check("S5 KEY STATE: not ready until Emery confirms; waiting on Emery", v["state"] == "gathering" and not v["gates"]["intake"] and track(v, "intake")["waiting_on"] == "You", (v["gates"], track(v, "intake")))
check("S5 office gets an 'intake confirm' task and a registration-update task for the corrected phone", task("Emery", "intake_confirm") and task("Emery", "registration_update"), [t["type"] for t in tasks("Emery")])
h = home("emery"); check("S5 patient's next step is 'check the answers' (attest)", h["next_action"]["key"] == "attest", h["next_action"])
s, f = P("emery", "GET", "/intake"); check("S5 patient sees exactly what the helper entered, and who entered it", f["submitted_answers"]["corrections"]["phone"].startswith("(208) 555-0199") and f["submitted_by"] == "Frankie Helper", (f.get("submitted_answers"), f.get("submitted_by")))
s, j = P("frankie", "POST", "/intake/attest", {}); check("S5 the helper cannot confirm on the patient's behalf (403)", s == 403, (s, j))
s, j = P("emery", "POST", "/intake/attest", {}); check("S5 patient confirms in the portal", s == 200, (s, j))
v = pv("emery"); check("S5 after confirmation: intake gate passes -> ready", v["gates"]["intake"] and v["state"] == "ready", v["gates"])
check("S5 the office confirm task was closed automatically by the patient's confirmation", not tasks("Emery", "intake_confirm"), tasks("Emery", "intake_confirm"))
s, j = P("emery", "POST", "/intake/attest", {}); check("S5 confirming twice -> 409", s == 409, (s, j))
load("caregiver", "key"); ic = task("Emery", "intake_confirm")
s, j = act("pat", ic["id"], "confirm_by_phone", note="Emery confirmed each answer by phone (example)."); check("S5 alternative: office records the patient's confirmation by phone", s == 200 and j["case_view"]["gates"]["intake"], j and j.get("case_view", {}).get("gates"))

# ======================================================== 6. not a fit / route elsewhere
print("--- scenario 6: referral that may need to route elsewhere")
load("notfit"); ft = task("Finley", "fit_review")
for _ in range(3): presenter("/api/presenter/tick")
v = pv("finley"); check("S6 NO auto-decline: after the background steps run, still waiting for a clinician", v["state"] == "fit_review" and task("Finley", "fit_review")["status"] != "Resolved", v["state"])
s, d = O("pat", "GET", f"/tasks/{ft['id']}"); ra = {a["key"]: a for a in d["actions"]}["route_elsewhere"]
check("S6 front desk sees 'Route elsewhere' disabled with the reason (clinician only)", not ra["allowed"] and "clinician" in ra["why_not"].lower(), ra)
s, j = act("pat", ft["id"], "route_elsewhere", reason="x"); check("S6 front desk cannot route elsewhere (403)", s == 403, (s, j))
s, j = act("nina", ft["id"], "route_elsewhere", reason="x"); check("S6 nurse cannot route elsewhere (403)", s == 403, (s, j))
s, j = act("frank", ft["id"], "need_info", question="Is there a lumbar MRI? (example question)"); check("S6 NP (clinician) asks the referring office a question instead", s == 200, (s, j))
v = pv("finley"); check("S6 patient sees 'we asked your referring office a question', waiting on that office", track(v, "referral")["waiting_on"] == "Example Urgent Care (fictional)", track(v, "referral"))
ri = task("Finley", "referral_info"); s, j = act("pat", ri["id"], "send_info_request"); check("S6 front desk sends the question (simulated fax) -> Waiting", s == 200 and j["task"]["status"] == "Waiting", j)
s, j = act("pat", ri["id"], "info_received", answer="No imaging; knee pain is primary (example)."); check("S6 answer recorded -> fit review is back with the clinician", s == 200 and pv("finley")["state"] == "fit_review", (s, j))
s, j = act("yakel", ft["id"], "route_elsewhere", reason=""); check("S6 routing elsewhere requires a reason (422)", s == 422, (s, j))
SECRET = "Knee is the primary complaint; better suited to an orthopedic knee clinic (example staff-only reason)"
s, j = act("yakel", ft["id"], "route_elsewhere", reason=SECRET); check("S6 clinician routes elsewhere (human decision, reason recorded)", s == 200 and j["case_view"]["state"] == "routed", (s, j))
nr = task("Finley", "notify_routed"); check("S6 a front-desk call task is created to tell the patient and referring office", nr["owner"] in ("pat", "nina"), nr)
h = home("finley"); raw = json.dumps(h)
check("S6 patient is asked to call us about next steps (no promise) and does NOT see the staff-only reason", "call us" in track(h["pipeline"], "referral")["patient_text"].lower() and "will call" not in track(h["pipeline"], "referral")["patient_text"] and "orthopedic knee clinic" not in raw, track(h["pipeline"], "referral"))   # preview19 Prompt C
check("S6 no intake/records/insurance asks shown to a routed patient", [t["key"] for t in h["pipeline"]["tracks"]] == ["referral"] and h["next_action"]["key"] == "none", ([t["key"] for t in h["pipeline"]["tracks"]], h.get("next_action")))
s, j = P("finley", "GET", "/intake"); check("S6 routed patient: intake stays closed", s == 409, (s, j))
load("notfit", "key"); check("S6 KEY STATE (presenter jump): clinician fit decision pending", pv("finley")["state"] == "fit_review")

# ======================================================== 7. red flag during intake
print("--- scenario 7: red-flag symptoms reported during intake")
load("redflag", "intake"); s, f = P("gray", "GET", "/intake")
check("S7 red-flag checklist and 911 guidance text are served with the form, marked as medical copy pending review", len(f["redflags"]) == 4 and "911" in f["redflag_guidance"] and "Dr. Yakel" in f["medical_copy_note"], f["medical_copy_note"])
s, j = P("gray", "PUT", "/intake/draft", {"answers": {"redflags": ["saddle_numb"]}})
check("S7 ticking a red-flag box raises the flag on AUTOSAVE (before submit) and returns 911 guidance", s == 200 and j["red_flag"] and "911" in j["guidance"], (s, j))
rf = task("Gray", "red_flag"); check("S7 urgent task created for the nurse team (owner Nina, backup Dr. Yakel)", rf["priority"] == "urgent" and rf["owner"] == "nina" and rf["backup"] == "yakel", rf)
h = home("gray"); check("S7 patient home: URGENT next step with 911 / call-the-office", h["next_action"]["key"] == "urgent" and "911" in h["next_action"]["title"] + h["next_action"]["why"], h["next_action"])
check("S7 case state urgent: not bookable", h["pipeline"]["state"] == "urgent" and not h["pipeline"]["ready"], h["pipeline"]["state"])
P("gray", "PUT", "/intake/draft", {"answers": {"redflags": ["saddle_numb", "bladder_bowel"]}})
check("S7 saving again does not create a duplicate urgent task", len(tasks("Gray", "red_flag")) == 1, tasks("Gray", "red_flag"))
s, q = O("nina", "GET", "/api/o/queue?filter=urgent".replace("/api/o", "")); check("S7 'Urgent' filter shows the red-flag task first", q["tasks"] and q["tasks"][0]["id"] == rf["id"], [t["type"] for t in q["tasks"]])
s, q = O("nina", "GET", "/queue?filter=open"); check("S7 'Next up' for the nurse is the red-flag task", q["next_up"] == rf["id"], q["next_up"])
s, j = act("pat", rf["id"], "clear_flag", note="x"); check("S7 front desk cannot clear the urgent hold (403)", s == 403, (s, j))
s, j = act("nina", rf["id"], "log_contact", note="Reached the patient by phone; advised per protocol (example)."); check("S7 nurse logs contact; urgent hold stays", s == 200 and pv("gray")["state"] == "urgent", (s, j))
s, j = act("nina", rf["id"], "clear_flag", note="Nurse + Dr. Yakel reviewed (example outcome)."); check("S7 nurse clears the hold with a clinical outcome note", s == 200 and pv("gray")["state"] == "gathering", (s, j))
P("gray", "PUT", "/intake/draft", {"answers": {"redflags": ["saddle_numb", "bladder_bowel"]}})
check("S7 autosaving the SAME reviewed symptoms does not re-raise the hold", pv("gray")["state"] == "gathering" and not tasks("Gray", "red_flag"), pv("gray")["state"])
s, j = P("gray", "PUT", "/intake/draft", {"answers": {"redflags": ["saddle_numb", "bladder_bowel", "new_weakness"]}})
check("S7 a NEW symptom raises it again", j["red_flag"] and pv("gray")["state"] == "urgent", j)
load("redflag", "intake"); s, j = P("gray", "PUT", "/intake/draft", {"answers": {"other": "Since yesterday I can't feel my legs (example)"}})
check("S7 emergency wording in the free-text answer also raises the flag", s == 200 and j["red_flag"], (s, j))
load("redflag", "key"); check("S7 KEY STATE (presenter jump): urgent", pv("gray")["state"] == "urgent" and task("Gray", "red_flag"))

# ======================================================== cross-cutting
print("--- cross-cutting")
load("clean"); load("missing")
raw = json.dumps(home("avery")); check("isolation: Avery's portal data contains nothing about Blake", "Blake" not in raw and "Neck pain with arm tingling" not in raw, "")
check("isolation: a patient token cannot use office routes", req("GET", "/api/o/queue", token=tok("avery", "portal"))[0] == 403)
check("isolation: a helper token cannot use office routes", req("GET", "/api/o/queue", token=tok("riley", "portal"))[0] == 403)
s, j = req("POST", f"/api/o/tasks/{task('Blake', 'fit_review')['id']}/act", {"action": "accept"}, tok("yakel", "office"))[:2]
check("quick actions require an Idempotency-Key (400/428)", s in (400, 428), (s, j))
s, j = act("yakel", task("Blake", "fit_review")["id"], "nonsense"); check("unknown action -> 409 with the list of available actions", s == 409 and "accept" in j.get("available", []), (s, j))
s, j = act("pat", 999999, "accept"); check("action on a missing task -> 404", s == 404, (s, j))
s, q = O("yakel", "GET", "/queue?filter=decisions"); check("'Clinician decisions' filter lists fit reviews for the clinician", any(t["type"] == "fit_review" for t in q["tasks"]) and all(t.get("primary_action") for t in q["tasks"] if t["type"] == "fit_review"), [t["type"] for t in q["tasks"]])
s, q = O("pat", "GET", "/queue?filter=referrals"); check("'Referral pipeline' filter: every row has a case state and a primary action", q["tasks"] and all(t.get("case_state") and t.get("primary_action") for t in q["tasks"]), [(t["type"], t.get("case_state")) for t in q["tasks"]][:5])
s, q = O("pat", "GET", "/queue?filter=open"); check("queue returns a 'next_up' the signed-in person can do now", q["next_up"] and next(t for t in q["tasks"] if t["id"] == q["next_up"])["primary_action"]["allowed"], q["next_up"])
raw = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
check("simulated channels are labelled in code (fax / text / insurance)", all(x in raw for x in ("SIMULATED \\u2014 nothing was sent", "SIM_TEXT", "SIM_INS")))
s, j = req("GET", "/api/health")[:2]; check("server healthy at the end", s == 200, j)
stop()
ok = sum(1 for r in RES if r[1]); print(f"\nDONE api_pass2_test: {ok}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_pass2_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(RES) else 1)
