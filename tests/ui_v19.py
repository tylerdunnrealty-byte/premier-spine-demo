#!/usr/bin/env python3
"""preview19 UI tests (real local server on 127.0.0.1, local Chrome, fictional data only).
  A. the complete intake flow at 360x740 and 390x844: first question high on the screen, one progress indicator with step names,
     inline errors (aria-describedby, aria-invalid, focus to the first error), answers kept going Back, real server draft (reload),
     review, double-click Send -> one request, clear success state (no auto-redirect), server refuses a 2nd submission
  B. failure state: the network drops the first Send -> clear failure message, nothing lost, retry re-uses the SAME idempotency key
  C. large text (125%) at 360x740 through every intake step, the success screen and Home: no horizontal scroll, nothing clipped
  D. mobile chrome: visible "Call us", labelled Account menu (text size, settings, about, sign out), solid tab bar that never
     covers text, safe-area CSS, focused field kept in view on a short (keyboard-sized) viewport, one "About this demo" sheet
  E. Home in six fictional states at 390x844: the first card reflects server state, one dominant action only when needed,
     no "nothing needed" + "call to schedule" contradiction, office-owned records say so with verified status + time
Screenshots go to $PS_SHOTS_DIR (default ../preview19-shots)/ (PS_SHOTS=0 skips them)."""
import json, os, re, sys, tempfile, time, uuid
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8782")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
OUT = L.SHOTS_DIR; SHOTS = os.environ.get("PS_SHOTS", "1") != "0"; os.makedirs(OUT, exist_ok=True)
ERRS = []; HEIGHTS = {}
def shot(pg, name, full=False):
    if SHOTS: pg.wait_for_timeout(450); pg.screenshot(path=f"{OUT}/{name}.png", full_page=full)
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def load(ctx, key, step="key", office_as=None):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "office_as": office_as}); assert s == 200, (key, step, s, j); return j
def portal(ctx, hash_="#/home", wait="main h1"):
    pg = ctx.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html" + hash_); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(300); return pg
def in_view(pg, sel):
    return pg.evaluate("s => { const e=document.querySelector(s); if(!e) return null; const r=e.getBoundingClientRect(); return {top:r.top, bottom:r.bottom, h:innerHeight, ok:r.top>=-1 && r.bottom<=innerHeight+1}; }", sel)
JS_TEXTCLIP = """() => { const o=[]; for (const el of document.querySelectorAll('main *, header *, nav *, .demobar, .protobar, dialog[open] *')) {
  const cs=getComputedStyle(el); if (cs.display==='none'||cs.visibility==='hidden') continue; const r=el.getBoundingClientRect(); if (!r.width||!r.height) continue; if ((r.width<=1.5 && r.height<=1.5) || (cs.position==='absolute' && cs.clip && cs.clip!=='auto')) continue;  /* visually-hidden text for screen readers */
  if (el.closest('.sr, .choice.chipc input') || el.classList.contains('sr') || (el.tagName==='INPUT' && (el.type==='radio'||el.type==='checkbox'))) continue;
  if (r.right > innerWidth + 1 || r.left < -1) o.push('offscreen:'+(el.id||el.className||el.tagName)+':'+Math.round(r.left)+'-'+Math.round(r.right));
  const ox=cs.overflowX; if ((ox==='hidden'||ox==='clip') && el.scrollWidth > el.clientWidth + 2 && el.textContent.trim()) o.push('clipped:'+(el.id||el.className||el.tagName));
  const tov=cs.textOverflow; if (tov==='ellipsis' && el.scrollWidth > el.clientWidth + 1) o.push('ellipsis:'+(el.id||el.tagName)); }
  return [...new Set(o)].slice(0,12); }"""
def big_checks(pg, name):
    ov = pg.evaluate(L.JS_OVERFLOW); check(f"large text: no horizontal scroll: {name}", ov["sw"] <= ov["iw"] + 1, ov)
    tc = pg.evaluate(JS_TEXTCLIP); check(f"large text: no clipped or off-screen text/controls: {name}", not tc, tc)
def err_state(pg, err_id, focus_id):
    return pg.evaluate("""([e, f]) => { const el=document.getElementById(e), a=document.activeElement, r=el?el.getBoundingClientRect():null;
      const desc=(a && a.getAttribute('aria-describedby')||'').split(/\\s+/);
      return {visible: !!el && !el.hidden && !!el.textContent.trim(), text: el?el.textContent:'', focus: a?a.id:'', described: desc.includes(e), inview: !!r && r.top>=0 && r.bottom<=innerHeight,
              invalid: !!document.querySelector('[aria-invalid=true]')}; }""", [err_id, focus_id])

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "ui_v19.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    # ================================================= A. complete intake flow at two phone sizes
    for (W, H) in ((360, 740), (390, 844)):
        tag = f"@{W}x{H}"
        c = br.new_context(viewport={"width": W, "height": H}); load(c, "clean", "intake")
        pg = portal(c, wait="#hero")
        check(f"A Home (intake owed): ONE dominant button and it is the intake {tag}", pg.locator("#hero .btn.big").count() == 1 and pg.locator("#hero #na-intake.btn.big").count() == 1, pg.locator("#hero").inner_text()[:160])
        pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000); pg.wait_for_timeout(400)
        y = pg.evaluate("() => document.querySelector('label[for=pf-name-ok]').getBoundingClientRect().bottom")
        check(f"A first answerable question is fully on the first screen without scrolling (bottom at {round(y)}px of {H}) {tag}", y <= H - 20, y)
        HEIGHTS[f"intake_first_question_bottom_{W}"] = round(y)
        check(f"A one progress indicator with a meaningful step name {tag}", pg.locator("[role=progressbar]").count() == 1 and pg.locator("#in-stepn").inner_text() == "Step 1 of 6: About you" and pg.locator("#in-bar").get_attribute("aria-valuetext") == "Step 1 of 6: About you" and pg.locator("#in-nextname").inner_text() == "Next: Referral and insurance", pg.locator("#in-stepn").inner_text())
        names = pg.evaluate("() => [...document.querySelectorAll('#in-steps .lab')].map(e => e.textContent)")
        check(f"A all six step names are meaningful (no bare numbers) {tag}", len(names) == 6 and all(len(n) > 4 and not n.lower().startswith("step") for n in names), names)
        check(f"A focus mode: the bottom tab bar is hidden while filling in the form {tag}", pg.locator("#nav").is_hidden())
        check(f"A pre-filled values are NOT shown as confirmed: no answer pre-selected, each says 'Not confirmed yet' {tag}",
              pg.locator("#in-step-1 input[type=radio]:checked").count() == 0 and all(t == "Not confirmed yet" for t in pg.locator("#in-step-1 .pfst").all_inner_texts()), pg.locator("#in-step-1 .pfst").all_inner_texts())
        shot(pg, f"intake-1-first-question-{W}")
        # error state: Next with nothing answered
        pg.locator("#in-next").click(); pg.wait_for_timeout(350)
        e = err_state(pg, "pf-err-name", "pf-name-ok")
        check(f"A error: explained next to the field, focus on the first error, aria-describedby + aria-invalid, error in view {tag}", e["visible"] and e["focus"] == "pf-name-ok" and e["described"] and e["invalid"] and e["inview"], e)
        check(f"A error: stays on step 1 and the summary line says what to do {tag}", pg.locator("#in-step-1").is_visible() and "attention" in pg.locator("#in-st").inner_text(), pg.locator("#in-st").inner_text())
        shot(pg, f"intake-2-error-state-{W}")
        pg.locator("label[for=pf-name-ok]").click()
        check(f"A answering clears that field's error and shows 'You confirmed this' {tag}", pg.locator("#pf-err-name").is_hidden() and "You confirmed this" in pg.locator("#pf-st-name").inner_text())
        if pg.locator("label[for=pf-dob-ok]").count(): pg.locator("label[for=pf-dob-ok]").click()
        pg.locator("label[for=pf-phone-change]").click(); pg.wait_for_timeout(150)
        check(f"A choosing 'No, change it' opens the correction box and moves focus into it {tag}", pg.evaluate("document.activeElement.id") == "pf-c-phone")
        pg.locator("#in-next").click(); pg.wait_for_timeout(300); e = err_state(pg, "pf-cerr-phone", "pf-c-phone")
        check(f"A empty correction -> error next to the box, focus in the box {tag}", e["visible"] and e["focus"] == "pf-c-phone" and e["described"], e)
        pg.fill("#pf-c-phone", "(208) 555-0142 (example)"); pg.locator("#in-next").click(); pg.locator("#in-step-2").wait_for(state="visible")
        check(f"A Next goes to step 2 and the indicator follows {tag}", pg.locator("#in-stepn").inner_text() == "Step 2 of 6: Referral and insurance")
        for k in pg.evaluate("() => [...document.querySelectorAll('#in-step-2 .pf')].map(e => e.id.slice(3))"): pg.locator(f"label[for=pf-{k}-ok]").click()
        if pg.locator("#in-fac").count(): pg.fill("#in-fac", "")
        pg.locator("#in-next").click(); pg.locator("#in-step-3").wait_for(state="visible")
        for k in pg.evaluate("() => [...document.querySelectorAll('#in-step-3 .pf')].map(e => e.id.slice(3))"): pg.locator(f"label[for=pf-{k}-ok]").click()
        pg.fill("#in-med", "Example: ibuprofen at night (fictional)")
        pg.locator("#in-next").click(); pg.locator("#in-step-4").wait_for(state="visible")
        # Back keeps answers
        pg.locator("#in-back").click(); pg.locator("#in-step-3").wait_for(state="visible")
        check(f"A Back: step 3 answer is still there {tag}", pg.input_value("#in-med") == "Example: ibuprofen at night (fictional)")
        pg.locator("#in-back").click(); pg.locator("#in-back").click(); pg.locator("#in-step-1").wait_for(state="visible")
        check(f"A Back to step 1: 'change it' and the correction are still there {tag}", pg.locator("#pf-phone-change").is_checked() and pg.input_value("#pf-c-phone") == "(208) 555-0142 (example)")
        for _ in range(3): pg.locator("#in-next").click(); pg.wait_for_timeout(150)
        pg.locator("#in-step-4").wait_for(state="visible")
        pg.locator("#in-next").click(); pg.wait_for_timeout(300); e = err_state(pg, "cp-err", "cp-text")
        check(f"A step 4: required contact question -> inline error + focus on its first choice {tag}", e["visible"] and e["focus"].startswith("cp-") and e["described"], e)
        pg.locator("label[for=cp-text]").click(); pg.locator("label[for=mt-0]").click()
        pg.locator("#in-next").click(); pg.locator("#in-step-5").wait_for(state="visible")
        pg.locator("#in-next").click(); pg.wait_for_timeout(300); e = err_state(pg, "rf-err", "")
        check(f"A step 5: unanswered safety question -> inline error + focus on a choice {tag}", e["visible"] and e["focus"].startswith("rf-") and e["described"], e)
        # keyboard-sized viewport: the last field of the step stays in view when focused (visualViewport handling)
        pg.locator("label[for=rf-none]").click()
        pg.set_viewport_size({"width": W, "height": 420}); pg.evaluate("window.scrollTo(0,0)"); pg.locator("#in-other").focus(); pg.wait_for_timeout(700)
        iv = in_view(pg, "#in-other")
        check(f"A keyboard-sized viewport (420px tall, simulated): focusing the last field scrolls it fully into view {tag}", iv and iv["ok"], iv)
        pg.set_viewport_size({"width": W, "height": H}); pg.wait_for_timeout(300)
        pg.locator("#in-ind").filter(has_text="Draft saved on the server").wait_for(timeout=8000)
        # real save-and-return: reload -> lands on the review step with everything kept
        pg.reload(); pg.locator("#intake").wait_for(timeout=8000); pg.wait_for_timeout(400)
        check(f"A save-and-return (server draft): after reload it opens on 'Review and send' with answers kept {tag}", pg.locator("#in-step-6").is_visible() and "Change to: (208) 555-0142 (example)" in pg.locator("#in-review").inner_text() and "ibuprofen" in pg.locator("#in-review").inner_text(), pg.locator("#in-stepn").inner_text())
        s, form = api(c, "GET", "/api/p/intake")
        check(f"A the server holds the draft and per-field status (phone corrected, name confirmed, NOT patient-confirmed yet) {tag}", form["draft"] and form["field_status"]["phone"]["state"] == "corrected" and form["field_status"]["name"]["state"] == "confirmed" and not form["field_status"]["name"]["patient_confirmed"], form.get("field_status"))
        check(f"A review: each section has a 'Change' button {tag}", pg.locator("#in-review button[id^=in-edit-]").count() >= 4)
        shot(pg, f"intake-3-review-{W}")
        # send without the final tick -> inline error at the confirm box
        pg.locator("#in-send").click(); pg.wait_for_timeout(300); e = err_state(pg, "cc-err", "in-confirm")
        check(f"A review: Send without 'These answers are right' -> error next to it, focus on it {tag}", e["visible"] and e["focus"] == "in-confirm" and e["described"], e)
        pg.locator("label[for=in-confirm]").click()
        pg.evaluate("document.getElementById('in-send').scrollIntoView({block:'nearest'})"); iv = in_view(pg, "#in-send")
        check(f"A the Send button can be brought fully into view (nothing fixed covers it) {tag}", iv and iv["ok"], iv)
        # duplicate protection: slow the server answer, double-click Send
        posts = []; pg.on("request", lambda r: posts.append(r.headers.get("idempotency-key")) if r.method == "POST" and r.url.endswith("/api/p/intake") else None)
        held = []
        pg.route("**/api/p/intake", lambda route: held.append(route))   # hold the request: the server answer is "slow"
        pg.locator("#in-send").click(); pg.wait_for_timeout(300)
        busy = pg.evaluate("() => { const b=document.getElementById('in-send'); return {dis:b.disabled, busy:b.getAttribute('aria-busy'), text:b.textContent}; }")
        check(f"A while sending, the Send button is disabled and says 'Sending' {tag}", busy["dis"] and busy["busy"] == "true" and "Sending" in busy["text"], busy)
        pg.locator("#in-send").click(force=True, timeout=2000) if pg.locator("#in-send").count() and pg.locator("#in-send").is_enabled() else None
        pg.wait_for_timeout(300)
        for r in held: r.continue_()
        pg.locator("#in-done").wait_for(timeout=10000); pg.unroute("**/api/p/intake")
        check(f"A double-click Send -> exactly ONE request reached the server {tag}", len(posts) == 1, posts)
        check(f"A success: clear confirmation, focus on its heading, time shown, Back-to-Home button {tag}", pg.evaluate("document.activeElement.id") == "in-done-h" and "Your intake was sent" in pg.locator("#in-done-h").inner_text() and "received it at" in pg.locator("#in-done").inner_text() and pg.locator("#in-done-home").count() == 1, pg.locator("#in-done").inner_text()[:200])
        shot(pg, f"intake-4-confirmation-{W}")
        pg.wait_for_timeout(2200); check(f"A success screen does not auto-redirect (the person decides when to leave) {tag}", pg.locator("#in-done").count() == 1)
        s, j = api(c, "POST", "/api/p/intake", {"answers": {}}, key=str(uuid.uuid4()))
        check(f"A server refuses a second submission with a new key (409 already_submitted) {tag}", s == 409 and j["error"] == "already_submitted", (s, j))
        s, form = api(c, "GET", "/api/p/intake")
        check(f"A after the patient sends, every field is patient-confirmed on the server {tag}", all(v["patient_confirmed"] for v in form["field_status"].values()), form["field_status"])
        pg.locator("#in-done-home").click(); pg.locator("#hero").wait_for(timeout=8000); pg.wait_for_timeout(300)
        check(f"A back on Home: intake row Done, the tab bar is back {tag}", "Done" in pg.locator("#ck-intake").inner_text() and pg.locator("#nav").is_visible(), pg.locator("#checklist").inner_text()[:200])
        check(f"A no page errors during the intake flow {tag}", not [x for x in ERRS if x[0] == "portal"], ERRS[-3:]); ERRS.clear()
        c.close()

    # ================================================= B. failure state, then a retry with the SAME idempotency key
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "nointake", "key")
    s, f = api(c, "GET", "/api/p/intake")
    ans = {"confirm": {x["key"]: "ok" for x in f["prefill"]}, "corrections": {}, "matters": [], "contact_pref": "phone", "redflags": [], "redflag_none": True, "medicines": "", "allergies": "", "other": "", "confirmed": False}
    s, j = api(c, "PUT", "/api/p/intake/draft", {"answers": ans}); assert s == 200, j
    pg = portal(c, "#/intake", wait="#intake"); pg.locator("#in-step-6").wait_for(state="visible", timeout=8000); pg.locator("label[for=in-confirm]").click()
    keys = []; pg.on("request", lambda r: keys.append(r.headers.get("idempotency-key")) if r.method == "POST" and r.url.endswith("/api/p/intake") else None)
    state = {"n": 0}
    def flaky(route):
        state["n"] += 1
        if state["n"] == 1: route.abort("internetdisconnected")
        else: route.continue_()
    pg.route("**/api/p/intake", flaky)
    pg.locator("#in-send").click(); pg.locator("#in-st.bad").wait_for(timeout=8000)
    t = pg.locator("#in-st").inner_text()
    check("B failure: clear message, nothing lost, how to get help; focus moves to the message", "couldn’t send" in t and "Nothing was lost" in t and "(208) 770-3536" in t and pg.evaluate("document.activeElement.id") == "in-st", t)
    check("B failure: Send is enabled again and says 'Try sending again'; answers still on the page", pg.locator("#in-send").is_enabled() and "Try sending again" in pg.locator("#in-send").inner_text() and pg.locator("#in-confirm").is_checked())
    shot(pg, "intake-5-failure-state-390")
    pg.locator("#in-send").click(); pg.locator("#in-done").wait_for(timeout=10000)
    check("B retry succeeds and re-uses the SAME idempotency key (so a lost answer can never create a duplicate)", len(keys) == 2 and keys[0] == keys[1] and keys[0], keys)
    other = [x for x in ERRS if x[0] == "portal" and "ERR_INTERNET_DISCONNECTED" not in x[1]]   # the one dropped request was forced by this test
    check("B no page errors apart from the deliberately dropped request", not other, other[:3]); ERRS.clear()
    c.close()

    # ================================================= C. large text through the whole intake at 360x740
    c = br.new_context(viewport={"width": 360, "height": 740}); c.add_init_script("try { localStorage.setItem('ps.largeText','1') } catch(e) {}"); load(c, "clean", "intake")
    pg = portal(c, wait="#hero")
    check("C large text is on (root 125% = 20px; body text 22.5px)", pg.evaluate("getComputedStyle(document.documentElement).fontSize") == "20px" and pg.evaluate("getComputedStyle(document.body).fontSize") == "22.5px")
    big_checks(pg, "Home (intake owed) @360"); layout_checks(pg, "large text Home @360", 360)
    pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000); pg.wait_for_timeout(300)
    big_checks(pg, "intake step 1 @360"); layout_checks(pg, "large text intake step 1 @360", 360)
    pg.locator("#in-next").click(); pg.wait_for_timeout(300); big_checks(pg, "intake step 1 with errors @360"); shot(pg, "intake-large-text-error-360")
    for k in pg.evaluate("() => [...document.querySelectorAll('#in-step-1 .pf')].map(e => e.id.slice(3))"): pg.locator(f"label[for=pf-{k}-ok]").click()
    pg.locator("#in-next").click(); pg.locator("#in-step-2").wait_for(state="visible"); big_checks(pg, "intake step 2 @360")
    for k in pg.evaluate("() => [...document.querySelectorAll('#in-step-2 .pf')].map(e => e.id.slice(3))"): pg.locator(f"label[for=pf-{k}-ok]").click()
    pg.locator("#in-next").click(); pg.locator("#in-step-3").wait_for(state="visible"); big_checks(pg, "intake step 3 @360")
    for k in pg.evaluate("() => [...document.querySelectorAll('#in-step-3 .pf')].map(e => e.id.slice(3))"): pg.locator(f"label[for=pf-{k}-ok]").click()
    pg.locator("#in-next").click(); pg.locator("#in-step-4").wait_for(state="visible"); big_checks(pg, "intake step 4 @360")
    pg.locator("label[for=cp-text]").click(); pg.locator("#in-next").click(); pg.locator("#in-step-5").wait_for(state="visible"); big_checks(pg, "intake step 5 @360")
    pg.locator("label[for=rf-none]").click(); pg.locator("#in-next").click(); pg.locator("#in-step-6").wait_for(state="visible"); big_checks(pg, "intake review @360"); layout_checks(pg, "large text intake review @360", 360)
    pg.evaluate("document.getElementById('in-allsteps').open = true"); pg.wait_for_timeout(200); big_checks(pg, "intake 'All steps' list open @360")
    pg.evaluate("document.getElementById('in-allsteps').open = false")
    shot(pg, "intake-large-text-review-360")
    pg.locator("label[for=in-confirm]").click(); pg.locator("#in-send").click(); pg.locator("#in-done").wait_for(timeout=10000); big_checks(pg, "intake confirmation @360")
    pg.locator("#in-done-home").click(); pg.locator("#hero").wait_for(timeout=8000); pg.wait_for_timeout(300); big_checks(pg, "Home (ready) @360"); layout_checks(pg, "large text Home ready @360", 360)
    pg.locator("#account-btn").click(); pg.locator("#account[open]").wait_for(); big_checks(pg, "Account menu open @360"); pg.keyboard.press("Escape")
    pg.locator("#about-open").click(); pg.locator("#about[open]").wait_for(); big_checks(pg, "About this demo sheet open @360"); pg.keyboard.press("Escape")
    check("C no page errors in the large-text run", not [x for x in ERRS if x[0] == "portal"], ERRS[-3:]); ERRS.clear()
    c.close()

    # ================================================= D. mobile chrome
    for W in (360, 390):
        c = br.new_context(viewport={"width": W, "height": 844 if W == 390 else 740}); load(c, "missing")
        pg = portal(c, wait="#hero")
        cu = pg.evaluate("() => { const a=document.getElementById('callus'), l=a.querySelector('.lbl-short'), r=l.getBoundingClientRect(); return {txt:a.innerText.trim(), w:r.width, href:a.getAttribute('href'), aria:a.getAttribute('aria-label')}; }")
        check(f"D 'Call us' is visibly labelled in the header (not icon-only) @{W}", cu["txt"].startswith("Call us") and cu["w"] > 30 and cu["href"] == "tel:2087703536" and "(208) 770-3536" in cu["aria"], cu)
        check(f"D header has a labelled 'Account' button; no separate settings / sign-out / text-size icons @{W}", pg.locator("#account-btn").inner_text().strip() == "Account" and pg.locator("header #signout, header #settings-btn, header #textsize").count() == 0)
        hh = pg.evaluate("() => document.querySelector('header.site').getBoundingClientRect().height"); check(f"D header stays one row at normal text size ({round(hh)}px) @{W}", hh < 72, hh)
        pg.locator("#account-btn").click(); pg.locator("#account[open]").wait_for()
        m = pg.locator("#account").inner_text()
        check(f"D Account menu: text size (Standard / Larger), Settings, About this demo, Sign out @{W}", all(x in m for x in ("Text size", "Standard", "Larger", "Settings", "About this demo", "Sign out")), m[:200])
        pg.locator("label[for=acct-ts-large]").click(); pg.wait_for_timeout(200)
        check(f"D choosing 'Larger' enlarges the text (125%) and stores only ps.largeText @{W}", pg.evaluate("document.documentElement.classList.contains('big')") and pg.evaluate("JSON.stringify(Object.keys(localStorage))") == '["ps.largeText"]')
        pg.locator("label[for=acct-ts-standard]").click(); pg.wait_for_timeout(200)
        check(f"D choosing 'Standard' returns to normal and clears storage @{W}", not pg.evaluate("document.documentElement.classList.contains('big')") and pg.evaluate("localStorage.length") == 0)
        if W == 390: shot(pg, "chrome-account-menu-390")
        pg.locator("#acct-settings").click(); pg.locator("h1:has-text('Settings')").wait_for()
        check(f"D Settings page has the same two-choice text-size control, in sync @{W}", pg.locator("#set-ts-standard").is_checked() and not pg.locator("#set-ts-large").is_checked())
        check(f"D Settings no longer repeats the 'what is real' explanation; it links to 'About this demo' @{W}", "What is real and what is made up" not in pg.locator("main").inner_text() and pg.locator("#set-about").count() == 1)
        pg.goto(BASE + "/portal.html#/home"); pg.locator("#hero").wait_for()
        tb = pg.evaluate("() => { const n=document.getElementById('nav'), cs=getComputedStyle(n); return {pos:cs.position, bg:cs.backgroundColor, pb:parseFloat(getComputedStyle(document.body).paddingBottom), h:n.getBoundingClientRect().height}; }")
        check(f"D tab bar is fixed with a SOLID background (no text showing through) @{W}", tb["pos"] == "fixed" and tb["bg"] in ("rgb(255, 255, 255)",), tb)
        check(f"D body padding is at least the tab bar height @{W}", tb["pb"] >= tb["h"], tb)
        pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(300)
        bl = pg.evaluate("() => { const top=document.getElementById('nav').getBoundingClientRect().top; const els=[...document.querySelectorAll('main *, footer *')].filter(e => e.children.length===0 && e.textContent.trim() && e.getBoundingClientRect().height && !(e.closest('details:not([open])') && !e.closest('summary'))); const last=els.map(e=>e.getBoundingClientRect().bottom); return {navTop:top, lastBottom:Math.max(...last)}; }")
        check(f"D scrolled to the bottom, the last text ends above the tab bar (no bleeding behind it) @{W}", bl["lastBottom"] <= bl["navTop"] + 0.5, bl)
        if W == 390: shot(pg, "chrome-bottom-of-home-above-tabbar-390")
        check(f"D the DEMO notice is still visible on Home @{W}", "Demo \u2014 example data only" in pg.locator("#demobar").inner_text() and pg.locator("#demobar").is_visible())
        pg.locator("#about-open").click(); pg.locator("#about[open]").wait_for(); ab = pg.locator("#about").inner_text()
        check(f"D one 'About this demo' sheet holds the limitations (simulated faxes/texts/insurance, no scheduling, not HIPAA-compliant) @{W}", all(x in ab for x in ("Simulated", "Not built", "not HIPAA-compliant", "no scheduling system", "Faxes")), ab[:200])
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        check(f"D Esc closes the sheet and returns focus to its opener @{W}", not pg.evaluate("document.getElementById('about').open") and pg.evaluate("document.activeElement.id") == "about-open")
        mt = pg.locator("main").inner_text()
        check(f"D Home no longer repeats long technical demo paragraphs (details are collapsed; About holds them) @{W}", "Faxes, text messages, automatic follow-ups and insurance checks in this prototype are simulated" not in mt and pg.locator("#pipe-more").get_attribute("open") is None)
        layout_checks(pg, f"Home (records) @{W}", W)
        c.close()
    css = open(os.path.join(L.ROOT, "shared.css")).read(); html = open(os.path.join(L.ROOT, "portal.html")).read()
    check("D safe-area insets are handled (viewport-fit=cover + env(safe-area-inset-bottom/left/right) in the CSS)", "viewport-fit=cover" in html and all(f"env(safe-area-inset-{x})" in css for x in ("bottom", "left", "right")))
    js = open(os.path.join(L.ROOT, "shared.js")).read()
    check("D on-screen keyboard handling uses visualViewport + scroll-into-view (code present; real keyboards can't be driven in headless Chrome)", "visualViewport" in js and "kb-open" in js and "keepInView" in js)

    # ================================================= E. Home in six fictional states at 390x844
    STATES = [("records", "missing", "key"), ("intake", "nointake", "key"), ("ready", "clean", "key"), ("booked", "clean", "booked"), ("preop", "surgery", "key"), ("postop", "surgery", "postop")]
    EXPECT = {"records": (0, None), "intake": (1, "#na-intake"), "ready": (1, "#ready-call"), "booked": (1, "#na-confirm"), "preop": (1, "#preop-ack"), "postop": (1, "#ck-send")}
    for name, key, step in STATES:
        HERO = "ck-card" if name == "postop" else "hero"   # preview19 Prompt B: after surgery the check-in card comes first
        c = br.new_context(viewport={"width": 390, "height": 844}); load(c, key, step); pg = portal(c, wait="#" + HERO); pg.wait_for_timeout(500)
        s, d = api(c, "GET", "/api/p/home")
        first = pg.evaluate("() => { const m=document.querySelector('main'); const c=[...m.children].filter(e => e.tagName==='SECTION'); return c[0] && c[0].id; }")
        check(f"E[{name}] the first card is the server-backed status card" + (" (post-op: the check-in)" if name == "postop" else ""), first == HERO)
        n, sel = EXPECT[name]; big = pg.locator(f"#{HERO} .btn.big").count()
        check(f"E[{name}] dominant actions in the first card: expected {n}, found {big}" + (f" ({sel})" if sel else ""), big == n and (not sel or pg.locator(f"#{HERO} {sel}").count() == 1), pg.locator("#" + HERO).inner_text()[:160])
        yd = pg.locator("#youdo").inner_text() if name != "postop" else pg.locator("#ck-card").inner_text(); mt = pg.locator("main").inner_text()
        check(f"E[{name}] answers 'Do you need to do anything?'" + (" (post-op: 'how are you doing?')" if name == "postop" else ""), ("Do you need to do anything?" in yd) if name != "postop" else ("how are you doing?" in yd))
        if d["next_action"]["key"] == "none" and d["pipeline"]["state"] != "ready":
            ydl = [x.strip() for x in yd.splitlines() if x.strip()]
            check(f"E[{name}] 'No' is never next to an instruction to call and schedule", len(ydl) > 1 and ydl[1].startswith("No.") and not re.search(r"(?i)call .{0,40}(schedule|book|find a time)", mt), (ydl, re.findall(r"(?i).{0,40}call .{0,40}(?:schedule|book|find a time).{0,20}", mt)))
        check(f"E[{name}] contacting the team is easy (help card) but never the biggest button", pg.locator("#help #help-call").count() == 1 and pg.locator("#help .btn.big").count() == 0)
        if name == "preop":   # preview19 Prompt B: before surgery the checklist is split into 'Your tasks' / 'What our team is handling'
            check("E[preop] split checklist: your tasks vs the team's, no connected progress line", pg.locator("#preop-you li").count() >= 1 and pg.locator("#preop-team li").count() >= 3 and pg.locator(".tracker").count() == 0, pg.locator("#preop-split").inner_text()[:120])
            check("E[preop] says ticks are not a clearance", pg.locator("#preop-noclear").count() == 1)
        else:
            check(f"E[{name}] compact checklist (no connected progress line)", pg.locator("#checklist li").count() >= 3 and pg.locator(".tracker").count() == 0, pg.locator("#checklist").inner_text()[:120])
            check(f"E[{name}] fax history / ownership / notes are collapsed in a details disclosure", pg.locator("#pipe-more").count() == 1 and pg.locator("#pipe-more").get_attribute("open") is None)
        if name == "records":
            hw = pg.locator("#hero-waits").inner_text()
            check("E[records] office-owned records: says who is handling it and that the patient need not chase", "handling these" in hw and "don’t need to chase" in hw, hw)
            check("E[records] ... with verified status and last update time (PT) for each item", hw.count("Last verified update:") >= 2 and hw.count(" PT") >= 2, hw)
            check("E[records] the patient is not told to call/schedule while records are outstanding", "No visit is booked yet. Call" not in mt and "find a time" not in mt)
        if name == "ready":
            hero = pg.locator("#hero").inner_text()
            check("E[ready] no invented availability: no times or slots on screen; the action is to call or request a call", not re.search(r"\b\d{1,2}:\d{2}\b", hero) and "Call us to book" in hero and "Ask us to call you instead" in hero, hero[:300])
            pg.locator("#ready-cb").click(); pg.locator("#ready-cb-status").filter(has_text="call-back request is in").wait_for(timeout=8000)
            check("E[ready] 'Ask us to call you instead' creates a real call-back request on the server", True)
        if name == "booked":
            check("E[booked] shows the staff-recorded visit (fictional) and asks for one-tap confirmation", "Not confirmed yet" in pg.locator("#hero").inner_text() and "Dr. Stefan Yakel" in pg.locator("#hero").inner_text())
        if name == "postop":
            check("E[postop] check-ins are the checklist after surgery; pre-op items are in the details", pg.locator("#ck-checkin-2").count() == 1 and "Your turn" in pg.locator("#ck-checkin-2").inner_text())
        HEIGHTS[name] = pg.evaluate("document.documentElement.scrollHeight")
        shot(pg, f"after-home-{name}-390"); shot(pg, f"after-home-{name}-390-full", full=True)
        layout_checks(pg, f"Home [{name}]", 390)
        c.close()
    # Records page shows the full detail (open)
    c = br.new_context(viewport={"width": 390, "height": 844}); load(c, "missing"); pg = portal(c, "#/records", wait="#pipe")
    check("E Records page: the same checklist with the details OPEN (who has it, fax history, last verified)", pg.locator("#pipe-more").get_attribute("open") is not None and pg.locator("#pipe-waiting .who").count() >= 2)
    c.close()
    check("no page errors", not ERRS, ERRS[:4])
    br.close()
finally:
    srv.stop()
json.dump(HEIGHTS, open(f"{OUT}/after-home-heights-ui_v19.json", "w"), indent=1)
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_v19: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
print("heights:", HEIGHTS)
json.dump(L.RESULTS, open(os.path.join(L.HERE, "ui_v19.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
