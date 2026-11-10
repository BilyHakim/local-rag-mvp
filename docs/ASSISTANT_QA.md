# Ruang Chat QA, 10 November 2026

Scope: additional general chat tab backed by the existing CommandCode adapter.
Mode: antislop during, selected in this conversation. Design direction:
editorial workspace, ENERGY 2 / RHYTHM 2 / MOTION 1, documented in DESIGN.md.

## Verification

- `python -m pytest -q`: 186 passed. New assistant cases cover provider message
  history, selected model, context limits, input validation, stale revisions,
  error preservation, authentication, reader access, per-user and tenant isolation,
  and deletion. Existing provider and specialist checks remain green.
- `node --check app/static/assistant.js`, `node --check app/static/app.js`,
  and `git diff --check`: pass.
- `python scripts/check_workspace_ui.py --url http://127.0.0.1:8013 --output
  storage/ui_qa_assistant`: PASS, 90 screen states and 21 interaction groups.
  Browser APIs use fixtures and block external requests. Four widths
  (360/768/1024/1440), both themes, text contrast and overflow checked.
- Browser click-through: new conversation, model refresh/selection, Enter send,
  Shift+Enter newline, continued chat, safely escaped code blocks, real clipboard
  copy, reload, history open/refresh, delete confirmation, provider failure with
  input retained. Asserted composer does not overlap the last message.
- Inspected desktop/light and mobile/dark screenshots. Initial inherited sticky
  composer overlap was fixed by keeping this composer in document flow; browser
  checks and screenshots were regenerated afterward.
- One live synthetic request to CommandCode succeeded with `google/gemini-3.8-flash`:
  answer `Siap.`. The local default in `.env` was corrected from the unsupported
  unprefixed ID. No API key printed; no user conversation sent in this check.

## Delivery gate

- Hard Gate PASS: new controls have native roles, visible labels, keyboard access,
  existing focus states, loading/error feedback and working handlers. The browser
  test confirms safe text rendering, both themes, text contrast and no horizontal
  overflow. Only the requested navigation destination was added, with a relevant
  text-bubble glyph and no generated assets, animation or fabricated claims.
- Purpose-Gate PASS: existing theme/type/components reused; code uses monospace
  only to read code, and the history disclosure keeps narrow screens readable.
  Reasons and visual direction are recorded in DESIGN.md.
- Liveliness PASS: existing teal/cream identity, editorial type, spacing and
  2/2/1 dials retained; composer is the primary action, history is secondary,
  and responses occupy plain reading space with distinct code blocks.
- Craftsmanship & Quality Locks PASS: 186 backend tests, JavaScript syntax checks,
  90 browser screen checks and live provider response support the reported
  behavior. Existing six-view navigation, model catalogs, RAG, specialists and
  authentication checks pass. No unexpected browser console errors.

## Limits

The live check verifies the default provider/model, not every catalog model or
subscription entitlement. Chat is text-based without browsing, attachments,
streaming, tool execution or memory across separate conversations. Stored messages
are per account/tenant; server operators with database access can still read them.
Restart the running backend to reload the corrected local model setting.
