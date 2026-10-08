#!/usr/bin/env python3
"""preview19 Prompt D: usability + functional REVIEW walkthroughs (simulated, scripted browser runs - NOT testing with real patients).
Real local server on 127.0.0.1:8789 (temp DB, no worker), local Chrome via Playwright, fictional data only.
Viewports: 360x740, 390x844 (phones), 768x1024 (tablet), 1440x900 (desktop); large text (the portal's own 'Larger' setting);
keyboard-only passes (Tab / Shift+Tab / Enter / Space, no mouse).
Ten walkthroughs:
  1 patient waiting on records          2 correcting pre-filled intake      3 returning to an unfinished form
  4 finding appointment details         5 assistant: administrative question 6 assistant: question it can't safely answer
  7 submitting a post-op concern        8 failed submission then retry      9 authorized caregiver helping
 10 staff handling urgent before routine
Every visited screen also gets generic audits: horizontal scroll, clipped controls, 44px targets, unlabeled fields, duplicate ids,
empty links, unnamed buttons, buttons with no click handler anywhere up the tree (CDP), body text size, and content hidden under the
phone tab bar.  Screenshots: ../preview19-shots/review-*.png.  axe-core: NOT RUN (not installed; would be a new dependency)."""
import json, os, re, sys, tempfile, time, uuid
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8789")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
SHOTS = L.SHOTS_DIR; os.makedirs(SHOTS, exist_ok=True)
ERRS = []; NOTES = []; COUNT = {"screens": 0, "keyboard_steps": 0, "controls_checked": 0}
VIEW = {"360": (360, 740), "390": (390, 844), "768": (768, 1024), "1440": (1440, 900)}
def note(msg): NOTES.append(msg); print("NOTE " + msg, flush=True)
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def shot(pg, name, el=None, full=False):
    pg.wait_for_timeout(250); p = os.path.join(SHOTS, f"review-{name}.png"); (el.screenshot(path=p) if el is not None else pg.screenshot(path=p, full_page=full))
def mk(br, vw, large=False):
    W, H = VIEW[vw]; c = br.new_context(viewport={"width": W, "height": H}, has_touch=W < 800, is_mobile=False)
    if large: c.add_init_script("try { localStorage.setItem('ps.largeText', '1'); } catch (e) {}")
    api(c, "POST", "/api/presenter/enter", {}); return c
def load(c, key, step="key", helper=False, office_as=None):
    s, j = api(c, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "as_helper": helper, "office_as": office_as}); assert s == 200, (key, step, s, j); return j
def login(c, who, app): s, j = api(c, "POST", "/api/login", {"persona": who, "app": app}); assert s == 200, (who, app, s, j)
def portal(c, h="#/home", wait="main h1", tag="portal"):
    pg = c.new_page(); watch(pg, tag); pg.goto(BASE + "/portal.html" + h); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(350); return pg
def office(c, h="#/queue", wait="#qlist .tcard", tag="office"):
    pg = c.new_page(); watch(pg, tag); pg.goto(BASE + "/office.html" + h); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(350); return pg

JS_AUDIT = r"""() => {
  const vis = el => { const cs = getComputedStyle(el), r = el.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0 && !el.closest('[hidden], dialog:not([open]), details:not([open]) > :not(summary)'); };
  const o = {unlabeled: [], dup: [], emptyLinks: [], unnamed: [], smallBody: [], under: [], tiny: []};
  for (const el of document.querySelectorAll('input:not([type=hidden]), select, textarea')) {
    if (!vis(el) && !(el.type === 'radio' || el.type === 'checkbox')) continue;
    const id = el.id, lab = (id && document.querySelector('label[for="' + CSS.escape(id) + '"]')) || el.closest('label') || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
    if (!lab) o.unlabeled.push(id || el.name || el.type); }
  const ids = {}; for (const el of document.querySelectorAll('[id]')) ids[el.id] = (ids[el.id] || 0) + 1; o.dup = Object.keys(ids).filter(k => ids[k] > 1);
  for (const a of document.querySelectorAll('a')) { if (!vis(a)) continue; const h = a.getAttribute('href'); if (!h || h === '#') o.emptyLinks.push(a.id || a.textContent.trim().slice(0, 40)); }
  for (const b of document.querySelectorAll('button, a, [role=button]')) { if (!vis(b)) continue; if (!(b.textContent.trim() || b.getAttribute('aria-label') || b.getAttribute('title'))) o.unnamed.push(b.id || b.className); }
  for (const p of document.querySelectorAll('main p, main li, main dd, main blockquote')) {
    if (!vis(p) || !p.textContent.trim() || p.closest('.small, .fine, .counter, .chip, .tag, .why, .muted, .kicker, .lastcheck, .meta, .src, .badge-row, .istatus, footer, .qact, .tmore') || p.matches('.small, .fine, .counter, .muted, .kicker, .lastcheck, .why, .istatus, .pfl, .pfst, .ind, #in-stepn, .as-who')) { const f2 = parseFloat(getComputedStyle(p).fontSize); if (vis(p) && p.textContent.trim() && f2 < 14) o.tiny.push((p.id || p.className) + ':' + f2); continue; }
    const fs = parseFloat(getComputedStyle(p).fontSize); if (fs < 17.5) o.smallBody.push((p.id || p.className || p.tagName) + ':' + fs + ':' + p.textContent.trim().slice(0, 30)); }
  const nav = document.querySelector('#nav.tabbar'); if (nav && getComputedStyle(nav).position === 'fixed' && vis(nav)) {
    const nr = nav.getBoundingClientRect(); window.scrollTo(0, document.documentElement.scrollHeight);
    const last = [...document.querySelectorAll('main *, footer *')].filter(e => vis(e) && e.children.length === 0 && e.textContent.trim()).pop();
    if (last) { const r = last.getBoundingClientRect(); if (r.bottom > nav.getBoundingClientRect().top + 1) o.under.push((last.id || last.tagName) + ':' + Math.round(r.bottom) + '>' + Math.round(nav.getBoundingClientRect().top)); }
    window.scrollTo(0, 0); }
  o.smallBody = o.smallBody.slice(0, 6); return o; }"""

def dead_controls(pg):
    """Buttons that are enabled and visible but have no click/submit handler on themselves or any ancestor (checked with Chrome DevTools Protocol)."""
    cdp = pg.context.new_cdp_session(pg)
    try:
        res = cdp.send("Runtime.evaluate", {"expression": """(() => { const vis = el => { const cs = getComputedStyle(el), r = el.getBoundingClientRect(); return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
            const bs = [...document.querySelectorAll('button:not([disabled])')].filter(vis); const set = new Set(); bs.forEach(b => { let e = b; while (e) { set.add(e); e = e.parentElement; } }); set.add(document); set.add(window);
            window.__dc = {bs, all: [...set]}; return [...set].length; })()""", "returnByValue": True})
        arr = cdp.send("Runtime.evaluate", {"expression": "window.__dc.all"})["result"]["objectId"]
        props = cdp.send("Runtime.getProperties", {"objectId": arr, "ownProperties": True})["result"]
        has = set()
        for pr in props:
            if not pr["name"].isdigit() or "objectId" not in pr.get("value", {}): continue
            ls = cdp.send("DOMDebugger.getEventListeners", {"objectId": pr["value"]["objectId"]})["listeners"]
            if any(x["type"] in ("click", "submit", "pointerdown", "pointerup", "mousedown", "keydown") for x in ls): has.add(int(pr["name"]))
        out = cdp.send("Runtime.evaluate", {"expression": "JSON.stringify(window.__dc.bs.map(b => { const ix = []; let e = b; while (e) { ix.push(window.__dc.all.indexOf(e)); e = e.parentElement; } ix.push(window.__dc.all.indexOf(document), window.__dc.all.indexOf(window)); return {id: b.id || b.textContent.trim().slice(0, 30), ix, submit: b.type === 'submit' && !!b.form}; }))", "returnByValue": True})["result"]["value"]
        bs = json.loads(out); COUNT["controls_checked"] += len(bs)
        return [b["id"] for b in bs if not b["submit"] and not any(i in has for i in b["ix"])]
    finally: cdp.detach()

def audit(pg, name, vw, strict=True):
    COUNT["screens"] += 1; W = VIEW[vw][0]
    layout_checks(pg, f"{name}", W, strict_small=strict)
    a = pg.evaluate(JS_AUDIT)
    check(f"every field has a label: {name} @{vw}", not a["unlabeled"], a["unlabeled"])
    check(f"no duplicate element ids: {name} @{vw}", not a["dup"], a["dup"][:5])
    check(f"no empty links / unnamed buttons: {name} @{vw}", not a["emptyLinks"] and not a["unnamed"], (a["emptyLinks"][:3], a["unnamed"][:3]))
    check(f"body text >= 18px (captions/status lines >= 16px, fine print >= 14px): {name} @{vw}", not a["smallBody"] and not a["tiny"], (a["smallBody"], a["tiny"][:4]))
    check(f"nothing at the end of the page is hidden under the phone tab bar: {name} @{vw}", not a["under"], a["under"])
    d = dead_controls(pg); check(f"no dead buttons (every enabled button has a handler): {name} @{vw}", not d, d[:5])
    if not strict:
        sm = pg.evaluate(L.JS_SMALL)
        if sm: note(f"office/desktop screen '{name}' @{vw}: {len(sm)} controls under 44px tall (staff screen, not held to the patient 44px rule): {sm[:4]}")

def kb_walk(pg, name, vw, n=30, start="body"):
    """Keyboard only: Tab through the page; every stop must be visible, show a focus ring and not sit under a fixed bar."""
    pg.evaluate("() => { document.activeElement && document.activeElement.blur(); window.scrollTo(0,0); }"); pg.locator(start).first.focus() if start != "body" else None
    bad, stops = [], []
    for i in range(n):
        pg.keyboard.press("Tab"); pg.wait_for_timeout(60); COUNT["keyboard_steps"] += 1
        r = pg.evaluate("""() => { const e = document.activeElement; if (!e || e === document.body) return null; const cs = getComputedStyle(e), r = e.getBoundingClientRect();
          const ring = (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 2) || (cs.boxShadow && cs.boxShadow !== 'none');
          const lab = e.closest('label'), ringLab = lab ? (getComputedStyle(lab).outlineStyle !== 'none' || getComputedStyle(lab).boxShadow !== 'none') : false;
          const cx = Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1), cy = Math.min(Math.max(r.top + Math.min(r.height / 2, 20), 1), innerHeight - 1);
          const top = document.elementFromPoint(cx, cy); const covered = !!top && !(e.contains(top) || top.contains(e) || (lab && lab.contains(top)));
          const sr = e.type === 'radio' || e.type === 'checkbox';
          return {id: e.id || e.tagName + ':' + (e.textContent || '').trim().slice(0, 24), ring: ring || ringLab, inview: r.bottom > 0 && r.top < innerHeight, covered: covered && !sr, coveredBy: covered ? (top.id || top.className || top.tagName) : '', sr}; }""")
        if not r: continue
        stops.append(r["id"])
        if not r["inview"] or r["covered"] or not r["ring"]: bad.append(r)
    check(f"keyboard: every Tab stop is visible, has a focus ring and isn't covered: {name} @{vw}", not bad and len(stops) >= 3, bad[:4])
    return stops

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "ui_review.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])

    # ============ 1. a patient waiting on records (Blake, 'missing' scenario)
    for vw in ("360", "390", "768", "1440"):
        c = mk(br, vw); load(c, "missing"); pg = portal(c, wait="#hero")
        hero = pg.locator("#hero").inner_text()
        check(f"W1 Home says what's happening (records) and whether Blake must act @{vw}", "records" in hero.lower() and ("Do you need to do anything" in hero or "need" in hero.lower()), hero[:200])
        nothing = re.search(r"nothing is needed from you|you don.t need to", hero, re.I); big = pg.locator("#hero .btn.big").count()
        check(f"W1 no conflicting instruction: 'nothing needed' never sits next to a big action button @{vw}", not (nothing and big), (bool(nothing), big))
        lc = pg.locator(".lastcheck").all_inner_texts()
        check(f"W1 'last verified' shows a time and no staff name or fax note @{vw}", lc and all("PT" in x and not re.search(r"Pat|Nina|fax", x) for x in lc), lc)
        audit(pg, "W1 Home waiting on records", vw)
        if vw in ("390", "768", "1440"): shot(pg, f"01-records-waiting-{vw}", full=(vw != "1440"))
        if vw == "390":
            kb_walk(pg, "W1 Home", vw, 25)
            d = pg.locator("#hero details, main details").first
            if d.count(): d.locator("summary").focus(); pg.keyboard.press("Enter"); pg.wait_for_timeout(200); check("W1 keyboard: Enter opens the Details disclosure", d.evaluate("e => e.open"))
            pg.locator("#nav button[data-view=records], #nav a[href='#/records']").first.click(); pg.locator("main h1").first.wait_for(); pg.wait_for_timeout(400)
            audit(pg, "W1 Records tab", vw); shot(pg, "01-records-tab-390", full=True)
        c.close()

    # ============ 2. correcting pre-filled intake (Avery, 'clean' at the intake step)
    for vw in ("360", "390", "768", "1440"):
        c = mk(br, vw); load(c, "clean", "intake"); pg = portal(c, wait="#hero")
        pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000); pg.wait_for_timeout(300)
        audit(pg, "W2 intake step 1", vw)
        pg.locator("label[for=pf-name-ok]").click()
        if pg.locator("label[for=pf-dob-ok]").count(): pg.locator("label[for=pf-dob-ok]").click()
        pg.locator("label[for=pf-phone-change]").click(); pg.fill("#pf-c-phone", "(208) 555-0199 (example)")
        if vw in ("390", "1440"): shot(pg, f"02-intake-correction-{vw}", pg.locator("#pf-phone"))
        for step in (2, 3):
            pg.locator("#in-next").click(); pg.locator(f"#in-step-{step}").wait_for(state="visible")
            for k in pg.evaluate(f"() => [...document.querySelectorAll('#in-step-{step} .pf')].map(e => e.id.slice(3))"):
                pg.locator(f"label[for=pf-{k}-ok]").click()
            if pg.locator(f"#in-step-{step} #in-fac").count(): pg.fill("#in-fac", "")
        pg.locator("#in-next").click(); pg.locator("#in-step-4").wait_for(state="visible"); pg.locator("label[for=cp-text]").click(); pg.locator("label[for=mt-0]").click()
        pg.locator("#in-next").click(); pg.locator("#in-step-5").wait_for(state="visible"); pg.locator("label[for=rf-none]").click()
        pg.locator("#in-next").click(); pg.locator("#in-step-6").wait_for(state="visible"); pg.wait_for_timeout(300)
        rv = pg.locator("#in-review").inner_text()
        check(f"W2 review shows the correction (not the old value as confirmed) @{vw}", "(208) 555-0199 (example)" in rv, rv[:300])
        audit(pg, "W2 intake review", vw)
        if vw in ("390", "768", "1440"): shot(pg, f"02-intake-review-{vw}", full=(vw == "390"))
        pg.locator("label[for=in-confirm]").click(); pg.locator("#in-send").click(); pg.locator("#in-done").wait_for(timeout=10000)
        done = pg.locator("#in-done").inner_text()
        check(f"W2 success message is specific (what was sent, when) and does not overclaim @{vw}", "received it at" in done and not re.search(r"approved|confirmed your (visit|appointment)|you.re all set", done, re.I), done[:200])
        so = mk(br, "1440"); login(so, "yakel", "office"); s, q = api(so, "GET", "/api/o/queue?filter=all")
        t = next(x for x in q["tasks"] if x["patient_name"].startswith("Avery") and x.get("case_id"))
        s, d = api(so, "GET", f"/api/o/tasks/{t['id']}"); sm = d.get("summary") or {}
        check(f"W2 staff summary carries the correction word for word, marked as the patient's @{vw}", any("(phone)" in x["topic"] and x["text"] == "(208) 555-0199 (example)" for x in sm.get("statements", [])), [x["topic"] for x in sm.get("statements", [])])
        so.close(); c.close()

    # ============ 3. returning to an unfinished form (Drew, 'nointake' at the intake step)
    for vw in ("390", "360"):
        c = mk(br, vw); load(c, "nointake", "intake"); pg = portal(c, wait="#hero")
        pg.locator("#na-intake").click(); pg.locator("#intake").wait_for(timeout=8000)
        pg.locator("label[for=pf-name-ok]").click(); pg.locator("label[for=pf-dob-ok]").click() if pg.locator("label[for=pf-dob-ok]").count() else None
        pg.locator("label[for=pf-phone-change]").click(); pg.fill("#pf-c-phone", "(208) 555-0177 (example)")
        pg.locator("#in-next").click(); pg.locator("#in-step-2").wait_for(state="visible"); pg.locator("#in-ind").filter(has_text="Draft saved").wait_for(timeout=8000)
        ind = pg.locator("#in-ind").inner_text(); check(f"W3 the form says the draft is saved on the server @{vw}", "saved" in ind.lower(), ind)
        pg.goto(BASE + "/portal.html#/home"); pg.locator("#hero").wait_for(timeout=8000); pg.wait_for_timeout(300)
        btn = pg.locator("#hero #na-intake")
        check(f"W3 Home offers 'Continue your intake form' (not 'Start') @{vw}", btn.count() == 1 and "Continue" in btn.inner_text(), btn.inner_text() if btn.count() else pg.locator("#hero").inner_text()[:200])
        if vw == "390": shot(pg, "03-return-home-390")
        ctx2 = mk(br, vw); load_cookie = c.cookies(); ctx2.add_cookies(load_cookie); pg2 = portal(ctx2, "#/intake", wait="#intake")
        pg2.wait_for_timeout(500)
        check(f"W3 coming back (new tab, same sign-in) restores the step and the correction @{vw}", pg2.locator("#in-step-2").is_visible() or ("(208) 555-0177" in (pg2.locator("#pf-c-phone").input_value() if pg2.locator("#pf-c-phone").count() else "")), pg2.locator("#in-stepn").inner_text())
        pg2.locator("#in-back").click() if pg2.locator("#in-step-2").is_visible() else None; pg2.wait_for_timeout(200)
        check(f"W3 the earlier answers are still there after returning @{vw}", pg2.locator("#pf-phone-change").is_checked() and pg2.input_value("#pf-c-phone") == "(208) 555-0177 (example)")
        if vw == "390": shot(pg2, "03-return-restored-390")
        audit(pg2, "W3 returned intake", vw); ctx2.close(); c.close()

    # ============ 4. finding appointment details (Avery, 'clean' booked)
    for vw in ("390", "768", "1440"):
        c = mk(br, vw); load(c, "clean", "booked"); pg = portal(c, wait="#hero")
        hero = pg.locator("#hero").inner_text()
        check(f"W4 Home shows the visit date/time and clinician up front @{vw}", re.search(r"\d{1,2}:\d\d (AM|PM)", pg.locator("main").inner_text()) and "Yakel" in pg.locator("main").inner_text(), hero[:200])
        pg.locator("#nav button[data-view=visits], #nav a[href='#/visits']").first.click(); pg.locator("#appt-card").wait_for(); pg.wait_for_timeout(300)
        vt = pg.locator("main").inner_text()
        check(f"W4 Visits: date, time, clinician, address and phone are all there @{vw}", re.search(r"\d{1,2}:\d\d (AM|PM) PT", vt) and "Yakel" in vt and "850 W Ironwood" in vt and "770-3536" in vt, vt[:300])
        audit(pg, "W4 Visits", vw); shot(pg, f"04-appointment-{vw}", full=(vw == "390"))
        pg.goto(BASE + "/portal.html#/home"); pg.locator("#hero").wait_for(); pg.wait_for_timeout(300)
        cb = pg.locator("#na-confirm")
        if cb.count():
            reqs = []; pg.on("request", lambda r: reqs.append(r.url) if r.method == "POST" and "/confirm" in r.url else None)
            cb.dblclick(); pg.wait_for_timeout(1200)
            check(f"W4 'Confirm I'm coming' double-click sends one request and shows a clear result @{vw}", len(reqs) == 1 and re.search(r"confirm", pg.locator("main").inner_text(), re.I), reqs)
        c.close()

    # ============ 5 + 6. the assistant: an administrative question, and one it can't safely answer
    for vw in ("390", "360", "1440"):
        c = mk(br, vw); load(c, "clean", "booked"); pg = portal(c, "#/assist", wait="#as-ask")
        pg.fill("#as-q", "What are your office hours?"); pg.locator("#as-btn").click(); pg.locator("#as-answer").wait_for(timeout=8000); pg.wait_for_timeout(300)
        a5 = pg.locator("#as-answer").inner_text()
        check(f"W5 admin question answered, labelled 'not a person', no invented hours @{vw}", "not a person" in a5.lower() and not re.search(r"\b\d{1,2}\s?(am|pm)\s?[-–]\s?\d", a5, re.I), a5[:300])
        audit(pg, "W5 assistant answer", vw); shot(pg, f"05-assistant-admin-{vw}") if vw in ("390", "1440") else None
        pg.fill("#as-q", "Should I double my pain medicine tonight?"); pg.locator("#as-btn").click(); pg.wait_for_timeout(900); pg.locator("#as-answer").wait_for(timeout=8000)
        a6 = pg.locator("#as-answer").inner_text()
        check(f"W6 medicine question: no advice, sends the person to the clinical team, offers to send it @{vw}", re.search(r"(can.t|cannot|not able)", a6, re.I) and re.search(r"(nurse|clinical|care team)", a6, re.I) and not re.search(r"\byes\b|\bdouble it\b|you can take", a6, re.I), a6[:300])
        shot(pg, f"06-assistant-unsafe-{vw}") if vw in ("390", "1440") else None
        pg.fill("#as-q", "I can't feel my legs and lost bladder control"); pg.wait_for_timeout(300)
        check(f"W6 emergency wording shows 911 guidance before anything is sent @{vw}", "911" in pg.locator("#as-em").inner_text(), pg.locator("#as-em").inner_text()[:200])
        if vw == "390": shot(pg, "06-assistant-emergency-390"); kb_walk(pg, "W5/6 assistant", vw, 20)
        c.close()

    # ============ 7. submitting a post-op concern (Harper, surgery post-op) + staff side
    for vw in ("390", "768", "1440"):
        c = mk(br, vw); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")
        audit(pg, "W7 post-op check-in", vw)
        labs = pg.evaluate("() => [...document.querySelectorAll('#ck-form label.choice')].map(l => l.getAttribute('for'))")
        worry = labs[-1]; pg.locator(f"label[for={worry}]").click(); pg.locator("#ck-send").click(); pg.wait_for_timeout(400)
        check(f"W7 a worry with no words is refused with a clear message (nothing sent) @{vw}", pg.locator("#ck-receipt").count() == 0 and pg.locator("#ck-st").inner_text().strip(), pg.locator("#ck-st").inner_text())
        pg.fill("#ck-note", "Example (fictional): the wound looks redder today and feels warm."); pg.locator("#ck-send").click(); pg.locator("#ck-receipt").wait_for(timeout=8000); pg.wait_for_timeout(300)
        rc = pg.locator("#ck-receipt").inner_text()
        check(f"W7 receipt: reference, what was sent (verbatim), who it reached, 911 reminder, no call-back promise @{vw}", "redder today" in rc and re.search(r"CI-\d+", rc) and "911" in rc and not re.search(r"will (call|phone) you", rc, re.I), rc[:300])
        shot(pg, f"07-postop-concern-receipt-{vw}", pg.locator("#ck-card") if vw != "390" else None, full=(vw == "390"))
        so = mk(br, "1440"); login(so, "nina", "office"); s, q = api(so, "GET", "/api/o/queue?filter=mine")
        check(f"W7 the concern is pinned as urgent for the nurse, whatever the filter @{vw}", any(t["patient_name"].startswith("Harper") for t in q["pinned"]), [t["patient_name"] for t in q["pinned"]])
        so.close(); c.close()

    # ============ 8. a failed submission then retry (Messages)
    for vw in ("390", "360", "1440"):
        c = mk(br, vw); load(c, "clean", "booked"); pg = portal(c, "#/messages", wait="#msg-body")
        pg.locator("label[for=cat-billing]").click(); body = f"Example (fictional) billing question about my statement {vw}."
        pg.fill("#msg-body", body)
        keys = []; mode = {"fail": True}
        def h(route, req):
            keys.append(req.headers.get("idempotency-key"))
            route.abort("internetdisconnected") if mode["fail"] else route.continue_()
        pg.route("**/api/p/messages", h)
        pg.locator("#msg-send").click(); pg.wait_for_timeout(900)
        st = pg.locator("#msg-status").inner_text()
        check(f"W8 failure: says it was NOT sent, keeps the text, offers Try again @{vw}", re.search(r"not sent|not confirmed", st, re.I) and pg.input_value("#msg-body") == body and re.search(r"try", pg.locator("#msg-send").inner_text(), re.I), (st, pg.locator("#msg-send").inner_text()))
        check(f"W8 failure: no success wording anywhere on the page @{vw}", not re.search(r"\bsent at\b|we.ve received|message sent", pg.locator("main").inner_text(), re.I))
        shot(pg, f"08-failed-send-{vw}", full=(vw == "390")) if vw in ("390", "1440") else None
        mode["fail"] = False; pg.locator("#msg-send").click(); pg.wait_for_timeout(1500)
        s, th = api(c, "GET", "/api/p/threads"); mine = [t for t in th["threads"] if body[:40] in t.get("preview", "")]
        check(f"W8 retry: exactly one message reached the office, same idempotency key @{vw}", len(mine) == 1 and len(keys) == 2 and keys[0] == keys[1], (len(mine), keys))
        check(f"W8 retry: success state is clear and the box is cleared @{vw}", pg.input_value("#msg-body") == "" and re.search(r"(sent|received)", pg.locator("main").inner_text(), re.I))
        if vw == "390": shot(pg, "08-retry-sent-390", full=True)
        pg.unroute("**/api/p/messages"); c.close()

    # ============ 9. an authorized caregiver helping (Frankie for Emery)
    for vw in ("390", "1440"):
        c = mk(br, vw); load(c, "caregiver", "intake", helper=True); pg = portal(c, wait="main h1")
        h1 = pg.locator("main h1").first.inner_text()
        check(f"W9 helper sees whose portal it is (not 'Hello, Frankie') @{vw}", "Viewing" in h1 and "Emery" in h1, h1)
        audit(pg, "W9 helper Home", vw); shot(pg, f"09-caregiver-home-{vw}", full=(vw == "390"))
        pg.goto(BASE + "/portal.html#/settings"); pg.locator("#set-rem h2").wait_for(timeout=8000); pg.wait_for_timeout(500)
        check(f"W9 helper can't change the patient's reminder setting (read-only, says why) @{vw}", pg.locator("#rem-toggle").count() == 0 and "Only the patient" in pg.locator("#set-rem").inner_text())
        c.close()

    # ============ 10. staff handling urgent before routine
    for vw in ("1440", "768", "390"):
        c = mk(br, vw)
        for k in ("clean", "missing", "redflag"): load(c, k)
        login(c, "pat", "portal") if False else None
        api(c, "POST", "/api/login", {"persona": "avery", "app": "portal"}); api(c, "POST", "/api/p/messages", {"category": "medical", "body": "Example (fictional): sudden numbness in both legs"}, key=f"rv-emerg-{vw}")
        for who in ("nina", "pat"):
            login(c, who, "office"); pg = office(c)
            nu = pg.locator("#nextup-card").inner_text()
            if who == "nina": check(f"W10 nurse: Do next is urgent and comes first @{vw}", "urgent" in (pg.locator("#nextup-card").get_attribute("class") or "") and pg.evaluate("() => document.querySelector('#qlist').firstElementChild.id") == "pinned", nu[:200])
            else: check(f"W10 front desk: told urgent items exist and who owns them, before any routine work; booking held @{vw}", "Urgent first" in nu and "Book the visit" not in nu, nu[:300])
            audit(pg, f"W10 office board ({who})", vw, strict=False)
            shot(pg, f"10-staff-urgent-{who}-{vw}", full=(vw == "390"))
            if vw == "1440" and who == "nina": kb_walk(pg, "W10 office board", vw, 30)
            pg.close()
        c.close()

    # ============ large text (the portal's own 'Larger' setting) on the walkthrough screens
    for vw in ("360", "390"):
        c = mk(br, vw, large=True); load(c, "missing")
        for h_, w_, nm in (("#/home", "#hero", "Home"), ("#/messages", "#msg-body", "Messages"), ("#/assist", "#as-ask", "Assistant"), ("#/settings", "#set-rem h2", "Settings")):
            pg = portal(c, h_, wait=w_); check(f"large text is on @{vw}: {nm}", pg.evaluate("document.documentElement.classList.contains('lt') || document.body.classList.contains('lt') || localStorage.getItem('ps.largeText') === '1'"))
            ov = pg.evaluate(L.JS_OVERFLOW); check(f"large text: no horizontal scroll: {nm} @{vw}", ov["sw"] <= ov["iw"] + 1, ov)
            cl = pg.evaluate(L.JS_CLIPPED); check(f"large text: no controls cut off: {nm} @{vw}", not cl, cl[:4])
            COUNT["screens"] += 1
            if nm == "Home": shot(pg, f"11-large-text-home-{vw}", full=True)
            pg.close()
        load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card"); ov = pg.evaluate(L.JS_OVERFLOW); check(f"large text: post-op check-in fits @{vw}", ov["sw"] <= ov["iw"] + 1, ov); pg.close()
        c.close()

    # ============ keyboard-only: complete one task end to end with no mouse (send a message)
    c = mk(br, "390"); load(c, "clean", "booked"); pg = portal(c, "#/messages", wait="#msg-body")
    pg.locator("#cat-billing").focus(); pg.keyboard.press("Space"); pg.locator("#msg-body").focus(); pg.keyboard.type("Example (fictional): keyboard-only question about a bill.")
    pg.keyboard.press("Tab"); fid = pg.evaluate("document.activeElement.id")
    while fid != "msg-send" and COUNT["keyboard_steps"] < 100000:
        pg.keyboard.press("Tab"); fid = pg.evaluate("document.activeElement.id"); COUNT["keyboard_steps"] += 1
        if fid in ("", None) and pg.evaluate("document.activeElement === document.body"): break
    check("keyboard only: Tab reaches 'Send message' straight after the text box (no traps)", fid == "msg-send", fid)
    pg.keyboard.press("Enter"); pg.wait_for_timeout(1200)
    check("keyboard only: Enter on Send sends it and the result is announced (status region)", re.search(r"(sent|received)", pg.locator("#msg-status").inner_text(), re.I) and pg.locator("#msg-status").get_attribute("role") in ("status", "alert") or pg.locator("#msg-status").get_attribute("aria-live"), pg.locator("#msg-status").inner_text())
    shot(pg, "12-keyboard-sent-390"); c.close()

    # ============ loading / empty / error states
    c = mk(br, "390"); load(c, "clean", "booked"); pg = c.new_page(); watch(pg, "states")
    held = []; pg.route("**/api/p/home", lambda r: held.append(r))
    pg.goto(BASE + "/portal.html#/home"); pg.wait_for_timeout(1200)
    lt = pg.locator("main").inner_text().strip()
    check("loading state: something is shown while Home loads (not a blank page)", bool(lt), lt[:120]); shot(pg, "13-state-loading-390")
    for r in held: r.abort("internetdisconnected")
    pg.unroute("**/api/p/home"); pg.wait_for_timeout(800)
    et = pg.locator("main").inner_text()
    check("error state: says what failed, gives the phone number and a way to try again", "couldn" in et.lower() and "770-3536" in et and pg.locator("main button:has-text('Try again')").count() == 1, et[:200])
    shot(pg, "13-state-error-390")
    if pg.locator("main button:has-text('Try again')").count():
        pg.locator("main button:has-text('Try again')").click(); pg.locator("#hero").wait_for(timeout=8000); check("error state: 'Try again' recovers the page", pg.locator("#hero").is_visible())
    pg.goto(BASE + "/portal.html#/messages"); pg.locator("#threads").wait_for(); pg.wait_for_timeout(600)
    check("empty state: no conversations says so plainly", "No conversations yet" in pg.locator("#threads").inner_text(), pg.locator("#threads").inner_text()[:100]); shot(pg, "13-state-empty-390", pg.locator("#threads").locator("xpath=ancestor::section[1]"))
    c.close()
    br.close()
finally:
    srv.stop()
ERRS = [e for e in ERRS if "status of 401" not in e[1] and "ERR_INTERNET_DISCONNECTED" not in e[1] and "net::ERR_FAILED" not in e[1]]
check("no JavaScript errors in any page", not ERRS, ERRS[:6])
ext = [u for u in L.REQS if not u.startswith(BASE)]
check("no requests to any other host", not ext, ext[:5])
print("SKIP axe-core: NOT RUN (not installed; adding it would be a new dependency)")
print(f"COVERAGE screens audited: {COUNT['screens']}, keyboard Tab steps: {COUNT['keyboard_steps']}, buttons checked for handlers: {COUNT['controls_checked']}, notes: {len(NOTES)}")
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_review: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
json.dump({"results": L.RESULTS, "notes": NOTES, "coverage": COUNT}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_review.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
