# Workspace redesign verification

The user selected anti-slop **during** and supplied palette
`#086288 / #4D8DBA / #97D7FF / #FFEFC4`. Visual decisions and their purposes are
recorded in `DESIGN.md`. No new logos, people, testimonials, or production data
were generated.

The latest tonal adjustment leaves the sidebar unchanged and brings the dark
content area into the same teal family: #0A4B66 canvas, #0B5573 panels, #09465F
inputs. All 40 screen/theme/width checks and the click-through were rerun after
this adjustment; latest local evidence is in `storage/ui_qa_tonal/report.json`.

## Delivery Gate

- **Hard Gate: PASS.** Local app started; the browser runner checks all five views
  at 360, 768, 1024, and 1440px in both themes (40 combinations). Assertions check
  horizontal overflow and visible text contrast. Forms, navigation, drawers,
  theme switching, empty/error states, and publishing controls are exercised.
  No unexpected JavaScript console errors were found. The image preview reserves
  its aspect ratio; assets are local and no third-party script blocks rendering.
- **Purpose-Gate: PASS.** `DESIGN.md` records the purpose of palette, type, spacing,
  work areas, navigation glyphs, functional status labels, and disclosure controls.
  There are no gradients, decorative glows, background grids, or stock illustrations.
- **Liveliness: PASS.** ENERGY 2 / RHYTHM 2 / MOTION 1. Teal distinguishes the
  brief and tool navigation, the result is a separate editing surface, and cream
  marks the primary create/send action. The design follows the actual work areas
  rather than a promotional hero/card template.
- **Craftsmanship & Quality Locks: PASS.** Both themes and four widths are checked;
  actions keep their existing API contracts. Typography works offline, labels name
  real actions, and no unsourced performance/security/customer claims were added.
  Native controls, focus indicators, Escape, inert content, and drawer focus
  containment support keyboard use. Backend regression suite: **89 passed**.

## Recorded click-through

The standalone runner `scripts/check_workspace_ui.py` uses a fresh headless Chrome
profile and fixture API responses. It blocks external requests and never invokes
real model providers, uploads to external services, or publishes real content.

| Area | Actions and observed result |
| --- | --- |
| Navigation | All five destinations open; wordmark opens Knowledge; sidebar collapses/expands |
| Mobile menu | Opens; main becomes inert; focus stays in drawer; Escape/backdrop closes |
| Themes | Theme button changes light/dark; contrast and overflow checked after transitions |
| Workspace access | Fixture key submits; tab-memory label changes; logout clears it; Escape dismisses |
| Company profile | Save returns fixture success feedback |
| Social brief/editor | Channel selection, brief, generation, edit/save, chat revision, image preview |
| Publishing/planner | Approve, schedule, cancel, publish with uncertain result, reconcile, refresh, open, new content |
| SEO | URL submit, knowledge checkbox, findings, history, detail disclosure, JSON download |
| Knowledge | Select/upload CSV, save note, search results |
| RAG | All query suggestions, source-count select, send, evidence show/hide, new conversation |
| API docs | Opens the real local `/docs` route in a new tab |
| Error state | Fixture provider failure produces persistent visible feedback; empty draft controls stay disabled |

The backend suite exercises server behavior; fixture browser tests exercise UI
behavior. These checks do not establish live integration readiness or full WCAG
conformance. Actual Instagram, AI provider, and CMS credentials are not used by
this regression run.

## Contrast samples

Computed with the vendored anti-slop contrast checker:

| Pair | Ratio |
| --- | --- |
| Teal text on cream primary button / selected navigation | 5.91:1 |
| Sidebar text on teal | 5.96:1 |
| White text on teal | 6.75:1 |
| Light-theme secondary text on canvas | 5.79:1 |
| Dark-theme secondary text on canvas | 7.03:1 |
| Light-theme input boundary on white | 3.45:1 |
| Dark-theme input boundary on surface | 3.98:1 |

## Reproduce

Install the optional UI test dependencies, start a development instance, then run:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
.\.venv\Scripts\python.exe -B scripts/check_workspace_ui.py --url http://127.0.0.1:8011
```

The runner uses an installed Google Chrome through Playwright's `chrome` channel.
It only accepts localhost/127.0.0.1. The test server must serve the current local
frontend assets. Outputs are saved under ignored `storage/ui_qa/`: eight Social
Media screenshots and `report.json` with all 40 checks and click-through groups.

Backend and source checks:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q
node --check app/static/app.js
node --check app/static/workspace.js
git diff --check
```
