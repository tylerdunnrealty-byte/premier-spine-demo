#!/usr/bin/env python3
"""preview19 publish: tests the ONLINE static demo (publish/portal/) served by a plain static file server, like GitHub Pages.
Viewports 360x740, 390x844, 768x1024, 1440x900.  Checks: DEMO banner, no JS errors, no external requests, no horizontal scroll, every entry
button opens a working screen, every portal/office screen of every recording renders without an error, writes are labelled as a demo
recording (never a fake "Sent"), the tour, sign-out, and the date shift that keeps recordings current.  Port 8797.  Stdlib + Playwright."""
import json, os, re, subprocess, sys, time, datetime, urllib.request
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
SITE = os.environ.get("PS_PUB_ROOT", os.path.join(ROOT, "publish")); PORT = 8797; BASE = f"http://127.0.0.1:{PORT}/portal/"
SHOTS = os.environ.get("PS_SHOTS_DIR") or os.path.join(os.path.dirname(ROOT), "preview19-shots"); os.makedirs(SHOTS, exist_ok=True)
RESULTS, ERRS, EXT = [], [], []
def check(name, ok, detail=""):
    RESULTS.append([name, bool(ok), str(detail)[:300]]); print(("PASS " if ok else "FAIL ") + name + ("" if ok else "  <-- " + str(detail)[:300]), flush=True)
VIEWS = {"360": (360, 740), "390": (390, 844), "768": (768, 1024), "1440": (1440, 900)}
PATIENTS = ["clean:booked", "clean:intake", "missing", "auth", "nointake", "caregiver+helper", "notfit", "redflag", "surgery", "surgery:postop"]
OFFICE = ["redflag", "redflag@pat", "clean@yakel", "redflag@admin"]
BAD = re.compile(r"isn.t part of this demo recording|Something went wrong|couldn.t load|could not load|Not found\.|undefined|NaN|\[object Object\]|python3|server\.py|localhost|127\.0\.0\.1", re.I)
JS_OVER = "() => document.documentElement.scrollWidth - window.innerWidth"
JS_SMALL = """() => { const o=[]; for (const el of document.querySelectorAll('button, a.btn, a.hbtn, .pick, .choice')) { const r=el.getBoundingClientRect(); if (!r.width||!r.height) continue; if (el.closest('[hidden]')) continue; if (r.height<43.5) o.push((el.id||el.className)+':'+Math.round(r.height)); } return o; }"""
def pid(s): return re.sub(r"[^a-z]", "-", s, flags=re.I)

def frame(pg, which):
    return pg.locator("#f-" + which).element_handle().content_frame()
def wait_frame(pg, which, sel="main h1, main h2"):
    pg.frame_locator("#f-" + which).locator(sel).first.wait_for(timeout=10000); pg.wait_for_timeout(250); return frame(pg, which)
def main_text(fr): return fr.locator("main").inner_text()
def goto_hash(fr, h, sel="main h1"):
    fr.evaluate("h => { location.hash = h; }", h); fr.wait_for_timeout(450); fr.locator(sel).first.wait_for(timeout=8000); return main_text(fr)

def run():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1", "--directory", SITE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen(BASE, timeout=1); break
            except Exception: time.sleep(0.1)
        html = urllib.request.urlopen(BASE).read().decode()
        check("entry page is served (200) with noindex and the demo title", "noindex" in html and "Premier Spine Patient Portal" in html and "example data only" in html)
        for n in ("portal.html", "office.html"):
            h = urllib.request.urlopen(BASE + n).read().decode(); check(f"{n} has noindex and only runs inside the demo shell", "noindex" in h and "window.parent === window" in h)
        files = []
        for r, _, fs in os.walk(os.path.join(SITE, "portal")): files += [os.path.relpath(os.path.join(r, f), os.path.join(SITE, "portal")) for f in fs]
        check("published folder holds only static demo files (no .py/.db/.log/tests/checkpoints)", not [f for f in files if re.search(r"\.(py|db|sqlite|log|md)$|tests/|checkpoints", f)], files)
        with sync_playwright() as p:
            br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
            def ctx(vw, **kw):
                w, h = VIEWS[vw]; c = br.new_context(viewport={"width": w, "height": h}, **kw); pg = c.new_page()
                pg.on("pageerror", lambda e: ERRS.append((vw, str(e))))
                pg.on("console", lambda m: ERRS.append((vw, m.text)) if m.type == "error" else None)
                c.on("request", lambda r: EXT.append(r.url) if not r.url.startswith((f"http://127.0.0.1:{PORT}/", "data:", "about:", "blob:")) else None)
                return c, pg
            for vw in VIEWS:
                c, pg = ctx(vw); pg.goto(BASE); pg.wait_for_timeout(400)
                check(f"start: DEMO banner visible @{vw}", pg.locator("#demobar").is_visible() and "example data only" in pg.locator("#demobar").inner_text())
                check(f"start: no horizontal scroll @{vw}", pg.evaluate(JS_OVER) <= 1, pg.evaluate(JS_OVER))
                check(f"start: value line, both choices, the tour and 'Built for Premier' with the BAA/HIPAA line @{vw}", pg.locator("#value").is_visible() and pg.locator("#go-patient").is_visible() and pg.locator("#go-office").is_visible() and pg.locator("#go-tour").is_visible() and re.search(r"BAA.*HIPAA.*secure host.*EHR", pg.locator("#honest").inner_text()))
                pg.click("#go-patient"); pg.wait_for_timeout(250)
                check(f"start: 'Explore as a patient' lists {len(PATIENTS)} example patients @{vw}", pg.locator("#plist .pick").count() == len(PATIENTS) and pg.locator("#pick-patient").is_visible())
                pg.click("#go-office"); pg.wait_for_timeout(250)
                check(f"start: 'Explore as the office' lists {len(OFFICE)} roles and closes the patient list @{vw}", pg.locator("#olist .pick").count() == len(OFFICE) and not pg.locator("#pick-patient").is_visible())
                check(f"start: targets >= 44px @{vw}", not pg.evaluate(JS_SMALL), pg.evaluate(JS_SMALL))
                check(f"start: no horizontal scroll with lists open @{vw}", pg.evaluate(JS_OVER) <= 1)
                if vw in ("390", "1440"): pg.screenshot(path=os.path.join(SHOTS, f"publish-start-{vw}.png"), full_page=True)
                # every entry button
                pats = PATIENTS if vw in ("390", "1440") else PATIENTS[:3]
                for s in pats:
                    pg.goto(BASE); pg.click("#go-patient"); pg.click("#pick-patient-" + pid(s)); fr = wait_frame(pg, "portal"); t = main_text(fr)
                    check(f"patient entry '{s}' opens a working portal screen with its DEMO banner @{vw}", fr.locator("#demobar").is_visible() and not BAD.search(t) and len(t) > 80, t[:160])
                    check(f"app view: no horizontal scroll ({s}) @{vw}", pg.evaluate(JS_OVER) <= 1)
                for s in OFFICE:
                    pg.goto(BASE); pg.click("#go-office"); pg.click("#pick-office-" + pid(s)); fr = wait_frame(pg, "office"); t = main_text(fr)
                    check(f"office entry '{s}' opens a working office screen with its DEMO banner @{vw}", fr.locator("#demobar").is_visible() and not BAD.search(t) and len(t) > 80, t[:160])
                if vw in ("390", "1440"):
                    pg.goto(BASE + "#/patient/missing"); wait_frame(pg, "portal"); pg.screenshot(path=os.path.join(SHOTS, f"publish-patient-{vw}.png"))
                    pg.goto(BASE + "#/office/redflag"); wait_frame(pg, "office"); pg.wait_for_timeout(300); pg.screenshot(path=os.path.join(SHOTS, f"publish-office-{vw}.png"))
                # the tour
                pg.goto(BASE); pg.click("#go-tour"); steps = 0
                for i in range(6):
                    side = "office" if i in (1, 3, 5) else "portal"
                    fr = wait_frame(pg, side if vw != "1440" else side); t = main_text(fr); steps += 1
                    check(f"tour step {i+1}: caption shown and the screen renders @{vw}", pg.locator("#tb-h").is_visible() and not BAD.search(t) and len(t) > 80, (pg.locator("#tb-k").inner_text(), t[:120]))
                    if vw in ("390", "1440") and i in (0, 5): pg.screenshot(path=os.path.join(SHOTS, f"publish-tour{i+1}-{vw}.png"))
                    pg.click("#tb-next"); pg.wait_for_timeout(300)
                check(f"tour: Finish after step 6 returns to the start @{vw}", pg.locator("#v-start").is_visible() and steps == 6)
                c.close()
            # ---- every portal screen of every patient recording, and every office screen (390 + 1440)
            for vw in ("390", "1440"):
                c, pg = ctx(vw)
                for s in PATIENTS:
                    pg.goto(BASE + "#/patient/" + s); fr = wait_frame(pg, "portal")
                    for h in ("#/home", "#/visits", "#/messages", "#/records", "#/assist", "#/settings", "#/intake"):
                        t = goto_hash(fr, h, "main h1, main h2")
                        check(f"portal {s} {h}: renders, no error text, no horizontal scroll @{vw}", not BAD.search(t) and fr.evaluate(JS_OVER) <= 1, t[:160])
                    goto_hash(fr, "#/messages", "main h1")
                    th = fr.locator("#threads a.qitem")
                    if th.count():
                        th.first.click(); fr.wait_for_timeout(500); t = main_text(fr); check(f"portal {s}: a conversation opens @{vw}", not BAD.search(t) and len(t) > 40, t[:120])
                for s in OFFICE + ["missing", "auth:chased", "surgery:postop_concern@nina"]:
                    pg.goto(BASE + ("#/office/" + s if s in OFFICE else "#/patient/" + s)); wait_frame(pg, "portal" if s not in OFFICE else "office")
                    if vw != "1440": pg.click("#seg button[data-side=office]")
                    fr = frame(pg, "office"); fr.locator("main h1").first.wait_for(timeout=10000)
                    t = goto_hash(fr, "#/queue"); check(f"office {s} queue renders @{vw}", not BAD.search(t) and "Work queue" in t, t[:120])
                    first = fr.locator("#qlist a.qitem").first
                    if first.count():
                        first.click(); fr.wait_for_timeout(700); t = main_text(fr); check(f"office {s}: the first item's detail opens @{vw}", not BAD.search(t), t[:200])
                    for h in ("#/notifications",) + (("#/reports", "#/audit", "#/settings") if s == "redflag@admin" else ()):
                        t = goto_hash(fr, h); check(f"office {s} {h} renders @{vw}", not BAD.search(t) and len(t) > 40, t[:120])
                c.close()
            # ---- honesty: writes are labelled as a demo recording, never a fake success
            c, pg = ctx("390"); pg.goto(BASE + "#/patient/clean:booked"); fr = wait_frame(pg, "portal")
            goto_hash(fr, "#/messages"); fr.locator("#msg-send").wait_for()
            fr.locator("input[name=cat]").first.check() if fr.locator("input[name=cat]").count() else fr.locator("#cat input").first.check()
            fr.fill("#msg-body", "Example question about parking (fictional)."); fr.click("#msg-send"); fr.wait_for_timeout(700)
            st = fr.locator("#msg-status"); check("send message: calm 'Demo recording' notice, text kept, no 'Sent'", "demo" in (st.get_attribute("class") or "") and "Demo recording" in st.inner_text() and fr.input_value("#msg-body").startswith("Example") and not re.search(r"\bSent\b", main_text(fr)), (st.get_attribute("class"), st.inner_text()))
            check("send message: the button does not change to 'Try sending again' for a demo recording", fr.locator("#msg-send").inner_text().strip() == "Send message", fr.locator("#msg-send").inner_text())
            pg.screenshot(path=os.path.join(SHOTS, "publish-demo-send-390.png"))
            goto_hash(fr, "#/assist", "#as-ask"); fr.click("#as-s-next"); fr.locator("#as-answer").wait_for(timeout=8000)
            check("assistant: an example question shows the recorded scripted answer, labelled a demo recording", "demo recording" in fr.locator("#as-who").inner_text().lower() and len(fr.locator("#as-answer").inner_text()) > 60, fr.locator("#as-who").inner_text())
            fr.fill("#as-q", "Where do I park?"); fr.click("#as-btn"); fr.wait_for_timeout(600)
            e = fr.locator("#as-err"); check("assistant: a typed question says only the example questions are recorded (nothing sent)", e.count() and "demo" in (e.get_attribute("class") or "") and "Nothing was sent" in e.inner_text(), e.inner_text() if e.count() else "")
            goto_hash(fr, "#/intake", "main h1"); fr.wait_for_timeout(300)
            if fr.locator("textarea").count():
                fr.locator("textarea").first.fill("Example change (fictional)"); fr.wait_for_timeout(1600)
                ind = fr.locator("#in-ind").inner_text(); check("intake: autosave says it's kept on this page only and would save to the server in the full version", "on this page only" in ind and "full version" in ind, ind)
            fr.locator("#account-btn").click(); fr.locator("#signout").click(); pg.wait_for_timeout(600)
            check("portal 'Sign out' returns to the demo start", pg.locator("#v-start").is_visible())
            pg.goto(BASE + "#/office/redflag"); fr = wait_frame(pg, "office"); fr.locator("#qlist a.qitem").first.wait_for()
            btn = fr.locator("#qlist .qact button, #qlist button.btn").first
            if btn.count():
                txt = btn.inner_text(); btn.click(); fr.wait_for_timeout(800)
                d = fr.locator(".actfail, #q-st, #do-st").filter(has_text=re.compile("Demo recording")).first
                dlg = fr.locator("dialog[open]")
                ok = d.count() > 0
                if not ok and dlg.count():   # an action that needs input opens a form first: submit it
                    sub = dlg.locator("button.btn:not(.ghost)").first
                    if sub.count(): sub.click(); fr.wait_for_timeout(700); ok = fr.locator("text=Demo recording").count() > 0
                check(f"office one-click action ('{txt.strip()[:30]}') shows the demo notice, not a fake 'Done'", ok and not fr.locator("text=/^Done:/").count())
            c.close()
            # ---- dates move forward with today's date (simulated 12 days later)
            c, pg = ctx("390"); pg.goto(BASE + "#/patient/clean:booked"); fr = wait_frame(pg, "portal"); goto_hash(fr, "#/visits", "#appt-card"); d0 = fr.locator("#appt-card .bigdate").inner_text(); c.close()
            c, pg = ctx("390"); pg.clock.install(time=datetime.datetime.now() + datetime.timedelta(days=12)); pg.goto(BASE + "#/patient/clean:booked"); fr = wait_frame(pg, "portal"); goto_hash(fr, "#/visits", "#appt-card"); d1 = fr.locator("#appt-card .bigdate").inner_text(); c.close()
            def pd(s): s2 = s.split("\u00b7")[0].strip(); return datetime.datetime.strptime(s2.split(", ", 1)[1] + " 2026", "%B %d %Y")
            def tm(s): return s.split("\u00b7")[1].strip() if "\u00b7" in s else ""
            try: diff = (pd(d1) - pd(d0)).days
            except Exception as ex: diff = str(ex)
            check("dates: opened 12 days later, the booked visit is still ahead (moved 12 days), same clock time", diff == 12 and tm(d0) == tm(d1), (d0, d1, diff))
            br.close()
        check("no JavaScript errors anywhere", not ERRS, ERRS[:5])
        check("no requests to any other host (no tracking, no fonts, no CDNs)", not EXT, sorted(set(EXT))[:5])
    finally:
        srv.terminate(); srv.wait(5)
    ok = sum(1 for r in RESULTS if r[1]); print(f"DONE ui_publish: {ok}/{len(RESULTS)} passed; failed: {[r[0] for r in RESULTS if not r[1]]}")
    json.dump(RESULTS, open(os.path.join(HERE, "ui_publish.results.json"), "w"), indent=1)
if __name__ == "__main__": run()
