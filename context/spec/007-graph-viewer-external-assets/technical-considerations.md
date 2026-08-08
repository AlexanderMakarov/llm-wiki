<!--
This document describes HOW to build the feature at an architectural level.
It is NOT a copy-paste implementation guide.
-->

# Technical Specification: External graph viewer assets

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Auto (implement-feature #127)

---

## 1. High-Level Technical Approach

Split the Knowledge Graph page into (1) a slim `graph.html` template, (2) an extracted first-party classic script `graph-viewer.js`, and (3) a pinned vendored UMD build of vis-network committed under `llmwiki/vendor/`. Both `llmwiki graph` and `llmwiki build` emit the HTML plus those two JS companions beside it. Graph JSON stays a tiny inline `const GRAPH = …` stub (already `file://`-safe). No `fetch`, no ES modules. Product `serve`/API unchanged.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

- No new services or runtime Python dependencies.
- New source module: `llmwiki/render/graph_viewer.py` exporting `GRAPH_VIEWER_JS` (mirrors `llmwiki/render/js.py`).
- New committed vendor asset: `llmwiki/vendor/vis-network.min.js` (vis-network **9.1.9** standalone UMD — same pin as today’s CDN) plus attribution (e.g. `llmwiki/vendor/NOTICE`).
- `llmwiki/graph.py` `HTML_TEMPLATE`: replace CDN `<script>` and the large inline viewer `<script>` with relative classic tags:
  - `<script src="vis-network.min.js"></script>`
  - keep site chrome: `style.css`, `script.js` (site/ path)
  - tiny inline: `const GRAPH = __GRAPH_JSON__;` (plus existing `__KIND_OTHER_LABEL__` substitutions as needed)
  - `<script src="graph-viewer.js" …></script>` after the GRAPH stub
- Emit helpers: extend `write_html` (or a sibling) to write `graph-viewer.js` and copy `vis-network.min.js` next to every `graph.html` (both `graph/` and `site/`).
- `copy_to_site` / `build_site` graph write path must carry both assets, not HTML alone.
- Standalone `llmwiki graph`: emit `graph.html` + `graph-viewer.js` + `vis-network.min.js` into `graph/` (does **not** copy full site chrome; nav/search remain site-root concerns when viewing via `site/graph.html`).

### Data Model / Database Changes

- None.

### API Contracts

- None. No wiki schema, config keys, or HTTP APIs.

### Component Breakdown

| Artifact | Responsibility |
|---|---|
| `llmwiki/render/graph_viewer.py` | Source of viewer logic string |
| `llmwiki/vendor/vis-network.min.js` | Offline canvas library |
| `llmwiki/graph.py` | Template + emission of HTML + companions |
| `llmwiki/build.py` | Ensure site graph path gets companions (via graph helpers) |
| `tests/test_graph_viewer.py` (+ related graph tests) | Point JS substring asserts at `GRAPH_VIEWER_JS` / emitted files; CDN assert → local `src`; size budget on `GRAPH_VIEWER_JS` |

### Logic / Algorithm

- Offline notice stays: if `typeof vis === 'undefined'`, show `#offline-notice` (now means missing/broken vendor file, not merely “no network”).
- SRI on the local file: omit; keep version pin documented in vendor NOTICE + changelog.
- Escape rules for embedding GRAPH JSON in a script tag unchanged.
- Size guardrail is **CI/`pytest` only**: `assert len(GRAPH_VIEWER_JS) < 32_000`; never at user `build` time.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** Graph page, graph tests, a11y pin tests (`test_ui_a11y_bundle_473.py` CDN/SRI asserts), docs that mention CDN/offline notice.
- **Potential Risks & Mitigations:**
  - ES modules or `fetch` for data → breaks Firefox/`file://` — mitigate: classic scripts + inline GRAPH only.
  - Large vendored file in git — accept: required for offline FR2.
  - Standalone `graph/` without `script.js` → site nav/theme dead there (pre-existing for full chrome); in scope: graph canvas works offline via local vis + viewer.
  - License attribution missing — mitigate: NOTICE under `llmwiki/vendor/`.
- **context/:** This spec directory satisfies CONTRIBUTING’s product-PR `context/` rule.

---

## 4. Testing Strategy

- Unit/template: budget moves to `GRAPH_VIEWER_JS`; HTML asserts `src="graph-viewer.js"` and `src="vis-network.min.js"`; no unpkg CDN URL.
- Emission: `write_html` / build / `llmwiki graph` tests assert companion files exist beside HTML with expected markers.
- Relative-asset / static checks: constructed HTML references relative assets; Playwright against built `$TMP_VAULT/site` with network blocked when harness allows.
- Repoint existing `HTML_TEMPLATE` JS substring tests to `GRAPH_VIEWER_JS` (HTML-only asserts stay on the template).
- Manual smoke (operator): build throwaway or live vault; open `site/graph.html` from disk with network off; confirm canvas draws.
