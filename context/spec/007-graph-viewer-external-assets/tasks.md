# Tasks: External graph viewer assets (#127)

- **Functional Spec:** [`functional-spec.md`](functional-spec.md)
- **Technical Spec:** [`technical-considerations.md`](technical-considerations.md)

Every slice leaves the package importable and the throwaway vault buildable. Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` before considering any slice done.

**Vault rule for every task:** mutating `llmwiki` commands target the worktree's throwaway vault only — `python3 -m llmwiki … --vault "$PWD/.worktree-vault"` from the worktree root. Never write `raw/`, `wiki/`, or `site/` under the operator's live vault. Always invoke `python3 -m llmwiki`, never PATH `llmwiki`.

---

- [x] **Slice 1: Extract viewer JS + emit beside graph.html (CDN still OK)**

  > First runnable increment: template shrinks; classic `graph-viewer.js` loads; graph still works over HTTP with network (CDN Vis unchanged in this slice). Covers FR1 partially + FR4 emission + FR5 CI budget foundation.
  - [x] Create `llmwiki/render/graph_viewer.py` exporting `GRAPH_VIEWER_JS` — move the inline viewer body from `HTML_TEMPLATE` (logic after the `const GRAPH = …` line through end of the big `<script>`), adapting so it reads the global `GRAPH` already set by a tiny inline stub. Do not use ES modules or `fetch`. **[Agent: general-purpose]**
  - [x] Update `HTML_TEMPLATE` to reference `<script src="graph-viewer.js">` after a tiny inline `const GRAPH = __GRAPH_JSON__;` stub; keep the existing vis-network CDN tag for this slice only. **[Agent: general-purpose]**
  - [x] Extend `write_html` (and callers `copy_to_site` / `build_and_report` / site build path) so every written `graph.html` gets a sibling `graph-viewer.js` written from `GRAPH_VIEWER_JS`. **[Agent: general-purpose]**
  - [x] Repoint template JS substring tests from `HTML_TEMPLATE` to `GRAPH_VIEWER_JS` where they target viewer logic; assert HTML contains `src="graph-viewer.js"`; move size budget to `assert len(GRAPH_VIEWER_JS) < 32_000` with a #127 citation in the failure message. Keep HTML-only asserts on the template. **[Agent: general-purpose]**
  - [x] Verify: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_graph_viewer.py tests/test_graph_context_menu.py tests/test_graph_physics_freeze.py tests/test_graph_site_url.py tests/test_graph_theme_sync.py -q` green; build throwaway vault and confirm `site/graph.html` + `site/graph-viewer.js` exist and HTML references the sibling. Delete scratch files. **[Agent: general-purpose]**

- [x] **Slice 2: Vendor vis-network for offline / file://**

  > FR2 + FR3 offline half + FR4 with local Vis. Removes CDN dependence for the canvas library.
  - [x] Add `llmwiki/vendor/vis-network.min.js` — pinned **9.1.9** standalone UMD (same bytes as today's unpkg pin) — plus `llmwiki/vendor/NOTICE` with license/attribution. **[Agent: general-purpose]**
  - [x] Replace CDN `<script>` in `HTML_TEMPLATE` with `<script src="vis-network.min.js"></script>`; emit/copy the vendor file next to every `graph.html` (standalone `graph/` and `site/`). Drop SRI on the local tag. **[Agent: general-purpose]**
  - [x] Update tests that assert unpkg/CDN/SRI (`test_graph_viewer.py`, `test_ui_a11y_bundle_473.py`, etc.) to expect the local relative `src` and presence of the emitted vendor file. Offline-notice behavior remains when `vis` is undefined. **[Agent: general-purpose]**
  - [x] Verify: build throwaway vault; assert `site/vis-network.min.js` and `site/graph-viewer.js` exist; HTML has no unpkg URL; run targeted pytest + ruff. Optional: Playwright/file open smoke if cheap — otherwise assert relative tags + file presence. Delete scratch files. **[Agent: general-purpose]**

- [x] **Slice 3: Docs + CHANGELOG**

  > FR6 and any references to CDN/offline in docs.
  - [x] Add `CHANGELOG.md` `[Unreleased]` entry: Knowledge Graph loads companion assets and works offline from the built static site (#127). Update any docs that claim the graph canvas always loads from unpkg or that offline needs a manual host step for vis-network on the graph page. **[Agent: general-purpose]**
  - [x] Verify: changelog grammar matches neighbors; docs references consistent; ruff/pytest still green for touched surface. **[Agent: general-purpose]**

- [x] **Slice 4: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 007-graph-viewer-external-assets` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
