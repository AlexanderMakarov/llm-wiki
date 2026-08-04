# Technical Specification: Honest estimate Candidates + end-of-synth summary

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** implement-feature / technical interview
- **GitHub Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/113

---

## 1. High-Level Technical Approach

Keep harvest and estimate math unchanged. Fix presentation and add a post-run summary:

1. Relabel the estimate `Candidates:` block as pre-run state and stop describing it as a preview of the upcoming run.
2. After a successful real `synth` (and the `all --with-synth` path), print a short factual summary: sources synthesized this run, wall duration, and tokens/cost when the Claude CLI returns them via `--output-format json`. Candidates stay on the existing harvest line only (do not duplicate in the end summary).
3. Centralize formatting in a small shared helper so CLI and `all` stay consistent.
4. Validate Claude JSON payloads (`result` required; reject `is_error` / non-success `subtype`) so envelopes are never written as wiki pages.

No new CLI flags, config keys, or runtime dependencies.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

None. Presentation and docs only within the existing CLI / harvest / estimate surfaces (plus Claude CLI stdout parsing for usage).

### Component Breakdown

| Piece | Responsibility | Primary paths |
| --- | --- | --- |
| Pre-run Candidates formatting | Label + pending-sources note for estimate output | `llmwiki/synth/reporting.py` `print_candidates_pre_run`; called from `llmwiki/cli.py` `_synthesize_estimate` |
| End-of-run summary | Print synthesized count, duration, optional token/cost (omit when unknown). No Candidates line | `print_synth_run_summary`; called from `cmd_synthesize` and `llmwiki/pipeline.py` `all --with-synth` after a successful path |
| Claude usage | `--output-format json`; accumulate usage / `total_cost_usd`; validate envelopes | `llmwiki/synth/claude_cli.py`; exposed via `reset_usage` / `take_usage` into the synth summary dict |
| Doc / UI copy | Remove “preview” framing for estimate Candidates | `docs/reference/cli.md`, `docs/cheatsheet.md`, `docs/reference/ui.md`, `docs/UPGRADING.md`, `llmwiki/render/js.py`, `summarize_backlog` docstring |
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
- Keep `run_harvest`’s existing Candidates / review-with line (single Candidates report).
- When the path succeeds, print the end-of-run summary via the helper (count + duration + optional tokens/cost). Do **not** call `summarize_backlog` for a second Candidates print.
- When `--sources-only` skips harvest: print synthesized count + duration (+ usage when known); harvest Candidates line is absent (expected).
- Token / USD lines: from Claude JSON usage when present; never invent figures from `estimate.py` heuristics.

**`llmwiki all --with-synth`:**

- Same wall-clock + end summary after its synth+harvest segment, using the shared helper.

### Data Model / API / Config

No schema, MCP, or config key changes.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** harvest `run_harvest`; `synthesize_new_sessions` return counts (+ optional tokens/cost); Claude CLI JSON shape.
- **Risks & Mitigations:**
  - Duplicate Candidates — mitigated by omitting Candidates from `print_synth_run_summary` (smoke fix).
  - JSON envelope written as a source page — reject missing/`is_error`/non-success payloads with `ClaudeCLIError`.
  - `#81` convention drift — document shared “current/pre-run state” labelling; do not change Corpus/Already-synthesized in this PR.
  - Docs drift — update every “preview” site listed in exploration; add CHANGELOG bullet.

---

## 4. Testing Strategy

- Extend `tests/test_synthesize_estimate.py`: assert `Candidates (pre-run state)` and pending-sources note; assert estimate does not emit the full post-run summary banner.
- CLI/integration coverage for real synth (tmp vault): after synth+harvest, stdout includes synthesized count + duration; exactly one `Candidates:` line (harvest); when usage unknown, no fabricated token/cost lines.
- Cover `--sources-only`: duration/count present; no harvest Candidates.
- Claude CLI unit tests: JSON success accumulates usage; empty/`is_error`/bad subtype raise; plaintext stubs still work.
- Prefer existing pytest fixtures; no new runtime deps.
- Lint/docs: CHANGELOG + reference rows touched by wording.
