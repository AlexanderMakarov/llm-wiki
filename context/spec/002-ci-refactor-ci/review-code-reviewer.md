# Code review: #116 CI refactor — Node 24 actions, Python 3.12-only matrix, drop Claude-in-CI (`feat/116-ci-refactor-ci`)

**Scope:** `git diff origin/main...HEAD` (one spec-docs commit) plus all uncommitted working-tree changes (the whole implementation is uncommitted).

**Focus:** bugs, logic errors, security issues, CONTRIBUTING violations. Confidence threshold ≥ 80.

**Verdict:** request_changes

| Severity | Count |
|---|---|
| Critical | 2 |
| Important | 4 |
| Advisory (&lt;80, not counted) | 3 |

---

## Critical

### 1. Three existing tests assert the old action pins and now fail (confidence: 100)

**Where:** `tests/test_ci_workflow.py:86-94` and `tests/test_editorconfig_lychee.py:144-147`.

**Bug:** The repo has tests that pin action majors by string match, and this change did not update them:

- `tests/test_ci_workflow.py::test_pinned_setup_python_version` — asserts `"actions/setup-python@v6" in .github/workflows/wiki-checks.yml`; the file now says `@v7`.
- `tests/test_ci_workflow.py::test_pinned_checkout_version` — asserts `"actions/checkout@v4" in .github/workflows/wiki-checks.yml`; the file now says `@v7`.
- `tests/test_editorconfig_lychee.py::test_workflow_uses_pinned_action_versions` — asserts `"actions/checkout@v4" in .github/workflows/link-check.yml`; the file now says `@v7`.

**Verified locally:** `python3 -m pytest tests/ -q` → 3 failed. (`ruff check llmwiki tests scripts` passes.)

**Guideline / impact:** CONTRIBUTING rule 5 ("Tests must pass. Run `python3 -m pytest tests/ -q` before pushing") and the CI-green requirement. `lint-and-test (3.12)` is a required check, so pushing as-is lands a red required check and blocks the PR.

**Fix:** Update the three assertions to the new majors (`actions/setup-python@v7`, `actions/checkout@v7`). Since these tests are pure version-string locks that break on every routine bump, prefer asserting a *floating major pin exists* (e.g. regex `actions/checkout@v\d+`) so the next bump doesn't re-break them; if the intent is genuinely to freeze a major, keep the literal but add the version to the docstring so it is obvious it must move with the workflow. Also add these two test files to the spec's "files touched" inventory — `technical-considerations.md` §"Files touched" omits `tests/` entirely, which is why the bump missed them.

### 2. Dropping the 3.13 matrix entry orphans a required status check — the PR cannot merge (confidence: 100)

**Where:** `.github/workflows/ci.yml:18` (`python-version: ["3.12"]`) vs. branch protection on `main`.

**Bug:** Branch protection for `main` currently requires **two** contexts:

```
lint-and-test (3.12)
lint-and-test (3.13)
```

With the matrix reduced to `["3.12"]`, the `lint-and-test (3.13)` job never runs and therefore never reports a status. GitHub keeps such a check permanently as "Expected — waiting for status to be reported", so this PR (and every later PR on `main`) is unmergeable until the protection rule is edited. Deleting a matrix entry is not self-healing on the protection side.

**Verified:** `gh api repos/<owner>/<repo>/branches/main/protection --jq '.required_status_checks'` returns both contexts; `rulesets` is empty, so classic branch protection is the only gate.

**Guideline / impact:** Hard merge blocker, and it silently breaks the "wait for CI green" step in CONTRIBUTING *After you push* — `gh pr checks --watch` will hang on a check that can never arrive rather than fail loudly.

**Fix:** Pick one and do it explicitly:

1. Preferred — a maintainer removes `lint-and-test (3.13)` from the required contexts (admin-only, cannot be done from the PR). Sequence it so `main` is never left requiring a non-existent check: update protection first (or immediately before merge), and state this in the PR body as a pre-merge step alongside the orphan `CLAUDE_CODE_OAUTH_TOKEN` secret cleanup the spec already calls out.
2. Or keep `3.13` in the matrix and drop only the classifier, which leaves protection valid with no admin action.

Note the matrix *key* must stay (it does) so the surviving job keeps the exact name `lint-and-test (3.12)`; collapsing the matrix to a plain job would orphan that required check too.

---

## Important

### 3. Node-20 objective not met in `pages.yml` — `upload-pages-artifact@v4` still runs a Node 20 action (confidence: 95)

**Where:** `.github/workflows/pages.yml` (`actions/upload-pages-artifact@v4`, left unbumped per `technical-considerations.md` §"Out of scope").

**Bug:** The spec excludes `upload-pages-artifact` on the rationale that it is "composite/non-Node". Being composite does not make its dependencies Node 24 — a composite action's nested `uses:` steps run on their own declared runtime. `upload-pages-artifact@v4`'s `action.yml` nests `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02`, which is tag `v4.6.2` with `runs.using: 'node20'`. So the Pages build still executes a Node 20 action and will still emit the deprecation annotation.

**Verified:** fetched `actions/upload-pages-artifact` `action.yml` at `v4` (nested SHA above) and `actions/upload-artifact` `action.yml` at `v4.6.2` (`using: 'node20'`). `upload-pages-artifact@v5` exists (published 2026-04-10) and nests `actions/upload-artifact@bbbca2d # v7.0.0` (Node 24).

**Guideline / impact:** The CHANGELOG entry claims the bump covers "current majors that clear Node 20 runtime deprecation warnings" — inaccurate for `pages.yml`. Beyond the cosmetic warning, Node 20 is removed from GitHub-hosted runners on 2026-09-16 (per the `gitleaks-action@v3` release notes cited in the spec), at which point the Pages deploy fails outright.

**Fix:** Bump `actions/upload-pages-artifact@v4` → `@v5` in `pages.yml` (`deploy-pages@v5` is already Node 24 and consumes the artifact through the Pages API, so the pairing is unchanged). Correct the out-of-scope rationale in `technical-considerations.md`: for composite actions, check the nested pins, not just `runs.using`. If the bump is deliberately deferred, say so in the CHANGELOG instead of claiming Node 20 is cleared.

### 4. Node-20 objective not met in `docker-publish.yml` — four `docker/*` actions are Node 20 (confidence: 95)

**Where:** `.github/workflows/docker-publish.yml` — `docker/setup-qemu-action@v3`, `docker/setup-buildx-action@v3`, `docker/login-action@v3`, `docker/metadata-action@v5`.

**Bug:** The spec lists `docker/*` under "actions already verified `node24`". Only `docker/build-push-action@v7` is; the other four resolve to `runs.using: 'node20'` at the pinned majors. Current majors are `login-action@v4.6.0`, `metadata-action@v6.2.0`, `setup-buildx-action@v4.2.0`, `setup-qemu-action@v4.2.0`.

**Verified:** fetched `action.yml` for each repo at the pinned ref (`v3`/`v5` → `node20`; `build-push-action@v7` → `node24`) and each repo's latest release tag.

**Guideline / impact:** Same as #3 — the "clears Node 20" claim doesn't hold repo-wide, and the image publish workflow breaks when Node 20 leaves hosted runners. `docker-publish.yml` runs on tag pushes, so this fails at release time rather than on PRs, where it is most expensive to discover.

**Fix:** Either bump the four `docker/*` actions in this PR (they are drop-in runtime bumps; verify inputs used — `platforms`, `registry`/`username`/`password`, `images`/`tags` — are unchanged in the new majors) or file a follow-up issue and scope the CHANGELOG wording to the workflows actually cleared. Do not leave the spec asserting a verification that does not hold.

### 5. `docs/maintainers/playwright-agents-bootstrap.md` still reproduces the old pins (confidence: 85)

**Where:** `docs/maintainers/playwright-agents-bootstrap.md:184-188, 222, 230, 354-355`.

**Bug:** That guide embeds copy-pasteable YAML for the two workflows this PR bumped (`agents-e2e.yml`, `agents-healer.yml`) and still shows `actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `actions/upload-artifact@v4`, `actions/download-artifact@v4`. Anyone following it recreates Node-20 pins, and the doc no longer matches the files it documents.

**Guideline / impact:** CONTRIBUTING rule 6 — "any `docs/...` that describes the touched surface" must be updated in the same PR. This is the only doc that mirrors the bumped YAML, and the spec's file inventory misses it.

**Fix:** Update those snippets to the new majors and add the file to the spec inventory. A grep gate in the PR checklist (`rg 'actions/(checkout|setup-python|setup-node|upload-artifact|download-artifact)@v[0-9]+' docs/`) would catch this class of drift next time.

### 6. `requires-python` still admits 3.13+ while both the classifier and the test job are gone (confidence: 85)

**Where:** `pyproject.toml` (classifier `Programming Language :: Python :: 3.13` removed, `requires-python = ">=3.12"` kept) + `.github/workflows/ci.yml` matrix.

**Bug:** The three signals now disagree. `pip install llm-notebook` still succeeds on 3.13 and 3.14 because `requires-python` is an open lower bound; PyPI metadata now advertises 3.12 only; and no CI job exercises anything above 3.12. That is untested-but-installable territory — a 3.13-only regression (stdlib deprecation, changed `ast`/`datetime`/`zipfile` behaviour) ships silently, and the first report comes from a user.

This is the approved spec decision (`technical-considerations.md` §"Python matrix and metadata" explicitly keeps `requires-python`), so it is a stance to make deliberate rather than a coding slip — but as shipped, the stance is undocumented and contradicts itself.

**Guideline / impact:** Support-surface accuracy; user-visible packaging metadata (which is why the spec correctly treats the classifier drop as CHANGELOG-worthy).

**Fix:** Choose and document one:

1. Keep a 3.13 job (cheapest correctness) and restore the classifier — but see #2, this also keeps branch protection valid.
2. Bound the floor: `requires-python = ">=3.12,<3.14"`, so pip refuses the untested interpreter instead of half-supporting it.
3. Keep it open and say so — one line in `CONTRIBUTING.md` Requirements plus the CHANGELOG entry: "installs on 3.13+, tested on 3.12 only; 3.13 issues accepted but untested in CI."

The current CHANGELOG wording ("verifies Python 3.12 only … while keeping `requires-python = ">=3.12"`") states the mechanics but not the support consequence.

---

## Advisory (below the ≥80 reporting bar — listed so they aren't lost)

1. **Stale process docs reference the deleted review workflow.** `context/product/delivery-flow.md:81` and its derived `.claude/commands/implement-feature.md` / `.claude/commands/fix-bug.md` still say "do not block on the soft-fail Claude Code Review Action". Harmless (they tell agents to ignore a check that now simply never appears), and `delivery-flow.md` is generated by `/awos:flow`, so regenerate rather than hand-edit.
2. **`sigstore/gh-action-sigstore-python@v3.3.0` nests `softprops/action-gh-release@153bb8e` (`node20`).** Only reached when `release-signing-artifacts` is set, which `release.yml` does not set; its other nested pin is `upload-artifact@v7.0.0`. Correctly out of scope (version/SHA-pinned third party), but worth tracking against the 2026-09-16 runner change.
3. **`actions/cache@v5` is behind current (`v6.1.0`)** in `e2e.yml` / `link-check.yml`. Already `node24`, so out of scope for this PR's objective — noted only so the "current majors" phrasing isn't read as repo-wide.

---

## Verified clean (checked and deliberately *not* flagged)

- **`checkout@v7`'s new fork-PR block does not break `agents-healer.yml`.** v7 (PR actions/checkout#2454) throws for `pull_request_target` / `workflow_run` workflows that resolve to a fork PR's head, gated behind the new `allow-unsafe-pr-checkout` input. `agents-healer.yml` is the repo's only `workflow_run` workflow and checks out with no `ref:`; for `workflow_run`, `GITHUB_REF`/`GITHUB_SHA` are the default branch and its last commit (GitHub events reference), so `assertSafePrCheckout`'s ref/commit/repository conditions all miss and it returns without throwing. No `allow-unsafe-pr-checkout` needed; no `pull_request_target` workflow exists in the repo.
- **Every bumped tag exists upstream:** `checkout@v7.0.1`, `setup-python@v7.0.0`, `setup-node@v7.0.0`, `upload-artifact@v7.0.1`, `download-artifact@v8.0.1`, `configure-pages@v6.0.0`, `create-pull-request@v8.1.1`, `gitleaks-action@v3.0.0`.
- **All inputs in use survive the majors.** `upload-artifact@v7` still accepts `name` / `path` / `if-no-files-found` / `retention-days`; `download-artifact@v8` still accepts `name` / `path` / `run-id` / `github-token`; `setup-python@v7` still accepts `python-version` (the input v7 *removed*, `pip-install`, is not used anywhere in the repo, and no workflow relies on the `NODE_AUTH_TOKEN` export that `setup-node@v7` dropped).
- **Upload/download majors move as a pair** in `release.yml` (`@v7` upload → `@v8` download in `publish` / `sign` / `github-release`) and across the `agents-e2e` → `agents-healer` cross-run download. `download-artifact@v8`'s new `digest-mismatch: error` default is the documented accepted risk.
- **`gitleaks-action@v3` is a runtime-only bump** — no input/output/behaviour change per its release notes, and no `GITLEAKS_LICENSE` is required for a personal-account repo.
- **Claude-in-CI removal is clean.** No `claude-code-action` / `CLAUDE_CODE_OAUTH_TOKEN` / `claude*.yml` references remain under `.github/` (including `dependabot.yml` and `CODEOWNERS`); the only matches are historical `CHANGELOG.md` entries, which the spec deliberately preserves. Neither deleted workflow was a required status check, so removing them does not orphan a gate (unlike #2).
- **No stale "3.12 + 3.13" claims left in docs.** `CONTRIBUTING.md` (both mentions), `docs/architecture.md`, `docs/maintainers/ARCHITECTURE.md`, and `docs/maintainers/REVIEW_CHECKLIST.md` (which also had a stale `3.9 + 3.12`) are consistent; remaining `3.13` hits are `uv.lock` environment markers and an unrelated `pyvenv.cfg` fixture string in `tests/test_install_hint.py`.
- **`ruff check llmwiki tests scripts` passes**, and the branch's single commit (`docs: add spec for #116 …`) uses an allowed conventional prefix.
