#!/usr/bin/env python3
"""preview19 API tests: per-field intake confirmation (patient vs helper), server-enforced duplicate-submit protection,
the Home payload for the six example states (incl. the new clean/booked step), and no office wording in patient payloads.
Own server on 127.0.0.1:8781 (PS_TEST_PORT), temp DB, --no-worker.  Fictional data only."""
import http.client, json, os, re, signal, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8781")); DB = os.path.join(tempfile.mkdtemp(), "t19.db")
RES = []; proc = None
def start():
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=open("/tmp/api19_srv.log", "w"), stderr=subprocess.STDOUT)
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

start()
# ======================================================== A. pre-filled data is never patient-confirmed by default
print("--- A. per-field confirmation is tracked on the server")
load("clean", "intake"); s, f = P("avery", "GET", "/intake")
check("A1 every pre-filled item starts NOT patient-confirmed", s == 200 and f["prefill"] and all(x["patient_confirmed"] is False for x in f["prefill"]), [(x["key"], x.get("patient_confirmed")) for x in f.get("prefill", [])])
check("A2 field_status lists every pre-filled field as 'unconfirmed'", set(f["field_status"]) == {x["key"] for x in f["prefill"]} and all(v["state"] == "unconfirmed" for v in f["field_status"].values()), f["field_status"])
check("A3 pre-fill only from source rows: Avery has no meds/allergies on the referral -> not pre-filled", not any(x["key"] in ("meds", "allergies") for x in f["prefill"]) or all(x["value"] for x in f["prefill"]), [x["key"] for x in f["prefill"]])
s, j = req("PUT", "/api/p/intake/draft", {"answers": {"confirm": {"name": "ok", "phone": "change"}, "corrections": {"phone": "(208) 555-0142 (example)"}}}, tok("avery", "portal"))[:2]
fs = j and j.get("field_status") or {}
check("A4 a draft save records per-field state: name confirmed, phone corrected, dob still unconfirmed", s == 200 and fs["name"]["state"] == "confirmed" and fs["phone"]["state"] == "corrected" and fs.get("dob", {"state": "unconfirmed"})["state"] == "unconfirmed", fs)
check("A5 ... recorded with WHO (role) and WHEN, but still not patient-confirmed (a draft is not a confirmation)", fs["name"]["by_role"] == "patient" and fs["name"]["at"] and fs["name"]["patient_confirmed"] is False, fs["name"])
t0 = fs["name"]["at"]; time.sleep(1.1)
s, j = req("PUT", "/api/p/intake/draft", {"answers": {"confirm": {"name": "ok", "phone": "change"}, "corrections": {"phone": "(208) 555-0142 (example)"}, "matters": ["Sleeping"]}}, tok("avery", "portal"))[:2]
check("A6 re-saving an unchanged answer keeps when it was first given", j["field_status"]["name"]["at"] == t0, (t0, j["field_status"]["name"]))
s, j = req("PUT", "/api/p/intake/draft", {"answers": {"confirm": {"phone": "change"}, "corrections": {"phone": "(208) 555-0142 (example)"}}}, tok("avery", "portal"))[:2]
check("A7 un-answering a field returns it to 'unconfirmed'", j["field_status"]["name"]["state"] == "unconfirmed", j["field_status"]["name"])
s, f = P("avery", "GET", "/intake"); check("A8 answers come back after leaving (server draft), incl. the correction", f["draft"]["corrections"].get("phone") == "(208) 555-0142 (example)" and f["field_status"]["phone"]["state"] == "corrected", f["draft"])

# ======================================================== B. duplicate submissions are blocked by the server
print("--- B. duplicate submission")
key = K(); ans = full(f, confirm=dict({x["key"]: "ok" for x in f["prefill"]}, phone="change"), corrections={"phone": "(208) 555-0142 (example)"})
s1, j1 = P("avery", "POST", "/intake", {"answers": ans}, key=key)
s2, j2 = P("avery", "POST", "/intake", {"answers": ans}, key=key)
check("B1 first submit succeeds", s1 == 200 and j1["ok"], (s1, j1))
check("B2 same Idempotency-Key + same body -> the SAME response is replayed (no second submission)", s2 == 200 and j1 == j2, (s2, j2))
s3, j3 = P("avery", "POST", "/intake", {"answers": ans}, key=K())
check("B3 a NEW key after success -> 409 already_submitted (server-enforced, not just the disabled button)", s3 == 409 and j3["error"] == "already_submitted", (s3, j3))
s4, j4 = P("avery", "POST", "/intake", {"answers": dict(ans, other="different")}, key=key)
check("B4 reusing a key for a DIFFERENT body -> 422", s4 == 422, (s4, j4))
s5, j5 = req("POST", "/api/p/intake", {"answers": ans}, tok("avery", "portal"))[:2]
check("B5 submit without an Idempotency-Key is refused", s5 in (400, 428), (s5, j5))
s, f = P("avery", "GET", "/intake")
check("B6 after the patient submits, every field is patient-confirmed (with a time)", all(v["patient_confirmed"] and v["patient_confirmed_at"] for v in f["field_status"].values()), f["field_status"])
raw = summary_raw("Avery")
# preview19 Prompt C: corrections are now verbatim patient statements; pre-filled checks carry "confirmed by patient"
check("B7 clinician summary lists the patient's own correction (verbatim) among the patient's statements", any("(phone)" in x["topic"] and x["text"] == "(208) 555-0142 (example)" for x in json.loads(raw)["statements"]), raw[:400])
check("B8 ... and confirmed items say 'confirmed by patient'", "confirmed by patient" in raw, raw[:400])

# ======================================================== C. a helper's ticks are never shown as the patient's
print("--- C. helper-entered answers")
load("caregiver", "intake"); s, f = P("frankie", "GET", "/intake")
s, j = P("frankie", "POST", "/intake", {"answers": full(f)})
check("C1 helper submits", s == 200 and j["needs_patient_confirmation"], (s, j))
s, f2 = P("emery", "GET", "/intake")
check("C2 fields the helper checked are recorded as by_role=caregiver and NOT patient-confirmed", all(v["by_role"] == "caregiver" and not v["patient_confirmed"] for v in f2["field_status"].values()), f2["field_status"])
raw = summary_raw("Emery")
check("C3 summary does NOT say 'confirmed by patient' for helper-checked items", "confirmed by patient" not in raw and "checked by helper" in raw and "has NOT confirmed" in raw, raw[:500])
s, j = P("emery", "POST", "/intake/attest", {})
check("C4 patient confirms the helper's answers", s == 200, (s, j))
s, f3 = P("emery", "GET", "/intake"); raw = summary_raw("Emery")
check("C5 after the patient's confirmation every field is patient-confirmed and the summary says so", all(v["patient_confirmed"] for v in f3["field_status"].values()) and "confirmed by patient" in raw, raw[:400])   # preview19 Prompt C: wording without brackets

# ======================================================== D. Home payload
print("--- D. Home payload for the six example states")
load("missing", "key"); h = home("blake"); pvb = h["pipeline"]
check("D1 waiting on records: next action is 'none' (the office owns the follow-up)", h["next_action"]["key"] == "none", h["next_action"])
rec = [t for t in pvb["tracks"] if t["key"].startswith("records:") and not t["done"]]
check("D2 ... records tracks name the outside office, the owner team and a last-verified time", rec and all(t["waiting_on"] and t["owner_team"] and t["last_verified_at"] for t in rec), rec)
check("D3 patient payload carries NO office wording (office_text stripped)", all("office_text" not in t for t in pvb["tracks"]), [sorted(t) for t in pvb["tracks"]][:1])
load("nointake", "key"); h = home("drew"); check("D4 incomplete intake: next action is the intake", h["next_action"]["key"] == "intake", h["next_action"])
load("clean", "key"); h = home("avery")
check("D5 ready to schedule: state 'ready', no appointment, nothing invented (no slots/times in the payload)", h["pipeline"]["state"] == "ready" and not h.get("next_appointment") and "slots" not in json.dumps(h), h["pipeline"]["state"])
j = load("clean", "booked"); h = home("avery")
check("D6 new seeded step clean/booked: a staff-recorded (fictional) visit; patient asked to confirm it", h["pipeline"]["state"] == "booked" and h["next_appointment"] and h["next_action"]["key"] == "confirm", (h["pipeline"]["state"], h.get("next_appointment"), h["next_action"]))
s, r = P("avery", "POST", f"/appointments/{h['next_appointment']['id']}/confirm", {}); h = home("avery")
check("D7 after confirming, nothing is needed from the patient", s == 200 and h["next_action"]["key"] == "none" and h["next_appointment"]["confirmed"], h["next_action"])
s, j = presenter("/api/presenter/scenario/load", {"key": "missing", "step": "booked"}); check("D8 'booked' step exists only for the clean scenario (422 otherwise)", s == 422, (s, j))
load("surgery", "key"); h = home("harper"); check("D9 pre-op: next action is the written-instructions acknowledgement", h["next_action"]["key"] == "preop_ack", h["next_action"])
load("surgery", "postop"); h = home("harper"); check("D10 post-op: next action is the day-2 check-in", h["next_action"]["key"] == "checkin", h["next_action"])
check("D11 surgery tracks carry no office wording for the patient either", all("office_text" not in t for t in h["pipeline"]["tracks"]), "")
load("caregiver", "key"); h = home("frankie")
check("D12 helper payload carries no office wording", all("office_text" not in t for t in h["pipeline"]["tracks"]), "")

s, j = req("GET", "/api/health")[:2]; check("server healthy at the end", s == 200, j)
srv_log = open("/tmp/api19_srv.log").read(); check("no server errors logged", "server error" not in srv_log, srv_log[-300:])
stop()
ok = sum(1 for r in RES if r[1]); print(f"\nDONE api_v19_test: {ok}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_v19_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(RES) else 1)
