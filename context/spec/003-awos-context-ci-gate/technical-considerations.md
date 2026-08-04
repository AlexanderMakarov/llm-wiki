<!--
This document describes HOW to build the feature at an architectural level.
It is NOT a copy-paste implementation guide.
-->

# Technical Specification: Spec-first gate for product changes

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Completed
- **Author(s):** AWOS /implement-feature (from #117 + interview)

---

## 1. High-Level Technical Approach

Add a fourth hard-fail job to the existing PR governance workflow. Path classification and the pass/fail decision live in a single Python module under `tests/` so the same predicates are unit-tested and invoked from CI. The job diffs the PR via `git merge-base` (honest branch-only file set), arms when any armed prefix matches, and requires at least one path under `context/`. Failure emits multi-line `::error::` guidance with no label bypass. Document the rule on the same four surfaces as the other governance gates, plus a CHANGELOG Unreleased entry. Do not change the CHANGELOG job’s existing base-tip diff behaviour in this PR.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

- No change to the llmwiki runtime package or Python dependencies.
- Governance CI grows from three jobs to four in `.github/workflows/pr-lint.yml`.
- Contributor/process docs and the PR template gain a matching checklist/rule.

### Component Breakdown

| Path | Responsibility |
|---|---|
| `tests/awos_context_gate.py` | Single source of armed path prefixes, `context/` satisfaction rule, CLI entry (`--base`, `--head` or equivalent) that lists changed files via `git diff --name-only`, exits 0/1, prints `::error::` / quiet success |
| `tests/test_awos_context_gate.py` | Unit tests over the pure path-list predicates (and light CLI/smoke as needed) |
| `.github/workflows/pr-lint.yml` | New job `awos-context` (“AWOS context updated”): `actions/checkout@v7` with `fetch-depth: 0`; compute merge-base from `github.event.pull_request.base.sha` and `head.sha`; invoke `python3 tests/awos_context_gate.py …`; update header comment to list gate 4 |
| `CONTRIBUTING.md` | Non-negotiable + pre-merge checklist row; keep box-count consistent with template tests |
| `.github/PULL_REQUEST_TEMPLATE.md` | Pre-merge checklist row for this gate |
| `docs/maintainers/REVIEW_CHECKLIST.md` | `## Meta` bullet |
| `CHANGELOG.md` | `## [Unreleased]` contributor-facing note |
| `tests/test_pr_template.py` | Adjust only if checklist box count derivation requires it |

### Logic / Algorithm

1. `changed = git diff --name-only $(git merge-base $base $head) $head`
2. If no path matches armed prefixes → exit 0 (no special log text required).
3. If any path matches `^context/` → exit 0.
4. Else → print full `::error::` explanation (spec-first flow; update notes; no label escape) and exit 1.

**Armed prefixes (constants in the module):**

- `llmwiki/`
- `integrations/`
- `tests/`
- `.github/workflows/`
- `docs/maintainers/`
- `docs/reference/`

**Satisfied-by:** any path under `context/`.

### Explicit non-changes

- No `awos-exempt` label; do not add `labeled` / `unlabeled` to the workflow triggers for this gate.
- Do not switch the existing `changelog` or `runtime-deps` jobs to merge-base in this PR.
- Do not validate content or specific AWOS filenames under `context/`.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** GitHub Actions `pull_request` events; repo must keep `contents: read`. Branch protection may require adding the new check’s display name once (operational note for maintainers / PR body).
- **Broader arming than original issue text:** tests, reference/maintainer docs, and workflows now arm the gate — intentional per functional interview; more PRs will need a `context/` touch.
- **Drift risk:** path lists live in one module; docs must list the same set in prose — keep them updated together in this PR.
- **Self-gating:** this feature’s own PR touches armed paths and `context/spec/003-…`, so it should pass its own gate once the job exists.

---

## 4. Testing Strategy

- Unit tests: exempt-only paths pass; armed + `context/` pass; armed without `context/` fail; edge cases (only `docs/tutorials/`, only `scripts/`, nested paths under armed trees).
- Workflow wiring verified when this PR’s own checks run (armed paths + context present).
- No end-to-end GitHub Actions simulation beyond the live PR; no new runtime deps.
