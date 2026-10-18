# Functional Specification: Codex CLI session Tokens capture

- **Roadmap Item:** [GitHub #324](https://github.com/AlexanderMakarov/llm-wiki/issues/324) — feat(codex_cli): investigate and capture native token usage
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

People who use Codex CLI alongside other agents want the Analytics **Tokens** figure to include real Codex session usage when the store provides it. Today Codex is treated as not captured, so those sessions do not strengthen the aggregate total and the coverage story still says Codex is missing.

Success: when Codex records measurable usage, sync and the existing historical Tokens migrate carry it into the shared Tokens totals and coverage; when usage is absent, nothing is invented as zero; reasoning-only output is excluded from Tokens when Codex reports it separately; docs and the Tokens coverage hint tell the truth.

---

## 2. Functional Requirements (The "What")

- **Capture measured Codex usage into the shared Tokens total**
  - Prefer native measured usage from the Codex session store over estimates.
  - Map into the four shared categories (input, cache creation, cache read, output) without double-counting overlapping categories (e.g. cache as a subset of input).
  - **Reasoning:** when Codex reports reasoning output separately from ordinary output, **do not count reasoning toward Tokens**. Count only ordinary (non-reasoning) output when that separation is available. If separation is unavailable, do not invent a split — document the limitation and keep those sessions honest (missing/partial rather than fabricated).
  - Do not sum repeated cumulative counters as if each were a new charge.
  - **Acceptance Criteria:**
    - [ ] Given a Codex session with measured usage (and separable ordinary vs reasoning output), when Tokens are recorded, then four-category totals update and reasoning is excluded from output.
    - [ ] Given repeated cumulative usage updates in one session, when totals are recorded, then the session contributes once at the correct cumulative amount (no double-count).
    - [ ] Given only occupancy or plan-limit percentages and no measured usage categories, when metrics run, then no fabricated Tokens usage is written.

- **Missing data stays missing**
  - Unavailable usage must not appear as measured zero.
  - Coverage and docs must state Codex support honestly (included when measured; gaps called out).
  - **Acceptance Criteria:**
    - [ ] Given a Codex session with no usable usage, when Analytics/coverage is viewed, then that session is not presented as measured zero usage.
    - [ ] Given Codex capture is shipped, when the user opens the Tokens coverage hint, then Codex is no longer described as “not captured by the token pipeline yet” (measured/known or equivalent honest wording).

- **Preserve agent identity and session-day attribution**
  - Keep enough agent and last-activity date information for approximate rolling week/month breakdowns later (#322).
  - Approximate attribution by session last-activity day (already the shared rule) is enough; precise per-event time buckets are not required here.
  - **Acceptance Criteria:**
    - [ ] Given a measured Codex session, when stored, then it is labeled as Codex and attributed under the shared last-activity day rule.

- **Document verified fields and historical options**
  - Document which native fields are verified (and any unavailable data), with synthetic or redacted fixtures as evidence.
  - Where the original Codex store remains available, describe practical historical backfill (existing Tokens migrate / re-sync path).
  - **Acceptance Criteria:**
    - [ ] Contributor/user-facing upgrade or adapter notes list verified Codex usage fields, gaps, and how to backfill historical sessions when stores remain.
    - [ ] Tests or fixtures demonstrate the mapping and the no-double-count / no-fabricated-zero rules.

---

## 3. Scope and Boundaries

### In-Scope

- Codex CLI → shared Tokens pipeline (sync + existing historical migrate).
- Reasoning excluded from Tokens when separately reported.
- Coverage hint / docs / CHANGELOG / UPGRADING updates for the new support.
- Investigation notes and fixtures for verified native fields.

### Out-of-Scope

- #322 expandable per-agent / week / month Analytics UI.
- #321 Home token metric redesign.
- Billing or plan-percentage dashboards; treating context-window occupancy as Tokens.
- Redesigning the shared session Tokens usage store (#325 already shipped).
- Cursor IDE and other agents’ capture (separate tickets).
