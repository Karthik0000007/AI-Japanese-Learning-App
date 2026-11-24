# Vendored frontend libraries

These files are committed so the app works fully offline (no CDN at runtime).
They are the unmodified production builds, pinned to exact versions.

| File | Library | Version | Source URL | SHA-256 |
|---|---|---|---|---|
| `vue.global.prod.js` | Vue | 3.5.29 | https://unpkg.com/vue@3.5.29/dist/vue.global.prod.js | `85f932480cd707a2655d5f49d64d6ca2274c692331213b6b24aab3e4145160d5` |
| `vue-router.global.prod.js` | Vue Router | 4.6.4 | https://unpkg.com/vue-router@4.6.4/dist/vue-router.global.prod.js | `71505f07492774a24202b07d1409652791845594d9846513d22310ac38fa0619` |
| `purify.min.js` | DOMPurify | 3.3.1 | https://unpkg.com/dompurify@3.3.1/dist/purify.min.js | `9b494057fad6656fd9ce2089d0b6898df9632c10e45e4775a43073a46cffc8cb` |

Licences: Vue and Vue Router are MIT; DOMPurify is Apache-2.0 / MPL-2.0
(licence headers are kept at the top of each file).

## Updating

1. Download the new exact version from the URL pattern above (never `@3` or `@latest`).
2. Replace the file here and update the version, URL and SHA-256 in this table.
3. Check the app in the browser: no console errors, flashcards and tutor still work.

Verify the files match this table:

```bash
sha256sum static/vendor/*.js
```
