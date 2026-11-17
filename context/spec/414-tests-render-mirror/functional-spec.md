# Functional Specification: Mirror static-site / render unit tests under tests/render/

- **Roadmap Item:** [test: mirror static site / render tests under tests/render/](https://github.com/AlexanderMakarov/llm-wiki/issues/315) — AWOS spec `414-tests-render-mirror`
- **Status:** Completed
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Contributors and agents who change how the static site is built still hunt behaviour checks across many flat modules at the tests root. The CLI batch already showed that a mirrored folder makes “find existing coverage, merge duplicates, extend one place” practical. This change applies that same layout pass to unit tests that cover static-site / HTML render behaviour, so the next person extending a render surface lands in one tree instead of opening another root-level module.

Success: after this lands, the meaningful unit coverage for that area lives under the mirrored render tests tree; CI still passes the same behavioural and coverage contracts; dead or duplicate cases from that batch are gone; each kept test (or parametrize group) has a one-sentence behaviour docstring.

---

## 2. Functional Requirements (The "What")

### 2.1 Mirrored layout for static-site / render unit tests

Unit tests that exist to protect static-site / HTML render behaviour are consolidated into a `tests/render/` tree (or equivalently named mirror of the render product package), grouped to match render subpackages where that mapping is practical.

- **Acceptance Criteria:**
  - [x] Given a maintainer opens the tests tree after this change, when they look for static-site / HTML render unit coverage from this batch, then those cases live under the mirrored render tests tree rather than only as a flat root pile for that batch. — evidence: 14 `tests/render/test_*.py`; flat batch originals absent; `test_quality_gates` package + modules-exist + no-flat-originals.
  - [x] Given a new contributor adds a unit check for a surface already covered by this batch, when they follow coding standards, then the natural place to extend is a module under that mirrored tree. — evidence: `docs/CODING_STANDARDS.md` names `tests/render/`; quality-gate asserts that mention.

### 2.2 Behaviour and CI contracts preserved

Moving and consolidating tests must not change what the product does, must not weaken the unit coverage gate, and must not delete cases merely to shrink counts.

- **Acceptance Criteria:**
  - [x] Given the same inputs exercised by this batch before the move, when the suite runs after the move, then the asserted outcomes for product behaviour are unchanged. — evidence: `pytest tests/render/` and full `pytest tests/` green after migration (6813 passed).
  - [x] Given CI’s unit coverage gate (87%), when this change’s suite runs, then coverage stays at or above the gate. — evidence: `--cov=llmwiki` **87.34%** (≥87%).
  - [x] Given a reviewer diffs the batch, when they look for deletions, then removed tests are only vacuous, duplicate, or otherwise non-protective cases — not arbitrary cuts toward a percentage target. — evidence: hygiene removed tautology/import-path-only/duplicate chip-contrast and filter-label cases; protective destinations remain under `tests/render/`.

### 2.3 #280-style batch hygiene

Within this render/static-site batch only: search existing coverage before adding, merge duplicates, delete vacuous tests, and give each test or parametrize group a one-sentence behaviour docstring.

- **Acceptance Criteria:**
  - [x] Given two modules in the batch that asserted the same behaviour, when the batch lands, then one protective check remains. — evidence: `test_chip_contrast` → `test_wcag_contrast`; `test_filter_slug_label` → `test_sessions_index`.
  - [x] Given a test that asserted nothing useful about product behaviour, when the batch lands, then it is gone. — evidence: vacuous asserts removed from `test_split` / related modules in hygiene pass.
  - [x] Given each kept test or parametrize group in the batch, when a reviewer reads it, then a one-sentence behaviour docstring is present. — evidence: `test_quality_gates` docstring invariant over `tests/render/`.

---

## 3. Scope and Boundaries

### In-Scope

- One layout migration pass for static-site / render behavioural unit tests into the mirrored render tests tree.
- Deduplication and vacuous-test cleanup inside that batch.
- Docstring hygiene for kept cases in that batch.
- Docs / AWOS notes required by contributor process for this change (no user-facing product behaviour change expected).

### Out-of-Scope

- Relocating Playwright end-to-end tests (they stay in their existing e2e suite).
- Lowering the 87% unit coverage floor.
- Adding a “N% fewer tests” gate or shrinking the suite to hit a count target.
- Further package mirrors (MCP, adapters, etc.) — separate tickets.
- Other roadmap items.
