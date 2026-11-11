# Compact Ruang Chat editor QA, 11 November 2026

Model dropdown follow-up: explicitly set option foreground and background using
the theme's ink/input tokens. Native menus previously could inherit pale text
while displaying a white background. This shared model-control rule covers both
Ruang Chat and RAG. Stylesheet cache version is now 31.

`check_chat_editor.py` passes after the fix: model selection via keyboard, explicit
nontransparent option backgrounds, and WCAG AA contrast with the native select
expanded as a list at 360/768/1024/1440 in light/dark. Inspected the mobile dark
options screenshot. This checks a native listbox; OS popup rendering was not
captured. Backend/provider calls were not needed for this CSS fix.

Follow-up delivery gate: Hard Gate PASS (contrast, keyboard and overflow checks);
Purpose-Gate PASS (paired theme colors make native options legible); Liveliness
PASS (existing 2/2/1 palette and layout); Craftsmanship PASS (browser assertions,
visual inspection and diff whitespace check).

The composer starts at one writing line and grows to a bounded scroll area. Model,
refresh and Send share the bottom row on phones and desktop. The refresh action
uses its existing reload glyph; the visible message label and studio themes remain.

Typing numbered markers with or without a space, bullets, heading markers and
quotes creates editable structure. Bold, italic and inline code markers format
their content. Enter continues a list and exits an empty item; Shift + Enter adds
a line, and Ctrl/Command + Enter sends from inside a list. Outside structured
blocks, Enter sends. Submitted content is serialized as Markdown, and user
messages use the existing safe renderer. Drafts survive failed requests; messages
over 12,000 serialized characters show an error without sending. Clipboard content
is inserted as text, excluding clipboard HTML.

## Evidence

- `python scripts/check_chat_editor.py`: PASS in local Chrome. Covers actual
  typing, numbered start values, list continuation/exit, headings, quotes,
  emphasis, code, exact Markdown serialization, submission keys, safe paste and
  disabled/reset states. Additional component checks at 360/768/1024/1440 in both
  themes confirm zero page overflow and empty composer height under 210px.
- `python scripts/check_workspace_ui.py --url http://127.0.0.1:8013 --output
  storage/ui_qa_compact_editor`: PASS, 118 screen checks, 28 interaction groups.
  Fixture APIs avoid provider calls and publishing. Detailed checks are in
  `storage/ui_qa_compact_editor/report.json`.
- Recorded interactions: model refresh loads options; selection reaches the
  request; Ctrl + Enter sends a numbered message rendered as a list; Send appends
  conversation turns; new conversation clears the editor; history opens/restores,
  refreshes, closes and deletes; provider failure preserves draft and history.
  Existing code/answer copy, theme toggle, mobile navigation, and workspace
  workflows pass the same regression. No unexpected console errors.
- `node --check` on both editor and assistant scripts and `git diff --check`: PASS.
- Visually inspected the full mobile dark conversation and the final compact
  mobile dark composer and desktop numbered-list composer screenshots. The final
  mobile toolbar adjustment was verified by the component checks above.

## Delivery gate

- Hard Gate PASS: labelled textbox, native 44px controls, keyboard focus, safe
  paste/rendering, preserved loading/error states and responsive themes. The
  regression verifies text contrast, overflow and working controls. No assets,
  navigation, claims or animation were added.
- Purpose-Gate PASS: the writing area grows only for content; the single toolbar
  reduces unused height; refresh glyph reloads models; cream retains Send as the
  focal action. Reasons recorded in DESIGN.md.
- Liveliness PASS: ENERGY 2 / RHYTHM 2 / MOTION 1, existing teal/cream identity,
  structured spacing and system typography retained.
- Craftsmanship & Quality Locks PASS: editor interaction assertions, 118 screen
  checks, 28 interaction groups, syntax checks and visual review support this
  change. Existing user edits remain in place.

Backend tests and live provider requests were not run. Editing is verified in
Chrome; other browser engines were not checked. Rich clipboard HTML, a formatting
toolbar, and live table/fenced-code editing are outside this change. Native
contenteditable formatting uses the browser's execCommand editing implementation.
Reload with Ctrl + F5 to fetch the updated versioned assets.
