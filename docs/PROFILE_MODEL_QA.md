# Per-account default text model QA, 11 November 2026

Profil Saya now stores `default_model` with the existing account profile JSON and
revision check in SQLite. Existing accounts default to an empty preference; no
table migration is required. Browser login sessions inherit their own preference
in a request-local model context. Explicit request model choices take priority;
the context resets on completion, including errors. API keys do not inherit a
browser account preference. New campaigns capture the selected effective model so
later profile changes do not alter scheduled work.

The labelled native select uses the existing catalog and reload/status controls.
Default chat choices display `Default profil: ...`, and new Ruang Chat/RAG
conversations return to the account default. Clearing the preference restores
the server default. A missing saved model remains visible as unavailable, and
catalog failures preserve its value so unrelated profile edits do not erase it.

## Verification

- Backend: 59 tests passed across auth, model selection, assistant, campaigns and
  private RAG history; 95 more passed across workspace, staging, WhatsApp and
  CommandCode plans. The updated auth suite passed again after adding API-key
  isolation coverage. Tests use isolated profile databases and mock providers.
- New assertions cover persistence after logout/login, two users in the same
  tenant making concurrent requests with different defaults, explicit overrides,
  invalid model length, unavailable model rejection, clearing to server default,
  API-key isolation and context restoration.
- Browser regression: `python scripts/check_workspace_ui.py --url
  http://127.0.0.1:8013 --output storage/ui_qa_profile_models` verifies the real
  local assets with fixture APIs, including profile catalog reload, saving,
  page-reload persistence, error preservation, default labels, new-conversation
  reset and clearing the preference. PASS: 118 screen checks and 29 interaction
  groups. Full results: the output `report.json`.
- Node syntax checks for app/account/assistant scripts and `git diff --check`
  pass. Inspected the mobile dark profile screenshot, including the new model
  field, reload control and explanation.

## Delivery gate

- Hard Gate PASS: native labelled model select, real reload/save actions, visible
  loading/error states, 44px controls, keyboard operation, text contrast and
  overflow checks at 360/768/1024/1440 in both themes. No new visual assets,
  navigation, claims or animation.
- Purpose-Gate PASS: one account-owned field defines the default; labels explain
  default vs explicit choice; failure feedback preserves the saved preference.
  Direction is recorded in DESIGN.md.
- Liveliness PASS: existing teal/cream identity, system typography and
  ENERGY 2 / RHYTHM 2 / MOTION 1 retained.
- Craftsmanship & Quality Locks PASS: backend isolation/persistence tests, browser
  save/reload/new-conversation interactions, responsive/contrast checks, syntax
  checks and visual review support the behavior.

No live provider credits were used. Browser verification uses Chrome; other
engines were not checked. Restart the backend to load the server changes and use
Ctrl + F5 for versioned browser assets. Image and embedding models are unchanged.
