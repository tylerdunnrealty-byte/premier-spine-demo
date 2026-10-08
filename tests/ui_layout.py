#!/usr/bin/env python3
"""Layout / zoom / a11y / keyboard tests against the REAL local server (127.0.0.1:8771, temp DB)."""
import json, os, re, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib
from ui_lib import *

tmp = tempfile.mkdtemp(); srv = Srv(os.path.join(tmp, "ui2.db")); srv.start(reset=True)
LONGMSG = "Please can you tell me about parking and what to bring. " * 12 + "\nEnd-marker \U0001F600"
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    def ctxw(w, h=800): return br.new_context(viewport={"width": w, "height": h})
    # seed a long thread via API so thread/detail screens have content
    seed_c = ctxw(1440); sp = portal_login(seed_c, "Alex Example")
    s, j = api(seed_c, "POST", "/api/p/messages", {"category": "scheduling", "body": LONGMSG}, key="seed-1"); TID = j["task"]["id"]
    pr = seed_c.request.post(BASE + "/api/presenter/enter", headers={"X-PS-Client": "1", "Content-Type": "application/json"}, data="{}")

    def screens_portal(pg, w, label):
        pg.goto(BASE + "/portal.html#/home"); pg.locator("h1:has-text('Hello')").wait_for(); pg.wait_for_timeout(250); layout_checks(pg, f"portal home ({label})", w)
        pg.goto(BASE + "/portal.html#/messages"); pg.locator("#threads a.qitem").first.wait_for(); layout_checks(pg, f"portal messages ({label})", w)
        pg.goto(BASE + f"/portal.html#/messages/{TID}"); pg.locator("#conv .msg").first.wait_for(); layout_checks(pg, f"portal thread ({label})", w)
        pg.goto(BASE + "/portal.html#/settings"); pg.locator("h1:has-text('Settings')").wait_for(); pg.wait_for_timeout(300); layout_checks(pg, f"portal settings ({label})", w)
    def screens_office(pg, w, label):
        pg.goto(BASE + "/office.html#/queue"); pg.locator("#qlist a.qitem").first.wait_for(); pg.wait_for_timeout(300); layout_checks(pg, f"office queue ({label})", w)
        pg.goto(BASE + f"/office.html#/task/{TID}"); pg.locator("#reply-body").wait_for(); pg.wait_for_timeout(400); layout_checks(pg, f"office case detail ({label})", w)

    for w in (360, 390):
        c = ctxw(w, 800); pg = c.new_page(); track(pg); pg.goto(BASE + "/portal.html"); layout_checks(pg, f"portal sign-in", w)
        pg.locator("button.qitem:has-text('Alex Example')").click(); pg.locator("h1:has-text('Hello')").wait_for(); screens_portal(pg, w, "normal text")
        o = c.new_page(); track(o); o.goto(BASE + "/office.html"); layout_checks(o, "office sign-in", w); o.locator("button.qitem:has-text('Pat')").click(); o.locator("h1:has-text('Work queue')").wait_for(); screens_office(o, w, "normal text")
        c.close()

    # sheet at 390: compact, focus trap, Esc, focus return, nothing overlaps the call bar
    c = ctxw(390, 800); pg = c.new_page(); track(pg); pg.goto(BASE + "/portal.html"); pg.locator("button.qitem:has-text('Alex Example')").click(); pg.locator("h1:has-text('Hello')").wait_for()
    op = pg.locator("section[aria-labelledby=h-reach] button:has-text('Who do I call?')"); op.scroll_into_view_if_needed(); op.focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(250)
    box = pg.evaluate("() => { const d=document.getElementById('whocall'); const r=d.getBoundingClientRect(); return {open:d.open, h:r.height, vh:innerHeight, w:r.width, inside:d.contains(document.activeElement)}; }")
    check("'Who do I call?' sheet opens as a compact bottom sheet (<=75% height) with focus inside", box["open"] and box["h"] <= box["vh"] * 0.75 + 1 and box["inside"], box)
    inside = True
    for _ in range(14): pg.keyboard.press("Tab"); inside = inside and pg.evaluate("document.getElementById('whocall').contains(document.activeElement)")
    check("focus is trapped inside the sheet (14 Tab presses)", inside)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(200); check("Esc closes the sheet and returns focus to the opener", not pg.evaluate("document.getElementById('whocall').open") and pg.evaluate("document.activeElement.textContent") == "Who do I call?")
    c.close()

    # zoom: 200% and 400% text at 360 and 320 wide; plus Larger-text toggle
    for scale, w in ((200, 390), (400, 390), (200, 320), (400, 320)):
        c = ctxw(w, 700); pg = c.new_page(); track(pg); pg.goto(BASE + "/portal.html"); pg.locator("button.qitem:has-text('Alex Example')").click(); pg.locator("h1:has-text('Hello')").wait_for()
        pg.evaluate(f"document.documentElement.style.fontSize='{scale}%'"); screens_portal(pg, w, f"{scale}% text")
        cb = pg.locator("a[href='tel:2087703536']").first; pg.goto(BASE + "/portal.html#/home"); pg.locator("h1:has-text('Hello')").wait_for(); cb.scroll_into_view_if_needed()
        top = pg.evaluate("() => { const a=document.querySelector('a.hbtn'); const r=a.getBoundingClientRect(); const e=document.elementFromPoint(r.left+r.width/2, r.top+r.height/2); return a===e||a.contains(e); }")
        check(f"call link is not covered by anything @{scale}% {w}px", top)
        o = c.new_page(); track(o); o.goto(BASE + "/office.html"); o.locator("button.qitem:has-text('Pat')").click(); o.locator("h1:has-text('Work queue')").wait_for(); o.evaluate(f"document.documentElement.style.fontSize='{scale}%'"); screens_office(o, w, f"{scale}% text")
        c.close()
    c = ctxw(320, 700); pg = c.new_page(); track(pg); pg.goto(BASE + "/portal.html"); pg.locator("button.qitem:has-text('Alex Example')").click(); pg.locator("h1:has-text('Hello')").wait_for()
    # preview19: text size is a labelled two-choice control in the Account menu (and in Settings)
    pg.locator("#account-btn").click(); pg.locator("label[for=acct-ts-large]").click(); pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
    check("Larger text control turns on ('Larger' checked, 125% root)", pg.locator("#acct-ts-large").is_checked() and pg.evaluate("getComputedStyle(document.documentElement).fontSize") == "20px", pg.evaluate("getComputedStyle(document.documentElement).fontSize"))
    screens_portal(pg, 320, "Larger text toggle")
    c.close()
    c = ctxw(1000); pg = c.new_page(); pg.goto(BASE + "/portal.html"); check("body font-size is 18px", pg.evaluate("getComputedStyle(document.body).fontSize") == "18px"); c.close()

    # desktop layout, axe on every screen
    c = ctxw(1440, 900); pg = c.new_page(); track(pg)
    pg.goto(BASE + "/"); axe_run(pg, "landing page")
    pg.goto(BASE + "/portal.html"); pg.wait_for_selector("button.qitem"); axe_run(pg, "portal sign-in"); pg.locator("button.qitem:has-text('Alex Example')").click(); pg.locator("h1:has-text('Hello')").wait_for(); pg.wait_for_timeout(300)
    screens = [("portal home", "/portal.html#/home", "h1:has-text('Hello')"), ("portal messages", "/portal.html#/messages", "#threads a.qitem"), ("portal thread", f"/portal.html#/messages/{TID}", "#conv .msg"), ("portal settings", "/portal.html#/settings", "h1:has-text('Settings')")]
    for nm_, url, sel in screens: pg.goto(BASE + url); pg.locator(sel).first.wait_for(); pg.wait_for_timeout(300); axe_run(pg, nm_)
    pg.goto(BASE + "/portal.html#/home"); pg.locator("section[aria-labelledby=h-reach] button:has-text('Who do I call?')").click(); pg.wait_for_timeout(200); axe_run(pg, "portal 'Who do I call?' sheet open"); pg.keyboard.press("Escape")
    pg.goto(BASE + "/portal.html#/home"); pg.locator("a#na-intake").click(); pg.locator("#intake").wait_for(); axe_run(pg, "portal intake page (Pass 2 tell-us-once form)")
    rc = ctxw(1440); rp = portal_login(rc, "Riley Helper"); axe_run(rp, "portal caregiver home")
    for who, nm_ in (("Pat", "office (front desk)"), ("Admin", "office (admin)")):
        oc = ctxw(1440); op_ = oc.new_page(); track(op_); op_.goto(BASE + "/office.html"); op_.wait_for_selector("button.qitem"); axe_run(op_, "office sign-in") if who == "Pat" else None
        op_.locator(f"button.qitem:has-text('{who}')").click(); op_.locator("h1:has-text('Work queue')").wait_for(); op_.locator("#qlist a.qitem").first.wait_for(); op_.wait_for_timeout(300); axe_run(op_, f"{nm_} queue")
        op_.goto(BASE + f"/office.html#/task/{TID}"); op_.locator("#reply-body").wait_for(); op_.wait_for_timeout(300); axe_run(op_, f"{nm_} case detail with composer")
        op_.locator("button:text-is('Resolve\u2026')").click(); axe_run(op_, f"{nm_} resolve form open")
        op_.goto(BASE + "/office.html#/notifications"); op_.locator("h1:has-text('Notifications')").wait_for(); axe_run(op_, f"{nm_} notifications")
        if who == "Admin":
            for v in ("reports", "audit", "settings"): op_.goto(BASE + f"/office.html#/{v}"); op_.wait_for_timeout(700); axe_run(op_, f"office {v}")
            layout_checks(op_, "office reports", 1440)
        oc.close()
    ppg = c.new_page(); track(ppg); ppg.goto(BASE + "/presenter.html"); ppg.locator("#pm-toggle").click(); ppg.locator("text=Scenarios").first.wait_for(); axe_run(ppg, "presenter mode (on)")

    # keyboard
    kc = ctxw(1440, 900); kp = kc.new_page(); track(kp); kp.goto(BASE + "/portal.html"); kp.locator("button.qitem").first.wait_for(); kp.keyboard.press("Tab")
    check("keyboard: first Tab stop is the 'Skip to main content' link", kp.evaluate("document.activeElement.className") == "skip" and "Skip" in kp.evaluate("document.activeElement.textContent"))
    kp.keyboard.press("Enter"); check("keyboard: skip link moves focus to <main>", kp.evaluate("document.activeElement.id") == "main")
    kp.locator("button.qitem:has-text('Alex Example')").focus(); kp.keyboard.press("Enter"); kp.locator("h1:has-text('Hello')").wait_for()
    seq = []
    for _ in range(40):
        kp.keyboard.press("Tab"); seq.append(kp.evaluate("(document.activeElement.textContent||document.activeElement.getAttribute('aria-label')||'').trim().slice(0,28)"))
    # preview19: header is "Call us" + "Account" (text size, settings, sign-out live in the Account menu)
    check("keyboard: Tab order reaches Call us, Account, nav, Start your intake form, Request a call back", all(any(x in s for s in seq) for x in ("Call us", "Account", "Messages", "Start your intake", "Request a call back")), seq[:22])
    kp.locator("#cb-btn").focus(); fv = kp.evaluate("() => { const e=document.activeElement; const cs=getComputedStyle(e); return cs.outlineStyle+' '+cs.outlineWidth; }"); check("keyboard: visible focus ring (>=3px outline)", fv.startswith("solid 3"), fv)
    ko = kc.new_page(); track(ko); ko.goto(BASE + "/office.html"); ko.locator("button.qitem:has-text('Pat')").focus(); ko.keyboard.press("Enter"); ko.locator("#qlist a.qitem").first.wait_for()
    lk = ko.locator(f"#qlist a.qitem[href='#/task/{TID}']"); lk.focus(); ko.keyboard.press("Enter"); ko.locator("#reply-body").wait_for()
    ko.locator("#reply-body").focus(); ko.keyboard.press("End"); ko.keyboard.type(" typed-by-keyboard"); ko.locator("#draft-ind").filter(has_text="Draft saved on the server").wait_for(timeout=6000)
    ko.keyboard.press("Tab"); tb = ko.evaluate("document.activeElement.id"); ko.keyboard.press("Tab")
    check("keyboard: office composer is reachable and operable with keys only (typing autosaves; Tab leaves the field in order)", tb == "reply-send", tb)
    ko.locator("#reply-send").focus(); ko.keyboard.press("Enter"); ko.locator("#reply-st").filter(has_text="Reply sent").wait_for(timeout=6000); check("keyboard: Send activated with Enter; request remains open", api(kc, "GET", f"/api/o/tasks/{TID}")[1]["task"]["status"] == "In Progress")

    ext = sorted(u for u in ui_lib.REQS if not u.startswith(BASE)); check("no external network requests during the layout/a11y run", not ext, ext)
    br.close()
srv.stop(); save_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_layout.results.json"); json.dump(RESULTS, open(save_path, "w"), indent=1)
bad = [r for r in RESULTS if not r[1]]; print(f"\nDONE ui_layout: {len(RESULTS) - len(bad)}/{len(RESULTS)} passed; failed: {[r[0] for r in bad]}; NOT RUN (axe-core unavailable): {len(ui_lib.SKIPPED)}")
