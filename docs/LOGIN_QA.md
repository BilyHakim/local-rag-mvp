# Workspace login verification

Date: 2026-11-06. Ponytail full; anti-slop during (session choice).
Direction: existing DESIGN.md, ENERGY 2 / RHYTHM 2 / MOTION 1.

## Behavior

Browser login is enabled by default. On first local login, the application creates
admin / admin123 if the account does not exist. The account uses tenant local and
retains access to the existing workspace. Users and sessions live in
STORAGE_DIR/auth.sqlite3. Passwords use salted scrypt; session tokens are random,
with only SHA-256 hashes stored server-side. HttpOnly/SameSite=Lax cookies last
eight hours, use Secure on HTTPS or outside local mode, and are revoked on logout.
Successful reauthentication rotates the browser's previous session.

The root page redirects anonymous users to /login. APIs require a valid session
or an existing Bearer API key. The browser sends a custom request header for
mutations; middleware also checks Origin and cross-site fetch metadata. Login is
limited to ten attempts per client address per minute on the single server process.
Signed public media remains accessible to Meta through its existing signature
verification. Logout does not stop active background campaigns.

No registration, password reset, account management or MFA was added. The initial
password setting initializes an absent account only; existing passwords are never
silently overwritten. Nonlocal mode does not seed admin123 automatically.

## Evidence

- Backend suite: 162 passed, 3 skipped. Auth tests cover missing/invalid sessions,
  password failures, SQL injection input, CSRF/origin checks, session expiry and
  revocation, stored hashes, session rotation, role/tenant boundaries, rate limits,
  Secure cookies, existing local data, bootstrap behavior and Bearer compatibility.
- Existing backend tests explicitly opt into legacy local access; auth tests turn
  login back on and reset middleware state. Production default is login enabled.
- Real local login UI: PASS, 8 viewport/theme checks and 5 interaction groups.
  Four widths (360, 768, 1024, 1440px), both themes, measured text contrast and no
  horizontal overflow; desktop dark and mobile light screenshots inspected.
- Click-through: anonymous root redirects; wrong password displays a generic
  error and clears the field; show/hide password works; keyboard login sets an
  HttpOnly cookie; reload retains login; logout revokes the session and protects
  the root/API again. No unexpected console errors.
- Workspace regression: PASS, 66 layout/contrast checks, 18 interaction groups.
  Existing chat, social, planner, editor navigation, image upload and knowledge
  workflows retain their fixture behavior with the authenticated identity header.
- Evidence: storage/qa/login/report.json and storage/qa/auth-workspace/report.json.
- Login UI ran against isolated SQLite storage; provider requests were blocked or
  mocked and no live publication took place. HTTPS deployment was not exercised.
- git diff --check: clean. The pre-existing test_staging.py import-order edit
  was retained unchanged.

## Delivery gate

- PASS Hard Gate, R-02/03/17/18/23/24/28/36/38: no new assets, fabricated content,
  unrelated sections or ghost navigation; no checked horizontal overflow.
- PASS R-25/26/27: text contrast checked in both themes; theme, password visibility,
  submit and logout perform real actions; validation/loading/error states exist.
- PASS R-32/34/35/39: labelled native inputs with autocomplete, keyboard login,
  visible focus, 44px controls, alert semantics, both themes and recorded click-through.
- PASS R-33/37/40: source edits with prior written direction; no new media or
  render-blocking third-party scripts. Web Vitals not measured.
- PASS Purpose Gate: reuse system typography, existing canvas/panels, teal identity,
  cream primary action and secondary controls; written reasons in DESIGN.md.
- PASS Liveliness: explicit 2/2/1 dials; sign-in is the focal action, whitespace
  separates identity and fields, the established wordmark and accent are retained.
- PASS Craftsmanship/Quality Locks: fields serve login only; session/role handling
  reuses workspace identity, state and errors are tested, no decorative template
  sections, new dependencies or unsupported claims.
