<!-- skip-tests: true -->
# Tasks: CI refactor (#116)

- **Spec:** `002-ci-refactor-ci`
- **Issue:** https://github.com/AlexanderMakarov/llm-wiki/issues/116
- **Notes:** Feature Testing & Regression skipped (CI/docs chore; verification is shell `rg` + PR CI). No dedicated `github-ci-packaging` agent — tasks use `generalPurpose`.

---

- [x] **Slice 1: Remove dead Claude-in-CI workflows**
  - [x] Delete `.github/workflows/claude.yml` and `.github/workflows/claude-code-review.yml`. **[Agent: generalPurpose]**
  - [x] Verify: `rg -n 'claude-code-action|CLAUDE_CODE_OAUTH_TOKEN' .github/` returns no matches. **[Agent: generalPurpose]**

- [x] **Slice 2: Bump GitHub Actions to Node-24 majors**
  - [x] Update every in-scope action pin per `technical-considerations.md` (checkout@v7, setup-python@v7, setup-node@v7, upload-artifact@v7, download-artifact@v8, configure-pages@v6, create-pull-request@v8, gitleaks-action@v3). Keep upload/download paired in `release.yml` and elsewhere. Do not bump out-of-scope actions listed in the tech spec. **[Agent: generalPurpose]**
  - [x] Verify: `rg` confirms no leftover in-scope Node-20 pins (`actions/checkout@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`, `actions/setup-node@v4`, `actions/setup-python@v5`, `gitleaks/gitleaks-action@v2`, `configure-pages@v5`, `create-pull-request@v7`); `release.yml` uses upload@v7 with download@v8. **[Agent: generalPurpose]**

- [x] **Slice 3: Python 3.12-only matrix, docs, and changelog**
  - [x] Set `ci.yml` matrix to `["3.12"]`; remove `Programming Language :: Python :: 3.13` from `pyproject.toml`; update `CONTRIBUTING.md`, `docs/architecture.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/REVIEW_CHECKLIST.md`; add `CHANGELOG.md` Unreleased entry (classifier drop is user-visible). Leave `requires-python` and ruff `target-version` unchanged. **[Agent: generalPurpose]**
  - [x] Verify: `rg` shows no dual-matrix claims in those docs; classifier gone from `pyproject.toml`; Unreleased changelog present. **[Agent: generalPurpose]**
