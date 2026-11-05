# Workspace design direction

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
