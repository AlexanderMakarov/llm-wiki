# Functional Specification: Mirror MCP unit tests under tests/mcp/

- **Roadmap Item:** [test: consolidate MCP tests under tests/mcp/](https://github.com/AlexanderMakarov/llm-wiki/issues/316) — AWOS spec `415-mcp-tests-consolidate`
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Contributors and agents who change the MCP server still hunt behaviour checks across many flat modules at the tests root. The CLI and static-site / render batches already showed that a mirrored folder makes “find existing coverage, merge duplicates, extend one place” practical. This change applies that same layout pass to unit tests that cover MCP behaviour, so the next person extending an MCP surface lands in one tree instead of opening another root-level module.

Success: after this lands, the meaningful unit coverage for that area lives under the mirrored MCP tests tree; CI still passes the same behavioural and coverage contracts; dead or duplicate cases from that batch are gone; each kept test (or parametrize group) has a one-sentence behaviour docstring. Contracts that pin timeout, lock, and add-as-CLI-proxy behaviour stay explicit — not folded away during consolidation.

---

## 2. Functional Requirements (The "What")

### 2.1 Mirrored layout for MCP unit tests

Unit tests that exist to protect MCP server / tool behaviour are consolidated into a `tests/mcp/` tree (or equivalently named mirror of the MCP product package), grouped to match MCP concerns where that mapping is practical.

- **Acceptance Criteria:**
  - [ ] Given a maintainer opens the tests tree after this change, when they look for MCP unit coverage from this batch, then those cases live under the mirrored MCP tests tree rather than only as a flat root pile for that batch.
  - [ ] Given a new contributor adds a unit check for a surface already covered by this batch, when they follow coding standards, then the natural place to extend is a module under that mirrored tree.

### 2.2 Behaviour and CI contracts preserved

Moving and consolidating tests must not change what the product does, must not weaken the unit coverage gate, and must not delete cases merely to shrink counts.

- **Acceptance Criteria:**
  - [ ] Given the same inputs exercised by this batch before the move, when the suite runs after the move, then the asserted outcomes for product behaviour are unchanged.
  - [ ] Given CI’s unit coverage gate (87%), when this change’s suite runs, then coverage stays at or above the gate.
  - [ ] Given a reviewer diffs the batch, when they look for deletions, then removed tests are only vacuous, duplicate, or otherwise non-protective cases — not arbitrary cuts toward a percentage target.

### 2.3 #280-style batch hygiene

Within this MCP batch only: search existing coverage before adding, merge duplicates, delete vacuous tests, and give each test or parametrize group a one-sentence behaviour docstring. Timeout, lock, and add-as-CLI-proxy contracts remain named and explicit after consolidation.

- **Acceptance Criteria:**
  - [ ] Given two modules in the batch that asserted the same behaviour, when the batch lands, then one protective check remains.
  - [ ] Given a test that asserted nothing useful about product behaviour, when the batch lands, then it is gone.
  - [ ] Given each kept test or parametrize group in the batch, when a reviewer reads it, then a one-sentence behaviour docstring is present.
  - [ ] Given timeout, lock, and add-as-CLI-proxy contracts that existed in the batch before the move, when a reviewer searches the mirrored tree, then those contracts are still present as explicit checks (not only implied by a broader test).

---

## 3. Scope and Boundaries

### In-Scope

- One layout migration pass for MCP behavioural unit tests into the mirrored MCP tests tree.
- Deduplication and vacuous-test cleanup inside that batch.
- Docstring hygiene for kept cases in that batch.
- Docs / AWOS notes / quality-gate mentions required by contributor process for this change (no user-facing product behaviour change expected).

### Out-of-Scope

- Changing MCP wire protocol or tool semantics (test-only / layout PR).
- Every-PR mutation CI / lowering the 87% unit coverage floor.
- Adding a “N% fewer tests” gate or shrinking the suite to hit a count target.
- Further package mirrors (adapters, synth, etc.) — separate tickets (#317, #318, …).
- Other roadmap items.
