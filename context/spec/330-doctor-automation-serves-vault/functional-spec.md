# Functional Specification: Doctor detects scheduled maintenance that no longer serves this vault

- **Roadmap Item:** Guided health check — `llmwiki doctor` (#110), follow-up [#359](https://github.com/AlexanderMakarov/llm-wiki/issues/359)
- **Status:** Completed
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
    - [x] Given vault A already has a schedule, when I set up scheduled maintenance for vault B, then both schedules are listed by the operating system's scheduler and vault A's next run still targets vault A.
    - [x] The schedule's visible name or description identifies which vault it serves.
    - [x] Given a person who already has the single schedule from an earlier version, when they set up or repair the schedule for the vault it serves, then the old schedule is replaced by that vault's own schedule (not left running beside it), and they are told this happened.
    - [x] Given that older single schedule serves vault A, when I set up a schedule for vault B, then vault A's schedule keeps running unchanged.
    - Evidence: Verified 2026-10-22: `test_two_vaults_get_two_unit_sets_and_each_wrapper_keeps_its_vault`, `test_two_vaults_coexist_and_legacy_adoption_is_announced`, `test_install_switches_off_the_legacy_unit_serving_this_vault`, `test_install_leaves_a_legacy_unit_serving_another_vault_alone`, `test_cli_says_the_legacy_schedule_was_replaced_or_how_to_remove_it`; CLI `install-automation --no-activate --units-dir <scratch>` wrote `llmwiki-maintain-worktree-vault-<hash>.{sh,service,timer}` with `Description=… — vault .worktree-vault` and wrapper pinned to `--vault <vault>`.

### R2 — Setting up a schedule never silently takes over or misfires

- **As a** person setting up scheduled maintenance, **I want** a clear warning before I replace something that is working, **so that** a test run can't break my real setup.
  - **Acceptance Criteria:**
    - [x] Given this vault already has a schedule that runs llmwiki from a different place on disk, when I set up the schedule again, then I am told where the current schedule runs from and where the new one would run from, and on a terminal I am asked to confirm. Without a terminal, setup stops with that explanation unless I pass `--force`.
    - [x] Given I set up a schedule from a development copy of llmwiki (for example a branch checkout or a worktree), when setup runs, then I see a warning that the scheduled job will keep using that copy and stop working if it is deleted.
    - [x] Given I pass `--force`, when setup runs, then it proceeds without asking, and the warning text still prints.
    - Evidence: Verified 2026-10-22: `test_wizard_asks_before_replacing_a_schedule_from_another_checkout`, `test_yes_without_force_refuses_to_replace_a_schedule_from_another_checkout`, `test_force_replaces_a_schedule_from_another_checkout_without_asking`, `test_installing_from_a_git_checkout_warns_that_the_job_keeps_using_it`, acceptance `test_yes_without_force_refuses_a_foreign_checkout_and_force_proceeds_with_warnings`; CLI run from the worktree printed the worktree warning.

### R3 — Doctor reads the recorded "switched on" state correctly

- **As a** person running doctor, **I want** a schedule that is recorded as installed but not switched on to be reported, **so that** I learn it will never run.
  - **Acceptance Criteria:**
    - [x] Given the vault records a schedule that was written but not switched on, when I run `llmwiki doctor --check`, then I see the existing "declared but not active" finding.
    - [x] Vaults set up by older llmwiki versions, which record this state in an older format, are still reported correctly.
    - Evidence: Verified 2026-10-22: `test_recorded_inactive_legacy_format_and_live_disabled_are_both_reported`, `test_status_carries_new_and_legacy_keys` and the R3 unit tests in `tests/test_doctor_checks.py`.

### R4 — Doctor detects a schedule that serves a different vault, or none at all

- **As a** person running doctor on my vault, **I want** to be told when no schedule actually works on this vault, **so that** I fix the cause, not only today's backlog.
  - **Acceptance Criteria:**
    - [x] Given this vault records scheduled maintenance but the schedule the operating system actually holds for it works on a different vault, when I run `llmwiki doctor --check`, then I see an **error** that names both vaults. The other vault is shown in shortened form (folder name, not the full private path).
    - [x] Given this vault records scheduled maintenance but the operating system holds no schedule for it, when I run doctor, then I see an **error** saying the schedule is missing.
    - [x] In both cases doctor offers one fix: set up this vault's schedule again. It is marked as a change that asks for confirmation, it is not applied by `--yes` alone, and doctor shows the exact command before running it. Because schedules are per vault (R1), applying the fix never affects another vault's schedule.
    - [x] After the fix is applied, a fresh `llmwiki doctor --check` shows no automation error for this vault.
    - [x] Given a vault that never set up scheduled maintenance, doctor reports nothing about schedules.
    - [x] This works on Linux, macOS, and Windows. Where doctor cannot read the scheduler on the current system, it says it could not check, not "all good".
    - Evidence: Verified 2026-10-22: acceptance `test_incident_replay_doctor_names_the_schedule_and_the_repair_sticks`, `test_yes_alone_never_applies_the_schedule_repair`, `test_missing_schedule_is_an_error_and_a_vault_without_a_job_is_silent`, `test_confirm_shows_exact_argv_and_dev_checkout_warning`, `test_check_unavailable_when_scheduler_cannot_be_asked`, `test_linux_without_a_user_bus_is_unavailable`, `test_unknown_platform_is_unavailable`; read-only `doctor --check` on the worktree vault reported `[error] automation.points_elsewhere` naming both vaults in shortened form. macOS and Windows discovery/install verified by tests only (`test_macos_reads_the_plist_and_asks_launchctl`, `test_windows_reads_the_task_list_and_task_xml`, `test_windows_query_failures_are_unavailable`); no real launchd/schtasks run.

### R5 — Doctor detects a schedule that has stopped completing runs

- **As a** person running doctor, **I want** to know when my vault's schedule hasn't completed a successful run recently, **so that** a broken or never-firing job doesn't hide behind a "switched on" status.
  - **Acceptance Criteria:**
    - [x] Given the schedule has existed for more than two of its intervals (for a daily schedule, more than two days), and there is no record of any run for this vault, when I run doctor, then I see a **warning** that the schedule has not run.
    - [x] Given the last recorded run is older than two schedule intervals, then I see a warning that gives how long ago that run was.
    - [x] Given the last recorded run ended in failure, then I see a warning saying the last run failed and where to read its output.
    - [x] Given the schedule was set up less than two intervals ago and has not run yet, then doctor stays quiet about runs.
    - [x] Run records written by older llmwiki versions in the shared, non-per-vault location are still used for vaults that have no record of their own.
    - Evidence: Verified 2026-10-22: `test_stale_run_never_ran_past_grace_warns`, `test_stale_run_never_ran_within_grace_is_quiet`, `test_stale_run_old_last_run_gives_age`, `test_stale_run_failed_run_names_log` (reported as `automation.last_run_failed`; exit 75 usage-limit stop is quiet), `test_stale_run_legacy_global_log`, acceptance `test_run_record_in_the_shared_legacy_location_still_counts`. AC4 after a fresh install or repair: `test_stale_run_ignores_a_log_older_than_the_schedule`, `test_stale_run_skips_the_shared_log_when_the_unit_names_its_own`, acceptance `test_a_fresh_install_is_not_judged_by_an_older_shared_log`.

### R6 — Backlog warning points at the schedule

- **As a** person with scheduled maintenance, **I want** the "backlog overdue" warning to tell me the schedule may not be reaching this vault, **so that** I don't keep clearing the backlog by hand.
  - **Acceptance Criteria:**
    - [x] Given this vault records scheduled maintenance and the backlog is overdue, when I run doctor, then the backlog warning says the scheduled job may not be reaching this vault and points to the automation findings in the same report. The one-time catch-up offer stays available.
    - [x] Given no scheduled maintenance is recorded, the backlog warning reads as it does today.
    - Evidence: Verified 2026-10-22: `test_pipeline_backlog_points_at_schedule_when_job_recorded`, `test_pipeline_backlog_only_when_overdue`, acceptance `test_backlog_warning_and_schedule_error_appear_together`.

### R7 — Leftover schedules for vaults that no longer exist

- **As a** person who tested with a throwaway vault, **I want** to hear about schedules left behind for vaults that are gone, **so that** they don't keep firing for nothing.
  - **Acceptance Criteria:**
    - [x] Given a schedule exists for a vault folder that no longer exists, when I run doctor on any vault, then I see a **warning** naming the leftover schedule, with step-by-step removal instructions for this operating system. Doctor does not remove it automatically.
    - Evidence: Verified 2026-10-22: `test_orphan_unit_lists_the_leftover_with_its_removal_steps`, `test_orphan_units_aggregate_into_one_finding`, `test_orphan_unit_quiet_unless_the_target_is_known_and_gone`, acceptance `test_leftover_schedule_for_a_gone_vault_is_listed_on_any_vault_with_removal_steps`.

### R8 — Error lookup knows the new findings

- **As a** person who pasted a doctor message or symptom, **I want** `llmwiki doctor --error "<text>"` to recognize these problems, **so that** I get the matching explanation and fix.
  - **Acceptance Criteria:**
    - [x] Pasting a message from any new finding (R4, R5, R7, plus the setup warnings in R2), or symptom words like "schedule points at another vault" or "automation not running", returns the matching entry with its fix, not the "unknown problem" path.
    - Evidence: Verified 2026-10-22: `tests/test_doctor_kb_match.py`, acceptance `test_error_lookup_recognises_every_new_message`; CLI `doctor --error` mapped all five symptom phrases and both setup-warning texts to their entries.

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
