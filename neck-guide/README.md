# Premier Spine: neck field-guide prototype

Review-only standalone experience. **Not approved for live publication.**

## Scope

- `neck-guide/index.html`, `guide.css`, `guide.js`: four-step educational neck guide and printable visit-preparation checklist.
- Existing homepage, portal demo, and `portal-source` are unchanged.
- Navy / cream / muted-gold palette and serif headings match the established site. System fonts keep the prototype entirely self-contained.
- All choices are optional. Goal/question IDs live in JavaScript memory only, with no storage, analytics, requests, API, authentication, or submission.
- Nothing diagnoses a condition, assigns severity, recommends treatment, or creates a clinical record.
- Print invokes the device print dialog. The checklist is printable without making selections. Print CSS isolates the checklist even if the browser print command is used from another step.

## Review

Open `index.html` from a local checkout or serve the repository with a simple static server; visit `/neck-guide/`. The `../` home link assumes the repository root retains the existing homepage.

Before publication:
1. Dr. Yakel / Sarah approve anatomy wording, schematic illustration, question wording, preparation details and safety copy. “Clinical review pending” must not be removed without that approval.
2. Review actual desktop and mobile rendering, native print/PDF output, keyboard navigation and a screen reader. No browser visual QA has been claimed for this revision.
3. Tyler approves the experience and any future homepage integration or deployment.
4. Confirm office details, appointment flow and live publication placement. No email or submission integration exists here.

## Content sources

Anatomy is grounded in AAOS OrthoInfo:
- https://www.orthoinfo.org/diseases--conditions/neck-pain/
- https://www.orthoinfo.org/diseases--conditions/cervical-radiculopathy-pinched-nerve/

Visit-preparation general reference:
- https://www.ahrq.gov/questions/be-engaged/index.html

The SVG is deliberately schematic, not to scale, with seven vertebrae and no disc between C1 and C2. Many structures are omitted. It must not be interpreted as a scan or used to localize symptoms. Contacts match the existing public homepage.

## Tests

From the repository root:

```
node --check neck-guide/guide.js
node neck-guide/tests/state.test.cjs
python3 neck-guide/tests/structure_test.py
```

The test uses a small dependency-free DOM contract stub, **not a real browser**. It covers empty/selected summaries, multi-select/deselect, forward/back/skip, active progress, focus invocation, reset, bounds and print invocation. It does not establish rendered appearance, browser focus/scroll behavior, assistive-technology support, contrast conformance, or print pagination. Those remain browser/manual review gates.

No dependencies or build step. No live deployment from this branch is requested.
