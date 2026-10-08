#!/usr/bin/env python3
"""preview18 design tests (Apple-Health-style restyle). Real local server, local Chrome, fictional data only.
Checks the new interface pieces, not the look: phone tab bar vs desktop top tabs, one "Your next step" hero, the
package-style progress tracker, the step-by-step intake wizard (progress bar, Next/Back, tap-to-pick chips,
confirm/edit for pre-filled values, completion check), the office task board (New / Waiting / Stuck / Ready,
stacked on phones, colour only where action is needed, one-click Do next), the large-text toggle persisting in
localStorage (the only stored key), prefers-reduced-motion, the DEMO banner, visible focus and inline SVG icons."""
import json, os, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8779")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
ERRS = []
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def load(ctx, key, step="key", office_as=None):
    api(ctx, "POST", "/api/presenter/enter", {}); s, j = api(ctx, "POST", "/api/presenter/scenario/load", {"key": key, "step": step, "office_as": office_as}); assert s == 200, (key, s, j); return j
def portal(ctx, hash_="#/home", wait="main h1"):
    pg = ctx.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html" + hash_); pg.locator(wait).first.wait_for(timeout=8000); pg.wait_for_timeout(250); return pg
def wiz(pg, n): pg.evaluate("document.getElementById('in-allsteps').open = true"); pg.locator(f"#in-stepbtn-{n}").click()  # preview19: step list sits in an 'All steps' disclosure; pg.locator(f"#in-step-{n}").wait_for(state="visible", timeout=8000)

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "ui_design.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    mk = lambda w, **kw: br.new_context(viewport={"width": w, "height": 844 if w < 800 else 900}, **kw)

    # ---------- navigation: bottom tab bar on phones, top tabs on desktop
    for w in (360, 390, 1440):
        c = mk(w); load(c, "missing"); pg = portal(c, wait="#hero")
        nv = pg.evaluate("""() => { const n=document.querySelector('#nav'), r=n.getBoundingClientRect(), m=document.querySelector('main').getBoundingClientRect();
          return {pos:getComputedStyle(n).position, bottom:r.bottom, top:r.top, ih:innerHeight, mainTop:m.top, labels:[...n.querySelectorAll('button')].map(b=>b.textContent.trim()),
                  svgs:n.querySelectorAll('button svg').length, imgs:n.querySelectorAll('img').length, minh:Math.min(...[...n.querySelectorAll('button')].map(b=>b.getBoundingClientRect().height)),
                  pb:parseFloat(getComputedStyle(document.body).paddingBottom), h:r.height}; }""")
        check(f"nav has Home, Visits, Messages, Records with inline SVG icons (no icon images) @{w}", nv["labels"] == ["Home", "Visits", "Messages", "Records"] and nv["svgs"] == 4 and nv["imgs"] == 0, nv)
        check(f"nav targets are at least 44px tall @{w}", nv["minh"] >= 44, nv["minh"])
        if w < 860:
            check(f"phone: nav is a bottom tab bar fixed to the screen bottom @{w}", nv["pos"] == "fixed" and abs(nv["bottom"] - nv["ih"]) <= 1, nv)
            check(f"phone: page has bottom padding at least the tab bar height, so it never covers content @{w}", nv["pb"] + 0.5 >= nv["h"], (nv["pb"], nv["h"]))
            pg.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)"); pg.wait_for_timeout(200)
            cov = pg.evaluate("""() => { const nav=document.querySelector('#nav').getBoundingClientRect(); const last=[...document.querySelectorAll('footer a, footer button')].pop().getBoundingClientRect(); return last.bottom <= nav.top + 0.5; }""")
            check(f"phone: scrolled to the bottom, the last footer control sits above the tab bar @{w}", cov)
        else:
            check(f"desktop: nav is in-flow top tabs above the content @{w}", nv["pos"] == "static" and nv["top"] < nv["mainTop"], nv)
        layout_checks(pg, f"patient home (new design)", w)
        c.close()

    # ---------- Home: one hero card + tracker
    c = mk(390); load(c, "missing"); pg = portal(c, wait="#hero")
    order = pg.evaluate("() => [...document.querySelectorAll('main > section, main > div.card, main > .card')].map(e => e.id || e.className).slice(0, 3)")
    # preview19: the hero answers "What's happening?" and "Do you need to do anything?"; while the office is chasing records nothing is
    # needed from the patient, so there is NO big button (one dominant action only when a patient action is needed)
    check("Home: the first card is the status card ('What’s happening')", order and order[0] == "hero", order)
    check("Home status card answers 'What’s happening' + 'Do you need to do anything?' and has no big button when nothing is needed", "What’s happening" in pg.locator("#hero").text_content() and "Do you need to do anything?" in pg.locator("#hero").text_content() and pg.locator("#hero .btn.big").count() == 0, pg.locator("#hero").text_content()[:160])
    tr = pg.evaluate("() => ({labels:[...document.querySelectorAll('#checklist li .cklabel')].map(l => l.textContent), states:[...document.querySelectorAll('#checklist li .ckstate')].map(l => l.textContent), cls:[...document.querySelectorAll('#checklist li')].map(l => l.className), note:document.querySelector('#ck-count').textContent, line:!!document.querySelector('#tracker')})")
    check("Home checklist (not a connected line) lists the parallel items with spelled-out states", len(tr["labels"]) >= 4 and len(tr["states"]) == len(tr["labels"]) and all(tr["states"]) and not tr["line"], tr)
    check("Home checklist says how many are done and that items finish in any order", tr["note"].startswith(f"{sum(1 for c in tr['cls'] if 's-done' in c)} of {len(tr['labels'])} done") and "any order" in tr["note"], tr)
    check("checklist states are text, not colour only (records rows say 'Waiting on reply')", "Waiting on reply" in tr["states"], tr["states"])
    c.close()
    c = mk(390); load(c, "nointake"); pg = portal(c, wait="#hero")
    check("Home hero: patient who owes the intake gets one big 'Start intake'-type button", pg.locator("#hero #na-intake.btn.big").count() == 1, pg.locator("#hero").text_content()[:120])
    c.close()
    c = mk(390); load(c, "surgery", "postop"); pg = portal(c, wait="#ck-card")   # preview19 Prompt B: post-op Home starts with the check-in card (#ck-card)
    tr = pg.evaluate("() => [...document.querySelectorAll('#checklist li .cklabel')].map(l => l.textContent)")
    check("post-op checklist lists the check-ins (day 2 ...)", pg.locator("#h-pipe").text_content() == "Your check-ins after surgery" and tr and all(t.startswith("Day ") and t.endswith("check-in") for t in tr), tr)
    check("post-op check-in is the first card, with three large choices and one Send button", pg.locator("#ck-card.hero #ck-form .choice").count() == 3 and pg.locator("#ck-card #ck-send").count() == 1)
    load(c, "surgery", "key"); pg.reload(); pg.locator("#hero").wait_for(timeout=8000)   # preview19 Prompt B: the date lives in the pre-op status card
    check("surgery date in the status card is labelled as an example date", "EXAMPLE DATE" in pg.locator("#surg-date").text_content().upper(), pg.locator("#surg-date").text_content()[:120])
    c.close()

    # ---------- Visits and Records views
    c = mk(1440); load(c, "missing"); pg = portal(c, "#/visits", wait="main h1:has-text('Visits')")
    check("Visits view: appointment card, 'Before your visit' and care team", pg.locator("#appt-card").count() == 1 and pg.locator("#h-ins").count() == 1 and pg.locator("#h-team").count() == 1, pg.locator("main").text_content()[:150])
    check("Visits tab is marked current", pg.locator("#nav button[data-view=visits]").get_attribute("aria-current") == "page")
    pg.locator("#nav button[data-view=records]").click(); pg.locator("main h1:has-text('Records')").wait_for(timeout=8000)
    check("Records view: checklist with details open, what we are waiting on, and the intake link", pg.locator("#checklist").count() == 1 and pg.locator("#pipe-more").evaluate("d => d.open") and "What we\u2019re waiting on" in pg.locator("main").text_content() and pg.locator("#rec-intake").count() == 1)
    c.close()

    # ---------- intake wizard
    for w in (390, 1440):
        c = mk(w); load(c, "clean", "intake"); pg = portal(c, "#/intake", wait="#intake")
        vis = pg.evaluate("() => [...document.querySelectorAll('#intake fieldset.step')].map(f => !f.hidden && f.offsetParent !== null)")
        check(f"intake: one section per screen (6 steps, only step 1 shown) @{w}", len(vis) == 6 and vis == [True] + [False] * 5, vis)
        check(f"intake: progress bar says step 1 of 6 @{w}", pg.locator("#in-bar").get_attribute("aria-valuenow") == "1" and pg.locator("#in-bar").get_attribute("aria-valuemax") == "6" and "Step 1 of 6" in pg.locator("#in-stepn").text_content())
        check(f"intake: Send is hidden until the last step; Back hidden or disabled on step 1 @{w}", not pg.locator("#in-send").is_visible() and (not pg.locator("#in-back").is_visible() or pg.locator("#in-back").is_disabled()))
        bw0 = pg.evaluate("document.querySelectorAll('#in-bar > span.done').length")
        for lab in pg.locator("#in-step-1 label[for$='-ok']").all(): lab.click()   # preview19: Next checks the step first
        pg.locator("#in-next").click(); pg.locator("#in-step-2").wait_for(state="visible", timeout=8000); pg.wait_for_timeout(300)
        bw1 = pg.evaluate("document.querySelectorAll('#in-bar > span.done').length")
        check(f"intake: Next goes to step 2 and the segmented progress bar fills one more segment @{w}", pg.locator("#in-bar").get_attribute("aria-valuenow") == "2" and not pg.locator("#in-step-1").is_visible() and bw1 == bw0 + 1, (bw0, bw1))
        check(f"intake: focus moves to the new step heading @{w}", pg.evaluate("document.activeElement && document.activeElement.id") == "in-step-2-h", pg.evaluate("document.activeElement && document.activeElement.id"))
        pg.locator("#in-back").click(); pg.locator("#in-step-1").wait_for(state="visible", timeout=8000)
        check(f"intake: Back returns to step 1 @{w}", pg.locator("#in-bar").get_attribute("aria-valuenow") == "1")
        check(f"intake: pre-filled values shown with a 'Looks right' / 'Edit' choice @{w}", pg.locator("#in-step-1 .pf").count() >= 3 and pg.locator("#in-step-1 .pf label[for$='-ok']").count() == pg.locator("#in-step-1 .pf").count() and pg.locator("#in-step-1 .pf label[for$='-change']").count() == pg.locator("#in-step-1 .pf").count())
        pf = pg.locator("#in-step-1 .pf").first; pid = pf.get_attribute("id"); key = pid[3:]
        pg.locator(f"label[for='pf-{key}-ok']").click(); pg.wait_for_timeout(200)
        check(f"intake: confirming a pre-filled value marks it confirmed (green tick) @{w}", "confirmed" in (pg.locator(f"#{pid}").get_attribute("class") or ""))
        pg.locator(f"label[for='pf-{key}-change']").click(); pg.wait_for_timeout(200)
        check(f"intake: 'Edit' opens a correction box and focus-friendly input @{w}", pg.locator(f"#pf-c-{key}").is_visible() and "confirmed" not in (pg.locator(f"#{pid}").get_attribute("class") or ""))
        pg.locator(f"label[for='pf-{key}-ok']").click()
        wiz(pg, 4)
        check(f"intake: 'What matters' and contact are tap-to-pick chips (no dropdowns) @{w}", pg.locator("#in-step-4 .choice.chipc").count() >= 4 and pg.locator("#in-step-4 select").count() == 0, pg.locator("#in-step-4 .choice.chipc").count())
        ch = pg.locator("#in-step-4 .choice.chipc").first; ch.click(); pg.wait_for_timeout(250)
        st = ch.evaluate("e => ({bg:getComputedStyle(e).backgroundColor, checked:e.querySelector('input').checked, h:e.getBoundingClientRect().height})")
        check(f"intake: a picked chip turns navy and is at least 44px tall @{w}", st["checked"] and st["bg"] in ("rgb(14, 19, 42)",) and st["h"] >= 44, st)
        check(f"intake: no <select> anywhere in the intake @{w}", pg.locator("#intake select").count() == 0)
        wiz(pg, 6)
        check(f"intake: the last step shows a review with Edit buttons and Send @{w}", pg.locator("#in-review button[id^='in-edit-']").count() >= 4 and pg.locator("#in-send").is_visible())
        pg.locator("#in-review button[id^='in-edit-']").first.click(); pg.wait_for_timeout(200)
        check(f"intake: a review 'Edit' button jumps back to that step @{w}", pg.locator("#in-bar").get_attribute("aria-valuenow") != "6")
        layout_checks(pg, "intake wizard", w)
        c.close()
    # completion check animation after a real submission
    c = mk(390); load(c, "clean", "intake"); pg = portal(c, "#/intake", wait="#intake")
    for n in (1, 2, 3):
        wiz(pg, n)
        for lab in pg.locator(f"#in-step-{n} label[for$='-ok']").all(): lab.click()
    wiz(pg, 4); pg.locator("label[for='mt-0']").click(); pg.locator("#in-step-4 label.choice[for^='cp-']").first.click()
    wiz(pg, 5); pg.locator("label[for='rf-none']").click(); wiz(pg, 6); pg.locator("label[for='in-confirm']").click(); pg.locator("#in-send").click()
    pg.locator(".donecheck").first.wait_for(timeout=10000)
    check("intake: sending shows a small completion check", pg.locator(".donecheck svg").count() >= 1)
    c.close()

    # ---------- large text toggle persists (localStorage: only 'ps.largeText')
    c = mk(390); load(c, "missing"); pg = portal(c, wait="#hero")
    check("large text starts off with nothing stored", not pg.evaluate("document.documentElement.classList.contains('big')") and pg.evaluate("localStorage.length") == 0)
    # preview19: the text-size control lives in the labelled Account menu (radio buttons "Standard" / "Larger")
    pg.locator("#account-btn").click(); pg.locator("label[for=acct-ts-large]").click(); pg.wait_for_timeout(200)
    check("large text toggle enlarges text and stores only 'ps.largeText'", pg.evaluate("document.documentElement.classList.contains('big')") and pg.evaluate("JSON.stringify(Object.keys(localStorage))") == '["ps.largeText"]' and pg.locator("#acct-ts-large").is_checked())
    pg.keyboard.press("Escape"); pg.reload(); pg.locator("#hero").wait_for(timeout=8000)
    check("large text persists after reload", pg.evaluate("document.documentElement.classList.contains('big')") and pg.locator("#acct-ts-large").is_checked())
    layout_checks(pg, "patient home, large text", 390)
    o = c.new_page(); watch(o, "office"); api(c, "POST", "/api/login", {"persona": "pat", "app": "office"}); o.goto(BASE + "/office.html#/queue"); o.locator("#qlist .qrow").first.wait_for(timeout=8000)
    check("large text preference also applies in the office workspace (same browser)", o.evaluate("document.documentElement.classList.contains('big')") and o.locator("#textsize").get_attribute("aria-pressed") == "true")
    pg.locator("#account-btn").click(); pg.locator("label[for=acct-ts-standard]").click(); pg.wait_for_timeout(200)
    check("turning large text off removes the stored key (nothing left in storage)", not pg.evaluate("document.documentElement.classList.contains('big')") and pg.evaluate("localStorage.length + sessionStorage.length") == 0)
    c.close()

    # ---------- reduced motion
    cm = mk(390); load(cm, "missing"); pm = portal(cm, wait="#hero")
    an = pm.evaluate("getComputedStyle(document.querySelector('#hero')).animationName")
    cr = mk(390, reduced_motion="reduce"); load(cr, "missing"); pr = portal(cr, wait="#hero")
    ar = pr.evaluate("() => { const o=[]; for (const el of document.querySelectorAll('body *')) { const s=getComputedStyle(el); const d=parseFloat(s.animationDuration)||0, t=parseFloat(s.transitionDuration)||0; if ((s.animationName!=='none' && d>0.011) || t>0.011) o.push(el.tagName+'#'+el.id); } return o; }")
    check("normal motion: cards rise in with a subtle animation", an != "none", an)
    check("prefers-reduced-motion: no animations or transitions anywhere on Home", ar == [], ar[:5])
    cm.close(); cr.close()

    # ---------- office board
    for w in (390, 1440):
        c = mk(w)
        for k in ("clean", "missing", "auth", "nointake", "caregiver", "notfit", "redflag", "surgery"): load(c, k)
        api(c, "POST", "/api/login", {"persona": "pat", "app": "office"})
        o = c.new_page(); watch(o, "office"); o.goto(BASE + "/office.html#/queue"); o.locator("#qlist .qrow").first.wait_for(timeout=8000); o.wait_for_timeout(300)
        # preview19 Prompt C: the board is now urgent-pinned + four groups (Needs action now / Waiting on someone else / Overdue or blocked / Completed),
        # computed on the server; colour = urgent (pinned) or overdue/blocked only.
        cols = o.evaluate("() => [...document.querySelectorAll('#board > .col')].map(c => ({k:c.id, n:c.querySelectorAll('.qrow').length, count:c.querySelector('.count').textContent, x:Math.round(c.getBoundingClientRect().left), y:Math.round(c.getBoundingClientRect().top)}))")
        check(f"office board groups are Needs action now, Waiting, Overdue or blocked, Completed in that order @{w}", [x["k"] for x in cols][:4] == ["grp-now", "grp-waiting", "grp-blocked", "grp-done"], cols)
        check(f"urgent items are pinned above the groups @{w}", o.locator("#pinned").count() == 1 and o.evaluate("() => document.querySelector('#qlist').firstElementChild.id") == "pinned")
        check(f"office board column counts match their cards @{w}", all(str(x["n"]) == x["count"] for x in cols), cols)
        if w >= 1000: check(f"desktop: the four columns sit side by side @{w}", len({x["y"] for x in cols[:4]}) == 1 and len({x["x"] for x in cols[:4]}) == 4, cols)
        else: check(f"phone: the columns stack as lists @{w}", len({x["x"] for x in cols[:4]}) == 1 and [x["y"] for x in cols[:4]] == sorted(x["y"] for x in cols[:4]), cols)
        s, q = api(c, "GET", "/api/o/queue?filter=open"); tasks = {t["id"]: t for t in q["tasks"] + q["pinned"] + q.get("recent_done", [])}
        rows = o.evaluate("() => [...document.querySelectorAll('#qlist .qrow')].map(r => ({id:+r.querySelector('a.qitem').getAttribute('href').split('/').pop(), col:r.closest('.col') ? r.closest('.col').id : (r.closest('#pinned') ? 'pinned' : '?'), act:[...r.classList].filter(c=>c.startsWith('act-')), statusChip:(r.querySelector('.badge-row .chip')||{className:'none'}).className}))")
        bad = [r for r in rows if bool(r["act"]) != (tasks[r["id"]]["group"] in ("urgent", "blocked"))]
        check(f"colour only where action is needed: coloured edge exactly on urgent (pinned) and overdue/blocked cards @{w}", not bad and any(r["act"] for r in rows), bad[:3])
        check(f"status chips (inside 'More') stay neutral grey @{w}", all(r["statusChip"] == "chip" for r in rows if r["col"] != "pinned"), [r["statusChip"] for r in rows][:5])
        misplaced = [r for r in rows if r["col"] != ("pinned" if tasks[r["id"]]["group"] == "urgent" else "grp-" + tasks[r["id"]]["group"])]
        check(f"cards land in their server-computed group (urgent pinned; overdue/blocked; waiting; now; done) @{w}", not misplaced and any(r["col"] == "grp-blocked" for r in rows), misplaced[:3])
        check(f"one-click 'Do next' card at the top of the board @{w}", o.locator("#nextup .nextup").count() == 1 and o.locator("#nextup .nextup .qact .btn").count() >= 1 and "Do next" in o.locator("#nextup").text_content())
        layout_checks(o, "office board", w)
        nu = o.locator("#nextup .nextup .qact a.btn, #nextup .nextup .qact button.btn").first
        tag = nu.evaluate("e => e.tagName")
        if tag == "A":
            nu.click(); o.locator("#detail #d-head h1").wait_for(timeout=8000)
            vis = o.evaluate("() => ({list:getComputedStyle(document.querySelector('.listcol')).display, detail:getComputedStyle(document.querySelector('#detail')).display, anim:getComputedStyle(document.querySelector('#detail')).animationName})")
            check(f"'Do next' opens the item; the detail slides in ({'next to the list' if w >= 1000 else 'as its own screen'}) @{w}", vis["detail"] != "none" and (vis["list"] != "none" if w >= 1000 else vis["list"] == "none") and vis["anim"] != "none", vis)
            layout_checks(o, "office item detail", w)
        else:
            check(f"'Do next' is a one-click button @{w}", True)
        c.close()

    # ---------- WCAG AA text contrast (computed colours, including alpha blends; 4.5:1 normal text, 3:1 large text)
    CJS = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "contrast_scan.js")).read()
    c = mk(390, reduced_motion="reduce"); load(c, "missing"); pg = portal(c, wait="#hero")
    pg.evaluate("() => { const d=document.createElement('p'); d.id='cx-self'; d.textContent='low contrast self-test'; document.querySelector('main').appendChild(d); d.classList.add('cx'); d.style.color='#BBBBBB'; }")
    selftest = pg.evaluate(CJS); pg.evaluate("document.getElementById('cx-self').remove()")
    check("contrast scanner self-test flags a deliberately low-contrast line", any("low contrast self-test" in x for x in selftest), selftest[:3])
    screens = [("portal home", "/portal.html#/home", "#hero"), ("portal visits", "/portal.html#/visits", "#h-ins"), ("portal records", "/portal.html#/records", "#checklist"), ("portal messages", "/portal.html#/messages", "main h1"), ("portal settings", "/portal.html#/settings", "main h1")]
    for w in (390, 1440):
        c = mk(w, reduced_motion="reduce"); load(c, "missing")
        for name, hsh, sel in screens:
            pg = c.new_page(); watch(pg, "portal"); pg.goto(BASE + hsh); pg.locator(sel).first.wait_for(timeout=8000); pg.wait_for_timeout(300)
            r = pg.evaluate(CJS); check(f"text contrast meets WCAG AA: {name} @{w}", not r, r[:4]); pg.close()
        load(c, "clean", "intake"); pg = c.new_page(); watch(pg, "portal"); pg.goto(BASE + "/portal.html#/intake"); pg.locator("#intake").wait_for(timeout=8000)
        bad = []
        for n in range(1, 7): wiz(pg, n); bad += pg.evaluate(CJS)
        check(f"text contrast meets WCAG AA: all 6 intake steps @{w}", not bad, bad[:4]); pg.close()
        load(c, "surgery", "postop"); pg = portal(c, wait="#ck-form"); r = pg.evaluate(CJS); check(f"text contrast meets WCAG AA: post-op check-in @{w}", not r, r[:4]); pg.close()
        for k in ("missing", "auth", "nointake", "notfit", "redflag"): load(c, k)
        api(c, "POST", "/api/login", {"persona": "pat", "app": "office"}); o = c.new_page(); watch(o, "office"); o.goto(BASE + "/office.html#/queue"); o.locator("#qlist .qrow").first.wait_for(timeout=8000); o.wait_for_timeout(300)
        r = o.evaluate(CJS); check(f"text contrast meets WCAG AA: office board @{w}", not r, r[:4])
        j = load(c, "clean", "key", office_as="yakel"); o.goto(BASE + f"/office.html#/task/{j['open_task']}"); o.locator("#d-sum").wait_for(timeout=8000); o.wait_for_timeout(300)
        r = o.evaluate(CJS); check(f"text contrast meets WCAG AA: office item + visit summary @{w}", not r, r[:4])
        pr = c.new_page(); watch(pr, "presenter"); pr.goto(BASE + "/presenter.html"); pr.locator("#pm-toggle").wait_for(timeout=8000)
        if pr.locator("#pm-toggle").get_attribute("aria-pressed") != "true": pr.locator("#pm-toggle").click()
        pr.locator("#scen-list article").first.wait_for(timeout=8000); pr.wait_for_timeout(300)
        r = pr.evaluate(CJS); check(f"text contrast meets WCAG AA: presenter @{w}", not r, r[:4])
        c.close()

    # ---------- DEMO banner, focus ring, icons, no external requests
    for page, w in (("portal.html", 360), ("office.html", 360), ("presenter.html", 360), ("portal.html", 1440)):
        c = mk(w); pg = c.new_page(); watch(pg, page); pg.goto(BASE + "/" + page); pg.locator("#demobar").wait_for(timeout=8000)
        d = pg.evaluate("() => { const b=document.querySelector('#demobar'), r=b.getBoundingClientRect(), s=getComputedStyle(b); return {pos:s.position, top:r.top, vis:r.height>0 && s.visibility!=='hidden', btn:b.querySelectorAll('button').length, txt:b.textContent, bg:s.backgroundColor}; }")
        check(f"DEMO banner restyled but still at the top, in flow, visible and not dismissible: {page} @{w}", d["pos"] == "static" and d["top"] <= 1 and d["vis"] and d["btn"] == 0 and "example data only" in d["txt"], d)
        c.close()
    c = mk(1440); load(c, "missing"); pg = portal(c, wait="#hero")
    pg.keyboard.press("Tab"); pg.keyboard.press("Tab")
    f = pg.evaluate("() => { const e=document.activeElement, s=getComputedStyle(e); return {tag:e.tagName, style:s.outlineStyle, w:parseFloat(s.outlineWidth)}; }")
    check("visible keyboard focus ring (3px solid)", f["style"] == "solid" and f["w"] >= 3, f)
    check("header buttons use inline SVG icons and visible text labels (Call us, Account)", pg.locator("header .hbtn").count() == 2 and pg.locator("header .hbtn svg").count() == 2 and pg.locator("header img:not(.logo)").count() == 0 and "Call us" in pg.locator("#callus").inner_text() and "Account" in pg.locator("#account-btn").inner_text())
    fonts = pg.evaluate("() => [...document.fonts].length")
    check("no web fonts are loaded (system font stack only)", fonts == 0, fonts)
    c.close()
    br.close()
finally:
    srv.stop()
ERRS = [e for e in ERRS if "status of 401" not in e[1]]
check("no JavaScript errors in any page", not ERRS, ERRS[:6])
ext = [u for u in L.REQS if not u.startswith(BASE)]
check("no requests to any other host (no tracking / external services / web fonts)", not ext, ext[:5])
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_design: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
json.dump(L.RESULTS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_design.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
