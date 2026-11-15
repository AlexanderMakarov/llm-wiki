# Technical Specification: Mirror static-site / render unit tests under tests/render/

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

One PR creates `tests/render/` mirroring `llmwiki/render/` (+ closely related static HTML emitters), moves a **bounded** unit-test batch into that tree (same workflow as #280 → `tests/cli/`), merges duplicates / drops vacuous cases, adds package helpers for `REPO_ROOT`, extends quality-gate / CODING_STANDARDS mentions, and leaves Playwright under `tests/e2e/`. No product behaviour change; 87% unit coverage floor unchanged.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Inclusion criteria (approved)

**In batch (move into `tests/render/`):** modules whose primary contract is static HTML / `llmwiki.render.*` / site chrome emitters named by #315 or tight siblings:

| Current path | Target under `tests/render/` |
|---|---|
| `test_render_split.py` | `test_split.py` (or keep name) |
| `test_render_is_subagent.py` | `test_is_subagent.py` |
| `test_site_chrome_shared.py` | `test_chrome.py` |
| `test_palette_dialog_a11y.py` | `test_palette_a11y.py` |
| `test_palette_indexes.py` | `test_palette_indexes.py` |
| `test_248_palette_match.py` | `test_palette_match.py` (drop digit prefix) |
| `test_documents_tree_filter.py` | merge into palette/js helper module or `test_documents_tree_filter.py` |
| `test_raw_docs_site.py` | `test_raw_docs_site.py` |
| `test_wcag_contrast.py` | `test_wcag_contrast.py` |
| `test_static_site_no_server.py` | `test_static_site.py` |
| `test_candidates_site.py` | `test_candidates_site.py` |
| `test_session_toc.py` | `test_session_toc.py` |
| `test_sessions_index_no_date_dup.py` | `test_sessions_index.py` |
| `test_filter_slug_label.py` | merge into `test_sessions_index.py` if same surface |
| `test_collapse_section.py` | `test_collapse_section.py` |
| `test_chip_contrast.py` | merge into `test_wcag_contrast.py` if duplicate theme of CSS contrast |

**Stay put (this PR):** `test_htmlmd.py` (product `htmlmd`, not site emit — optional later mirror); graph_viewer unit suite (`test_graph_*`) deferred; e2e; CLI; domain acceptance that only incidentally calls `build_site`; `test_build_docs_or_sessions.py` (orchestration).

### 2.2 Package layout

```
tests/render/
  __init__.py          # docstring + @spec: 414-tests-render-mirror / #315
  _paths.py            # REPO_ROOT = parents[2] (cli pattern)
  _js_harness.py       # optional DRY for node extract/run (if ≥2 modules share it)
  test_*.py            # consolidated modules as above
```

Align module names with concerns, not issue numbers. Issue/spec links in module docstrings / `# @spec:`.

### 2.3 Hygiene rules (batch-only)

- Search before merge; one protective check per behaviour; parametrize variants.
- Delete vacuous / tautology / import-path-only asserts (PIT weak patterns).
- One-sentence behaviour docstring per test or parametrize group touched.
- Fix `Path(__file__).parents[N]` after depth change via `_paths.REPO_ROOT`.
- Extend `tests/test_quality_gates.py` + `docs/CODING_STANDARDS.md` to name `tests/render/` like `tests/cli/`.
- AWOS notes under `context/spec/414-tests-render-mirror/`; CHANGELOG only if contributor-visible (layout convention mention if standards change).

### 2.4 Out of product code

No changes to `llmwiki/render/` or `build.py` behaviour — tests and contributor docs/gates only.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** pytest collection of `tests/`; `test_quality_gates`; CODING_STANDARDS; any docs that hardcode old `tests/test_*.py` paths.
- **Potential Risks & Mitigations:**
  - Broken `REPO_ROOT` / fixture paths → shared `_paths.py`; grep `parents\[1\]` in moved files.
  - Coverage dip from over-deletion → delete only vacuous/duplicate; full `--cov` before push.
  - Oversized PR → defer graph/topic sprawl (approved).
  - Cross-test string refs to old module names → grep and update.

---

## 4. Testing Strategy

- `ruff check llmwiki tests scripts`
- `python3 -m pytest tests/render/ -q`
- `python3 -m pytest tests/ -q`
- `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (≥87%)
- `python3 -m pytest tests/test_quality_gates.py -q`

No new harness; no Playwright move; no mutation tooling.
