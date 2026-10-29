# Existing symptom section: focused polish

Base: `main` at `e15ce38dfa0d30c111990ec8cf235fe2296a4aff`.
Branch: `codex/dot-symptom-polish`. Shared coordination: issue #1.

## Scope

Preserve the existing homepage layout, four choices, 3D spine, colors, hero, contact/portal demo behavior, and photographs. This does not revive the rejected separate neck guide.

- Clearer instruction and fixed “Call our team” action.
- Readable sentence-case 1rem panel headings/body/lists, calmer effects and 44px close/area controls.
- Replace the pain slider and severity-dependent marketing messages with three questions to discuss at a visit. No scoring, data capture, diagnosis or treatment algorithm.
- Mobile dialog naming, initial/repeated navigation scroll reset, Shift-Tab containment from heading, Escape/focus restoration, canceled delayed focus after rapid dismissal, responsive dialog/region semantics.
- Keep single-scroll mobile sheet, emergency guidance, disclaimer and call CTA.
- Stop cursor-driven provider-photo translation to avoid fractional resampling. Every image data URI remains byte-for-byte unchanged; no pixel retouching, upscaling, artificial sharpness or recropping.

## Photo findings

Hero sources: Yakel 986x1332, Sarah 1006x1344, plus responsive smaller variants. At the existing maximum 600 CSS px height these are sufficient for approximately 2x display. Team portraits are 640x800, adequate for their current 248x310 maximum display. Higher device pixel ratios may still show limits. Lake CTA image is 1122x1402 and can be displayed 880 CSS px wide on tablet: its ~1.28 source pixels per CSS pixel is not fully 2x crisp. No better original was found in either branch; request the original higher-resolution lake photograph rather than inventing detail or changing the crop. Existing photo comments disclose digitally composited coat logos and require practice approval; this patch does not alter them.

## Verification

Run from repository root:

```sh
python -m unittest discover -s tests -v
node tests/symptom_state.test.cjs
```

14 structural/syntax tests pass (9 existing, 5 new). Node minimal DOM-stub regression passes five content states, exclusive pressed selection, scroll resets, mobile semantics, title Shift-Tab loop, Escape/return focus, rapid close, breakpoint changes and invalid state. All inline executable scripts pass Node syntax checks. These are not real browser or screen-reader tests.

Not yet verified: candidate desktop/mobile rendering, physical iPhone/Safari, screen reader behavior, actual telephony. The cloud browser cannot reach the workspace localhost. Before merging, browser review must cover the four choices plus hand/wrist back-link, text wrapping, panel scroll to warnings, keyboard cycle/dismiss/reopen, narrow/short viewport, desktop-to-mobile resize, and unchanged hero/team photos. GitHub Pages deploys main; this draft branch is not a deployment.

All existing medical education remains draft and needs Dr. Yakel's review. No new medical claims were introduced. Nothing here verifies clinical accuracy, legal/privacy compliance, appointment integrations or response times.
