# Flow log: 291-dispatch-rebuild-ref

## fetch-bug
- BUG_ID: 291 — "docker-publish: workflow_dispatch rebuild publishes main under the requested tag"
- SPEC_NAME: `291-dispatch-rebuild-ref` (orphan fix-as-spec, #164 — no owning functional-spec; CI-only change)
- Branch: `fix/290-dispatch-rebuild-ref` — the branch name cites the wrong issue (#290 is an unrelated agnix-lint task). Code comments, tests, CHANGELOG and the PR all cite **#291**; renaming mid-flight was judged not worth it.
- Entry: issue open, no PR, no prior flow-log.
- Related: #211, which introduced the `workflow_dispatch` path being fixed here.

## diagnose
- `.github/workflows/docker-publish.yml`'s `build-and-push` job checked out with no explicit `ref:`.
- A `workflow_dispatch` event's ref is the **branch** the dispatch ran from, not the tag in `inputs.tag`. So the job built the default branch's source and `docker/metadata-action`'s `type=raw` override published it under the requested release tag.
- Latent, not observed: #211 wired the dispatch input through `metadata-action` and added the smoke job, but the workflow only reached the default branch with `f2706ac` and has never been dispatched. Nothing in the registry is mislabelled.
- The smoke job would have caught it — it pulls the tag back and compares the whole version line — but only *after* the bad image was pushed, since `pyproject.toml` carries a static version that a `main` build would report as the newer one.

## classify
- **Conformance.** The #211 CHANGELOG entry already promises that a dispatch rebuild publishes and verifies the tag you asked for; the workflow did not do that. No documented behaviour changes.

## fix
- Checkout now names its ref, and the tag-format guard moved ahead of the checkout so a malformed input fails with the guard's `::error::` rather than an opaque git failure. The guard is `run:` + `env:` only and reads nothing from disk, so it is safe as the job's first step; the runner creates the workspace regardless of checkout.
- Nothing downstream reads the worktree except `build-push-action`'s `context: .` — `metadata-action` and the smoke job resolve from the event context — so no tagging semantics shift.

## regression-test
- `tests/test_docker.py` gained `_checkout_ref_expression()` and evaluates it, through the existing `_gha_eval` model, against both run scenarios.
- `test_build_checks_out_and_publishes_the_tag_the_smoke_job_pulls` (parametrized) now requires one tag to name the source built, the tag published, and the image smoked.
- `test_tag_push_checks_out_the_same_ref_the_default_would_have` pins the unchanged tag-push path.
- `test_dispatch_checks_out_a_tag_ref_not_a_bare_name` pins the `refs/tags/` qualification (added when the review's N3 was taken; without it, dropping the qualification is invisible, because the shared helper reduces a ref to its tag name before comparing).
- `test_tag_guard_runs_before_anything_consumes_the_tag` extends the #211 ordering check to the checkout.
- Re-proved RED: with `tests.test_docker.PUBLISH_WORKFLOW` repointed at `git show origin/main:.github/workflows/docker-publish.yml`, all five fail pre-fix. A mutated copy of the fixed workflow that drops the `refs/tags/` qualification fails the qualification test alone.

## local-review
- Independent review: **Request changes** — 1 Blocker, 11 Nits. All applied except the ones that are not code.
- B1 was this file: the diff touched `.github/workflows/` and `tests/`, both armed prefixes for `tests/awos_context_gate.py`, with nothing tracked under `context/` (the review file itself is gitignored), so `pr-lint.yml`'s `awos-context` job would have failed.
- Substantive nits taken:
  - The checkout expression dropped the `github.event_name ==` clause the guard carries, so it was the only step that would follow `inputs` for a non-dispatch event — a `workflow_call` with a `tag` input would have made the guard validate a different ref than the one built, the same class of bug as #291. The clause is back.
  - The dispatch ref was unqualified, and `actions/checkout` resolves a bare name as a branch before a tag, so a branch named like the release tag would have been built and published under it. The ref is now `refs/tags/<tag>`, which needed a `format` shim in `_gha_eval` (it evaluates with empty builtins) and a fifth entry in that model's known-divergences block.
  - Buildx GHA cache had no `scope:`, and the cache is partitioned by `GITHUB_REF`, which on a dispatch is the branch — so a rebuild read and wrote the branch's cache while building an old tag's source. Scoped by the tag name now. The review's literal suggestion put `scope:` as a step input; it is a parameter of the `type=gha` cache backend, so it is spelled `type=gha,scope=…` on `cache-from`/`cache-to`.
  - "Exactly what checkout defaults to" was too strong in three places (workflow comment, CHANGELOG, test name and docstring): the default also pins `github.sha`, so naming only the ref means a force-moved tag is re-resolved. All three now say "the same *ref*" and state the `github.sha` caveat.
  - Test hygiene: a missing assertion message, two copies of the job-block helper collapsed into `_job_text(job)`, a checkout-ref regex that required `ref:` to be the first key under `with:`, and step-ordering offsets taken across the whole file rather than within the job.
- Declined / not code: no CHANGELOG restructure (length is within guidance) and no edit to the still-unreleased #211 entry whose promise this PR makes true — `DECLINED.md`'s append-only changelog rule forbids it; whoever cuts the release collapses the two release-note bullets there.

## post-merge
- Dispatch the workflow once against an already-released tag. That exercises the new checkout on real old source, and it retires the unverified assumption recorded inside `_published_tags` — that a disabled `type=raw` row renders as `type=raw,value=` and pushes nothing — whose comment asks for exactly this confirmation "once the workflow is on the default branch". The precondition is met as of `f2706ac`, and this PR makes that assumption more load-bearing, not less.
- The rebuilt image is expected to report the old tag's version: the version is static in `pyproject.toml` and the Dockerfile derives nothing from git history, so the smoke job's whole-version-line comparison should pass.
- Doing so also turns the CHANGELOG's "never dispatched, so nothing in the registry is mislabelled" from an assertion into a verified statement.

## gates
- `ruff check llmwiki tests scripts` — clean.
- `python3 -m pytest tests/` — green.
