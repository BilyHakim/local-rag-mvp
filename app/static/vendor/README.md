# Browser dependencies

markdown-it 15.0.3, MIT license. Browser UMD bundle vendored from
https://unpkg.com/markdown-it@15.0.3/dist/browser/markdown-it.umd.min.js
on 2026-11-10. License: markdown-it-LICENSE.txt.

Upstream: https://github.com/markdown-it/markdown-it
No CDN request is made by the application at runtime. Configuration and DOM
enhancements are in ../markdown.js; raw HTML is disabled and remote images are
rendered as alternative text. No plugins or custom HTML highlighter are used.
