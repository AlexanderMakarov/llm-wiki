# Local PR checklist review — `feat/116-ci-refactor-ci` (issue #116)

**Verdict: REQUEST CHANGES**

| Severity | Count |
|---|---|
| Blocker | 2 |
| Major | 5 |
| Nit | 5 |

**Scope reviewed:** `git diff origin/main...HEAD` (1 commit, `f105dea` — spec docs only) **plus** the uncommitted working tree (`git diff HEAD` + `git status` deletions). Working tree: 18 workflows modified, 2 workflows deleted, plus `action.yml`, `pyproject.toml`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/architecture.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/REVIEW_CHECKLIST.md`, and the spec artifacts under `context/spec/002-ci-refactor-ci/`. Total ≈ 73 insertions / 173 deletions — comfortably under the 500-line PR ceiling in CONTRIBUTING §PR size.

**Checklists applied:** `docs/maintainers/REVIEW_CHECKLIST.md`, `docs/maintainers/ARCHITECTURE.md`, `docs/maintainers/DECLINED.md`, `CONTRIBUTING.md`, `SECURITY.md`. No author-supplied focus areas were used.

**How claims were verified:** every target action tag was resolved against the GitHub API for both existence and `runs.using` runtime; composite actions were opened and their internal pins inspected; upstream release notes were read for each major crossed; `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` were run locally.

---

## Blockers

### BLOCKER-1 — Three existing tests fail on this working tree; CI will be red

`python3 -m pytest tests/ -q` fails with 3 errors. All three are workflow-pin assertions that the diff invalidated but did not update:

```
FAILED tests/test_ci_workflow.py::test_pinned_setup_python_version
FAILED tests/test_ci_workflow.py::test_pinned_checkout_version
FAILED tests/test_editorconfig_lychee.py::test_workflow_uses_pinned_action_versions
```

The assertions are literal string checks against workflow files this PR edited:

```86:94:tests/test_ci_workflow.py
def test_pinned_setup_python_version():
    """Verify actions/setup-python@v6 (from the dependency bundle #189)."""
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/setup-python@v6" in text


def test_pinned_checkout_version():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/checkout@v4" in text
```

`WORKFLOW` here is `.github/workflows/wiki-checks.yml`, which the diff moved to `checkout@v7` / `setup-python@v7`. `tests/test_editorconfig_lychee.py:147` does the same for `.github/workflows/link-check.yml`, which moved to `checkout@v7`.

This trips the "CI is green" and "Run `python3 -m pytest tests/ -q` locally" boxes in REVIEW_CHECKLIST (Meta and Tests sections), and CONTRIBUTING TL;DR rule 5. Under the checklist's own blocker rule ("failing tests" → `request changes`), this alone blocks the merge.

**Fix:** update all three assertions to the new majors. While in there, prefer a version-agnostic assertion (e.g. `re.search(r"actions/checkout@v\d+", text)`) so the assertion keeps expressing the real invariant — "the action is pinned to a major tag, not a floating branch" — instead of hard-coding a number that must be edited on every routine bump. Also refresh the `test_pinned_setup_python_version` docstring, which still cites the `#189` dependency bundle as the reason for `v6`.

Note that `ruff check llmwiki tests scripts` passes cleanly — lint is not the problem, only the tests.

### BLOCKER-2 — The PR must be titled `chore:`, not `feat:`

The branch is named `feat/116-ci-refactor-ci`, which signals a `feat:` PR title. That is the wrong conventional-commit type for this change. CONTRIBUTING §PR title format defines `chore` as "Maintenance, deps, **CI**, version bumps" and reserves `feat` for a "New user-visible capability". This PR ships no new capability — it bumps action pins, narrows a CI matrix, drops a Trove classifier, and deletes two dead workflows.

`.github/workflows/pr-lint.yml` will *not* catch this: its title regex accepts `feat` just as happily as `chore`, so the only gate here is human review — which is exactly what this pass is.

Two knock-on effects worth knowing before you pick the title:

1. `pr-lint.yml` **skips the CHANGELOG-updated check** for titles starting with `chore:` / `docs:` / `test:` (see the `classify` step). That is fine here — the CHANGELOG entry already exists, so the check would pass either way; the skip just means CI stops enforcing it.
2. Per the CONTRIBUTING type table, `chore` implies a patch bump rather than a minor one, which matches the actual blast radius.

REVIEW_CHECKLIST puts "Conventional-commit title" in the Meta section, and the Meta section is blocker-rated by the document's own blocker-vs-nit rule. Retitle to something like `chore(ci): Node 24 action majors, Python 3.12-only matrix, drop Claude-in-CI (#116)` and include `Closes #116` in the body.

---

## Major

### MAJOR-1 — `pages.yml` still runs a Node 20 step, so the PR's own goal is unmet there

`pages.yml` was touched by this diff (`configure-pages@v5` → `@v6`, plus `checkout` and `setup-python`), but it still calls `actions/upload-pages-artifact@v4`. That action is a composite, and its internals pin a Node 20 child:

```
actions/upload-pages-artifact@v4  →  using: composite
                                     uses: actions/upload-artifact@ea165f8d… # v4.6.2   (node20)
```

`actions/upload-pages-artifact@v5.0.0` is published and internally uses `actions/upload-artifact@bbbca2dd… # v7.0.0` (node24).

The technical spec excluded `upload-pages-artifact` under the heading "actions already verified `node24` or composite/non-Node". That rationale does not hold: a composite action does not have its own runtime, it inherits whatever its children declare, so "composite" is never by itself evidence that a step is Node 20-free. The consequence is concrete — the Pages deploy path keeps emitting Node 20 deprecation annotations today and stops working when Node 20 is removed from GitHub-hosted runners. Per the `gitleaks-action@v3` release notes read during this review, that removal date is **September 16, 2026**, roughly six weeks out.

**Fix:** bump to `actions/upload-pages-artifact@v5`, or, if you would rather keep the PR to the issue's literal acceptance list, say so explicitly in the PR body and file a follow-up issue so the date does not pass unnoticed.

### MAJOR-2 — `docker-publish.yml` keeps four Node 20 actions, excluded on an incorrect rationale

Same root cause as MAJOR-1, different file. `docker-publish.yml` got its `checkout` bumped to `@v7` in this diff, but every remaining action in it resolves to `node20`, and every one has a published node24 major:

| Action | Pinned here | Runtime at that tag | Latest major |
|---|---|---|---|
| `docker/metadata-action` | `@v5` | `node20` | `v6.2.0` |
| `docker/login-action` | `@v3` | `node20` | `v4.6.0` |
| `docker/setup-buildx-action` | `@v3` | `node20` | `v4.2.0` |
| `docker/setup-qemu-action` | `@v3` | `node20` | `v4.2.0` |

The technical spec lists `docker/*` under the same "already verified `node24` or composite/non-Node" exclusion, which is factually wrong for all four. Because the file appears in the diff with a partial bump, a reader will reasonably assume it was audited.

The functional spec frames the whole point of this work as "today it is a warning; after the grace period those steps fail" — that failure mode still applies to the container publish path after this PR lands.

**Fix:** either bump the four, or correct the exclusion rationale in `technical-considerations.md` to say "deliberately deferred, still Node 20" and open a follow-up issue. What should not survive review is an exclusion list that asserts these are already safe.

### MAJOR-3 — The bootstrap doc that generates two of these workflows still teaches Node 20 pins

`docs/maintainers/playwright-agents-bootstrap.md` carries full copy-pasteable workflow YAML for the agents suite, and it still pins the old majors:

- line 184 `actions/checkout@v4`
- line 185 `actions/setup-python@v5`
- line 188 `actions/setup-node@v4`
- lines 222, 230 `actions/upload-artifact@v4`
- line 354 `actions/checkout@v4`
- line 355 `actions/download-artifact@v4`

Those are the templates for `agents-e2e.yml` and `agents-healer.yml` — the exact two files this PR bumps. Anyone who re-bootstraps from the doc silently reintroduces every Node 20 pin the PR just removed.

This trips REVIEW_CHECKLIST §Docs ("docs/ updated for any architectural change") and CONTRIBUTING rule 6 (update any doc that describes the touched surface). The four doc paths the spec did update are all prose statements about the Python matrix; this one is executable content and matters more.

### MAJOR-4 — `action.yml` raises the runner floor for downstream consumers, undocumented and outside the approved plan

`action.yml` is the composite action this project publishes for other repositories (consumed as `Pratiyush/llm-wiki@v0.9`). The diff moves its `setup-python` from `@v6` to `@v7`. Because `setup-python@v7` declares `runs.using: node24`, any consumer on a self-hosted runner older than **Actions Runner v2.327.1** will break on upgrade.

Two problems:

1. **It is a user-visible change with no CHANGELOG coverage.** The Unreleased bullet describes CI-internal bumps and the classifier drop; it says nothing about the shipped action's new minimum runner version. REVIEW_CHECKLIST §Docs and CONTRIBUTING rule 6 both require the docs for a touched user-visible surface to move in the same PR.
2. **It was not in the approved plan, and it was not needed.** The technical spec's "Files touched (inventory)" lists the workflows, the two deletions, `pyproject.toml`, `CHANGELOG.md`, and four doc paths — `action.yml` is absent, and the spec explicitly puts "composite wrappers the issue lists as out of scope" out of scope. Separately, `actions/setup-python@v6` is **already** `node24` (verified against the API), so this bump buys nothing toward the stated Node 20 goal.

Worth noting the same "already node24" point applies to every `setup-python@v6 → @v7` bump across the workflows. Inside the repo that is harmless currency work on hosted runners, and I would not block it — but on the published `action.yml` it changes other people's compatibility surface, which deserves either a revert or a line in the CHANGELOG.

### MAJOR-5 — The one cross-workflow artifact download is the one case the risk register does not cover

`agents-healer.yml` downloads an artifact produced by a *different* workflow run:

```32:39:.github/workflows/agents-healer.yml
      - name: Download agents-e2e HTML report (contains results.json)
        uses: actions/download-artifact@v8
        with:
          run-id: ${{ github.event.workflow_run.id }}
          name: agents-html-report
          github-token: ${{ secrets.GITHUB_TOKEN }}
          path: playwright-report
```

`download-artifact@v8`'s headline breaking change is that digest mismatches now **error by default** rather than warn (`digest-mismatch` input, default `error`). The technical spec's risk note waves this through as "acceptable for same-workflow artifacts on GitHub-hosted runners" — but this call site is precisely not same-workflow. It is the only cross-run download in the repo, and it is the one that received no analysis.

Likelihood of an actual mismatch is low, and the healer is advisory-only per ADR-001, so this is not a blocker. The problem is that it cannot be smoke-tested by a normal PR run: the healer only fires on `workflow_run` completion with `conclusion == 'failure'`, so a green PR never exercises it, and a silent break here is invisible by design.

**Fix:** update the risk note to name this call site honestly, and either exercise it once (force an `agents-e2e` failure on the branch) or record the untested path as accepted residual risk in the PR body — the same treatment the spec already gives the `release.yml` tag-publish path.

---

## Nits

### NIT-1 — Live agent process docs still reference the deleted Claude Code Review workflow

Three files instruct agents about a workflow that will no longer exist:

- `.claude/commands/fix-bug.md:189` — "Do not block on soft-fail Claude Code Review"
- `.claude/commands/implement-feature.md:195` — "Do **not** block on the soft-fail Claude Code Review Action"
- `context/product/delivery-flow.md:81` — "Claude Code Review Action is soft-fail/advisory (do not block the flow on it)"

Behaviourally harmless — they all say "do not wait for it", and not waiting for a check that never appears is the correct outcome. But they are now dead references in live process docs, and a future reader will waste time looking for the workflow. The spec's post-change audit only greps `.github/`, which is why these survived.

The `CHANGELOG.md` hits at lines 728 and 1341 are historical entries and are correctly left alone per the spec's explicit instruction.

### NIT-2 — Historical CHANGELOG line will look like a miss to anyone grepping

`CHANGELOG.md:254` still reads "CI matrix is 3.12 + 3.13" in a shipped 1.x entry. Leaving history untouched is right, but the functional spec's acceptance criterion is phrased as "when searching for claims of a dual 3.12+3.13 matrix, then none remain" — a reviewer running that grep will hit this line and have to work out that it is intentional. One sentence in the PR body ("historical CHANGELOG entries are intentionally not rewritten") saves that round-trip.

### NIT-3 — The CHANGELOG bullet does not name what actually moved

The Unreleased entry says "bumped GitHub Actions to current majors that clear Node 20 runtime deprecation warnings". Six months from now, nobody can tell from that which actions moved or to what, and the runner-version floor (≥ v2.327.1 for every node24 action) is not mentioned at all. Consider naming the majors inline or, at minimum, the runner floor — this is the same information MAJOR-4 needs anyway.

### NIT-4 — Commits are unsigned

`git log --format='%h %G?' origin/main..HEAD` shows `f105dea` as `N` (unsigned). CONTRIBUTING §Branch protection says "Signed commits required" and pre-merge checklist box 15 says "Commits GPG-signed".

Not treated as a blocker because the existing `main` history is also unsigned — every non-merge commit on `origin/main` reports `N`, so this is the fork's de-facto practice rather than a regression introduced here. Flagged only so box 15 in the PR body carries an explicit one-line waiver rather than sitting unchecked.

### NIT-5 — Test assertions will break again on the next bump

Beyond fixing BLOCKER-1, the three assertions encode a specific version number as the invariant. Every future action bump — and there will be one every few months — will fail these tests for no reason other than the number changing. A regex on `@v\d+` keeps the real guarantee (pinned major, not a floating branch or unpinned `@main`) while surviving routine currency work. Small change, and this PR is the natural moment for it.

---

## Verified clear

Things checked against the checklists that came back clean, recorded so they are not re-litigated:

- **Every target tag exists and is genuinely node24.** Resolved via the GitHub API: `checkout@v7` (v7.0.1), `setup-python@v7` (v7.0.0), `setup-node@v7` (v7.0.0), `upload-artifact@v7` (v7.0.1), `download-artifact@v8` (v8.0.1), `configure-pages@v6` (v6.0.0), `gitleaks-action@v3` (v3.0.0), `create-pull-request@v8` (v8.1.1). All eight report `runs.using: node24`.
- **The five acceptance-list workflows are Node 20-free.** `ci.yml`, `e2e.yml`, `gitleaks.yml`, `pr-lint.yml`, and `link-check.yml` were enumerated action by action; every remaining pin in them (`actions/cache@v5`, `actions/github-script@v9`, `peter-evans/create-issue-from-file@v6`) is node24, and `lycheeverse/lychee-action@v2` is a composite with no Node child. The issue's primary acceptance criterion is met.
- **`checkout@v7`'s new fork-PR guard does not break the healer.** `checkout@v7` added blocking for fork-PR checkouts under `pull_request_target` / `workflow_run` (PR #2454, with an `allow-unsafe-pr-checkout` opt-in). `agents-healer.yml` is a `workflow_run` workflow on `@v7`, so this looked like a real hazard. Reading `src/input-helper.ts` at `v7`, the guard runs only when `!isDefaultCheckout` — that is, only when the caller sets `repository` or `ref`. The healer sets neither, so it takes the default self-checkout path and is unaffected. No `pull_request_target` triggers exist anywhere in `.github/`.
- **Artifact upload/download majors are correctly paired, and no removed inputs are used.** `release.yml` uses `upload-artifact@v7` with `download-artifact@v8` throughout, matching the spec's pairing requirement. Every `upload-artifact` call site in the repo uses only `name`, `path`, `retention-days`, and `if-no-files-found` — all still supported in v7. The v7 `archive` and v8 `skip-decompress` / `digest-mismatch` additions are opt-in and unused.
- **`gitleaks-action@v3` is runtime-only.** Release notes confirm "No changes to inputs, outputs, or behavior" — runtime `node20` → `node24` and a dependency refresh. The existing `GITHUB_TOKEN` env is unchanged and no `GITLEAKS_LICENSE` is needed for a personal-account repo, matching the spec's assumption.
- **Layer boundaries hold.** The diff is confined to L7 (CI/Ops) plus L4 (`pyproject.toml`) and L5 (docs). Nothing under `llmwiki/` changed, so no converter/builder/viewer boundary is crossed and no Layer-0 stdlib rule is at risk.
- **No new runtime deps.** The only `pyproject.toml` change is the removal of one Trove classifier; the `dependencies` block is untouched. `requires-python = ">=3.12"` and ruff `target-version = "py312"` are preserved as the spec requires, and the README badge ("Python 3.12+") stays accurate.
- **Security and privacy clean.** No real session data, no machine-specific paths, no usernames, no secrets, and no telemetry anywhere in the diff. Nothing touches redaction, HTML rendering, network calls, or server binding, so the SECURITY.md threat classes (redaction bypass, exfiltration, XSS, path traversal) are all unreachable from this change. Deleting the two Claude workflows *reduces* the `.github/workflows/` attack surface that SECURITY.md explicitly scopes in. `ruff check llmwiki tests scripts` passes.
- **CHANGELOG entry exists** under `## [Unreleased]` → `### Changed`, single-line (no hard wrap), and correctly flags the classifier drop as user-visible.
- **`DECLINED.md` holds nothing relevant.** Every entry concerns product features (comparisons, benchmarks, cost estimates, search, governance). Nothing about CI, action pinning, or the Python matrix has been previously declined.
- **One concern per PR** is technically violated (three concerns: action bumps, matrix narrowing, workflow deletion), but the functional spec approves A+B+C in a single PR by design and the total diff is ~250 lines. Accepted — no finding raised.

## Not verified

- **Build + runtime smoke (REVIEW_CHECKLIST §Build + runtime smoke) — waived.** No product code changed, so `llmwiki build` output is byte-identical by construction and the run would produce no signal. Recorded as an explicit N/A rather than a silent skip.
- **CI green on a real head SHA.** Cannot be confirmed pre-PR. Given BLOCKER-1, `lint-and-test` will fail on the first push as things stand. CONTRIBUTING §After you push still applies once the branch is pushed.
- **`release.yml` end-to-end artifact round-trip.** Only exercised by a real tag push; the spec already documents this as residual risk and that treatment is reasonable.

## Suggested follow-ups for the PR body

1. `Closes #116`, titled `chore(ci): …` (BLOCKER-2).
2. The reminder the functional spec asks for: a maintainer should delete the orphan `CLAUDE_CODE_OAUTH_TOKEN` repository secret in Settings — this PR does not remove secrets via the API.
3. An explicit note that historical `CHANGELOG.md` mentions of the Claude workflows and the 3.12+3.13 matrix are intentionally not rewritten (NIT-2).
4. A one-line waiver for pre-merge boxes 5 (tests — CI-only change, no product code), 13 (light/dark UI), 14 (a11y), and 15 (GPG signing, NIT-4).
5. Whatever you decide on MAJOR-1 and MAJOR-2 — bump now, or a linked follow-up issue with the September 16, 2026 Node 20 removal date called out.
