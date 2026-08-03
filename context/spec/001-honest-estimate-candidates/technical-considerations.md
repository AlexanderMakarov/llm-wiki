# Technical Specification: Honest estimate Candidates + end-of-synth summary

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** implement-feature / technical interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/113

---

## 1. High-Level Technical Approach

Keep harvest and estimate math unchanged. Fix presentation and add a post-run summary:

1. Relabel the estimate `Candidates:` block as pre-run state and stop describing it as a preview of the upcoming run.
2. After a successful real `synth` (and the `all --with-synth` path), print a short factual summary: sources synthesized this run, wall duration, post-harvest backlog via existing `summarize_backlog`, omitting token/cost lines until backends report usage.
3. Centralize formatting in a small shared helper so CLI and `all` stay consistent.

No new CLI flags, config keys, or runtime dependencies.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

None. Presentation and docs only within the existing CLI / harvest / estimate surfaces.

### Component Breakdown

| Piece | Responsibility | Primary paths |
| --- | --- | --- |
| Pre-run Candidates formatting | Label + pending-sources note for estimate output | New small helper (suggested: `llmwiki/synth/reporting.py` or adjacent to existing synth CLI helpers); called from `llmwiki/cli.py` `_synthesize_estimate` |
| End-of-run summary | Print synthesized count, duration, optional token/cost (omit when unknown), post-harvest `summarize_backlog` Candidates | Same helper module; called from `cmd_synthesize` and `llmwiki/pipeline.py` `all --with-synth` after harvest succeeds |
| Doc / UI copy | Remove “preview” framing for estimate Candidates | `docs/reference/cli.md`, `docs/cheatsheet.md`, `docs/reference/ui.md`, `docs/UPGRADING.md`, `llmwiki/render/js.py` (Home copy), `summarize_backlog` docstring, related CLI comments |
| CHANGELOG | User-visible note under Unreleased | `CHANGELOG.md` |

### Logic / Algorithm

**Estimate path (`args.estimate` → `_synthesize_estimate`):**

- Continue calling `summarize_backlog` as today.
- Print header as `Candidates (pre-run state):` (retain existing counts / min-refs / distribution / “generate with” guidance).
- Add one clarifying line that sources still pending synthesis are not reflected in this figure.
- Do **not** print the new end-of-run summary on estimate.

**Real synth path (`cmd_synthesize`):**

- Record `time.monotonic()` when the real run begins (after estimate/check early returns).
- Keep existing progress and one-liner (`Scanned … synthesized …`).
- Keep `run_harvest`’s existing “stubs written this pass” line (different metric — written vs backlog).
- When harvest runs and completes successfully, call `summarize_backlog` and print the end-of-run summary via the helper.
- When `--sources-only` skips harvest: print synthesized count + duration; **omit** Candidates from the end summary (harvest did not run; do not pretend post-harvest backlog).
- Token / USD lines: omit for now (backends return text only; do not invent figures from `estimate.py` heuristics).

**`llmwiki all --with-synth`:**

- Same wall-clock + end summary after its synth+harvest segment, using the shared helper.

### Data Model / API / Config

No schema, MCP, or config key changes.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** `candidates_harvest.summarize_backlog` / `harvest_targets`; `synthesize_new_sessions` return counts; optional Home site rebuild only if docs/widget copy changes require a local visual check (copy strings in `js.py` are enough for CI).
- **Risks & Mitigations:**
  - Dual Candidates lines (harvest “written” vs summary “backlog”) — mitigate with clear summary wording (“backlog now” / post-run state).
  - `#81` convention drift — document shared “current/pre-run state” labelling; do not change Corpus/Already-synthesized in this PR.
  - Docs drift — update every “preview” site listed in exploration; add CHANGELOG bullet.

---

## 4. Testing Strategy

- Extend `tests/test_synthesize_estimate.py`: assert `Candidates (pre-run state)` (or approved string) and pending-sources note when estimate includes the Candidates block; assert estimate does not emit the full post-run summary banner.
- Add CLI/integration coverage for real synth (tmp vault): after synth+harvest, stdout includes synthesized count, a duration figure, and Candidates consistent with `summarize_backlog`; when usage unknown, no fabricated token/cost lines.
- Cover `--sources-only`: duration/count present; Candidates end-summary absent.
- Prefer existing pytest fixtures; no new runtime deps.
- Lint/docs: CHANGELOG + reference rows touched by wording.
