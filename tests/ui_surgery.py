#!/usr/bin/env python3
"""preview19 Prompt B UI tests: before / after surgery (real local server, local Chrome, fictional data only).
  A. pre-op Home: verified facts ('Not added yet' otherwise), your tasks vs the team's, exact missing-instructions sentence, no readiness wording
  B. post-op Home: the check-in first and it FITS with its Send button on a 390x844 screen (measured), 911 box + contact always visible
  C. states: submitting (no receipt), failed (answers kept, 911 still there, retry with the SAME key), submitted (server receipt, verbatim words)
  D. the four fictional examples: ordinary, request for help, concern for staff review, failed submission; history list
  E. reachability: every control in main can be scrolled clear of the bottom tab bar - 360x740 and 390x844, normal and large text
  F. office Settings: call-back wording empty by default; example escalation rule table marked as needing Dr. Yakel's approval
Screenshots: $PS_SHOTS_DIR (default ../preview19-shots)/surgery-*.png (PS_SHOTS=0 skips them)."""
import json, os, re, sqlite3, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8786")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
OUT = L.SHOTS_DIR; SHOTS = os.environ.get("PS_SHOTS", "1") != "0"; os.makedirs(OUT, exist_ok=True)
ERRS = []; MEAS = {}
def shot(pg, name, full=False):
    if SHOTS: pg.wait_for_timeout(450); pg.screenshot(path=f"{OUT}/{name}.png", full_page=full)
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def load(ctx, key, step="key", office_as=None):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "office_as": office_as}); assert s == 200, (key, step, s, j); return j
def portal(ctx, hash_="#/home", wait="main h1"):
    pg = ctx.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html" + hash_); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(300); return pg
def n_tasks():
    d = sqlite3.connect(DBF); n = d.execute("SELECT COUNT(*) FROM tasks WHERE patient_id=18 AND type='postop_concern'").fetchone()[0]; d.close(); return n
def scroll_to(pg, sel): pg.evaluate("s => document.querySelector(s).scrollIntoView({block:'center'})", sel); pg.wait_for_timeout(250)
JS_REACH = """() => { const bad=[]; let n=0; const nav=document.getElementById('nav'); const navOn = nav && !nav.hidden && getComputedStyle(nav).display!=='none';
  const els=[...document.querySelectorAll('main a, main button, main textarea, main summary, main label.choice, main input[type=text]')];
  for (const e of els) { if (e.closest('details:not([open])') && e.tagName!=='SUMMARY') continue; const cs=getComputedStyle(e); if (cs.display==='none'||cs.visibility==='hidden') continue;
    let r=e.getBoundingClientRect(); if (!r.width||!r.height) continue; n++;
    e.scrollIntoView({block:'center'}); r=e.getClientRects()[0] || e.getBoundingClientRect();   /* a wrapped inline link: test its first line box */ const x=r.left+Math.min(r.width/2, 40), y=r.top+r.height/2, t=document.elementFromPoint(x,y);
    const navTop = navOn ? nav.getBoundingClientRect().top : innerHeight;
    if (!t || !(t===e || e.contains(t) || (e.tagName==='LABEL' && t===document.getElementById(e.htmlFor))) || r.top < 0 || r.bottom > navTop + 0.5) bad.push((e.id||e.textContent.trim().slice(0,30)||e.tagName)+' -> '+(t?(t.id||t.tagName):'none'));
  }
  window.scrollTo(0, document.documentElement.scrollHeight); const last=els.filter(e=>{const r=e.getBoundingClientRect(); return r.width&&r.height&&!e.closest('details:not([open])');}).pop();
  const lr = last ? last.getBoundingClientRect() : null, navTop = navOn ? nav.getBoundingClientRect().top : innerHeight;
  return {n, bad: bad.slice(0,8), lastOk: !lr || lr.bottom <= navTop + 0.5, last: last ? (last.id||last.tagName) : null}; }"""
def reach_all(pg, name):
    r = pg.evaluate(JS_REACH); check(f"E every control ({r['n']}) can be scrolled clear of the tab bar; the last one too: {name}", r["n"] > 3 and not r["bad"] and r["lastOk"], r)

DBF = os.path.join(tempfile.mkdtemp(), "ui_surgery.db"); srv = L.Srv(DBF); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    # ================================================= A. before surgery
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "key"); pg = portal(c, wait="#hero")
    check("A heading for the pre-op state: 'Your surgery is being planned' (no 'ready')", pg.locator("#h-na").inner_text() == "Your surgery is being planned", pg.locator("#h-na").inner_text())
    f = pg.locator("#surg-facts").inner_text()
    check("A Your surgery: procedure + date marked Example; date confirmation with who/when (PT)", "Spine surgery (example)" in f and "example date" in pg.locator("#sf-date").inner_text().lower() and "Confirmed by" in f and " PT" in f, f)
    check("A surgeon, place and arrival time are 'Not added yet' (never guessed)", all("Not added yet" in pg.locator(s).inner_text() for s in ("#sf-surgeon", "#sf-where", "#sf-arrive")))
    you, team = pg.locator("#preop-you").inner_text(), pg.locator("#preop-team").inner_text()
    check("A 'Your tasks' holds only the written-instructions step", pg.locator("#preop-you li").count() == 1 and "instructions" in you.lower(), you)
    check("A 'What our team is handling' lists the 5 office items, each with who handles it", pg.locator("#preop-team li").count() == 5 and team.count("Handled by:") == 5, team[:300])
    check("A exact sentence when the surgical team has not added instructions", pg.locator("#preop-instr-missing").inner_text() == "Your team has not added these instructions yet.")
    mt = pg.evaluate("() => { const m=document.querySelector('main').cloneNode(true); m.querySelectorAll('#preop-noclear').forEach(x => x.remove()); return m.innerText; }")   # the one sentence that NEGATES readiness is excluded
    check("A no readiness or clearance claims ('ready for surgery', 'cleared', 'all set')", not re.search(r"ready for surgery|you(’|')re cleared|you are cleared|all set for surgery|cleared for surgery", mt, re.I), "")
    check("A the list says ticks are not a clearance", "do not mean you are cleared or ready" in pg.locator("#preop-noclear").inner_text())
    shot(pg, "surgery-1-preop-home-390")
    scroll_to(pg, "#preop-split"); shot(pg, "surgery-2-preop-who-does-what-390")
    scroll_to(pg, "#preop-instr"); shot(pg, "surgery-3-preop-instructions-missing-390")
    layout_checks(pg, "pre-op Home", 390)
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
    check("A all pre-op items done after surgery: still no 'cleared/ready' wording anywhere", not re.search(r"ready for surgery|cleared for surgery|you are cleared", pg.locator("main").inner_text(), re.I))
    c.close()
    # ================================================= B. after surgery: layout + measurement
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
    order = pg.evaluate("() => [...document.querySelectorAll('main section.card')].map(s => s.id)")
    check("B the check-in is the first card, then Urgent help, then contact", order[:3] == ["ck-card", "ck-911", "help"], order)
    m = pg.evaluate("""() => { const c=document.getElementById('ck-card').getBoundingClientRect(), s=document.getElementById('ck-send').getBoundingClientRect(), n=document.getElementById('nav').getBoundingClientRect();
      return {card_top: Math.round(c.top), card_h: Math.round(c.height), send_bottom: Math.round(s.bottom), nav_top: Math.round(n.top), vh: innerHeight}; }""")
    MEAS["postop_390x844_first_screen"] = m
    check(f"B MEASURED at 390x844 with no scrolling: check-in card {m['card_h']}px tall, Send bottom at {m['send_bottom']}px, tab bar top at {m['nav_top']}px -> Send fully visible with >= 16px to spare", m["send_bottom"] + 16 <= m["nav_top"], m)
    check("B check-in card is short: <= 560px including the Send button", m["card_h"] <= 560, m)
    check("B three large answer choices (>= 44px each)", pg.evaluate("() => [...document.querySelectorAll('#ck-form label.choice')].map(l => l.getBoundingClientRect().height)") >= [44, 44, 44] and pg.locator("#ck-form label.choice").count() == 3)
    check("B choices make no call-back promise ('please call me' removed)", "call me" not in pg.locator("#ck-form").inner_text().lower())
    check("B 911 box and contact are visible on the page without depending on any send", pg.locator("#ck-call911").get_attribute("href") == "tel:911" and pg.locator("#ck-calloffice").is_visible() and pg.locator("#help-call").count() == 1)
    check("B no promise of a call or response time anywhere on the post-op Home", not re.search(r"will (phone|call) you|call you back|nurse will", pg.locator("main").inner_text(), re.I), "")
    shot(pg, "surgery-4-postop-checkin-390")
    layout_checks(pg, "post-op Home", 390)
    # ================================================= C. states: submitting -> failed -> retry -> submitted (request for help)
    pg.locator("label[for=ck-question]").click(); words = "Can I shower yet?\nThe leaflet says \"wait\" (example, fictional)."
    pg.fill("#ck-note", words)
    keys = []; pg.on("request", lambda r: keys.append(r.headers.get("idempotency-key")) if r.method == "POST" and "/api/p/checkin/" in r.url else None)
    held = []; pg.route("**/api/p/checkin/*", lambda route: held.append(route)); n0 = n_tasks()
    pg.locator("#ck-send").click(); pg.wait_for_timeout(350)
    b = pg.evaluate("() => { const b=document.getElementById('ck-send'); return {dis:b.disabled, busy:b.getAttribute('aria-busy'), text:b.textContent, st:document.getElementById('ck-st').textContent, receipt: !!document.getElementById('ck-receipt')}; }")
    check("C SUBMITTING: button disabled 'Sending…', status 'not sent yet', no receipt shown", b["dis"] and b["busy"] == "true" and "Sending" in b["text"] and "not sent yet" in b["st"] and not b["receipt"], b)
    check("C ... 911 guidance still on screen while sending", pg.locator("#ck-911").is_visible())
    for r in held: r.abort("internetdisconnected")
    pg.unroute("**/api/p/checkin/*"); pg.locator("#ck-st.bad").wait_for(timeout=8000); st = pg.locator("#ck-st").inner_text()
    check("C FAILED: 'Not sent', answers still here, 'Try again', call + 911 in the message", "Not sent" in st and "still here" in st and "911" in st and pg.locator("#ck-send").inner_text() == "Try again" and pg.locator("#ck-question").is_checked() and pg.locator("#ck-note").input_value() == words, st)
    check("C FAILED: 911 + office call buttons right in the failure message (never depends on sending)", pg.locator("#ck-fail-911").get_attribute("href") == "tel:911" and pg.locator("#ck-fail-911").is_visible())
    check("C FAILED: nothing claims it reached anyone; no receipt; no task on the server", pg.locator("#ck-receipt").count() == 0 and "reached" not in pg.locator("#ck-card").inner_text() and n_tasks() == n0)
    check("C FAILED: the Urgent help box is still visible and reachable", pg.locator("#ck-911").is_visible() and pg.evaluate("() => { const e=document.getElementById('ck-call911'); e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); return document.elementFromPoint(r.left+r.width/2, r.top+r.height/2)===e; }"))
    scroll_to(pg, "#ck-card"); pg.evaluate("document.getElementById('ck-st').scrollIntoView({block:'end'})"); shot(pg, "surgery-8-failed-submission-390")
    pg.locator("#ck-send").click(); pg.locator("#ck-receipt").wait_for(timeout=8000); pg.wait_for_timeout(300)
    rc = pg.locator("#ck-receipt").inner_text()
    check("C SUBMITTED (request for help): 'reached the care team', server reference CI-n, time in PT", "reached the care team" in rc and re.search(r"Reference CI-\d+", rc) and " PT" in rc, rc)
    check("C ... the patient's words are shown exactly as sent (newline and quotes kept)", pg.locator("#ck-receipt-note").inner_text() == words, pg.locator("#ck-receipt-note").inner_text())
    check("C ... what happened: sent to the care team for review, with the task number; no call-back promise", "Sent to the care team for review" in rc and re.search(r"task #\d+", rc) and "No call-back time has been promised" in rc, rc)
    check("C retry used the SAME idempotency key; exactly one task", len(keys) == 2 and keys[0] == keys[1] and n_tasks() == n0 + 1, (keys, n_tasks()))
    check("C focus moves to the receipt", pg.evaluate("document.activeElement.id") == "ck-receipt")
    shot(pg, "surgery-6-help-request-receipt-390")
    pg.wait_for_timeout(600); h = pg.locator("#ck-history").inner_text()
    check("D history list shows the check-in with its reference and the verbatim words", re.search(r"Ref CI-\d+", h) and "Can I shower yet?" in h, h)
    scroll_to(pg, "#ck-history-card"); shot(pg, "surgery-9-history-390")
    other = [x for x in ERRS if x[0] == "portal" and "ERR_INTERNET_DISCONNECTED" not in x[1] and "Failed to fetch" not in x[1]]
    check("C no page errors apart from the deliberately dropped request", not other, other[:3]); ERRS.clear()
    c.close()
    # ================================================= D. ordinary + concern examples
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
    pg.locator("label[for=ck-ok]").click(); pg.fill("#ck-note", "Sleeping better, walked to the mailbox (example)."); pg.locator("#ck-send").click(); pg.locator("#ck-receipt").wait_for(timeout=8000)
    rc = pg.locator("#ck-receipt").inner_text()
    check("D ORDINARY check-in: 'saved', honest that it did not create a task, no 'reached the care team'", "Your check-in is saved" in rc and "did not create a task" in rc and "reached the care team" not in rc, rc)
    shot(pg, "surgery-5-ordinary-receipt-390")
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
    pg.locator("label[for=ck-concern]").click(); pg.locator("#ck-send").click(); pg.wait_for_timeout(200)
    check("D a worry without words -> inline prompt to add a few words; nothing sent", "add a few words" in pg.locator("#ck-st").inner_text() and n_tasks() == 0)
    pg.fill("#ck-note", "The wound area looks different today and I am worried (example)."); pg.locator("#ck-send").click(); pg.locator("#ck-receipt").wait_for(timeout=8000)
    rc = pg.locator("#ck-receipt").inner_text()
    check("D CONCERN: 'Sent to the care team as URGENT' with the task number (only after the task exists)", "Sent to the care team as URGENT" in rc and re.search(r"task #\d+", rc) and n_tasks() == 1, rc)
    shot(pg, "surgery-7-concern-receipt-390")
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
    pg.locator("label[for=ck-question]").click(); pg.fill("#ck-note", "I suddenly can't feel my legs (example)")
    pg.wait_for_timeout(200); em = pg.locator("#ck-em").inner_text()
    check("D emergency words while typing -> 911 guidance at once, and it says nothing has been sent yet", "911" in em and "Nothing has been sent yet" in em, em)
    c.close()
    # ================================================= E. reachability at two sizes, normal + large text, pre-op and post-op
    for (W, H) in ((360, 740), (390, 844)):
        for big in (False, True):
            tg = f"{W}x{H}{' large text' if big else ''}"
            for step, wait in (("key", "#preop-split"), ("postop", "#ck-card")):
                c = br.new_context(viewport={"width": W, "height": H})
                if big: c.add_init_script("try { localStorage.setItem('ps.largeText','1') } catch(e) {}")
                load(c, "surgery", step); pg = portal(c, wait=wait)
                if step == "postop":
                    pg.evaluate("document.querySelectorAll('main details').forEach(d => d.open = true)")
                reach_all(pg, f"{'pre-op' if step == 'key' else 'post-op'} {tg}")
                ov = pg.evaluate(L.JS_OVERFLOW); check(f"E no horizontal scroll: {step} {tg}", ov["sw"] <= ov["iw"] + 1, ov)
                if step == "postop":
                    m = pg.evaluate("() => { window.scrollTo(0,0); const s=document.getElementById('ck-send').getBoundingClientRect(), n=document.getElementById('nav').getBoundingClientRect(), c=document.getElementById('ck-card').getBoundingClientRect(); return {card_h: Math.round(c.height), send_bottom: Math.round(s.bottom), nav_top: Math.round(n.top)}; }")
                    MEAS[f"postop_{W}x{H}{'_large' if big else ''}"] = m
                    if big and W == 360: shot(pg, "surgery-10-postop-large-text-360")
                c.close()
    # ================================================= F. office settings
    c = br.new_context(viewport={"width": 1280, "height": 900}); load(c, "surgery", "postop", office_as="admin")
    pg = c.new_page(); watch(pg, "office"); pg.goto(BASE + "/office.html#/settings"); pg.locator("#esc-table").wait_for(timeout=10000); pg.wait_for_timeout(300)
    check("F call-back wording field is empty by default", pg.locator("#cbp").input_value() == "")
    check("F escalation rules shown read-only and marked as needing Dr. Yakel's approval (approved by nobody yet)", "NEEDS DR. YAKEL" in pg.locator("#esc-status").inner_text() and "nobody yet" in pg.locator("#esc-status").inner_text() and pg.locator("#esc-table tbody tr").count() >= 9)
    scroll_to(pg, "#set-cbp"); shot(pg, "surgery-11-office-settings-escalation-1280")
    c.close()
    ext = [u for u in L.REQS if not u.startswith(BASE)]
    check("no requests leave the local server", not ext, ext[:5])
    check("no page errors", not ERRS, ERRS[:4])
    br.close()
finally:
    srv.stop()
json.dump(MEAS, open(f"{OUT}/surgery-checkin-measurements.json", "w"), indent=1)
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_surgery: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
print("measurements:", json.dumps(MEAS))
json.dump(L.RESULTS, open(os.path.join(L.HERE, "ui_surgery.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
