# preview19 — Inspection (step 0, written before any preview19 change)

Inspected: the preview18 code as copied into preview19 on Wed Oct 7, 2026 (~4:50 PM PT).
Everything here is a **prototype with fictional people and example data only**. Nothing is production,
nothing is HIPAA-compliant, and nothing is connected to a real clinic system.

## 1. What actually works (server-backed)

These run in `server.py` (Python standard library `http.server` + SQLite). They only work when the
server is running (`python3 server.py --port 8770`). Each one writes to or reads from the SQLite database,
so it survives a page reload and a server restart:

| Area | What is real in the prototype | Where |
|---|---|---|
| Sign-in | Fictional personas only (no passwords). The session is a signed token in an `HttpOnly; SameSite=Strict` cookie; page JavaScript never sees it. Roles: patient, caregiver (helper), office, clinician, admin. | `server.py` login/session, `/api/p/me` |
| Permissions | A helper only sees what the patient shared (scopes checked server-side on every call). Office/clinician actions are role-checked per task type. | `patient_scopes()`, `need()`, `do_action()` |
| Home status | `/api/p/home` computes the case state (`case_state()`), the checklist (`case_view()`), and the single next action (`pipeline_next_action()`) from database rows. | `p_home`, `case_view`, `pipeline_next_action` |
| Referral tracking | Fit review, records per sending office, MRI review, insurance, intake, safety hold, first visit. Each tracked item carries owner team, "last verified" time and source, and the next follow-up date. | `case_view()`, `tasks` table |
| Intake | Pre-fill comes only from DB rows (patient, referral, case). Server draft (`PUT /api/p/intake/draft`) is real save-and-return. Final submit (`POST /api/p/intake`) validates every field, requires an Idempotency-Key, and refuses a second submission (409 `already_submitted`). Helper-entered intake must be confirmed by the patient (`/api/p/intake/attest`). Red-flag answers raise an urgent task. | `intake_form`, `clean_answers`, `submit_intake_v2` |
| Messages / call-back | Messages, "Ask", and call-back requests create tasks in the office queue (deduplicated, idempotent). | `/api/p/messages`, `/api/p/ask`, `/api/p/callback` |
| Office queue | Task states, owners, transitions, outcome notes, follow-up dates, "next up". | `office.js`, `/api/o/*` |
| Surgery / post-op | Pre-op checklist items, patient "I have my written instructions" acknowledgement, scheduled post-op check-ins, concerns routed to a nurse task. | `surgery_view`, `/api/p/checkin`, `/api/p/preop/instructions` |
| Duplicate protection | `X-PS-Client` header required on writes; `Idempotency-Key` on submit-type routes (same key + same body replays, same key + different body = 422). | `dispatch` |
| Audit log | Append-only `events` table (DB triggers block update/delete). | `log()` |

## 2. What is simulated (looks real, is not)

| Simulated thing | How it is simulated |
|---|---|
| Faxes (records requests, arrivals, clearances) | Rows are written as "sent (simulated fax)". Arrivals happen only when the presenter clicks an event. No fax is sent. |
| Text messages / email (reminders, invites) | A background worker marks queued notifications "sent/delivered" by a **simulated vendor**. Nothing leaves the machine. |
| Insurance checks and prior auth | "Run check" sets a status; the result is invented example data. No insurer is contacted. |
| Automatic follow-ups ("auto-chasing") | The worker increments a counter and logs "simulated" chases. |
| Time passing | The presenter "days pass" control shifts dates in the database. |
| "Ask" answers | Keyword matching against a short fixed FAQ; anything else is handed to a person. It is not AI triage and not clinical triage. |
| Appointment availability | There is **no scheduling system**. Visits exist only when staff (or a presenter script) record one. |
| Clinical wording | Red-flag symptom wording and pre-op items are example copy pending Dr. Yakel's review. |
| `snapshot.html` | A single static file. A browser-side mock (`snapshot_mock.js`) replays responses recorded from the real server plus a small in-browser fake for the first persona. |

**`snapshot.html` cannot prove backend behaviour.** It has no server, no database, no sessions, no
permission checks, no idempotency, and no persistence beyond the open tab. Anything shown working
in the snapshot only shows what the screen looks like. Backend behaviour is proven only by the API
and UI test suites run against `server.py` (see `tests/`).

## 3. Files that control the patient experience

| File | Controls |
|---|---|
| `portal.html` | Page shell, header, tab bar, Content-Security-Policy (self-only, no inline styles). |
| `portal.js` | Every patient screen: Home (`renderHome`, `nextActionCard`, `pipelineCard`, `apptCard`, `reachCard`), intake wizard (`buildIntakeForm`), visits, records, messages, Ask, settings, helper sharing. |
| `shared.js` | `PS.api` (headers, idempotency keys), icons, text-size toggle, tab-bar fitting, demo banner. |
| `shared.css` | Design system (navy/cream/gold), type scale (18px body), touch targets, tab bar. |
| `server.py` → `p_home`, `pipeline_next_action`, `case_view`, `surgery_view` | What Home says, which single action is shown, and every checklist line (patient wording and office wording). |
| `server.py` → `intake_form`, `clean_answers`, `submit_intake_v2`, `build_summary` | What is pre-filled, what is required, how submission works, what the clinician summary says. |
| `snapshot_mock.js`, `build_snapshot.py` | The static snapshot only. |

## 4. Problems found during inspection (to fix in preview19)

1. **Home contradiction.** When nothing is needed from the patient, the first card says "Nothing needed
   from you right now" with a big "Message the team" button, while the appointment card below says
   "No visit is booked yet. Call (208) 770-3536 and we'll find a time with you" — even when records
   are still outstanding and the visit cannot be booked yet.
2. **Home is long.** Greeting, next-action card, tracker, appointment card, connected progress line with
   fax notes / owner / next step / last-verified for every item, contact card, links card.
3. **Office wording leaks to patients.** `case_view()` sends `office_text` (e.g. "Auto-chasing: 1 of 2")
   in the patient's `/api/p/home` payload. It is not shown, but it should not be sent.
4. **Confirmation is not tracked per field.** The intake stores `confirm: {field: ok|change}` inside the
   answers blob only. `build_summary()` labels a field "(confirmed by patient)" even when a **helper**
   confirmed it.
5. **No seeded "appointment booked" example** in the presenter scenarios (it can only be reached by
   clicking through the office screens).
6. **Intake** shows title, kicker, a 6-button step row, an indicator and an intro paragraph before the
   first answerable question; errors appear in one status line rather than next to the field; success
   auto-redirects to Home after 1.5 s.
7. **Mobile header**: the phone button is icon-only below 860px; settings and sign-out are separate
   icon buttons; the "Larger text" toggle does not say what it does at a glance.
8. **Tab bar** background is 97% opaque, so text scrolling underneath shows through.
9. **Demo explanations are repeated** (banner, sign-in page, pipeline fine print, records page,
   settings "What is real" card, intake footer).

## 5. Addendum (added after the preview19 changes): where each problem was fixed
Sections 1–4 above are unchanged from the step-0 inspection.
1. **Home contradiction.** Fixed: `#youdo` says either "No. Nothing is needed from you right now." or shows exactly one action. The contact options live in the separate "Need help?" card.
2. **Home is long.** Fixed: three-question layout, compact checklist, details collapsed. Home height at 390×844 is down 37–46% (`../preview19-shots/before-home-heights.json` vs `after-home-heights.json`).
3. **office_text leak.** Fixed in `server.py` `case_view` (stripped unless the viewer is office). Covered by `api_spotlight_test` and `api_v19_test` D-checks.
4. **Per-field confirmation.** Fixed: new `intake_fields` table, `field_status` in the intake API, and role-aware office summary wording.
5. **No booked example.** Fixed: `clean` scenario step `booked`.
6. **Intake.** Fixed: compact top, one progress indicator, inline errors with focus, review, and success/failure screens. No auto-redirect.
7. **Mobile header.** Fixed: labelled "Call us" and "Account" menu.
8. **Tab bar.** Fixed: solid background, body padding and safe-area insets. Hidden during intake and while the keyboard is open.
9. **Repeated demo text.** Fixed: one "About this demo" sheet. The DEMO bar and prototype line stay visible.

`snapshot.html` was rebuilt from preview19. It still **cannot prove backend behaviour**: in the snapshot, drafts, idempotency and per-field status are replayed or mocked in the browser.

## 6. Prompt A step 0 — the existing FAQ, message routing and triage (inspected Wed Oct 7, 2026 ~6:00 PM PT, before the assistant was built)
**What exists today (all server-side, in `server.py`):**
* **"Ask a quick question"** (Messages tab → `POST /api/p/ask`) is a keyword FAQ.
  * `triage()` runs regular-expression lists in a fixed order:
    1. `EMERGENCY` wording → an urgent nurse task plus the 911/office guidance.
    2. `CLINICAL` wording (symptoms, medicines, surgery…) → a nurse task and "a person will review it".
    3. `HUMAN_FIRST` (bills, approvals) → a front-desk task.
    4. Exactly one `FAQ` match → a canned answer with its source line. `@APPT@` is filled from the patient's real appointment row.
    5. Anything else (no match, or two FAQ matches) → a front-desk task ("I couldn't answer that confidently").
  * Unknown and clinical questions **create tasks automatically**.
* **Messages** (`POST /api/p/messages`): the patient picks a category.
  * `ROUTES` maps it to an owner, a backup, an internal deadline and a team label.
  * Clinical wording in any category is re-routed to "Medical question" (nurse). Emergency wording uses `URGENT_ROUTE`.
  * Identical text within 20 s is suppressed as a duplicate. The request needs an idempotency key, and the server replays the same key.
* **Live emergency warning:** `/api/p/rules` shares the emergency patterns so the page can show 911 guidance while the person types. The server checks again on submit.
* **Static snapshot:** `snapshot_mock.js` re-implements the Ask/FAQ in the browser for the Pass 1 demo patient only.

**Three different things, and which one this prototype is:**

| | What it means | In this prototype? |
|---|---|---|
| **Scripted responses** | Fixed text or templates chosen by deterministic rules (keywords, record fields) and filled from the database. The same question and data always give the same answer, and every path can be tested. | **Yes.** The existing Ask/FAQ and the new "Ask about your visit" demo assistant are both scripted. |
| **Simulated AI** | Scripted output dressed up to look like a model (chat bubbles, "typing…", a persona, free-form phrasing). | **No, deliberately.** The assistant is labelled "Demo assistant: scripted answers from your portal data, no AI model connected" and says it is not a person. |
| **Actual model integration** | Calling a language model (an API key, an SDK or an external endpoint). In practice that also needs a vendor agreement for health data, data-flow review, injection defences, evaluation and monitoring. | **No. None exists.** No API keys, SDKs, credentials or external calls were added. Adding one is a paid service plus credentials, which Tyler must approve first. |

**Rules the new assistant follows:**
* **Its sources** are the signed-in patient's own structured records (case/checklist rows with last-verified time and source, appointments, check-ins, approved-content records).
* **Messages and documents** are source material only. Their text is never treated as instructions.
* **It creates nothing on its own,** except the existing urgent route when emergency wording is used. Drafted messages are sent only after the patient reviews and confirms them, through the existing message system.

**Added after the 6:05 PM PT steering note (AWS Bedrock later, not now):**
* Every assistant answer now goes through one server-side interface, `assistant_provider.py` → `provider.answer(AssistRequest)`.
  * `ScriptedProvider` is **active**. It only returns the answer the server already built from this patient's records (or the scripted office FAQ, or "unknown").
  * `BedrockProvider` is a **stub**. It raises `NotConfigured` and its docstring lists what a real link needs (IAM role or server-side credentials only, never in the browser; region; model ID; a signed AWS BAA and HIPAA-eligible configuration; a Bedrock Guardrail; logging and retention decisions; Tyler's approval). No boto3, no credentials, no network code, no new dependency.
  * Selected by `PS_ASSISTANT_PROVIDER` (default `scripted`). With `bedrock` the server answers honestly "the assistant isn't available" plus a hand-off; the red-flag and medical-refusal rules still work because they run before any provider.
* The server owns safety around the provider: access (session patient only) → **pre-rules** (red flag → existing urgent/911 route; medical/out-of-scope → refusal; the provider is not called) → **grounded context** (`assist_context`: verified facts with sources, approved content, messages/documents as status/title only, marked untrusted) → provider → **post-rules** (`assist_post_check`: allowed kinds only; facts must be in the context; links must be this patient's; approved wording must match exactly; no advice/reassurance/imaging/surgical-suitability wording, no injection echoes, no red-flag wording; anything failing → refusal + clinical hand-off, logged as `assist.output_blocked`).
* The UI label is unchanged: "Demo assistant: scripted answers from your portal data, no AI model connected".

## 7. Prompt B step 0 — the existing pre-op / post-op flow (inspected Wed Oct 7, 2026 ~6:20 PM PT, before changing it)
**What existed (server.py `PREOP`, `surgery_view`, `run_surgery`, `answer_checkin`, `p_checkin`; portal.js `checkinForm`, `checklistRows`):**
* A six-item pre-op checklist (date, consent, clearance, labs, insurance, written-instructions acknowledgement), each with an owner team. One fictional surgery scenario (Harper) with steps start / key / postop / postop_concern.
* `surgery_view` sent a `ready` flag (all items done) to the patient; the portal tracker used it to move "Surgery" to the current step. **Problem:** a complete paperwork list was being turned into a readiness signal.
* Procedure facts were only "Spine surgery (example)" + a date; nothing said whether the date had been confirmed, and nothing said "not added yet" for surgeon / place / arrival time.
* No approved pre-op/post-op instruction content existed; the Visits tab's general office information was the only "instructions".
* Post-op check-in: three choices, the third read "Something worries me — please call me"; the hint said "A nurse reads this during office hours".
* **Promises with no configuration behind them:** `p_checkin` returned "Thank you. A nurse will phone you."; the check-in prompt said "Anything worrying goes to a nurse, who will phone you"; missed check-ins said "the office will call you".
* `answer_checkin` stripped the patient's note (not verbatim) and used two hard-coded levels (question → nurse task, concern/emergency wording → urgent task). An "I'm doing okay" answer with worrying words created no task.
* The portal showed the server message as the only confirmation: no reference, no record of what was sent, no history for the patient (notes were office-only).
* 911 guidance on the check-in was a single button next to Send, plus the live emergency-wording warning, whose text claimed "We have still sent it to a nurse" **before** anything was sent (shared with Messages).

**Where each was fixed:** see README "Prompt B — before / after surgery".

## 8. Prompt C step 0 — the office workspace (inspected Wed Oct 7, 2026 ~7:15 PM PT, before changing it; the pre-change copy is in checkpoints/preview19-pre-office/)
**What existed (server.py `o_queue`, `task_actions`, `do_action`, `build_summary`, `act_send_reminder`; office.js `loadQueue`, `chipsFor`, `COLS`, `renderSummary`):**
* **Priority bug (confirmed).** `o_queue` sorted urgent first, but **Do next** (`next_up`) was picked only from the signed-in user's *own* tasks. Pat (front desk) owns the "Ready for appointment — book the visit" task, while urgent items are routed to Nina (nurse). So Pat's Do next card offered "Book the visit" while an emergency-wording message or red-flag intake for the **same patient** was open and unresolved. Nothing held the booking.
* **Urgent items could be hidden.** The "Mine", "Waiting", "Referral pipeline" and "Resolved" filters dropped urgent tasks owned by someone else. There was no pinned area.
* **Role enforcement was partial.** Resolve rules (level 1 nurse/clinician, level 2 clinician) were enforced, but a front-desk or admin user still got the urgent task's quick actions (log contact, add note, transition, reply, reassign, including reassigning it to themselves). Nothing on screen said they should not act.
* **Cards were crowded.** Each queue row repeated status, priority, team, origin and "simulated" chips, plus reason and next-step text. There was no single "what needs attention / who owns it / when / one next action" line, and no "Unassigned" wording.
* **Columns.** The board columns were status-based (Received/Assigned/In progress/Waiting/Stuck). The requested groups (needs action now / waiting / overdue or blocked / completed) did not exist.
* **Reminders.** Intake reminders were a counter on the case (`intake_reminders`). The automatic chase and the staff "send reminder" button incremented it separately, with no record per patient + requirement and no opt-out. Appointment-confirmation notifications had no reminder rule at all.
* **Same record.** The patient and staff views were already computed from the same task/case rows (`case_view`, `patient_task`, `staff_task`), with no separate patient copy. But no test proved it across patients.
* **Visit-ready summary.** It was labelled "DRAFT". Sections mixed referral facts and intake answers in one list, intake answers were paraphrased into the same columns as record facts, and most facts had no source. Missing items appeared only as "Still open".
* **Queued gaps:** the patient Home records card showed `last_verified_source` = "Pat · Front desk" (a staff name) next to the date. Non-surgery promises remained: "A team member will call you about next steps" (routed), "will call you to talk about options" (insurance denied), "We will call you to book a time" / "our front desk will call you to book" (ready). The Messages tab still had the old "Ask a quick question" card beside the new "Ask about your visit" assistant.

**Where each was fixed:** see README "Prompt C — office workspace". Summary: server-side groups + pinned urgent + urgent-first Do next (P1–P3); `urgent_guard` on act/assign/transition/reply, and the owner of an urgent task must be a nurse/clinician; booking held while the same patient has an open urgent item; one-card layout with "More" details; `reminders` table with a unique key per patient + requirement, opt-out, staff take-over and limit; summary split into verbatim statements / extracted facts with sources / missing-or-conflicting flags; staff names removed from the patient side; call promises replaced with the phone number unless the practice sets `patient_call_expectation`; the Ask card merged into the assistant.
