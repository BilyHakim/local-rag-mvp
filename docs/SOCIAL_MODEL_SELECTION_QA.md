# Social Media model selection QA

Date: 2026-11-06. Anti-slop: during (session override).
Scope: text model selection in Social Media, including creation and revision.
Direction: existing editorial workspace; ENERGY 2 / RHYTHM 2 / MOTION 1.

Compact placement refinement: the model select now shares the secondary action
row with "Tulis tanpa AI", below the primary generation button. It grows from
170px to a maximum 240px group width and wraps when space is insufficient.
Refresh uses a named 44px icon button. The same fixture regression was rerun:
50 layout/contrast checks and 16 interaction groups, light/dark at all four widths.
Evidence for the refinement: `storage/qa/social-model-compact/report.json`.

## Verification

- Backend: `python -m pytest -q`, 142 passed.
- UI: `scripts/check_workspace_ui.py`, PASS, 50 layout/contrast checks and
  16 interaction groups using fixture APIs, with external requests blocked.
- Widths: 360, 768, 1024, 1440px, light and dark themes. No horizontal overflow
  or unexpected console errors. Desktop light and mobile dark screenshots inspected.
- Model text contrast: white on #086288 = 6.75:1; #173f50 on white = 11.27:1.
- Native select supports keyboard selection; refresh preserves its choice.
- Create sends `model-lain`; revision sends `model-uji`; catalog failure sends
  null for the server default. Empty catalog, visible error and retry checked.
- API tests verify selection on creation/revision, default, rejection of unknown
  models, and context restoration after success and provider failure.
- Existing click-through also covers manual drafts, image upload/preview, editing,
  approval, scheduling/cancellation, publishing/reconciliation, planner, and new draft.
- Evidence: `storage/qa/social-model-selection/report.json` and screenshots.
- Live provider compatibility and paid generation were not exercised.

## Delivery gate

- PASS Hard Gate, R-02/03/17/18/23/24/36/38: no new assets, fabricated claims,
  navigation, or decorative content; checked layouts have no horizontal overflow.
- PASS R-25: automated text contrast checks and measured new color pairs above.
- PASS R-26/27: select and refresh work; loading, empty, error and retry states
  are implemented and exercised; fallback generation remains available.
- PASS R-28/33: no FAQ or source-rewriting script added; changes are in source.
- PASS R-32/34/35/39: native labelled field, status association, keyboard operation,
  visible inherited cream focus, 44px controls, both themes and recorded click-through.
- PASS R-37/40: existing DESIGN.md direction extended before completion; no new
  media, dependencies, animation or blocking scripts. Web Vitals not measured.
- PASS Purpose Gate, R-01/04/06/07/08/09/10/12/13/14/19/22: reuse palette,
  system typography and secondary button; no new decorative techniques. The
  placement and flexible width serve the brief workflow, recorded in DESIGN.md.
- PASS Liveliness: retain declared dials, brief/result hierarchy, cream primary
  action, teal studio identity and structural form spacing.
- PASS Craftsmanship and Quality Locks, C-1..C-5 and R-05/11/15/16/20/21/29/30/31:
  scoped functional control, Indonesian labels, existing radii, responsive layout,
  retained theme choice and documented purpose; no new template sections or claims.
