# Functional Specification: Mirror synth unit tests under tests/synth/

- **Roadmap Item:** [test: consolidate synth tests under tests/synth/](https://github.com/AlexanderMakarov/llm-wiki/issues/318) — AWOS spec `417-synth-tests-consolidate`
- **Status:** Completed
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Contributors and agents who change synthesis (turning raw sessions and documents into wiki source pages, choosing backends, estimating cost, guarding duplicates and stubs) still hunt behaviour checks across many flat modules at the tests root. The CLI, static-site / render, MCP, and adapter batches already showed that a mirrored folder makes “find existing coverage, merge duplicates, extend one place” practical. This change applies that same layout pass to unit tests that cover synthesis behaviour, so the next person extending a synth surface lands in one tree instead of opening another root-level module.

Success: after this lands, the meaningful unit coverage for that area lives under the mirrored synth tests tree; CI still passes the same behavioural and coverage contracts; dead or duplicate cases from that batch are gone; each kept test (or parametrize group) has a one-sentence behaviour docstring. Usage-limit, interrupt/Ctrl+C, and backend mock contracts stay explicit — not folded away during consolidation.

---

## 2. Functional Requirements (The "What")

### 2.1 Mirrored layout for synth unit tests

Unit tests that exist to protect synthesis pipeline / backend / estimate / path-guard behaviour are consolidated into a `tests/synth/` tree (or equivalently named mirror of the synth product package), grouped to match major synth concerns (backends, pipeline, harvest-adjacent interaction) where that mapping is practical. An existing reporting module already under that tree stays and is extended by this batch rather than left as a one-off island.

- **Acceptance Criteria:**
  - [x] Given a maintainer opens the tests tree after this change, when they look for synth unit coverage from this batch, then those cases live under the mirrored synth tests tree rather than only as a flat root pile for that batch. — evidence: 14 `tests/synth/test_*.py` after the move; stay-put `tests/test_synthesize_overview_safety.py` left at root by review/tech stay-put list (not enforced by a filename-inventory pytest); layout via `test_synth_unit_tests_live_under_mirrored_synth_package` + CODING_STANDARDS DOC assert.
  - [x] Given a new contributor adds a unit check for a surface already covered by this batch, when they follow coding standards, then the natural place to extend is a module under that mirrored tree. — evidence: `docs/CODING_STANDARDS.md` names `tests/synth/`; `test_coding_standards_doc_names_floor_and_cli_layout` DOC assert; `test_synth_unit_tests_live_under_mirrored_synth_package` layout gate.

### 2.2 Behaviour and CI contracts preserved

Moving and consolidating tests must not change what the product does, must not weaken the unit coverage gate, and must not delete cases merely to shrink counts.

- **Acceptance Criteria:**
  - [x] Given the same inputs exercised by this batch before the move, when the suite runs after the move, then the asserted outcomes for product behaviour are unchanged. — evidence: `pytest tests/synth/ tests/test_quality_gates.py` green and full `pytest tests/` green (exit 0) after migration.
  - [x] Given CI’s unit coverage gate (87%), when this change’s suite runs, then coverage stays at or above the gate. — evidence: `--cov=llmwiki` **87.33%** (≥87%, gate reached).
  - [x] Given a reviewer diffs the batch, when they look for deletions, then removed tests are only vacuous, duplicate, or otherwise non-protective cases — not arbitrary cuts toward a percentage target. — evidence: hygiene removed 3 exact-duplicate parallel unit cases already covered by CLI acceptance (`test_in_flight_pages_stay_within_the_worker_count`, `test_every_result_line_carries_its_position`, `test_a_placeholder_never_replaces_a_real_page_under_concurrency`); no count-target cuts.

### 2.3 #280-style batch hygiene

Within this synth batch only: search existing coverage before adding, merge parallel/acceptance duplicates that assert the same outcome, delete vacuous tests, and give each test or parametrize group a one-sentence behaviour docstring. Usage-limit, interrupt/Ctrl+C drain, and backend mock contracts remain named and explicit after consolidation.

- **Acceptance Criteria:**
  - [x] Given two modules in the batch that asserted the same behaviour (including overlapping parallel unit vs acceptance slices), when the batch lands, then one protective check remains for that behaviour. — evidence: three duplicate unit outcomes dropped; acceptance counterparts retained under `test_parallel_acceptance.py`.
  - [x] Given a test that asserted nothing useful about product behaviour, when the batch lands, then it is gone. — evidence: no vacuous `assert True` found; only exact-duplicate outcome cases removed.
  - [x] Given each kept test or parametrize group **touched in this batch's hygiene pass**, when a reviewer reads it, then a one-sentence behaviour docstring is present. — evidence: docstring hygiene on the touched parallel cases; pre-existing gaps on untouched moved modules remain review-enforced per CODING_STANDARDS / #316 layout-migration precedent (no suite docstring inventory).
  - [x] Given usage-limit, interrupt/Ctrl+C, and backend mock contracts that existed in the batch before the move, when a reviewer searches the mirrored tree, then those contracts are still present as explicit checks (not only implied by a broader test). — evidence: concurrent usage / `reset_usage` in `test_parallel.py` + claude usage parsers; interrupt drain + exit-130 paths in `test_parallel.py` / `test_run_summary.py`; DummySynthesizer / stubbed backends retained.

---

## 3. Scope and Boundaries

### In-Scope

- One layout migration pass for synth behavioural unit tests into the mirrored synth tests tree (backends, pipeline, estimate, path/dedup/stub/numeric-slug guards, run-summary / parallel unit coverage from the flat `test_synth*` / `test_synthesize*` batch named in the issue).
- Deduplication and vacuous-test cleanup inside that batch (including parallel vs acceptance overlap).
- Docstring hygiene for kept cases in that batch.
- Docs / AWOS notes / quality-gate mentions required by contributor process for this change (no user-facing product behaviour change expected).

### Out-of-Scope

- Rewriting synthesis product behaviour (backends, pipeline semantics, estimate math).
- Every-PR mutation CI / lowering the 87% unit coverage floor.
- Adding a “N% fewer tests” gate or shrinking the suite to hit a count target.
- Moving CLI-handler-only synth tests that already live under the CLI mirror, or overview-safety checks that protect the static-site build overview path rather than the synth package (leave those where they belong unless they are exact duplicates of a moved case).
- Other roadmap items / further package mirrors.
