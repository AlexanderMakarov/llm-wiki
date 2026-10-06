# Functional Specification: Quality gates for useful, fast tests (with proof rewrites)

- **Roadmap Item:** [test: shrink the unit test suite to tests that protect behavior](https://github.com/AlexanderMakarov/llm-wiki/issues/280) — AWOS spec `280-shrink-test-suite`
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

The automated suite is large and slow, and many checks do not earn their keep. Raw test count is a weak signal. What matters is whether tests protect real product behavior, how long the suite takes, and whether measured coverage of product code stays honest.

The main delivery is lasting quality gates so agents and people writing new tests are steered toward useful coverage. Architectural cleanups and first test rewrites are proofs that those gates work — delivered together with the gates in the first change set — not a separate afterthought.

Primary outcomes: coding standards and a testing-expert agent as the main testing guardrail; coverage measurement with a CI fail below the measured baseline (87%) on the **unit** suite only; agnix locally and in CI for both the shipped user agent kit and this repository’s inner agentic tooling (important agnix findings are shown to the maintainer to fix now or postpone as GitHub issues); a closed experiment loop on the CLI unit-test surface (guardrails → apply to CLI batch → scoped mutation → measure what mutation still finds that guardrails missed) with mutation results in the first change set. Mutation is a **measurement** of remaining gap, not a mandate to write every missing test. After those results, the maintainer decides whether to file mutation testing as an important follow-up or skip it. Soft count targets stay informational. Delivery-flow SDLC commands stay as they are — test rules live in standards and the testing expert, not a regenerated flow. Agent instructions live once under the Claude tooling tree; other agent folders point at them via symlinks or short links, not duplicated mirrors.

Baseline measured for this work: about 87.33% line coverage of product code. The CI threshold is **87%**.

---

## 2. Functional Requirements (The "What")

### 2.1 Coverage measurement and CI gate (primary)

Every pull request measures how much of the product code the suite exercises. CI fails if overall coverage falls below **87%**. Maintainers can see coverage by product-code area in CI logs (no required coverage essay in the pull request body).

- **Acceptance Criteria:**
  - [ ] Given a pull request on the default CI path, when tests run, then a coverage report for product code is produced and visible in the CI run.
  - [ ] Given coverage would fall below 87%, when CI finishes, then the required check fails.
  - [ ] Given coverage stays at or above 87%, when CI finishes, then this gate does not fail solely because the number of tests changed.
  - [ ] Given a maintainer opens contributor or maintainer docs, when they look for the threshold and how to measure locally, then both are documented.

### 2.2 Skipped-test cleanup (primary)

Permanently skipped tests that only document removed commands or dead surfaces are removed. Environment-conditional skips (optional tools not installed) may remain when they have a clear reason; the audit lists them and the policy.

- **Acceptance Criteria:**
  - [ ] Given tests marked skip because a subcommand or surface was removed, when the first guardrails-and-proofs change lands, then those dead skipped tests are gone.
  - [ ] Given remaining skips, when a maintainer reads the audit or standards, then the policy for keeping env-conditional skips is clear.

### 2.3 Coding standards, testing-expert, skills, and agnix (primary)

A coding-standards document (agents load it) covers: coverage and usefulness over raw count; prefer fast equivalent checks; anti-patterns from the ticket; no wall-clock timing tests outside deliberate perf; no format-mirroring; test isolation; product behavior must not change in cleanup diffs; consolidate tests into package-mirrored modules rather than one new test module per feature; one-sentence behavior docstring per test or parametrize group (steered by known weak-test patterns such as untested side effects, missing boundaries, unchecked return values).

The **testing-expert** agent (Claude and Cursor) is the main delivery-time testing guardrail. Feature and bug SDLC commands are not regenerated for this work.

New or updated agent rules and skills from this work must be valid under agnix. Agnix runs **locally and in CI** for (1) the shipped user agent kit and (2) this repository’s inner agentic tooling (skills, agents, commands as scoped). Canonical agent files live under the Claude tooling tree; Cursor/Kiro surfaces use symlinks or short markdown links — not duplicated kept-in-sync copies.

- **Acceptance Criteria:**
  - [ ] Given an agent starts work that adds or edits tests, when they follow project instructions, then the standards and testing-expert rules are discoverable without reading the whole original ticket.
  - [ ] Given the short agent-facing contributing pointers, when they summarize testing, then they point at this standard without conflicting rules.
  - [ ] Given the new or updated skills or rules produced by this work, when agnix is run on that surface, then they pass (or any intentional waiver is documented).
  - [ ] Given CI on a pull request, when agnix jobs run, then both the shipped agent kit and the agreed inner agentic paths are validated (scoped paths, not a noisy full-repo demo scan) **or** the first run’s important findings were shown to the maintainer, who chose which to fix in this change and which to postpone as GitHub issues.
  - [ ] Given Cursor or Kiro tooling folders, when they reference testing-expert or new test skills, then they symlink or link to the Claude canonical file rather than duplicating the body.

### 2.4 Test layout and naming (primary convention; migration by follow-up issues)

Tests should live in a tree that mirrors product packages under `llmwiki/`, not as a flat list of hundreds of modules in the tests root. New work extends the mirrored module for that package; it does **not** create a new top-level test module per feature or issue number. Issue or spec linkage stays in module docstrings or `@spec` comments, not in filenames like `test_<digits>_…`.

Bulk moves for CLI, static site, MCP, and other areas are tracked as **separate GitHub issues** with bounded scope. The first change set ships guardrails plus enough proof rewrites (including skip cleanup and at least one mirrored-package consolidation) to show the gates work — that first change set may be large but must remain reviewable as one concern: “gates + proofs.”

- **Acceptance Criteria:**
  - [ ] Given coding standards and testing-expert after this lands, when an agent adds tests for a package, then they are told to extend the mirrored tests module for that package rather than add `test_<issue>_acceptance.py` at the tests root.
  - [ ] Given the first guardrails-and-proofs change, when a reviewer looks for proof, then dead skips are removed and at least one package slice has been consolidated into the mirrored layout.
  - [ ] Given remaining flat or numbered modules, when follow-up work is planned, then separate scoped GitHub issues exist (or are filed) for major areas rather than one mega-move.

### 2.5 CLI experiment loop including mutation (primary, first PR)

The first change set runs a closed loop on **CLI** unit tests and product code. The goal of the loop is **better guardrails**, not a complete extra test suite written from mutation survivors.

1. Update guardrails → run them against the CLI test batch → fix/consolidate that batch from guardrail suggestions.
2. Run temporary scoped mutation on the same CLI product surface.
3. Classify survivors: how many weak or missing checks did mutation find that the guardrails did **not** catch? Tune guardrails where a rule hole is clear and cheap. Do **not** treat “write every missing unit test” as success. Guardrails cannot catch everything; the experiment exists to **measure that remainder**.
4. Present mutation results to the maintainer with an explicit question: file a follow-up issue for mutation testing as an **important** enhancement, or skip mutation as an ongoing practice.

TDD is encouraged as a way to avoid weak tests; it is not a mandatory process gate for this ticket.

- **Acceptance Criteria:**
  - [ ] Given the first pull request (or the experiment report in chat), when a maintainer reads the mutation results, then they see how many survivor classes the guardrails missed, and any guardrail tweaks made — not a dump of newly invented tests as the primary outcome.
  - [ ] Given those results, when the maintainer is asked, then they can choose to file mutation testing as an important follow-up issue or to skip it.

### 2.6 Proof cleanups with the first gates delivery (co-shipped on CLI)

The first pull request delivers gates and the CLI experiment together: remove dead skips (at least in the CLI batch; prefer all “subcommand removed” skips); consolidate CLI unit tests into the mirrored layout; apply guardrail-driven strengthening on that batch; include the mutation **gap report**; do not change product-facing behavior. Other areas get separate follow-up issues.

- **Acceptance Criteria:**
  - [ ] Given the first pull request, when a reviewer checks behavior, then user-visible and CLI-visible outcomes for the same inputs are unchanged.
  - [ ] Given proof work in that pull request, when coverage is checked, then CI stays at or above 87%.
  - [ ] Given CLI tests after the pull request, when a maintainer looks at layout, then CLI coverage lives under the mirrored tests tree rather than only as a flat root pile for that batch.

### 2.7 Contributor Testing guideline

Testing section aligns with standards, coverage measurement (87%), layout/consolidation rules, and skip policy; parked draft on the docs branch for this issue is taken or adapted.

- **Acceptance Criteria:**
  - [ ] Given a contributor opens Testing, when they look for how to add a test, coverage expectations, and layout rules, then those are present.

### 2.8 Reporting

Coverage lives in CI logs via the coverage gate. Agents do not pad pull request descriptions with coverage essays. Usefulness is enforced by standards: one-sentence behavior docstring per test or parametrize group, and testing-expert review against weak-test patterns.

- **Acceptance Criteria:**
  - [ ] Given a pull request that only needs the coverage gate, when CI is green, then reviewers can see coverage in CI without a mandatory PR coverage section.
  - [ ] Given new or rewritten tests in this series, when a reviewer opens them, then each test or parametrize group states the behavior it protects in one sentence.

---

## 3. Scope and Boundaries

### In-Scope

- Primary: CODING_STANDARDS; testing-expert under `.claude/` with symlink/link pointers from other agent folders; coverage measurement and CI fail under **87%** (unit suite only); skipped-test audit and removal of dead skips; layout/consolidation convention; agnix locally and in CI for **shipped agent kit and inner agentic tooling**, with important findings triaged (fix now vs GitHub issues); CLI experiment loop with **mutation results presented for a keep-or-skip decision**; modest guardrail tuning from that experiment (not exhaustive test-writing from survivors)
- First PR: gates + CLI consolidation/proofs + mutation experiment results
- Follow-up GitHub issues for non-CLI area migrations (site, MCP, …)
- Contributor Testing guideline with concrete coverage commands
- TDD mentioned as guidance only

### Out-of-Scope

- Regenerating delivery-flow / feature / bug SDLC commands for this ticket
- CI fail solely because collected-test count rose
- Using mutation survivors as a mandate to write all missing unit tests
- Installing every-PR mutation CI before the maintainer’s keep-or-skip decision
- Duplicated kept-in-sync copies of agent files across `.cursor` / `.kiro`
- Large production rewrites or any change that alters product behavior
- One mega-PR moving all flat tests
- Creating a new top-level test module per feature as the ongoing pattern
- Mandatory TDD process gate
- Closing the GitHub issue from the delivery flow
