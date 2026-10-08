#!/usr/bin/env python3
"""Build preview16/snapshot.html: ONE static file that runs the portal, office workspace and presenter pages in the browser against
an in-browser JS mock of the API (snapshot_mock.js) seeded with fictional data.  Rules come from server.export_rules() so they cannot drift silently.
No network, no server.  Stdlib only."""
import base64, http.client, json, os, re, signal, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import server

def rd(n): return open(os.path.join(HERE, n), encoding="utf-8").read()
def data_uri(n):
    ext = n.rsplit(".", 1)[1]; mime = {"png": "image/png", "webp": "image/webp"}[ext]
    return f"data:{mime};base64," + base64.b64encode(open(os.path.join(HERE, "assets", n), "rb").read()).decode()
ASSETS = {n: data_uri(n) for n in os.listdir(os.path.join(HERE, "assets")) if n.endswith((".png", ".webp"))}
def inline_assets(t):
    for n, u in ASSETS.items(): t = t.replace("assets/" + n, u)
    return t

CSS = rd("shared.css"); SHARED = rd("shared.js")
def page(html_name, js_name):
    h = rd(html_name)
    h = re.sub(r'<link rel="stylesheet" href="shared.css">', lambda m: "<style>\n" + CSS + "\n</style>", h)
    h = re.sub(r'<script src="shared.js"></script>', lambda m: "<script>\n" + SHARED + "\n</script>", h)
    h = re.sub(r'<script src="%s"></script>' % re.escape(js_name), lambda m: "<script>\n" + inline_assets(rd(js_name)) + "\n</script>", h)
    h = re.sub(r'<a class="hbtn" href="(portal|office)\.html">[^<]*</a>\s*', "", h)   # presenter header links do not apply inside the snapshot
    return inline_assets(h)
DOCS = {"portal": page("portal.html", "portal.js"), "office": page("office.html", "office.js"), "presenter": page("presenter.html", "presenter.js")}
rules = json.dumps(server.export_rules(), ensure_ascii=False)

# ---- Pass 2: RECORD each referral scenario's key state from the REAL server (temp DB, 127.0.0.1 only), so the snapshot can replay
#      exactly what the server returned.  Replayed screens are read-only: actions need the local server.
REC_PORT = 8775
FILTERS = ["open", "mine", "urgent", "decisions", "referrals", "overdue", "waiting", "resolved", "all"]
def record():
    db = os.path.join(tempfile.mkdtemp(), "rec.db")
    pr = subprocess.Popen([sys.executable, os.path.join(HERE, "server.py"), "--port", str(REC_PORT), "--db", db, "--no-worker", "--reset"], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    def req(m, path, body=None, cookie=""):
        c = http.client.HTTPConnection("127.0.0.1", REC_PORT, timeout=15); h = {"Host": f"127.0.0.1:{REC_PORT}", "X-PS-Client": "1", "Cookie": cookie}
        if body is not None: h["Content-Type"] = "application/json"
        c.request(m, path, json.dumps(body) if body is not None else None, h); r = c.getresponse(); b = r.read(); hd = r.getheaders(); c.close()
        return r.status, json.loads(b), hd
    try:
        for _ in range(60):
            try: req("GET", "/api/health"); break
            except Exception: time.sleep(0.1)
        out = {"recorded_at": time.strftime("%b %-d, %Y %-I:%M %p PT"), "scenarios": None, "keys": {}}
        for sc in server.SCENARIOS:
            k = sc["key"]; s, j, hd = req("POST", "/api/presenter/scenario/load", {"key": k, "step": "key"}, "ps_presenter=1"); assert s == 200, (k, s, j)
            ck = {v.split("=", 1)[0]: v.split(";")[0] for n, v in hd if n.lower() == "set-cookie"}
            P, O = ck["ps_portal"], ck["ps_office"]; got = {}
            def g(app, path, cookie):
                st, body, _ = req("GET", path, None, cookie); got[app + " " + path] = [st, body]; return st, body
            for path in ("/api/p/me", "/api/p/home", "/api/p/intake", "/api/p/threads", "/api/p/rules", "/api/p/helper"): g("portal", path, P)
            for path in ("/api/o/me", "/api/o/staff", "/api/o/appointments/today", "/api/o/calls-avoided"): g("office", path, O)
            ids = set()
            for f in FILTERS:
                st, q = g("office", "/api/o/queue?filter=" + f, O)
                ids |= {t["id"] for t in q.get("tasks", []) if t["patient_id"] == sc["pid"]}
            for i in sorted(ids): g("office", f"/api/o/tasks/{i}", O)
            out["keys"][k] = {"get": got, "message": j["message"] + " (recorded from the local server; read-only here)", "portal_as": j["portal_as"], "office_as": j["office_as"], "n": sc["n"], "title": sc["title"]}
        out["scenarios"] = req("GET", "/api/presenter/scenarios", None, "ps_presenter=1")[1]["scenarios"]
        return out
    finally:
        pr.send_signal(signal.SIGTERM); pr.wait(10)
REC = record()
mock = inline_assets(rd("snapshot_mock.js")).replace("/*__RULES__*/null", rules).replace("/*__REC__*/null", json.dumps(REC, ensure_ascii=False).replace("</", "<\\/"))
docs_js = "var DOCS=" + json.dumps(DOCS, ensure_ascii=False).replace("</", "<\\/") + ";"
BANNER = "Static snapshot \u2014 server rules simulated in browser \u00b7 fictional data \u00b7 not production \u00b7 not HIPAA-compliant"
OUT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DEMO · Premier Spine portal + office — STATIC SNAPSHOT (prototype)</title>
<style>
%(css)s
.tabs{display:flex;flex-wrap:wrap;gap:4px;padding:4px;margin:12px 0;background:var(--fill);border-radius:24px;width:fit-content;max-width:100%%}
.tabs button{min-height:44px;padding:8px 16px;border-radius:999px;border:0;background:transparent;color:var(--muted);font:inherit;font-weight:650;font-size:.95rem;cursor:pointer;transition:background .2s var(--ease),color .2s var(--ease)}
.tabs button:hover{color:var(--navy)}
.tabs button[aria-pressed=true]{background:#fff;color:var(--navy);box-shadow:var(--shadow)}
#rec-tabs{width:auto;border-radius:20px}
.frames{display:grid;gap:18px;grid-template-columns:1fr}
.frames.both{grid-template-columns:1fr}
@media(min-width:1100px){.frames.both{grid-template-columns:1fr 1fr}}
iframe.f{width:100%%;height:78vh;min-height:560px;border:0;border-radius:24px;background:#fff;box-shadow:var(--shadow-lift)}
.limits{background:#fff;border:0;border-radius:20px;padding:10px 20px;margin:12px 0;box-shadow:var(--shadow)}
.limits summary{min-height:44px;display:flex;align-items:center;font-weight:700;cursor:pointer}
body>main.wrap{max-width:1440px}
</style></head>
<body>
<a class="skip" href="#snapmain">Skip to the views</a>
<div class="demobar" id="demobar" role="region" aria-label="Demo notice"><span class="demotag" aria-hidden="true">DEMO</span> <span id="demotext">Demo — example data only, not a real patient portal</span></div>
<header class="site"><div class="wrap"><img class="logo" src="%(logo)s" alt="Premier Spine" width="145" height="34"><span class="appname">Static snapshot · portal + office workspace</span></div></header>
<div class="protobar" role="region" aria-label="Prototype notice" id="sb">%(banner)s</div>
<main class="wrap" id="snapmain" tabindex="-1">
<h1>Static snapshot: patient portal and office workspace</h1>
<details class="limits"><summary>What this snapshot is, and what it cannot prove</summary>
<ul>
<li>It is one HTML file. The same screens as the server version run here against a JavaScript <b>mock</b> of the API with made-up data held in this browser tab only. Reloading resets it.</li>
<li>The workflow rules (states, routing, triage patterns, FAQ, limits) are generated from the server code, but they are <b>re-implemented in the browser</b>.</li>
<li><b>It cannot prove</b> server-side authorization (signed session tokens, patient A cannot read patient B, caregiver scope), SQLite persistence, restart durability, append-only audit enforcement in the database, or that secrets are not exposed. In the snapshot, any visitor can run any persona.</li>
<li>Nothing is sent anywhere. No text messages, no real people, no real records. Delivery receipts are simulated.</li>
<li><b>Referral scenarios (Pass 2):</b> the eight key states below (including the surgery pathway) are <b>recordings</b> of what the local server returned when this file was built (%(rec_at)s). The real screens render them, but they are <b>read-only</b>: buttons that change data say so. The presenter’s spotlight tour, automatic follow-ups (“follow-up date passes”) and post-op check-ins need the local server; here only each scenario’s key state can be shown.</li>
</ul></details>
<div class="tabs" id="tabs" role="group" aria-label="Choose a view">
<button type="button" data-t="portal" aria-pressed="true">Patient portal</button><button type="button" data-t="office" aria-pressed="false">Office workspace</button><button type="button" data-t="presenter" aria-pressed="false">Presenter mode</button><button type="button" id="both" aria-pressed="false">Portal + office side by side</button>
</div>
<section aria-labelledby="h-rec" class="card"><h2 id="h-rec">Referral scenarios: recorded key states</h2>
<div class="tabs" id="rec-tabs" role="group" aria-label="Show a recorded scenario">%(rec_buttons)s<button type="button" id="rec-off">Back to the interactive Pass 1 demo</button></div>
<p class="istatus" id="rec-note" role="status" aria-live="polite"></p></section>
<div class="frames" id="frames">
<iframe class="f" id="f-portal" title="Patient portal (static snapshot)"></iframe>
<iframe class="f" id="f-office" title="Office workspace (static snapshot)" hidden></iframe>
<iframe class="f" id="f-presenter" title="Presenter mode (static snapshot)" hidden></iframe>
</div></main>
<script>
%(mock)s
</script>
<script>
%(docs)s
(function(){
  var cur='portal', both=false;
  ['portal','office','presenter'].forEach(function(k){ document.getElementById('f-'+k).srcdoc=DOCS[k]; });
  function show(){
    ['portal','office','presenter'].forEach(function(k){ var f=document.getElementById('f-'+k); f.hidden = both ? !(k==='portal'||k==='office') : k!==cur; });
    document.getElementById('frames').className='frames'+(both?' both':'');
    Array.prototype.forEach.call(document.querySelectorAll('.tabs button[data-t]'),function(b){ b.setAttribute('aria-pressed', String(!both && b.dataset.t===cur)); });
    document.getElementById('both').setAttribute('aria-pressed', String(both));
  }
  window.__PS_RELOAD = function(msg){ ['portal','office'].forEach(function(k){ document.getElementById('f-'+k).srcdoc=DOCS[k]; }); var n=document.getElementById('rec-note'); n.textContent = msg || ''; n.className = 'istatus' + (msg ? ' ok' : ''); };
  document.getElementById('rec-tabs').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; var M=window.__PS_MOCK;
    if (b.id==='rec-off') { M.replay(null); window.__PS_RELOAD(''); return; }
    M.call('POST','/api/presenter/enter',{}).then(function(){ return M.call('POST','/api/presenter/scenario/load',{key:b.dataset.k, step:'key'}); }).then(function(r){ both=true; show(); });
  });
  document.querySelector('.tabs').addEventListener('click',function(e){ var b=e.target.closest('button'); if(!b) return; if(b.id==='both'){ both=!both; } else { both=false; cur=b.dataset.t; } show(); });
  show();
})();
</script>
</body></html>
""" % {"css": inline_assets(CSS), "logo": ASSETS["logo-dark.png"], "banner": BANNER, "mock": mock, "docs": docs_js, "rec_at": REC["recorded_at"],
       "rec_buttons": "".join(f'<button type="button" data-k="{k}" id="rec-{k}">{v["n"]}. {v["title"]}</button>' for k, v in REC["keys"].items())}
open(os.path.join(HERE, "snapshot.html"), "w", encoding="utf-8").write(OUT)
print("snapshot.html", len(OUT), "bytes;", "https:// occurrences:", OUT.count("https://"), "http:// occurrences:", OUT.count("http://"))
