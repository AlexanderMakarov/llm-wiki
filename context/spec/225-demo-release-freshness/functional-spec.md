# Functional Specification: Live demo stays recent between releases (Pages-only session refresh)

- **Roadmap Item:** [#225](https://github.com/AlexanderMakarov/llm-wiki/issues/225) — stop “old sessions on a current-looking demo” without weekly releases
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Visitors judge the product by the public demo. Some metrics only light up when sessions look recent (within about a week). Session dates today only move when a maintainer regenerates the demo for a release and commits it — so either widgets go stale between releases, or maintainers cut releases just to keep the demo looking alive.

Success: the **live** demo’s sessions always look at most six days old, without weekly releases, **without any AI in GitHub Actions**, and **without writing regenerated demo files back to git** (Option A: publish a Pages artifact only). Releases remain the only time the full demo — including docs refresh and AI synthesis — is updated and committed.

---

## 2. Functional Requirements (The "What")

### FR1 — Live sessions look at most six days old

On the public demo site, session dates must not be older than six days relative to the day the freshness job last published (or a release that already shipped current dates).

- **Acceptance Criteria:**
  - [ ] Given the scheduled freshness job finished successfully on day D, when a visitor opens the live demo’s session list, then the newest session dates are on D or within the six days before D.
  - [ ] Given no release happened in that window, when a maintainer inspects the default branch’s demo corpus, then those slid dates are **not** present as new commits (Pages-only; repo pin may stay older).

### FR2 — Every six days: rebuild and republish Pages only (Option A)

Every six days, automation slides demo **session** dates forward for the run, builds the site, and deploys to the **same** GitHub Pages site. It does **not** push or open a PR with regenerated demo content.

- **Acceptance Criteria:**
  - [ ] Given six days have passed since the previous scheduled freshness publish (or the feature just shipped), when the schedule fires, then a GitHub Actions run slides session dates, builds, and deploys to the existing public demo URL.
  - [ ] Given that run finishes, when a maintainer checks the repository history, then there is no bot commit whose purpose is those regenerated session files.
  - [ ] Given a maintainer reads release/demo/Pages docs and the release skill, when they look for between-release freshness, then this every-six-days Pages-only path is described next to the release-time full refresh.

### FR3 — No AI / no synth in CI (hard restriction)

The scheduled job must never call a language-model backend and must never run the release-time synth step. Wiki synthesis stays maintainer/release-only.

- **Acceptance Criteria:**
  - [ ] Given only the scheduled freshness job runs, when it completes, then it required no LLM/API credentials and did not run synth.
  - [ ] Given a maintainer cuts a release, when they follow the release checklist / skill, then full demo refresh **including synthesis** remains a release-time step.

### FR4 — Sessions only on the schedule; docs only on release

Between releases, automation updates **session** calendar freshness for the live site only. It does **not** refresh demo docs on that path. Docs (and the rest of the committed demo content refresh) happen on release.

- **Acceptance Criteria:**
  - [ ] Given the scheduled job runs, when maintainers read what it changes before publish, then it is described as re-dating demo sessions only — not regenerating demo docs, not regenerating usage/MCP fixtures.
  - [ ] Given demo docs still reflect the last release cut while session dates on Pages look current, when that is observed, then it is accepted for this scope.

### FR5 — Release and schedule share one Pages site

Both the version-tag Pages deploy and the every-six-days job publish to the **same** public demo site.

- The schedule checks out **`main`** (current session generator + committed demo), slides session dates in the runner, builds, and deploys.
- A later release deploy **replaces** whatever the schedule last published with that release’s **committed** demo.
- Overlapping deploys: one at a time; last successful deploy wins.

- **Acceptance Criteria:**
  - [ ] Given the schedule runs from `main`, when the job finishes, then the live site has session dates slid for the run day and the version label matches that `main` commit’s package version.
  - [ ] Given a new release tag deploys after a scheduled refresh, when that deploy succeeds, then visitors see that release’s committed demo (full cut).
  - [ ] Given release deploy and scheduled refresh contend, when they overlap, then only one Pages deploy finishes at a time and the last successful deploy stays live.
  - [ ] Given a maintainer reads uptime/release/Pages docs, when they look for how the two publishers relate, then docs state: **release** owns committed content (sessions + docs + synth + usage as today); **schedule** owns between-release **session calendar** freshness on Pages only (from `main`), with **no git write**.

### FR6 — Version freshness stays coherent

Tag (and equivalent) deploys keep the existing “live version matches this release” guarantee. The between-release schedule checks out **`main`** so the session generator is current; after that publish, the live version matches **`main`’s** package version (which may be ahead of the last tag until the next cut). The schedule must not invent an unrelated version label.

- **Acceptance Criteria:**
  - [ ] Given a version tag deploy finishes green, when someone checks the live site version, then it matches that release.
  - [ ] Given the scheduled job finishes green, when someone checks the live site version, then it matches the `__version__` from the `main` commit that job published (dates moved; version is whatever `main` currently declares, not a fabricated value).

### FR7 — Failures stay visible; previous site remains

If the scheduled publish fails, the failed Actions run is visible; visitors keep the last successful Pages deploy. Opting out of a **full committed** demo regen at release is separate from turning off the every-six-days Pages refresh.

- **Acceptance Criteria:**
  - [ ] Given the scheduled job fails, when a maintainer opens Actions, then that run shows failed, and visitors still see the last successful deploy.
  - [ ] Given docs describe skipping, when they mention opt-out, then “skip full demo regen at release” is separate from “disable the every-six-days Pages refresh.”

### FR8 — No real personal session data

Automation uses only the synthetic committed demo corpus (plus in-runner date sliding). It must not import private session stores into what Pages publishes.

- **Acceptance Criteria:**
  - [ ] Given the scheduled job runs, when it builds the site, then it uses only the repo demo corpus plus in-runner session date sliding — never a maintainer’s private session directory.

---

## 3. Scope and Boundaries

### In-Scope

- Every-six-days GitHub Actions path: slide demo session dates → build → deploy to existing GitHub Pages (**no** git push of generated demo content — Option A)
- Documenting how that path and the release/tag Pages deploy share one site
- Hard ban on synth / LLM in that CI path
- Sessions-only on the schedule; docs (and usage) refresh remain release-time
- Keeping release-time version assert; schedule stays on the released version

### Out-of-Scope

- Bot commits / PRs of regenerated `demo/` (rejected Option B/C/D for this issue)
- Regenerating demo docs or Analytics usage fixtures on the schedule
- Running synth / any LLM backend in CI
- Forcing a release every six days
- Changing end-user private-vault sync/synth UX
- Removing the maintainer release checklist’s full committed demo refresh
