# Flow log — 010-automation-profiles (#156)

Delivery record for `/implement-feature https://github.com/AlexanderMakarov/llm-wiki/issues/156`. One entry per completed stage; finalized at commit-push (nothing is appended once the PR is open).

## fetch-ticket — done

- Source: GitHub Issue [#156](https://github.com/AlexanderMakarov/llm-wiki/issues/156) "feat: reshape install-automation profiles for first-time users (lean/full + lint/graph addons)", state OPEN, label `enhancement`, no comments.
- Linked issues referenced in the body (#90, #147, #112) read for context; none unreachable.

## workspace — done

- Branch `feat/156-automation-profiles`, worktree `.claude/worktrees/feat-156-automation-profiles`, created from `origin/main`.
- `LLMWIKI_SKIP_AUTOMATION=1 bash ./setup.sh` (the `./setup.sh` form fails with `Permission denied` in a fresh worktree — the file is not checked out executable; invoke via `bash`).
- Throwaway vault `.worktree-vault` scaffolded via `python3 -m llmwiki init --vault …`; worktree `config.json` points `vault.default_path` at it. The primary checkout's `config.json` was never copied.
- Rebased onto `origin/main` at `07f1462` mid-spec, picking up #147/#145 (`8301835`). That merge already corrected profile B's deprecated `synthesize` string to `synth`, so this feature no longer carries that fix.

## specs — functional spec done, tech pending

- `context/spec/010-automation-profiles/functional-spec.md` — Status **Approved** by the user.
- Decisions taken during the interview (all user calls):
  - Base question drops from three lettered profiles to **two** outcomes: *Ingest only* and *Maintain*. The former third profile's distinguishing behaviour becomes opt-in extras.
  - *Maintain* **always** runs lint, non-failing, into the per-run log (the wrapper truncates it each run). Failure policies are opt-in extras with two levels (errors / warnings).
  - Extras are one step: knowledge graph, fail-on-errors, fail-on-warnings. Enter = none.
  - Graph builder question only appears once the graph extra is chosen; defaults to built-in (skip is expressed by not selecting the extra).
  - `llmwiki all` is repurposed to mean **every stage, with per-stage opt-outs**, replacing the current opt-in `--with-sync` / `--with-synth` shape. Raised as a breaking behaviour change; user reaffirmed. Old opt-in flags stay accepted as no-op aliases so existing scheduled jobs do not hard-fail on unknown arguments.
  - `--profile` keeps accepting `A|B|C`: `A` → Ingest only, `B` and `C` → Maintain.
- Scope added by the user beyond the issue text: the newcomer docs (`docs/cheatsheet.md`, `docs/getting-started.md`, `docs/tutorials/00-quickstart-walkthrough.md`) never mention `install-automation` and teach a manual daily routine. Verified stale claims on the cheatsheet: `pip install llm-notebook[graph]` (package is `llm-wiki`), "11 CLI commands" over a 12-row table when the CLI has 25, and both "14 wiki-quality rules" and "17 structural rules" on one page.
- Scope explicitly **kept out**: issue #161 (`synth --estimate` derives doc part pages differently from `synth`). Considered because this feature's wizard copy points users at `synth --estimate` for cost framing, but folding a `bug` fix into a `feat` PR violates CONTRIBUTING rule 1 / checklist box 1. It ships as its own PR; the user chose to continue #156 first.

## tech — done

- `context/spec/010-automation-profiles/technical-considerations.md` — Status **Approved**.
- Design decisions:
  - The `all` opt-in → opt-out flip is an **argparse-layer-only** change: `with_sync` / `with_synth` keep their namespace attribute names and their `run_pipeline` guards; only the defaults flip, with `--no-sync` / `--no-synth` as `store_false` on the same dests. This is forced by `tests/test_cmd_all_parser.py:37` and `tests/test_issue_383_pipeline.py`, which build `argparse.Namespace` by hand using those exact keys.
  - `--with-sync` / `--with-synth` stay registered on throwaway dests. Deleting them would make argparse hard-fail every already-installed scheduled command — silently, until the timer next fires — which is worse than the behaviour change itself.
  - First-run notice for the flip is gated on `sys.stdout.isatty()` plus a one-shot state flag. The wrapper redirects stdout to the log, so a timer-driven run is never a TTY and stays silent with no extra bookkeeping.
- Scope added by the user during tech review:
  - **DRY audit** (§2.1) — one definition per concept, enforced by deleting `profile_command` and by removing `hour`/`minute` from the three unit renderers rather than keeping them alongside a schedule argument.
  - **Site content** (§2.9) — the Home *Commands* table at `llmwiki/render/js.py:97-115` lists thirteen manual commands with no automation row and no `llmwiki all` row. Same "llmwiki is a chore list" defect as the docs.
  - **Cron expressions replace `--hour` / `--minute`** — new `llmwiki/cron_spec.py` parses a 5-field expression once and renders systemd `OnCalendar`, launchd `StartCalendarInterval`, and Windows Task Scheduler XML. Wizard asks presets (Every day / Weekdays only / Once a week / Custom cron). Key guard: an expression restricting **both** day-of-month and day-of-week is refused at parse time, because cron ORs those two fields and none of the three backends can express that — rendering it would be silently wrong everywhere.
  - **Profile names over letters** — `--job ingest|maintain` is the documented spelling; `--profile A|B|C` is demoted to deprecated-but-accepted.
- Clarified for the record: `.llmwiki/automation-status.json` is **not** a new file. It ships today, is written by `save_status` on every install, and is the only channel by which the built site learns about automation. It is separate from `config.json` because config is user-authored and lives in the clone, while status is machine-written and lives under the vault — and `build` reads the vault.
- PR shape: estimate rose from ~875 to **~1362 lines** (~642 code / ~535 tests / ~185 docs) once cron landed in scope. Maintainer re-confirmed **one PR with an extended waiver** in the body. Fallback seams recorded in tech spec §6 (cron out first, then the `all` flip) so they are not re-derived under review pressure.

Next stage: `/awos:tasks`.

## implement — done

Eight slices, each dispatched to a subagent and independently verified by the orchestrator before being ticked.

- **Slice 1** `llmwiki/cron_spec.py` + 75 tests. Parses a 5-field cron expression once and renders systemd `OnCalendar`, launchd `StartCalendarInterval`, and Windows Task Scheduler XML.
- **Slice 2** `llmwiki/automation_plan.py` + 98 tests. `AutomationPlan`, command composer, label, status round-trip, legacy letter map.
- **Slice 3** `llmwiki all` flipped to opt-out; `resolve_lint_fail` three-level policy; first-run notice gated on TTY plus a one-shot state flag.
- **Slice 4** installer takes a plan and a `CronSpec`; `profile_command` deleted outright; default-schedule renderings byte-identical.
- **Slice 5** the wizard: two-job question, extras step, graph-builder follow-up, schedule presets, confirmation summary.
- **Slice 6** Home Automation panel and Commands table.
- **Slice 7** newcomer docs, upgrade guide, CHANGELOG.
- **Slice 8** `tests/test_156_acceptance.py` — 16 whole-feature acceptance tests, five of them RED-validated by breaking source and reverting.

Three defects found and fixed during implementation that the technical spec had got wrong:

1. **Windows schedule widening (three branches).** The tech spec said "`ScheduleByDay` unless day-of-week is restricted", which silently assumed day-of-week was the only calendar field that mattered. A restricted day-of-month rendered as a plain daily trigger (`0 6 1,15 * *` would have fired every day, ~15x too often), as did a restricted month, and day-of-week combined with months dropped the month restriction. All three now render faithfully (`ScheduleByMonth`, `ScheduleByMonthDayOfWeek`), and `test_windows_trigger_never_widens_the_schedule` closes the class rather than the instances.
2. **The launchd expansion cap figure was wrong.** The spec claimed `*/1 * * * *` produces 1440 entries; it produces 60, because unrestricted `*` fields are omitted from launchd dicts entirely. Reaching 1440 needs the hours field restricted too.
3. **R10's file scope was narrower than R10 itself.** The criterion says "any page that describes what `all` does", but the task list named five files. `llmwiki all` was in fact documented in nine places, including the **shipped** `llmwiki/agent_kit/commands/wiki-all.md` that `install-agent-kit` copies into users' `.claude/commands/`. All are now consistent.

## verify — done

- `ruff check llmwiki tests scripts` clean; `python3 -m pytest tests/` → **4370 passed, 48 skipped** (baseline before this feature: 4283).
- All 52 acceptance criteria in `functional-spec.md` ticked; both spec documents marked Completed.
- Orchestrator-run checks beyond the suite: legacy `--with-sync --with-synth --skip-graph` still parses; `--no-synth --with-synth` resolves to synth off; `resolve_lint_fail` maps `--strict` to `warnings` and takes the stricter when combined; all four Windows branch shapes correct; legacy letter-only status files render readable panels (`B` to "Maintain", unknown letter degrades safely, `{}` shows the setup prompt); an invalid `--schedule` exits 2 with a message naming the conflict and the fix; declining the wizard confirmation writes no status file, no units, no config change; a second `all` run over an unchanged vault converts 0 and exits 0.
- RED-probe residue checked and clean: log redirect still truncating, ingest command still byte-identical, no default-backend change.

Deferred to their own issues, deliberately not fixed here:

- **#161** — `synth --estimate` derives doc part pages differently from `synth`. Adjacent (this feature's wizard points users at that command for cost framing) but a `bug`, so CONTRIBUTING rule 1 forbids mixing it into a `feat` PR.
- **`llmwiki/agent_kit/skills/wiki-all/SKILL.md`** is stale in ways predating this feature: teaches `init` → `sync` → `graph` → `build` → `lint` (wrong order, `init` is not a pipeline stage, `synth` missing entirely), instructs manual per-stage commands rather than `llmwiki all`, and hardcodes an Obsidian vault path.
- **Package-name split** — `pyproject.toml` says `llm-wiki`; roughly ten places across `docs/` and `CLAUDE.md` say the PyPI distribution is `llm-notebook`, and `docs/deploy/pypi-publishing.md` asserts it as policy. Only the `[graph]` extra install command was unified here, in files this change already touched.

Next stage: user smoke confirm, then local review.
