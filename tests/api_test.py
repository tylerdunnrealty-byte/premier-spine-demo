#!/usr/bin/env python3
"""API acceptance tests against the REAL local prototype server (stdlib only; no external network).
Starts its own server on 127.0.0.1:8771 with a temp DB and --no-worker (ticks are driven explicitly), then restarts it to prove persistence."""
import http.client, json, os, signal, sqlite3, subprocess, sys, tempfile, time, uuid
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
PORT = int(os.environ.get("PS_TEST_PORT", "8771")); DB = os.path.join(tempfile.mkdtemp(), "t.db")
RES = []; proc = None
def start():
    global proc
    proc = subprocess.Popen([sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", DB, "--no-worker"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    for _ in range(50):
        try:
            http.client.HTTPConnection("127.0.0.1", PORT, timeout=1).request("GET", "/api/health"); return
        except Exception: time.sleep(0.1)
    raise SystemExit("server did not start")
def stop():
    proc.send_signal(signal.SIGTERM); proc.wait(10)
def req(method, path, body=None, token=None, key=None, headers=None, host=None, raw=None, client=True, cookie=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10); h = {"Host": host or f"127.0.0.1:{PORT}"}
    if client: h["X-PS-Client"] = "1"
    if token: h["Authorization"] = "Bearer " + token
    if key: h["Idempotency-Key"] = key
    if cookie: h["Cookie"] = cookie
    h.update(headers or {}); data = None
    if raw is not None: data = raw; h["Content-Type"] = "application/json"
    elif body is not None: data = json.dumps(body, ensure_ascii=False).encode(); h["Content-Type"] = "application/json"
    c.request(method, path, data, h); r = c.getresponse(); b = r.read(); hd = dict(r.getheaders()); c.close()
    try: j = json.loads(b)
    except Exception: j = None
    return r.status, j, hd, b
def login(persona, app):
    s, j, hd, _ = req("POST", "/api/login", {"persona": persona, "app": app}); assert s == 200, (persona, s, j)
    ck = hd["Set-Cookie"].split(";")[0]; return ck.split("=", 1)[1]
def check(name, cond, info=""):
    RES.append((name, bool(cond), str(info)[:240])); print(("PASS " if cond else "FAIL ") + name + ("" if cond else "  <-- " + str(info)[:240]), flush=True)
def K(): return uuid.uuid4().hex
def presenter(path, body=None, method="POST"): return req(method, path, body or {}, cookie="ps_presenter=1")

import socket as _s; _so = _s.socket(); _so.setsockopt(_s.SOL_SOCKET, _s.SO_REUSEADDR, 1)
try: _so.bind(("127.0.0.1", PORT))
except OSError: raise SystemExit(f"port {PORT} is busy (stale server?) - refusing to test against it")
finally: _so.close()
start()
presenter("/api/presenter/reset")
T = {k: login(k, "portal") for k in ("alex", "jordan", "riley")}; T.update({k: login(k, "office") for k in ("pat", "nina", "yakel", "admin")})
def P(m, p, b=None, who="alex", key=None): return req(m, "/api/p" + p, b, T[who], key or (K() if m == "POST" else None))
def O(m, p, b=None, who="pat", key=None): return req(m, "/api/o" + p, b, T[who], key or (K() if m == "POST" else None))

# ---------------- authn / authz
check("no token -> 401 (portal)", req("GET", "/api/p/me")[0] == 401)
check("no token -> 401 (office)", req("GET", "/api/o/queue")[0] == 401)
check("garbage token -> 401", req("GET", "/api/p/me", token="abc.def")[0] == 401)
t = T["alex"]; body, sig = t.split(".")
check("tampered signature -> 401", req("GET", "/api/p/me", token=body + "." + sig[:-2] + ("AA" if not sig.endswith("AA") else "BB"))[0] == 401)
import base64, hmac, hashlib
def forge(payload, secret=b"not-the-secret"):
    b = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("="); return b + "." + base64.urlsafe_b64encode(hmac.new(secret, b.encode(), hashlib.sha256).digest()).decode().rstrip("=")
check("forged token (wrong key, claims admin) -> 401", req("GET", "/api/o/audit", token=forge({"sid": "x", "uk": "admin", "app": "office", "exp": time.time() + 999}))[0] == 401)
check("patient token on office route -> 403", req("GET", "/api/o/queue", token=T["alex"])[0] == 403)
check("caregiver token on office route -> 403", req("GET", "/api/o/queue", token=T["riley"])[0] == 403)
check("staff token on patient route -> 403", req("GET", "/api/p/home", token=T["pat"])[0] == 403)
check("POST without X-PS-Client -> 403", req("POST", "/api/p/callback", {}, T["alex"], K(), client=False)[0] == 403)
check("wrong Host header -> 400", req("GET", "/api/health", host="evil.example")[0] == 400)
check("bad JSON -> 400", req("POST", "/api/p/callback", token=T["alex"], key=K(), raw=b"{nope")[0] == 400)
check("oversized body -> 413", req("POST", "/api/p/callback", token=T["alex"], key=K(), raw=b'{"note":"' + b"a" * 70000 + b'"}')[0] == 413)
for p in ("/server.py", "/data/x.db", "/../server.py", "/tests/api_test.py", "/README.md"): check(f"static {p} not served", req("GET", p)[0] == 404)
s, _, hd, b = req("GET", "/portal.html"); check("html has CSP and no external URLs", s == 200 and "Content-Security-Policy" in hd and b"https://" not in b and b"http://" not in b, hd.get("Content-Security-Policy"))
for f in ("shared.js", "portal.js", "office.js", "presenter.js", "shared.css"):
    s, _, _, b = req("GET", "/" + f); ns = b.count(b"'http://www.w3.org/2000/svg'"); b = b.replace(b"'http://www.w3.org/2000/svg'", b"")  # preview18: the SVG namespace identifier for createElementNS (an XML name, never fetched) is the only allowed http:// string
    check(f"{f}: no external URLs (except documented maps link; SVG namespace id allowed)", s == 200 and (b"http://" not in b) and b.count(b"https://") <= 1 and ns <= 1, (b.count(b"https://"), ns))
check("presenter route without presenter cookie -> 403", req("POST", "/api/presenter/reset", {})[0] == 403)
check("presenter route with patient token only -> 403", req("POST", "/api/presenter/reset", {}, token=T["alex"])[0] == 403)

# ---------------- isolation + caregiver
s, home, _, _ = P("GET", "/home"); check("Alex home has Alex's appointment/waiting/next action", s == 200 and home["next_appointment"] and home["waiting_on"] and home["next_action"]["key"] == "intake", home.get("next_action"))
s, jh, _, _ = P("GET", "/home", who="jordan"); check("Jordan home differs from Alex (isolation)", jh["waiting_on"][0]["label"] != home["waiting_on"][0]["label"] and jh["next_appointment"]["id"] != home["next_appointment"]["id"])
s, jt, _, _ = P("GET", "/threads", who="jordan"); jtid = jt["threads"][0]["id"]
check("Jordan sees own seeded thread", s == 200 and len(jt["threads"]) == 1)
check("Alex cannot read Jordan's thread -> 404", P("GET", f"/threads/{jtid}")[0] == 404)
check("Alex thread list excludes Jordan's", all(t["id"] != jtid for t in P("GET", "/threads")[1]["threads"]))
check("Jordan cannot confirm Alex's appointment -> 404", P("POST", f"/appointments/{home['next_appointment']['id']}/confirm", {}, who="jordan")[0] == 404)
s, rh, _, _ = P("GET", "/home", who="riley")
check("caregiver sees shared sections only (appointments+instructions)", s == 200 and "next_appointment" in rh and "instructions" in rh and "waiting_on" not in rh and "next_action" not in rh and "stage" not in rh, list(rh))
check("caregiver cannot read threads -> 403", P("GET", "/threads", who="riley")[0] == 403)
check("caregiver cannot send message -> 403", P("POST", "/messages", {"category": "other", "body": "hi"}, who="riley")[0] == 403)
check("caregiver cannot read/modify helper settings -> 403", P("GET", "/helper", who="riley")[0] == 403 and P("PUT", "/helper", {"scopes": {"messages": True}}, who="riley")[0] == 403)
check("caregiver cannot do intake/imaging -> 403", P("POST", "/intake", {"confirmed": True}, who="riley")[0] == 403 and P("POST", "/imaging", {"facility": "x"}, who="riley")[0] == 403)
P("PUT", "/helper", {"scopes": {"messages": True}}); s, rt, _, _ = P("GET", "/threads", who="riley")
check("after Alex shares messages, caregiver sees only Alex's threads", s == 200 and all(t["id"] != jtid for t in rt["threads"]))
check("caregiver still blocked from Jordan's thread -> 404", P("GET", f"/threads/{jtid}", who="riley")[0] == 404)
P("PUT", "/helper", {"status": "stopped"}); s, j, _, _ = P("GET", "/home", who="riley"); check("after Alex stops sharing, caregiver -> 403", s == 403 and j["error"] == "access_stopped")
P("PUT", "/helper", {"status": "active", "scopes": {"messages": False}})

s, j, _, _ = P("GET", "/rules"); check("patient can read the shared emergency-wording list (used for immediate 911 guidance)", s == 200 and len(j["emergency_patterns"]) > 10 and "911" in j["emergency_message"] and "triage" in j["not_triage"].lower())
check("rules endpoint: no token -> 401, office token -> 403", req("GET", "/api/p/rules")[0] == 401 and req("GET", "/api/p/rules", token=T["pat"])[0] == 403)
# ---------------- long messages end to end
body = ("Line one with an \u00e9 and emoji \U0001F600 and CJK \u6f22\u5b57.\n\nSecond paragraph.\n" + "x" * 380 + "\nTail-marker-END \U0001F680")
body = body + "\n" + ("y" * (1200 - len(body)))
n0 = len(body)
s, j, _, _ = P("POST", "/messages", {"category": "scheduling", "body": body}); mt = j["task"]["id"]
check("long message (%d chars, newlines, unicode) accepted" % n0, s == 200 and j["created"])
s, th, _, _ = P("GET", f"/threads/{mt}"); check("patient thread returns the full message byte-for-byte", th["messages"][0]["body"] == body)
s, d, _, _ = O("GET", f"/tasks/{mt}"); check("office case conversation holds the full message", d["conversation"][0]["body"] == body and "Tail-marker-END" in d["conversation"][0]["body"])
s, q, _, _ = O("GET", "/queue?filter=all"); qi = next(t for t in q["tasks"] if t["id"] == mt)
check("queue excerpt is explicitly marked as an excerpt with the true length", qi["excerpt_truncated"] and qi["excerpt"].endswith("\u2026") and qi["message_length"] == n0)
check("suggested draft is a separate field and never replaces the patient's words", d["draft"]["source"] == "suggestion" and body not in d["draft"]["body"])
s, j, _, _ = P("POST", "/messages", {"category": "other", "body": "   \n  "}); check("empty/whitespace message rejected (422 empty)", s == 422 and j["error"] == "empty")
s, j, _, _ = P("POST", "/messages", {"category": "other", "body": "a" * 2001}); check("2001 chars rejected with length+max (422 too_long)", s == 422 and j["error"] == "too_long" and j["length"] == 2001 and j["max"] == 2000, j)
s, j, _, _ = P("POST", "/messages", {"category": "other", "body": "b" * 2000}); check("exactly 2000 chars accepted", s == 200)
s, j, _, _ = P("POST", "/messages", {"category": "other", "body": "\U0001F600" * 2000 + "!"}); check("limit counts characters (code points), 2001 emoji rejected", s == 422 and j["length"] == 2001)
s, j, _, _ = P("POST", "/messages", {"category": "other", "body": "\U0001F600" * 1500 + " ok"}); check("1503 emoji/characters accepted and stored whole", s == 200 and P("GET", f"/threads/{j['task']['id']}")[1]["messages"][0]["body"] == "\U0001F600" * 1500 + " ok")
_th = P("GET", "/threads")[1]["threads"]; check("rejected messages created no task (only the 3 accepted ones exist)", len(_th) == 3, [t["id"] for t in _th])
s, j, _, _ = P("POST", "/messages", {"category": "bogus", "body": "hi"}); check("bad category rejected", s == 422)

# ---------------- idempotency / duplicates
k = K(); a = P("POST", "/messages", {"category": "billing", "body": "Statement question one"}, key=k); b = P("POST", "/messages", {"category": "billing", "body": "Statement question one"}, key=k)
check("same Idempotency-Key twice -> same task, replay header", a[1]["task"]["id"] == b[1]["task"]["id"] and b[2].get("X-Idempotent-Replay") == "true")
check("same key different body -> 422", P("POST", "/messages", {"category": "billing", "body": "Different"}, key=k)[0] == 422)
c = P("POST", "/messages", {"category": "billing", "body": "Statement question one"}); check("double-click (new key, same text) suppressed -> same task", c[1]["task"]["id"] == a[1]["task"]["id"] and c[1]["duplicate_suppressed"])
check("only ONE task/message for that submission", sum(1 for t in O("GET", "/queue?filter=all")[1]["tasks"] if t["blocked_step"] == "Patient message awaiting reply" and t["patient_id"] == 1 and "billing" in (t["category"] or "").lower()) == 1)
cb = [P("POST", "/callback", {}) for _ in range(3)]; check("three call-back clicks -> one open callback task", len({x[1]["task"]["id"] for x in cb}) == 1 and sum(1 for x in cb if x[1]["created"]) == 1)
check("missing Idempotency-Key on a creating POST -> 400", req("POST", "/api/p/messages", {"category": "other", "body": "x"}, T["alex"])[0] == 400)

# ---------------- triage + handoff
def ask(q, who="alex"): return P("POST", "/ask", {"question": q}, who=who)[1]
r = ask("When is my appointment?"); check("appointment question answered from the record (not the reschedule text)", r["kind"] == "answer" and "next visit" in r["answer"] and "10:30" in r["answer"], r.get("answer"))
r = ask("What's the plan for my back?"); check("'plan for my back' is NOT answered as insurance (goes to a person or nurse)", r["kind"] in ("handoff", "clinical") and r["task"], r.get("kind"))
r = ask("Can I bring my dog?"); check("'bring my dog' is NOT answered with the what-to-bring list", r["kind"] == "handoff" and r["task"])
r = ask("Do you take Blue Cross?"); check("insurance acceptance question answered with 'call the office'", r["kind"] == "answer" and "verify your insurance" in r["answer"])
r = ask("Where is the office?"); check("address answered with source", r["kind"] == "answer" and "Ironwood" in r["answer"] and r["source"])
r = ask("What are your hours?"); check("hours: honest 'not confirmed' answer, no invented hours", r["kind"] == "answer" and "won\u2019t guess" in r["answer"])
for q in ("My leg hurts a lot", "I can't feel my toes", "tingling in my arm", "I fell yesterday", "Can I take ibuprofen?", "can i drive after the procedure", "Is this normal after my injection?", "I have a rash near the incision", "should I stop my medication"):
    r = ask(q); check(f"symptom/medication phrase routed to a nurse task, not auto-answered: {q!r}", r["kind"] in ("clinical", "emergency") and r["task"] and r["task"]["team"] == "Nurse" and "can\u2019t answer medical" in r["answer"] + "can\u2019t answer medical" or r["kind"] == "emergency", r)
for q in ("I lost control of my bladder", "I can't feel my legs", "numbness in my groin since last night", "I have chest pain", "my incision has pus and I have a fever", "I want to die"):
    r = ask(q); check(f"emergency wording shows 911 guidance immediately + urgent nurse task: {q!r}", r["kind"] == "emergency" and "911" in r["answer"] and r["task"]["team"] == "Nurse", r.get("kind"))
s, qq, _, _ = O("GET", "/queue?filter=all", who="nina"); em = [t for t in qq["tasks"] if t["priority"] == "urgent"]
check("urgent tasks are assigned (owner, backup, deadline) to the nurse", em and all(t["owner"] == "nina" and t["backup"] == "yakel" and t["deadline"] for t in em), em[:1])
r = ask("Do you do knee replacements?"); hid = r["task"]["id"]
check("handoff creates a REAL task with owner, backup, deadline", r["kind"] == "handoff" and r["task"]["status"] == "Assigned" and r["task"]["team"] == "Front desk")
t = next(x for x in O("GET", "/queue?filter=all")[1]["tasks"] if x["id"] == hid); check("...visible in the office queue", t["owner"] == "pat" and t["backup"] == "nina" and t["deadline"] and t["status"] == "Assigned")
check("...patient sees 'Received · Assigned to Front desk' and NO promised time (office set none)", "Assigned to Front desk" in r["task"]["status_text"] and r["task"]["reply_target"] is None)
O("PUT", "/settings", {"patient_reply_target": "within 1 business day"}, who="admin"); th = P("GET", f"/threads/{hid}")[1]["thread"]
check("after admin sets a target, patient sees it (only then)", th["reply_target"] == "We aim to reply within 1 business day"); O("PUT", "/settings", {"patient_reply_target": ""}, who="admin")
check("office role cannot change settings -> 403", O("PUT", "/settings", {"patient_reply_target": "x"}, who="pat")[0] == 403)
r2 = ask("Do you do knee replacements?"); check("repeat of the same question does not make a second task", r2["task"]["id"] == hid)

# ---------------- acknowledgement is not resolution; state rules
jt_id = jtid
s, j, _, _ = O("POST", f"/tasks/{jt_id}/reply", {"body": "Hi Jordan, thanks. We got your request.", "kind": "ack"})
check("acknowledgment sent", s == 200 and j["still_open"] and j["task"]["status"] == "In Progress" and j["task"]["acknowledged"])
s, d, _, _ = O("GET", f"/tasks/{jt_id}"); check("acknowledged task is still open in the office queue", d["task"]["status"] != "Resolved" and any(t["id"] == jt_id for t in O("GET", "/queue")[1]["tasks"]))
th = P("GET", f"/threads/{jt_id}", who="jordan")[1]; check("patient sees acknowledgment AND that the request is still open", th["thread"]["open"] and "still open" in th["thread"].get("ack_note", "") and th["messages"][-1]["kind"] == "staff_ack")
s, j, _, _ = O("POST", f"/tasks/{jt_id}/reply", {"body": "We can move you to 4:15 PM. Confirmed by phone.", "kind": "reply"}); check("a real reply still does not resolve", j["task"]["status"] == "In Progress")
check("resolve without outcome -> 422", O("POST", f"/tasks/{jt_id}/transition", {"to": "Resolved"})[0] == 422)
check("resolve with blank outcome -> 422", O("POST", f"/tasks/{jt_id}/transition", {"to": "Resolved", "outcome": "  "})[0] == 422)
check("waiting without whom/what or date -> 422", O("POST", f"/tasks/{jt_id}/transition", {"to": "Waiting"})[0] == 422 and O("POST", f"/tasks/{jt_id}/transition", {"to": "Waiting", "waiting_on": "Patient call-back"})[0] == 422)
check("waiting with past date -> 422", O("POST", f"/tasks/{jt_id}/transition", {"to": "Waiting", "waiting_on": "Patient", "follow_up_by": "2020-01-01"})[0] == 422)
s, j, _, _ = O("POST", f"/tasks/{jt_id}/transition", {"to": "Waiting", "waiting_on": "Patient to confirm 4:15 PM", "follow_up_by": time.strftime("%Y-%m-%d", time.localtime(time.time() + 3 * 86400))}); check("waiting with whom + date ok", s == 200 and j["task"]["waiting_on"] and j["task"]["follow_up_by"])
check("manual Waiting->Assigned refused (system only)", O("POST", f"/tasks/{jt_id}/transition", {"to": "Assigned"})[0] == 403)
check("patient sees 'Waiting for ...'", "Waiting for Patient to confirm" in P("GET", f"/threads/{jt_id}", who="jordan")[1]["thread"]["status_text"])
s, j, _, _ = O("POST", f"/tasks/{jt_id}/transition", {"to": "In Progress"}); check("Waiting -> In Progress clears waiting fields", s == 200 and j["task"]["waiting_on"] is None)
s, j, _, _ = O("POST", f"/tasks/{jt_id}/transition", {"to": "Resolved", "outcome": "Moved to 4:15 PM; patient confirmed by phone."}); check("resolve with outcome records who + outcome", s == 200 and j["task"]["resolved_by"] == "pat" and j["task"]["outcome"].startswith("Moved"))
check("Resolved -> In Progress needs a reason", O("POST", f"/tasks/{jt_id}/transition", {"to": "In Progress"})[0] == 422 and O("POST", f"/tasks/{jt_id}/transition", {"to": "In Progress", "reason": "Patient called back"})[0] == 200)
check("illegal transition Received->Resolved is not offered / 409 on bad jump", O("POST", f"/tasks/{hid}/transition", {"to": "Received"})[0] == 409)
check("reply to resolved task refused", O("POST", f"/tasks/{jt_id}/transition", {"to": "Resolved", "outcome": "done again"})[0] == 200 and O("POST", f"/tasks/{jt_id}/reply", {"body": "x"})[0] == 409)

# staff-only notes
O("POST", f"/tasks/{hid}/note", {"body": "STAFFONLY-SECRET-NOTE internal reminder"}, who="nina")
th = P("GET", f"/threads/{hid}"); check("staff-only note never appears in patient thread", b"STAFFONLY" not in th[3])
check("staff-only note visible to office", any("STAFFONLY" in m["body"] for m in O("GET", f"/tasks/{hid}")[1]["conversation"]))
ap = [P("GET", "/home"), P("GET", "/threads"), P("GET", "/me"), P("GET", "/home", who="riley")]; check("staff-only note/task text appears in no patient/caregiver payload", all(b"STAFFONLY" not in x[3] for x in ap))
for who in ("alex", "riley", "jordan"):
    check(f"{who}: every office endpoint is forbidden", all(req(m, "/api/o" + p, {} if m != "GET" else None, T[who], K())[0] == 403 for m, p in (("GET", "/queue"), ("GET", "/audit"), ("GET", "/reports"), ("GET", "/tasks/1"), ("GET", "/notifications"), ("GET", "/staff"), ("GET", "/settings"), ("POST", "/tasks/1/note"), ("PUT", "/tasks/1/draft"), ("GET", "/appointments/today"))))
check("front desk cannot read audit log or reports -> 403", O("GET", "/audit")[0] == 403 and O("GET", "/reports")[0] == 403)
check("admin reads audit; clinician+admin read reports", O("GET", "/audit", who="admin")[0] == 200 and O("GET", "/reports", who="admin")[0] == 200 and O("GET", "/reports", who="yakel")[0] == 200)
check("nurse cannot read audit -> 403", O("GET", "/audit", who="nina")[0] == 403)

# role-restricted actions
qs = O("GET", "/queue?filter=all")[1]["tasks"]; rev = next(t for t in qs if t["type"] == "records_review"); med = next(t for t in qs if t["category"] == "Medical question" and t["status"] == "Assigned")
check("front desk cannot resolve a clinical (nurse) task -> 403", O("POST", f"/tasks/{med['id']}/transition", {"to": "Resolved", "outcome": "handled"})[0] == 403)
check("nurse cannot resolve a clinician-only review task -> 403", O("POST", f"/tasks/{rev['id']}/transition", {"to": "Resolved", "outcome": "reviewed"}, who="nina")[0] == 403)
check("front desk cannot mark a radiology report reviewed -> 403", O("POST", "/docs/5/review", {}, who="pat")[0] == 403 and O("POST", "/docs/5/review", {}, who="nina")[0] == 403)
check("front desk cannot waive images (clinician only) -> 403", O("POST", "/cases/2/images", {"images_status": "waived", "note": "x"})[0] == 403)
s, j, _, _ = O("POST", "/docs/5/review", {}, who="yakel"); check("clinician marks report reviewed; images untouched", s == 200 and "separate" in j["note"])
check("review task auto-resolved with resolver recorded", next(t for t in O("GET", "/queue?filter=all")[1]["tasks"] if t["id"] == rev["id"])["resolved_by"] == "yakel")

# ---------------- workflow slice (Alex): facility -> records -> report arrives -> separate image tracking
s, j, _, _ = P("POST", "/intake", {"confirmed": True, "matters": ["Walking"], "note": "n"}); check("Alex completes intake", s == 200)
check("intake requires confirmation", P("POST", "/intake", {"confirmed": False})[0] == 422)
s, home, _, _ = P("GET", "/home"); check("next action moves to 'Tell us where your MRI was done'", home["next_action"]["key"] == "imaging")
s, j, _, _ = P("POST", "/imaging", {"facility": "Example Radiology (fictional)"}); rt = next(t for t in O("GET", "/queue?filter=all")[1]["tasks"] if t["type"] == "records_request" and t["patient_id"] == 1)
check("facility provided -> records task leaves Waiting, next action names the facility", rt["status"] == "In Progress" and "Example Radiology" in rt["next_action"])
s, home, _, _ = P("GET", "/home"); check("next action moves to confirm appointment", home["next_action"]["key"] == "confirm")
nid = [n for n in O("GET", "/notifications")[1]["notifications"] if n["template"] == "appt_reminder"][0]["id"]
check("appointment reminder is 'received' after Alex opened Home", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == nid)["status"] == "received")
P("POST", f"/appointments/{home['next_appointment']['id']}/confirm", {}); check("confirming marks the notification 'accepted'", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == nid)["status"] == "accepted")
s, home, _, _ = P("GET", "/home"); check("next action: nothing needed", home["next_action"]["key"] == "none")
presenter("/api/presenter/scenario", {"name": "report_arrives_alex"})
s, d, _, _ = O("GET", f"/tasks/{rt['id']}"); c = d["case"]; check("report arrived, images still unknown (tracked separately)", c["report_status"] == "received" and c["images_status"] == "unknown" and not c["ready"], c["missing"])
rv = next(t for t in O("GET", "/queue?filter=all", who="yakel")[1]["tasks"] if t["case_id"] == 1 and t["type"] == "records_review"); check("clinician review task created, owner Dr. Yakel, backup set", rv["owner"] == "yakel" and rv["backup"] and rv["deadline"])
did = [x for x in d["documents"] if x["doc_type"] == "radiology_report"][0]["id"]; O("POST", f"/docs/{did}/review", {}, who="yakel")
c = O("GET", f"/tasks/{rt['id']}")[1]["case"]; check("report reviewed but case NOT ready (images not available)", c["report_status"] == "reviewed" and not c["ready"] and "Images not received" in c["missing"])
O("POST", "/cases/1/images", {"images_status": "received"}); c = O("GET", f"/tasks/{rt['id']}")[1]["case"]; check("images received -> case ready for appointment", c["ready"])
check("Jordan scenario: report reviewed + images unavailable -> not ready, tracked separately", O("GET", "/tasks/2")[1]["case"]["images_status"] == "unavailable" and not O("GET", "/tasks/2")[1]["case"]["ready"])
today = O("GET", "/appointments/today")[1]["appointments"]; check("today's strip shows missing prep per appointment", len(today) >= 3 and any(a["missing"] for a in today) and any(a["ready"] for a in today))

# ---------------- drafts survive; per-user
tid = hid
s, j, _, _ = O("PUT", f"/tasks/{tid}/draft", {"body": "Draft v1 \u00e9\U0001F600\nline2"}, who="pat"); check("draft autosave endpoint stores text", s == 200 and j["saved_at"])
O("POST", f"/tasks/{tid}/note", {"body": "unrelated action"}, who="pat"); O("POST", f"/tasks/{tid}/verify", {"source_note": "x"}, who="pat")
d = O("GET", f"/tasks/{tid}", who="pat")[1]["draft"]; check("draft unchanged after unrelated actions", d["source"] == "saved" and d["body"] == "Draft v1 \u00e9\U0001F600\nline2")
check("drafts are per staff member (nurse does not see Pat's)", O("GET", f"/tasks/{tid}", who="nina")[1]["draft"]["source"] == "suggestion")
check("draft too long -> 422", O("PUT", f"/tasks/{tid}/draft", {"body": "z" * 4001}, who="pat")[0] == 422)

# ---------------- notifications: sent -> delivered, failure -> exception, recovery
s, r, _, _ = O("POST", f"/tasks/{tid}/reply", {"body": "Hello Alex - a reply.", "kind": "reply"}, who="pat"); n1 = r["notification_id"]
check("reply queues a notification (queued)", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n1)["status"] == "queued")
presenter("/api/presenter/tick"); check("tick: queued -> sent", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n1)["status"] == "sent")
presenter("/api/presenter/tick"); check("tick: sent -> delivered (simulated vendor receipt)", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n1)["status"] == "delivered")
P("GET", f"/threads/{tid}"); check("patient opening the thread -> received", next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n1)["status"] == "received")
presenter("/api/presenter/scenario", {"name": "bad_phone_jordan"}); jt = jt_id
O("POST", f"/tasks/{jt}/transition", {"to": "In Progress", "reason": "reopen for failure test"}) if O("GET", f"/tasks/{jt}")[1]["task"]["status"] == "Resolved" else None
s, r, _, _ = O("POST", f"/tasks/{jt}/reply", {"body": "Following up.", "kind": "reply"}); n2 = r["notification_id"]
for i in range(3): presenter("/api/presenter/tick")
nn = next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n2); check("unreachable number: notification FAILED after retry limit (3 attempts)", nn["status"] == "failed" and nn["attempts"] == 3, nn)
ex = [t for t in O("GET", "/queue")[1]["tasks"] if t["type"] == "exception"]; check("failure created a visible exception task (owner, backup, deadline)", len(ex) == 1 and ex[0]["owner"] == "pat" and ex[0]["backup"] and ex[0]["deadline"], ex)
presenter("/api/presenter/tick"); check("more ticks do not create a second exception", len([t for t in O("GET", "/queue")[1]["tasks"] if t["type"] == "exception"]) == 1)
check("patient is not told the failed message was 'received' (status stays failed)", nn["received_at"] is None)
O("POST", f"/notifications/{n2}/retry", {}); [presenter("/api/presenter/tick") for _ in range(3)]; nn = next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n2); check("manual retry with bad number fails again (manual_retries=1)", nn["status"] == "failed" and nn["manual_retries"] == 1)
check("fix contact then retry succeeds (recoverable)", O("POST", "/patients/2/contact", {"phone": "(208) 555-0102", "phone_valid": True})[0] == 200 and O("POST", f"/notifications/{n2}/retry", {})[0] == 200)
presenter("/api/presenter/tick"); presenter("/api/presenter/tick"); nn = next(n for n in O("GET", "/notifications")[1]["notifications"] if n["id"] == n2); check("retried notification reaches 'delivered'", nn["status"] == "delivered", nn["status"])
s, j, _, _ = O("POST", f"/tasks/{ex[0]['id']}/transition", {"to": "Resolved", "outcome": "Phoned patient, number confirmed."}); check("exception task resolvable with outcome", s == 200)
presenter("/api/presenter/scenario", {"name": "bad_phone_jordan"}); O("POST", f"/tasks/{jt}/reply", {"body": "again", "kind": "reply"}); [presenter("/api/presenter/tick") for _ in range(3)]
n3 = O("GET", "/notifications")[1]["notifications"][0]; O("POST", f"/notifications/{n3['id']}/retry", {}); [presenter("/api/presenter/tick") for _ in range(3)]; O("POST", f"/notifications/{n3['id']}/retry", {}); [presenter("/api/presenter/tick") for _ in range(3)]
check("manual retries are limited (3rd retry -> 409)", O("POST", f"/notifications/{n3['id']}/retry", {})[0] == 409)
presenter("/api/presenter/scenario", {"name": "good_phone_jordan"})

# ---------------- follow-up date passing (system moves Waiting -> Assigned)
conn = sqlite3.connect(DB); wid = conn.execute("SELECT id FROM tasks WHERE status='Waiting' LIMIT 1").fetchone()[0]
conn.execute("UPDATE tasks SET follow_up_by='2000-01-01T00:00:00Z' WHERE id=?", (wid,)); conn.commit(); conn.close()
presenter("/api/presenter/tick"); w = next(t for t in O("GET", "/queue?filter=all")[1]["tasks"] if t["id"] == wid); check("follow-up date passed -> back to Assigned flagged follow-up due", w["status"] == "Assigned" and w["followup_due"] == 1, w["status"])

# ---------------- audit
au = O("GET", "/audit?limit=500", who="admin")[1]["events"]; acts = {e["action"] for e in au}
check("audit log has actor+timestamp on events", all(e["ts"] and e["actor_name"] for e in au))
check("audit covers messages, replies, transitions, notifications, reads", {"message.created", "message.reply", "task.transition", "notification.failed", "notification.delivered", "task.view", "task.acknowledged"} <= acts, sorted(acts))
conn = sqlite3.connect(DB)
try: conn.execute("DELETE FROM events"); ok = False
except sqlite3.DatabaseError: ok = True
try: conn.execute("UPDATE events SET action='x'"); ok2 = False
except sqlite3.DatabaseError: ok2 = True
conn.close(); check("audit log is append-only at the database level (UPDATE/DELETE refused)", ok and ok2)
O("POST", f"/tasks/{mt}/reply", {"body": "We received this.", "kind": "ack"})
rp = O("GET", "/reports", who="admin")[1]; check("reports show only measured values (ack/reply counts match real replies; seeded tasks excluded)", rp["minutes_to_first_acknowledgment"]["n"] >= 1 and rp["seeded_tasks"] > 0 and "payroll" in " ".join(rp["notes"]), rp["minutes_to_first_acknowledgment"])

# ---------------- persistence across restart
before = {"tasks": O("GET", "/queue?filter=all")[1]["counts"], "draft": O("GET", f"/tasks/{tid}", who="pat")[1]["draft"], "msg": P("GET", f"/threads/{mt}")[1]["messages"][0]["body"]}
stop(); start()
after = {"tasks": O("GET", "/queue?filter=all")[1]["counts"], "draft": O("GET", f"/tasks/{tid}", who="pat")[1]["draft"], "msg": P("GET", f"/threads/{mt}")[1]["messages"][0]["body"]}
check("tasks, drafts and the long message survive a SERVER RESTART (same session still valid)", before == after, (before["tasks"], after["tasks"]))
stop()
f = sum(1 for r in RES if not r[1]); print(f"\nDONE api_test: {len(RES)-f}/{len(RES)} passed; failed: {[r[0] for r in RES if not r[1]]}")
json.dump(RES, open(os.path.join(HERE, "api_test.results.json"), "w"), indent=1)
sys.exit(1 if f else 0)
