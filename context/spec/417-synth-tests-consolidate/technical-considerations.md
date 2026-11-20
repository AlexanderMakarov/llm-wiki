# Technical Specification: Mirror synth unit tests under tests/synth/

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

One PR extends the existing `tests/synth/` mirror (already home to `test_reporting.py` from #280) by moving the bounded flat `tests/test_synth*.py` / `tests/test_synthesize*.py` unit batch into that tree (same workflow as #280 → `tests/cli/`, #315 → `tests/render/`, #316 → `tests/mcp/`, #317 → `tests/adapters/`), merges exact-duplicate parallel unit vs acceptance cases / drops vacuous asserts only when clearly non-protective, keeps usage-accounting, interrupt/Ctrl+C drain, and backend mock contracts as explicit named tests, extends quality-gate / CODING_STANDARDS mentions to name `tests/synth/` alongside the other mirrors, and leaves product synth behaviour untouched. No product behaviour change; 87% unit coverage floor unchanged.

Keep the existing `tests/synth/__init__.py` package docstring (pre-#318 mirror island) — do not delete it solely for parity with adapters' "no ticket-only init" rule. Prefer `from tests._paths import REPO_ROOT` over fragile `Path(__file__).parents[N]` after the move.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Inclusion criteria (proposed)

**In batch (move into `tests/synth/`):**

| Current path | Target under `tests/synth/` |
|---|---|
| `test_synth_backends_shared.py` | `test_backends_shared.py` |
| `test_synth_claude_cli.py` | `test_claude_cli.py` |
| `test_synth_cursor_cli.py` | `test_cursor_cli.py` |
| `test_synth_pipeline.py` | `test_pipeline.py` |
| `test_synth_raw_docs.py` | `test_raw_docs.py` |
| `test_synth_dedup_guard.py` | `test_dedup_guard.py` |
| `test_synth_stub_guard.py` | `test_stub_guard.py` |
| `test_synth_numeric_slug.py` | `test_numeric_slug.py` |
| `test_synthesize_estimate.py` | `test_estimate.py` |
| `test_synthesize_path.py` | `test_path.py` |
| `test_synth_run_summary.py` | `test_run_summary.py` |
| `test_synth_parallel.py` | `test_parallel.py` |
| `test_synth_parallel_acceptance.py` | `test_parallel_acceptance.py` |
| `test_reporting.py` (already present) | stays |

**Stay put (this PR):**

| Path | Why |
|---|---|
| `test_synthesize_overview_safety.py` | Protects `llmwiki.build.synthesize_overview` guards, not `llmwiki/synth/` package behaviour (functional out-of-scope). |
| `test_ollama_backend.py` | Outside the issue's `test_synth*` / `test_synthesize*` glob; optional follow-up. |
| `tests/cli/test_synth.py` | Already under CLI mirror. |
| Product code under `llmwiki/synth/` | No behaviour change. |

### 2.2 Package layout

```
tests/synth/
  __init__.py                 # existing — keep
  test_reporting.py           # existing — keep
  test_backends_shared.py
  test_claude_cli.py
  test_cursor_cli.py
  test_pipeline.py
  test_raw_docs.py
  test_dedup_guard.py
  test_stub_guard.py
  test_numeric_slug.py
  test_estimate.py
  test_path.py
  test_run_summary.py
  test_parallel.py
  test_parallel_acceptance.py
```

Align module names with concerns, not issue numbers. Issue/spec links in module docstrings / `# @spec: 417-synth-tests-consolidate`.

**Path fixes required:** `test_synthesize_estimate.py` and `test_synth_parallel_acceptance.py` use `Path(__file__).resolve().parents[1]` for repo root — under `tests/synth/` that becomes wrong; switch to `tests._paths.REPO_ROOT` (or `parents[2]`). Grep all moved files for `parents[` / `__file__`.

### 2.3 Hygiene rules (batch-only)

- Search before merge; one protective check per behaviour when two modules assert the **same** outcome (especially overlapping parallel unit vs `test_parallel_acceptance` CLI slices — keep CLI end-to-end acceptance for operator-visible guarantees; drop only exact-duplicate unit outcomes already covered by acceptance or vice versa when truly identical).
- Keep **usage accounting** (`take_usage` / concurrent accumulation / reset), **interrupt/Ctrl+C drain** (`interrupted`, exit 130 / harvest-on-interrupt), and **backend mock** (`DummySynthesizer` / stubbed child-process runners — no live Claude/Cursor/Ollama network) contracts as **explicit** named tests (ticket non-negotiable).
- Delete vacuous / tautology / import-path-only asserts only when clearly non-protective; do not delete to hit a count target.
- One-sentence behaviour docstring per test or parametrize group touched.
- Grep and update docstring / docs / acceptance pointers that hardcode old flat paths (`tests/test_synth_*.py`, `tests/test_synthesize_*.py`). Historical CHANGELOG path mentions stay.
- Extend `tests/test_quality_gates.py` + `docs/CODING_STANDARDS.md` to name `tests/synth/` like `tests/cli/` / `tests/render/` / `tests/mcp/` / `tests/adapters/`. Layout gate: directory exists with `test_*.py` modules. Do **not** add a hard-coded inventory of migrated filenames (CODING_STANDARDS: tests assert product behaviour, not the edit).
- AWOS notes under `context/spec/417-synth-tests-consolidate/`; CHANGELOG — prefer editing the existing Unreleased testing/standards / mirror-layout bullets to add #318 / `tests/synth/` rather than a separate “synth tests moved” entry.

### 2.4 Out of product code

No changes to `llmwiki/synth/` behaviour — tests and contributor docs/gates only.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** pytest collection of `tests/`; `test_quality_gates`; CODING_STANDARDS; acceptance / docs modules that cite flat `test_synth*` paths.
- **Potential Risks & Mitigations:**
  - Broken `REPO_ROOT` in estimate / parallel-acceptance subprocess tests → use `tests._paths.REPO_ROOT`; grep `parents[` in moved files.
  - Coverage dip from over-deletion → delete only vacuous/exact-duplicate; full `--cov` before push.
  - Losing usage / interrupt / backend-mock contracts in a merge → keep those tests named and present under parallel / claude_cli / run_summary modules.
  - Oversized PR → batch is bounded to the table in §2.1; do not pull stay-put modules.
  - Cross-test string refs to old module names → grep and update.

---

## 4. Testing Strategy

- `ruff check llmwiki tests scripts`
- `python3 -m pytest tests/synth/ -q`
- `python3 -m pytest tests/ -q`
- `python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (≥87%)
- `python3 -m pytest tests/test_quality_gates.py -q`

No new harness; no Playwright move; no mutation tooling.
