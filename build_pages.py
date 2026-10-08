#!/usr/bin/env python3
"""Build the PUBLISHED static demo: preview19/publish/portal/ (for GitHub Pages at <site>/portal/).
Same screens as the prototype (portal.html, office.html, shared.css/js, portal.js, office.js) running against the in-browser mock
(snapshot_mock.js) that REPLAYS demo recordings made from the real local prototype server at build time (temp DB, fictional data,
127.0.0.1 only).  Recorded screens are read-only: actions that would save say "Demo recording: in the full version this saves to the
server" and nothing pretends to be sent.  No server code, database, tests, logs or checkpoints are copied.  Stdlib only."""
import http.client, json, os, re, shutil, signal, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import server
OUT = os.path.join(HERE, "publish", "portal"); SRC = os.path.join(HERE, "publish_src")
PORT = 8774
OFFICE_FULL = {"auth:chased", "clean@yakel", "redflag", "redflag@pat", "redflag@admin", "surgery:postop_concern@nina"}   # recordings meant for exploring the office
FILTERS = ["open", "mine", "urgent", "decisions", "referrals", "overdue", "waiting", "resolved", "all"]
INTENTS = [k for k, _ in server.ASSIST_SUGGESTED]
# slot id -> (scenario key, step, office_as, as_helper, advance event, label for the picker)
SLOTS = [
    ("clean", "clean", "key", None, False, None),
    ("clean:intake", "clean", "intake", None, False, None),
    ("clean:booked", "clean", "booked", None, False, None),
    ("clean@yakel", "clean", "key", "yakel", False, None),
    ("missing", "missing", "key", None, False, None),
    ("auth", "auth", "key", None, False, None),
    ("auth:chased", "auth", "key", None, False, {"event": "days_pass", "key": "auth"}),
    ("nointake", "nointake", "key", None, False, None),
    ("caregiver", "caregiver", "key", None, False, None),
    ("caregiver+helper", "caregiver", "key", None, True, None),
    ("notfit", "notfit", "key", None, False, None),
    ("redflag", "redflag", "key", None, False, None),
    ("redflag@pat", "redflag", "key", "pat", False, None),
    ("redflag@admin", "redflag", "key", "admin", False, None),
    ("surgery", "surgery", "key", None, False, None),
    ("surgery:postop", "surgery", "postop", None, False, None),
    ("surgery:postop_concern@nina", "surgery", "postop_concern", "nina", False, None),
]

def record():
    db = os.path.join(tempfile.mkdtemp(), "rec.db")
    pr = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py"), "--port", str(PORT), "--db", db, "--no-worker", "--reset"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    n = [0]
    def req(m, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=20); h = {"Host": f"127.0.0.1:{PORT}", "X-PS-Client": "1", "Cookie": cookie}
        if body is not None: h["Content-Type"] = "application/json"; n[0] += 1; h["Idempotency-Key"] = f"build-{n[0]}"
        c.request(m, path, json.dumps(body) if body is not None else None, h); r = c.getresponse(); b = r.read(); hd = r.getheaders(); c.close()
        return r.status, json.loads(b), hd
    try:
        for _ in range(80):
            try: req("GET", "/api/health"); break
            except Exception: time.sleep(0.1)
        req("POST", "/api/presenter/enter", {}, "")
        out = {"recorded_at": time.strftime("%b %-d, %Y %-I:%M %p PT"), "keys": {}, "recorded_day": time.strftime("%Y-%m-%d"), "banner": "Demo recording \u00b7 fictional patients \u00b7 nothing you do here is sent or saved \u00b7 not production \u00b7 not HIPAA-compliant"}
        for sid, key, step, oa, helper, adv in SLOTS:
            body = {"key": key, "step": step}
            if oa: body["office_as"] = oa
            if helper: body["as_helper"] = True
            s, j, hd = req("POST", "/api/presenter/scenario/load", body, "ps_presenter=1"); assert s == 200, (sid, s, j)
            ck = {v.split("=", 1)[0]: v.split(";")[0] for nm, v in hd if nm.lower() == "set-cookie"}
            P, O = ck["ps_portal"], ck["ps_office"]
            msg = j["message"]
            if adv:
                s2, j2, _ = req("POST", "/api/presenter/scenario/advance", adv, "ps_presenter=1"); assert s2 == 200, (sid, s2, j2); msg = j2["message"]
            got = {}
            def g(app, path, cookie):
                st, b, _ = req("GET", path, None, cookie)
                if st != 404: got[app + " " + path] = [st, b]   # refusals are real answers too (e.g. "not available yet")
                return st, b
            for path in ("/api/p/me", "/api/p/home", "/api/p/intake", "/api/p/threads", "/api/p/rules", "/api/p/helper", "/api/p/reminders"): g("portal", path, P)
            st, th, _ = req("GET", "/api/p/threads", None, P)
            for t in (th.get("threads", []) if st == 200 else []): g("portal", f"/api/p/threads/{t['id']}", P)
            for cid in range(1, 40):
                st, _, _ = req("GET", f"/api/p/content/{cid}", None, P)
                if st == 200: g("portal", f"/api/p/content/{cid}", P)
            for path in ("/api/o/me", "/api/o/staff", "/api/o/appointments/today", "/api/o/calls-avoided", "/api/o/priority-rules", "/api/o/notifications",
                         "/api/o/reports", "/api/o/audit?limit=200", "/api/o/settings", "/api/o/escalation-rules"): g("office", path, O)
            ids = set()
            full = sid in OFFICE_FULL; pid = server.SCN[key]["pid"]   # patient-first recordings carry the open list and all its items (size)
            for f in (FILTERS if full else ["open"]):   # patient-first recordings carry the office's main list only
                st, q = g("office", "/api/o/queue?filter=" + f, O)
                if st == 200:
                    ids |= {t["id"] for t in q.get("tasks", []) + q.get("pinned", []) }   # every listed item's detail opens
                    if q.get("next_up_task"): ids.add(q["next_up_task"]["id"])
            for i in sorted(ids): g("office", f"/api/o/tasks/{i}", O)
            assist = {}
            for it in INTENTS:   # the four example questions: answers computed by the real scripted assistant, from this patient's records
                st, a, _ = req("POST", "/api/p/assist", {"intent": it}, P)
                if st == 200: assist[it] = a
            st, ot = 0, None
            otr = j.get("open_task")
            out["keys"][sid] = {"get": got, "assist": assist, "message": msg, "portal_as": j["portal_as"], "office_as": j["office_as"], "open_task": otr,
                                "n": server.SCN[key]["n"], "title": server.SCN[key]["title"], "case_id": j.get("case_id")}
        # wording polish for the online demo: internal tool names read as "demo" (meaning unchanged; everything stays labelled simulated)
        SUBS = [(re.compile(r"scenario script"), "demo script"), (re.compile(r"presenter scenario shortcut"), "demo sign-in shortcut"),
                (re.compile(r"(?i)\bpresenter script\b"), "demo script"), (re.compile(r"\bpresenter\."), "demo."), (re.compile(r"\bthe presenter\b"), "the demo")]
        def polish(o):
            if isinstance(o, str):
                for rx, rep in SUBS: o = rx.sub(rep, o)
                return o
            if isinstance(o, list): return [polish(x) for x in o]
            if isinstance(o, dict): return {k: polish(v) for k, v in o.items()}
            return o
        for K in out["keys"].values():
            K["get"] = {k: [v[0], polish(v[1])] for k, v in K["get"].items()}; K["assist"] = polish(K["assist"]); K["message"] = polish(K["message"])
        blobs, index = [], {}   # store identical responses once
        for K in out["keys"].values():
            for k, v in K["get"].items():
                t = json.dumps(v[1], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                if t not in index: index[t] = len(blobs); blobs.append(v[1])
                K["get"][k] = [v[0], index[t]]
        out["blobs"] = blobs
        return out
    finally:
        pr.send_signal(signal.SIGTERM); pr.wait(10)

def main():
    REC = record()
    rules = json.dumps(server.export_rules(), ensure_ascii=False)
    mock = open(os.path.join(HERE, "snapshot_mock.js"), encoding="utf-8").read()
    mock = mock.replace("/*__RULES__*/null", rules).replace("/*__REC__*/null", json.dumps(REC, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
    if os.path.isdir(OUT): shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "assets"))
    for n in os.listdir(os.path.join(HERE, "assets")):
        if n.endswith((".png", ".webp")): shutil.copy(os.path.join(HERE, "assets", n), os.path.join(OUT, "assets", n))
    for n in ("shared.css", "shared.js", "portal.js", "office.js"): shutil.copy(os.path.join(HERE, n), os.path.join(OUT, n))
    open(os.path.join(OUT, "demo-data.js"), "w", encoding="utf-8").write("/* Demo recordings of FICTIONAL patients, made from the local prototype server on " + REC["recorded_at"] + ". No real patient data. */\n" + mock)
    GUARD = '<meta name="robots" content="noindex,nofollow">\n<script>if (window.parent === window) location.replace("./");</script>'   # these pages only run inside the demo shell
    for n in ("portal.html", "office.html"):
        h = open(os.path.join(HERE, n), encoding="utf-8").read()
        h = h.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n' + GUARD, 1)
        if n == "portal.html":   # the About sheet describes the ONLINE demo honestly (no server here)
            i = h.index("<h3>Works in this prototype</h3>"); j = h.index("</ul>", i) + 5
            h = h[:i] + ("<h3>In this online demo</h3>\n  <ul id=\"about-real\">\n    <li>The screens are recordings of the working prototype, made with fictional patients.</li>\n"
                         "    <li>Nothing you type here is sent or saved. Buttons that would save say so.</li>\n"
                         "    <li>In the full prototype, answers, messages and call-back requests are stored by the server and the office sees them as tasks.</li>\n  </ul>") + h[j:]
        open(os.path.join(OUT, n), "w", encoding="utf-8").write(h)
    for n in os.listdir(SRC):
        shutil.copy(os.path.join(SRC, n), os.path.join(OUT, n))
    tot = 0
    for root, _, fs in os.walk(OUT):
        for f in fs: tot += os.path.getsize(os.path.join(root, f))
    print("publish/portal:", tot, "bytes;", len(REC["keys"]), "recordings;", "demo-data.js", os.path.getsize(os.path.join(OUT, "demo-data.js")))
    bad = [f for f in os.listdir(OUT) if re.search(r"\.(py|db|log|sqlite)$", f)]
    assert not bad, bad

if __name__ == "__main__": main()
