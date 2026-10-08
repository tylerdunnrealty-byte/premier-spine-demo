#!/usr/bin/env python3
"""Functional Playwright tests against the REAL local server (127.0.0.1:8771, temp DB).  No external service is called."""
import json, os, re, sys, tempfile, time
from playwright.sync_api import sync_playwright
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ui_lib import *

LONG = ("Hello \u00e9\u00e8 \U0001F600 \u6f22\u5b57 first line about my appointment.\n\nSecond paragraph: where do I park, and what should I bring along?\n" + "Detail " * 70 + "\nFINAL-MARKER-LINE \U0001F680")
tmp = tempfile.mkdtemp(); srv = Srv(os.path.join(tmp, "ui.db")); srv.start(reset=True)
with sync_playwright() as p:
    br = p.chromium.launch(executable_path=os.environ.get("PS_CHROME", "/usr/bin/google-chrome"), args=["--no-sandbox"])
    mk = lambda w=1440, h=900: br.new_context(viewport={"width": w, "height": h})
    alex_c, jordan_c, riley_c, pat_c, nina_c, yakel_c, admin_c = mk(), mk(), mk(), mk(), mk(), mk(), mk()
    alex = portal_login(alex_c, "Alex Example")

    # ---------- C: patient home content
    txt = alex.locator("main").text_content()
    check("home leads with next appointment (date, time, clinician, location)", re.search(r"(Mon|Tues|Wednes|Thurs|Fri|Satur|Sun)day, \w+ \d+ \u00b7 \d+:\d\d (AM|PM) PT", txt) and "Dr. Stefan Yakel, DO" in txt and "850 W Ironwood" in txt, txt[:200])
    first_h = alex.locator("main h2, main h1").evaluate_all("els => els.map(e => e.textContent)")
    # preview19: Home answers three questions in order -- what is happening (status card), do I need to do anything (inside it), how do I get help
    check("order (preview19 Home): status card first (with 'Do you need to do anything?' and the intake as its one action), then the checklist, then 'Need help?'", first_h[2] == "Your checklist" and first_h[3] == "Need help?" and alex.locator("section[aria-labelledby=h-na] #youdo").count() == 1 and alex.locator("section[aria-labelledby=h-na] #na-intake").count() == 1, first_h[:5])
    check("exactly one primary next-action button in the next-step card", alex.locator("section[aria-labelledby=h-na] .btn").count() == 1)
    check("waiting-on shows 'Last verified update' with a timestamp and no staff name (the team is under Details)", re.search(r"Last verified update: \w+ \d+, \d+:\d\d (AM|PM) PT(?! \u00b7 Pat)", txt) and "\u00b7 Pat" not in txt, txt[txt.find("Last verified"):][:120])   # preview19 Prompt C
    check("reach-the-team: Call link, Request a call back, assisted route", alex.locator("a[href='tel:2087703536']").count() >= 2 and alex.locator("#cb-btn").is_visible() and "Can\u2019t use the portal? Call (208) 770-3536 and we\u2019ll do this with you." in re.sub(r"\s+", " ", txt))
    alex.locator("#nav button[data-view=visits]").click(); alex.locator("#h-ins").wait_for(timeout=8000); vtxt = alex.locator("main").text_content()
    check("care instructions shown with source tag (Visits tab)", "Bring these to your visit" in vtxt and "Source:" in vtxt.title().replace("SOURCE", "Source"))
    alex.wait_for_function("() => Array.from(document.querySelectorAll('.person img')).every(i => i.complete)"); imgs = alex.locator(".person img").evaluate_all("els => els.map(e => [e.naturalWidth, e.getBoundingClientRect().width])")
    check("two real clinician photos load, compact (<=64px) with names and roles (Visits tab)", len(imgs) == 2 and all(w > 0 and r <= 64 for w, r in imgs) and "Dr. Stefan Yakel, DO" in vtxt and "Sarah Frank, APRN" in vtxt and "Nurse practitioner" in vtxt, imgs)
    alex.locator("#nav button[data-view=home]").click(); alex.locator("#h-na").wait_for(timeout=8000)
    full_page = alex.evaluate("() => { const d = document.documentElement.cloneNode(true); d.querySelectorAll('#about').forEach(x => x.remove()); return d.outerHTML; }")  # preview19: the 'About this demo' sheet legitimately explains what is simulated
    check("no demo controls in patient UI (scrubber/simulate/persona switch/toast/presenter)", not re.search(r"scrub|simulate|persona|presenter|toast|Inbox zero", full_page + txt + vtxt, re.I), re.findall(r".{0,80}(?:scrub|simulate|persona|presenter|toast|Inbox zero).{0,40}", full_page + txt, re.I))
    check("banner says prototype/fictional/not HIPAA", "not HIPAA-compliant" in alex.locator("#banner").text_content())

    # ---------- B1: long message end to end
    alex.locator("button[data-view=messages]").click(); alex.locator("#msg-body").wait_for()
    n0 = alex.locator("#threads a.qitem").count()
    alex.locator("label[for=cat-scheduling]").click(); alex.locator("#msg-body").fill(LONG)
    cnt_txt = alex.locator("#msg-c").text_content(); check("counter matches code-point count", cnt_txt.startswith(f"{len(LONG)} of 2,000") or cnt_txt.startswith(f"{len(LONG):,} of 2,000"), cnt_txt)
    alex.locator("#msg-send").click(); alex.locator("#msg-status").filter(has_text="Sent.").wait_for(timeout=8000)
    st = alex.locator("#msg-status").text_content(); check("sent message shows TRUE status (Received \u00b7 Assigned to Front desk) and no promised time", "Received \u00b7 Assigned to Front desk" in st and "can\u2019t promise" in st, st)
    alex.locator("#threads a.qitem").first.wait_for(); check("new conversation appears (and only one)", alex.locator("#threads a.qitem").count() == n0 + 1)
    alex.locator("#threads a.qitem").first.click(); alex.locator("#conv .msg").first.wait_for()
    body = alex.locator("#conv .msg .body").first.text_content(); check("patient thread shows the FULL message (%d chars, line breaks, unicode)" % len(LONG), body == LONG, (len(body), body[-30:]))
    check("a 'LONG' > 400 chars (not truncated at 90)", len(body) > 400)
    tid = int(alex.url.split("/")[-1])
    pat = office_login(pat_c, "Pat")
    pat.goto(BASE + f"/office.html#/task/{tid}"); pat.locator("#d-convo .msg .body").first.wait_for(timeout=8000)
    ob = pat.locator("#d-convo .msg .body").first.text_content(); check("office case conversation shows the full message byte-for-byte", ob == LONG, (len(ob),))
    q_item = pat.locator("#qlist .qrow details.tmore:has-text('first 140 of')"); check("queue excerpt (under 'More', preview19 Prompt C) is explicitly marked as an excerpt with true length", q_item.count() >= 1 and f"{len(LONG):,} characters" in q_item.first.text_content().replace("\n", " "), q_item.first.text_content()[:200] if q_item.count() else "")
    check("composer label says suggestion is canned/simulated, never auto-sent", "canned template, simulated AI" in pat.locator("#draft-label").text_content())
    pat.locator("#reply-quote").click(); qv = pat.locator("#reply-body").input_value()
    check("draft quote contains the ENTIRE patient message (every line prefixed '> ')", all(("> " + ln) in qv for ln in LONG.split("\n") if ln) and "FINAL-MARKER-LINE" in qv, qv[-80:])
    check("nothing was auto-sent: patient thread still has exactly 1 message", len(api(alex_c, "GET", f"/api/p/threads/{tid}")[1]["messages"]) == 1)

    # ---------- B1b: counter / empty / too long
    alex.goto(BASE + "/portal.html#/messages"); alex.locator("#msg-body").wait_for(); alex.locator("#msg-body").fill("a" * 2001)
    check("UI counter flags 2,001 and disables Send (matches server max)", "over the 2,000 limit" in alex.locator("#msg-c").text_content() and alex.locator("#msg-send").is_disabled())
    alex.locator("#msg-body").fill("a" * 2000); check("2,000 characters allowed", alex.locator("#msg-send").is_enabled() and alex.locator("#msg-c").text_content().startswith("2,000 of 2,000"))
    alex.locator("#msg-body").fill("   \n "); alex.locator("label[for=cat-other]").click(); alex.locator("#msg-send").click()
    check("empty message rejected with inline message", "empty message can\u2019t be sent" in alex.locator("#msg-status").text_content())
    alex.locator("#msg-body").fill(""); 

    # ---------- B5: emergency live guidance + FAQ + handoff
    # preview19 Prompt C: the old Messages quick-question box (#ask-q) was merged into "Ask about your visit" (#/assist, scripted, no AI model).
    # The same questions are asked there; the old /api/p/ask route is still checked through the API (kept for older clients).
    check("Messages shows one 'Ask about your visit' entry and no separate quick-question box", alex.locator("#msg-assist").get_attribute("href") == "#/assist" and alex.locator("#ask-q").count() == 0)
    alex.locator("#msg-assist").click(); alex.locator("#as-q").wait_for(timeout=8000)
    alex.locator("#as-q").fill("I have chest pain and can't breathe")
    check("emergency wording shows 911/office guidance immediately (before submit)", "call 911 now" in alex.locator("#as-em").text_content())
    def ask_ui(q):
        alex.locator("#as-q").fill(q); alex.locator("#as-btn").click(); alex.locator("#as-answer").wait_for(timeout=8000); alex.wait_for_timeout(300); return alex.locator("#as-answer").text_content()
    ans = ask_ui("when is my next appointment"); check("appointment question answered with the REAL appointment (not a canned wrong answer)", re.search(r"October \d+", ans) and "10:30" in ans, ans[:300])
    ans = ask_ui("Do you have valet parking for oversized trucks?"); check("unknown question: says it can't answer and offers a person (no invented answer)", re.search(r"(can.t|couldn.t|not sure|don.t know|don.t have an answer)", ans, re.I) and re.search(r"(person|team|front desk|call)", ans, re.I), ans[:300])
    ans = ask_ui("Can I take ibuprofen with my medicine?"); check("medication question never auto-answered: refers to the clinical team", re.search(r"(nurse|clinical team|care team)", ans, re.I) and "take ibuprofen" not in ans.lower().replace("can i take ibuprofen", ""), ans[:300])
    ans = ask_ui("where is the office"); check("office-location answer shows the real address", "850 W Ironwood" in ans, ans[:300])
    s_, aa = api(alex_c, "POST", "/api/p/ask", {"question": "Do you have valet parking for oversized trucks?"}, key="ui-test-ask-1")
    qs = api(pat_c, "GET", "/api/o/queue?filter=open")[1]["tasks"]; hand = [t for t in qs if "valet" in (t.get("excerpt") or "")]
    check("(API) /api/p/ask handoff still creates a REAL assigned task (owner, backup, deadline) visible to staff", s_ == 200 and len(hand) == 1 and hand[0]["owner"] == "pat" and hand[0]["backup"] == "nina" and hand[0]["deadline"] and hand[0]["status"] == "Assigned", hand[:1])
    s_, aa = api(alex_c, "POST", "/api/p/ask", {"question": "Can I take ibuprofen with my medicine?"}, key="ui-test-ask-2")
    ib = [t for t in api(pat_c, "GET", "/api/o/queue?filter=open")[1]["tasks"] if "ibuprofen" in (t.get("excerpt") or "")]; check("(API) medication question task routed to Nurse", len(ib) == 1 and ib[0]["owner"] == "nina", ib[:1])
    alex.locator("button[data-view=messages]").click(); alex.locator("#msg-body").wait_for()

    # ---------- idempotency / double click
    before = len(api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"])
    alex.locator("button[data-view=messages]").click(); alex.locator("#msg-body").wait_for(); alex.locator("label[for=cat-billing]").click(); alex.locator("#msg-body").fill("Double click test message about a statement")
    alex.locator("#msg-send").dblclick(); alex.locator("#msg-status").filter(has_text="Status:").wait_for(timeout=8000); alex.wait_for_timeout(500)
    after = len(api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"]); check("double-click on Send creates exactly ONE task", after == before + 1, (before, after))
    alex.goto(BASE + "/portal.html#/home"); alex.locator("#cb-btn").wait_for(); b0 = len(api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"])
    alex.locator("#cb-btn").dblclick(); alex.locator("#cb-status").filter(has_text="Status:").wait_for(timeout=8000); alex.wait_for_timeout(400); alex.locator("#cb-btn").click(); alex.wait_for_timeout(600)
    b1 = len(api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"]); check("call-back requested twice+ creates exactly ONE open task", b1 == b0 + 1, (b0, b1))
    cbt = alex.locator("#cb-status").text_content(); check("call-back status is true and promises no time when office set none", "Received \u00b7 Assigned to Front desk" in cbt and "can\u2019t promise" in cbt, cbt)
    k = "same-key-123"; s1, j1 = api(alex_c, "POST", "/api/p/messages", {"category": "other", "body": "Idempotent retry body"}, key=k); s2, j2 = api(alex_c, "POST", "/api/p/messages", {"category": "other", "body": "Idempotent retry body"}, key=k)
    check("retry with same idempotency key returns the original (one task)", s1 == s2 == 200 and j1["task"]["id"] == j2["task"]["id"])

    # ---------- D: acknowledgment never closes; write-my-own keeps draft; drafts persist
    pat.goto(BASE + f"/office.html#/task/{tid}"); pat.locator("#d-head").get_by_text(f"Request #{tid} ").wait_for(timeout=8000); pat.locator("#reply-body").wait_for(); pat.locator("#reply-body").fill("Hi Alex, we got your note. (ack only)")
    pat.locator("label[for=k-ack]").click(); pat.locator("#reply-send").click(); pat.locator("#reply-st").filter(has_text="still open").wait_for(timeout=8000)
    d = api(pat_c, "GET", f"/api/o/tasks/{tid}")[1]; check("approving/sending an acknowledgment leaves the underlying request OPEN", d["task"]["status"] in ("In Progress", "Assigned") and d["task"]["acknowledged"] and d["task"]["status"] != "Resolved", d["task"]["status"])
    check("task still listed in the open queue", any(t["id"] == tid for t in api(pat_c, "GET", "/api/o/queue?filter=open")[1]["tasks"]))
    alex.goto(BASE + f"/portal.html#/messages/{tid}"); alex.locator("#conv .msg").nth(1).wait_for(); pt = alex.locator("main").text_content()
    check("patient sees the acknowledgment labelled as NOT an answer, and the request still open", "acknowledgment (not an answer yet)" in pt and "still open" in pt, pt[:300])
    jt = api(pat_c, "GET", "/api/o/queue?filter=open")[1]["tasks"]; jt = [t for t in jt if t["patient_name"] == "Jordan Sample" and t["type"] == "message"][0]["id"]
    pat.goto(BASE + f"/office.html#/task/{jt}"); pat.locator("#d-head").get_by_text(f"Request #{jt} ").wait_for(timeout=8000); pat.locator("#reply-body").wait_for(); sugg = pat.locator("#reply-body").input_value()
    check("composer opens with the suggested draft, labelled as suggestion", sugg.startswith("Hi Jordan") and "Suggested draft" in pat.locator("#draft-label").text_content())
    pat.locator("#reply-own").click(); check("'Write my own' keeps the draft text, focuses the composer, relabels it", pat.locator("#reply-body").input_value() == sugg and pat.evaluate("document.activeElement.id") == "reply-body" and pat.locator("#draft-label").text_content().startswith("Your draft"))
    mine = sugg + "\n\nOur front desk can move you to 4:15 PM \u2014 UNSAVED-EDIT-1 \u00e9\U0001F600"; pat.locator("#reply-body").fill(mine)
    pat.locator("#draft-ind").filter(has_text="Draft saved on the server").wait_for(timeout=6000)
    check("autosave indicator reports a REAL server save with time", re.search(r"Draft saved on the server at .* PT\. Not sent\.", pat.locator("#draft-ind").text_content()))
    ds = api(pat_c, "GET", f"/api/o/tasks/{jt}")[1]["draft"]; check("server holds the exact draft (source=saved)", ds["source"] == "saved" and ds["body"] == mine)
    pat.locator("#note-body").fill("staff-only: INTERNAL-ONLY-XYZ"); pat.locator("#d-notes button").click(); pat.locator("#note-st").filter(has_text="Note added").wait_for()
    pat.locator("#ver-src").fill("called the front desk"); pat.locator("button:has-text('Record verified update')").click(); pat.locator("#act-st").filter(has_text="Verified update recorded").wait_for()
    pat.locator("#refresh").click(); pat.wait_for_timeout(700)
    check("draft survives unrelated actions (note, verified update, manual refresh)", pat.locator("#reply-body").input_value() == mine)
    pat.locator("nav button[data-view=notifications]").click(); pat.locator("h1:has-text('Notifications')").wait_for(); pat.locator("nav button[data-view=queue]").click(); pat.wait_for_timeout(300); pat.goto(BASE + f"/office.html#/task/{jt}")
    pat.locator("#reply-body").wait_for(); check("draft survives tab switch (Notifications and back)", pat.locator("#reply-body").input_value() == mine)
    pat.locator("#reply-body").press("End"); pat.keyboard.type(" TYPED-NOW"); pat.locator("#qlist a.qitem").first.click(); pat.wait_for_timeout(300); pat.goto(BASE + f"/office.html#/task/{jt}"); pat.locator("#d-head").get_by_text(f"Request #{jt} ").wait_for(timeout=8000); pat.locator("#reply-body").wait_for(); pat.wait_for_timeout(500)
    check("unsaved typing is flushed to the server when switching to another item", pat.locator("#reply-body").input_value() == mine + " TYPED-NOW", pat.locator("#reply-body").input_value()[-30:])
    pat.reload(); pat.locator("#reply-body").wait_for(); check("draft survives full page REFRESH", pat.locator("#reply-body").input_value() == mine + " TYPED-NOW")
    jp = jordan_c.new_page(); track(jp); jp.goto(BASE + "/portal.html"); jp.locator("button.qitem:has-text('Jordan Sample')").click(); jp.locator("h1:has-text('Hello')").wait_for(); jp.goto(BASE + f"/portal.html#/messages/{jt}"); jp.locator("#conv .msg").first.wait_for()
    check("staff-only note and unsent draft are invisible to the patient UI", "INTERNAL-ONLY-XYZ" not in jp.content() and "UNSAVED-EDIT-1" not in jp.content())
    # failure of autosave is shown honestly
    pat.route("**/draft", lambda r: r.abort()); pat.locator("#reply-body").press("End"); pat.keyboard.type("!"); pat.wait_for_timeout(1800)
    check("autosave failure is shown honestly ('Could not save'), never 'Saved'", "Could not save" in pat.locator("#draft-ind").text_content() and "saved on the server" not in pat.locator("#draft-ind").text_content(), pat.locator("#draft-ind").text_content())
    pat.unroute("**/draft")

    # ---------- state rules in the UI
    pat.goto(BASE + f"/office.html#/task/{jt}"); pat.locator("button:text-is('Resolve…')").wait_for(); pat.locator("button:text-is('Resolve…')").click(); pat.locator("#st-form button:has-text('Resolve with this outcome')").click()
    pat.locator("#act-st").filter(has_text=re.compile("Outcome note is required", re.I)).wait_for(); check("Resolve without an outcome note is refused (inline)", True)
    pat.locator("#f-outcome").fill("Moved Jordan to 4:15 PM; confirmed by phone."); pat.locator("#st-form button:has-text('Resolve with this outcome')").click(); pat.locator("#act-st").filter(has_text="Resolved").wait_for(timeout=6000)
    d = api(pat_c, "GET", f"/api/o/tasks/{jt}")[1]["task"]; check("Resolved records outcome and WHO resolved it", d["status"] == "Resolved" and d["outcome"].startswith("Moved Jordan") and d["resolved_by"] == "pat")
    pat.goto(BASE + f"/office.html#/task/{tid}"); pat.locator("button:text-is('Mark waiting…')").click(); pat.locator("#st-form button:text-is('Mark waiting')").click(); pat.locator("#act-st").filter(has_text=re.compile("Waiting on is required", re.I)).wait_for()
    check("Waiting requires whom/what (refused when blank)", True)

    # ---------- caregiver UI scope
    rl = portal_login(riley_c, "Riley Helper"); rt = rl.locator("main").text_content(); rl.locator("#nav button[data-view=visits]").click(); rl.locator("main h1:has-text('Visits')").wait_for(timeout=8000); rl.wait_for_timeout(300); rt += rl.locator("main").text_content()
    check("caregiver sees only what Alex shared (appointment + instructions); no waiting-on, no call-back request", "Next appointment" in rt and "Before your visit" in rt and "What we\u2019re waiting on" not in rt and rl.locator("#cb-btn").count() == 0, rt[:200])
    check("caregiver API: threads 403, Jordan's thread 404/403", api(riley_c, "GET", "/api/p/threads")[0] == 403 and api(riley_c, "GET", f"/api/p/threads/{jt}")[0] in (403, 404))
    check("caregiver token on office API -> 403", api(riley_c, "GET", "/api/o/queue")[0] in (401, 403))
    check("patient token on office API -> 403", api(alex_c, "GET", "/api/o/queue")[0] in (401, 403) and api(alex_c, "GET", f"/api/o/tasks/{tid}")[0] in (401, 403))

    # ---------- failed notification -> visible, recoverable exception
    from ui_lib import api as A
    pr = jordan_c.request.post(BASE + "/api/presenter/enter", headers={"X-PS-Client": "1", "Content-Type": "application/json"}, data="{}")
    def prs(path, body=None): return A(jordan_c, "POST", path, body or {})
    prs("/api/presenter/scenario", {"name": "bad_phone_jordan"})
    jt2 = api(jordan_c, "POST", "/api/p/messages", {"category": "scheduling", "body": "Second scheduling question for the failure test"}, key="jk-1")[1]["task"]["id"]
    pat.goto(BASE + f"/office.html#/task/{jt2}"); pat.locator("#d-head").get_by_text(f"Request #{jt2} ").wait_for(timeout=8000); pat.locator("#reply-body").wait_for(); pat.locator("#reply-send").click(); 
    try: pat.locator("#reply-st").filter(has_text="Reply sent").wait_for(timeout=6000)
    except Exception: print("DEBUG reply-st:", pat.locator("#reply-st").text_content(), "| body:", pat.locator("#reply-body").input_value()[:100], "| url", pat.url); raise
    for _ in range(5): prs("/api/presenter/tick")
    pat.goto(BASE + "/office.html#/queue"); pat.locator("#qlist a.qitem").first.wait_for(); qtxt = pat.locator("#qlist").text_content()
    check("failed notification created a VISIBLE exception task in the single queue", "Notification failed after 3 attempts" in qtxt, qtxt[:200])
    ex = [t for t in api(pat_c, "GET", "/api/o/queue?filter=open")[1]["tasks"] if t["type"] == "exception"]; check("exception task has owner, backup and deadline", len(ex) == 1 and ex[0]["owner"] and ex[0]["backup"] and ex[0]["deadline"], ex[:1])
    pat.locator("nav button[data-view=notifications]").click(); pat.locator("button:has-text('Retry sending')").first.wait_for(); prs("/api/presenter/scenario", {"name": "good_phone_jordan"})
    pat.locator("button:has-text('Retry sending')").first.click(); pat.wait_for_timeout(600); prs("/api/presenter/tick"); prs("/api/presenter/tick")
    pat.reload(); pat.wait_for_timeout(800); nt = [n for n in api(pat_c, "GET", "/api/o/notifications")[1]["notifications"] if n["task_id"] == jt2][0]
    check("failed notification is recoverable: manual retry -> sent -> delivered", nt["status"] == "delivered", nt["status"])

    # ---------- presenter-only controls
    pp = admin_c.new_page(); track(pp); pp.goto(BASE + "/presenter.html"); pp.locator("#pm-toggle").wait_for()
    check("presenter page has a visible 'Presenter mode' toggle, OFF by default, panels hidden", "OFF" in pp.locator("#pm-toggle").text_content() and pp.locator("#panels").text_content().strip() == "")
    pp.locator("#pm-toggle").click(); pp.locator("text=Scenarios").first.wait_for(); check("turning it on reveals persona switching, scenarios, reset", pp.locator("text=Switch persona").count() == 2 and pp.locator("button:has-text('Reset all fictional data')").count() == 1)
    ix = alex_c.new_page(); ix.goto(BASE + "/"); check("landing page links to presenter only as a small separate link; portal/office pages have none", "presenter.html" in ix.content() and "presenter" not in alex.content().lower() and "presenter" not in pat.content().lower())

    # ---------- reports (admin) measured only
    ad = office_login(admin_c, "Admin"); ad.locator("nav button[data-view=reports]").click(); ad.locator("h1:has-text('Reports')").wait_for(); ad.locator("table").wait_for(); rtxt = ad.locator("main").text_content()
    check("Reports page: measured values, payroll disclaimer, no invented money/percent figures", "not payroll savings" in rtxt and "Time to first acknowledgment" in rtxt and not re.search(r"\$\d|\d+%", rtxt), rtxt[:200])
    check("front desk has no Reports/Audit/Settings nav; API refuses", pat.locator("#nav-reports").is_hidden() and api(pat_c, "GET", "/api/o/reports")[0] == 403 and api(pat_c, "GET", "/api/o/audit")[0] == 403)
    check("no 'Inbox zero' or bare 'Saved' claims anywhere", not re.search(r"Inbox zero|\bSaved!?\b(?! on)", rtxt + alex.content() + pat.content()), "")

    # ---------- restart durability (real server restart)
    before_q = api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"]; draft_before = api(pat_c, "GET", f"/api/o/tasks/{tid}")[1]["draft"]
    pat.goto(BASE + f"/office.html#/task/{tid}")
    jt3 = [t for t in before_q if t["patient_name"] == "Jordan Sample" and t["status"] == "In Progress"]
    pat.goto(BASE + f"/office.html#/task/{jt2}"); pat.locator("#d-head").get_by_text(f"Request #{jt2} ").wait_for(timeout=8000); pat.locator("#reply-body").wait_for(); pat.locator("#reply-body").fill("RESTART-DRAFT survives the server restart \u00e9"); pat.locator("#draft-ind").filter(has_text="Draft saved on the server").wait_for(timeout=6000)
    srv.stop(); time.sleep(0.5); srv.start(reset=False)
    pat.reload(); pat.locator("#reply-body").wait_for(timeout=8000)
    # jt2 was already replied (draft deleted) -> composer shows suggestion for a new reply? use API for exactness
    after_q = api(pat_c, "GET", "/api/o/queue?filter=all")[1]["tasks"]
    check("tasks survive a SERVER RESTART (same ids, same count, same session cookie)", [t["id"] for t in after_q] == [t["id"] for t in before_q] and api(pat_c, "GET", "/api/o/me")[0] == 200)
    check("the unsent draft survives a SERVER RESTART and reload", pat.locator("#reply-body").input_value() == "RESTART-DRAFT survives the server restart \u00e9", pat.locator("#reply-body").input_value()[:40])
    check("the long patient message survives the restart in full", api(alex_c, "GET", f"/api/p/threads/{tid}")[1]["messages"][0]["body"] == LONG)

    # ---------- browser storage / cookies / network
    for name, pg in (("patient", alex), ("office", pat), ("presenter", pp)):
        s = pg.evaluate("() => [localStorage.length, sessionStorage.length, document.cookie]"); check(f"no localStorage/sessionStorage and no script-visible cookie: {name}", s == [0, 0, ""], s)
    ck = {c["name"]: c for c in alex_c.cookies()}; check("session token is an httpOnly SameSite=Strict cookie (not readable by page JS)", ck["ps_portal"]["httpOnly"] and ck["ps_portal"]["sameSite"] == "Strict")
    ext = sorted(u for u in REQS if not u.startswith(BASE)); check("no external network requests during the whole run", not ext, ext)
    br.close()
srv.stop(); save()
bad = [r for r in RESULTS if not r[1]]; print(f"\nDONE ui_test: {len(RESULTS) - len(bad)}/{len(RESULTS)} passed; failed: {[r[0] for r in bad]}")
