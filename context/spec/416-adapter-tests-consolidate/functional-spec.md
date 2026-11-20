# Functional Specification: Mirror adapter unit tests under tests/adapters/

- **Roadmap Item:** [test: consolidate adapter tests under tests/adapters/](https://github.com/AlexanderMakarov/llm-wiki/issues/317) — AWOS spec `416-adapter-tests-consolidate`
- **Status:** Completed
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Contributors and agents who change session-source adapters still hunt behaviour checks across many flat modules at the tests root. The CLI, static-site / render, and MCP batches already showed that a mirrored folder makes “find existing coverage, merge duplicates, extend one place” practical. This change applies that same layout pass to unit tests that cover adapter behaviour, so the next person extending an adapter lands in one tree instead of opening another root-level module.

Success: after this lands, the meaningful unit coverage for that area lives under the mirrored adapters tests tree; CI still passes the same behavioural and coverage contracts; dead or duplicate cases from that batch are gone; each kept test (or parametrize group) has a one-sentence behaviour docstring. Per-adapter enable/sync contracts stay explicit — not folded away during consolidation.

---

## 2. Functional Requirements (The "What")

### 2.1 Mirrored layout for adapter unit tests

Unit tests that exist to protect adapter behaviour are consolidated into a `tests/adapters/` tree (or equivalently named mirror of the adapters product package), grouped to match core vs contrib concerns where that mapping is practical.

- **Acceptance Criteria:**
  - [x] Given a maintainer opens the tests tree after this change, when they look for adapter unit coverage from this batch, then those cases live under the mirrored adapters tests tree rather than only as a flat root pile for that batch.
  - [x] Given a new contributor adds a unit check for a surface already covered by this batch, when they follow coding standards, then the natural place to extend is a module under that mirrored tree.

### 2.2 Behaviour and CI contracts preserved

Moving and consolidating tests must not change what the product does, must not weaken the unit coverage gate, and must not delete cases merely to shrink counts.

- **Acceptance Criteria:**
  - [x] Given the same inputs exercised by this batch before the move, when the suite runs after the move, then the asserted outcomes for product behaviour are unchanged.
  - [x] Given CI’s unit coverage gate (87%), when this change’s suite runs, then coverage stays at or above the gate.
  - [x] Given a reviewer diffs the batch, when they look for deletions, then removed tests are only vacuous, duplicate, or otherwise non-protective cases — not arbitrary cuts toward a percentage target.

### 2.3 #280-style batch hygiene

Within this adapter batch only: search existing coverage before adding, merge duplicates (especially shared config/availability/headless contracts), delete vacuous tests, and give each test or parametrize group a one-sentence behaviour docstring. Per-adapter enable/sync contracts remain named and explicit after consolidation.

- **Acceptance Criteria:**
  - [x] Given two modules in the batch that asserted the same behaviour, when the batch lands, then one protective check remains.
  - [x] Given a test that asserted nothing useful about product behaviour, when the batch lands, then it is gone.
  - [x] Given each kept test or parametrize group in the batch, when a reviewer reads it, then a one-sentence behaviour docstring is present.
  - [x] Given per-adapter enable/sync contracts that existed in the batch before the move, when a reviewer searches the mirrored tree, then those contracts are still present as explicit checks (not only implied by a broader test).

---

## 3. Scope and Boundaries

### In-Scope

- One layout migration pass for adapter behavioural unit tests into the mirrored adapters tests tree (batch option 1: unit + shared contracts; not numbered acceptance / watch / docs-currency modules).
- Deduplication and vacuous-test cleanup inside that batch.
- Docstring hygiene for kept cases in that batch.
- Docs / AWOS notes / quality-gate mentions required by contributor process for this change (no user-facing product behaviour change expected).

### Out-of-Scope

- Changing adapter sync/enable semantics (test-only / layout PR).
- Every-PR mutation CI / lowering the 87% unit coverage floor.
- Adding a “N% fewer tests” gate or shrinking the suite to hit a count target.
- Moving numbered acceptance modules (e.g. configurable-adapters acceptance), watch-adapter modules, or docs-currency modules — leave for a follow-up if needed.
- Further package mirrors (e.g. synth topic sprawl) — separate tickets.
- Other roadmap items.
