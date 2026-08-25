# Functional Specification: Keep CI Quiet, Current, and Honest About Supported Python

- **Roadmap Item:** GitHub Issue #116 — CI maintenance: clear Node 20 deprecation warnings, verify Python 3.12 only, remove non-working Claude-in-CI workflows
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

Maintainers opening pull requests and watching CI currently get three kinds of noise and latent breakage that are unrelated to product code:

1. Every run warns that key automation steps still target an outdated runtime that GitHub is sunsetting — today it is a warning; after the grace period those steps fail.
2. The default lint-and-test matrix spends time on a second Python release we are not committing to support in CI, while contributor docs still advertise that dual matrix.
3. Two Claude-branded review/assist workflows cannot authenticate on this repository. One fails hard when someone mentions the bot; the other soft-fails on every pull request. Both add noise without reviewing anything.

Success looks like: a normal pull-request CI run shows zero Node-runtime deprecation annotations on the workflows called out in the issue; a single Python 3.12 lint-and-test job; no Claude-in-CI workflow files left; packaging still able to hand artifacts between release jobs; docs and the Unreleased changelog reflecting that we only verify 3.12 in CI.

---

## 2. Functional Requirements (The "What")

- **As a** maintainer watching CI, **I want** automation steps bumped to their current major releases that run on the supported runtime, **so that** a full CI run on the change request produces zero "Node.js 20 is deprecated" annotations across at least the main lint/test, secrets scan, PR lint, end-to-end, and link-check workflows.
  - **Acceptance Criteria:**
    - [ ] Given a pull request that includes the automation bumps, when CI finishes, then the run annotations contain no `Node.js 20 is deprecated` messages for the workflows named in the issue’s acceptance list.
    - [ ] Upload and download majors used by the release packaging path stay paired so an artifact produced in one job can still be consumed in the dependent job.

- **As a** contributor reading how we test, **I want** CI and docs to say we verify Python 3.12 only, **so that** we do not imply commitment to a second Python version we choose not to spend CI on.
  - **Acceptance Criteria:**
    - [ ] Given the CI configuration after this change, when viewing the lint-and-test jobs on a PR, then only a single `lint-and-test (3.12)` job appears (no 3.13 job).
    - [ ] Given the package metadata and contributor/maintainer docs listed in the issue, when searching for claims of a dual 3.12+3.13 (or stale 3.9+3.12) CI matrix, then none remain; installability of Python ≥3.12 for users is unchanged.
    - [ ] Given `CHANGELOG.md`, when reading `## [Unreleased]`, then there is an entry covering this work, including that dropping the 3.13 classifier is user-visible.

- **As a** maintainer, **I want** the non-authenticating Claude CI workflows removed, **so that** `@claude` mentions and every PR no longer trigger dead automation.
  - **Acceptance Criteria:**
    - [ ] Given the repository’s `.github/` tree after the change, when searching for Claude Code Action usage or the Claude OAuth token secret name, then there are no matches.
    - [ ] The PR body notes that a maintainer should delete the orphan repository secret in Settings if it is still present (this change does not itself delete secrets via API).

- **As a** maintainer shipping this pass, **I want** A+B+C in one pull request unless review becomes clearly painful, **so that** we avoid reviewing three near-identical workflow diffs.

---

## 3. Scope and Boundaries

### In-Scope

- Bump every listed Node-20-targeting action to its **latest** major (per the agreed pin strategy).
- Verify and bump the secrets-scan action to v3 (confirmed: license still optional for personal-account repos).
- Narrow CI to Python 3.12 only; drop the unused 3.13 package classifier; update the docs pages named in the issue.
- Delete both Claude-in-CI workflow files; leave synthesis-backend API key docs alone; do not rewrite historical CHANGELOG mentions of Claude workflows.
- One PR covering sections A, B, and C; Unreleased changelog entry.

### Out-of-Scope

- Changing what Python versions users may install (`requires-python` stays `>=3.12`).
- Bumping actions already on the supported runtime or composite wrappers the issue lists as out of scope.
- Installing the Claude Code GitHub App or keeping either Claude workflow with soft-fail papering.
- Other roadmap items (e.g. deferred claude.ai chat ingest).
- Product feature work unrelated to CI hygiene.
