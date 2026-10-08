#!/usr/bin/env python3
"""Tests for the single-file static snapshot, opened from file:// (no server at all)."""
import json, os, re, sys
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_lib import check, RESULTS, AXE
HAVE_AXE = os.path.exists(AXE); SKIPPED = []
SNAP = "file://" + os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "snapshot.html")
LONG = "Snapshot long message \u00e9 \U0001F600\nline two " + "word " * 100 + "\nSNAP-END"
reqs = []
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    pg = br.new_page(viewport={"width": 1440, "height": 900}); pg.on("request", lambda r: reqs.append(r.url) if not r.url.startswith(("file:", "data:", "about:", "blob:")) else None)
    errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(SNAP); P = pg.frame_locator("#f-portal"); O = pg.frame_locator("#f-office")
    check("snapshot: outer banner says 'static snapshot \u2014 server rules simulated in browser'", "Static snapshot \u2014 server rules simulated in browser" in pg.locator(".protobar").first.text_content())
    check("snapshot: each embedded app banner says static snapshot / fictional / not production", "Static snapshot" in P.locator("#banner").text_content() and "fictional data" in P.locator("#banner").text_content())
    DT = "Demo \u2014 example data only, not a real patient portal"
    check("snapshot DEMO: outer page title starts with DEMO", pg.title().startswith("DEMO"), pg.title())
    check("snapshot DEMO: outer page shows the DEMO banner (static, not dismissible)", DT in pg.locator("#demobar").inner_text() and pg.locator("#demobar").evaluate("e => getComputedStyle(e).position") == "static" and pg.locator("#demobar button, #demobar a").count() == 0)
    P.locator("#demobar").wait_for(timeout=8000); O.locator("#demobar").wait_for(state="attached", timeout=8000)
    check("snapshot DEMO: embedded portal and office each show the DEMO banner", DT in P.locator("#demobar").inner_text() and DT in O.locator("#demobar").text_content())
    m = br.new_page(viewport={"width": 360, "height": 740}); m.goto(SNAP); m.locator("#demobar").wait_for()
    b = m.locator("#demobar").bounding_box(); sw = m.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    check("snapshot DEMO: banner visible at 360 px, full width, no horizontal scroll", b and b["y"] < 60 and b["width"] >= 359 and sw[0] <= sw[1] + 1, (b, sw)); m.close()
    check("snapshot: limits panel states it cannot prove server-side authorization", "cannot prove" in pg.locator(".limits").text_content() and "authorization" in pg.locator(".limits").text_content())
    P.locator("button.qitem:has-text('Alex Example')").click(); P.locator("h1:has-text('Hello')").wait_for(timeout=8000)
    t = P.locator("main").text_content(); check("snapshot: Alex home (preview19) answers what's happening / do I need to do anything (one intake button) / checklist / help with call-back; photos on Visits", "What\u2019s happening" in t and "Do you need to do anything?" in t and P.locator("#hero #na-intake").count() == 1 and "Your checklist" in t and "Need help?" in t and "Last verified update" in t and P.locator("#cb-btn").is_visible() and (P.locator("button[data-view=visits]").click() or P.locator(".person img").nth(1).wait_for(timeout=8000) or P.locator(".person img").count() == 2))
    check("snapshot: clinician photos load (embedded data URIs)", P.locator(".person img").first.evaluate("e => e.naturalWidth") > 0)
    P.locator("button[data-view=home]").click(); P.locator("#h-na").wait_for(timeout=8000)
    P.locator("button[data-view=messages]").click(); P.locator("#msg-body").wait_for(); P.locator("label[for=cat-scheduling]").click(); P.locator("#msg-body").fill(LONG); P.locator("#msg-send").dblclick()
    P.locator("#msg-status").filter(has_text="Status:").wait_for(timeout=8000); pg.wait_for_timeout(400)
    check("snapshot: double-click Send creates one conversation", P.locator("#threads a.qitem").count() == 1)
    P.locator("#threads a.qitem").first.click(); P.locator("#conv .msg .body").first.wait_for(); check("snapshot: patient thread shows the full long message", P.locator("#conv .msg .body").first.text_content() == LONG)
    pg.locator("button[data-t=office]").click(); O.locator("button.qitem:has-text('Pat')").click(); O.locator("#qlist a.qitem").first.wait_for()
    O.locator(f"#qlist a.qitem:has-text('Alex Example')").first.click(); O.locator("#d-convo .msg .body").first.wait_for()
    check("snapshot: office case shows the full message", O.locator("#d-convo .msg .body").first.text_content() == LONG)
    O.locator("#reply-quote").click(); check("snapshot: quote includes the whole message", "SNAP-END" in O.locator("#reply-body").input_value() and O.locator("#reply-body").input_value().count("> ") >= 3)
    O.locator("#reply-body").fill("Snapshot draft \u00e9 UNSENT"); O.locator("#draft-ind").filter(has_text="Draft saved").wait_for(timeout=6000)
    pg.locator("button[data-t=presenter]").click(); pg.locator("button[data-t=office]").click(); check("snapshot: draft survives switching tabs", O.locator("#reply-body").input_value() == "Snapshot draft \u00e9 UNSENT")
    O.locator("#qlist a.qitem").nth(1).click(); O.locator("#d-head h1").wait_for(); pg.wait_for_timeout(300); O.locator("#qlist a.qitem:has-text('Alex Example')").first.click(); O.locator("#reply-body").wait_for(); check("snapshot: draft survives opening another item and returning", O.locator("#reply-body").input_value() == "Snapshot draft \u00e9 UNSENT")
    O.locator("label[for=k-ack]").click(); O.locator("#reply-send").click(); O.locator("#reply-st").filter(has_text="still open").wait_for(timeout=6000); check("snapshot: acknowledgment leaves the request open", "Resolved" not in O.locator("#d-head").text_content())
    pg.locator("button[data-t=portal]").click(); P.locator("button[data-view=messages]").click(); P.locator("#msg-body").wait_for()
    # preview19 Prompt C: the old quick-question box is merged into "Ask about your visit"; the snapshot has no server, so the assistant says so instead of answering
    check("snapshot: Messages has one 'Ask about your visit' entry (old quick-question box gone)", P.locator("#msg-assist").count() == 1 and P.locator("#ask-q").count() == 0)
    P.locator("#msg-assist").click(); P.locator("#as-q").wait_for(timeout=8000)
    P.locator("#as-q").fill("I have chest pain"); check("snapshot: emergency wording shows 911 guidance immediately", "call 911 now" in P.locator("#as-em").text_content())
    P.locator("#as-q").fill("Do you have valet parking for oversized trucks?"); P.locator("#as-btn").click(); P.locator("main").filter(has_text="local prototype server").wait_for(timeout=8000)
    check("snapshot: the assistant says it needs the local server (no fake answer, nothing sent)", "Nothing was sent" in P.locator("main").inner_text())
    P.locator("button[data-view=messages]").click(); P.locator("#msg-body").wait_for()
    pg.locator("button[data-t=presenter]").click(); pg.frame_locator("#f-presenter").locator("#pm-toggle").click(); F = pg.frame_locator("#f-presenter"); F.locator("text=Scenarios").first.wait_for()
    F.locator("button:has-text('Make Jordan')").first.click(); pg.wait_for_timeout(300)
    pg.locator("button[data-t=office]").click(); O.locator("a.qitem:has-text('Jordan Sample')").first.click(); O.locator("#reply-send").wait_for(); O.locator("#reply-send").click(); O.locator("#reply-st").filter(has_text="Reply sent").wait_for(timeout=6000)
    pg.locator("button[data-t=presenter]").click()
    for _ in range(5): F.locator("button:has-text('Run simulated delivery step')").click(); pg.wait_for_timeout(250)
    pg.locator("button[data-t=office]").click(); O.locator("#refresh").click(); O.locator("#qlist a.qitem:has-text('Notification failed')").first.wait_for(timeout=6000); check("snapshot: failed notification creates a visible exception task", True)
    st = pg.evaluate("[localStorage.length, sessionStorage.length]"); fst = [f.evaluate("[localStorage.length, sessionStorage.length]") for f in pg.frames]
    check("snapshot: no localStorage/sessionStorage in page or frames", st == [0, 0] and all(x == [0, 0] for x in fst), (st, fst))
    if not HAVE_AXE: SKIPPED.append("axe: snapshot outer page + embedded apps"); print("SKIP axe on the snapshot (axe-core not available - not run)")
    else: pg.evaluate(open(AXE).read()); v = pg.evaluate("async () => (await axe.run(document, {resultTypes:['violations']})).violations.map(v => v.id)"); check("snapshot: axe on the outer page", not v, v)
    for f in (pg.frames if HAVE_AXE else []):
        if f == pg.main_frame: continue
        try:
            f.evaluate(open(AXE).read()); v = f.evaluate("async () => (await axe.run(document, {resultTypes:['violations']})).violations.map(v => v.id)")
            check(f"snapshot: axe in embedded app ({(f.evaluate('document.title') or '')[:30]})", not v, v)
        except Exception as e: check("snapshot: axe in embedded frame", False, e)
    pg.reload(); pg.frame_locator("#f-portal").locator("button.qitem:has-text('Alex Example')").click(); pg.frame_locator("#f-portal").locator("button[data-view=messages]").click(); pg.frame_locator("#f-portal").locator("#threads").get_by_text("No conversations yet").or_(pg.frame_locator("#f-portal").locator("#threads .qitem, #threads a")).first.wait_for()
    check("snapshot: reload RESETS data (no persistence \u2014 documented limitation)", "No conversations yet" in pg.frame_locator("#f-portal").locator("#threads").text_content())
    # ---- Pass 2: tell-us-once intake (mock) for the Pass 1 demo patient
    P = pg.frame_locator("#f-portal"); P.locator("button[data-view=home]").click(); P.locator("#na-intake").click(); P.locator("#intake").wait_for(timeout=8000)
    check("snapshot (Pass 2): intake wizard opens on 'About you' with pre-filled facts to confirm", "Alex Example" in P.locator("#intake").text_content() and "Please check each one" in P.locator("#intake").text_content() and P.locator("#in-step-1 .pf").count() >= 1 and P.locator("#in-step-1").is_visible())
    P.locator("#in-allsteps summary").click(); P.locator("#in-stepbtn-5").click(); P.locator("#in-step-5").wait_for(state="visible", timeout=6000); P.locator("label[for='rf-new_weakness']").click(); P.locator("#rf-task").filter(has_text="urgent task").wait_for(timeout=6000)
    check("snapshot (Pass 2): ticking a red-flag box shows 911 / call-the-office guidance", P.locator("#rf-alert").is_visible() and P.locator("#rf-alert a[href='tel:911']").count() == 1)
    # ---- Pass 2: recorded key states of the eight referral scenarios (read-only replay of real server responses)
    EXP = {"clean": ("Avery", "ready for your first visit"), "missing": ("Blake", "Lakeshore Imaging"), "auth": ("Cameron", "Sample Insurance"), "nointake": ("Drew", "3 reminders"),
           "caregiver": ("Emery", "Check the answers"), "notfit": ("Finley", "reviewing"), "redflag": ("Gray", "Call 911"), "surgery": ("Harper", "Pre-op clearance")}
    check("snapshot (Pass 2): limits panel says the referral scenarios are recordings and read-only", "recordings" in pg.locator(".limits").first.text_content() and "read-only" in pg.locator(".limits").first.text_content())
    for k, (nm, txt) in EXP.items():
        pg.locator(f"#rec-{k}").click(); pg.locator("#rec-note").filter(has_text="Showing scenario").wait_for(timeout=8000); pg.wait_for_timeout(300)
        P = pg.frame_locator("#f-portal"); O = pg.frame_locator("#f-office")
        # preview19 Prompt B: the recorded pre-op Home shows the split checklist (#preop-split) instead of #pipe
        P.locator("#pipe, #preop-split").first.wait_for(timeout=8000); O.locator("#qlist .qrow, #qlist a.qitem").first.wait_for(timeout=8000)
        check(f"snapshot (Pass 2): recorded '{k}' portal shows {nm}'s referral status", f"Hello, {nm}" in P.locator("main").text_content() and txt in P.locator("main").text_content(), P.locator("#pipe-summary").text_content())
        check(f"snapshot (Pass 2): recorded '{k}' office queue lists {nm}", nm in O.locator("#qlist").text_content())
    pg.locator("#rec-clean").click(); pg.locator("#rec-note").filter(has_text="scenario 1").wait_for(timeout=8000); pg.wait_for_timeout(300); O = pg.frame_locator("#f-office")
    O.locator("#qlist a.qitem:has-text('Avery Example')").first.click(); O.locator("#do-book").wait_for(timeout=8000); O.locator("#do-book").click(); O.locator("#dosub-book").click(); O.locator("#do-st.demo").wait_for(timeout=6000)
    # preview19 publish: the refusal is a calm .demo notice (was .bad) worded "Demo recording: in the full version this saves to the server. Nothing was sent or saved here."
    check("snapshot (Pass 2): actions on a recorded state are refused as read-only (nothing pretends to save)", "Demo recording" in O.locator("#do-st").text_content() and "Nothing was sent or saved" in O.locator("#do-st").text_content(), O.locator("#do-st").text_content())
    pg.locator("#rec-off").click(); pg.frame_locator("#f-portal").locator("h1:has-text('Hello, Alex')").wait_for(timeout=8000)
    check("snapshot (Pass 2): 'Back to the interactive Pass 1 demo' returns to the in-browser demo (Alex, intake already started)", pg.frame_locator("#f-portal").locator("#pipe-summary").count() == 0 and pg.frame_locator("#f-portal").locator("#hero #na-intake").count() == 1)  # preview19: Alex now has a checklist card (#pipe) too; the recorded referral summary (#pipe-summary) must be gone
    pg.locator("#rec-surgery").click(); pg.locator("#rec-note").filter(has_text="scenario 8").wait_for(timeout=8000); pg.wait_for_timeout(300); O = pg.frame_locator("#f-office")
    O.locator("#qlist a.qitem:has-text('Harper Example')").first.click(); O.locator("#po-items").wait_for(timeout=8000)
    check("snapshot (Pass 2b): recorded surgery state shows the office surgery checklist and the DRAFT visit summary", "Pre-op clearance" in O.locator("#po-items").text_content() and O.locator("#sum-label").text_content().strip() == "Draft \u2014 clinician review required")   # preview19 Prompt C: exact label
    pg.locator("#rec-auth").click(); pg.locator("#rec-note").filter(has_text="scenario 3").wait_for(timeout=8000); pg.wait_for_timeout(300); O = pg.frame_locator("#f-office")
    O.locator("#calls-label").wait_for(timeout=8000); check("snapshot (Pass 2b): recorded office queue shows the calls-saved card labelled example counts only", "EXAMPLE COUNTS ONLY" in O.locator("#calls-label").text_content())
    pg.locator("#rec-off").click(); pg.frame_locator("#f-portal").locator("h1:has-text('Hello, Alex')").wait_for(timeout=8000)
    check("snapshot: no page errors", not errs, errs[:3])
    check("snapshot: no external network requests", not reqs, reqs[:3])
    br.close()
json.dump(RESULTS, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui_snapshot.results.json"), "w"), indent=1)
bad = [r for r in RESULTS if not r[1]]; print(f"\nDONE ui_snapshot: {len(RESULTS) - len(bad)}/{len(RESULTS)} passed; failed: {[r[0] for r in bad]}; NOT RUN: {SKIPPED}")
