#!/usr/bin/env python3
"""Six fictional Home states at 390x844: screenshot + page height.  -> $PS_SHOTS_DIR (default ../preview19-shots)/
PS_ROOT selects which copy runs (preview18 = BEFORE, preview19 = AFTER).  The server always uses a temp DB, so the source folder is never written to.
Usage: PS_ROOT=/workspace/premier-spine/preview18 PS_PREFIX=before python3 tests/home_states.py"""
import os, sys, json, tempfile, uuid
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.ROOT = os.environ.get("PS_ROOT", L.ROOT); PREFIX = os.environ.get("PS_PREFIX", "after")
L.PORT = int(os.environ.get("PS_SHOT_PORT", "8780")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"; api = L.api
OUT = L.SHOTS_DIR; os.makedirs(OUT, exist_ok=True)
W, H = 390, 844

def load(ctx, key, step="key"):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step}); assert s == 200, j; return j

def booked(ctx):
    """Ready (Avery) + staff records a visit through the normal office action (same path the office screen uses)."""
    load(ctx, "clean", "key"); s, j = api(ctx, "POST", "/api/login", {"persona": "pat", "app": "office"}); assert s == 200, j
    s, q = api(ctx, "GET", "/api/o/queue?filter=open"); assert s == 200, q
    t = next(x for x in q["tasks"] if x["type"] == "schedule_visit")
    from datetime import datetime, timedelta
    d = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    s, r = api(ctx, "POST", f"/api/o/tasks/{t['id']}/act", {"action": "book", "date": d, "time": "10:30", "clinician": "Dr. Stefan Yakel, DO"}, key=str(uuid.uuid4())); assert s == 200, r

STATES = [("records", "Waiting on records", lambda c: load(c, "missing")),
          ("intake", "Incomplete intake", lambda c: load(c, "nointake")),
          ("ready", "Ready to schedule", lambda c: load(c, "clean")),
          ("booked", "Appointment booked", booked),
          ("preop", "Pre-op", lambda c: load(c, "surgery")),
          ("postop", "Post-op", lambda c: load(c, "surgery", "postop"))]

res = {}
srv = L.Srv(os.path.join(tempfile.mkdtemp(), "home.db")); srv.start(reset=True)
try:
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
        for k, label, fn in STATES:
            c = br.new_context(viewport={"width": W, "height": H}); fn(c); pg = c.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(BASE + "/portal.html#/home"); pg.wait_for_load_state("networkidle"); pg.wait_for_timeout(1500)
            h = pg.evaluate("() => document.documentElement.scrollHeight")
            pg.screenshot(path=f"{OUT}/{PREFIX}-home-{k}-390.png"); pg.screenshot(path=f"{OUT}/{PREFIX}-home-{k}-390-full.png", full_page=True)
            res[k] = {"label": label, "height_px": h, "screens": round(h / H, 2), "errors": errs}
            print(f"{PREFIX} {k:8s} {label:20s} height={h}px ({h / H:.2f} screens) errors={errs}"); c.close()
        br.close()
finally:
    srv.stop()
json.dump(res, open(f"{OUT}/{PREFIX}-home-heights.json", "w"), indent=1)
