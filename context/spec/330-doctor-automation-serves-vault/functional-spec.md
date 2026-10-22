# Functional Specification: Doctor detects scheduled maintenance that no longer serves this vault

- **Roadmap Item:** Guided health check — `llmwiki doctor` (#110), follow-up [#359](https://github.com/AlexanderMakarov/llm-wiki/issues/359)
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

People who set up scheduled maintenance expect their vault to stay current without thinking about it. Today the schedule can quietly stop serving the vault and nothing says so. In one real case, setting up the schedule again from a test copy of the code moved it to a throwaway test vault. For more than ten days it ran "successfully" every day while the real vault received nothing. `llmwiki doctor` only reported a growing backlog and offered a one-time catch-up, so the next scheduled run missed the vault again.

Two gaps caused this. First, a person gets only one schedule, so setting it up for one vault silently takes it away from another. Second, doctor believes the vault's own record that the schedule is active and never checks what is actually scheduled or whether it ran.

**Desired outcome:** every vault can have its own schedule. Doctor tells you plainly when this vault's schedule is missing, switched off, aimed somewhere else, or has stopped completing runs, and offers to fix it. Setting up a schedule never silently takes one away from another vault.

**Success:** replaying the incident above (a schedule redirected to a test vault, the real vault falling behind) makes `llmwiki doctor` on the real vault name the schedule as the cause and offer a repair that keeps working on later runs.

---

## 2. Functional Requirements (The "What")

### R1 — One schedule per vault

- **As a** person with more than one vault, **I want** each vault to have its own scheduled maintenance, **so that** setting up one never stops the other.
  - **Acceptance Criteria:**
    - [ ] Given vault A already has a schedule, when I set up scheduled maintenance for vault B, then both schedules are listed by the operating system's scheduler and vault A's next run still targets vault A.
    - [ ] The schedule's visible name or description identifies which vault it serves.
    - [ ] Given a person who already has the single schedule from an earlier version, when they set up or repair the schedule for the vault it serves, then the old schedule is replaced by that vault's own schedule (not left running beside it), and they are told this happened.
    - [ ] Given that older single schedule serves vault A, when I set up a schedule for vault B, then vault A's schedule keeps running unchanged.

### R2 — Setting up a schedule never silently takes over or misfires

- **As a** person setting up scheduled maintenance, **I want** a clear warning before I replace something that is working, **so that** a test run can't break my real setup.
  - **Acceptance Criteria:**
    - [ ] Given this vault already has a schedule that runs llmwiki from a different place on disk, when I set up the schedule again, then I am told where the current schedule runs from and where the new one would run from, and on a terminal I am asked to confirm. Without a terminal, setup stops with that explanation unless I pass `--force`.
    - [ ] Given I set up a schedule from a development copy of llmwiki (for example a branch checkout or a worktree), when setup runs, then I see a warning that the scheduled job will keep using that copy and stop working if it is deleted.
    - [ ] Given I pass `--force`, when setup runs, then it proceeds without asking, and the warning text still prints.

### R3 — Doctor reads the recorded "switched on" state correctly

- **As a** person running doctor, **I want** a schedule that is recorded as installed but not switched on to be reported, **so that** I learn it will never run.
  - **Acceptance Criteria:**
    - [ ] Given the vault records a schedule that was written but not switched on, when I run `llmwiki doctor --check`, then I see the existing "declared but not active" finding.
    - [ ] Vaults set up by older llmwiki versions, which record this state in an older format, are still reported correctly.

### R4 — Doctor detects a schedule that serves a different vault, or none at all

- **As a** person running doctor on my vault, **I want** to be told when no schedule actually works on this vault, **so that** I fix the cause, not only today's backlog.
  - **Acceptance Criteria:**
    - [ ] Given this vault records scheduled maintenance but the schedule the operating system actually holds for it works on a different vault, when I run `llmwiki doctor --check`, then I see an **error** that names both vaults. The other vault is shown in shortened form (folder name, not the full private path).
    - [ ] Given this vault records scheduled maintenance but the operating system holds no schedule for it, when I run doctor, then I see an **error** saying the schedule is missing.
    - [ ] In both cases doctor offers one fix: set up this vault's schedule again. It is marked as a change that asks for confirmation, it is not applied by `--yes` alone, and doctor shows the exact command before running it. Because schedules are per vault (R1), applying the fix never affects another vault's schedule.
    - [ ] After the fix is applied, a fresh `llmwiki doctor --check` shows no automation error for this vault.
    - [ ] Given a vault that never set up scheduled maintenance, doctor reports nothing about schedules.
    - [ ] This works on Linux, macOS, and Windows. Where doctor cannot read the scheduler on the current system, it says it could not check, not "all good".

### R5 — Doctor detects a schedule that has stopped completing runs

- **As a** person running doctor, **I want** to know when my vault's schedule hasn't completed a successful run recently, **so that** a broken or never-firing job doesn't hide behind a "switched on" status.
  - **Acceptance Criteria:**
    - [ ] Given the schedule has existed for more than two of its intervals (for a daily schedule, more than two days), and there is no record of any run for this vault, when I run doctor, then I see a **warning** that the schedule has not run.
    - [ ] Given the last recorded run is older than two schedule intervals, then I see a warning that gives how long ago that run was.
    - [ ] Given the last recorded run ended in failure, then I see a warning saying the last run failed and where to read its output.
    - [ ] Given the schedule was set up less than two intervals ago and has not run yet, then doctor stays quiet about runs.
    - [ ] Run records written by older llmwiki versions in the shared, non-per-vault location are still used for vaults that have no record of their own.

### R6 — Backlog warning points at the schedule

- **As a** person with scheduled maintenance, **I want** the "backlog overdue" warning to tell me the schedule may not be reaching this vault, **so that** I don't keep clearing the backlog by hand.
  - **Acceptance Criteria:**
    - [ ] Given this vault records scheduled maintenance and the backlog is overdue, when I run doctor, then the backlog warning says the scheduled job may not be reaching this vault and points to the automation findings in the same report. The one-time catch-up offer stays available.
    - [ ] Given no scheduled maintenance is recorded, the backlog warning reads as it does today.

### R7 — Leftover schedules for vaults that no longer exist

- **As a** person who tested with a throwaway vault, **I want** to hear about schedules left behind for vaults that are gone, **so that** they don't keep firing for nothing.
  - **Acceptance Criteria:**
    - [ ] Given a schedule exists for a vault folder that no longer exists, when I run doctor on any vault, then I see a **warning** naming the leftover schedule, with step-by-step removal instructions for this operating system. Doctor does not remove it automatically.

### R8 — Error lookup knows the new findings

- **As a** person who pasted a doctor message or symptom, **I want** `llmwiki doctor --error "<text>"` to recognize these problems, **so that** I get the matching explanation and fix.
  - **Acceptance Criteria:**
    - [ ] Pasting a message from any new finding (R4, R5, R7, plus the setup warnings in R2), or symptom words like "schedule points at another vault" or "automation not running", returns the matching entry with its fix, not the "unknown problem" path.

---

## 3. Scope and Boundaries

### In-Scope

- Per-vault schedules, including taking over the single schedule left by an earlier version (R1).
- Setup guard and development-copy warning (R2).
- Doctor findings R3–R7 and the error-lookup entries (R8).
- Docs and changelog for the changed behavior.

### Out-of-Scope

- A new command to remove a schedule. R7 gives manual instructions only.
- Automatically removing or redirecting another vault's schedule.
- Changing what the scheduled job does (sync/synth/build steps), its timing, or login hooks.
- Doctor checks unrelated to scheduling (other heal areas), and all other roadmap items.
