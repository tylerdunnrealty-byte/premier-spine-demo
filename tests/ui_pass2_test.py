#!/usr/bin/env python3
"""Pass 2 UI tests (Playwright + local Chrome, real local server, fictional data).
Every scenario's KEY STATE is opened in the patient portal and the office workspace at 360 px and 1440 px with layout checks,
and the human steps are done by clicking the real screens (accept, records request from the queue, insurer decision,
intake form, helper intake + patient confirmation, route elsewhere, red-flag guidance)."""
import json, os, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8773")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
PAT = {"clean": "Avery", "missing": "Blake", "auth": "Cameron", "nointake": "Drew", "caregiver": "Emery", "notfit": "Finley", "redflag": "Gray", "surgery": "Harper"}
EXPECT = {  # key state: (patient summary fragment, patient next-action id or None, office: first Do-next button text fragment)
    "clean": ("ready for your first visit", None, "Book the visit"),
    "missing": ("getting everything ready", None, "Mark received"),
    "auth": ("getting everything ready", None, "Record the insurer"),
    "nointake": ("getting everything ready", "na-intake", "Log a phone call"),
    "caregiver": ("getting everything ready", "na-attest", "Patient confirmed by phone"),
    "notfit": ("reviewing it", None, "Accept referral"),
    "redflag": ("guidance at the top", None, "Log contact with the patient"),
    "surgery": ("surgery is being prepared", "preop-ack", "Clearance arrived"),
}
DEMO_TXT = "Demo \u2014 example data only, not a real patient portal"
JS_DEMO = """() => { const b = document.getElementById('demobar'); if (!b) return {missing: true};
  const r = b.getBoundingClientRect(), cs = getComputedStyle(b); const hits = [];
  for (const el of document.querySelectorAll('a, button, input, select, textarea, h1, .site, .protobar')) { if (b.contains(el)) continue; const q = el.getBoundingClientRect(); if (!q.width || !q.height) continue;
    if (q.top < r.bottom - 1 && q.bottom > r.top + 1 && q.left < r.right - 1 && q.right > r.left + 1) hits.push(el.id || el.className || el.tagName); }
  return {text: b.innerText, pos: cs.position, visible: r.height > 20 && cs.display !== 'none' && cs.visibility !== 'hidden', top: Math.round(r.top + window.scrollY), first: document.body.firstElementChild === b || document.body.firstElementChild.classList.contains('skip'),
          buttons: b.querySelectorAll('button, [role=button], a').length, hits: hits, title: document.title, fullWidth: r.width >= window.innerWidth - 1}; }"""
def wiz(pg, n):  # step-by-step wizard: jump to step n via its step button (preview19: the step list sits in an 'All steps' disclosure)
    pg.evaluate("document.getElementById('in-allsteps').open = true"); pg.locator(f"#in-stepbtn-{n}").click(); pg.locator(f"#in-step-{n}").wait_for(state="visible", timeout=8000)
def confirm_all(pg):
    for n in (1, 2, 3):
        wiz(pg, n)
        for lab in pg.locator(f"#in-step-{n} label[for$='-ok']").all(): lab.click()

def openmore(pg):  # preview19: Home keeps who/next-step/fax detail in a collapsed 'details' section -- open it before reading
    pg.evaluate("document.querySelectorAll('details.more').forEach(d => d.open = true)")
def demo_checks(pg, name, w):
    d = pg.evaluate(JS_DEMO)
    check(f"DEMO banner present + visible: {name} @{w}", not d.get("missing") and d["visible"] and DEMO_TXT in d["text"], d)
    check(f"DEMO banner is in normal flow at the top, full width, not dismissible: {name} @{w}", d.get("pos") == "static" and d.get("top", 99) <= 60 and d.get("buttons") == 0 and d.get("fullWidth"), d)
    check(f"DEMO banner covers no content or controls: {name} @{w}", d.get("hits") == [], d.get("hits"))
    check(f"page title starts with DEMO: {name} @{w}", (d.get("title") or "").startswith("DEMO"), d.get("title"))
ERRS = []
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def load(ctx, key, step="key", helper=False):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "as_helper": helper}); assert s == 200, (key, s, j); return j
def login(ctx, persona, app): s, j = api(ctx, "POST", "/api/login", {"persona": persona, "app": app}); assert s == 200, (persona, s, j)
def first_task(ctx, name, typ=None):
    s, q = api(ctx, "GET", "/api/o/queue?filter=all")
    ts = [t for t in q["tasks"] if t["patient_name"].startswith(name) and t["status"] != "Resolved" and (typ is None or t["type"] == typ)]
    return ts[0]["id"] if ts else None
def portal(ctx, hash_="#/home"):
    pg = ctx.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html" + hash_); return pg
def office(ctx, tid):
    pg = ctx.new_page(); watch(pg, "office"); pg.goto(BASE + f"/office.html#/task/{tid}"); pg.locator("#d-do h2").wait_for(timeout=8000); pg.locator("#d-pipe .tracks").wait_for(timeout=8000); return pg

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "ui2.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    mk = lambda w: br.new_context(viewport={"width": w, "height": 800 if w < 400 else 900})
    # ---------------------------------------------------------------- key states, both views, both widths
    for w in (360, 1440):
        for key, (summ, na, act) in EXPECT.items():
            ctx = mk(w); load(ctx, key)
            pg = portal(ctx); pg.locator("#preop-split" if key == "surgery" else "#pipe").wait_for(timeout=8000)   # preview19 Prompt B: pre-op Home shows a split checklist instead of #pipe
            check(f"[{key}] patient sees 'where things stand' summary @{w}", summ in pg.locator("#pipe-summary").inner_text(), pg.locator("#pipe-summary").inner_text())
            if na: check(f"[{key}] patient's one next action is shown (#{na}) @{w}", pg.locator("#" + na).is_visible())
            if key == "redflag":
                check(f"[redflag] urgent card with Call 911 (tel:911) and the office number @{w}", pg.locator(".card.urgent a[href='tel:911']").is_visible() and pg.locator(".card.urgent a[href='tel:2087703536']").is_visible())
            if key in ("missing", "auth", "nointake"):
                openmore(pg); wt = pg.locator("#pipe-waiting").inner_text()
                exp = {"missing": ["Lakeshore Imaging (fictional)", "Example Family Clinic (fictional)"], "auth": ["Sample Insurance Co. (fictional)"], "nointake": ["Waiting on: You"]}[key]
                check(f"[{key}] patient 'What we're waiting on' names who @{w}", all(x in wt for x in exp), wt[:200])
                check(f"[{key}] simulated steps are labelled 'Simulated' @{w}", pg.locator("#pipe-waiting .tag:has-text('Simulated')").count() >= 1)
            layout_checks(pg, f"{key} patient home", w); demo_checks(pg, f"{key} patient home", w)
            tid = first_task(ctx, PAT[key])
            if key == "missing": tid = first_task(ctx, "Blake", "records_request")
            op = office(ctx, tid)
            b = op.locator("#d-do .actlist button").first
            check(f"[{key}] office 'Do next' first action is '{act}' @{w}", act in b.inner_text(), b.inner_text())
            check(f"[{key}] office referral checklist shows the case state chip @{w}", op.locator("#d-pipe .chip").first.is_visible())
            layout_checks(op, f"{key} office detail", w); demo_checks(op, f"{key} office detail", w)
            ctx.close()
    # ---------------------------------------------------------------- DEMO notice on the sign-in screens and the presenter
    for w in (360, 1440):
        ctx = br.new_context(viewport={"width": w, "height": 800}); pg = ctx.new_page(); watch(pg, "login")
        pg.goto(BASE + "/portal.html"); pg.locator("#login-demo").wait_for(timeout=8000)
        check(f"portal sign-in says Demo in the heading and the note @{w}", pg.locator("h1").first.inner_text().startswith("Demo") and "DEMO" in pg.locator("#login-demo").inner_text())
        demo_checks(pg, "portal sign-in", w); layout_checks(pg, "portal sign-in", w)
        pg.goto(BASE + "/office.html"); pg.locator("button.qitem").first.wait_for(timeout=8000)
        check(f"office sign-in says Demo in the heading @{w}", pg.locator("h1").first.inner_text().startswith("Demo"))
        demo_checks(pg, "office sign-in", w)
        pg.goto(BASE + "/presenter.html"); pg.locator("#pm-toggle").wait_for(timeout=8000); demo_checks(pg, "presenter", w)
        pg.goto(BASE + "/"); pg.locator("#demobar").wait_for(timeout=8000); demo_checks(pg, "preview landing page", w)
        ctx.close()
    # ---------------------------------------------------------------- SPOTLIGHT 1: fewer calls
    ctx = mk(360); load(ctx, "missing"); pg = portal(ctx); pg.locator("#pipe-waiting").wait_for(state="attached", timeout=8000); openmore(pg)
    check("SP1 patient status: each waiting item says who's handling it and the next step @360", pg.locator("#pipe-waiting .who").count() >= 2 and pg.locator("#pipe-waiting .nextstep").count() >= 2, pg.locator("#pipe-waiting").inner_text()[:300])
    check("SP1 patient status explains it answers the usual phone questions @360", "usual phone questions" in pg.locator("#pipe-why").inner_text())
    q = ctx.new_page(); watch(q, "office-sp1"); q.goto(BASE + "/office.html#/queue"); q.locator("#calls-label").wait_for(timeout=8000)
    check("SP1 office queue shows 'Phone calls the portal may have saved' labelled EXAMPLE COUNTS ONLY @360", "EXAMPLE COUNTS ONLY" in q.locator("#calls-label").inner_text() and "not a measured reduction" in q.locator("#calls").inner_text())
    layout_checks(q, "office queue with calls-saved card", 360); ctx.close()
    # ---------------------------------------------------------------- SPOTLIGHT 2: automatic chasing
    ctx = mk(1440); load(ctx, "auth"); api(ctx, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"}); aid = first_task(ctx, "Cameron", "prior_auth")
    q = ctx.new_page(); watch(q, "office-sp2"); q.goto(BASE + "/office.html#/queue"); q.locator("#filters button[data-f=waiting]").click(); q.wait_for_timeout(800)
    q.locator("#qlist .qrow:has-text('Cameron')").first.wait_for(timeout=8000)
    # preview19 Prompt C: badges moved into the card's 'More' disclosure (closed by default), so read the card's DOM text and open 'More' to see it
    check("SP2 waiting item shows 'Auto-chasing 1 of 2 (simulated)' (under 'More')", "Auto-chasing 1 of 2 (simulated)" in q.locator("#qlist .qrow:has-text('Cameron')").first.text_content(), q.locator("#qlist .qrow:has-text('Cameron')").first.text_content()[:300])
    for _ in range(2): api(ctx, "POST", "/api/presenter/scenario/advance", {"event": "days_pass", "key": "auth"})
    q.locator("#filters button[data-f=open]").click(); q.locator("#qlist .chip:has-text('Stuck')").first.wait_for(state="attached", timeout=8000); q.wait_for_timeout(1200)   # preview19 Prompt C: chip sits inside 'More'; give the refreshed Do next a moment 
    # preview19 Prompt C: other scenarios loaded earlier in this run also have urgent/stuck items, so "next up" is now: the urgent notice first, then the
    # first overdue/blocked item (which may be another stuck patient). Check Cameron is flagged and sits in 'Overdue or blocked', and Do next starts there.
    qq = api(ctx, "GET", "/api/o/queue?filter=open")[1]
    check("SP2 after the follow-up limit the item is flagged 'Stuck — needs a phone call', sits in 'Overdue or blocked', and Do next starts with blocked work (urgent notice first)", "Cameron" in q.locator("#grp-blocked").inner_text() and q.locator("#qlist .chip:has-text('Stuck')").count() >= 1 and qq["next_up_task"]["group"] == "blocked" and (not qq["pinned"] or "Urgent first" in q.locator("#nextup").inner_text()), (q.locator("#nextup").inner_text()[:300], qq.get("next_up_task", {}).get("group")))
    pg = portal(ctx); pg.locator("#pipe").wait_for(timeout=8000); openmore(pg)
    check("SP2 patient is told a team member is following up by phone", "following up by phone" in pg.locator("#pipe").inner_text())
    ctx.close()
    # ---------------------------------------------------------------- SPOTLIGHT 3: pre-filled intake + summary
    ctx = mk(360); load(ctx, "clean", "intake"); pg = portal(ctx, "#/intake"); pg.locator("#intake").wait_for(timeout=8000)
    check("SP3 every pre-filled item shows a 'Simulated source' label @360", pg.locator("#intake .pf").count() == pg.locator("#intake .pf .src .tag:has-text('Simulated source')").count() >= 9)
    check("SP3 medicines and allergies arrive pre-filled from the referral @360", "Medicines listed on your referral" in pg.locator("#intake").text_content() and "Allergies listed on your referral" in pg.locator("#intake").text_content())
    wiz(pg, 3)
    # preview19: 'Where this came from' + 'Why we ask' share one disclosure (details.whyask#pf-meds-help); the example hint sits by the correction box (#pf-h-meds)
    check("SP3 'Why we ask' is collapsed until opened @360", not pg.locator("#pf-meds-help").evaluate("d => d.open") and not pg.locator("#pf-meds-help p").last.is_visible())
    pg.locator("#pf-meds-help summary").click(); check("SP3 opening 'Why we ask' explains the reason in plain words @360", "medicines" in pg.locator("#pf-meds-help").inner_text().split("Why we ask")[-1].lower(), pg.locator("#pf-meds-help").inner_text())
    check("SP3 hints give an example @360", "Example" in pg.locator("#pf-h-meds").text_content(), pg.locator("#pf-h-meds").text_content())
    layout_checks(pg, "pre-filled intake with help", 360); ctx.close()
    ctx = mk(1440); j = load(ctx, "clean"); login(ctx, "pat", "office"); op = office(ctx, j["open_task"]); op.locator("#sum-label").wait_for(timeout=8000)
    check("SP3 office: visit-ready summary is labelled 'Draft — clinician review required'", op.locator("#sum-label").inner_text().strip() == "Draft \u2014 clinician review required", op.locator("#sum-label").inner_text())   # preview19 Prompt C: exact label
    check("SP3 front desk cannot mark it reviewed (button disabled, reason shown)", op.locator("#sum-review").is_disabled() and "Only a clinician" in op.locator("#d-sum").inner_text())
    check("SP3 summary names the questionnaires as not collected (office decision)", "Not collected in this demo" in op.locator("#d-sum").inner_text())
    login(ctx, "yakel", "office"); op.reload(); op.locator("#sum-review").wait_for(timeout=8000); op.locator("#sum-review").click(); op.locator("#sum-reviewed.ok").wait_for(timeout=8000)
    check("SP3 Dr. Yakel marks the draft reviewed; card shows who", "Reviewed by Dr." in op.locator("#sum-reviewed").inner_text())
    layout_checks(op, "office detail with summary", 1440); ctx.close()
    # ---------------------------------------------------------------- SPOTLIGHT 4: surgery prep + post-op
    ctx = mk(1440); j = load(ctx, "surgery", "start"); op = office(ctx, j["open_task"]); op.locator("#po-items").wait_for(timeout=8000)
    check("SP4 office surgery checklist: consent button disabled for front desk with reason", op.locator("#po-consent-done").is_disabled() and "Only a clinician" in op.locator("#po-item-consent").inner_text())
    login(ctx, "yakel", "office"); op.reload(); op.locator("#po-consent-done-n").wait_for(timeout=8000); op.fill("#po-consent-done-n", "Discussed in clinic (example)."); op.locator("#po-consent-done").click()
    op.locator("#po-item-consent .chip.ok").wait_for(timeout=8000); check("SP4 clinician records consent from the checklist", True)
    layout_checks(op, "office surgery checklist", 1440); ctx.close()
    ctx = mk(360); load(ctx, "surgery", "postop"); pg = portal(ctx); pg.locator("#ck-form").wait_for(timeout=8000)
    check("SP4 patient post-op check-in shows three choices + 911 @360", pg.locator("#ck-form input[name=ck]").count() == 3 and pg.locator("#ck-911 a[href='tel:911']").first.is_visible())  # preview19 Prompt B: post-op Home = check-in card first + a static 'Urgent help' box
    layout_checks(pg, "post-op check-in", 360)
    pg.locator("label[for=ck-concern]").click(); pg.locator("#ck-send").click(); pg.locator("#ck-st.bad").wait_for(timeout=8000)   # preview19 Prompt B: status id #ck-st
    check("SP4 a worry without any words is refused with a clear message @360", "a few words" in pg.locator("#ck-st").inner_text(), pg.locator("#ck-st").inner_text())
    pg.fill("#ck-note", "The wound area looks different today and I am worried (example)."); pg.locator("#ck-send").click(); pg.locator("#ck-receipt").wait_for(timeout=8000)
    rc_ = pg.locator("#ck-receipt").inner_text()   # preview19 Prompt B: server receipt; the old "a nurse will phone" promise was removed
    check("SP4 sending a worry shows the server receipt (reached the care team, urgent), no call-back promise, 911 in an emergency @360", "reached the care team" in rc_ and "URGENT" in rc_ and "911" in rc_ and "will phone" not in rc_, rc_)
    login(ctx, "nina", "office"); q = ctx.new_page(); watch(q, "office-sp4"); q.goto(BASE + "/office.html#/queue"); q.locator("#qlist .qrow").first.wait_for(timeout=8000)
    q.locator("#filters button[data-f=urgent]").click(); q.locator("#qlist .qrow:has-text('Harper')").first.wait_for(timeout=8000)
    check("SP4 the worry lands in the nurse's URGENT list as a post-op concern", "Post-op day 2 check-in" in q.locator("#qlist .qrow:has-text('Harper')").first.inner_text() and "URGENT" in q.locator("#qlist .qrow:has-text('Harper')").first.inner_text())
    ctx.close()
    ctx = mk(360); load(ctx, "surgery", "key"); pg = portal(ctx); pg.locator("#surg-date").wait_for(timeout=8000); openmore(pg)
    # preview19 Prompt B: the pre-op checklist is split (patient vs office) and says ticks are not a clearance; missing instructions use the exact sentence
    check("SP4 patient pre-op checklist: example date + clearance line on the team's side + 'ticks are not a clearance' + no invented instructions @360", "example date" in pg.locator("#surg-date").inner_text().lower() and "Pre-op clearance" in pg.locator("#preop-team").inner_text() and "do not mean you are cleared" in pg.locator("#preop-noclear").inner_text() and "Your team has not added these instructions yet." in pg.locator("main").inner_text())
    pg.locator("#preop-ack").click(); pg.locator("#na-status.ok").wait_for(timeout=8000); check("SP4 patient confirms they have the written instructions in one tap @360", True)
    ctx.close()
    # ---------------------------------------------------------------- S1: accept in the office, patient intake via the form, then booked
    ctx = mk(1440); load(ctx, "clean", "start")
    login(ctx, "pat", "office"); op = office(ctx, first_task(ctx, "Avery", "fit_review"))
    check("S1 front desk: Accept is disabled with the reason shown", op.locator("#do-accept").is_disabled() and "clinician" in op.locator("#why-accept").inner_text().lower())
    login(ctx, "yakel", "office"); op.reload(); op.locator("#do-accept").wait_for()
    op.locator("#do-accept").click(); op.locator("#dof-accept").wait_for()
    check("S1 accept form opens with the 'I reviewed the MRI report' box pre-ticked", op.locator("#f-accept-reviewed_report").is_checked())
    op.locator("#dosub-accept").click(); op.locator("#do-st").filter(has_text="Done").wait_for(timeout=8000)
    check("S1 clinician accepted in the office UI (status says Done)", "accepted" in op.locator("#do-st").inner_text().lower())
    login(ctx, "pat", "office"); it = first_task(ctx, "Avery", "insurance_check")
    q = ctx.new_page(); watch(q, "office-q"); q.goto(BASE + "/office.html#/queue"); q.locator(f"#q-act-{it}").wait_for(timeout=8000)
    check("S1 queue row has a one-click 'Run eligibility check (simulated)' button", "simulated" in q.locator(f"#q-act-{it}").inner_text().lower())
    q.locator(f"#q-act-{it}").click(); q.locator("#q-st").filter(has_text="Done").wait_for(timeout=8000)
    check("S1 one click from the queue ran the simulated check", "no prior authorization" in q.locator("#q-st").inner_text().lower(), q.locator("#q-st").inner_text())
    pg = portal(ctx); pg.locator("#na-intake").wait_for(timeout=8000); pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000)
    check("S1 intake shows what we already have (tell us once): name and referrer pre-filled", "Avery Example" in pg.locator("#intake").text_content() and "Dr. Jamie Referrer" in pg.locator("#intake").text_content())
    wiz(pg, 6); pg.locator("label[for='in-confirm']").click(); pg.locator("#in-send").click(); pg.locator("#in-st.bad").wait_for(timeout=8000)
    # preview19: the form is checked before sending; it opens the first step with a missing answer and explains it next to the field
    check("S1 sending an incomplete form explains what is missing (nothing lost)", pg.locator("#in-step-1").is_visible() and "Please choose" in pg.locator("#in-step-1 .ferr:not([hidden])").first.inner_text() and "attention" in pg.locator("#in-st").inner_text() and pg.locator("#in-confirm").is_checked(), pg.locator("#in-st").inner_text())
    confirm_all(pg)
    wiz(pg, 4); pg.locator("label[for='mt-0']").click(); pg.locator("label[for='cp-text']").or_(pg.locator("#intake fieldset label.choice[for^='cp-']").first).first.click()
    wiz(pg, 5); pg.locator("label[for='rf-none']").click(); pg.locator("#in-ind").filter(has_text="Draft saved on the server").wait_for(timeout=8000)
    check("S1 autosave indicator says saved on the server (not sent)", "Not sent" in pg.locator("#in-ind").inner_text())
    pg.reload(); pg.locator("#intake").wait_for(timeout=8000)
    check("S1 after reload the draft is restored from the server", pg.locator("#rf-none").is_checked() and pg.locator("#mt-0").is_checked())
    wiz(pg, 6)
    if not pg.locator("#in-confirm").is_checked(): pg.locator("label[for='in-confirm']").click()
    pg.locator("#in-send").click(); pg.locator("#in-done-home").click(timeout=10000); pg.locator("#pipe").wait_for(timeout=10000)  # preview19: a confirmation screen, no auto-redirect
    check("S1 after sending: patient home says ready for the first visit", "ready for your first visit" in pg.locator("#pipe-summary").inner_text())
    ctx.close()
    # ---------------------------------------------------------------- S2: records request from the queue (one click), still waiting
    ctx = mk(1440); load(ctx, "missing", "start"); login(ctx, "yakel", "office"); api(ctx, "POST", f"/api/o/tasks/{first_task(ctx, 'Blake', 'fit_review')}/act", {"action": "accept"}, key="a1")
    login(ctx, "pat", "office"); rid = first_task(ctx, "Blake", "records_request")
    q = ctx.new_page(); watch(q, "office-q2"); q.goto(BASE + "/office.html#/queue"); q.locator(f"#q-act-{rid}").wait_for(timeout=8000)
    q.locator(f"#q-act-{rid}").click(); q.locator("#q-st").filter(has_text="Done").wait_for(timeout=8000)
    check("S2 one click from the queue sends the records request (simulated fax)", "simulated fax" in q.locator("#q-st").inner_text().lower(), q.locator("#q-st").inner_text())
    ctx.close()
    # ---------------------------------------------------------------- S3: insurer decision needs a reference
    ctx = mk(1440); load(ctx, "auth"); op = office(ctx, first_task(ctx, "Cameron", "prior_auth"))
    op.locator("#do-record_decision").click(); op.locator("#dof-record_decision").wait_for()
    check("S3 opening the decision form moves focus into it (keyboard)", op.evaluate("document.activeElement.id") == "f-record_decision-decision")
    op.select_option("#f-record_decision-decision", "approved"); op.locator("#dosub-record_decision").click(); op.locator("#do-st.bad").wait_for(timeout=8000)
    check("S3 saving without a reference is refused with a clear message", "Reference" in op.locator("#do-st").inner_text(), op.locator("#do-st").inner_text())
    op.fill("#f-record_decision-reference", "Auth EX-777 (example)"); op.locator("#dosub-record_decision").click(); op.locator("#do-st").filter(has_text="Done").wait_for(timeout=8000)
    op.wait_for_timeout(800); check("S3 after recording approval the checklist shows Ready", "Ready" in op.locator("#d-pipe .chip").first.inner_text(), op.locator("#d-pipe .chip").first.inner_text())
    ctx.close()
    # ---------------------------------------------------------------- S4: after 3 reminders the queue sends you to a phone call (needs input)
    ctx = mk(360); load(ctx, "nointake"); did = first_task(ctx, "Drew", "intake_followup")
    q = ctx.new_page(); watch(q, "office-q4"); q.goto(BASE + "/office.html#/queue"); q.locator(f"#q-open-{did}").wait_for(timeout=8000)
    check("S4 queue: after 3 reminders the next step is 'Log a phone call…' (opens the item, needs input) @360", "phone call" in q.locator(f"#q-open-{did}").inner_text())
    layout_checks(q, "office queue with actions", 360)
    pg = portal(ctx); pg.locator("#pipe").wait_for(timeout=8000); openmore(pg)
    check("S4 patient sees '3 reminders (simulated text messages)' @360", "3 reminders" in pg.locator("#pipe-waiting").inner_text())
    ctx.close()
    # ---------------------------------------------------------------- S5: helper fills in at 360, patient confirms
    ctx = mk(360); load(ctx, "caregiver", "intake", helper=True)
    pg = portal(ctx); pg.locator("#na-intake").wait_for(timeout=8000); pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000)
    check("S5 helper sees 'filling this in for Emery' and that Emery must confirm @360", "Emery will be asked to check" in pg.locator("#in-helper").inner_text())
    confirm_all(pg)
    wiz(pg, 1); pg.locator("label[for='pf-phone-change']").click(); pg.fill("#pf-c-phone", "(208) 555-0100 (example)")
    wiz(pg, 4); pg.locator("#intake label.choice[for^='cp-']").first.click(); wiz(pg, 5); pg.locator("label[for='rf-none']").click(); wiz(pg, 6); pg.locator("label[for='in-confirm']").click()
    layout_checks(pg, "helper intake form", 360)
    pg.locator("#in-send").click(); pg.locator("#in-done-h").filter(has_text="Emery will be asked").wait_for(timeout=8000)  # preview19: confirmation screen
    check("S5 helper's send says Emery will be asked to confirm @360", True)
    login(ctx, "emery", "portal"); pg2 = portal(ctx); pg2.locator("#na-attest").wait_for(timeout=8000); pg2.locator("#na-attest").click(); pg2.locator("#att-summary").wait_for(timeout=8000)
    check("S5 patient sees the helper's answers incl. the corrected phone @360", "(208) 555-0100" in pg2.locator("#att-summary").inner_text())
    layout_checks(pg2, "patient attest", 360)
    pg2.locator("#att-btn").click(); pg2.locator("#pipe").wait_for(timeout=10000)
    check("S5 after the patient confirms: ready for the first visit @360", "ready for your first visit" in pg2.locator("#pipe-summary").inner_text())
    ctx.close()
    # ---------------------------------------------------------------- S6: route elsewhere is clinician-only, patient sees 'we'll call'
    ctx = mk(1440); load(ctx, "notfit"); fid = first_task(ctx, "Finley", "fit_review")
    login(ctx, "pat", "office"); op = office(ctx, fid)
    check("S6 front desk sees Route elsewhere disabled + why", op.locator("#do-route_elsewhere").is_disabled() and "never declines" in op.locator("#d-do").inner_text())
    login(ctx, "yakel", "office"); op.reload(); op.locator("#do-route_elsewhere").wait_for()
    op.locator("#do-route_elsewhere").click(); op.fill("#f-route_elsewhere-reason", "Knee is primary - suggest a knee clinic (example, staff only)"); op.locator("#dosub-route_elsewhere").click(); op.locator("#do-st").filter(has_text="Done").wait_for(timeout=8000)
    pg = portal(ctx); pg.locator("#pipe").wait_for(timeout=8000)
    check("S6 patient is asked to call us about next steps (no promise) and not the staff reason", "call us" in pg.locator("main").inner_text().lower() and "will call" not in pg.locator("main").inner_text() and "knee clinic" not in pg.content())   # preview19 Prompt C
    ctx.close()
    # ---------------------------------------------------------------- S7: ticking a red-flag box shows guidance immediately and creates the urgent task
    ctx = mk(360); load(ctx, "redflag", "intake")
    pg = portal(ctx, "#/intake"); pg.locator("#intake").wait_for(timeout=8000)
    wiz(pg, 5)
    check("S7 guidance hidden until a symptom is ticked @360", not pg.locator("#rf-alert").is_visible())
    pg.locator("label[for='rf-bladder_bowel']").click()
    check("S7 ticking a red-flag box shows 911 / call-the-office guidance at once @360", pg.locator("#rf-alert").is_visible() and pg.locator("#rf-alert a[href='tel:911']").is_visible())
    pg.locator("#rf-task").filter(has_text="urgent task").wait_for(timeout=8000)
    check("S7 the page confirms the urgent nurse task was created (saved on the server) @360", "does not reach anyone instantly" in pg.locator("#rf-task").inner_text())
    layout_checks(pg, "red-flag guidance in intake", 360)
    login(ctx, "nina", "office"); q = ctx.new_page(); watch(q, "office-q7"); q.goto(BASE + "/office.html#/queue"); q.locator("#nextup .nextup").wait_for(timeout=8000)
    check("S7 nurse's 'Next up' is Gray's red-flag task", "Gray Example" in q.locator("#nextup").inner_text())
    q.locator("#filters button[data-f=urgent]").click(); q.wait_for_timeout(700)
    check("S7 'Urgent' filter lists Gray first", "Gray Example" in q.locator("#qlist .qrow").first.inner_text())
    ctx.close()
    # ---------------------------------------------------------------- presenter
    ctx = mk(1440); pp = ctx.new_page(); watch(pp, "presenter"); pp.goto(BASE + "/presenter.html"); pp.locator("#pm-toggle").click(); pp.locator("#scen-list article").first.wait_for(timeout=8000)
    check("presenter lists all eight scenario cards with load + jump buttons", pp.locator("#scen-list article").count() == 8 and pp.locator("#scen-list button:has-text('Jump to key state')").count() == 8)
    check("presenter spotlight tour lists 4 stops in order", pp.locator("#tour > li").count() == 4 and [x.split(":")[0] for x in pp.locator("#tour > li h3").all_inner_texts()] == ["Stop 1", "Stop 2", "Stop 3", "Stop 4"], pp.locator("#tour > li h3").all_inner_texts())
    pp.locator("#tour-2-go").click(); pp.locator("#tour-2-office").wait_for(timeout=8000)
    check("tour stop 2 sets up Cameron and offers portal + office links", "Cameron" in pp.locator("#tour-2-portal").inner_text() and "#/task/" in pp.locator("#tour-2-office").get_attribute("href"))
    pp.locator("#tour-2-days").click(); pp.locator("#tour-st").filter(has_text="automatic follow-up").wait_for(timeout=8000)
    check("tour stop 2 'follow-up date passes' sends an automatic follow-up (simulated)", "simulated" in pp.locator("#tour-st").inner_text().lower())
    for sid in ("1", "3a", "3b", "4a", "4b", "4c"):
        pp.locator(f"#tour-{sid}-go").click(); pp.locator("#tour-st").filter(has_text="ready").wait_for(timeout=8000); ok_ = "ready" in pp.locator("#tour-st").inner_text(); pp.evaluate("document.getElementById('tour-st').textContent=''")
        check(f"tour step {sid} loads", ok_)
    pp.locator("#sc-redflag-key").click(); pp.locator("#sc-st").filter(has_text="key state").wait_for(timeout=8000)
    check("presenter 'Jump to key state' loads scenario 7 and says who is signed in", "Gray Example" in pp.locator("#sc-st").inner_text())
    layout_checks(pp, "presenter scenarios", 1440, strict_small=False)
    ctx.close()
    br.close()
finally:
    srv.stop()
ERRS = [e for e in ERRS if not (e[0] == "login" and "status of 401" in e[1])]  # signed-out sign-in pages probe /me and get 401 by design
EXPECTED = [e for e in ERRS if "status of 422" in e[1]]  # the deliberate invalid submissions above (missing insurer reference, empty check-in worry)
# preview19: the incomplete intake is now caught on the page before it is sent, so it no longer produces a server 422 (2 instead of 3)
# preview19 Prompt B: an empty worry is now caught on the page before sending (the server still rejects it: api_surgery_test), so only the insurer-reference 422 remains
check("no JavaScript errors in any page (only the 1 deliberate 422 response is logged)", len(EXPECTED) == 1 and len(ERRS) == 1, ERRS[:6])
ext = [u for u in L.REQS if not u.startswith(BASE)]
check("no requests to any other host (no tracking / external services)", not ext, ext[:5])
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_pass2_test: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
json.dump(L.RESULTS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_pass2_test.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
