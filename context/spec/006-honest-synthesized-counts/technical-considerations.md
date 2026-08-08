# Technical Specification: Honest already-synthesized counts on estimate and Home

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** implement-feature / architecture interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/81

---

## 1. High-Level Technical Approach

Honesty-only change to synthesize estimate reporting and the Home Pipeline state widget. Keep the existing **eligible-input** meaning of `corpus` / `synthesized` / `pipeline_rows[*].{raw,pending,synthesized}`. Stop labelling those quantities as pages or files. Export on-disk `wiki/sources/` **file** counts from one walk (`scan_wiki_sources_disk`), attach them as `pipeline_rows[*].on_disk` (plus CLI mix keys), and teach the widget a fifth **On disk** column. Smoke feedback dropped the under-table note.

No change to synthesis matching, backlog eligibility (#24), or stale-state reconciliation.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

None. Reporting and UI copy only; same `llmwiki-state.js` / `synth.estimate` / `synth.pipeline` surfaces.

### Data Model / Report Keys

`scan_wiki_sources_disk` (`llmwiki/synth/pipeline.py`) — one `rglob("*.md")` walk excluding `_`-prefixed names — returns real/stub **keys** (for matching) and exclusive **file** category counts. `_scan_source_page_keys` is a thin wrapper over that scan.

Extend `synthesize_estimate_report` (`llmwiki/synth/estimate.py`) return value with:

| Key | Meaning |
| --- | --- |
| `source_pages_on_disk` | Count of `.md` files under `wiki/sources/` (file count, not unique `source_file` keys) |
| `source_page_stubs` | Stub file subset |
| `source_pages_sessions` | Non-stub session-page files (`source_file` starts with `raw/sessions/`) |
| `source_pages_docs` | Non-stub doc-page files (`raw/docs/` prefix or `raw-doc` in tags) |
| `source_pages_other` | Remaining non-stub files (when >0, also a pipeline Other row) |
| `pipeline_rows[*].on_disk` | Per-row file count; Stubs row `kind: "stubs"` / label `"Stubs"`; Other row when needed |

Session-page files attribute to agents via `detect_agent_label(meta)`. Stubs are exclusive (never also counted in agent/docs On disk). Include agent/Documents rows when `raw>0 OR on_disk>0`.

Existing keys stay: `corpus`, `corpus_sessions`, `corpus_docs`, `synthesized`, `synthesized_sessions`, `synthesized_docs`.

### Persist for Home

When writing `synth.estimate` in `_synthesize_estimate` (`llmwiki/cli.py`), store the source_pages_* file-count keys alongside existing estimate fields. Pipeline rows (with `on_disk`) persist via the existing estimate/pipeline snapshot.

When `refresh_synth_pending` and build’s pipeline backfill refresh the Home snapshot, recompute the same counts via the estimate report’s single scan and merge onto `synth.estimate` so Home does not wait for an explicit `--estimate` run.

### CLI Contracts (stdout)

In `_synthesize_estimate` print block:

1. `Corpus:                {N:>6} eligible sources ({S} sessions + {D} docs)`
2. `Already synthesized:   {n:>6} of {N} eligible sources`
3. `print_source_pages_current_state`: `Source pages (current state): {T} on disk ({Sess} sessions + {D} docs + {X} stubs)` (+ ` + {O} other` when O>0)

Do not change cost lines, New/Breakdown, eligibility notes, or Candidates pre-run block. Drop any unique-key wording that framed P as `|real ∪ stub|`.

### Home Widget (`llmwiki/render/js.py`)

- Caption stays eligible sources: `Eligible sources: Raw → To synthesize → Synthesized (by agent). Handled by shell commands.`
- Five columns: Source | Raw | To synthesize | Synthesized | On disk.
- Stubs / Other rows: Raw / To synthesize / Synthesized render as muted "—"; On disk is numeric. Total On disk sums the file column (including stubs/other).
- **Remove** the under-table `sourcePagesNote` / "Source pages (current state): …" block.
- Input-column cell math unchanged (chunked doc = 1).

### Docs / Product Notes

- `docs/reference/ui.md` — Pipeline Eligible sources description: On disk column + Stubs; no under-table note.
- `CHANGELOG.md` under Unreleased — user-visible honesty fix citing #81 (smoke redesign).
- `context/product/roadmap.md` — check off #81 item when delivered (same PR).
- Any other `context/` product note required by the AWOS context CI gate for touched product paths.

### Tests

- `tests/test_synthesize_estimate.py` — assert new Corpus / Already synthesized strings; assert Source pages mix line; assert file counts (not unique keys); assert `on_disk` / Stubs row.
- `tests/test_state_widget.py` — On disk column present; `sourcePagesNote` / under-table note string absent; stubs/other dash labelling.
- `tests/test_81_acceptance.py` — print helper + stale-vault divergence with new CLI wording.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** Estimate → state sidecar → Home JS; `refresh_synth_pending` / build backfill must stay compatible with missing keys (forward-only additive fields).
- **Risks & Mitigations:**
  - Users mistaking “Already synthesized N” for page count after the fix — mitigated by `of M eligible sources` plus the On disk column / CLI mix line.
  - Unique-key vs file-count regression — tests force two pages sharing one `source_file` and assert `source_pages_on_disk == 2+`.
  - Double-counting stubs into agent On disk — stubs classified first and exclusive.
  - Do not “fix” matched-OR-state math in this PR — that would change cost estimates; out of functional scope.

---

## 4. Testing Strategy

- Unit/CLI: golden substring assertions on `_synthesize_estimate` / report helpers with a tiny vault (real pages + stub + docs via tags).
- Widget: string containment in emitted JS for On disk column + absence of under-table note.
- No browser E2E required if JS strings and state shape are covered (same bar as prior Home widget tests).
- Manual smoke (operator): live vault `synth --estimate` then Home/build — after verify gate (~612 md / ~378 sessions / ~234 raw-doc / 0 stubs).
