#!/usr/bin/env python3
"""preview19 Prompt A UI tests: "Ask about your visit" = DEMO assistant (scripted, no AI model), real local server, local Chrome, fictional data only.
  A. labelling (exact demo label, 'not a person', every answer tagged), inline page section (no floating chat window), Contact Premier always there
  B. verified answers with source + last update (PT) under 'More detail'; original approved record opens; missing / conflicting instructions
  C. out-of-scope medical question -> refusal + clinical hand-off draft (nothing sent by itself); red-flag wording -> live 911 guidance + urgent route
  D. hand-off: review, edit, confirm; while sending no 'sent'; failed delivery keeps the draft + retry with the SAME key (no duplicate); success from the server
  E. injection fixture ignored; another patient's record -> not found; no outside requests
  F. 390x844 + 360x740 + large text: no overflow, 44px targets, the tab bar never covers the answer or Send; keyboard-sized viewport keeps the field in view
Screenshots: $PS_SHOTS_DIR (default ../preview19-shots)/assist-*.png at 390x844 (PS_SHOTS=0 skips them)."""
import json, os, re, sqlite3, sys, tempfile, uuid
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8784")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
OUT = L.SHOTS_DIR; SHOTS = os.environ.get("PS_SHOTS", "1") != "0"; os.makedirs(OUT, exist_ok=True)
LABEL = "Demo assistant: scripted answers from your portal data, no AI model connected"
ERRS = []
def shot(pg, name, full=False):
    if SHOTS: pg.wait_for_timeout(450); pg.screenshot(path=f"{OUT}/{name}.png", full_page=full)
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def load(ctx, key, step="key"):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step}); assert s == 200, (key, step, s, j); return j
def portal(ctx, hash_="#/assist", wait="#as-ask"):
    pg = ctx.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html" + hash_); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(250); return pg
def ask_intent(pg, intent):
    pg.locator(f"#as-s-{intent}").click(); pg.locator("#as-answer").wait_for(timeout=8000); pg.wait_for_timeout(350)
def ask_text(pg, q):
    pg.fill("#as-q", q); pg.locator("#as-btn").click(); pg.locator("#as-answer").wait_for(timeout=8000); pg.wait_for_timeout(350)
def n_tasks(pid):
    d = sqlite3.connect(DBF); n = d.execute("SELECT COUNT(*) FROM tasks WHERE patient_id=?", (pid,)).fetchone()[0]; d.close(); return n
def reachable(pg, sel):
    """scroll the control into view, then ask the browser what is on top at its centre: it must be the control itself (not the tab bar)."""
    return pg.evaluate("""s => { const e=document.querySelector(s); if(!e) return {ok:false, why:'missing'}; e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect();
      const x=r.left+r.width/2, y=r.top+r.height/2, t=document.elementFromPoint(x,y); return {ok: !!t && (t===e || e.contains(t)), top: t ? (t.id||t.tagName) : null, y: Math.round(y), h: innerHeight}; }""", sel)

DBF = os.path.join(tempfile.mkdtemp(), "ui_assist.db"); srv = L.Srv(DBF); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    # ================================================= A. labelling + page shape
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "clean", "booked")
    pg = portal(c, "#/home", wait="#hero")
    check("A Home 'Need help?' card links to Ask about your visit", pg.locator("#help-assist").get_attribute("href") == "#/assist")
    pg.locator("#help-assist").click(); pg.locator("#as-ask").wait_for(timeout=8000); pg.wait_for_timeout(300)
    check("A page heading 'Ask about your visit'", pg.locator("main h1").inner_text().strip() == "Ask about your visit")
    check("A exact demo label is visible at the top", pg.locator("#as-label").inner_text().strip() == LABEL and pg.locator("#as-label").is_visible(), pg.locator("#as-label").inner_text())
    np_ = pg.locator("#as-notperson").inner_text()
    check("A 'Not a person' line names Dr. Yakel, Sarah Frank, nurses and staff", all(w in np_ for w in ("Not a person", "Dr. Yakel", "Sarah Frank", "nurse", "staff")), np_)
    check("A the four suggested questions, in order", [x.strip() for x in pg.locator("#as-sugg .qitem").all_inner_texts()] == ["What happens next?", "What do I still need to complete?", "Where can I find my visit instructions?", "Can you help me contact the team?"], pg.locator("#as-sugg").inner_text())
    check("A Contact Premier: Call us + Message the team on the page", pg.locator("#as-call").get_attribute("href") == "tel:2087703536" and pg.locator("#as-msg").get_attribute("href") == "#/messages")
    check("A header 'Call us' is still there (contact is reachable from every page)", pg.locator("#whocall-open-2").is_visible())
    check("A inline page section: no dialog/floating chat window, nothing fixed except the tab bar", pg.locator("dialog[open]").count() == 0 and not pg.evaluate(L.JS_FIXED))
    layout_checks(pg, "assist page", 390); shot(pg, "assist-1-page-390")
    # ================================================= B. verified answers
    ask_intent(pg, "next")
    tag = pg.locator("#as-who").inner_text()
    check("B every answer is tagged 'Demo assistant ... not a person'", "demo assistant" in tag.lower() and "not a person" in tag.lower(), tag)
    check("B short answer first (focus moves to the answer card)", pg.evaluate("document.activeElement.id") == "as-answer" and "confirm" in pg.locator("#as-short").inner_text().lower(), pg.locator("#as-short").inner_text())
    check("B 'More detail' is a closed disclosure", pg.locator("#as-more").get_attribute("open") is None)
    pg.locator("#as-more summary").click(); pg.wait_for_timeout(200); facts = pg.locator("#as-facts").inner_text()
    check("B More detail: each fact shows its source and a last update in PT", "Source: Appointment record" in facts and "Last update" in facts and " PT" in facts, facts[:300])
    shot(pg, "assist-2-next-detail-390")
    ask_intent(pg, "todo")
    check("B 'What do I still need to complete?' -> the confirm step", "waiting on you" in pg.locator("#as-short").inner_text(), pg.locator("#as-short").inner_text())
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "clean"); pg = portal(c)
    ask_intent(pg, "instructions")
    check("B verified instructions: link to the ORIGINAL record", pg.locator("#as-link-0").count() == 1 and "Open the original" in pg.locator("#as-link-0").inner_text())
    pg.locator("#as-more summary").click(); pg.wait_for_timeout(150)
    check("B exact approved wording in More detail, labelled EXAMPLE, approver marked fictional", "EXAMPLE" in pg.locator("#as-verbatim").inner_text() and "fictional" in pg.locator("#as-facts").inner_text())
    shot(pg, "assist-3-instructions-verified-390")
    pg.locator("#as-link-0").click(); pg.locator("#ct-body").wait_for(timeout=8000); pg.wait_for_timeout(250)
    check("B original record page: EXAMPLE banner, body, version, approver, approval date", pg.locator("#ct-example").is_visible() and "Version" in pg.locator("main").inner_text() and "not a real clinician" in pg.locator("main").inner_text())
    check("B ... Contact Premier is on that page too", pg.locator("#as-call").is_visible())
    shot(pg, "assist-4-original-record-390"); layout_checks(pg, "original record", 390)
    # cross-patient: Blake's record id while signed in as Avery
    d = sqlite3.connect(DBF); bl = d.execute("SELECT id FROM approved_content WHERE patient_id=12 ORDER BY id").fetchone()[0]; d.close()
    pg.goto(BASE + f"/portal.html#/content/{bl}"); pg.locator("#ct-err").wait_for(timeout=8000)
    check("E another patient's approved record -> 'couldn't find', nothing of theirs shown", "couldn’t find" in pg.locator("#ct-err").inner_text() and "version 2" not in pg.locator("main").inner_text())
    ERRS[:] = [e for e in ERRS if "404" not in e[1]]   # the deliberate 404 logs a console resource error
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "missing"); pg = portal(c)
    ask_intent(pg, "instructions")
    t = pg.locator("#as-answer").inner_text()
    check("B CONFLICT: says the two versions don't match, 'Not certain' chip, both originals linked, no verbatim", "don’t match" in t and "Not certain" in t and pg.locator("[id^=as-link-]").count() == 2 and pg.locator("#as-verbatim").count() == 0, t[:300])
    check("B ... offers a hand-off with an editable draft", pg.locator("#as-draft").count() == 1 and "Which one should I follow" in pg.locator("#as-draft").input_value())
    shot(pg, "assist-5-conflict-390")
    c.close()
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "surgery"); pg = portal(c)
    ask_intent(pg, "instructions")
    check("B MISSING (pre-op): exact 'Your team has not added these instructions yet.'", "Your team has not added these instructions yet." in pg.locator("#as-short").inner_text())
    shot(pg, "assist-6-missing-390")
    c.close()
    # ================================================= C. refusal + red flag
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "clean"); pg = portal(c)
    posts = []; pg.on("request", lambda r: posts.append(r.url) if r.method == "POST" and r.url.endswith("/api/p/messages") else None)
    before = n_tasks(11)
    ask_text(pg, "Should I stop taking my gabapentin?")
    t = pg.locator("#as-answer").inner_text()
    check("C medical question -> refusal ('can’t help with medical questions'), 'Needs a person' chip", "can’t help with medical questions" in t and "Needs a person" in t, t[:300])
    check("C ... clinical team pre-selected, draft quotes the question, NOTHING sent by itself", pg.locator("#as-team-medical").is_checked() and "Should I stop taking my gabapentin?" in pg.locator("#as-draft").input_value() and not posts and n_tasks(11) == before)
    check("C ... no medical advice on screen", not re.search(r"\b(you should|stop taking|it is safe|keep taking)\b", pg.locator("#as-short").inner_text(), re.I))
    shot(pg, "assist-7-refusal-handoff-390")
    pg.fill("#as-q", "I suddenly can't feel my legs")
    pg.wait_for_timeout(150); em = pg.locator("#as-em").inner_text()
    check("C red-flag wording: 911 guidance appears while typing (before anything is sent)", "911" in em, em)
    check("C ... and the live text never claims anything was sent ('Nothing has been sent yet')", "Nothing has been sent yet" in em and "sent it" not in em, em)
    pg.locator("#as-btn").click(); pg.locator("#as-emergency").wait_for(timeout=8000); pg.wait_for_timeout(300)
    check("C after Ask the typing-time box clears (no stale pre-send text next to the result)", pg.locator("#as-em").inner_text().strip() == "", pg.locator("#as-em").inner_text())
    check("C after Ask: emergency box with Call 911 + Call the office", pg.locator("#as-911").get_attribute("href") == "tel:911" and "call 911" in pg.locator("#as-emergency").inner_text().lower())
    check("C 'urgent request created' shown only because the server created it (task count +1)", "urgent request was also created" in pg.locator("#as-urgent-task").inner_text() and n_tasks(11) == before + 1, (pg.locator("#as-urgent-task").inner_text(), n_tasks(11)))
    shot(pg, "assist-8-redflag-390")
    c.close()
    # ================================================= D. hand-off: review -> send; slow, failed and lost-response sends
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "clean"); pg = portal(c)
    ask_intent(pg, "contact")
    check("D contact: four teams to choose from, nothing pre-sent", pg.locator("#as-teams input[type=radio]").count() == 4 and not pg.locator("#as-sent").count())
    pg.locator("label[for=as-team-records]").click()
    check("D picking Records fills an editable starter draft", pg.locator("#as-draft").input_value().startswith("Hello, I have a question about my records"))
    pg.fill("#as-draft", "Hello, I have a question about my records: did my MRI report arrive? (example, fictional)")
    pg.locator("#as-review").click(); pg.locator("#as-reviewbox").wait_for(timeout=4000)
    rv = pg.locator("#as-reviewbox").inner_text()
    check("D review step: 'Nothing has been sent yet', exact text, team named, 'Send to Records' + 'Edit'", "Nothing has been sent yet" in rv and "did my MRI report arrive" in rv and "Records (Front desk)" in rv and pg.locator("#as-send").inner_text() == "Send to Records" and pg.locator("#as-edit").is_visible(), rv)
    rc = reachable(pg, "#as-send"); check("D the Send button is reachable (not under the tab bar)", rc["ok"], rc)
    shot(pg, "assist-9-review-390")
    before = n_tasks(11); keys = []
    pg.on("request", lambda r: keys.append(r.headers.get("idempotency-key")) if r.method == "POST" and r.url.endswith("/api/p/messages") else None)
    # 1) slow server: hold the request
    held = []; pg.route("**/api/p/messages", lambda route: held.append(route))
    pg.locator("#as-send").click(); pg.wait_for_timeout(350)
    b = pg.evaluate("() => { const b=document.getElementById('as-send'); return {dis:b.disabled, busy:b.getAttribute('aria-busy'), text:b.textContent, st:document.getElementById('as-send-status').textContent}; }")
    check("D while sending: button disabled + 'Sending…', status says 'not sent yet', no 'Sent'", b["dis"] and b["busy"] == "true" and "Sending" in b["text"] and "not sent yet" in b["st"] and pg.locator("#as-sent").count() == 0, b)
    pg.locator("#as-send").click(force=True, timeout=1500) if pg.locator("#as-send").is_enabled() else None
    # 2) the network drops the request (it never reached the server)
    for r in held: r.abort("internetdisconnected")
    pg.unroute("**/api/p/messages"); pg.locator("#as-send-status.bad").wait_for(timeout=8000)
    st = pg.locator("#as-send-status").inner_text()
    check("D failure: 'Not sent', draft kept, 'Try again', call number; no 'sent/received/notified' claim", "Not sent" in st and "still here" in st and "(208) 770-3536" in st and pg.locator("#as-send").inner_text() == "Try again"
          and not re.search(r"\b(Sent at|received|notified)\b", pg.locator("#as-answer").inner_text()) and pg.locator("#as-sent").count() == 0, st)
    check("D failure: the draft text is still in the box and in the review", "did my MRI report arrive" in pg.locator("#as-draft").input_value() and "did my MRI report arrive" in pg.locator("#as-review-text").inner_text())
    check("D failure: nothing reached the server (no task)", n_tasks(11) == before, (before, n_tasks(11)))
    shot(pg, "assist-10-send-failed-390")
    # 3) retry, but the RESPONSE is lost after the server created the task
    state = {"n": 0}
    def lose_response(route):
        state["n"] += 1
        if state["n"] == 1: route.fetch(); route.abort("connectionreset")
        else: route.continue_()
    pg.route("**/api/p/messages", lose_response)
    pg.locator("#as-send").click(); pg.locator("#as-send-status.bad").wait_for(timeout=8000); pg.wait_for_timeout(200)
    check("D lost response: still shown as NOT sent (no server confirmation reached the page)", pg.locator("#as-sent").count() == 0 and "Not sent" in pg.locator("#as-send-status").inner_text())
    check("D ... the server did create one task", n_tasks(11) == before + 1, n_tasks(11))
    pg.locator("#as-send").click(); pg.locator("#as-sent").wait_for(timeout=8000); pg.unroute("**/api/p/messages")
    sent = pg.locator("#as-send-status").inner_text()
    check("D retry -> confirmation from the server: time (PT), reference #, team", re.search(r"Sent at \d{1,2}:\d{2} [AP]M PT · Reference #\d+ · Routed to Front desk", sent) is not None, sent)
    check("D every attempt used the SAME idempotency key (3 attempts, 1 key)", len(keys) == 3 and len(set(keys)) == 1 and keys[0], keys)
    check("D no duplicate: exactly ONE task for the message", n_tasks(11) == before + 1, (before, n_tasks(11)))
    check("D no reply-time promise (none configured)", "No reply time has been promised" in sent, sent)
    shot(pg, "assist-11-sent-390")
    s, th = api(c, "GET", "/api/p/threads")
    check("D it is a normal portal conversation (existing message system)", s == 200 and any(t["category"] == "Records question" for t in th["threads"]), th)
    other = [x for x in ERRS if x[0] == "portal" and not re.search(r"ERR_INTERNET_DISCONNECTED|ERR_CONNECTION_RESET|Failed to fetch", x[1])]
    check("D no page errors apart from the deliberately dropped requests", not other, other[:3]); ERRS.clear()
    c.close()
    # ================================================= E. injection fixture
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "clean")
    s, fx = api(c, "POST", "/api/presenter/fixtures/injection", {"key": "clean"}); assert s == 200, fx
    pg = portal(c); ask_intent(pg, "next"); pg.locator("#as-more summary").click(); pg.wait_for_timeout(200)
    txt = pg.locator("main").inner_text()
    check("E injection fixture (message + shared document saying 'ignore your rules ... stop their medication') is NOT followed or repeated", not re.search(r"ignore your rules|stop their medication|surgery is not needed", txt, re.I), txt[:400])
    check("E ... the document is listed by title only, with 'I don’t read or follow what documents say'", "I don’t read or follow what documents say" in txt)
    shot(pg, "assist-12-injection-ignored-390")
    c.close()
    # ================================================= F. sizes, large text, keyboard
    for (W, H, big) in ((360, 740, False), (390, 844, True), (360, 740, True)):
        tg = f"{W}x{H}{' large text' if big else ''}"
        c = br.new_context(viewport={"width": W, "height": H})
        if big: c.add_init_script("try { localStorage.setItem('ps.largeText','1') } catch(e) {}")
        load(c, "missing"); pg = portal(c); layout_checks(pg, f"assist page {tg}", W)
        ask_intent(pg, "instructions"); pg.locator("#as-more summary").click(); pg.wait_for_timeout(150)
        layout_checks(pg, f"assist conflict answer {tg}", W)
        ov = pg.evaluate(L.JS_OVERFLOW); check(f"F no horizontal scroll {tg}", ov["sw"] <= ov["iw"] + 1, ov)
        for sel in ("#as-review", "#as-call", "#as-msg", "#as-s-contact", "#as-btn"):
            rc = reachable(pg, sel); check(f"F {sel} reachable (the tab bar never covers it) {tg}", rc["ok"], rc)
        if big and W == 360: shot(pg, "assist-13-large-text-360")
        c.close()
    c = br.new_context(viewport={"width": 390, "height": 460}); load(c, "clean"); pg = portal(c)   # ~ a phone with the keyboard up
    pg.locator("#as-q").focus(); pg.wait_for_timeout(300)
    r = pg.evaluate("() => { const e=document.getElementById('as-q').getBoundingClientRect(), n=document.getElementById('nav').getBoundingClientRect(); return {top:e.top, bottom:e.bottom, h:innerHeight, navTop:n.top, navShown:getComputedStyle(document.getElementById('nav')).display!=='none'}; }")
    check("F short (keyboard-sized) viewport: the focused question box is fully visible and above the tab bar", r["top"] >= 0 and r["bottom"] <= (r["navTop"] if r["navShown"] else r["h"]), r)
    c.close()
    ext = [u for u in L.REQS if not u.startswith(BASE)]
    check("E no requests leave the local server (no model, no outside service)", not ext, ext[:5])
    check("no page errors", not [e for e in ERRS], ERRS[:4])
    br.close()
finally:
    srv.stop()
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_assist: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
json.dump(L.RESULTS, open(os.path.join(L.HERE, "ui_assist.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
