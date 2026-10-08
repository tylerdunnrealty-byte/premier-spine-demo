# Streamlining the office side of a spine clinic: brainstorm

**Premier Spine, Coeur d'Alene, ID. This is a DEMO brainstorm. All examples are fictional, and nothing here describes Premier Spine's real process.**

This document walks through the patient journey at a spine clinic. For each step it covers four things:

* the work that usually lands on the front desk, nurses and clinicians;
* how a patient portal plus some background automation could take part of that work off staff;
* what a person still has to review;
* whether the preview17 demo already shows it (**BUILT**, **PARTLY BUILT** or **FUTURE IDEA**).

Ground rules for reading it:

* **No savings figures.** We have not measured Premier Spine's call volume, staff time or costs, so this document gives no time, cost or call-reduction numbers. The demo's "calls this portal may have saved" card counts events in fictional data only and is labelled *example counts only*.
* **Simulated outside contact.** Everything that would reach another organisation is simulated in the demo and labelled that way. That includes faxes, insurer portals, texts, email and labs. Nothing is sent anywhere.
* **The clinic owns clinical content.** Wording about symptoms, red flags, surgery instructions and post-op care has to come from or be approved by Dr. Yakel and the care team. The demo leaves slots for this content and does not write it.
* **Burden descriptions are general.** The "manual burden" notes describe common spine-clinic work. They are not an observation of this office. The office should correct them.

Status key:

* **BUILT**: you can click through it in preview17. The presenter tour or a scenario shows it.
* **PARTLY BUILT**: the demo covers some of the step, and the rest is a future idea.
* **FUTURE IDEA**: not in the demo.

---

## 1. Referral intake: BUILT
* **Manual burden today:** Referrals arrive by fax, e-referral or phone and are often incomplete. Someone keys in the demographics, works out whether the referral fits the practice, and phones the referring office about anything missing. Patients call to ask whether the referral arrived.
* **How to streamline it:**
  * Each referral becomes one case with explicit gates (fit, records, insurance, intake, safety, identity) and a computed state.
  * The clinician sees a fit-review task. They can accept, ask the referring office a question (sent as a simulated fax, then auto-chased) or route the patient elsewhere with a reason.
  * The patient sees "we have your referral" and what happens next, so there is no need to call.
* **Still needs a person:** Accepting, declining or routing a referral is a clinician decision; the system never makes it. Someone has to check the referral really belongs to this patient.
* **In the demo:** Scenarios 1 and 6 (*not a fit / route elsewhere*). The fit-review buttons are clinician-only.

## 2. Records and imaging retrieval: BUILT
* **Manual burden today:** The office faxes requests for office notes, MRI reports and images, waits, re-faxes and phones. Then it has to work out what arrived and whether the images are actually loadable. This is one of the most common reasons a first visit slips.
* **How to streamline it:**
  * Each missing item becomes a records request with an owner and a follow-up date.
  * **Automatic chasing:** after the follow-up date, the system sends up to 2 simulated follow-ups, 2 days apart. These numbers are placeholders. Staff only see the task again when it is **stuck**: they get a red "Stuck — needs a phone call" chip with the next step written out.
  * Report and images are tracked separately.
  * The patient sees which facility we are waiting on and that we are handling it.
* **Still needs a person:**
  * A clinician reviews the radiology report.
  * A clinician decides whether to go ahead without images, and a reason is recorded.
  * Staff confirm that a received record matches the patient.
  * Stuck items need a phone call.
* **In the demo:** Scenario 2 (*missing records*) and presenter spotlight 2 ("Follow-up date passes").

## 3. Insurance verification and prior authorization: BUILT (both simulated)
* **Manual burden today:** Eligibility checks, working out whether the plan needs prior authorization, submitting it, then repeatedly checking insurer portals or phoning. Patients call to ask whether they are approved.
* **How to streamline it:**
  * A simulated eligibility check records whether prior auth is needed.
  * If it is, a prior-auth task waits on the insurer and is auto-chased the same way as records (simulated insurer-portal messages).
  * The insurance gate passes only when staff record the decision **with a reference number**.
  * The patient sees "waiting on your insurance plan — nothing needed from you."
* **Still needs a person:** Submitting the authorization, reading the insurer's answer, and handling denials or peer-to-peer reviews. The demo contains no real insurer list and no plan rules.
* **In the demo:** Scenario 3 (*prior auth*) and spotlight 2.

## 4. Scheduling: PARTLY BUILT
* **Manual burden today:** Phone tag to book, confirm and reschedule. The visit is sometimes booked before records or authorization are in, and then has to be moved.
* **How to streamline it:**
  * When every gate passes, the case becomes *Ready for appointment* and the system creates exactly **one** "Book the visit" task for the front desk.
  * The patient can confirm an appointment in the portal (Pass 1).
* **Still needs a person:** Choosing the slot. The office also has to decide whether to book before or after the gates pass (open question).
* **Future idea:** Self-scheduling into slots the office releases, a waitlist and cancellation fill, and reminder cadence. No reminder schedule is invented here.

## 5. Intake forms: BUILT
* **Manual burden today:** Patients fill in long paper or PDF forms that repeat what the referral already says. Staff then re-key the answers and phone about blanks.
* **How to streamline it:**
  * **Tell us once.** The form arrives **pre-filled** from the referral and registration: name, date of birth, phone, referring clinic, reason, insurance, imaging facility, and listed medicines and allergies.
  * The patient only confirms or corrects each item. Corrections show to staff side by side with the original.
  * Every pre-filled item shows its **source**, labelled *Simulated source*, plus a plain-language hint and a "Why we ask" explanation.
  * A caregiver can fill it in, but the answers only count once the patient confirms them.
  * Drafts autosave, and reminders stop after 3. After that the next step is a phone call.
* **Still needs a person:** Office review of the help wording. Staff follow up when someone never completes intake.
* **In the demo:** Scenarios 1, 4 (*never completes intake*) and 5 (*caregiver*), and spotlight 3.

## 6. Outcome questionnaires (for example ODI, NDI, PROMIS): FUTURE IDEA
* **Manual burden today:** Questionnaires are handed out on paper at check-in, scored by hand or re-keyed, and often missed at follow-ups.
* **How to streamline it:** Send the questionnaire the clinic chooses with the intake and again at set follow-up points. Score it automatically and show the trend in the visit summary.
* **Still needs a person:**
  * The clinicians choose the instruments.
  * Someone checks the **licensing and permitted use** of each instrument. Some are copyrighted or need permission.
  * Clinicians interpret the scores.
* **In the demo:** **Not collected.** The questionnaires are only named here. The visit-ready summary says outright that they are not collected in this demo.

## 7. Consent: PARTLY BUILT
* **Manual burden today:** Paper consent forms (general, financial, surgical) get signed, scanned and filed, and sometimes go missing on the day.
* **How to streamline it:**
  * The surgery checklist has a "Surgical consent discussion with the surgeon" item that **only a clinician** can mark done.
  * The helper (caregiver) flow records what the patient shared and lets the patient stop sharing.
* **Still needs a person:** The consent discussion itself, and any legally required signature process.
* **Future idea:** E-signature for general and financial consents, with the wording supplied by the practice. No consent text is written in the demo.

## 8. Day-of check-in: FUTURE IDEA
* **Manual burden today:** Clipboard forms, copying the insurance card and ID, confirming demographics, and the front-desk queue at the start of clinic.
* **How to streamline it:** Pre-arrival check-in from the phone: confirm details that are already verified, upload a card photo, and an "I'm here" button. The visit summary is already assembled.
* **Still needs a person:** Identity check at the desk, and handling anything flagged.
* **In the demo:** Not built. The pieces it would reuse are the confirmed intake and the visit summary.

## 9. Treatment pathways: PT, injections, surgery: PARTLY BUILT (surgery only)
* **Manual burden today:** Each pathway has its own paperwork, referrals out, authorizations, scheduling and follow-up calls.
* **How to streamline it:** One case with a pathway-specific checklist, showing owner, status and next step for each item, and the same "waiting on / who / next" view for the patient.
* **Built:** The **surgery pathway** (scenario 8, spotlight 4):
  * a pre-op checklist covering date, consent, primary-care clearance, labs, insurance approval and written instructions received;
  * clearance tracking with automatic chasing;
  * post-op check-ins.
* **Future idea:** PT referral-out tracking (sent, scheduled, attended), and injection pathways (authorization, pre-procedure instructions, driver arranged, follow-up).
* **Still needs a person:** Every clinical decision, and the content of every instruction.

## 10. Pre-op clearance: BUILT (simulated)
* **Manual burden today:** Fax the primary-care office, wait, re-fax, phone, then check that the clearance actually covers what the surgeon needs. A missing clearance near the date causes cancellations.
* **How to streamline it:**
  * A clearance-request task is sent (simulated fax) to the fictional primary-care clinic and auto-chased.
  * When it arrives, the checklist shows *received — needs review*, and **only a clinician** can sign it off.
  * The patient sees "We asked your primary care clinic for a pre-op clearance" and who is following up.
* **Still needs a person:** Clinician review of the clearance contents, and the phone call when it is stuck.
* **In the demo:** Scenario 8 (key state) and spotlight 4.

## 11. Post-op follow-up: BUILT
* **Manual burden today:** Nurses phone patients after surgery, play phone tag, and log the calls. Concerns arrive at random times by phone.
* **How to streamline it:**
  * Check-ins are scheduled (days 2, 7 and 14 as placeholders; the surgeon decides) and sent as a simulated text plus a portal card.
  * The patient answers *I’m doing okay*, *I have a question for a nurse* or *Something worries me — please call me*. A few words are required for a question or concern.
  * Routing:
    * **Concern** creates an **urgent nurse task**.
    * **Question** creates a normal nurse task.
    * Emergency wording shows 911 guidance immediately.
    * A **missed** check-in (placeholder rule: unanswered for a day) creates a front-desk "phone the patient" task.
* **Still needs a person:** Every response to a concern or question. The system gives **no clinical advice**.
* **In the demo:** Scenario 8 (*postop* and *postop_concern* steps) and spotlight 4.

## 12. Results (imaging, labs): PARTLY BUILT
* **Manual burden today:** Calls asking "are my results back?", results that sit unreviewed, and calls back to explain them.
* **How to streamline it:**
  * Built: a radiology report must be reviewed by a clinician before the records gate passes, and pre-op labs appear on the checklist.
  * Future idea: release reviewed results to the portal with a clinician note, and a "results reviewed" status so patients don't need to call.
* **Still needs a person:** Clinician review and the decision on what to release and when.

## 13. Prescription refills: PARTLY BUILT
* **Manual burden today:** Refill calls and pharmacy faxes, chart look-ups, and getting clinician sign-off.
* **How to streamline it:**
  * Built (Pass 1): a portal message in the *prescription refill* category becomes a nurse task with an owner, a backup and a deadline. The patient is told it went to a nurse and to call if they are running out soon.
  * Future idea: a structured refill request (medicine, pharmacy, last dose) pre-filled from the medication list.
* **Still needs a person:** Every refill decision. Controlled-substance rules are a clinic policy matter.

## 14. FMLA and disability paperwork: FUTURE IDEA
* **Manual burden today:** Forms arrive from employers and insurers. Someone has to fill in dates and restrictions from the chart, get a clinician signature, chase the patient for missing pages, and field repeated "is my form done?" calls.
* **How to streamline it:** The patient uploads the form and gets a tracked task with a status they can see. Known fields (visit dates, surgery date) are pre-filled. The task is auto-chased if pages are missing.
* **Still needs a person:** All medical content and restrictions, plus the clinician signature. Any form fees are the office's decision; none are shown.

## 15. Billing questions: PARTLY BUILT
* **Manual burden today:** Calls about statements, insurance denials and payment plans, often misrouted to clinical staff.
* **How to streamline it:**
  * Built (Pass 1): a portal message in the *bill or insurance question* category becomes a front-desk task with an owner and a deadline. The patient sees its status.
  * Future idea: show the insurance-decision status already tracked in the case (step 3) so patients don't have to ask.
* **Still needs a person:** Every billing answer. The demo shows **no prices**.

## Cross-cutting pieces (BUILT)
* **Fewer phone calls (spotlight 1).** Every status line tells the patient what we are waiting on, who at Premier Spine is handling it, and the next step. The office queue shows a "Calls this portal may have saved" card, labelled **example counts only** and counted from fictional demo data. It is not a measured reduction.
* **Visit-ready summary for Dr. Yakel (spotlight 3).** It is assembled from the referral, records status, insurance and the patient's confirmed intake. It is labelled **DRAFT — needs clinician review**, only a clinician can mark it reviewed, and it flags any change made after review.
* **Red-flag routing.** Example symptom checkboxes and emergency wording raise an urgent nurse task and show 911 or call-the-office guidance. This copy (`MEDICAL COPY`) needs Dr. Yakel's review.
* **One work queue.** Every task has an owner, a backup, a deadline and a written next step. "Do next" buttons replace hand-picked statuses, and urgent, overdue and stuck items sort first.

## What was built in this pass (highest value first)
1. Automatic chasing of records, prior auth, clearance and referral questions, with a stuck → phone-call handoff (simulated).
2. A patient status page with "waiting on / who's handling it / next step", plus the example-counts calls card.
3. Pre-filled intake with simulated-source labels, hints and "Why we ask".
4. The visit-ready summary draft with clinician review.
5. The surgery pre-op checklist, clearance tracking and post-op check-ins routed to a person.

## Biggest future ideas (not built)
* Outcome questionnaires, once the clinicians have chosen them and licensing is confirmed.
* Day-of check-in.
* Results release.
* Structured refills.
* FMLA and disability forms.
* PT and injection pathways.
* E-consent.
* Self-scheduling.
