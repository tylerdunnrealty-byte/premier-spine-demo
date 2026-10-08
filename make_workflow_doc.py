#!/usr/bin/env python3
"""Writes workflow-states.md from server.py (TRANSITIONS, CASE_STATES, gates, SCENARIOS, and the quick-action catalog collected by
actually walking the eight scenarios on a scratch database) so the doc cannot drift from the code."""
import os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import server
rows = "\n".join(f"| {t['from']} | {t['to']} | {t['who']} | {t['requires']} | {t['meaning']} |" for t in server.TRANSITIONS)
# ---- Pass 2: collect the quick-action catalog by running the scenario scripts on a scratch DB (nothing leaves this machine)
server.STATE["db"] = os.path.join(tempfile.mkdtemp(), "doc.db"); server.init_db(fresh=True)
db = server.connect(); CAT = {}
USERS = {k: server.user_row(db, k) for k in ("pat", "nina", "yakel")}
def collect():
    for t in server.rows(db.execute("SELECT * FROM tasks WHERE source='case' AND status NOT IN ('Resolved','Received')")):
        for a in server.task_actions(db, t):
            d = CAT.setdefault(t["type"], {}).setdefault(a["key"], {"label": a["label"], "fields": [f["label"] for f in a["fields"]], "simulated": a["simulated"], "roles": a["roles"]})
def act(cid, ty, key, who="pat", **b):
    t = server.open_task(db, cid, ty); server.do_action(db, USERS[who], t, key, b); collect()
for sc in server.SCENARIOS:
    for step in ("start", "intake", "key"):
        if step == "intake" and sc["key"] not in server.INTAKE_STEP: continue
        server.run_scenario(db, sc["key"], step); collect()
S = {sc["key"]: sc for sc in server.SCENARIOS}
server.run_scenario(db, "auth", "start"); act(13, "fit_review", "accept", "yakel", reviewed_report=True); act(13, "insurance_check", "run_check")
server.run_scenario(db, "notfit", "start"); act(16, "fit_review", "need_info", "yakel", question="Example?"); act(16, "referral_info", "send_info_request")
act(16, "referral_info", "info_received", answer="Example answer"); act(16, "fit_review", "route_elsewhere", "yakel", reason="Example reason")
server.run_scenario(db, "auth", "key"); act(13, "prior_auth", "record_decision", decision="denied", reference="EX-1")
server.run_scenario(db, "missing", "key"); server.sim_records_arrive(db, 12, S["missing"]["facility"], ["radiology_report"]); collect()
for t in server.rows(db.execute("SELECT * FROM tasks WHERE case_id=12 AND type='records_request' AND status!='Resolved'")):
    acts = {a["key"]: a for a in server.task_actions(db, t)}
    if "mark_received" in acts: server.do_action(db, USERS["pat"], t, "mark_received", {}); collect()
for step in ("postop", "postop_concern"): server.run_scenario(db, "surgery", step); collect()
# a stuck chase: push the 'missing' records request past its follow-up date until the automatic follow-ups run out
server.run_scenario(db, "missing", "key")
for _ in range(server.MAX_CHASES + 1):
    db.execute("UPDATE tasks SET follow_up_by=? WHERE case_id=12 AND status='Waiting' AND type IN ('records_request','prior_auth','clearance_request','referral_info')", ("2000-01-01T00:00:00Z",)); server.chase_tick(db)
collect()
server.run_scenario(db, "caregiver", "intake"); server.script_intake(db, "frankie", 15, confirm={"name": "ok", "dob": "ok", "phone": "change", "referrer": "ok", "reason": "ok", "insurance": "ok", "imaging": "ok", "meds": "ok", "allergies": "ok"}, corrections={"phone": "(208) 555-0100 (example)"}); collect()
db.close()
WHO = {None: "Front desk, nurse or clinician", "clinician": "**Clinician only** (Dr. Yakel / Sarah Frank, APRN)", "nurse_or_clinician": "**Nurse or clinician**"}
cat_rows = "\n".join(f"| `{ty}` | {a['label']} | {WHO[a['roles']]} | {', '.join(a['fields']) or '\u2014 (one click)'} | {'yes' if a['simulated'] else ''} |" for ty in CAT for k, a in CAT[ty].items())
state_rows = "\n".join(f"| `{k}` | {o} | {pw} |" for k, o, pw in server.CASE_STATES)
scn_rows = "\n".join(f"| {sc['n']}. {sc['title']} | {sc['key_state']} | {sc['owner']} | {sc['human']} | {sc['patient_sees']} | {sc['office_sees']} |" for sc in server.SCENARIOS)
preop_rows = "\n".join(f"| `{k}` | {lab} | {team} | {dict(front='Front desk, nurse or clinician', clinician='**Clinician only**', patient='The patient (in the portal)').get(who, who)} | {pw} |" for k, lab, team, who, pw in server.PREOP)
RT = lambda r: f"owner {r[0]}, backup {r[1]}, {r[2]} h internal deadline ({r[3]})"

doc = f"""# Workflow states (preview17 prototype — DEMO, example data only)

Generated from `TRANSITIONS` in `server.py` by `make_workflow_doc.py`. The server enforces this table: any move not listed is refused (HTTP 409).
**Prototype · fictional data · not production · not HIPAA-compliant.**

## The five states

| State | Meaning |
|---|---|
| **Received** | The request exists. No one is named yet. (Routing rules normally assign immediately, so work does not sit here.) |
| **Assigned** | A named **owner**, a **backup** and an internal **deadline** exist. Nobody has started. |
| **In Progress** | A person has started. A reply or internal note by staff moves *Assigned → In Progress* automatically. |
| **Waiting** | Work is blocked on someone outside the practice, or on the patient. Requires **waiting on whom/what** and a **follow-up date**. Patients see what we are waiting on. |
| **Resolved** | The underlying need is met or closed on purpose. Requires an **outcome note** and records **who resolved** it. |

## Transitions

| From | To | Who | Requires | Meaning |
|---|---|---|---|---|
{rows}

Anything else (for example *Received → Resolved*, *Assigned → Received*) is refused.

## Rules that matter

1. **Acknowledgment is not resolution.** Sending an acknowledgment (`kind=ack`) records `ack_at`, queues a notification and tells the patient "we received this; it is still open". The task status does not become Resolved. A real reply (`kind=reply`) does not resolve it either. Only the *→ Resolved* transition does, and it needs an outcome note from a person allowed to close that task type.
2. **Waiting is a promise to look again.** If the follow-up date passes, the server moves the task *Waiting → Assigned* flagged "follow-up due" (system only; staff cannot do this by hand).
3. **Clinical tasks are closed by clinical staff.** Tasks with `clinical_level` 1 (nurse) or 2 (clinician) refuse Resolve from the front desk. Marking a radiology report reviewed is clinician-only.
4. **Every handoff claim creates a real task.** When the portal says "a person will help" (a message, an *Ask* that has no confident answer, a call-back request, a failed notification) the server creates an assigned task with owner, backup and deadline in the same database transaction. If no task can be created, the request fails visibly instead of making a claim.
5. **The patient sees the true status**: `Received · Assigned to Front desk`, `Being worked on by Nurse`, `Waiting for …`, `Closed`. A reply-time sentence ("We aim to reply …") appears **only** if an administrator set a target in Settings. Otherwise the portal says no time is promised. Internal deadlines are never shown to patients as promises.
6. **Report vs images are separate.** `report_status` (not requested → requested → received → reviewed) and `images_status` (unknown/requested/received/unavailable/waived) are tracked independently. "Ready for appointment" needs the report reviewed *and* images received (or a clinician waiving them with a note).

## Notification states (messages sent to a patient)

`queued → sent → delivered → received → accepted`, or `failed`.

| State | Meaning | Real or simulated here |
|---|---|---|
| queued | The office action asked for a notification. | real row in the database |
| sent | Handed to the delivery provider. | **simulated provider** (a worker step) |
| delivered | The provider reported delivery. | **simulated receipt** |
| received | The patient opened the message in the portal. | real (server sees the patient read it) |
| accepted | The patient did what it asked (for example confirmed the appointment). | real |
| failed | Not delivered after **3 attempts** (retry limit). Creates an **exception task** (owner Pat, backup Nina, 4-hour deadline) so the failure is visible in the queue. | rule is real, the vendor error is simulated |

Staff may retry a failed notification manually at most **2** times; after that the screen says to phone the patient. "Delivered" never means "the patient read it".

## Limits enforced by the server (the screens show the same counters)

Message 2,000 characters (code points) · Ask 300 · internal note 2,000 · reply draft 4,000 · outcome note 1,000 · request body 64 KB. Empty or whitespace-only text is refused. Over-limit text is refused with the exact length and limit; nothing is truncated.

## Pass 2 — referral → records → intake → ready for appointment

A referral is a **case** with gates. The case state is **computed** from the gates every time anything changes (`recompute_case`),
and both the portal and the office read the SAME description of it (`case_view`), worded for each audience. The system never
declines a referral, never cancels a visit and never decides anything clinical: those are buttons only a clinician can press.

### Gates (all must pass before "Ready for appointment")

| Gate | Passes when |
|---|---|
| fit | a clinician accepted the referral (no automatic acceptance or decline) |
| records | office notes received; MRI **report** reviewed by a clinician (or waived); MRI **images** received **or** a clinician decided to proceed without them (reason recorded). Report and images are tracked separately. |
| insurance | simulated eligibility check says no prior auth needed, **or** staff recorded the insurer's approval **with a reference** |
| intake | intake submitted **and** confirmed by the patient (helper-entered answers count only after the patient confirms in the portal or by phone with staff) |
| safety | no unreviewed red-flag symptom (a nurse or clinician clears it with an outcome note) |
| identity | identity verified (seeded as verified for the fictional scenario patients) |

### Case states

| State | Office label | What the patient reads |
|---|---|---|
{state_rows}

When a case first becomes ready the server creates ONE "Book the visit" task for the front desk and logs `case.ready`; if a gate later fails it logs `case.not_ready`.

### Routing (prototype placeholders — the office must confirm owners and hours)

* Clinician decisions (fit review, report review, images waiver): {RT(server.CLIN_ROUTE)}
* Front-desk work (records requests, insurance, intake follow-up, booking, calls): {RT(server.FRONT_ROUTE)}
* Red flag reported in intake: {RT(server.REDFLAG_ROUTE)}, priority **urgent**

### Quick actions ("Do next") — collected from the code by walking the scenarios

The office never has to pick a status by hand for this work: each task type offers the next real step. The server re-checks role and
state on every click (`POST /api/o/tasks/{{id}}/act`, Idempotency-Key required). Disallowed actions are shown disabled with the reason.

| Task type | Action | Who may do it | Inputs | Simulated |
|---|---|---|---|---|
{cat_rows}

Intake reminders stop at **{server.MAX_INTAKE_REMINDERS}** (a 4th is refused, HTTP 409); after that the next step is a phone call logged by a person.
The reminder cadence is NOT invented: reminders are sent when staff click (or the presenter simulates one). See the open questions in README.md.

### The eight scenarios (presenter: *Referral scenarios* card → "Load at start" / "Jump to key state")

| Scenario | Key state | Owner | Human step | Patient sees | Office sees |
|---|---|---|---|---|---|
{scn_rows}

### Automatic chasing (spotlight 2) — SIMULATED follow-ups, people step in only when stuck

Applies to referral-pipeline tasks of type {", ".join("`%s`" % t for t in server.CHASE_TYPES)} while they are **Waiting** on another office or insurer.

1. When the follow-up date passes, the server sends an **automatic follow-up** (simulated fax or simulated insurer-portal message — nothing leaves this machine), logs `chase.sent`, counts it on the task (`chases`) and sets a new follow-up date **{server.CHASE_GAP_DAYS} days** later. The task stays *Waiting*; nobody is asked to do anything.
2. After **{server.MAX_CHASES}** automatic follow-ups with no answer, the next due date makes the task **STUCK**: *Waiting → Assigned* (system), `blocked_step` "STUCK: no answer from … after {server.MAX_CHASES} automatic follow-ups (simulated)", a type-aware next step ("Phone …, then record …"), event `chase.stuck`. Stuck items sort right after urgent/overdue work in the queue and carry a red "Stuck — needs a phone call" chip.
3. The patient sees "We followed up automatically N time(s) (simulated) — nothing needed from you", and once stuck, "This is taking longer than expected, so a team member is following up by phone." No dates are predicted.
4. Presenter: *Referral scenarios* → "Follow-up date passes" (missing records, prior auth, surgery clearance) moves the clock for that scenario only.

`{server.MAX_CHASES}` follow-ups and `{server.CHASE_GAP_DAYS}`-day gaps are **prototype placeholders — the office decides** (see README open questions).

### Fewer phone calls (spotlight 1)

Every status line in the portal names **what we are waiting on, who is handling it (team) and the next step**. Opening the status page while items are pending logs `status.viewed` (at most once per 10 minutes per patient). The office queue shows a **"Calls this portal may have saved"** card (`GET /api/o/calls-avoided`) that counts status views, automatic follow-ups, self-confirmed intake answers and check-ins answered in this demo's **fictional** data. It is labelled **EXAMPLE COUNTS ONLY** and says it is not a measured reduction in calls and says nothing about staff time or cost.

### Visit-ready summary for Dr. Yakel (spotlight 3) — DRAFT, needs clinician review

`GET /api/o/cases/{{id}}/summary` assembles patient, referral, records/imaging status, insurance, the patient's confirmed or corrected intake answers, the safety question and any open items. Outcome questionnaires (ODI, NDI, PROMIS — named only) are **not collected** in this demo; the summary says so. Every summary carries the label "DRAFT — assembled automatically … Needs clinician review. Not a clinical note." Only a clinician can mark it reviewed (`POST …/summary/review`, event `summary.reviewed`); a content hash shows "changed since review" if anything moves afterwards.

### Surgery pathway (scenario 8, spotlight 4) — pre-op checklist, clearance tracking, post-op check-ins

A case with `pathway = surgery` leaves the referral gates behind and is in state **surgery** until the (example) surgery date, then **postop**. The checklist items are **prototype placeholders; the office defines the real list**:

| Item | Label | Owner team | Who may mark it done | Patient reads (until done) |
|---|---|---|---|---|
{preop_rows}

* **Clearance tracking:** a `clearance_request` task is sent (simulated fax) to the primary-care office and auto-chased like records (above). "Clearance received" moves the checklist item to *received — needs review*; only a clinician signs it off.
* **Pre-op instructions:** the portal never shows instruction content. It asks the patient to confirm they have the written instructions from the surgical team (`POST /api/p/preop/instructions`). Instruction content is a clinic decision (see README "placeholder instruction slots").
* **Post-op check-ins:** scheduled on days {", ".join(str(d) for d in server.CHECKIN_DAYS)} after surgery (placeholder — surgeon decides), sent as a simulated text plus a portal card. The patient picks *I’m doing okay* / *I have a question for a nurse* / *Something worries me — please call me* (a few words are required for question/concern). A **concern** creates an **urgent** nurse task ({RT(server.REDFLAG_ROUTE)}); a **question** creates a normal nurse task; emergency wording shows 911 guidance immediately and makes the task urgent. No advice is generated.
* **Missed check-in:** a check-in not answered within one day of being sent (placeholder rule) becomes `missed` and creates a `postop_missed` front-desk task: "Phone the patient".

### Red flags in the intake

Four example symptom checkboxes (plus emergency wording in the free-text answer) raise an **urgent** nurse task **when the draft autosaves**,
before the patient presses Send, and show 911 / call-the-office guidance immediately. Saving the same, already-reviewed symptoms again does not
re-raise the hold; a NEW symptom does. `MEDICAL COPY — symptom wording and guidance need Dr. Yakel's review.`

## Intake pre-fill (tell us once)

Each pre-filled item shows its **source** (for example "Referral letter from … (simulated fax — example data)") with a "Simulated source" tag, a plain-language **hint** and a **"Why we ask"** explanation. The patient only confirms or corrects; corrections are shown to staff side by side with the original. Help copy is example wording for the office to review.

## Not a clinical triage system

The wording lists in `server.py` (emergency, symptom/medication) only decide **where a request goes and what the patient is told immediately**. Anything uncertain goes to a person. The clinical escalation path must be owned by the care team; it is not live in this prototype. `MEDICAL COPY — needs Dr. Yakel review`.
"""
open(os.path.join(HERE, "workflow-states.md"), "w", encoding="utf-8").write(doc)
print("workflow-states.md written")
