# Code review — #127 graph viewer external assets

**Scope:** `git diff origin/main...HEAD` plus uncommitted/untracked work in worktree `feat-127-graph-viewer-external-js` (graph viewer externalization + vendored vis-network).

**Reviewed:** `llmwiki/graph.py`, `llmwiki/render/graph_viewer.py`, `llmwiki/vendor/*`, tests (including `tests/test_127_acceptance.py`), CHANGELOG/docs/reference updates, `pyproject.toml` packaging, related test/docs touch-ups.

**Verdict:** Request changes — one Critical packaging bug blocks shipped/pip installs; one Important UX/docs mismatch on the offline notice.

---

## Critical

### 1. Vendored `vis-network.min.js` is not included in the PyPI wheel — `write_html` will crash for non-checkout installs

- **Confidence:** 98
- **Where:** `pyproject.toml` `[tool.setuptools.package-data]` (currently `llmwiki = ["py.typed"]` only); consumers: `llmwiki/graph.py` (`VIS_NETWORK_VENDOR`, `write_html` → `shutil.copy2`)
- **Why it matters:** `write_html` copies `Path(__file__).parent / "vendor" / "vis-network.min.js"` into every emitted graph. Repo checkouts and editable installs see that file on disk. A confirmed `python3 -m build --wheel` of this worktree produces a wheel that contains `llmwiki/render/graph_viewer.py` but **no** `llmwiki/vendor/` paths (`has vis? False`). A `pip install` from that wheel therefore leaves `VIS_NETWORK_VENDOR` missing; `shutil.copy2` raises `FileNotFoundError` on every `llmwiki graph` / `llmwiki build` that emits HTML — breaking the user-visible feature this PR advertises for normal installs.
- **Guideline:** CONTRIBUTING “ship what users need”; feature promises offline companions from build. Setuptools only ships listed `package-data` (non-`.py` files are not included by default).
- **Fix:** Extend package data, e.g. `llmwiki = ["py.typed", "vendor/*"]` (or explicit filenames). Add a regression test that either builds a wheel and asserts `llmwiki/vendor/vis-network.min.js` is present, or uses `importlib.resources`/`files("llmwiki")` against an installed layout. Optionally fail `write_html` with a clear message if the vendor file is absent.

---

## Important

### 2. Offline notice cannot fire when `graph-viewer.js` itself is missing — docs/CHANGELOG overclaim

- **Confidence:** 90
- **Where:** `llmwiki/graph.py` HTML (`#offline-notice`, `<script src="graph-viewer.js">` with no `onerror`); `llmwiki/render/graph_viewer.py` (only place that adds `.show`); docs: `docs/reference/ui.md`, CHANGELOG `#127` bullet (“inline offline notice remains when a companion script is missing”)
- **Why it matters:** The only code path that shows `#offline-notice` runs inside `graph-viewer.js` (`typeof vis === 'undefined'`). If that companion fails to load (deleted sibling, bad deploy, partial copy), `vis` may already be defined and `main()` never runs — blank canvas, notice stays hidden. That contradicts CONTRIBUTING “Never fail silently in the browser” and the PR’s own FR/docs claim that missing companions surface the notice. Missing `vis-network.min.js` is handled; missing `graph-viewer.js` is not.
- **Fix:** Detect viewer load failure in the HTML (e.g. `onerror` on the `graph-viewer.js` tag, or a tiny inline watchdog that shows the notice if `window.__llmwikiGraphViewerLoaded` is unset after scripts run), and keep the existing `vis` check for the library. Align docs once that works for both companions.

---

## Notes (below reporting threshold — not blocking)

- Dead `.replace("__KIND_OTHER_LABEL__", …)` on `HTML_TEMPLATE` is now a no-op (placeholder lives only in `GRAPH_VIEWER_JS`); harmless clutter.
- Dropping CDN SRI for a locally emitted sibling is acceptable given a pinned vendor file + NOTICE; supply-chain trust moves to the committed vendor blob (reviewable).
- Size budgets (`len(GRAPH_VIEWER_JS)` vs UTF-8 bytes) agree for this ASCII-only script; ~29.8 kB is under 32 kB.
- Docs + CHANGELOG + `context/` updates look aligned with CONTRIBUTING for a user-visible change; no new runtime PyPI deps (vendoring is correct).

---

## Summary counts

| Severity | Count |
|----------|------:|
| Critical | 1 |
| Important | 1 |
| Total (≥80 confidence) | 2 |

**Verdict: request changes** — fix wheel `package-data` (and cover it in tests) before merge; harden or honest-doc the offline notice for a missing first-party viewer script.
