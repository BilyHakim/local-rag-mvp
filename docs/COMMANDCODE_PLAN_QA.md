# Filter model CommandCode GOAT, 10 November 2026

Configured the local server with `COMMANDCODE_PLAN=goat`. Default installations
retain `catalog` mode until a plan filter is selected. No package discovery is
claimed: the authenticated models response has no plan/entitlement fields.
The source for the GOAT inclusion snapshot is
[CommandCode GOAT](https://commandcode.ai/docs/plans/goat).

## Evidence

- Live authenticated GET, no chat probes: 68 endpoint-compatible GOAT models;
  `gpt-6-sol` and `gpt-6.1-terra` absent, `gpt-6-luna` present. Default
  `google/gemini-3.8-flash` is in the filtered result. No API key printed.
- `python -m pytest -q`: **192 passed**. New cases cover exact model IDs,
  endpoint filtering, other providers, catalog mode, restricted explicit/default
  selection, saved model identity, empty catalog behavior and direct-call bypass
  prevention. Legacy tests explicitly isolate themselves from local plan settings.
- `node --check app/static/app.js` and `git diff --check`: pass.
- Browser regression: **90 screen states, 21 click groups, PASS**; fixtures expose
  GOAT metadata. Model status identifies the filter and states quota is checked
  on send. Existing catalog refresh, error handling, chat, campaign and specialist
  interactions remain covered. Report: `storage/ui_qa_plan_filter/report.json`.
- Inspected mobile/dark and desktop/light screenshots. No overflow or unexpected
  console error; both themes and widths 360/768/1024/1440 pass text contrast checks.

## Delivery gate

- Hard Gate PASS: only existing model status text changed; controls remain native,
  labelled and keyboard-operated, with loading/empty/error states. Browser
  click-through, layout, theme and contrast checks pass; no new assets or claims
  of guaranteed provider access.
- Purpose-Gate PASS: existing status region explains the shorter model list;
  no new decorative treatment or controls. Purpose recorded in DESIGN.md.
- Liveliness PASS: existing ENERGY 2 / RHYTHM 2 / MOTION 1 and teal/cream studio
  direction retained; screenshot inspection confirms unchanged visual hierarchy.
- Craftsmanship & Quality Locks PASS: 192 backend tests plus 90 browser screen
  checks and live catalog verification support the implementation. Server-side
  guard prevents stored/crafted selections from bypassing the GOAT filter.

The filter represents published plan inclusion, not current account balance or
temporary provider capacity. No paid completion was sent to verify every listed
model. Snapshot maintenance is required when plan membership changes. Restart the
running backend to load the local `.env` setting, then refresh the model list.
