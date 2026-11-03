# Anti-slop skills

Installed locally for this project from
[miqdadbadjuber/anti-slop](https://github.com/miqdadbadjuber/anti-slop), using the
Codex Skill Installer with the upstream `main` branch. These are agent instructions,
not application dependencies; FastAPI and the website do not load them at runtime.

The six upstream skill directories are preserved under `.agents/skills/`:

| Skill | Purpose |
| --- | --- |
| `antislop` | Core rules, usage modes, design direction, delivery checks |
| `antislop-ui` | Layout, visual hierarchy, components, decoration, motion |
| `antislop-copywriting` | Product text, headings, calls to action |
| `antislop-human` | Accessibility, contrast, keyboard use, interaction states |
| `antislop-layoutmobile` | Responsive layout, reflow, mobile interactions |
| `antislop-code` | Code comment quality |

Each directory contains its upstream `SKILL.md`. The core's `VERSION` records
release **3.2.25**. Supporting files are included when provided, including the
human skill's contrast checker.
The upstream MIT license is preserved at
`.agents/skills/antislop/LICENSE` and covers the vendored skill files.

`AGENTS.md` points coding agents to the core and relevant supplements for UI work.
Start a new Codex turn/session after installation so local skills can be discovered.
The core's mode selection applies when using the skill; this installation does
not save a global preference or choose a design direction.

Only these six skill directories are unignored in Git. Other local `.agents`
content remains ignored. No global skill directory or application credentials
were changed. The website redesign is a separate task.

Upstream files are a local snapshot and do not update automatically. To update,
review the upstream changes and replace the same six skill directories together,
preserving the license. Do not install an unrelated package named `antislop`.
