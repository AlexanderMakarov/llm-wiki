# Functional Specification: Spec-first gate for product changes

- **Roadmap Item:** Issue #117 — pull-request check that product-related changes also update AWOS working notes
- **Status:** Completed
- **Author:** AWOS /implement-feature (from #117 + interview)

---

## 1. Overview and Rationale (The "Why")

Maintainers and agents plan future work from written AWOS notes. Today a change request can alter product behaviour, tests, governance docs, or CI workflows without touching those notes, so the written record quietly stops matching the product. Success means every change request that touches the agreed product-related areas also updates something under the project's AWOS notes folder, while requests that only touch exempt areas pass without that requirement. There is no label-based bypass: path filters alone decide when notes are required, and a notes update (or staying outside the armed paths) is how a request passes.

---

## 2. Functional Requirements (The "What")

1. **Armed by path filters.** The check runs its requirement only when the change request touches at least one of: the main product package, shipped integrations, the test suite, GitHub Actions workflow definitions, maintainer governance docs, or reference docs that define CLI/config/lint contracts. Other areas (tutorials, guides, packaging, scripts, examples, and similar) do not arm the check.
   - **Acceptance Criteria:**
     - [x] Given a change request that only edits a tutorial or similar exempt area, when checks run, then this check passes without requiring AWOS notes. _(evidence: `gate_passes(["docs/tutorials/…"])` + acceptance pytest)_
     - [x] Given a change request that edits the main product package (or another armed area) and also updates any AWOS notes file, when checks run, then this check passes. _(evidence: predicates + `tests/test_awos_context_gate*.py`)_

2. **Hard fail when armed and notes missing.** If any armed path changed and no file under the AWOS notes tree changed, the check fails and the log shows a full explanation: what failed, why notes are required, and how to fix (run the feature/fix flow, or update the owning notes to match the change). It does not mention a bypass label.
   - **Acceptance Criteria:**
     - [x] Given a change request that touches an armed path and nothing under AWOS notes, when checks run, then the check fails and the log contains that explanation (and does not offer a label bypass). _(evidence: `print_failure` `::error::` lines; acceptance tests assert no awos-exempt)_

3. **Any notes update satisfies.** Creating or correcting any file under the AWOS notes tree is enough; the check does not require particular note filenames.
   - **Acceptance Criteria:**
     - [x] Given armed paths plus any notes-file change, when checks run, then the check passes. _(evidence: `has_context_change` / `gate_passes`)_

4. **No escape-hatch label.** Labels never clear or skip this check. The workflow does not need to re-run on label changes for this gate.
   - **Acceptance Criteria:**
     - [x] There is no documented or implemented label that makes this check pass when notes are missing. _(evidence: `rg` on workflow + docs; triggers lack labeled/unlabeled)_

5. **Honest branch comparison.** The check judges only files changed on the branch relative to where it split from the base branch, so later unrelated product commits on the base branch do not falsely fail (or pass) this request.
   - **Acceptance Criteria:**
     - [x] Given a branch cut before later base-branch product commits, when this request itself did not change armed paths without notes, then the check passes. _(evidence: pr-lint job uses `git merge-base`; CLI requires `--base`/`--head`)_

6. **Documentation.** Contributors and reviewers can find the rule in the contributing guide, the pull-request checklist, the maintainer review checklist, and the governance-check workflow header comment — including the armed paths and that there is no label bypass.
   - **Acceptance Criteria:**
     - [x] Those four places describe the rule and the armed-path set consistently. _(evidence: CONTRIBUTING, PR template, REVIEW_CHECKLIST Meta, pr-lint header lists six prefixes + no label bypass)_

7. **Contributor-visible notice.** The project changelog records this as an unreleased contributor-facing behaviour change.
   - **Acceptance Criteria:**
     - [x] `CHANGELOG.md` under Unreleased mentions the new check. _(evidence: Unreleased Added bullet for #117)_

---

## 3. Scope and Boundaries

### In-Scope

- New hard pull-request check wired into the existing governance checks
- Path-filter triggers: main product package, shipped integrations, tests, GitHub Actions workflows, maintainer docs, and reference docs
- Clear failure explanation without a bypass label
- Docs in the four places named above plus a changelog entry

### Out-of-Scope

- Validating that notes are well-formed, complete, or match the code
- Requiring specific AWOS artifact names
- A bypass label or re-running checks on label changes for this gate
- Fixing the existing changelog-check quirk about base-branch tips (follow-up)
- Extending the gate to tutorials, guides, scripts, packaging, or examples
