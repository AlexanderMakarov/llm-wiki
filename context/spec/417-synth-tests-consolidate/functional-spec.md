# Functional Specification: Mirror synth unit tests under tests/synth/

- **Roadmap Item:** [test: consolidate synth tests under tests/synth/](https://github.com/AlexanderMakarov/llm-wiki/issues/318) — AWOS spec `417-synth-tests-consolidate`
- **Status:** Approved
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
  - [ ] Given a maintainer opens the tests tree after this change, when they look for synth unit coverage from this batch, then those cases live under the mirrored synth tests tree rather than only as a flat root pile for that batch.
  - [ ] Given a new contributor adds a unit check for a surface already covered by this batch, when they follow coding standards, then the natural place to extend is a module under that mirrored tree.

### 2.2 Behaviour and CI contracts preserved

Moving and consolidating tests must not change what the product does, must not weaken the unit coverage gate, and must not delete cases merely to shrink counts.

- **Acceptance Criteria:**
  - [ ] Given the same inputs exercised by this batch before the move, when the suite runs after the move, then the asserted outcomes for product behaviour are unchanged.
  - [ ] Given CI’s unit coverage gate (87%), when this change’s suite runs, then coverage stays at or above the gate.
  - [ ] Given a reviewer diffs the batch, when they look for deletions, then removed tests are only vacuous, duplicate, or otherwise non-protective cases — not arbitrary cuts toward a percentage target.

### 2.3 #280-style batch hygiene

Within this synth batch only: search existing coverage before adding, merge parallel/acceptance duplicates that assert the same outcome, delete vacuous tests, and give each test or parametrize group a one-sentence behaviour docstring. Usage-limit, interrupt/Ctrl+C drain, and backend mock contracts remain named and explicit after consolidation.

- **Acceptance Criteria:**
  - [ ] Given two modules in the batch that asserted the same behaviour (including overlapping parallel unit vs acceptance slices), when the batch lands, then one protective check remains for that behaviour.
  - [ ] Given a test that asserted nothing useful about product behaviour, when the batch lands, then it is gone.
  - [ ] Given each kept test or parametrize group in the batch, when a reviewer reads it, then a one-sentence behaviour docstring is present.
  - [ ] Given usage-limit, interrupt/Ctrl+C, and backend mock contracts that existed in the batch before the move, when a reviewer searches the mirrored tree, then those contracts are still present as explicit checks (not only implied by a broader test).

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
