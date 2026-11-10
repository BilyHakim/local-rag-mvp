# Personal profile QA, 10 November 2026

Scope: personal profile, feature preferences, password changes, navigation and
session API enforcement. Anti-slop during was selected in the conversation.
Direction: editorial workspace, ENERGY 2 / RHYTHM 2 / MOTION 1, recorded in DESIGN.md.

## Evidence

- `python -m pytest -q`: **199 passed, 3 skipped**. New tests exercise profile
  persistence, stale revision rejection, CSRF/input validation, per-user isolation,
  role limits, disabled API paths, all-features-off recovery, API-key read-only
  behavior, old/new password verification, hashed storage, other-session revocation,
  and separate password attempt rate limiting.
- `node --check` on app.js and account.js plus `git diff --check`: pass.
- Workspace browser regression: **PASS, 99 screen states, 23 click groups**.
  Report: `storage/ui_qa_account/report.json`. Tested seven views at widths
  360/768/1024/1440 and in both themes, with text contrast and overflow checks.
  Profile interactions cover edit/save, reload persistence, disabling/restoring
  all four functions, direct-hash guard, keyboard save, password confirmation,
  incorrect current-password feedback, success feedback and profile reload.
- Real login/profile endpoints: **PASS, 8 login screen states, 7 click groups**.
  Report: `storage/ui_qa_profile_auth/report.json`. Used isolated storage
  `storage/profile_auth_qa`, scheduler disabled, external requests blocked. Verified
  browser cookie login, real profile persistence, actual disabled-feature HTTP 403,
  restored navigation, password change, login with the new password, and final
  logout. The test password was restored within that isolated database.
- Inspected mobile/dark and desktop/light profile screenshots. Forms stack on
  phones; fixed account identity and editable fields remain visibly labelled;
  four feature checkboxes and separate password form fit without horizontal overflow.

## Delivery gate

- Hard Gate PASS: native, labelled fields/buttons/checkboxes; focus and keyboard
  behavior reuse the tested shell. Loading/disabled/error states and actionable
  error text are present. Seven-view click-through, themes, text contrast and
  responsive layout checks pass. No new visual assets or fabricated claims.
- Purpose-Gate PASS: sidebar account utility stays reachable when main features
  are off; a single-width form groups profile/preferences; password changes have
  their own submit action. Existing theme/type controls reused; reasons in DESIGN.md.
- Liveliness PASS: the existing 2/2/1 dials, teal/cream identity, content hierarchy
  and studio spacing remain consistent in inspected screenshots.
- Craftsmanship & Quality Locks PASS: 199 backend tests, 99 fixture screen checks,
  real authenticated browser checks and JavaScript syntax checks support the
  reported functionality. Only intentional fixture 409/503 errors are excluded
  from the browser console report; no unexpected console errors remain.

Preferences apply to browser accounts and do not stop existing shared campaigns
or modify API-key permissions. Username and role remain immutable; email is contact
information only. API-key/auth-disabled sessions cannot edit profile/password.
Restart the running backend and refresh browser assets to use the new endpoints.
