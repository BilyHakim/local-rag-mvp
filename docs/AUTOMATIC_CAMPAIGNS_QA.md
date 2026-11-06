# Automatic campaign verification

## Planner return refinement

Opening a post from the list now exposes "Kembali ke Content planner" above the
editor. Returning restores scroll and keyboard focus to that post. Unsaved caption
edits remain in memory when reopening the same post; opening a different post is
blocked until edits are saved. A new draft clears the return destination.

UI regression: PASS, 66 layout/contrast checks and 18 click-through groups. Return
navigation was keyboard-tested at 360, 768, 1024 and 1440px in both themes, with
scroll restoration assertions and no unexpected console errors. Desktop dark and
mobile light editor screenshots inspected. Evidence: `storage/qa/planner-return/`.

Delivery gate for this refinement: PASS Hard Gate (native named button, focus,
44px target, responsive layout and checked contrast); PASS Purpose Gate (existing
secondary style and written placement reason in DESIGN.md); PASS Liveliness
(retained 2/2/1 direction); PASS Craftsmanship (real return action, preserved edit
state, no new assets or claims). The detailed gate below still applies.

Date: 2026-11-06. Anti-slop: during, session choice. Direction: DESIGN.md,
ENERGY 2 / RHYTHM 2 / MOTION 1, existing editorial workspace.

## Behavior

Content planner accepts a theme, text model, channel, first WIB publication time,
recurrence, count (1 to 30), knowledge choice and image mode. Activation authorizes
automatic generation and publication for that campaign. Campaign and queued slots
are committed together. Model selection uses the existing API/Ollama boundary,
including the configured Command Code adapter.

Manual images are the default: caption generation proceeds, while Instagram slots
without uploaded images wait. Upload may happen before or after generation. When
both are ready, the slot is scheduled automatically. Automatic image mode checks
provider configuration and uses the existing generation adapter. Website slots
can publish text without a manual image.

Each prompt gets a slot-specific angle and recent content. Normalized exact text,
word-set overlap (0.8) and sequence similarity (0.85) reject duplicates or close
copies. At most three candidates are tried. This is a text similarity filter over
up to 10,000 recent tenant posts, not a semantic uniqueness guarantee. The prompt
includes up to 60 recent captions. Failed slots remain visible instead of posting
the rejected result.

Generation and publication run in separate tasks; slow AI calls do not block the
publication loop. Publication checks active campaign status inside the atomic
database claim. Pausing prevents new claims; in-flight operations can finish.
Late ready slots run on a later scheduler check, including after resume/restart.
An uncertain publication is not retried automatically. Interrupted generation is
marked failed after the existing 15-minute recovery window. One worker is required.

## Evidence

- Full backend suite: 155 passed.
- Campaign tests: 12 passed, covering API model validation, atomic slot creation,
  timezone/recurrence, tenant boundaries, duplicate regeneration/exhaustion,
  context cleanup, upload before/after generation, manual image gate, automatic
  image HTTP adapter, pause/resume, atomic publish gate, interrupted generation,
  uncertain results, concurrent slot claims, and independent generator shutdown.
- UI regression: real local assets and fixture APIs; external requests blocked.
  `storage/qa/automatic-campaigns/report.json` records layout/contrast checks and
  individual click-through groups.
- Viewports: 360, 768, 1024, 1440px, light and dark. Desktop dark and mobile light
  screenshots inspected. No checked horizontal overflow or text contrast failure.
- New click-through: model refresh retains selection; form defaults to manual;
  theme/model/count/interval/WIB range preview; keyboard activation creates a
  campaign; pause and resume change state; an awaiting-image slot disables publish;
  uploading its image moves it to scheduled. Existing manual workflows also pass.
- Launcher help exposes `--enable-scheduler`. No live campaign or external post
  was created during verification; actual provider and Instagram behavior need a
  live smoke test by the operator.

## Delivery gate

- PASS Hard Gate, R-02/03/17/18/23/24/28/36/38: no fabricated claims, assets, FAQ,
  navigation or unrelated sections; tested mobile layouts have no horizontal leak.
- PASS R-25: automated text contrast across both themes, including the new form.
- PASS R-26/27: activation, model refresh, pause/resume and upload work; empty,
  loading, failed and waiting states are implemented and exercised.
- PASS R-32/34/35/39: native visibly labelled controls, status regions, keyboard
  activation, inherited visible focus and 44px targets; both themes were run.
- PASS R-33/37/40: source edits, recorded design direction, no new media or scripts
  that block rendering. Web Vitals were not measured.
- PASS Purpose Gate: retained palette, typography, radii and button hierarchy;
  no new decorative gradients, glow, glass, shadows, icons or motion. Refresh
  reuses the existing action icon. Reasons are recorded in DESIGN.md.
- PASS Liveliness: explicit 2/2/1 dials, campaign activation as focal action,
  structural spacing, cream accent and teal studio identity retained.
- PASS Craftsmanship/Quality Locks: each field serves campaign setup; manual
  default matches the user's current image workflow; preview and progress use
  actual configuration/state. No new template sections or unsupported guarantees.

## Run locally with the media tunnel

Restart the previous launcher, then use:

```powershell
.\.venv\Scripts\python.exe -B scripts/run_instagram_prototype.py --cloudflared storage/tools/cloudflared.exe --enable-scheduler
```

Open `http://127.0.0.1:8011/#social`, then Content planner. Keep the server and
tunnel running. Scheduler starts processing stored active campaigns when enabled;
pause campaigns before stopping if they should remain on hold after restart.
