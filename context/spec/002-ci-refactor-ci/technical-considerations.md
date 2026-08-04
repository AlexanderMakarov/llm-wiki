# Technical Specification: CI refactor — Node 24 actions, Python 3.12-only matrix, drop Claude-in-CI

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** implement-feature flow (issue #116)

---

## 1. High-Level Technical Approach

Mechanical maintenance of GitHub Actions YAML, package classifiers, and contributor/maintainer docs. No changes under `llmwiki/` or product runtime behavior. Ship sections A–C of issue #116 in a single PR on `feat/116-ci-refactor-ci`.

Specialist note: `github-ci-packaging` was not hired; this document was drafted from workflow inventory + action release notes. No new hire required for this change.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture Changes

None in the product. CI orchestration under `.github/workflows/` is updated in place.

### Action pin policy

Use floating major tags (`@vN`), not SHA pins (except for existing SHA-pinned third parties we are **not** changing, e.g. `pypa/gh-action-pypi-publish`).

| Action | From | To |
| --- | --- | --- |
| `actions/checkout` | `@v4` | `@v7` |
| `actions/setup-python` | `@v5` / `@v6` | `@v7` (workflow pins; see `action.yml` exception below) |
| `actions/setup-node` | `@v4` | `@v7` |
| `actions/upload-artifact` | `@v4` | `@v7` |
| `actions/download-artifact` | `@v4` | `@v8` |
| `actions/configure-pages` | `@v5` | `@v6` |
| `actions/upload-pages-artifact` | `@v4` | `@v5` (composite that nested Node-20 `upload-artifact@v4`; `@v5` nests Node-24 `@v7`) |
| `peter-evans/create-pull-request` | `@v7` | `@v8` |
| `gitleaks/gitleaks-action` | `@v2` | `@v3` |
| `docker/metadata-action` | `@v5` | `@v6` |
| `docker/login-action` | `@v3` | `@v4` |
| `docker/setup-buildx-action` | `@v3` | `@v4` |
| `docker/setup-qemu-action` | `@v3` | `@v4` |

**Artifact pairing:** every `upload-artifact` and `download-artifact` use in the repo must move together. `release.yml` builds in one job and downloads in `publish` / `sign` / `github-release` — keep `@v7` / `@v8` as a matched pair. Inputs used today are `name` and `path` only (compatible).

**Published composite (`action.yml`):** leave `actions/setup-python@v6` — already `node24`, and bumping to `@v7` would change the published consumer surface (self-hosted runners older than Actions Runner v2.327.1) without serving this PR's Node-20 goal. Out of the approved CI plan.

**Out of scope (do not bump):** actions already verified `node24` with no Nested Node-20 children, or third parties we are not refreshing now (e.g. `actions/cache@v5`, `actions/github-script@v9`, `actions/deploy-pages@v5`, `lychee-action` composite with no Node child, SHA-pinned PyPI publish, `docker/build-push-action@v7` already node24). Earlier drafts wrongly treated "composite" and `docker/*` as node24-safe without checking nested/`runs.using` — composite actions inherit whatever their nested `uses:` declare; several `docker/*` majors at the old pins were still `node20`. Those are now in the bump table above for this PR.

### Workflow deletions

Delete:

- `.github/workflows/claude.yml`
- `.github/workflows/claude-code-review.yml`

Post-change audit: `rg 'claude-code-action|CLAUDE_CODE_OAUTH_TOKEN' .github/` must be empty. PR body instructs a maintainer to remove the orphan repo secret in Settings if present (no API secret deletion in this PR).

Leave `ANTHROPIC_API_KEY` / synthesis-backend docs alone. Do not rewrite historical CHANGELOG mentions of Claude workflows.

### Python matrix and metadata

- `.github/workflows/ci.yml` — `python-version: ["3.12"]` only.
- `pyproject.toml` — remove classifier `Programming Language :: Python :: 3.13`. Keep `requires-python = ">=3.12"` and `target-version = "py312"`.
- Docs: `CONTRIBUTING.md` (two matrix mentions), `docs/architecture.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/REVIEW_CHECKLIST.md` (replace stale `3.9 + 3.12` with `3.12`).
- `CHANGELOG.md` under `## [Unreleased]` — include the user-visible classifier drop.

### Files touched (inventory)

- All `.github/workflows/*.yml` that still pin the table above (including but not limited to `ci.yml`, `e2e.yml`, `gitleaks.yml`, `pr-lint.yml`, `link-check.yml`, `release.yml`, `agents-e2e.yml`, `agents-healer.yml`, `pages.yml`, `docker-publish.yml`, `regen-screenshots.yml`, plus any other matches from `rg`).
- Delete the two Claude workflow files.
- `pyproject.toml`, `CHANGELOG.md`, and the four doc paths above.
- Version-pin tests: `tests/test_ci_workflow.py`, `tests/test_editorconfig_lychee.py` (assert floating `@vN`, not a hardcoded major).
- Embedded YAML in `docs/maintainers/playwright-agents-bootstrap.md` (keep aligned with agents workflows).
- Do **not** bump `action.yml`'s `setup-python` past `@v6` (see exception above).
- Process-doc nits: `context/product/delivery-flow.md` and aligned `.claude/commands/implement-feature.md` / `fix-bug.md` (Claude-in-CI removed).

---

## 3. Impact and Risk Analysis

- **System Dependencies:** GitHub-hosted runners; PyPI OIDC release path; gitleaks on personal account (no `GITLEAKS_LICENSE` required — confirmed in v3 README).
- **Potential Risks & Mitigations:**
  - **Artifact round-trip breakage** after upload/download major bump — mitigate by pairing majors; use default inputs; verify via PR CI jobs that upload/download in-run, and note that full `release.yml` tag publish cannot be exercised without a version tag (dry-run/document residual risk).
  - **download-artifact@v8** defaults hash mismatch to hard fail — acceptable for same-workflow artifacts on GitHub-hosted runners.
  - **gitleaks@v3** license surprise — mitigated by docs check (org-only).
  - **Review size** — one PR preferred; split only if review is clearly painful (per functional spec).

---

## 4. Testing Strategy

- Local: `rg` audits for old action majors still in-scope; empty Claude/token grep under `.github/`; matrix string; classifier absence; doc string checks.
- PR CI: confirm no `Node.js 20 is deprecated` annotations on at least `ci.yml`, `gitleaks.yml`, `pr-lint.yml`, `e2e.yml`, `link-check.yml`; confirm single `lint-and-test (3.12)` job.
- Release path: inspect `release.yml` post-bump for paired upload/download; treat a real tag push as out of band for this PR unless maintainers volunteer a dry run.
- No new pytest cases (no product code).
