# Technical Specification: Honest already-synthesized counts on estimate and Home

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** implement-feature / architecture interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/81

---

## 1. High-Level Technical Approach

Honesty-only change to synthesize estimate reporting and the Home Pipeline state widget. Keep the existing **eligible-input** meaning of `corpus` / `synthesized` / `pipeline_rows[*].synthesized`. Stop labelling those quantities as pages or files. Export on-disk `wiki/sources/` page and stub counts from the walk the pipeline already pays for, label them as **current state** (same convention as #113 `Candidates (pre-run state):`), persist them wherever the Home snapshot is refreshed, and teach the widget to show a short note under the files-layer table.

No change to synthesis matching, backlog eligibility (#24), or stale-state reconciliation.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

None. Reporting and UI copy only; same `llmwiki-state.js` / `synth.estimate` / `synth.pipeline` surfaces.

### Data Model / Report Keys

Extend `synthesize_estimate_report` (`llmwiki/synth/estimate.py`) return value with:

| Key | Meaning |
| --- | --- |
| `source_pages_on_disk` | Count of `.md` pages under `wiki/sources/` from `_scan_source_page_keys` (`|real ∪ stub|`, or `len(real) + len(stub)` given stubs already exclude reals) |
| `source_page_stubs` | Stub subset count from the same scan |

Computation: call `_scan_source_page_keys(wiki_sources_dir)` once (or reuse a caller-provided scan if already in hand). Do **not** invent a second filesystem walk when the estimate path already has `discover_synth_source_keys` — prefer changing the call site to use `_scan_source_page_keys` and pass both sets, or call `_scan` and derive `discovered = real`.

Existing keys stay: `corpus`, `corpus_sessions`, `corpus_docs`, `synthesized`, `synthesized_sessions`, `synthesized_docs`.

### Persist for Home

When writing `synth.estimate` in `_synthesize_estimate` (`llmwiki/cli.py`), store `source_pages_on_disk` and `source_page_stubs` alongside existing estimate fields.

When `refresh_synth_pending` and build’s pipeline backfill refresh the Home snapshot (`llmwiki/synth/pipeline.py` / `llmwiki/build.py`), recompute the same two counts via `_scan_source_page_keys` and write them onto `synth.estimate` (create/merge the estimate dict if missing) so Home does not wait for an explicit `--estimate` run.

### CLI Contracts (stdout)

In `_synthesize_estimate` print block (replace lines that currently say `sources (sessions + docs)` / `pages in wiki/sources/`):

1. `Corpus:                {N:>6} eligible sources ({S} sessions + {D} docs)`
2. `Already synthesized:   {n:>6} of {N} eligible sources`
3. New helper in `llmwiki/synth/reporting.py` (mirror `print_candidates_pre_run`): `Source pages (current state): {P} on disk ({stubs} stubs)`

Do not change cost lines, New/Breakdown, eligibility notes, or Candidates pre-run block.

### Home Widget (`llmwiki/render/js.py`)

- Replace files-layer caption so the unit is **eligible sources** (inputs handled by shell commands), not “Files” as the measure of the counts. Prefer wording like: `Eligible sources: Raw → To synthesize → Synthesized (by agent). Handled by shell commands.` (exact string locked in implementation/tests).
- Column header `Synthesized` may stay if caption/tooltip makes the unit clear; if a one-word header remains ambiguous, prefer `Synthesized (sources)` only if tests stay readable — caption honesty is mandatory.
- Immediately under the files-layer table (before Knowledge layer), render a muted note when `synth.estimate.source_pages_on_disk` is present: `Source pages (current state): P on disk (S stubs)`. Omit the note when keys are absent (legacy snapshots).
- Table cell math unchanged (input counts; chunked doc = 1).

### Docs / Product Notes

- `docs/reference/ui.md` — Pipeline Files layer description must match eligible-sources + current-state page note.
- `CHANGELOG.md` under Unreleased — user-visible honesty fix citing #81.
- `context/product/roadmap.md` — check off #81 item when delivered (same PR).
- Any other `context/` product note required by the AWOS context CI gate for touched product paths.

### Tests

- `tests/test_synthesize_estimate.py` — assert new Corpus / Already synthesized strings; assert Source pages current-state line; assert absence of `pages in wiki/sources/`.
- `tests/test_state_widget.py` — caption no longer claims “Files layer” as the unit of counts; note HTML when estimate keys present; omit when absent.
- Prefer a small focused acceptance module if that matches prior #113 style (`test_113_acceptance.py` pattern) — optional as long as criteria are covered.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** Estimate → state sidecar → Home JS; `refresh_synth_pending` / build backfill must stay compatible with missing keys (forward-only additive fields).
- **Risks & Mitigations:**
  - Users mistaking “Already synthesized N” for page count after the fix — mitigated by `of M eligible sources` plus the separate current-state page line.
  - Double-counting stubs in P — use `_scan_source_page_keys` contract (`stub - real`) so P = len(real)+len(stub).
  - Stale page note if only estimate wrote keys historically — mitigated by also refreshing on pipeline snapshot updates.
  - Do not “fix” matched-OR-state math in this PR — that would change cost estimates; out of functional scope.

---

## 4. Testing Strategy

- Unit/CLI: golden substring assertions on `_synthesize_estimate` / report helpers with a tiny vault (real page + stub + one pending raw).
- Widget: string containment in emitted JS for caption + note branch.
- No browser E2E required if JS strings and state shape are covered (same bar as prior Home widget tests).
- Manual smoke (operator): live vault `synth --estimate` then Home/build — after verify gate.
