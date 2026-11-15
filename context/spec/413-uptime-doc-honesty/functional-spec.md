# Functional Specification: Delete dishonest uptime monitoring guide

- **Roadmap Item:** [GitHub #288](https://github.com/AlexanderMakarov/llm-wiki/issues/288) — docs describe an uptime workflow that does not exist (chosen fix: delete the guide)
- **Status:** Approved
- **Author:** Alexander Makarov

---

## 1. Overview and Rationale (The "Why")

Maintainers and contributors can open a guide titled as if availability monitoring is already set up. That guide walks through a scheduled check, failure alerts, and a status badge someone could paste into the project home page. **None of that monitoring exists.** A badge for a job that never ran looks fine at a glance (“no status”) and can mislead people into thinking the demo site is watched.

A similar honesty problem was fixed before by dropping a documented schedule that was not real, rather than leaving a convincing false description. Success here means: nobody reading project docs believes scheduled uptime monitoring is configured; anyone looking for “is the site reachable vs is it serving the right build” still finds that distinction in the deploy/release documentation that already owns those topics; the example knowledge base does not keep presenting the deleted guide as a live source.

## 2. Functional Requirements (The "What")

- **FR1 — Remove the dishonest uptime guide**
  The standalone uptime / availability-monitoring guide that currently implies live monitoring must no longer be part of the published documentation set.
  - **Acceptance Criteria:**
    - [ ] Given a reader browses the project documentation tree, when they look for that uptime monitoring guide by its usual title or path, then it is gone (not merely marked “proposal”).
    - [ ] Given someone searches project docs for a paste-ready uptime status badge tied to a non-existent scheduled check, when they search after this change, then that badge snippet is not offered.

- **FR2 — Keep truthful “up vs current” guidance findable**
  Useful, accurate guidance that lived inside the deleted guide (especially: HTTP success is not the same as serving the intended build; how the demo site is published and verified) must remain available in the deploy/release docs that already describe those publishers — without claiming a separate uptime monitoring job exists.
  - **Acceptance Criteria:**
    - [ ] Given a maintainer reads the GitHub Pages deploy guide and the release process guide, when they look for how the shared demo URL is published and how a green deploy is checked against the live build identity, then that material is present and does not depend on opening the deleted uptime guide.
    - [ ] Given those same guides previously pointed readers at the deleted uptime guide, when a reader follows every remaining link meant for that topic, then no link lands on a missing page.

- **FR3 — Example vault follows**
  The committed example vault that mirrors project docs must not keep the deleted guide as an ingested document source (or a wiki summary that still presents that monitoring story as current project docs).
  - **Acceptance Criteria:**
    - [ ] Given someone opens the example vault’s documentation sources, when they look for the uptime-monitoring doc mirrored from the deleted guide, then that raw source is gone or clearly no longer part of the live example corpus for this topic.
    - [ ] Given the example wiki catalog and any summary page that existed only for that mirrored guide, when a reader browses after the change, then they are not directed to treat that uptime monitoring write-up as a current source.

- **FR4 — Changelog honesty**
  The unreleased changelog records that the misleading uptime guide was removed so release notes stay accurate.
  - **Acceptance Criteria:**
    - [ ] Given a reader opens the unreleased section of the changelog, when they look for this documentation honesty fix, then a short bullet describes removal of the guide that documented non-existent monitoring.

## 3. Scope and Boundaries

### In-Scope

- Delete the dishonest uptime monitoring guide and its pasteable badge content.
- Retarget or absorb links from deploy/release docs so readers are not sent to a missing page.
- Preserve accurate publisher / version-freshness explanation in the docs that already own deploy and release.
- Align the example vault’s mirrored copy and wiki surface for that guide.
- Update any automated documentation contracts that still require the deleted guide to exist.
- Unreleased changelog note.

### Out-of-Scope

- Adding a new scheduled uptime / availability monitoring workflow or external monitoring account.
- Keeping the guide as a “proposal” with a banner (issue option 3 — not chosen).
- Changing how GitHub Pages deploy or session-freshness publishing actually runs (only documentation honesty and link targets).
- Bumping third-party GitHub Actions action versions / Node.js runner runtime warnings (separate chore; one concern per PR — not owned by #288).
- Broader rewrite of `docs/framework.md` unless it still points at the deleted guide after the change (currently it does not reference it).
- Closing or retargeting unrelated self-heal / fork-identity work beyond what #288 owns.
