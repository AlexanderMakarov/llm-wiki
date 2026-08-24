# Tasks: Plain-language automation setup (#156)

Spec: [`functional-spec.md`](functional-spec.md) · [`technical-considerations.md`](technical-considerations.md)

**Vault rule for every task below:** always invoke `python3 -m llmwiki` from this worktree, never PATH `llmwiki`. Any command that writes must target the throwaway vault `.worktree-vault` (the worktree `config.json` already points there). Never mutate the operator's live vault.

**Gates for every slice:** `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` must both pass before the slice is ticked.

---

- [ ] **Slice 1: A cron expression can be translated into every scheduler format**

  > Foundation leaf module. Nothing imports it yet, so the suite stays green throughout.

  - [ ] Create `llmwiki/cron_spec.py` with the `CronSpec` frozen dataclass (`minutes`, `hours`, `days_of_month`, `months`, `days_of_week` — each a sorted tuple of ints or `None` for `*`), `CronError`, and `parse_cron(expr)`. Support `*`, integer, list, range, step, day names `SUN`–`SAT` (with `0` and `7` both Sunday) and month names `JAN`–`DEC`. Reject with a specific message: nicknames (`@daily`, `@reboot`), Vixie/Quartz extensions (`L`, `W`, `#`), a seconds field, and — most importantly — an expression restricting **both** day-of-month and day-of-week, because cron ORs those fields and no target scheduler can express it. Stdlib only; public functions carry docstrings. **[Agent: general-purpose]**
  - [ ] Add `describe(spec)` returning human text (`Every day at 08:00`, `Weekdays at 08:00`, `Mondays at 09:30`) — this is the single source of truth for schedule wording used later by the wizard, the Home panel, and the status file. **[Agent: general-purpose]**
  - [ ] Add the three renderers: `to_systemd_oncalendar(spec)`, `to_launchd_intervals(spec)` (cross-product expansion of restricted fields, returning a single dict when the product has one element so today's daily plist stays byte-identical, with a cap raising `CronError` and pointing at `llmwiki watch` for sub-hourly schedules), and `to_windows_trigger(spec)` (`ScheduleByDay` when day-of-week is unrestricted, else `ScheduleByWeek` with `<DaysOfWeek>` children). **[Agent: general-purpose]**
  - [ ] Write `tests/test_cron_spec.py` per tech spec §4: grammar acceptance; one test per rejected form asserting the message names the reason; `describe()` for daily/weekday/weekly/custom; table-driven renderer assertions across ~6 expressions for all three backends; `0 8 * * *` yields a single launchd dict rather than a one-element array; the expansion cap raises. **[Agent: general-purpose]**
  - [ ] Verify: run `python3 -m pytest tests/test_cron_spec.py -q` and `ruff check llmwiki tests scripts`, both green. No ephemeral artifacts are produced by this slice; nothing to clean up. **[Agent: general-purpose]**

- [ ] **Slice 2: A daily job can be described, named, and turned into a command**

  > Second foundation leaf. Still nothing imports it, so the suite stays green.

  - [ ] Create `llmwiki/automation_plan.py` with `Job` / `GraphChoice` / `LintFail` literals, the `AutomationPlan` frozen dataclass (defaults `ingest` / `none` / `never`), and `LEGACY_PROFILE_MAP` mapping `A`→ingest, `B`→maintain, `C`→maintain. Stdlib only, no imports from the rest of `llmwiki`. **[Agent: general-purpose]**
  - [ ] Add `plan_command(plan, *, python_bin, working_dir)` composing the scheduled shell line: `ingest` emits `<py> -m llmwiki sync` byte-for-byte as profile A does today; `maintain` emits `<py> -m llmwiki all` plus, in fixed order, `--skip-graph` or `--graph-engine {builtin,graphify}`, then `--lint-fail {errors,warnings}` when not `never`. Fixed flag order so tests are exact string comparisons. **[Agent: general-purpose]**
  - [ ] Add `plan_label(plan)` (e.g. `Maintain + graph (built-in)`), `spends_tokens(plan)`, `plan_to_status(plan)` and `plan_from_status(status)`. `plan_from_status` reads `job` when present, else falls back through `LEGACY_PROFILE_MAP[status["profile"]]`, else the `ingest` default; schedule reading is symmetric (`schedule` key, else `"{minute} {hour} * * *"` synthesised from the legacy integers). These fallbacks live here and nowhere else. **[Agent: general-purpose]**
  - [ ] Write `tests/test_automation_plan.py` per tech spec §4: exact-string `plan_command` for every combination; the ingest command is byte-identical to the pre-change profile-A string; status round-trip; `plan_from_status` on legacy dicts (`A`/`B`/`C`, unknown letter, missing key); legacy `hour`/`minute` → cron fallback; `plan_label` never returns a bare letter. **[Agent: general-purpose]**
  - [ ] Verify: run `python3 -m pytest tests/test_automation_plan.py -q` and `ruff check`, both green. No ephemeral artifacts to clean up. **[Agent: general-purpose]**

- [ ] **Slice 3: `llmwiki all` runs every stage, with per-stage opt-outs**

  > First user-visible change. After this slice `llmwiki all` does the whole loop and the old flags still parse.

  - [ ] In `llmwiki/pipeline.py`: gate the lint step on `not getattr(args, "skip_lint", False)`; add `resolve_lint_fail(args)` mapping `--strict` to `warnings` and taking the stricter when both are given; replace the `--strict` escalation block with a branch over the `summary` dict `_run_lint_step` already returns (`never` never fails; `errors` fails on `summary["error"]`; `warnings` fails on either), keeping exit code `2`. Leave the `if args.with_sync:` / `if args.with_synth:` guards untouched — the flip happens at the argparse default. **[Agent: general-purpose]**
  - [ ] In `llmwiki/pipeline.py`: add the first-run notice before the synth stage, emitted only when the stage is about to run **and** `load_synthesis_backend()` is not `"dummy"` **and** `sys.stdout.isatty()`. Persist a one-shot flag `ops.all_optout_notice_shown` through the `update_state` helper the module already imports, so an interactive user sees it once and scheduled runs (stdout redirected to the log, never a TTY) stay silent. **[Agent: general-purpose]**
  - [ ] In `llmwiki/cli.py` `all` parser: flip `with_sync` / `with_synth` defaults to `True`; add `--no-sync` / `--no-synth` as `store_false` on those same dests; add `--skip-lint` and `--lint-fail {never,errors,warnings}`; re-register `--with-sync` / `--with-synth` as `store_true` on throwaway dests `legacy_with_sync` / `legacy_with_synth` so existing scheduled commands still parse but cannot re-enable a stage the user disabled. Have `cmd_all` print one stderr line when either legacy flag is set. **[Agent: general-purpose]**
  - [ ] In `llmwiki/config_schedule.py`: drop the now-redundant `--with-synth` from the two `synthesis_status_hint` strings (~lines 141, 146), and update the matching assertions in `tests/test_issue_383_pipeline.py` in the same change. **[Agent: general-purpose]**
  - [ ] Update the `all` section and flag table in `docs/reference/cli.md`: stage order, the opt-out flags, the lint policy, the deprecated aliases, and the documented resolution that `--no-synth` wins over `--with-synth`. Required in this slice — `tests/test_cli_doc_parity.py` fails the build on any undocumented flag. **[Agent: general-purpose]**
  - [ ] Write `tests/test_all_optout.py` per tech spec §4: bare `all` parses to both stages on; each `--no-*` flips independently; the full legacy profile-C line (`all --with-sync --with-synth --skip-graph`) still parses and runs every stage; `--skip-lint` skips lint; the policy matrix (`never`/`errors`/`warnings` × `{}`/`{error:1}`/`{warning:1}`) yields the expected exit codes; `--strict` is equivalent to `--lint-fail warnings`; the notice is silent when not a TTY and silent for the `dummy` backend even on a TTY. **[Agent: general-purpose]**
  - [ ] Verify: run the full suite `python3 -m pytest tests/ -q` plus `ruff check`; then against the throwaway vault run `python3 -m llmwiki all --no-synth --skip-graph --vault .worktree-vault` and confirm it completes and reports the stages it ran. Delete any files the check wrote outside `.worktree-vault`. **[Agent: general-purpose]**

- [ ] **Slice 4: The installer writes unit files from a plan and a schedule**

  > The install API produces the new command and the new unit files; the wizard still asks the old questions until Slice 5.

  - [ ] In `llmwiki/automation_install.py`: delete `profile_command` and route `render_wrapper_script` through `automation_plan.plan_command`. Do not leave a wrapper around the deleted function — the tech spec's DRY rule requires the removal. **[Agent: general-purpose]**
  - [ ] In `llmwiki/automation_install.py`: change `render_systemd_timer`, `render_launchd_plist`, and `render_windows_task` to take a `CronSpec` instead of `hour: int, minute: int`, delegating to `cron_spec.to_systemd_oncalendar` / `to_launchd_intervals` / `to_windows_trigger`. Remove the `hour`/`minute` parameters rather than keeping them alongside — a parameter kept "just in case" is the duplication this slice exists to remove. **[Agent: general-purpose]**
  - [ ] Update `run_install` to accept the plan and the schedule, and to record the new status keys (`job`, `graph`, `lint_fail`, `schedule`, `schedule_label`, `label`) alongside the retained legacy `profile`, `hour`, and `minute` so an older `llmwiki` reading a newer status file keeps working. Add the same keys to `automation_status.empty_status()`. **[Agent: general-purpose]**
  - [ ] Update `tests/test_automation_install.py`: the existing four tests must keep passing (`test_run_install_writes_status_and_units` needs its `"profile": "A"` input replaced by the plan). Add coverage that the rendered systemd timer for a weekday schedule carries the expected `OnCalendar`, and that the status file carries both new and legacy keys. **[Agent: general-purpose]**
  - [ ] Verify: run the full suite and `ruff check`; call `run_install` against a `tmp_path` units dir for both an ingest plan and a maintain plan, and read back the generated `llmwiki-maintain.sh` to confirm the command line matches `plan_command`. Delete the generated temp artifacts at the end of the check. **[Agent: general-purpose]**

- [ ] **Slice 5: The setup wizard asks plain-language questions**

  > The headline user-visible change: the new question flow, the confirmation summary, and the non-interactive flag matrix.

  - [ ] Add `_ask_choice(prompt, valid, default)` to `llmwiki/cli.py` — one re-ask loop shared by every new question, so none of them hand-rolls its own. **[Agent: general-purpose]**
  - [ ] Rewrite the interactive branch of `cmd_install_automation` per functional spec R1–R5: the two-choice daily-job question (accepting `1`/`2` and legacy `A`/`B`/`C`), the extras step (comma-separated; both failure policies resolving to `warnings` with a printed note), the graph-builder follow-up shown only when the graph extra was chosen (probing `graphifyy` importability with a deferred import carrying `# noqa: PLC0415` and its reason, warning and continuing on absence), and the schedule question offering Every day / Weekdays only / Once a week / Custom cron — validating any typed expression through `parse_cron` and re-asking on `CronError`. **[Agent: general-purpose]**
  - [ ] Add the confirmation summary (label, `describe()` schedule, exact composed command) and make declining write nothing at all — which requires moving the existing `config.json` synth-backend write to *after* confirmation, since today it happens before `run_install`. **[Agent: general-purpose]**
  - [ ] Add the non-interactive flags per tech spec §2.8: `--job {ingest,maintain}`, `--graph {none,builtin,graphify}`, `--lint-fail {never,errors,warnings}`, `--schedule "<cron>"` (invalid expressions exit 2 with the `CronError` message). Keep `--profile`, `--hour`, `--minute` accepted but deprecated, each printing a one-line notice naming its replacement; `--job` wins over `--profile`, and `--schedule` wins over `--hour`/`--minute`. **[Agent: general-purpose]**
  - [ ] Rewrite the `install-automation` section and flag table in `docs/reference/cli.md`, outcome-first rather than flag-soup, covering every new and deprecated flag. Required in this slice — `tests/test_cli_doc_parity.py` gates it. **[Agent: general-purpose]**
  - [ ] Extend `tests/test_automation_install.py` with wizard tests driven by monkeypatched `builtins.input`: scripted answers producing each plan and schedule; Enter-through yields the ingest plan and asks neither the extras nor the builder question; invalid input re-asks; both failure policies resolve to `warnings`; the weekday preset produces a `* * 1-5` cron; declining the confirmation writes no status file, no unit files, and no `config.json` change. **[Agent: general-purpose]**
  - [ ] Verify: run the full suite and `ruff check`; then drive the wizard non-interactively against the throwaway vault — e.g. `python3 -m llmwiki install-automation --yes --job maintain --graph builtin --schedule "0 8 * * 1-5" --units-dir .worktree-vault/units --vault .worktree-vault` — and read back the generated wrapper and unit files. Delete the generated units directory at the end of the check. **[Agent: general-purpose]**

- [ ] **Slice 6: The built site describes the automation and offers it**

  > Both Home panels stop showing a mystery letter and stop presenting llmwiki as a list of manual chores.

  - [ ] In `llmwiki/build.py` `render_automation_panel`: replace the `Scheduler profile: <letter>` line with `plan_label(plan_from_status(status))`, show `schedule_label` in place of the raw `HH:MM`, add a line stating whether the job can spend tokens (`spends_tokens`), and add a line when `lint_fail != "never"` saying quality findings can mark the job failed. Leave the rest of the panel and its HTML escaping untouched. **[Agent: general-purpose]**
  - [ ] In `llmwiki/render/js.py` (the `queue-commands-table`, ~lines 97–115): add a leading `llmwiki install-automation` row described as the way to stop running the rest by hand, add an `llmwiki all` row (the table omits it entirely today), and update the `llmwiki synth --estimate` row's purpose text now that the wizard points users at it for cost. **[Agent: general-purpose]**
  - [ ] Extend the panel tests: the human label and schedule label render for a new-format status **and** for a legacy letter-only status; the token-spend line appears only for maintain; the commands table contains an `install-automation` row. **[Agent: general-purpose]**
  - [ ] Verify: run the full suite and `ruff check`; build the site into the throwaway vault with `python3 -m llmwiki build --vault .worktree-vault` and confirm both panels render as intended in the generated HTML. Delete any screenshots or scratch files produced during the check — leave the built site in `.worktree-vault`. **[Agent: general-purpose]**

- [ ] **Slice 7: Newcomer docs point at automation, and upgraders are told to refresh**

  > Closes functional spec R10 and R11.

  - [ ] Rewrite the relevant parts of `docs/cheatsheet.md`: present setting up the daily job as the normal path with manual commands as the one-off alternative, and fix the verified stale facts — `pip install llm-notebook[graph]` → `llm-wiki[graph]`, the "11 CLI commands" heading over a 12-row table when the CLI has 25, and the page contradicting itself with both "14 wiki-quality rules" and "17 structural rules". **[Agent: general-purpose]**
  - [ ] In `docs/getting-started.md` and `docs/tutorials/00-quickstart-walkthrough.md`, make automation the next step offered after the first successful build. **[Agent: general-purpose]**
  - [ ] Add the `docs/UPGRADING.md` entry (the `all` behaviour change, re-running `install-automation` to refresh an existing scheduled job, `--hour`/`--minute` superseded by `--schedule`) and the `CHANGELOG.md` entry under `## [Unreleased]`, flagged as a **behaviour change** rather than only a feature. **[Agent: general-purpose]**
  - [ ] Verify: re-read each edited page end-to-end for internal consistency, confirm no prose line was hard-wrapped (repo markdown rule), and grep the docs tree for any remaining `--with-synth` / `--with-sync` guidance or `llm-notebook` package references that this change makes wrong. **[Agent: general-purpose]**

- [ ] **Slice 8: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 010-automation-profiles` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–7 (all implementation tasks) | Assigned to `general-purpose` — `context/product/hired-agents.md` records Python/CLI specialists as declined, so no `python-cli-backend` agent exists | Optional: re-run `/awos:hire` if a suitable registry Python CLI agent appears. The `modern-python-development` and `pytest-best-practices` skills are installed and remain available to `general-purpose`. |
| Slice 8 (QA) | `testing-expert` expects the testing stack declared in `context/product/architecture.md`, which does not currently name pytest/ruff | Low risk here — this spec's §4 test plan is explicit enough to work from. Worth adding the stack to `architecture.md` before relying on `testing-expert` for less-specified features. |
| Slice 6 verification | No browser MCP needed — the site is static files and the panels are assertable from the generated HTML | None. |
