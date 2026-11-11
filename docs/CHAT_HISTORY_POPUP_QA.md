# Floating chat history: delivery gate

Result: PASS. Direction: existing teal studio, ENERGY 2 / RHYTHM 2 / MOTION 1,
with one history launcher and a native modal list. No backend changes.

- R-03 PASS: desktop/mobile layout and overflow checks passed; a 100-item list
  scrolls inside the dialog while footer controls remain visible.
- R-23/R-24 PASS: no assets or destinations added; each list item opens its actual
  existing conversation through the existing endpoint.
- R-25/R-34 PASS: light/dark text contrast passed at 360 and 1440 pixels for the
  popup, including a separate 100-item fixture.
- R-26 PASS: launcher opens; a history item loads its conversation and closes;
  refresh reloads; delete asks for confirmation and updates the list/empty state.
- R-27 PASS: loading, empty, API-error and disabled states are visible. A refresh
  error was exercised inside the popup, with prior items preserved for recovery.
- R-32 PASS: native modal focus containment; Enter opens, Escape closes, the close
  button and backdrop dismiss; focus returns to the history launcher.
- R-33 PASS: HTML/CSS/JavaScript edited directly, without source-rewriting scripts.
- R-35 PASS: full browser regression passed 114 layout/contrast checks and 26
  interaction groups, without unexpected console errors. Evidence is recorded in
  `storage/ui_qa_history_popup_delivery/report.json` with popup screenshots.
- R-37 PASS: purpose, placement, theme and interaction direction in `DESIGN.md`.
- R-39 PASS: labelled native dialog, named buttons, status announcement, visible
  focus, 44px targets and existing reduced-motion handling.
- R-40 PASS: no remote assets, libraries, media or performance claims introduced.
- R-12 PASS: the bounded dialog shadow marks a temporary layer over the conversation.
- C-1/C-2/C-3 PASS: the single launcher reduces persistent controls; the list and
  footer each perform actual conversation operations.
- C-4/C-5 PASS: both themes, keyboard, mobile, errors and empty history exercised;
  fixtures explicitly labelled and conversation titles rendered with textContent.
- Remaining shared visual gates retain the evidence in `REFERENCE_REDESIGN_QA.md`:
  no new decorative effects, typography, marketing copy, statistics or illustrations.

Additional check: 100 conversation titles, including an HTML injection fixture,
render as text. Selecting the final item works, its dialog closes, and an API
error is displayed inside the popup. Screenshots are under
`storage/ui_qa_history_popup_focused`. Visual inspection included the mobile dark
popup. Browser tests used fixture APIs and sent no AI or publishing requests.
