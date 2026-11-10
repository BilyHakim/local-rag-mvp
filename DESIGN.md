# Workspace design direction

Markdown answers retain ENERGY 2 / RHYTHM 2 / MOTION 1 and the studio theme.
Use real headings and lists for reading hierarchy, theme-token table headers for
comparison, and monospace only for code. Tight paragraph spacing removes the
excess blank lines from plain-text rendering. Wide tables and unwrapped code scroll
inside keyboard-focusable regions; they never widen the page. Code toolbars name
the language and copy only that block. Quote surfaces group quoted content without
decorative stripes. Raw HTML and remote image loading are disabled; no new assets.

Plan filtering retains the current 2/2/1 studio direction. Show the configured
GOAT filter in each existing model status line so users understand the shorter
catalog. Keep model selection and refresh controls unchanged; label quota as a
send-time check instead of claiming guaranteed account access. No new assets.

Ruang Chat adds one requested navigation destination for general conversations.
Retain the editorial workspace language, ENERGY 2 / RHYTHM 2 / MOTION 1.
Use a compact history disclosure above the conversation so narrow screens retain
space for reading. User messages use the existing soft surface; assistant answers
use plain reading space with code blocks separated for copying. The labelled
composer and cream Send action remain the focus. Existing system type, teal,
focus states and theme tokens apply; no new decorative assets or animation.

Carousel extension: retain ENERGY 2 / RHYTHM 2 / MOTION 1 and the current
editorial studio direction. Numbered previews follow reading order in a wrapping
grid, so infographics remain inspectable on phones. Native earlier/later buttons
support keyboard ordering without dragging. Existing secondary buttons, type,
theme colors and focus states keep the editor consistent. Count fields distinguish
slides per post from campaign post count; no new visual assets or animation.

Login: retain ENERGY 2 / RHYTHM 2 / MOTION 1, the teal wordmark, system type and
cream submit action. A single narrow form on the existing canvas asks only for
username and password. Visible labels, autocomplete, password visibility, inline
errors and a submit loading state serve sign-in. Use the saved light/dark theme
with a working toggle. The authenticated utility bar shows identity and logout.
No new assets or decorative claims; mobile padding follows existing scale.

Planner return navigation: show a native secondary "Kembali ke Content planner"
button above the editor when a post was opened from the list. Preserve the list
scroll position and return keyboard focus to that post's manage button. Opening
the editor focuses the return control so its location is clear. Unsaved edits
stay in memory when returning; opening another post requires saving them first.
Use existing spacing, colors and typography, with no new navigation destination.

Automatic planner: retain ENERGY 2 / RHYTHM 2 / MOTION 1 and the editorial teal
workspace. A labelled campaign form precedes the campaign list and existing post
history. Theme spans the form; schedule, recurrence and image mode pair only when
readable. Campaign status, progress and pause/resume sit together so operators can
see what will publish. Manual images are the default; waiting posts explain the
next upload action. The cream primary action explicitly activates automatic
publication. No new assets, animations, decorative metrics or navigation.

Social Media model selection follows ENERGY 2 / RHYTHM 2 / MOTION 1. Place a
compact native "Model teks" select beside "Tulis tanpa AI" below generation,
keeping secondary controls together without interrupting brief entry. Reuse white
brief inputs with a 240px maximum group width and a labelled 44px refresh icon;
the row wraps on phones and long model names stay inside the select. A status line
appears only for loading, empty catalogs, and errors. Text model selection applies
to creation and revision; image generation keeps its own server configuration.

Manual Instagram prototype: keep ENERGY 2 / RHYTHM 2 / MOTION 1. Place a native,
visibly labelled image picker beside the existing preview, with the same quiet
secondary button style as Save. This groups image selection with its result and
keeps publishing as the deliberate final action. "Tulis tanpa AI" creates a
draft without spending provider credits. Upload states follow draft editability;
errors use the existing toast and successful uploads refresh the reserved preview.

The RAG composer puts model, refresh, source count, and send in one bottom toolbar.
Its 24px outer corners soften the writing surface; smaller 10px controls preserve
hierarchy. Model and source inputs use theme input colors, refresh is a quiet
44px icon control, and cream belongs to Send. A top-right expand/collapse control
changes writing height without taking over navigation. Controls wrap on phones.
Only loading, empty, and error model feedback occupies a status line. No new assets.

Reading this as: a research and content production workspace for SEO and social
media specialists, in an editorial studio language. ENERGY 2 / RHYTHM 2 /
MOTION 1. Anti-slop mode: during, selected by the user for this session.

The current user-supplied palette is #086288 / #4D8DBA / #97D7FF / #FFEFC4.
Teal separates persistent navigation and the brief from the editable result.
Medium blue defines supporting structure rather than backgrounds for small white
text. Sky blue marks secondary accents and dark-theme links. Cream identifies the
selected navigation destination and primary create/send action with teal text.
Cool paper neutrals support long editing sessions. At the user's request, dark
mode uses tonal teal surfaces close to the unchanged sidebar: #0A4B66 canvas,
#0B5573 panels, and #09465F inputs. This avoids the previous near-black/bright-teal
split while retaining readable depth. The user's theme preference is preserved. This replaces the
previous vivid blue/lime palette at the user's request.

Keep the existing five navigation destinations and application workflows. Put
workspace access in a utility header, separate from the task. Social Media has two
actual work areas: brief and material. Publishing is a disclosure after editing.
RAG has a left-aligned headline, text suggestions, and a prominent question form.
SEO and knowledge share the shell with their own content-specific form layouts.

Use Segoe UI/system sans for readable Indonesian labels, native offline availability,
and consistent form rendering. Heavier, tighter headings provide editorial emphasis.
Use 32/40px between work regions, 20/24px within forms, and 8px between labels and
fields; narrow screens use a smaller spacing register. Flat surfaces and 8px
controls distinguish inputs from 16px work panels. Shadow marks only popovers,
the composer, and the mobile drawer. The existing glyphs identify actual tools;
the product name is a text wordmark, with no new generated logo or stock imagery.

Narrow screens stack brief and result; medium screens pair fields when readable;
wide screens show both work areas side by side. The existing sidebar becomes a
dismissible mobile drawer with Escape, backdrop, keyboard focus containment, and
a visible menu label. Enabled targets are at least 44px. Motion is limited to
short interaction transitions and respects reduced motion. Both themes, visible
labels, and empty/loading/error states belong to the design. Preview images reserve
a square area. No fabricated metrics, decorative grids, gradients, glass, or glow.
