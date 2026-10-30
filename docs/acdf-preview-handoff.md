# ACDF education preview — clinician and design review required

## Scope
First batch only: sharper homepage supporting copy and care philosophy; compact two-entry explorer; one directly shareable public ACDF guide. Preserve existing headline, navy/cream/gold styling, photographs, symptom explorer and unrelated content. No account, portal, patient input, telemetry, API, backend, or build dependency added. Rejected neck wizard remains untouched. Do not merge or deploy until owner reviews.

## Source / maintenance
Base main: ea9176d0beb1c8b71e4befeef0439124671e0021. Guide source lives in procedures/acdf/index.html; styling and minimal state switching in sibling files. Native details exposes optional depth; all illustrations remain readable without JavaScript, controls enable only after initialization. Print presents all states; reduced motion removes smooth scrolling.

Clinical research reviewed October 2026 (not clinician approval):
- https://www.orthoinfo.org/treatment/cervical-radiculopathy-surgical-treatment-options/
- https://www.aans.org/patients/conditions-treatments/cervical-spine/
- https://www.uclh.nhs.uk/patients-and-visitors/patient-information-pages/single-level-anterior-cervical-discectomy

## Before publication
- Yakel signs off anatomy diagrams, indications, alternatives, risks, recovery questions and practice copy. This draft is not consent or individual advice.
- Confirm implant/graft models, current manufacturers, image rights and actual technology workflow before adding specific products. No robotic ACDF claim is made. Existing homepage robotic-surgery service wording and biography outcome-frequency statements are legacy assertions, not verified by this batch; confirm with Yakel.
- Choose next procedure only after reviewing this experience. No empty future-procedure tabs shipped.
- Owner approves isolated preview/publication separately; main remains unchanged.

## Checks
13 existing Python checks, existing Node symptom state suite, and new Node ACDF state suite pass. JS syntax checked. Independent code review checked unique IDs, static anchors, image-byte preservation, no forms and view-state selection. Clinical research review corrected wording and reviewed generic SVG arrangement, not a substitute for physician review.
Managed local browser verified homepage-to-guide navigation and goal-view switching at narrow viewport. Further desktop/mobile device and assistive-technology checks needed. Remote logo/favicon paths exist; local binary download is unsupported by GitHub connector, so local preview logo is missing rather than a changed asset. No image bytes are modified.

Run from repo root:
python -m unittest discover -s tests
node tests/symptom_state.test.cjs
node tests/acdf_state.test.cjs
node --check procedures/acdf/guide.js
