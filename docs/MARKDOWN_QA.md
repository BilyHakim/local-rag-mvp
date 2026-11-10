# Ruang Chat Markdown QA, 10 November 2026

Replaced the partial regex formatter with a locally vendored markdown-it 15.0.3
browser parser. License and origin are in `app/static/vendor`. Stored messages,
provider calls, model selection and backend routes are unchanged.

## Verification

- `node --check app/static/markdown.js`, `node --check app/static/assistant.js`
  and `git diff --check`: pass.
- `python scripts/check_workspace_ui.py --url http://127.0.0.1:8013 --output
  storage/ui_qa_markdown`: **PASS**, 91 screen states and 22 interaction groups.
  Detailed output: `storage/ui_qa_markdown/report.json`.
- Confirmed real heading elements, tables, nested and numbered lists, emphasis,
  inline code, fenced code, quotes, links and separators. Code copy uses the
  actual browser clipboard and contains code only; answer copy retains Markdown.
- Nine safety samples cover raw script/image/SVG/iframe HTML, event attributes,
  JavaScript URLs, encoded JavaScript, data/file/VBScript URLs, remote image
  Markdown, code containing HTML, and a valid HTTPS link. No executable elements,
  event attributes or unsafe anchors were produced.
- Widths 360/768/1024/1440 and light/dark themes pass overflow and text contrast
  checks. Tables and code scroll horizontally with ArrowRight after keyboard
  focus; 200% answer text passes layout checks. Composer does not overlap answers.
- Inspected mobile/dark and desktop/light screenshots: headings and tables replace
  raw markers, code has a language toolbar, paragraphs have normal spacing.
- Browser fixtures block external requests. Parser loads from the local app, and
  Markdown images do not trigger downloads. No provider credits were consumed.

## Delivery gate

- Hard Gate PASS: native, labelled copy buttons work; headings/lists/tables have
  semantic markup; code and table regions are keyboard-focusable and scrollable;
  both themes, narrow layouts and 200% answer text pass browser checks. No new
  navigation, visual assets, fabricated claims or animation.
- Purpose-Gate PASS: headings organize answers, table headers support comparison,
  quote backgrounds group quoted material, monospace identifies code, and code
  toolbars identify/copy the block. Existing palette and controls retained;
  reasons recorded in DESIGN.md.
- Liveliness PASS: ENERGY 2 / RHYTHM 2 / MOTION 1 and the editorial teal/cream
  direction retained, with content hierarchy replacing plain-text whitespace.
- Craftsmanship & Quality Locks PASS: 91 screen checks, 22 interaction groups,
  syntax checks, clipboard verification and nine safety samples support the
  delivered behavior. No unexpected console errors; history reload, provider
  error recovery and existing workspace workflows still pass.

Backend tests were not rerun because this change only affects browser rendering.
Mathematical typesetting, Mermaid diagrams and syntax coloring are not included.
Raw HTML remains visible text; Markdown image alt text replaces image downloads.
Ctrl+F5 loads the updated versioned assets without restarting the backend.
