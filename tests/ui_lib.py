"""Shared helpers for the Playwright UI tests (real local server, no external service)."""
import json, os, signal, subprocess, sys, time, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
AXE = os.environ.get("PS_AXE", "/workspace/axe/node_modules/axe-core/axe.min.js")   # optional; reported NOT RUN when absent
SHOTS_DIR = os.environ.get("PS_SHOTS_DIR") or os.path.join(os.path.dirname(ROOT), "preview19-shots")   # screenshots (not in the repo)
PORT = 8771; BASE = f"http://127.0.0.1:{PORT}"
RESULTS = []; REQS = set()

def check(name, ok, detail=""):
    RESULTS.append([name, bool(ok), str(detail)[:300]])
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  <-- " + str(detail)[:300]), flush=True)

class Srv:
    def __init__(self, db): self.db = db; self.p = None
    def start(self, reset=False, worker=False):
        import socket, atexit
        so = socket.socket(); so.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # ignore TIME_WAIT from a previous run; a LISTENING server still blocks
        try: so.bind(("127.0.0.1", PORT))
        except OSError: raise RuntimeError(f"port {PORT} is busy (stale server?) - refusing to test against it")
        finally: so.close()
        atexit.register(lambda: self.p and self.stop())
        args = [sys.executable, os.path.join(ROOT, "server.py"), "--port", str(PORT), "--db", self.db] + (["--reset"] if reset else []) + ([] if worker else ["--no-worker"])
        self.p = subprocess.Popen(args, stdout=open("/tmp/ui_srv.log", "a"), stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(60):
            try: urllib.request.urlopen(BASE + "/api/health", timeout=1); return
            except Exception: time.sleep(0.2)
        raise RuntimeError("server did not start")
    def stop(self):
        if self.p: os.killpg(self.p.pid, signal.SIGTERM); self.p.wait(timeout=10); self.p = None

def api(ctx, method, path, body=None, key=None):
    h = {"X-PS-Client": "1", "Content-Type": "application/json"}
    if key: h["Idempotency-Key"] = key
    fn = {"GET": ctx.request.get, "POST": ctx.request.post, "PUT": ctx.request.put}[method]
    r = fn(BASE + path, headers=h, data=json.dumps(body) if body is not None else None) if method != "GET" else fn(BASE + path, headers=h)
    try: j = r.json()
    except Exception: j = None
    return r.status, j

def track(page):
    page.on("request", lambda r: REQS.add(r.url.split("?")[0]) if not r.url.startswith(("data:", "about:", "blob:")) else None)

JS_FIXED = """() => { const o=[]; for (const el of document.querySelectorAll('body *')) { if (el.tagName==='DIALOG') continue; const p=getComputedStyle(el).position; if (p==='fixed'||p==='sticky') { if (el.id==='nav' && el.classList.contains('tabbar') && p==='fixed' && innerWidth < 860) { const pb=parseFloat(getComputedStyle(document.body).paddingBottom), bh=el.getBoundingClientRect().height; if (pb + 0.5 < bh) o.push('tab bar would cover content: body padding-bottom '+pb+' < bar height '+bh); continue; } o.push(el.tagName+'.'+el.className); } } return o; }"""
JS_OVERFLOW = """() => ({sw: document.documentElement.scrollWidth, iw: window.innerWidth})"""
JS_SMALL = """() => { const o=[]; const sel='button, a.btn, a.hbtn, a.qitem, nav a, input[type=text], input[type=date], select, textarea, summary, .choice'; for (const el of document.querySelectorAll(sel)) { if (el.closest('dialog:not([open])')) continue; const r=el.getBoundingClientRect(); if (r.width===0||r.height===0) continue; const cs=getComputedStyle(el); if (cs.visibility==='hidden'||cs.display==='none') continue; if (r.height<43.5) o.push((el.id||el.className||el.tagName)+':'+Math.round(r.height)); } return o; }"""
JS_CLIPPED = """() => { const o=[]; for (const el of document.querySelectorAll('button, a, input, select, textarea')) { const r=el.getBoundingClientRect(); if (r.width===0||r.height===0) continue; if (getComputedStyle(el).position==='absolute' && el.classList.contains('skip')) continue; if (r.right>window.innerWidth+1||r.left<-1) o.push((el.id||el.className||el.tagName)+':'+Math.round(r.left)+'-'+Math.round(r.right)); } return o; }"""

SKIPPED = []
def axe_run(page, name):
    if not os.path.exists(AXE):  # axe-core is not on this box and installing it would be a new dependency: report as NOT RUN, never as passed
        SKIPPED.append(f"axe: {name}"); print(f"SKIP axe: {name} (axe-core not available - not run)", flush=True); return []
    page.evaluate(open(AXE).read())
    res = page.evaluate("async () => { const r = await axe.run(document, {resultTypes:['violations']}); return r.violations.map(v => ({id:v.id, impact:v.impact, n:v.nodes.length, sample:(v.nodes[0]||{}).target})); }")
    check(f"axe: {name}", not res, json.dumps(res)[:300])
    return res

def layout_checks(page, name, width, strict_small=True):
    fx = page.evaluate(JS_FIXED); check(f"no fixed/sticky overlays (only the phone tab bar, with matching body padding): {name} @{width}", not fx, fx)
    ov = page.evaluate(JS_OVERFLOW); check(f"no horizontal scroll: {name} @{width}", ov["sw"] <= ov["iw"] + 1, ov)
    cl = page.evaluate(JS_CLIPPED); check(f"no controls clipped off-screen: {name} @{width}", not cl, cl)
    if strict_small:
        sm = page.evaluate(JS_SMALL); check(f"targets >= 44px: {name} @{width}", not sm, sm[:6])

def portal_login(ctx, who, width=1440, height=900):
    pg = ctx.new_page(); track(pg); pg.goto(BASE + "/portal.html"); pg.locator(f"button.qitem:has-text('{who}')").click(); pg.locator("h1").filter(has_text="Hello").or_(pg.locator("h1").filter(has_text="Viewing")).first.wait_for(timeout=8000); return pg

def office_login(ctx, who):
    pg = ctx.new_page(); track(pg); pg.goto(BASE + "/office.html"); pg.locator(f"button.qitem:has-text('{who}')").click(); pg.locator("h1:has-text('Work queue')").wait_for(timeout=8000); pg.locator("#qlist a.qitem, #qlist p").first.wait_for(timeout=8000); return pg

def save():
    json.dump(RESULTS, open(os.path.join(HERE, "ui_test.results.json"), "w"), indent=1)
