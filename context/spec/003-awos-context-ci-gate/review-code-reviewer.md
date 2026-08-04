# Code review: #117 AWOS context CI gate

**Scope:** `origin/main...HEAD` plus uncommitted shippable work (excludes `.worktree-vault/`). Worktree: `.claude/worktrees/feat-117-awos-context-ci-gate`.

**Reviewed artifacts:** `tests/awos_context_gate.py`, `tests/test_awos_context_gate.py`, `tests/test_awos_context_gate_acceptance.py`, `.github/workflows/pr-lint.yml` (`awos-context` job), CONTRIBUTING / PR template / REVIEW_CHECKLIST / CHANGELOG / `tests/test_pr_template.py`, and `context/spec/003-awos-context-ci-gate/*`.

**Verdict:** CHANGES REQUESTED

| Severity | Count |
|---|---|
| Critical | 0 |
| Important | 1 |

---

## Important

### 1. FR6 incomplete — workflow header omits the armed-path set (confidence: 90)

**Where:** `.github/workflows/pr-lint.yml` lines 7–9 (header comment for gate #4); acceptance claim in `context/spec/003-awos-context-ci-gate/functional-spec.md` FR6 / AC marked `[x]`.

**Why:** Functional requirement 6 requires the rule in four places **including the armed paths** and no label bypass: contributing guide, PR checklist, maintainer review checklist, and the governance workflow **header comment**. CONTRIBUTING, the PR template, and REVIEW_CHECKLIST Meta all enumerate `llmwiki/`, `integrations/`, `tests/`, `.github/workflows/`, `docs/maintainers/`, `docs/reference/`. The pr-lint header only says:

```text
#   4. AWOS context/ updated when armed product paths change
#      (path filters; no label bypass)
```

That matches the brevity of gates 1–3 stylistically, but it does **not** list the armed-path set. FR6 AC evidence (“pr-lint header”) overstates coverage. Acceptance tests assert the header mentions AWOS / no label bypass, but they do **not** assert the six prefixes appear in the header — so the suite stays green while FR6 stays unmet.

**Fix:** Extend the gate #4 header comment with the same six prefixes used in `ARMED_PREFIXES` / the other three surfaces (one line is enough). Optionally tighten FR6 acceptance tests to require those prefixes in the workflow header text so this cannot regress. Re-check the FR6 evidence note after.

---

## Notes (below reporting threshold; not counted)

- Gate predicates, merge-base wiring (`mb` then `--base`/`--head`), `::error::` failure text, no-label-bypass surfaces, CHANGELOG Unreleased, and 17-box checklist/count wiring look correct; unit + acceptance + `test_pr_template` were green locally under the uncommitted tree.
- `git_changed_paths(..., check=True)` surfaces a raw `CalledProcessError` if git fails instead of a gate-shaped `::error::` — fine for the intended CI wiring; not elevated.
- No security issues found (static annotations, list-form subprocess argv, no secrets, no label bypass).
- No CONTRIBUTING privacy / runtime-deps / hard-wrap violations in the shipping delta. One concern for #117 holds relative to `origin/main` (implementation still uncommitted; committed tip is the #117 spec).
