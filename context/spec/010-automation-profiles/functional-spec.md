# Functional Specification: Plain-language automation setup

- **Roadmap Item:** Phase 2 — Make the product self-explanatory (sibling of "README as a product page" #109 and "CLI help as a lifecycle map" #112)
- **Status:** Completed
- **Author:** Alexander Makarov
- **Issue:** [#156](https://github.com/AlexanderMakarov/llm-wiki/issues/156)

---

## 1. Overview and Rationale (The "Why")

Setting up the daily automation is one of the first things a new user does — `setup.sh` offers it, and the docs point at it. Right now that setup asks a single question written in the product's own internal shorthand:

```
Scheduler profile A=sync  B=sync+synth+build  C=all --with-sync --with-synth  [A]:
```

A person who installed llmwiki ten minutes ago cannot answer this. They do not know what "synth" means, they cannot tell why the second and third choices look almost identical, and — most importantly — nothing on that line warns them that one of these choices sends their session transcripts to a paid AI service while another does not. Two of the three choices also silently decide things the user was never asked about: quality checks are forced on for one and unavailable in another, and the knowledge graph is switched off for everyone with no way to turn it on.

There is a second, related problem. The daily job is built out of the `all` command, whose name promises everything but which actually skips the two most important steps unless you know to ask for them. Someone reading their own scheduled command back a month later cannot tell what it does. The same confusion shows up in the user-facing documentation: the cheatsheet and the quickstart still teach people to run every step by hand and never mention that automation exists at all, and several of their stated facts are simply out of date.

**Desired outcome.** The setup asks one plain question everybody can answer — should the daily job just collect my sessions, or also make sense of them? — and then offers a short list of optional extras for people who want them. The command that gets scheduled reads like a sentence rather than a puzzle. The docs point newcomers at automation instead of a list of daily chores.

**How we measure success.** A person who has never read the source can (a) pick a daily job and correctly predict whether it will spend money, (b) read back the scheduled command and say what it does, and (c) find automation from the cheatsheet or the quickstart without being told it exists.

---

## 2. Functional Requirements (The "What")

### R1 — One plain-language question with two real choices

- **As a** new user running the automation setup, **I want** the choice described by what it does and what it costs, **so that** I can pick without guessing.

The old three-letter menu collapses to two genuine outcomes. Everything that used to distinguish the third choice becomes an optional extra (R2).

```
What should the daily job do?

  1) Ingest only     Collect new agent sessions into your vault and refresh
                     the site. Never contacts an AI provider — no cost.
                     Writes: raw/, site/

  2) Maintain        Collect new sessions, summarise each one into a wiki page,
                     gather candidate topics for you to review, refresh the
                     site, and report wiki quality findings into the run log.
                     Sends session text to your AI provider — this costs money
                     once a real provider is configured.
                     Writes: raw/, wiki/sources/, wiki/candidates/, site/

Choice [1]:
```

- **Acceptance Criteria:**
  - [x] Given the setup is running interactively, when the daily-job question is displayed, then each choice shows an outcome name, the folders it writes, and an explicit statement about AI-provider cost.
  - [x] Given the daily-job question is displayed, when the user presses Enter without typing anything, then choice 1 (Ingest only) is selected.
  - [x] Given the daily-job question is displayed, when the user types `A`, then Ingest only is selected; when the user types `B` or `C`, then Maintain is selected. In all three cases the setup continues without an error.
  - [x] Given the daily-job question is displayed, when the user types something that is not a recognised choice, then the question is re-asked rather than the setup silently falling back to a default.
  - [x] Given the user chose Maintain, when the choice is confirmed, then a line appears telling them they can see the expected cost by running `llmwiki synth --estimate` before the job first fires.

### R2 — One add-ons step for the optional extras

- **As a** user, **I want** the optional behaviours offered as a short list I opt into, **so that** nothing is decided for me by which numbered choice I happened to pick.

After choosing Maintain, the setup offers a list of extras. Selecting none is the normal answer and is what pressing Enter does.

```
Optional extras (comma-separated numbers, Enter = none):

  1) Build the knowledge graph        Adds a graph of how your pages link
                                      together. Writes: graph/
  2) Fail the job on quality errors   Report the scheduled job as failed when
                                      the quality check finds errors.
  3) Fail the job on quality warnings Report the scheduled job as failed when
                                      the quality check finds warnings or
                                      errors. Stricter than 2.

Extras []:
```

- **Acceptance Criteria:**
  - [x] Given the user chose Maintain, when the daily-job choice is confirmed, then the extras list is displayed as a single step offering the graph and the two failure policies.
  - [x] Given the extras list is displayed, when the user presses Enter without typing anything, then no extras are enabled: the graph is not built and quality findings never fail the job.
  - [x] Given the extras list is displayed, when the user enters several numbers separated by commas, then every named extra is enabled.
  - [x] Given the extras list is displayed, when the user enters a number that is not offered, then the step is re-asked rather than silently ignoring it.
  - [x] Given the user chose Ingest only, when the setup continues, then the extras step is not shown at all.
  - [x] Given the user selects both failure policies, when the answers are confirmed, then the stricter one (warnings) applies and the setup says so rather than silently picking one.

### R3 — Quality checks always run for Maintain, and never fail the job by default

- **As a** user, **I want** wiki quality findings reported without them breaking my scheduler, **so that** a red daily job means the job actually broke.

- **Acceptance Criteria:**
  - [x] Given the Maintain job is scheduled with no extras, when it runs, then the quality check runs and its full report — orphan pages, broken links, stale pages — appears in the run log.
  - [x] Given the Maintain job is scheduled with no extras, when the quality check reports errors or warnings, then the job still finishes successfully and the operating system's scheduler reports it as successful.
  - [x] Given the run log from a previous run exists, when the job runs again, then the log contains only the latest run's output.
  - [x] Given the "fail on quality errors" extra is enabled, when the quality check reports one or more errors, then the job is reported as failed; when it reports only warnings, then the job still succeeds.
  - [x] Given the "fail on quality warnings" extra is enabled, when the quality check reports any warning or error, then the job is reported as failed.

### R4 — The knowledge-graph extra asks which builder to use

- **As a** user enabling the graph, **I want to** be told there is a richer builder and what it needs, **so that** I can make an informed choice instead of silently getting the basic one.

- **Acceptance Criteria:**
  - [x] Given the user enabled the knowledge-graph extra, when the extras step is confirmed, then a follow-up question asks which builder to use, offering the built-in one and the richer one.
  - [x] Given the builder question is displayed, when the user presses Enter, then the built-in builder is selected — it needs no extra install.
  - [x] Given the builder question is displayed, when the richer builder is offered, then the line states that it needs an extra install and shows the exact command (`pip install llm-wiki[graph]`).
  - [x] Given the user chooses the richer builder while that extra is not installed, when the choice is confirmed, then the setup warns that the daily job will fall back to the built-in builder until the extra is installed, and continues rather than refusing.
  - [x] Given the user did not enable the knowledge-graph extra, when the setup continues, then the builder question is not asked.

### R5 — The setup shows the exact daily job before writing anything

- **As a** user, **I want to** see the command that is about to be scheduled, **so that** I can tell whether the answers I gave produced what I meant.

- **Acceptance Criteria:**
  - [x] Given all questions have been answered, when the setup is about to write the scheduler files, then it prints a short summary showing the chosen job in words (for example, `Maintain + graph (built-in)`), the daily run time, and the exact command line that will run.
  - [x] Given the summary is displayed, when the user declines to continue, then no scheduler files, status file, or configuration changes are written.
  - [x] Given the summary is displayed, when the user confirms, then the scheduler files are written and their paths are printed.

### R6 — `llmwiki all` means all of it, with the ability to opt out

- **As a** user reading my own scheduled command, **I want** `all` to mean what it says, **so that** I can tell what the daily job does without consulting the manual.

Today `all` runs only part of the pipeline and hides the two most consequential steps behind opt-in switches, which is why the scheduled command needs a trail of switches to express something simple. `all` becomes the whole loop — collect, summarise, rebuild the site, build the graph, run quality checks — and each stage can be switched **off** individually.

- **Acceptance Criteria:**
  - [x] Given a vault with new sessions, when `llmwiki all` is run with no other options, then it collects new sessions, summarises them, rebuilds the site, builds the graph, and runs the quality check.
  - [x] Given `llmwiki all` is run, when any single stage is switched off by its opt-out option, then that stage is skipped and every other stage still runs.
  - [x] Given a user's existing script or scheduled job passes the old opt-in switches, when it runs on the new version, then it still succeeds — the old switches are accepted, are treated as "yes, include that stage", and print a one-line notice that they are no longer needed.
  - [x] Given the summarise stage is about to run as part of `all`, when no AI provider has been configured (the out-of-the-box state), then no request is sent to any provider and no money is spent.
  - [x] Given a user runs `llmwiki all` in a terminal for the first time after upgrading, when a real AI provider **is** configured, then a notice appears before any provider request explaining that `all` now includes the summarise step and naming the option that switches it off.
  - [x] Given `llmwiki all` is run with no failure-policy option, when the quality check reports errors or warnings, then the command still exits successfully.
  - [x] Given `llmwiki all` is run with a failure-policy option, when the quality check reports findings at or above the chosen level, then the command exits with a failure.
  - [x] Given the command's built-in help is displayed, when the user reads it, then it lists the stages in order and states which option switches each one off.

### R7 — The scheduled command is a single run

- **As a** user, **I want** the daily job to be one command rather than a chain, **so that** a machine that sleeps mid-run cannot leave my vault half-updated.

- **Acceptance Criteria:**
  - [x] Given the user chose Maintain with any combination of extras, when the scheduler files are written, then the scheduled command is a single `llmwiki all …` invocation, not several commands chained together.
  - [x] Given the user chose Ingest only, when the scheduler files are written, then the scheduled command is unchanged from what this version's predecessor produced for that choice.
  - [x] Given a daily job is scheduled and a day passes with no new agent sessions, when the job fires, then it completes successfully having changed nothing.

### R8 — The same choices are available without the questions

- **As a** person automating installs or following a scripted guide, **I want** every wizard answer available as a command-line option, **so that** an unattended install produces the same result as answering the questions.

- **Acceptance Criteria:**
  - [x] Given an unattended install, when the daily-job choice is given by name (`ingest`, `maintain`), then the same scheduled command is produced as answering 1 or 2 interactively.
  - [x] Given an unattended install, when the daily-job choice is given as `A`, then Ingest only is produced; when given as `B` or `C`, then Maintain is produced.
  - [x] Given an unattended install, when the knowledge-graph extra and its builder are given by option, then the scheduled command reflects that choice.
  - [x] Given an unattended install, when a quality failure policy is given by option, then the scheduled command reflects it; when none is given, then findings never fail the job.
  - [x] Given an unattended install where an extra is not mentioned, when the scheduler files are written, then that extra is off — the same default the extras step would have applied.
  - [x] Given every option this setup accepts, when the command reference is checked, then each option appears there — no undocumented options exist.

### R9 — The site's Automation panel says what the job does

- **As a** user glancing at my wiki's home page, **I want** the automation panel to describe my daily job, **so that** I do not have to remember what a letter meant.

- **Acceptance Criteria:**
  - [x] Given a daily job has been set up, when the home page is viewed, then the automation panel names the job in words (for example, `Maintain + graph (built-in)`) rather than showing only a letter.
  - [x] Given a daily job has been set up, when the home page is viewed, then the panel states whether the job can spend money at an AI provider.
  - [x] Given a daily job has a failure policy enabled, when the home page is viewed, then the panel says the job can be marked failed by quality findings.
  - [x] Given a wiki whose automation was set up by an older version and records only a letter, when the home page is viewed, then the panel shows a readable name for that letter rather than breaking or showing a blank.

### R10 — Newcomer docs point at automation instead of chores

- **As a** newcomer reading the cheatsheet or the quickstart, **I want to** learn that the daily work can run itself, **so that** I do not conclude that llmwiki requires me to type four commands every day.

The cheatsheet, the getting-started guide, and the quickstart walkthrough currently teach a manual routine and never mention that automation exists. They also carry statements that are no longer true.

- **Acceptance Criteria:**
  - [x] Given the cheatsheet, when a reader looks for how to keep the wiki current, then it presents setting up the daily job as the normal path, with the manual commands shown as the alternative for one-off runs.
  - [x] Given the getting-started guide and the quickstart walkthrough, when a reader finishes the first successful build, then the next step offered is setting up automation.
  - [x] Given the cheatsheet, when its factual claims are checked against the product, then the command count, the quality-rule count, and the install command for the richer graph builder all match reality, and no count contradicts another count on the same page.
  - [x] Given any page that describes what `all` does, when it is read after this change, then it describes the new behaviour.

### R11 — Existing installations are told to refresh

- **As a** user who set up automation on an older version, **I want to** be told my scheduled job is out of date, **so that** it does not keep running yesterday's command forever.

- **Acceptance Criteria:**
  - [x] Given the upgrade guide, when a user reads the entry for this release, then it states that the daily job's command changed, that `all` now includes previously opt-in stages, and that re-running the automation setup refreshes the scheduled command.
  - [x] Given the release notes, when a user reads them, then the change to `all` is listed as a behaviour change, not only as a new feature.
  - [x] Given a user re-runs the automation setup on a machine that already has a scheduled job, when the setup completes, then the existing job is replaced rather than duplicated.

---

## 3. Scope and Boundaries

### In-Scope

- The interactive flow: one plain-language daily-job question with two choices, one add-ons step, a follow-up builder question when the graph is enabled, and a confirmation summary.
- Command-line options covering every wizard answer, with the existing letter choices still accepted.
- Making `all` mean the full loop with per-stage opt-outs, including accepting the previous opt-in switches so existing scripts keep working, and a two-level quality failure policy.
- The home page's Automation panel wording, including readable names for jobs recorded by older versions.
- Documentation: the command reference, the cheatsheet, the getting-started guide, the quickstart walkthrough, the upgrade guide, and the release notes.
- Tests covering the scheduled command produced by each combination of answers.

### Out-of-Scope

- Changing which AI provider is used by default, or how summarising works. (Non-goal from the issue.)
- Automatically approving candidate topics — review stays a human or agent decision. (Non-goal from the issue.)
- Requiring the richer graph builder for anybody; it stays an optional extra. (Non-goal from the issue.)
- Adding any new pipeline stage. This work re-composes and renames existing stages only.
- Offering quality checks or the graph to the Ingest-only job. That choice stays exactly as it is today.
- Showing a live cost estimate inside the wizard. The wizard points at the estimate command instead, so setup never blocks on a slow or paid lookup.
- Starting or managing the continuous watch mode; the setup only records whether it is in use, as today.
- Every other roadmap item, including CLI help as a lifecycle map (#112), the guided health check (#110), and the README rewrite (#109). These are separate specifications; this one may overlap in spirit but does not deliver them.

---

## 4. Open Risks

- **The `all` change is a behaviour change, not an addition.** Anyone with a bare `llmwiki all` already scheduled will start summarising sessions after upgrading. Two things contain the blast radius: out of the box no AI provider is configured, so the default install spends nothing; and a first-run notice plus an upgrade-guide entry warn the users who did configure a provider. This was raised and accepted as a deliberate trade for a command whose name matches what it does.
- **Two former choices now map to one.** Old installs recorded as `B` or `C` both become Maintain. They differed only in whether the graph was skipped and whether the steps ran as one process — both now answered by the extras step. Anyone who wants the old `C` shape enables no extras; the graph was already off for them.
