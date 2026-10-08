#!/usr/bin/env python3
"""Generate the review screenshots into $PS_SHOTS_DIR (default ../preview19-shots)/legacy-pass1/ (preview19 copy; never writes to older shot folders; legacy script, not re-run for preview19) from a fresh temp server (fictional data)."""
import os, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_lib import *
OUT = os.path.join(SHOTS_DIR, "legacy-pass1"); os.makedirs(OUT, exist_ok=True)
LONG = ("Hello, I need to move my appointment if possible. \u00e9 \U0001F600\n\nThis is a long message on purpose, to show that the whole thing reaches the office. " + "I can come any weekday after 2 PM, and Fridays are best. " * 5 + "\n\nThe last line says: thank you so much for your help, this is the END of my message.")
srv = Srv(os.path.join(tempfile.mkdtemp(), "shots.db")); srv.start(reset=True)
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    mk = lambda w, h=900: br.new_context(viewport={"width": w, "height": h})
    def shot(pg, name, full=True): pg.wait_for_timeout(350); pg.screenshot(path=f"{OUT}/{name}.png", full_page=full); print("shot", name)
    a390, a1440 = mk(390, 844), mk(1440)
    for ctx, w in ((a390, 390), (a1440, 1440)):
        pg = portal_login(ctx, "Alex Example"); shot(pg, f"01-patient-home-{w}")
    pg = a1440.pages[0]; pg.goto(BASE + "/portal.html#/messages"); pg.locator("#msg-body").wait_for()
    pg.locator("label[for=cat-scheduling]").click(); pg.locator("#msg-body").fill(LONG); shot(pg, "02a-patient-compose-with-counter-1440"); pg.locator("#msg-send").click(); pg.locator("#msg-status").filter(has_text="Sent.").wait_for()
    pg.locator("#threads a.qitem").first.click(); pg.locator("#conv .msg").first.wait_for(); shot(pg, "02-patient-messages-thread-long-message-1440")
    p3 = a390.pages[0]; p3.goto(BASE + "/portal.html#/messages"); p3.locator("#threads a.qitem").first.wait_for(); p3.locator("#threads a.qitem").first.click(); p3.locator("#conv .msg").first.wait_for(); shot(p3, "02b-patient-thread-long-message-390")
    p3.goto(BASE + "/portal.html#/home"); p3.locator("section[aria-labelledby=h-reach] button:has-text('Who do I call?')").click(); p3.wait_for_timeout(300); p3.screenshot(path=f"{OUT}/03-patient-who-do-i-call-sheet-390.png"); print("shot sheet"); p3.keyboard.press("Escape")
    # large text
    z = mk(390, 844); zp = portal_login(z, "Alex Example"); zp.evaluate("document.documentElement.style.fontSize='200%'"); zp.wait_for_timeout(300); shot(zp, "08-large-text-200pct-patient-home-390")
    z4 = mk(320, 700); z4p = portal_login(z4, "Alex Example"); z4p.evaluate("document.documentElement.style.fontSize='400%'"); z4p.wait_for_timeout(300); shot(z4p, "08b-large-text-400pct-patient-home-320")
    zb = mk(390, 844); zbp = portal_login(zb, "Alex Example"); zbp.locator("#textsize").click(); shot(zbp, "08c-larger-text-toggle-patient-home-390")
    # office
    o1440, o390 = mk(1440), mk(390, 844)
    po = office_login(o1440, "Pat"); shot(po, "04-office-queue-1440")
    p390 = office_login(o390, "Pat"); shot(p390, "04b-office-queue-390")
    tid = [t for t in api(o1440, "GET", "/api/o/queue?filter=open")[1]["tasks"] if t["patient_name"] == "Alex Example" and t["type"] == "message"][0]["id"]
    api(o1440, "POST", f"/api/o/tasks/{tid}/note", {"body": "Internal: patient asked for Fridays after 2 PM. Check Dr. Yakel's template."}, key="n1")
    po.goto(BASE + f"/office.html#/task/{tid}"); po.locator("#reply-body").wait_for(); po.locator("label[for=k-ack]").click(); po.locator("#reply-body").fill("Hi Alex, we received your message and a person is working on it. This is an acknowledgment, not the answer yet."); po.locator("#reply-send").click(); po.locator("#reply-st").filter(has_text="still open").wait_for()
    po.wait_for_timeout(600); shot(po, "05-office-case-detail-with-history-1440")
    p390.goto(BASE + f"/office.html#/task/{tid}"); p390.locator("#reply-body").wait_for(); shot(p390, "05b-office-case-detail-390")
    # composer with preserved draft (Jordan's seeded message)
    jt = [t for t in api(o1440, "GET", "/api/o/queue?filter=open")[1]["tasks"] if t["patient_name"] == "Jordan Sample" and t["type"] == "message"][0]["id"]
    po.goto(BASE + f"/office.html#/task/{jt}"); po.locator("#reply-body").wait_for(); po.locator("#reply-own").click(); po.locator("#reply-body").press("End"); po.keyboard.type("\n\nWe can move you to 4:15 PM. (my own edit \u2014 not yet sent)"); po.locator("#draft-ind").filter(has_text="Draft saved on the server").wait_for()
    po.locator("nav button[data-view=notifications]").click(); po.locator("h1:has-text('Notifications')").wait_for(); po.locator("nav button[data-view=queue]").click(); po.goto(BASE + f"/office.html#/task/{jt}"); po.locator("#reply-body").wait_for(); po.wait_for_timeout(500)
    po.locator("#d-composer").scroll_into_view_if_needed(); po.locator("#d-composer").screenshot(path=f"{OUT}/06-office-composer-preserved-draft.png"); print("shot composer")
    # failed notification exception
    pj = mk(1440); A = lambda path, b=None: api(pj, "POST", path, b or {})
    pj.request.post(BASE + "/api/presenter/enter", headers={"X-PS-Client": "1", "Content-Type": "application/json"}, data="{}"); A("/api/presenter/scenario", {"name": "bad_phone_jordan"})
    po.goto(BASE + f"/office.html#/task/{jt}"); po.locator("#reply-send").click(); po.locator("#reply-st").filter(has_text="Reply sent").wait_for()
    for _ in range(5): A("/api/presenter/tick")
    po.goto(BASE + "/office.html#/queue"); po.locator("#qlist a.qitem").first.wait_for(); shot(po, "07-office-queue-with-failed-notification-exception-1440")
    # presenter
    pp = pj.new_page(); pp.goto(BASE + "/presenter.html"); pp.locator("#pm-toggle").click(); pp.locator("text=Scenarios").first.wait_for(); shot(pp, "09-presenter-mode-1440")
    ad = office_login(mk(1440), "Admin"); ad.locator("nav button[data-view=reports]").click(); ad.locator("table").wait_for(); shot(ad, "10-office-reports-measured-only-1440")
    sp = br.new_context(viewport={"width": 1440, "height": 1000}).new_page(); sp.goto("file://" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshot.html")); sp.wait_for_timeout(600); shot(sp, "11-static-snapshot-1440", full=False)
    br.close()
srv.stop()
