#!/usr/bin/env python3
"""Pass 2 review screenshots -> $PS_SHOTS_DIR (default ../preview19-shots)/legacy-pass2/ (preview19 copy; never writes to older shot folders; legacy script, not re-run for preview19) (fresh temp server, fictional data).
One patient view and one office view for each scenario's KEY STATE, plus a few interaction extras."""
import os, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_SHOT_PORT", "8774")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"; api = L.api
OUT = os.path.join(L.SHOTS_DIR, "legacy-pass2"); os.makedirs(OUT, exist_ok=True)
SC = [("clean", 1, "Avery", None), ("missing", 2, "Blake", "records_request"), ("auth", 3, "Cameron", "prior_auth"), ("nointake", 4, "Drew", "intake_followup"),
      ("caregiver", 5, "Emery", "intake_confirm"), ("notfit", 6, "Finley", "fit_review"), ("redflag", 7, "Gray", "red_flag"), ("surgery", 8, "Harper", "clearance_request")]
def load(ctx, key, step="key", helper=False, office_as=None):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "as_helper": helper, "office_as": office_as}); assert s == 200, j; return j
def tid(ctx, name, typ=None):
    s, q = api(ctx, "GET", "/api/o/queue?filter=all"); return [t for t in q["tasks"] if t["patient_name"].startswith(name) and t["status"] != "Resolved" and (typ is None or t["type"] == typ)][0]["id"]
def shot(pg, name, full=True): pg.wait_for_timeout(400); pg.screenshot(path=f"{OUT}/{name}.png", full_page=full); print("shot", name)
def office_top(pg): pg.evaluate("window.scrollTo(0, document.querySelector('#split').offsetTop - 8)")
def el_shot(pg, sel, name): pg.locator(sel).scroll_into_view_if_needed(); pg.wait_for_timeout(300); pg.locator(sel).screenshot(path=f"{OUT}/{name}.png"); print("shot", name)
def spotlights(br):
    # DEMO banner on login screens at 360 px
    c = br.new_context(viewport={"width": 360, "height": 740}); pg = c.new_page()
    pg.goto(BASE + "/portal.html"); pg.locator("#login-demo").wait_for(); shot(pg, "d1-demo-banner-portal-login-360", full=False)
    pg.goto(BASE + "/office.html"); pg.locator("#demobar").wait_for(); pg.wait_for_timeout(500); shot(pg, "d2-demo-banner-office-login-360", full=False); c.close()
    # presenter tour
    d = br.new_context(viewport={"width": 1440, "height": 1100}); api(d, "POST", "/api/presenter/enter", {})
    pp = d.new_page(); pp.goto(BASE + "/presenter.html"); pp.locator("#pm-toggle").click(); pp.locator("#tour-card").wait_for(); el_shot(pp, "#tour-card", "sp0-presenter-spotlight-tour-1440"); d.close()
    # 1. fewer calls
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "missing")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#pipe-waiting").wait_for(); el_shot(pg, "#pipe", "sp1a-patient-status-who-and-next-step-390"); m.close()
    d = br.new_context(viewport={"width": 1440, "height": 1100}); load(d, "missing"); load(d, "auth"); load(d, "clean", "intake")
    for who in ("blake", "cameron"):
        api(d, "POST", "/api/login", {"persona": who, "app": "portal"}); api(d, "GET", "/api/p/home")
    api(d, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"}); api(d, "POST", "/api/login", {"persona": "pat", "app": "office"})
    q = d.new_page(); q.goto(BASE + "/office.html#/queue"); q.locator("#calls-label").wait_for(); el_shot(q, "#calls", "sp1b-office-calls-saved-example-counts-1440")
    # 2. chasing
    load(d, "auth"); api(d, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"})
    q.goto(BASE + f"/office.html#/task/{tid(d, 'Cameron', 'prior_auth')}"); q.locator("#d-pipe .tracks").wait_for(); office_top(q); shot(q, "sp2a-office-auto-chasing-1-of-2-1440", full=False)
    api(d, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"}); api(d, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"})
    q.goto(BASE + "/office.html#/queue"); q.locator("#qlist .qrow").first.wait_for(); q.wait_for_timeout(600); office_top(q); shot(q, "sp2b-office-queue-stuck-needs-a-call-1440", full=False)
    pd = d.new_page(); api(d, "POST", "/api/login", {"persona": "cameron", "app": "portal"}); pd.goto(BASE + "/portal.html#/home"); pd.locator("#pipe").wait_for(); el_shot(pd, "#pipe", "sp2c-patient-sees-following-up-by-phone-1440")
    d.close()
    # 3. prefilled intake + summary
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "clean", "intake")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/intake"); pg.locator("#intake").wait_for(); pg.locator("#pf-meds-help summary").click()
    el_shot(pg, "#intake fieldset.card >> nth=0", "sp3a-prefilled-intake-sources-hints-why-390"); m.close()
    d = br.new_context(viewport={"width": 1440, "height": 1100}); j = load(d, "clean", "key", office_as="yakel")
    q = d.new_page(); q.goto(BASE + f"/office.html#/task/{j['open_task']}"); q.locator("#sum-label").wait_for(); el_shot(q, "#d-sum", "sp3b-visit-ready-summary-draft-1440")
    q.locator("#sum-review").click(); q.locator("#sum-reviewed.ok").wait_for(); el_shot(q, "#d-sum", "sp3c-summary-marked-reviewed-by-clinician-1440"); d.close()
    # 4. surgery
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "surgery", "key")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#pipe").wait_for(); shot(pg, "sp4a-patient-preop-checklist-390"); m.close()
    d = br.new_context(viewport={"width": 1440, "height": 1100}); j = load(d, "surgery", "key", office_as="yakel")
    q = d.new_page(); q.goto(BASE + f"/office.html#/task/{j['open_task']}"); q.locator("#po-items").wait_for(); el_shot(q, "#d-pipe", "sp4b-office-surgery-checklist-1440"); d.close()
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "surgery", "postop")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#ck-form").wait_for(); pg.locator("label[for=ck-concern]").click(); pg.locator("#ck-note").fill("The wound area looks different today and I am worried (example).")
    pg.locator("#ck-send").click(); pg.locator("#na-status.warn").wait_for(); el_shot(pg, "section.card.gold", "sp4c-patient-postop-checkin-concern-sent-390"); m.close()
    d = br.new_context(viewport={"width": 1440, "height": 1100}); j = load(d, "surgery", "postop_concern", office_as="nina")
    q = d.new_page(); q.goto(BASE + f"/office.html#/task/{j['open_task']}"); q.locator("#do-close_concern").wait_for(); office_top(q); shot(q, "sp4d-office-urgent-nurse-task-from-checkin-1440", full=False); d.close()

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "shots2.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    for key, n, name, typ in SC:
        m = br.new_context(viewport={"width": 390, "height": 844}); load(m, key)
        pg = m.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#pipe").wait_for(); shot(pg, f"s{n}-{key}-patient-390")
        d = br.new_context(viewport={"width": 1440, "height": 1100}); load(d, key)
        op = d.new_page(); op.goto(BASE + f"/office.html#/task/{tid(d, name, typ)}"); op.locator("#d-pipe .tracks").wait_for(); office_top(op); shot(op, f"s{n}-{key}-office-1440", full=False)
        if key in ("clean", "redflag"):
            pd = d.new_page(); pd.goto(BASE + "/portal.html#/home"); pd.locator("#pipe").wait_for(); shot(pd, f"s{n}-{key}-patient-1440")
        m.close(); d.close()
    # extras
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "redflag", "intake")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/intake"); pg.locator("#intake").wait_for(); shot(pg, "x1-intake-tell-us-once-form-390")
    pg.locator("label[for='rf-saddle_numb']").click(); pg.locator("#rf-task").filter(has_text="urgent task").wait_for()
    pg.locator("#rf-set").scroll_into_view_if_needed(); pg.locator("#rf-set").screenshot(path=f"{OUT}/x2-intake-red-flag-guidance-390.png"); print("shot x2")
    m.close()
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "caregiver", "intake", helper=True)
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/home"); pg.locator("#pipe").wait_for(); shot(pg, "x3-helper-home-intake-next-390")
    m.close()
    m = br.new_context(viewport={"width": 390, "height": 844}); load(m, "caregiver")
    pg = m.new_page(); pg.goto(BASE + "/portal.html#/intake"); pg.locator("#att-summary").wait_for(); shot(pg, "x4-patient-confirms-helper-answers-390")
    m.close()
    d = br.new_context(viewport={"width": 1440, "height": 1100}); load(d, "missing", "key"); load(d, "auth", "key"); load(d, "nointake", "key"); load(d, "redflag", "key"); load(d, "notfit", "key")
    api(d, "POST", "/api/login", {"persona": "pat", "app": "office"})
    q = d.new_page(); q.goto(BASE + "/office.html#/queue"); q.locator("#nextup .nextup").wait_for(); q.locator("#filters button[data-f=referrals]").click(); q.wait_for_timeout(800); office_top(q); shot(q, "x5-office-queue-referral-pipeline-one-click-actions-1440", full=False)
    q.goto(BASE + f"/office.html#/task/{tid(d, 'Cameron', 'prior_auth')}"); q.locator("#do-record_decision").wait_for(); q.locator("#do-record_decision").click(); q.locator("#dof-record_decision").wait_for(); office_top(q); shot(q, "x6-office-do-next-insurer-decision-form-1440", full=False)
    q.goto(BASE + f"/office.html#/task/{tid(d, 'Finley', 'fit_review')}"); q.locator("#do-route_elsewhere").wait_for(); office_top(q); shot(q, "x7-office-front-desk-cannot-route-elsewhere-1440", full=False)
    q2 = br.new_context(viewport={"width": 390, "height": 844}); load(q2, "nointake"); qq = q2.new_page(); qq.goto(BASE + "/office.html#/queue"); qq.locator("#qlist .qrow").first.wait_for(); shot(qq, "x8-office-queue-with-actions-390", full=False)
    pp = d.new_page(); pp.goto(BASE + "/presenter.html"); pp.locator("#pm-toggle").click(); pp.locator("#scen-list article").first.wait_for(); pp.wait_for_timeout(500); shot(pp, "x9-presenter-eight-scenarios-1440")
    spotlights(br)
    br.close()
finally:
    srv.stop()
