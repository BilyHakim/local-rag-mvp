# Folder knowledge QA, 10 November 2026

Scope: explicit browser folder selection, recursive file list, extension/size
preflight, sequential ingestion, progress, pause/resume, failed-file retry,
relative source identities and existing single-file compatibility.
Anti-slop during; editorial workspace, ENERGY 2 / RHYTHM 2 / MOTION 1.

## Evidence

- `python -m pytest -q`: **213 passed, 3 skipped**. New cases cover same-named
  files in different subfolders, uppercase extensions, relative source/chunk
  metadata, exact-source duplicate lookup, temporary file cleanup, invalid/absolute/
  traversal paths, Windows separator normalization, metadata configuration,
  multipart contract/length validation and legacy hash lookup compatibility.
- `node --check app/static/app.js`, `node --check app/static/folder-upload.js`
  and `git diff --check`: pass.
- Workspace browser regression: **PASS, 108 screen states, 24 click groups**.
  Output: `storage/ui_qa_folder/report.json`. Four widths 360/768/1024/1440,
  both themes, contrast/overflow checks and a 200-character active path on mobile.
- Browser selected a real fixture directory with a nested same-name CSV, uppercase
  extension, duplicate result, broken PDF result, rate-limited file, unsupported
  TXT, empty CSV and oversized CSV. Only eligible files were sent. Fixture APIs
  simulate indexing results; no user documents or paid provider requests were used.
- Held a response open: overall progress stayed at 0 and upload inputs remained
  disabled. Paused after the active file, resumed remaining files, confirmed 100%
  with visible failure count, retried only failed files while leaving a paused
  queue untouched, then confirmed complete results. HTTP 429 automatically retried
  after Retry-After; formats failure/reload recovered the picker.
- Inspected mobile/dark and desktop/light completed-batch screenshots. The list
  is bounded and keyboard-focusable; relative names wrap, the progress bar remains
  within its container, and old single-file/manual-note/search workflows pass.

## Delivery gate

- Hard Gate PASS: native labelled input, buttons and progress element; explicit
  loading/empty/error/paused/completed states, per-file text results and existing
  focus styles. Both themes, narrow widths and long paths pass layout/contrast
  checks. No new visual assets, navigation or fabricated success percentages.
- Purpose-Gate PASS: the full-width folder panel groups bulk controls; measured
  progress and per-file status separate transfer from indexing. Existing theme
  tokens and controls reused; reasons recorded in DESIGN.md.
- Liveliness PASS: 2/2/1 dials and teal/cream studio identity retained. Main upload
  action stays prominent; result details and single-file forms remain secondary.
- Craftsmanship & Quality Locks PASS: 213 backend tests, JavaScript syntax checks,
  108 browser screen checks and explicit held-response/recovery cases substantiate
  behavior. Intentional fixture 409/422/429/503 errors exercise recovery; no
  unexpected console errors remain.

The queue requires the browser page to remain open. It does not watch the device
folder in the background. Production parsing/embedding/Qdrant use the existing
ingestion services; this QA did not index user documents into their active store.
100% means all eligible files reached a result, not that every file succeeded.
