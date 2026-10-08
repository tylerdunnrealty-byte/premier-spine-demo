#!/usr/bin/env python3
"""Before/after screenshots for the preview18 restyle -> $PS_SHOTS_DIR (default ../preview19-shots)/legacy-v18/ (fresh temp server, fictional data).
Each shot opens a fresh tab, so the app reads the signed-in person fresh after each scenario load.
PS_ROOT selects which copy runs (preview17 = BEFORE, preview18 = AFTER); the server uses a temp DB, so the source folder is not written to."""
import os, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.ROOT = os.environ.get("PS_ROOT", L.ROOT); PREFIX = os.environ.get("PS_PREFIX", "after")
L.PORT = int(os.environ.get("PS_SHOT_PORT", "8778")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"; api = L.api
OUT = os.path.join(L.SHOTS_DIR, "legacy-v18"); os.makedirs(OUT, exist_ok=True)
def load(ctx, key, step="key", office_as=None):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "office_as": office_as}); assert s == 200, j; return j
def shot(pg, name, full=False): pg.wait_for_timeout(700); pg.screenshot(path=f"{OUT}/{PREFIX}-{name}.png", full_page=full); print("shot", f"{PREFIX}-{name}")
def to(pg, sel): pg.evaluate("s => { const e = document.querySelector(s); if (e) window.scrollTo(0, e.getBoundingClientRect().top + window.scrollY - 12); }", sel)
WIDTHS = ((390, 844), (1440, 900))
srv = L.Srv(os.path.join(tempfile.mkdtemp(), "shots.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    for w, hgt in WIDTHS:
        # 1. patient Home (Blake: records outstanding)
        c = br.new_context(viewport={"width": w, "height": hgt}); load(c, "missing"); pg = c.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#pipe").wait_for()
        shot(pg, f"1-patient-home-{w}"); shot(pg, f"1-patient-home-full-{w}", full=True)
        # 2. intake (Avery: pre-filled)
        load(c, "clean", "intake"); pg = c.new_page(); pg.goto(BASE + "/portal.html#/intake"); pg.locator("#intake").wait_for(); shot(pg, f"2-intake-{w}")
        # 3. office board (all eight scenarios loaded, front desk)
        for k in ("clean", "missing", "auth", "nointake", "caregiver", "notfit", "redflag", "surgery"): load(c, k)
        api(c, "POST", "/api/login", {"persona": "pat", "app": "office"}); q = c.new_page(); q.goto(BASE + "/office.html#/queue"); q.locator("#qlist .qrow").first.wait_for(); to(q, "#qlist" if PREFIX == "before" else "#board-top")
        shot(q, f"3-office-board-{w}")
        # 4. visit-ready summary (Avery ready, Dr. Yakel)
        j = load(c, "clean", "key", office_as="yakel"); q = c.new_page(); q.goto(BASE + f"/office.html#/task/{j['open_task']}"); q.locator("#sum-label").wait_for(); to(q, "#d-sum"); shot(q, f"4-visit-summary-{w}")
        # 5. post-op (Harper: day-2 check-in waiting)
        load(c, "surgery", "postop"); pg = c.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#ck-form").wait_for(); shot(pg, f"5-postop-checkin-{w}")
        c.close()
    br.close()
finally:
    srv.stop()
