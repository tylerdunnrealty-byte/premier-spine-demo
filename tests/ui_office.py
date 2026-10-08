#!/usr/bin/env python3
"""preview19 Prompt C UI tests: the office board (urgent pinned, Do next urgent-first, one-card layout with a 'More' disclosure,
admin/front-desk read-only view of urgent items, failed action stays visible with a retry that re-uses the same idempotency key,
visit-ready summary draft), plus the patient side of the same records (reminder opt-out, merged Ask card, no staff names on Home).
Real local server (127.0.0.1:8788, temp DB, no worker), local Chrome via Playwright, fictional data only.
Screenshots: ../preview19-shots/office-*.png at 1440 and 390."""
import json, os, re, sys, tempfile
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ui_lib as L
L.PORT = int(os.environ.get("PS_UI_PORT", "8788")); L.BASE = BASE = f"http://127.0.0.1:{L.PORT}"
check, layout_checks, api = L.check, L.layout_checks, L.api
SHOTS = L.SHOTS_DIR; os.makedirs(SHOTS, exist_ok=True)
ERRS = []
EMERG = "Example (fictional): I suddenly can't control my bladder and my legs are numb"
def watch(pg, tag):
    L.track(pg); pg.on("pageerror", lambda e: ERRS.append((tag, str(e)))); pg.on("console", lambda m: ERRS.append((tag, m.text)) if m.type == "error" else None)
def shot(pg, name, el=None, full=False):
    p = os.path.join(SHOTS, name + ".png")
    (el.screenshot(path=p) if el is not None else pg.screenshot(path=p, full_page=full)); return p
def ctx_for(br, w, who=None, app="office"):
    c = br.new_context(viewport={"width": w, "height": 844 if w < 800 else 900})
    api(c, "POST", "/api/presenter/enter", {})
    if who: s, j = api(c, "POST", "/api/login", {"persona": who, "app": app}); assert s == 200, (who, s, j)
    return c
def board(c, tag):
    pg = c.new_page(); watch(pg, tag); pg.goto(BASE + "/office.html#/queue"); pg.locator("#qlist .tcard").first.wait_for(timeout=10000); pg.wait_for_timeout(300); return pg
def portal(c, h="#/home", wait="main h1", tag="portal"):
    pg = c.new_page(); watch(pg, tag); pg.goto(BASE + "/portal.html" + h); pg.locator(wait).first.wait_for(timeout=10000); pg.wait_for_timeout(300); return pg
def load(c, key, step="key"):
    s, j = api(c, "POST", "/api/presenter/scenario/load", {"key": key, "step": step}); assert s == 200, (key, s, j)
def tid(c, pname, typ=None, pinned=False):
    s, q = api(c, "GET", "/api/o/queue?filter=all"); src = q["pinned"] if pinned else q["tasks"]
    return next(t["id"] for t in src if t["patient_name"].startswith(pname) and (typ is None or t["type"] == typ) and t["status"] != "Resolved")

srv = L.Srv(os.path.join(tempfile.mkdtemp(), "ui_office.db")); srv.start(reset=True)
try:
  with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    setup = ctx_for(br, 1440)
    for k in ("clean", "missing", "nointake", "redflag"): load(setup, k)
    load(setup, "nointake", "intake")
    api(setup, "POST", "/api/login", {"persona": "avery", "app": "portal"}); s, j = api(setup, "POST", "/api/p/messages", {"category": "medical", "body": EMERG}, key="ui-office-emerg-1")
    check("setup: Avery's emergency-wording message accepted (fictional)", s == 200 and j["triage"]["level"] == "emergency", (s, j and j.get("triage")))
    api(setup, "POST", "/api/login", {"persona": "nina", "app": "office"})
    AV_U = tid(setup, "Avery", pinned=True); GR_U = tid(setup, "Gray", "red_flag", pinned=True); AV_B = tid(setup, "Avery", "schedule_visit"); BL_R = tid(setup, "Blake", "records_request")

    for w in (1440, 390):
        # ---------------- nurse: urgent pinned, Do next urgent-first
        c = ctx_for(br, w, "nina"); pg = board(c, f"nina@{w}")
        pin = pg.locator("#pinned")
        check(f"[{w}] nurse board: urgent section pinned at the top of the list", pin.is_visible() and pg.evaluate("() => document.querySelector('#qlist').firstElementChild.id") == "pinned")
        check(f"[{w}] both urgent items are pinned (Avery message, Gray red flag)", pg.locator(f"#pin-card-{AV_U}").is_visible() and pg.locator(f"#pin-card-{GR_U}").is_visible())
        check(f"[{w}] nurse's Do next is an urgent item, styled urgent", "urgent" in (pg.locator("#nextup-card").get_attribute("class") or "") and ("Gray" in pg.locator("#nextup-card").inner_text() or "Avery" in pg.locator("#nextup-card").inner_text()), pg.locator("#nextup-card").inner_text()[:200])
        check(f"[{w}] nurse gets a real action on the pinned urgent card", pg.locator(f"#pin-card-{GR_U} .qact a, #pin-card-{GR_U} .qact button").count() >= 1)
        check(f"[{w}] all four groups are on the board (needs action now / waiting / overdue or blocked / completed)", all(pg.locator(f"#grp-{g}").count() == 1 for g in ("now", "waiting", "blocked", "done")))
        check(f"[{w}] Avery's booking card is in 'Overdue or blocked' with the hold explained, no Book button", pg.locator(f"#grp-blocked #q-card-{AV_B}").count() == 1 and pg.locator(f"#q-held-{AV_B}").is_visible() and pg.locator(f"#q-card-{AV_B} .qact").count() == 0)
        layout_checks(pg, "office board (nurse)", w, strict_small=False)
        pg.evaluate("window.scrollTo(0,0)"); shot(pg, f"office-board-urgent-pinned-{w}", full=(w == 390))
        for f in ("mine", "waiting", "resolved", "referrals", "overdue", "decisions", "all", "urgent", "open"):
            pg.locator(f"#filters button[data-f={f}]").click(); pg.wait_for_timeout(350)
            check(f"[{w}] nurse filter '{f}': both urgent items still pinned and visible", pg.locator(f"#pin-card-{AV_U}").is_visible() and pg.locator(f"#pin-card-{GR_U}").is_visible())
        # ---------------- card collapsed / expanded
        card = pg.locator(f"#q-card-{BL_R}"); card.scroll_into_view_if_needed()
        face = card.inner_text()
        check(f"[{w}] card face: patient, what needs attention, owner, due/waiting, one action", "Blake" in face and pg.locator(f"#q-card-{BL_R} .attn").inner_text().strip() and re.search(r"(Pat|Nina|Unassigned)", pg.locator(f"#q-card-{BL_R} .meta").inner_text()) and re.search(r"(Due|Waiting|waiting|overdue|Overdue)", pg.locator(f"#q-card-{BL_R} .meta").inner_text()) and pg.locator(f"#q-card-{BL_R} .qact").count() == 1, face[:200])
        check(f"[{w}] card face has no badges or explanations until 'More' is opened", not pg.locator(f"#q-more-{BL_R} .badge-row").is_visible())
        shot(pg, f"office-card-collapsed-{w}", card)
        pg.locator(f"#q-more-{BL_R} > summary").click(); pg.wait_for_timeout(200)
        check(f"[{w}] 'More' opens the details (badges, why, next step)", pg.locator(f"#q-more-{BL_R} .badge-row").is_visible() and "Next step" in pg.locator(f"#q-more-{BL_R}").inner_text())
        shot(pg, f"office-card-expanded-{w}", card)
        pg.locator("#refresh").click(); pg.wait_for_timeout(600)
        check(f"[{w}] an open 'More' stays open across a refresh", pg.locator(f"#q-more-{BL_R}").evaluate("d => d.open"))
        c.close()

        # ---------------- front desk / admin: urgent visible, owner shown, no clinical action
        for who in ("pat", "admin"):
            c = ctx_for(br, w, who); pg = board(c, f"{who}@{w}")
            nu = pg.locator("#nextup-card").inner_text()
            check(f"[{w}/{who}] Do next opens with the urgent notice (exists + owner), not the booking", "Urgent first" in nu and "Nina" in nu and "Book the visit" not in nu, nu[:300])
            check(f"[{w}/{who}] pinned urgent cards say who handles it and offer no action", pg.locator(f"#pin-ro-{GR_U}").is_visible() and pg.locator(f"#pin-card-{GR_U} .qact").count() == 0 and pg.locator(f"#pin-card-{GR_U} button").count() == 0)
            for f in ("mine", "waiting", "resolved", "referrals"):
                pg.locator(f"#filters button[data-f={f}]").click(); pg.wait_for_timeout(350)
                check(f"[{w}/{who}] filter '{f}' can't hide the urgent items", pg.locator(f"#pin-card-{AV_U}").is_visible() and pg.locator(f"#pin-card-{GR_U}").is_visible())
            pg.locator("#filters button[data-f=open]").click(); pg.wait_for_timeout(300)
            if who == "admin":
                pg.goto(BASE + f"/office.html#/task/{GR_U}"); pg.locator("#d-urgent-ro, #act-ro").first.wait_for(timeout=8000); pg.wait_for_timeout(400)
                det = pg.locator("#detail") if pg.locator("#detail").count() else pg.locator("main")
                check(f"[{w}/admin] urgent detail: read-only notice, owner named, no action buttons", pg.locator("#d-urgent-ro").is_visible() and "Nina" in pg.locator("#d-urgent-ro").inner_text() and pg.locator("#acts button, #d-next button").count() == 0, pg.locator("#d-urgent-ro").inner_text()[:200])
                pg.locator("#d-urgent-ro").scroll_into_view_if_needed(); shot(pg, f"office-admin-urgent-{w}", full=False)
            c.close()

        # ---------------- visit-ready summary draft
        c = ctx_for(br, w, "yakel"); pg = c.new_page(); watch(pg, f"yakel@{w}")
        pg.goto(BASE + f"/office.html#/task/{BL_R}"); pg.locator("#sum-label").wait_for(timeout=10000); pg.wait_for_timeout(300)
        check(f"[{w}] summary label is exactly 'Draft — clinician review required'", pg.locator("#sum-label").inner_text().strip() == "Draft \u2014 clinician review required", pg.locator("#sum-label").inner_text())
        check(f"[{w}] patient statements (verbatim) are shown apart from extracted facts", pg.locator("#sum-statements blockquote.verbatim").count() >= 1 and pg.locator("#sum-extracted").count() == 1)
        check(f"[{w}] facts link to their source", pg.locator("#sum-extracted .srclink").count() >= 3)
        check(f"[{w}] missing/conflicting info is highlighted", pg.locator("#sum-flags li.flag").count() >= 1, pg.locator("#sum-flags").inner_text()[:200] if pg.locator("#sum-flags").count() else "")
        sec = pg.locator("#sum-label").locator("xpath=ancestor::section[1]"); sec.scroll_into_view_if_needed(); shot(pg, f"office-summary-draft-{w}", sec)
        b = pg.locator("#sum-extracted button.srclink").first
        if b.count():
            b.click(); pg.wait_for_timeout(500)
            check(f"[{w}] a source link takes you to that document in the task's document list", (pg.evaluate("() => document.activeElement && document.activeElement.id") or "").startswith("doc-"), pg.evaluate("() => document.activeElement && document.activeElement.id"))
        c.close()

    # ---------------- failed action: stays visible, retry re-uses the key, done once, right patient only
    for w in (1440, 390):
        c = ctx_for(br, w, "pat"); pg = board(c, f"pat-fail@{w}")
        btn = pg.locator("#qlist [id^=q-act-]").first; bid = int(btn.get_attribute("id").split("-")[-1]); label = btn.inner_text()
        s, d = api(c, "GET", f"/api/o/tasks/{bid}"); pname = d["patient"]["name"]; ev0 = len(d["history"])
        keys = []; mode = {"fail": True}
        def handler(route, req):
            keys.append(req.headers.get("idempotency-key"))
            if mode["fail"]: route.abort("failed")
            else: route.continue_()
        pg.route("**/api/o/tasks/*/act", handler)
        btn.click(); pg.locator(f"#fail-{bid}").wait_for(timeout=8000)
        ft = pg.locator(f"#fail-{bid}").inner_text()
        check(f"[{w}] failed action stays on the card with a 'Try again' button", pg.locator(f"#retry-{bid}").is_visible() and "Not confirmed" in ft, ft)
        check(f"[{w}] failure text doesn't claim success or claim nothing happened when it can't know", "Done" not in ft and "won\u2019t be done twice" in ft, ft)
        pg.locator(f"#fail-{bid}").scroll_into_view_if_needed(); shot(pg, f"office-failed-action-{w}", pg.locator(f"#q-card-{bid}"))
        pg.evaluate("() => document.querySelector('#refresh').click()"); pg.wait_for_timeout(700)
        check(f"[{w}] the failure is still shown after the list refreshes", pg.locator(f"#fail-{bid}").is_visible())
        mode["fail"] = False; pg.locator(f"#retry-{bid}").click(); pg.wait_for_timeout(1200)
        check(f"[{w}] retry succeeds and the failure box goes away", pg.locator(f"#fail-{bid}").count() == 0 and "Done" in pg.locator("#q-st").inner_text(), pg.locator("#q-st").inner_text())
        check(f"[{w}] the retry re-used the same idempotency key", len(keys) == 2 and keys[0] and keys[0] == keys[1], keys)
        s, d2 = api(c, "GET", f"/api/o/tasks/{bid}")
        sent0 = sum(1 for e in d["history"] if e["action"] == "reminder.sent"); sent1 = sum(1 for e in d2["history"] if e["action"] == "reminder.sent")
        check(f"[{w}] the action ran once for {pname} ({label!r}): history grew" + (", exactly one reminder sent" if "reminder" in label.lower() else ""), len(d2["history"]) > ev0 and ("reminder" not in label.lower() or sent1 == sent0 + 1), (ev0, len(d2["history"]), sent0, sent1))
        pg.unroute("**/api/o/tasks/*/act"); c.close()

    # ---------------- staff action -> the right patient's portal only
    c = ctx_for(br, 1440, "blake", "portal"); before_b = portal(c).locator("main").inner_text()
    c2 = ctx_for(br, 1440, "cameron", "portal"); before_c = portal(c2).locator("main").inner_text()
    so = ctx_for(br, 1440, "pat"); s, d = api(so, "GET", f"/api/o/tasks/{BL_R}")
    opts = next(a for a in d["actions"] if a["key"] == "mark_received")["fields"][0]["options"]
    s, j = api(so, "POST", f"/api/o/tasks/{BL_R}/act", {"action": "mark_received", "items": [opts[0]["value"]]}, key="ui-office-mark-1")
    check("staff marks a Blake record received", s == 200, (s, j))
    after_b = portal(c).locator("main").inner_text(); after_c = portal(c2).locator("main").inner_text()
    norm = lambda t: re.sub(r"\d{1,2}:\d{2} [AP]M PT", "T", t)
    check("Blake's portal shows the change", norm(after_b) != norm(before_b))
    check("Cameron's portal is unchanged", norm(after_c) == norm(before_c))
    hm = portal(c).locator(".lastcheck").all_inner_texts()
    check("patient Home 'last verified' lines show the time only (no staff name, no fax note)", hm and not any(re.search(r"Pat|Nina|Front desk|fax", x) for x in hm), hm)
    c.close(); c2.close(); so.close()

    # ---------------- patient: merged Ask card; reminder opt-out seen by staff
    for w in (390, 1440):
        c = ctx_for(br, w, "drew", "portal"); pg = portal(c, "#/messages")
        check(f"[{w}] Messages: one 'Ask about your visit' entry, the old quick-question box is gone", pg.locator("#msg-assist").is_visible() and pg.locator("#ask-q").count() == 0 and pg.locator("#msg-assist").get_attribute("href") == "#/assist")
        if w == 390: shot(pg, f"office-portal-messages-ask-merged-{w}", pg.locator("#ask-card"))
        pg = portal(c, "#/settings", "#set-rem h2")
        pg.locator("#rem-toggle").wait_for(timeout=8000)
        was_on = "Turn reminder texts off" in pg.locator("#rem-toggle").inner_text()
        if was_on: pg.locator("#rem-toggle").click(); pg.locator("#rem-st.ok, #rem-st").first.wait_for(timeout=8000); pg.wait_for_timeout(400)
        check(f"[{w}] patient turns reminder texts off and sees it saved", "Off." in pg.locator("#rem-state").inner_text() and "Saved" in pg.locator("#rem-st").inner_text(), pg.locator("#set-rem").inner_text()[:300])
        if w == 390: shot(pg, f"office-portal-reminders-off-{w}", pg.locator("#set-rem"))
        so = ctx_for(br, w, "pat"); s, q = api(so, "GET", "/api/o/queue?filter=all"); dt = next(t for t in q["tasks"] if t["patient_name"].startswith("Drew") and t["type"] == "intake_followup" and t["status"] != "Resolved")
        check(f"[{w}] staff see the same opt-out on Drew's task (one record)", dt["reminders_opted_out"] is True and any(r["stop_reason"] == "opted_out" for r in dt["reminders"]), dt.get("reminders"))
        pg.locator("#rem-toggle").click(); pg.wait_for_timeout(600)
        check(f"[{w}] patient turns them back on", "On." in pg.locator("#rem-state").inner_text())
        so.close(); c.close()
    s, j = api(ctx_for(br, 390, "frankie", "portal"), "GET", "/api/p/reminders"); check("helper sees reminder status read-only", s == 200 and j["can_change"] is False)
    br.close()
finally:
    srv.stop()
ERRS = [e for e in ERRS if "status of 401" not in e[1] and "net::ERR_FAILED" not in e[1]]   # the deliberate aborted request logs net::ERR_FAILED
check("no JavaScript errors in any page", not ERRS, ERRS[:6])
ext = [u for u in L.REQS if not u.startswith(BASE)]
check("no requests to any other host", not ext, ext[:5])
print("SKIP axe-core: NOT RUN (not installed on this box; adding it would be a new dependency)")
ok = sum(1 for r in L.RESULTS if r[1]); print(f"\nDONE ui_office: {ok}/{len(L.RESULTS)} passed; failed: {[r[0] for r in L.RESULTS if not r[1]]}")
json.dump(L.RESULTS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_office.results.json"), "w"), indent=1)
sys.exit(0 if ok == len(L.RESULTS) else 1)
