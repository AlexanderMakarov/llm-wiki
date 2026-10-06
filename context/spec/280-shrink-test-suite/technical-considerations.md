# Technical Specification: Quality gates for useful, fast tests (with proof rewrites)

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

One first PR delivers **guardrails + a closed CLI experiment loop** (including **mutation results**), then follow-up GitHub issues handle other product areas.

**Experiment loop (local, then reported to the maintainer):**

1. Land / update guardrails (CODING_STANDARDS, testing-expert, CONTRIBUTING, cov gate, agnix).
2. Run them against a **CLI-focused batch** of unit tests.
3. Fix / consolidate that batch from **guardrail** suggestions (mirror under `tests/` for CLI; delete dead skips touching CLI).
4. Run **temporary scoped mutation** on the same CLI product surface.
5. Investigate survivors to **measure the gap**: how many bad/weak checks did mutation find that guardrails missed? Tune guardrails where a hole is clear. Do **not** treat filling the suite from survivors as the goal (skills/agents cannot catch everything).
6. Present results and ask: file mutation testing as an **important** follow-up issue, or skip it as ongoing practice.

CLI is the experiment substrate (easy to test, low-level), not a later ticket.

Runtime stays `markdown`-only. Coverage, agnix, and mutation tooling are CI/dev/optional only.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Coverage gate

| Item | Choice |
|---|---|
| Tool | `pytest-cov` (CI + `[project.optional-dependencies] dev` only) |
| Scope | `source = ["llmwiki"]` |
| Which tests feed the gate | **Default unit invocation** — same as today’s `ci.yml` lint-and-test: `pytest tests/` with existing `addopts` (`--ignore=tests/e2e`) |
| Threshold | `[tool.coverage.report] fail_under = 87` in `pyproject.toml` (baseline ~87.33%) |
| CI | Install `pytest-cov`; run `python -m pytest tests/ --cov=llmwiki --cov-report=term-missing` (no second `-q`) |

#### Why e2e stays out of this coverage number (unless we change it)

Today:

| Fact | Detail |
|---|---|
| Unit CI (`ci.yml`) | Always runs `pytest tests/` with `--ignore=tests/e2e` in `addopts` |
| E2E CI (`.github/workflows/e2e.yml`) | **Separate** workflow; Playwright + pytest-bdd; **path-filtered** (build/render/viz/e2e/…), push to main with those paths, or `workflow_dispatch` — **not every PR** |
| Duration | Job timeout 15m; recent green run ~**2–3 minutes** wall clock after cache (browser install dominates cold runs) |
| Intent | Comment in workflow: keep slow browser work off the fast unit suite |

If we **included** e2e in the 87% gate without running e2e on every PR, the measured coverage would **jump or drop depending on whether e2e ran** — unstable gate. Running full e2e on every PR for coverage would slow every change and still mostly exercises built HTML/JS in the browser, not a clean map onto `llmwiki/` line coverage.

**Decision:** keep the **87% gate on the unit suite only**; document that e2e is a separate quality gate. Optional later (out of this PR unless asked): a second informational cov report on the e2e workflow only (not the merge-blocking 87% number).

### 2.2 Local docs — CONTRIBUTING coverage details

CONTRIBUTING §Testing must spell out, not just “note 87%”:

```bash
# Everyday unit suite (fast; e2e ignored via pyproject addopts)
python3 -m pytest tests/

# Same suite + coverage (what CI gates at 87%)
python3 -m pip install -e '.[dev]'   # includes pytest-cov once added
python3 -m pytest tests/ --cov=llmwiki --cov-report=term-missing

# Optional: HTML report for local browsing
python3 -m pytest tests/ --cov=llmwiki --cov-report=html
# open htmlcov/index.html

# E2E is separate (needs [e2e] extras + Playwright browsers); not part of the 87% gate
python3 -m pip install -e '.[e2e]'
python3 -m playwright install chromium
python3 -m pytest tests/e2e/
```

Also document: threshold lives in `pyproject.toml` as `fail_under = 87`; baseline was ~87.33% when measured for #280; dropping below 87 fails CI; raising the floor later is a deliberate follow-up.

### 2.3 Skipped-test policy

| Kind | Action |
|---|---|
| `@pytest.mark.skip(reason="… subcommand removed")` | **Delete** |
| Env / optional tool skips | Keep when justified; document |
| Empty-input skips that green without exercising code | Delete or rewrite when touching those files |

### 2.4 Coding standards

`docs/CODING_STANDARDS.md` (canonical, under `.claude` discovery pointers): usefulness > count; coverage ≥87% on unit gate; consolidate into mirrored modules; no new one-module-per-feature / `test_<digits>_*.py`; one-sentence behavior docstring; weak-test patterns ([PIT](https://pitest.org/weak_tests/)); no wall-clock asserts outside deliberate slow perf; isolation; behavior-preserving cleanups; TDD encouraged; experiment loop for local batches; mutation as a **gap measurement** after guardrails, not a default every-PR job until the maintainer decides.

CONTRIBUTING stays human-facing and points at CODING_STANDARDS + the commands above.

### 2.5 testing-expert — single source under `.claude/`

- **Canonical file:** `.claude/agents/testing-expert.md` (update in place with #280 rules).
- **Do not** maintain a duplicate “kept-in-sync mirror” body under `.cursor/` or `.kiro/`.
- **Pointers:** prefer **symlink** from `.cursor/agents/testing-expert.md` → `../../.claude/agents/testing-expert.md` (and likewise for any new skill) if the tool loads symlinks; if a surface cannot follow symlinks, use a **short stub markdown** that only links to the `.claude` path (no duplicated rules).
- Same pattern for new test-usefulness skills/rules: author once under `.claude/`, link/symlink elsewhere.
- Allowlist / git: ensure symlink or stub is force-allowlisted like other `.cursor/agents/**` entries.

### 2.6 Agnix — user kit + inner repo tooling

| Surface | Local | CI |
|---|---|---|
| User-facing kit `llmwiki/agent_kit/**` | `agnix` scoped to kit | Job/step (pins agnix; #290) |
| Inner repo agentic tooling (`.claude/skills`, `.claude/agents`, `.claude/commands` as appropriate; Cursor/Kiro stubs that are real content) | Same tool, documented command(s) | CI job/step that lints those paths (may start with error-severity only; waiver list documented) |

Full-repo `agnix .` including demo vault noise stays out of CI. Scope paths deliberately.

**First run triage:** if agnix reports important findings (errors that would block agents loading skills/commands, broken frontmatter, dangerous names, etc.), **stop and show them to the maintainer** before silently fixing everything. Ask: fix in this change, or postpone as GitHub issues. Cosmetic/warning-only noise can be listed with a recommended default (waive vs fix).

### 2.7 CLI experiment batch (first PR proofs + mutation)

**In the first PR**, for CLI:

1. Apply guardrails to the CLI unit-test batch (files that exercise `llmwiki/cli.py` and closely related CLI helpers — consolidate into mirrored layout under e.g. `tests/cli/` rather than many root modules).
2. Delete dead skips that live in that batch (e.g. removed observability subcommands in `test_cli_observability.py`).
3. Strengthen weak tests / add behavior docstrings on touched tests.
4. Run **scoped mutation** (e.g. mutmut) against the CLI product module(s) touched (`llmwiki/cli.py` and any tiny helpers the batch owns).
5. Classify survivors vs what guardrails already cover. **Tune guardrails** only where a cheap, general rule would have caught the class of miss. Do **not** bulk-write unit tests from the survivor list as the experiment’s success criterion.
6. Write results under `context/spec/280-shrink-test-suite/` (counts, examples of missed classes, guardrail tweaks). **Ask the maintainer** whether to file mutation testing as an **important** follow-up issue or skip it. Do not add every-PR mutation CI unless they choose that.

### 2.8 Follow-up GitHub issues (after first PR)

Separate issues for non-CLI areas (static site/render, MCP, adapters, synth, …) — same experiment loop optional per area. Not blocking the first PR.

### 2.9 CHANGELOG / context

Unreleased notes for: coverage CI 87%, CODING_STANDARDS, testing-expert updates, agnix CI (kit + inner tooling), CLI test consolidation + mutation experiment results pointer. Spec dir satisfies AWOS context gate.

---

## 3. Impact and Risk Analysis

### System Dependencies

- CI unit job slightly slower with coverage
- Agnix CI needs pinned action/CLI (Node or binary)
- Mutation run is heavy — **local / one-shot in first PR**, not every PR by default
- Symlinks: verify Cursor/Kiro resolve them; fall back to stub links

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Mutation makes first PR slow to author | Scope mutants to `llmwiki/cli.py` (and minimal helpers); time-box; record partial results if full kill-list is huge |
| `fail_under = 87` tight after CLI rewrite | Keep behavior; only delete dead skips; if coverage dips, restore with tests that guardrails already demand — not a mutation-driven test dump |
| Agnix on all of `.claude/` noisy | First run: report important findings and ask fix-now vs postpone issues; do not block on demo/AWOS vendored trees |
| Symlinks unsupported on a tool | Stub markdown with link to `.claude` path |

---

## 4. Testing Strategy

- Unit CI green with `--cov` and `fail_under = 87`
- Agnix CI green on kit + agreed inner paths
- CLI batch consolidated; dead skips in batch gone; behavior docstrings on touched tests
- **Mutation experiment executed for CLI surface; gap vs guardrails reported; maintainer asked keep-or-skip**
- No product behavior change

### Checklist

- [ ] `fail_under = 87` enforced in CI (unit suite)
- [ ] CONTRIBUTING documents exact cov / e2e commands and 87% floor
- [ ] Dead “subcommand removed” skips deleted (at least those in CLI batch; prefer all such skips in-repo)
- [ ] CLI unit tests consolidated into mirrored `tests/` layout for CLI
- [ ] CODING_STANDARDS + CONTRIBUTING pointers + testing-expert updated under `.claude/` with symlink/stub pointers from `.cursor`/`.kiro`
- [ ] Agnix runnable locally and in CI for `llmwiki/agent_kit` **and** inner agentic tooling paths
- [ ] **Mutation experiment on CLI area run; report how many/which classes guardrails missed; modest guardrail tweaks only; ask maintainer whether to file mutation as an important issue or skip it**
- [ ] Agnix first-run important findings shown to maintainer (fix in this PR vs postpone issues) before treating CI as the silent auto-fix list
- [ ] Behavior docstrings on touched tests
- [ ] Follow-up area issues filed for non-CLI migrations
