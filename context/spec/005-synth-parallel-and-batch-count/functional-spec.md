# Functional Specification: Synth batch count and parallel page synthesis

- **Roadmap Item:** Phase 1 — Honest pipeline reporting (follow-up to "Honest `--estimate` candidate preview (#113)"); GitHub Issue [#118](https://github.com/AlexanderMakarov/llm-wiki/issues/118)
- **Status:** Completed
- **Author:** AWOS `/implement-feature` (agent), for AlexanderMakarov

---

## 1. Overview and Rationale (The "Why")

When an operator catches up on a backlog of sessions, `synth` turns each pending source into a wiki page. Today that happens strictly one page after another, and the operator learns nothing about the size of the job until it is already running: the first thing printed is the first finished page. On a real catch-up batch this means staring at a near-silent terminal for minutes with no idea whether five pages remain or fifty — one operator report measured roughly eleven minutes for eleven pages.

Two things are wrong from the operator's point of view:

1. **No expectation is set.** The operator cannot decide "I'll wait" versus "I'll come back after lunch", because the batch size is invisible until the run ends. The companion change #113 already added an end-of-run summary (how many pages, how long) — but a summary arrives too late to be a decision aid.
2. **The wait is the sum of every page.** Each page's wait is spent waiting on a language model to answer, not on the operator's machine doing work. Nothing about the job requires those waits to happen one at a time, yet they do.

The desired outcome is that a catch-up run tells the operator up front how much work it is about to do, then works on several pages at once so the wall-clock wait shrinks roughly in proportion — while the resulting wiki is indistinguishable from what a one-at-a-time run would have produced.

**Success is measured by:** a run of N pending sources prints the number N before the first page is worked on; a batch of pages completes in meaningfully less wall-clock time than the same batch run one at a time; and the pages, skip decisions, protections, candidate harvest, and error reporting produced by a parallel run match what the sequential run produces for the same inputs.

---

## 2. Functional Requirements (The "What")

### FR1 — The operator sees the batch size before any page is worked on

- **As an** operator running a catch-up synth, **I want to** see how many sources this run will synthesize before the first one starts, **so that** I can decide whether to wait at the terminal or come back later.
  - The count is the final work queue — the sources that will actually be synthesized this run, after every source that is up to date, ineligible, or already claimed by an existing page has been excluded.
  - The line also names which synthesizer is being used and how many pages are being worked on at once, so the operator can tell at a glance whether the run is configured the way they expect.
  - **Acceptance Criteria:**
    - [x] Given a vault with pending sources, when the operator runs a real synth, then a line stating how many sources will be synthesized appears **before** any per-page result line.
    - [x] Given the same run, when the start line appears, then it also names the synthesizer in use and how many pages are being worked on at once.
    - [x] Given a run where every source is already up to date, when the operator runs synth, then the operator sees a clear statement that there is nothing to synthesize, rather than silence.
    - [x] Given a run where some sources are skipped because an existing page already claims them, when the start line is printed, then the count excludes those skipped sources — it states only what will actually be synthesized.

### FR2 — Several pages are synthesized at once

- **As an** operator with a backlog of pending sources, **I want** synth to work on several pages at the same time, **so that** a catch-up run finishes in a fraction of the time it takes today.
  - By default, synth works on **two pages at a time**. This applies to every synthesizer — the Claude command-line synthesizer and a locally-run model alike.
  - **Acceptance Criteria:**
    - [x] Given a vault with several pending sources and default settings, when the operator runs synth, then more than one page is being worked on at the same time.
    - [x] Given the same batch run one page at a time versus at the default setting, when both runs finish, then the default-setting run takes noticeably less wall-clock time.
    - [x] Given a batch of pending sources, when the run finishes, then the set of pages written, their contents, and the recorded end-of-run totals match what the same batch produces one page at a time.

### FR3 — The operator can change how many pages run at once

- **As an** operator on a constrained machine, or one who wants to push harder, **I want to** raise or lower how many pages run at once, **so that** I can match the run to my machine and my language-model provider's limits.
  - The setting can be given **for a single run** as an option on the synth command, and **saved as a preference** so it also applies to scheduled and automatic runs.
  - When both are present, the option given on the command wins for that run.
  - **Acceptance Criteria:**
    - [x] Given no saved preference and no option on the command, when the operator runs synth, then two pages are worked on at once and the start line says so.
    - [x] Given the operator passes an option on the synth command, when the run starts, then that number of pages is worked on at once and the start line reflects it.
    - [x] Given a saved preference exists and no option is given on the command, when the operator runs synth, then the saved preference is used and the start line reflects it.
    - [x] Given both a saved preference and an option on the command, when the run starts, then the option on the command is used.
    - [x] Given the operator sets the number to one, when the run executes, then pages are synthesized strictly one after another, exactly as they are today.
    - [x] Given the operator sets a number below one or a value that is not a whole number, when they run synth, then they see a clear message explaining the accepted range instead of an unexplained failure or a silently ignored setting.

### FR4 — Progress is visible as pages finish

- **As an** operator watching a long run, **I want** each finished page to tell me how far through the batch I am, **so that** I can see the run advancing and estimate the remaining wait.
  - Each per-page result line is prefixed with its position in the batch and the batch total.
  - Because several pages are in flight at once, they finish in whatever order the language model returns them; the position number counts completions, not queue order.
  - **Acceptance Criteria:**
    - [x] Given a batch of several sources, when each page finishes, then its result line shows how many pages have completed so far out of the batch total.
    - [x] Given a batch of several sources, when the run finishes, then the last completed page's position equals the batch total announced at the start.
    - [x] Given a page that fails, when its error line is printed, then it also carries a position so the operator can see the run is progressing.

### FR5 — Nothing else about the result changes

- **As an** operator, **I want** parallel synthesis to change only speed and progress reporting, **so that** I can adopt it without re-checking my wiki for damage.
  - Specifically preserved: a source is only marked done once its page is successfully written; a placeholder page never replaces a real one; sources already claimed by an existing page are still skipped with the same message; the candidate harvest still runs only after all pages are done; a failing page does not stop the rest of the batch; and every failure is still reported.
  - **Acceptance Criteria:**
    - [x] Given a run where one page fails, when the run finishes, then the remaining pages still complete, the failure is reported in the run's errors, and the failed source is **not** recorded as done.
    - [x] Given a run interrupted partway through, when the operator runs synth again, then only the sources that did not complete are synthesized again — completed ones are not redone.
    - [x] Given a source whose synthesizer returns placeholder content and whose page already exists as a real page, when the run finishes, then the existing real page is left untouched and the operator sees the same "kept real page" message as today.
    - [x] Given a completed run, when the candidate harvest reports its results, then it accounts for every page written by that run.
    - [x] Given a completed run, when the operator inspects the wiki log entry and the end-of-run summary, then the counts, the per-producer breakdown, and the total pages match the pages actually written.

### FR6 — The new setting is discoverable

- **As an** operator, **I want** the new option and preference documented where I already look, **so that** I can find it without reading the source.
  - **Acceptance Criteria:**
    - [x] Given the operator asks the synth command for help, when the help text is shown, then the new option appears with a description and its default.
    - [x] Given the operator reads the command reference documentation, when they look up synth, then the new option and the saved preference are listed with their default.
    - [x] Given the operator reads the release notes, when they look at the unreleased section, then this change is described.

---

## 3. Scope and Boundaries

### In-Scope

- A start-of-run line, printed before the first page result, stating how many sources this run will synthesize, which synthesizer is in use, and how many pages run at once.
- A clear "nothing to synthesize" statement when the work queue is empty.
- Synthesizing several pages at once, defaulting to two, for every synthesizer.
- A per-run option on the synth command and a saved preference to change that number, with the command option taking precedence.
- Validation and a clear message for out-of-range values.
- A completed-so-far / batch-total position on each per-page result and error line.
- The same behavior applies wherever synth runs as part of a larger pipeline run, not only when invoked directly.
- Help text, command reference documentation, and release-notes entry for the new option and preference.

### Out-of-Scope

- **Running the candidate harvest in parallel** — the harvest is cheap relative to page synthesis (explicitly excluded by the issue).
- **Forecasting candidates before the run** — that is #113's concern and already resolved there.
- **Token and cost reporting from the Claude command-line synthesizer** — tracked on #113 / PR #119, not here. This change must not regress the existing totals, but it adds nothing to them.
- **Parallelizing anything other than page synthesis** — session conversion, site build, index rebuild, and lint are untouched.
- **A live-updating progress bar or spinner** — progress is reported as completed lines, not as redrawn terminal output.
- **Automatically tuning the number based on machine capability or provider rate limits** — the operator chooses the number.
- **Retrying a failed page** — failure handling is unchanged from today.
- All other roadmap items (honest already-synthesized counts #81, docs link hygiene #107, migration inventory, Phase 2 documentation and `doctor` #110, Phase 3 Cursor ingest #2, Cursor-compatible AWOS #114, and everything under Later/deferred) are automatically out-of-scope for this specification.
