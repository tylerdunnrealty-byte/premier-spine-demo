# Workflow states (preview17 prototype — DEMO, example data only)

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
| Received | Assigned | office, clinician, admin, or the routing rule at creation | owner, backup, deadline | Someone is named as responsible, with a backup and an internal deadline. Nobody has started yet. |
| Assigned | In Progress | any staff member (a reply or note by staff does this automatically) | — | A person has started work. This is the earliest state in which the patient is told it is being worked on. |
| Assigned | Waiting | any staff member | waiting_on (whom/what) + follow_up_by (date) | Work is blocked on someone outside the practice or on the patient. The follow-up date is when staff will look again. |
| In Progress | Waiting | any staff member | waiting_on (whom/what) + follow_up_by (date) | Same as above, after work has started. |
| Waiting | In Progress | any staff member, or the system when the awaited item arrives | — | The awaited item arrived or was chased; work resumes. waiting_on and follow_up_by are cleared. |
| Waiting | Assigned | system only (follow-up date passed) | — | The follow-up date passed with no change; the task returns to its owner flagged 'follow-up due'. |
| Assigned | Resolved | staff allowed to close this task type | outcome note (who/what changed) | The underlying need is met or closed on purpose. An acknowledgment or a reply does NOT do this. |
| In Progress | Resolved | staff allowed to close this task type | outcome note | Same as above. |
| Waiting | Resolved | staff allowed to close this task type | outcome note | Closed while waiting (for example patient unreachable after the allowed attempts, or no longer needed). |
| Resolved | In Progress | office, clinician, admin | reason | Reopened because the need came back or the outcome was wrong. Logged. |

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
| `fit_review` | New referral — clinician fit review | We received your referral. Our clinical team is reviewing it. |
| `gathering` | Gathering what the first visit needs | We’re getting everything ready for your first visit. |
| `urgent` | URGENT — red-flag symptom, clinical review | Because of a symptom you told us about, please read the guidance at the top of this page now. |
| `ready` | Ready for appointment | Everything we need is in. You’re ready for your first visit. |
| `booked` | Ready for appointment · visit booked | Everything we need is in and your first visit is booked. |
| `routed` | Closed — routed elsewhere (clinician decision) | Our clinical team reviewed your referral. A team member will call you to talk about next steps. |
| `surgery` | Surgical pathway — pre-op checklist | Your surgery is being prepared. The checklist below shows what is done, who has it, and what we are waiting on. |
| `postop` | After surgery — post-op check-ins | After your surgery we check in with you at set points. Your answers go to your care team. |

When a case first becomes ready the server creates ONE "Book the visit" task for the front desk and logs `case.ready`; if a gate later fails it logs `case.not_ready`.

### Routing (prototype placeholders — the office must confirm owners and hours)

* Clinician decisions (fit review, report review, images waiver): owner yakel, backup frank, 24 h internal deadline (Clinician)
* Front-desk work (records requests, insurance, intake follow-up, booking, calls): owner pat, backup nina, 24 h internal deadline (Front desk)
* Red flag reported in intake: owner nina, backup yakel, 2 h internal deadline (Nurse), priority **urgent**

### Quick actions ("Do next") — collected from the code by walking the scenarios

The office never has to pick a status by hand for this work: each task type offers the next real step. The server re-checks role and
state on every click (`POST /api/o/tasks/{id}/act`, Idempotency-Key required). Disallowed actions are shown disabled with the reason.

| Task type | Action | Who may do it | Inputs | Simulated |
|---|---|---|---|---|
| `fit_review` | Accept referral | **Clinician only** (Dr. Yakel / Sarah Frank, APRN) | — (one click) |  |
| `fit_review` | Ask the referring office a question… | **Clinician only** (Dr. Yakel / Sarah Frank, APRN) | Question for the referring office, Check again by (prototype default — change it) |  |
| `fit_review` | Route elsewhere… | **Clinician only** (Dr. Yakel / Sarah Frank, APRN) | Reason (staff only — the patient is told by phone, not in the portal) |  |
| `records_request` | Send records request to Example Family Clinic (fictional) (simulated fax) | Front desk, nurse or clinician | Check again by (prototype default — change it) | yes |
| `records_request` | Mark received… | Front desk, nurse or clinician | Which items arrived and match this patient? |  |
| `records_request` | Images not available… | Front desk, nurse or clinician | What did the facility say? |  |
| `intake_followup` | Send reminder 1 of 3 (simulated text) | Front desk, nurse or clinician | — (one click) | yes |
| `intake_followup` | Log a phone call… | Front desk, nurse or clinician | What happened?, Note (optional) |  |
| `intake_followup` | Close: patient unreachable… | Front desk, nurse or clinician | What was tried? |  |
| `schedule_visit` | Book the visit… | Front desk, nurse or clinician | Date, Time (PT), With |  |
| `prior_auth` | Record the insurer’s decision… | Front desk, nurse or clinician | What did the insurer decide?, Reference number or who you spoke to |  |
| `prior_auth` | Submit prior-auth request (simulated) | Front desk, nurse or clinician | Check again by (prototype default — change it) | yes |
| `intake_confirm` | Patient confirmed by phone… | Front desk, nurse or clinician | Who confirmed, and how? |  |
| `red_flag` | Log contact with the patient… | Front desk, nurse or clinician | What happened? (staff only) |  |
| `red_flag` | Clinical review done — clear urgent hold… | **Nurse or clinician** | Clinical outcome (staff only) |  |
| `clearance_request` | Send clearance request (simulated fax) | Front desk, nurse or clinician | Check again by (prototype default — change it) | yes |
| `clearance_request` | Clearance arrived — matches this patient | Front desk, nurse or clinician | — (one click) |  |
| `insurance_check` | Run eligibility check (simulated) | Front desk, nurse or clinician | — (one click) | yes |
| `referral_info` | Send the question (simulated fax) | Front desk, nurse or clinician | Check again by (prototype default — change it) | yes |
| `referral_info` | Referring office answered… | Front desk, nurse or clinician | Their answer |  |
| `notify_routed` | Patient and referring office told… | Front desk, nurse or clinician | Outcome note (who / what) |  |
| `auth_denied` | Record what was agreed with the patient… | Front desk, nurse or clinician | Outcome note (who / what) |  |
| `records_review` | Mark MRI report reviewed | **Clinician only** (Dr. Yakel / Sarah Frank, APRN) | — (one click) |  |
| `records_review` | Proceed without images… | **Clinician only** (Dr. Yakel / Sarah Frank, APRN) | Clinical reason (staff only) |  |
| `postop_concern` | Log contact with the patient… | Front desk, nurse or clinician | What happened? (staff only) |  |
| `postop_concern` | Concern handled — close… | **Nurse or clinician** | Outcome (staff only) |  |
| `registration_update` | Registration updated… | Front desk, nurse or clinician | Outcome note (who / what) |  |

Intake reminders stop at **3** (a 4th is refused, HTTP 409); after that the next step is a phone call logged by a person.
The reminder cadence is NOT invented: reminders are sent when staff click (or the presenter simulates one). See the open questions in README.md.

### The eight scenarios (presenter: *Referral scenarios* card → "Load at start" / "Jump to key state")

| Scenario | Key state | Owner | Human step | Patient sees | Office sees |
|---|---|---|---|---|---|
| 1. Clean referral, complete records | Ready for appointment | Clinician (fit review), then Front desk | Clinician accepts the referral and confirms the attached MRI report was reviewed (one click). | Every line ticked and “You’re ready for your first visit”; the office will call to book. | One “Book the visit” task; every gate green. |
| 2. Referral missing records and imaging | Waiting on the imaging center and the referring office | Front desk | Front desk sends the requests (simulated fax) and confirms each arrival matches the patient; a clinician reviews the report or decides to proceed without images. | “Waiting on Lakeshore Imaging (fictional): MRI report, MRI images” with the date we asked and when we will check again. | Two records tasks in Waiting with follow-up dates; one-click “Mark received” when the fax arrives. |
| 3. Insurance needs prior authorization | Waiting on the insurer’s prior-authorization decision | Front desk (billing) | Staff record the insurer’s decision with a reference — the system never assumes an approval. A denial becomes a person-to-person conversation. | “Waiting on Sample Insurance Co. (fictional): approval for this visit” — never a predicted date. | Prior-auth task in Waiting with a follow-up date and a “Record the insurer’s decision” button. |
| 4. Patient never completes intake | 3 reminders sent (simulated), no response — phone-call task | Front desk | After the reminder limit the system stops texting and hands it to a person to phone; staff log each call outcome. | One next step: “Finish your intake form”, plus how many reminders we have sent. | Intake task back with its owner: “Stop texting. Phone the patient”, with call-outcome choices. |
| 5. Caregiver completes intake for the patient | Intake entered by the helper — waiting for the patient to confirm | Front desk | Answers entered by a helper count only after the patient confirms them (in the portal, or by phone with staff). | “Frankie Helper filled in the intake for you — please check it” with a one-tap confirm. | “Confirm helper-entered intake with the patient” task; it closes itself if the patient confirms in the portal. |
| 6. Referral that may belong elsewhere | Clinician fit decision (accept / ask / route elsewhere) | Clinician | Only a clinician can route a referral elsewhere, with a reason. The system never declines. A person then phones the patient. | “Our clinical team is reviewing your referral”; after a decision, “A team member will call you about next steps” (no reason shown in the portal). | Fit-review task with Accept / Ask the referring office / Route elsewhere; after routing, a front-desk call task. |
| 7. Red-flag symptom reported during intake | URGENT — 911 / call-the-office guidance shown, urgent nurse task | Nurse (backup: Dr. Yakel) | A nurse or clinician must phone the patient and record what happened before the urgent hold can be cleared. | 911 / call-the-office guidance the moment the box is ticked (before submitting), and again on Home. | URGENT task at the top of every queue view, owner Nurse, 2-hour internal deadline (placeholder). |
| 8. Surgery prep and post-op follow-up | Pre-op checklist: waiting on the primary-care clearance (automatic follow-up running) | Front desk + Clinician (nurse for post-op concerns) | A clinician records the consent discussion and reviews the clearance; a nurse phones the patient about any post-op concern. The system never gives medical advice. | A pre-op checklist showing what is done, who has each item and what we are waiting on; after surgery, short check-ins where “Something worries me” goes to a nurse. | Surgery checklist with owners and one-click updates; the clearance request is chased automatically (simulated); post-op concerns arrive as nurse tasks. |

### Automatic chasing (spotlight 2) — SIMULATED follow-ups, people step in only when stuck

Applies to referral-pipeline tasks of type `records_request`, `prior_auth`, `clearance_request`, `referral_info` while they are **Waiting** on another office or insurer.

1. When the follow-up date passes, the server sends an **automatic follow-up** (simulated fax or simulated insurer-portal message — nothing leaves this machine), logs `chase.sent`, counts it on the task (`chases`) and sets a new follow-up date **2 days** later. The task stays *Waiting*; nobody is asked to do anything.
2. After **2** automatic follow-ups with no answer, the next due date makes the task **STUCK**: *Waiting → Assigned* (system), `blocked_step` "STUCK: no answer from … after 2 automatic follow-ups (simulated)", a type-aware next step ("Phone …, then record …"), event `chase.stuck`. Stuck items sort right after urgent/overdue work in the queue and carry a red "Stuck — needs a phone call" chip.
3. The patient sees "We followed up automatically N time(s) (simulated) — nothing needed from you", and once stuck, "This is taking longer than expected, so a team member is following up by phone." No dates are predicted.
4. Presenter: *Referral scenarios* → "Follow-up date passes" (missing records, prior auth, surgery clearance) moves the clock for that scenario only.

`2` follow-ups and `2`-day gaps are **prototype placeholders — the office decides** (see README open questions).

### Fewer phone calls (spotlight 1)

Every status line in the portal names **what we are waiting on, who is handling it (team) and the next step**. Opening the status page while items are pending logs `status.viewed` (at most once per 10 minutes per patient). The office queue shows a **"Calls this portal may have saved"** card (`GET /api/o/calls-avoided`) that counts status views, automatic follow-ups, self-confirmed intake answers and check-ins answered in this demo's **fictional** data. It is labelled **EXAMPLE COUNTS ONLY** and says it is not a measured reduction in calls and says nothing about staff time or cost.

### Visit-ready summary for Dr. Yakel (spotlight 3) — DRAFT, needs clinician review

`GET /api/o/cases/{id}/summary` assembles patient, referral, records/imaging status, insurance, the patient's confirmed or corrected intake answers, the safety question and any open items. Outcome questionnaires (ODI, NDI, PROMIS — named only) are **not collected** in this demo; the summary says so. Every summary carries the label "DRAFT — assembled automatically … Needs clinician review. Not a clinical note." Only a clinician can mark it reviewed (`POST …/summary/review`, event `summary.reviewed`); a content hash shows "changed since review" if anything moves afterwards.

### Surgery pathway (scenario 8, spotlight 4) — pre-op checklist, clearance tracking, post-op check-ins

A case with `pathway = surgery` leaves the referral gates behind and is in state **surgery** until the (example) surgery date, then **postop**. The checklist items are **prototype placeholders; the office defines the real list**:

| Item | Label | Owner team | Who may mark it done | Patient reads (until done) |
|---|---|---|---|---|
| `date` | Surgery date confirmed | Front desk | Front desk, nurse or clinician | We will confirm your surgery date with you. |
| `consent` | Surgical consent discussion with the surgeon | Clinician | **Clinician only** | Your surgeon will go through consent with you in person. |
| `clearance` | Pre-op clearance from primary care | Front desk, then Clinician | **Clinician only** | We asked your primary care clinic for a pre-op clearance. |
| `labs` | Pre-op lab results | Front desk | Front desk, nurse or clinician | We are waiting for your pre-op lab results. |
| `insurance` | Insurance approval for surgery | Front desk (billing) | Front desk, nurse or clinician | We are checking whether your plan needs to approve the surgery. |
| `instructions` | Written pre-op instructions received (from the surgical team) | You | The patient (in the portal) | Your surgical team gives you written instructions. Tap below once you have them. |

* **Clearance tracking:** a `clearance_request` task is sent (simulated fax) to the primary-care office and auto-chased like records (above). "Clearance received" moves the checklist item to *received — needs review*; only a clinician signs it off.
* **Pre-op instructions:** the portal never shows instruction content. It asks the patient to confirm they have the written instructions from the surgical team (`POST /api/p/preop/instructions`). Instruction content is a clinic decision (see README "placeholder instruction slots").
* **Post-op check-ins:** scheduled on days 2, 7, 14 after surgery (placeholder — surgeon decides), sent as a simulated text plus a portal card. The patient picks *I’m doing okay* / *I have a question for a nurse* / *Something worries me — please call me* (a few words are required for question/concern). A **concern** creates an **urgent** nurse task (owner nina, backup yakel, 2 h internal deadline (Nurse)); a **question** creates a normal nurse task; emergency wording shows 911 guidance immediately and makes the task urgent. No advice is generated.
* **Missed check-in:** a check-in not answered within one day of being sent (placeholder rule) becomes `missed` and creates a `postop_missed` front-desk task: "Phone the patient".

### Red flags in the intake

Four example symptom checkboxes (plus emergency wording in the free-text answer) raise an **urgent** nurse task **when the draft autosaves**,
before the patient presses Send, and show 911 / call-the-office guidance immediately. Saving the same, already-reviewed symptoms again does not
re-raise the hold; a NEW symptom does. `MEDICAL COPY — symptom wording and guidance need Dr. Yakel's review.`

## Intake pre-fill (tell us once)

Each pre-filled item shows its **source** (for example "Referral letter from … (simulated fax — example data)") with a "Simulated source" tag, a plain-language **hint** and a **"Why we ask"** explanation. The patient only confirms or corrects; corrections are shown to staff side by side with the original. Help copy is example wording for the office to review.

## Not a clinical triage system

The wording lists in `server.py` (emergency, symptom/medication) only decide **where a request goes and what the patient is told immediately**. Anything uncertain goes to a person. The clinical escalation path must be owned by the care team; it is not live in this prototype. `MEDICAL COPY — needs Dr. Yakel review`.
