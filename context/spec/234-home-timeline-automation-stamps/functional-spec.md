# Functional Specification: Honest Home pipeline stamps for sync, synth, build, and lint

- **Roadmap Item:** Home Pipeline state and automation should make sync / synth / build timing unambiguous; lint outcomes must be visible on the static Home page without digging in scheduler logs
- **Status:** Approved
- **Author:** Alexander Makarov
- **Issue:** [#234](https://github.com/AlexanderMakarov/llm-wiki/issues/234)

---

## 1. Overview and Rationale (The "Why")

After a scheduled Maintain run (or a manual full pipeline), Home’s pipeline overview is easy to misread. It already shows when the last sync finished (buried in a collapsible Timeline), but not when summarization finished or when the browsable site was last published. A fresh “Last sync” next to a large “still to summarize” count looks like automation failed — even when summarization is still running or finished later, or when a separate sync-only run refreshed the sync time without finishing the full Maintain cycle.

A second pain: when quality (lint) runs — as part of Maintain or on its own — the operator often has to dig into the automation log or scheduler exit status to learn whether the last check passed or failed. Opening Home should show that outcome prominently. A third pain: the Home Automation panel mixes settings with noise (policy reminders, installer “Updated” timestamps, and related lines that could be one line each), while stage completion times do not belong there.

**Desired outcome.** Looking at Home **Timeline** (under Pipeline state), an operator can tell — from stamped completion times, not from backlog counts — when sync, summarization, site publish, and quality check last finished, and whether the last quality check passed or failed. When lint failed, a note **under the Candidates table** shows the console-shaped error (up to about six lines). The Automation panel shows **automation settings only**. The site that build just published stays published even if a later lint step fails the job. A standalone lint run refreshes those lint results via the data snapshot (no HTML rewrite). The full pipeline keeps going after a failed stage unless `--fail-fast`.

**How we measure success.** After a successful Maintain / full-pipeline run, Timeline shows Last sync, Last synth, Last build, and Last lint in stage order. After lint policy fails the job, the newly built site is still what the browser opens, and Home shows the lint failure note under Candidates. After a standalone lint, Timeline lint fields update without a full Maintain cycle. Without `--fail-fast`, a failed synth still leaves build free to run. Automation no longer carries stage stamps or the removed boilerplate.

---

## 2. Functional Requirements (The "What")

### R1 — Timeline shows distinct completion times for each major stage

- **As an** operator opening Home after automation, **I want** separate “last finished” times for sync, summarization (synth), site publish (build), and quality check (lint) inside the **Timeline** collapsible under Pipeline state, **so that** I do not mistake a fresh sync for a finished Maintain cycle and the count tables stay uncluttered.

**Timeline** must show (or equivalent clear labels), along with existing useful rows such as Oldest pending / Last queue run:

- **Last sync**
- **Last synth**
- **Last build**
- **Last lint**

These times come from recorded completion stamps for each stage, not from inferring progress from pending counts. Empty / never-run stages stay empty or show the same “never” treatment used elsewhere. These four stamps must **not** live in the Automation panel, and must **not** sit above the Eligible sources / Knowledge tables.

- **Acceptance Criteria:**
  - [ ] Given Home is open after at least one successful full pipeline (Maintain / `all`-equivalent), when the operator expands **Timeline**, then they see distinct Last sync, Last synth, Last build, and Last lint values (labels may vary slightly but meaning must be unambiguous).
  - [ ] Given only sync has ever completed, when the operator expands Timeline, then Last sync has a time and Last synth / Last build remain empty (or “never”), so backlog counts alone are not the only signal.
  - [ ] Given a successful Maintain run completes sync, then synth, then build, then lint, when the operator compares the four times, then they are consistent with that order (sync ≤ synth ≤ build ≤ lint, allowing equal times when stages finish in the same second).
  - [ ] Given Home is open, when the operator reads the **Automation** panel, then it does **not** list Last sync / Last synth / Last build / Last lint as stage completion times.
  - [ ] Given Home is open, when the operator views the Eligible sources and Knowledge tables, then those four stamps are **not** rendered above the tables.

### R2 — Lint failure note under Candidates table; pass/fail on Last lint

- **As an** operator, **I want** Last lint to show whether the last quality check passed or failed, and — when it failed — a note **under the Candidates / Knowledge table** with the error detail, **so that** the failure is unmistakable without opening logs and without cluttering the count tables.

Rules:

- When the last quality check **passed** (or there is no failure detail), the note is **not shown** (empty → nothing rendered).
- When the last quality check **failed**, Home shows a **required note under the Candidates table** with the error text, using the **same wording shape the console already prints** (multiple lines; shortened with an ellipsis when long), roughly up to six lines. Last lint in Timeline also shows failed (and may repeat a short indication).

- **Acceptance Criteria:**
  - [ ] Given the last quality check completed successfully with no failure detail, when the operator views Home, then they see Last lint’s time in Timeline (and a passed / OK indication if shown) and **no** lint-error note under Candidates.
  - [ ] Given the last quality check failed under fail-on-errors or fail-on-warnings policy, when the operator views Home, then a note **under the Candidates table** shows the multiline error (up to ~six lines), and Timeline Last lint shows failed with a time.
  - [ ] Given quality checks have never run, when the operator views Home, then Last lint is empty / never and no note appears.

### R3 — Build stays published; lint updates the existing site’s lint status (data only)

- **As an** operator, **I want** a successful site publish to remain what I open even if a later quality step fails the job, and **I want** a standalone quality check to refresh lint status on that same site, **so that** Home always reflects the latest lint without reverting published pages or rewriting HTML.

Rules:

- When the pipeline’s **build** step succeeds, that published site remains the live browsable site. A following **lint** step that fails the job under lint-fail policy must **not** roll the site back to a previous backup or withhold the build.
- After lint runs (inside Maintain / full pipeline **or** as a standalone lint), Pipeline state updates Last lint / pass-fail / banner per R2 by refreshing the **data snapshot** the page already loads — **without rewriting HTML pages**, and without requiring a separate build solely to see lint results.
- Lint-fail may still mark the scheduled / CLI run as failed (exit status / logs); visibility on Home is via R2, not by undoing build.

- **Acceptance Criteria:**
  - [ ] Given Maintain / full pipeline builds successfully and then lint fails under fail-on-errors (or warnings), when the run ends, then opening the site shows the **newly built** pages, and Home shows the lint failure banner from R2.
  - [ ] Given a site already exists, when the operator runs a standalone lint that records new results, then reopening Home shows updated Last lint / banner without requiring a separate full Maintain cycle or HTML rewrite.
  - [ ] Given the job is **not** configured to fail on lint findings, when quality findings exist but the job still succeeds, then the new site remains published and Last lint reflects that the check ran (pass/OK path — no banner unless a failure detail is recorded).

### R4 — Full pipeline continues after a failed stage unless `--fail-fast`

- **As an** operator running the full pipeline, **I want** later stages (especially build) to still run when an earlier stage fails, **unless** I pass `--fail-fast`, **so that** the site can still refresh after a partial run (for example sync OK, synth failed — build still runs and may show not-yet-updated synth counts). `--fail-fast` remains the switch for “stop at the first problem,” which is particularly useful when updating the in-repo demo vault.

Default (no `--fail-fast`): if synth fails but sync succeeded, build still executes. Only `--fail-fast` stops the pipeline as soon as something is wrong. `--fail-fast` is aimed at automation where a human will not open the static site afterward — the console must still report the failure; refreshing Home for that aborted run is not required.

- **Acceptance Criteria:**
  - [ ] Given the full pipeline runs without `--fail-fast`, and synth fails after a successful sync, when the run continues, then build still executes (pipeline counts may show synth backlog that build did not clear).
  - [ ] Given the full pipeline runs with `--fail-fast`, and an early stage fails, when that failure is detected, then later stages (including build) do not run.
  - [ ] Docs / help for the full-pipeline command still describe `--fail-fast` as stop-on-first-failure (including the demo-vault use case in maintainer-facing notes if those docs are touched).

### R5 — Maintain contract is clear; Automation panel is settings-only and shorter

- **As an** operator reading install-automation docs or the Home Automation panel, **I want** Maintain described as rebuilding the browsable site **once per cycle, after summarization**, and **I want** Automation to show **settings only** (shorter), **so that** stage timing lives under Pipeline state and Automation is not cluttered.

**Docs / brief Maintain wording:** Maintain runs the full ordered pipeline and refreshes the site once at the build step after synth. A separate sync-only path (including optional **Ingest** automation) is a different concern — not “Maintain finished.”

**Ingest automation is unchanged in this work.**

**Shrink / focus the Home Automation panel** by:

- Removing the line that says quality findings can mark the scheduled run as failed (the `--lint-fail …` reminder).
- Removing the installer “Updated: …” timestamp line.
- Short **Synth backend** line with spend hint (not a long Cost essay); **Agent hooks** without “(recommended)”; **Watch** on its own line.
- Keeping **only automation settings** — no Last sync / synth / build / lint stamps here.

- **Acceptance Criteria:**
  - [ ] Given the operator reads the install-automation / Maintain documentation updated by this work, when they look for when the site is rebuilt under Maintain, then the docs state it is once per cycle after summarization.
  - [ ] Given Home shows the Automation panel after install-automation, when the panel describes Maintain, then it states (briefly) that Maintain refreshes the site once after summarization — not that every sync alone means the pipeline is complete.
  - [ ] Given the Automation panel is rendered, when the operator reads it, then it does **not** include the “Quality findings can mark the scheduled run as failed…” line, does **not** include an “Updated: …” installer timestamp, shows a short Synth backend line (spend hint when applicable), shows Agent hooks without “(recommended)”, shows Watch on a separate line, and does **not** list pipeline stage completion times.
  - [ ] Given Ingest-only automation is already installed, when this feature ships, then Ingest’s scheduled behavior is unchanged by this work.

---

## 3. Scope and Boundaries

### In-Scope

- Timeline: Last sync, Last synth, Last build, Last lint; required lint-error note under the Candidates table when failed.
- Automation panel: settings only + shrink/merge as listed; Maintain one-liner.
- Lint (pipeline or standalone) refreshes lint status via data snapshot only; build is not reverted when lint fails.
- Full-pipeline continue-after-failure unless `--fail-fast` (confirm / document).
- Docs + automated tests for the above.
- Implementation must reuse existing shared helpers (DRY) rather than duplicating stamp/copy/lint-render logic per CLI command.

### Out-of-Scope

- Changing the stage **order** of the full pipeline (already sync → synth → build → … → lint).
- Changing Ingest-only automation defaults or removing sync-driven site refresh for Ingest.
- Managing or rewriting operator-local scheduler units not produced by install-automation.
- Redesigning the full Pipeline state **counts** table beyond adding stage stamps + lint banner clarity.
- A separate dedicated lint-report page or a site-wide footer badge on every page.
- Inventing a new “revert published site” or backup/restore publish path.
- Closing or transitioning the GitHub issue from the delivery flow.
- Unrelated roadmap items (e.g. chronological session Timeline browse surface).

---

## Decisions locked in this draft

| Topic | Choice |
| --- | --- |
| Stage stamps location | **Timeline** collapsible (not above tables; not Automation) |
| Lint failure UI | **Note under Candidates table** + Last lint failed in Timeline; console-shaped multiline (~6 lines) |
| Lint-policy failure vs publish | Keep the newly built site; do **not** revert; show failure via Candidates note / Last lint |
| Standalone lint | Updates JSON/data snapshot only (no HTML rewrite) |
| Pipeline after stage failure | Continue unless `--fail-fast` (console enough on fail-fast) |
| Ingest-only automation | No behavior change |
| Automation panel | Settings only; short Synth backend line; hooks without “(recommended)”; Watch separate; drop lint-fail reminder + Updated |
| Implementation style | DRY — reuse existing helpers across CLI / `all` |
