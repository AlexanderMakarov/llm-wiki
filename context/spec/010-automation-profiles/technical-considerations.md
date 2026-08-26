# Technical Specification: Plain-language automation setup

- **Functional Specification:** [`functional-spec.md`](functional-spec.md) (Status: Approved)
- **Status:** Completed
- **Author(s):** Alexander Makarov
- **Issue:** [#156](https://github.com/AlexanderMakarov/llm-wiki/issues/156)

---

## 1. High-Level Technical Approach

Four changes, in dependency order.

1. **`llmwiki all` flips from opt-in to opt-out.** Today `run_pipeline` gates sync and synth behind `--with-sync` / `--with-synth`. The flip happens entirely at the argparse layer: the namespace attributes `with_sync` / `with_synth` keep their names and meaning, their **defaults become `True`**, and new `--no-sync` / `--no-synth` flip them off. `run_pipeline`'s body is untouched for those two stages. The old `--with-*` flags stay registered so existing scheduled commands keep parsing, and emit a deprecation notice. `--skip-lint` completes the opt-out set; lint gains a three-level failure policy.

2. **Scheduling moves to cron expressions.** `hour` / `minute` integers are replaced by a single cron expression, parsed once into a normalised spec and rendered three ways (systemd `OnCalendar`, launchd `StartCalendarInterval`, Windows Task Scheduler XML). This is what makes "weekdays only" and similar expressible. Cron is the *notation*; none of the three backends is cron, so translation is the work.

3. **Two new modules own the vocabulary**, so no logic is written twice: `llmwiki/automation_plan.py` (what the job does) and `llmwiki/cron_spec.py` (when it runs). Both are dependency-free leaves that `automation_install.py`, `cli.py`, and `build.py` import.

4. **Everything user-visible is regenerated from those two modules** — the wizard, the scheduled command, the Home Automation panel, the Home *Commands* table, and six documentation files.

No new runtime dependencies. Everything is stdlib plus the existing `markdown`.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 DRY: one definition per concept

Called out first because it constrains every section below. Each row is a fact that currently would be — or today already is — expressible in more than one place. After this change each has exactly one home, and every other site calls it.

| Concept | Single source of truth | Callers |
|---|---|---|
| What the scheduled shell command is | `automation_plan.plan_command()` | `render_wrapper_script`, wizard confirmation, tests |
| Human name of a job (`Maintain + graph (built-in)`) | `automation_plan.plan_label()` | wizard summary, Home Automation panel, status file `label` key |
| Whether a job can spend tokens | `automation_plan.spends_tokens()` | wizard cost line, Home panel |
| Legacy `A`/`B`/`C` → plan | `automation_plan.LEGACY_PROFILE_MAP` | `--profile` flag, wizard input, `plan_from_status` |
| Cron expression → schedule | `cron_spec.parse_cron()` | all three unit renderers, wizard, `--schedule` |
| Human name of a schedule (`Weekdays at 08:00`) | `cron_spec.describe()` | wizard summary, Home panel, status file |
| Prompt-with-re-ask loop | `cli._ask_choice()` | all new wizard questions |
| Lint failure policy resolution (`--strict` → `warnings`) | `pipeline.resolve_lint_fail()` | `run_pipeline`, tests |

Two deletions enforce this rather than leaving duplicates behind: `automation_install.profile_command` is **removed** (not wrapped) once `plan_command` exists, and the `hour: int, minute: int` parameters are **removed** from all three unit renderers rather than kept alongside a schedule argument. A parameter kept "just in case" is the duplication.

One honest exception: the command strings on the Home page (`render/js.py`) and in `docs/cheatsheet.md` describe the same commands in two media — an HTML table built in JavaScript and a markdown table. Unifying them would mean generating docs from code, which is out of scope here. They are kept consistent by review, and this spec lists both so neither is forgotten.

### 2.2 New module: `llmwiki/cron_spec.py`

Parses a standard 5-field cron expression and renders it for each scheduler backend. Stdlib only, no dependency on the rest of `llmwiki`.

| Symbol | Responsibility |
|---|---|
| `CronSpec` | Frozen dataclass: `minutes`, `hours`, `days_of_month`, `months`, `days_of_week` — each a sorted tuple of ints, or `None` for `*`. |
| `parse_cron(expr) -> CronSpec` | Parses `M H DOM MON DOW`. Raises `CronError` with a readable message on anything unsupported. |
| `describe(spec) -> str` | Human text: `Every day at 08:00`, `Weekdays at 08:00`, `Mondays at 09:30`. |
| `to_systemd_oncalendar(spec) -> str` | e.g. `Mon-Fri *-*-* 08:00:00`. |
| `to_launchd_intervals(spec) -> list[dict[str,int]]` | Expanded cross-product of dicts (see below). |
| `to_windows_trigger(spec) -> str` | `ScheduleByDay` or `ScheduleByWeek` XML fragment. |
| `CronError` | Raised for unsupported input; the CLI turns it into an exit-2 usage error. |

**Supported grammar:** `*`, integer, list (`1,15`), range (`1-5`), step (`*/15`, `1-5/2`). Day-of-week accepts `0-7` (both `0` and `7` are Sunday) and the three-letter names `SUN`–`SAT`; months accept `1-12` and `JAN`–`DEC`.

**Deliberately rejected**, each with a specific error message rather than silent misbehaviour:

- Nicknames (`@daily`, `@reboot`) — `@reboot` has no calendar meaning at all, and accepting some nicknames but not others is worse than accepting none.
- Vixie/Quartz extensions (`L`, `W`, `#`, seconds field).
- **Day-of-month and day-of-week both restricted.** In cron these OR together (`0 8 1 * MON` fires on the 1st *and* on Mondays), and neither systemd, launchd, nor Windows can express that. Rendering it as an AND would be silently wrong on all three, so it is refused with a message naming the conflict. This is the single most important guard in the module.

**launchd expansion.** `StartCalendarInterval` takes either one dict or an array of them, and each dict is an AND of its keys. So a spec is expanded into the cross-product of its restricted fields: `0 8 * * 1-5` becomes five dicts (`{Hour: 8, Minute: 0, Weekday: 1..5}`). The renderer emits a single dict when the product has one element (preserving today's output byte-for-byte for the daily case) and an array otherwise. A guard caps the expansion — an expression like `*/1 * * * *` would produce 1440 entries — and `CronError` explains that such a schedule belongs in `llmwiki watch`, not a daily timer.

**Windows.** `ScheduleByDay/DaysInterval` when day-of-week is unrestricted; `ScheduleByWeek` with `<DaysOfWeek>` children otherwise. The existing hardcoded `StartBoundary` date is retained, with the time taken from the spec's first hour/minute.

### 2.3 New module: `llmwiki/automation_plan.py`

The shared vocabulary for "what should the daily job do". It lives in its own module rather than inside `automation_install.py` so `build.py` — which only needs to *render* a label — does not import the installer. Same dependency direction as the existing `automation_status.py`, which `build.py` already imports.

| Symbol | Shape | Responsibility |
|---|---|---|
| `Job` | `Literal["ingest", "maintain"]` | Base choice (spec R1). |
| `GraphChoice` | `Literal["none", "builtin", "graphify"]` | Graph extra + builder (R2, R4). `"none"` = extra not selected. |
| `LintFail` | `Literal["never", "errors", "warnings"]` | Failure policy (R2, R3). |
| `AutomationPlan` | frozen dataclass: `job`, `graph`, `lint_fail` | Defaults `ingest` / `none` / `never`. |
| `plan_command(plan, *, python_bin, working_dir) -> str` | | Composes the scheduled shell line (§2.4). |
| `plan_label(plan) -> str` | | `Maintain + graph (built-in)`. |
| `spends_tokens(plan) -> bool` | | `plan.job == "maintain"`. |
| `plan_to_status(plan) -> dict` / `plan_from_status(status) -> AutomationPlan` | | Status round-trip (§2.5). |
| `LEGACY_PROFILE_MAP` | `{"A": ingest, "B": maintain, "C": maintain}` | Used by `--profile`, wizard input, and status back-compat alike. |

### 2.4 Command composition

`plan_command` replaces `automation_install.profile_command`, which is deleted.

| Job | Emitted command (after `cd <working_dir> &&`) |
|---|---|
| `ingest` | `<py> -m llmwiki sync` — byte-for-byte what profile A emits today (R7). |
| `maintain` | `<py> -m llmwiki all` plus, in fixed order: `--skip-graph` when `graph == "none"`, else `--graph-engine {builtin,graphify}`; then `--lint-fail {errors,warnings}` when the policy is not `never`. |

Flag order is fixed so rendered-command tests are exact string comparisons. Note what is *absent* from `maintain`: no `--with-sync` / `--with-synth`, because after the flip they are the default — which is the readability argument for the flip.

### 2.5 Status file and backward compatibility

**No new file is introduced.** `.llmwiki/automation-status.json` already exists: `run_install` writes it today via `automation_status.save_status`, and it is the only channel by which the built site learns anything about automation — `build.render_automation_panel` reads it through `load_status`. This change adds keys to that existing file.

Why it is separate from `config.json` (the pre-existing split, restated because it was unclear): `config.json` is user-authored, gitignored, and lives in the clone; `automation-status.json` is machine-written and lives **under the vault**, because the site build reads the vault, not the clone. Putting automation state in `config.json` would make it invisible to `build`.

New keys:

| Key | Value | Why |
|---|---|---|
| `job` | `"ingest"` \| `"maintain"` | The plan. |
| `graph` | `"none"` \| `"builtin"` \| `"graphify"` | The plan. |
| `lint_fail` | `"never"` \| `"errors"` \| `"warnings"` | The plan. |
| `schedule` | cron expression, e.g. `"0 8 * * 1-5"` | Replaces `hour` / `minute` as the source of truth. |
| `schedule_label` | `"Weekdays at 08:00"` | From `cron_spec.describe()`. |
| `label` | `"Maintain + graph (built-in)"` | From `plan_label()`. |
| `profile` | `"A"` for ingest, `"B"` for maintain | **Still written** so an older `llmwiki` reading a newer file keeps working. |
| `hour`, `minute` | first firing hour/minute | **Still written** for the same reason; derived from the spec, not authored. |

`plan_from_status` reads `job` when present and falls back to `LEGACY_PROFILE_MAP[status["profile"]]`, then to the `ingest` default. Schedule reading is symmetric: `schedule` when present, else `"{minute} {hour} * * *"` synthesised from the legacy integers. Both fallbacks live in these two modules only — `render_automation_panel` never inspects raw keys itself.

### 2.6 `llmwiki all`: opt-in → opt-out

**Argparse changes** (`llmwiki/cli.py`, `all` parser):

| Flag | Action | Notes |
|---|---|---|
| `--no-sync` | `store_false`, `dest="with_sync"` | New. `with_sync` default flips to `True`. |
| `--no-synth` | `store_false`, `dest="with_synth"` | New. `with_synth` default flips to `True`. |
| `--skip-lint` | `store_true` | New. Mirrors `--skip-graph`. |
| `--lint-fail {never,errors,warnings}` | default `never` | New (R3). |
| `--with-sync` / `--with-synth` | `store_true`, `dest="legacy_with_sync"` / `"legacy_with_synth"` | **Kept, deprecated, inert.** |
| `--strict` | unchanged | Alias for `--lint-fail warnings`. |

The legacy flags land on throwaway destinations so they cannot *re-enable* a stage the user just disabled; since the real default is already `True` they have nothing to contribute. They exist so an already-installed scheduled command does not die on argparse's "unrecognized arguments" — a hard failure strictly worse than the behaviour change being shipped. `cmd_all` prints one stderr line when either is set.

Documented resolution for `--no-synth --with-synth`: `--no-synth` wins. Stated in `docs/reference/cli.md`, not left to argparse ordering.

**`run_pipeline` changes** (`llmwiki/pipeline.py`):

- The `if args.with_sync:` / `if args.with_synth:` guards are **unchanged** — the flip is upstream at the default. Deliberate: `tests/test_cmd_all_parser.py:37` and `tests/test_issue_383_pipeline.py` build `argparse.Namespace` by hand with these exact keys and keep working.
- Lint becomes conditional on `not getattr(args, "skip_lint", False)`; `getattr` with a default keeps hand-built namespaces valid.
- A new `resolve_lint_fail(args) -> LintFail` maps `--strict` to `warnings` and takes the stricter when both are given. The escalation block becomes a branch over the `summary` dict `_run_lint_step` already returns:

  | Policy | Fails when |
  |---|---|
  | `never` (default) | never — findings reported, run exits 0 |
  | `errors` | `summary["error"] > 0` |
  | `warnings` | `summary["error"] > 0 or summary["warning"] > 0` |

  Exit code stays `2`, matching today's `--strict`.

**First-run notice** (R6): before the synth stage, emit one line when all three hold — the stage is about to run, `load_synthesis_backend()` is not `"dummy"`, and `sys.stdout.isatty()`. The TTY check is what silences scheduled runs: the wrapper redirects stdout to the log, so a timer-driven run is never a TTY. "First time" uses a one-shot flag in the existing state store (`ops.all_optout_notice_shown`) via the `update_state` helper `pipeline.py` already imports.

### 2.7 The wizard (`cmd_install_automation`)

Question order puts the consequential choice first; every prompt re-asks on invalid input rather than silently defaulting (R1, R2).

1. **Daily job** — two numbered choices with the folders-written and cost lines from R1. Accepts `1`/`2` and `A`/`B`/`C` via `LEGACY_PROFILE_MAP`. Enter → `ingest`.
2. **Extras** (maintain only) — comma-separated numbers; Enter → none. Both failure policies selected resolves to `warnings` with a printed note.
3. **Graph builder** (only if the graph extra was chosen) — Enter → `builtin`. Choosing `graphify` when `graphifyy` is not importable prints a fallback warning and continues (R4). The probe is an import attempt inside the handler — a legitimate deferred import for an optional extra, carrying `# noqa: PLC0415` with that reason per the enforced ruff rule.
4. **When it runs** — a preset menu rather than raw cron, with cron as the escape hatch:

   | Choice | Cron | Then asks |
   |---|---|---|
   | Every day | `M H * * *` | time |
   | Weekdays only (skip weekends) | `M H * * 1-5` | time |
   | Once a week | `M H * * D` | day + time |
   | Custom cron expression | as typed | — |

   The typed expression is validated with `parse_cron` immediately and re-asked on `CronError`, so an invalid schedule can never reach a unit file. Every branch produces a cron string; there is one code path downstream.
5. Existing questions retained: synth backend, agent hooks, watch, units dir.
6. **Confirmation summary** (R5) — `plan_label`, `cron_spec.describe()`, and the exact composed command. Declining writes nothing at all, which means the `config.json` synth-backend write must move to *after* confirmation; today it happens before `run_install`.

`_ask_choice(prompt, valid, default)` absorbs the re-ask loop so the new questions do not each hand-roll it.

### 2.8 Non-interactive flag matrix (R8)

Names are the primary interface; letters survive only as legacy input.

| Flag | Values | Maps to |
|---|---|---|
| `--job {ingest,maintain}` | | `plan.job`. New, and the documented spelling. |
| `--profile {A,B,C}` | | **Deprecated, still accepted.** Translated via `LEGACY_PROFILE_MAP`; prints a one-line notice naming `--job`. |
| `--graph {none,builtin,graphify}` | default `none` | `plan.graph`. One flag covers "is it on" and "which builder". |
| `--lint-fail {never,errors,warnings}` | default `never` | `plan.lint_fail`. Same spelling as the `all` flag, deliberately. |
| `--schedule "<cron>"` | default `"0 8 * * *"` | The schedule. Validated by `parse_cron`; `CronError` exits 2 with the message. |
| `--hour N` / `--minute N` | | **Deprecated, still accepted.** Translated to `"{minute} {hour} * * *"`; ignored when `--schedule` is given, with a notice. |
| `--yes`, `--synth-backend`, `--units-dir`, `--watch-enabled`, `--force-platform`, `--vault` | | unchanged |

`--job` and `--profile` together: `--job` wins with a stderr note. Every flag here needs its row in `docs/reference/cli.md` — `tests/test_cli_doc_parity.py` fails the build otherwise.

### 2.9 Site surfaces

Two panels on the built Home page, both currently wrong after this change.

**Automation panel** (`build.render_automation_panel`) — replaces `Scheduler profile: <B>` with `plan_label(plan_from_status(status))`, shows `schedule_label` instead of a raw `HH:MM`, adds a line stating whether the job can spend tokens (`spends_tokens`), and adds a line when `lint_fail != "never"`. Everything else untouched; HTML escaping unchanged.

**Commands table** (`llmwiki/render/js.py:97-115`) — thirteen copy-paste rows, all manual, no automation row. This is the site telling users llmwiki is a daily chore list, the same defect R10 fixes in the docs. Changes:

- Add a leading row for `llmwiki install-automation` described as the way to stop running the rest by hand.
- Add `llmwiki all` — the one-command manual equivalent of the daily job — which the table omits entirely today.
- Update the `llmwiki synth --estimate` row's purpose text, since the wizard now points users at it for cost.

### 2.10 Documentation

| File | Change |
|---|---|
| `docs/reference/cli.md` | `all` section + flag table (opt-outs, lint policy, deprecated aliases); `install-automation` section rewritten outcome-first with the new flag table. |
| `docs/cheatsheet.md` | Automation as the normal path, manual commands as the one-off alternative. Fix verified stale facts: `pip install llm-notebook[graph]` → `llm-wiki[graph]`; "11 CLI commands" over a 12-row table when there are 25; "14 wiki-quality rules" and "17 structural rules" contradicting each other on one page. |
| `docs/getting-started.md`, `docs/tutorials/00-quickstart-walkthrough.md` | After the first successful build, the next step offered is automation. |
| `docs/UPGRADING.md` | `all` behaviour change; re-run `install-automation` to refresh the wrapper; `--hour`/`--minute` → `--schedule`. |
| `CHANGELOG.md` | Under `[Unreleased]`, flagged as a **behaviour change**, not only a feature. |

---

## 3. Impact and Risk Analysis

### System Dependencies

- `llmwiki/pipeline.py` — lint policy, `skip_lint`, first-run notice.
- `llmwiki/cli.py` — the `all` parser and the whole `install-automation` command.
- `llmwiki/automation_install.py` — all three unit renderers change signature (`hour`/`minute` → `CronSpec`); `run_install` takes a plan + schedule.
- `llmwiki/build.py`, `llmwiki/render/js.py` — the two Home panels.
- `llmwiki/config_schedule.py` — `synthesis_status_hint` hardcodes `` `llmwiki all --with-synth` `` at ~lines 141 and 146; both lose the now-redundant flag, and `tests/test_issue_383_pipeline.py` asserts on that exact substring.
- `setup.sh` — unchanged; it only invokes the command.

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **A bare `llmwiki all` in someone's cron starts spending tokens.** The headline risk. | `load_synthesis_backend()` defaults to `"dummy"`, which makes no provider call — a default install spends nothing. Configured users get the interactive first-run notice, an `UPGRADING.md` entry, and a CHANGELOG behaviour-change line. `--no-synth` is the documented opt-out. |
| **Existing scheduled commands fail to parse** — worse than a behaviour change, because it is silent until the timer fires. | `--with-sync` / `--with-synth` stay registered; a dedicated test asserts the old profile-C command line still parses. |
| **Cron translation is silently wrong on one platform.** A wrong schedule is invisible until the job does not run. | Table-driven tests assert the rendered output of all three backends for the same set of expressions. The DOM+DOW combination — the one case none of the three can express — is refused at parse time rather than mistranslated. |
| **launchd expansion explodes** on a dense expression. | Cross-product size is capped, with a `CronError` pointing at `llmwiki watch` for sub-hourly needs. |
| **Two former profiles collapse to one.** | `LEGACY_PROFILE_MAP` sends `B` and `C` to `maintain` with `graph="none"` — which is what `C` already did, since it hardcoded `--skip-graph`. |
| **`--strict` semantics drift** from today's "errors *or* warnings". | Mapped explicitly to `lint_fail="warnings"`; a test pins the equivalence. |
| **The wizard is interactive and easy to leave untested.** | Tests monkeypatch `builtins.input` with scripted answers and assert the resulting plan, schedule, and rendered command. No new test dependency. |
| **Diff size.** | See §5 — decided as one PR with a waiver; the fallback seam is recorded. |

---

## 4. Testing Strategy

All `pytest`, no new dependencies, vault-touching tests use `tmp_path` — never the operator's live vault.

**New — `tests/test_cron_spec.py`:**
- `parse_cron` accepts `*`, int, list, range, step, day names, month names; `0`/`7` both mean Sunday.
- `CronError` for each rejected form, asserting the message names the reason: nicknames, `L`/`W`/`#`, a seconds field, and DOM+DOW both restricted.
- `describe()` for daily / weekday / weekly / custom.
- Table-driven renderer tests: for each of ~6 expressions, assert the systemd `OnCalendar` string, the launchd interval list, and the Windows trigger fragment.
- `0 8 * * *` renders a **single** launchd dict, not a one-element array (byte-compatible with today's plist).
- The expansion cap raises `CronError` rather than emitting thousands of entries.

**New — `tests/test_automation_plan.py`:**
- `plan_command` exact-string for every combination: ingest; maintain bare; maintain + each graph choice; maintain + each lint policy; maintain + both.
- Ingest's command is byte-identical to the pre-change profile-A string (R7 regression guard).
- `plan_to_status` / `plan_from_status` round-trip.
- `plan_from_status` on legacy dicts: `profile: "A"`/`"B"`/`"C"`, an unknown letter, and no `profile` key.
- Legacy schedule fallback: a status with only `hour`/`minute` yields the equivalent cron spec.
- `plan_label` never returns a bare letter.

**New — `tests/test_all_optout.py`:**
- Bare `all` parses to `with_sync is True` and `with_synth is True`.
- `--no-sync` / `--no-synth` flip each independently.
- The full legacy profile-C line (`all --with-sync --with-synth --skip-graph`) still parses and runs every stage.
- `--skip-lint` skips lint (same stubbing pattern as `tests/test_issue_383_pipeline.py`).
- Policy matrix: `never`/`errors`/`warnings` × summaries `{}`, `{error:1}`, `{warning:1}` → expected exit code. `--strict` ≡ `--lint-fail warnings`.
- First-run notice silent when not a TTY, and silent for `dummy` even on a TTY.

**Extended — `tests/test_automation_install.py`:** existing four tests keep passing (`test_run_install_writes_status_and_units` needs its `"profile": "A"` key updated). New: scripted-`input()` wizard runs producing each plan and schedule; Enter-through yields ingest and asks neither extras nor builder; invalid input re-asks; both failure policies → `warnings`; the weekday preset produces `* * 1-5`; declining confirmation writes no status file, no units, no `config.json` change.

**Extended — panel tests:** `render_automation_panel` shows the human label and schedule label for a new-format status and for a legacy letter-only status; the token-spend line appears only for maintain. A test asserts the `render/js.py` commands table contains an `install-automation` row.

**Docs parity:** `tests/test_cli_doc_parity.py` already enforces that every new flag appears in `docs/reference/cli.md` — the gate, not an extra test.

**Manual verification:** run the wizard against `.worktree-vault`, read back the generated `.llmwiki/units/*`, build the site into the throwaway vault, and view both Home panels.

---

## 5. File-by-File Change List

| File | Change | Est. lines |
|---|---|---|
| `llmwiki/cron_spec.py` | **New** — parser, guards, three renderers, `describe` | ~200 |
| `llmwiki/automation_plan.py` | **New** — dataclass, composer, label, status round-trip, legacy map | ~130 |
| `llmwiki/cli.py` | `all` flags; deprecation notices; wizard rewrite; `install-automation` flags | ~160 |
| `llmwiki/automation_install.py` | Plan-based command; three renderers take a `CronSpec`; `run_install` signature | ~70 |
| `llmwiki/pipeline.py` | `skip_lint`; `resolve_lint_fail`; policy branch; first-run notice | ~40 |
| `llmwiki/build.py` | Panel label, schedule label, two lines | ~20 |
| `llmwiki/render/js.py` | Commands table: automation + `all` rows | ~10 |
| `llmwiki/automation_status.py` | `empty_status()` gains new keys | ~8 |
| `llmwiki/config_schedule.py` | Drop `--with-synth` from two hint strings | ~4 |
| **Code subtotal** | | **~642** |
| `tests/test_cron_spec.py` | New | ~170 |
| `tests/test_automation_plan.py` | New | ~120 |
| `tests/test_all_optout.py` | New | ~120 |
| `tests/test_automation_install.py` | Wizard + schedule tests | ~90 |
| Panel / js-table tests, `test_issue_383_pipeline.py` | Extended | ~35 |
| **Test subtotal** | | **~535** |
| `docs/reference/cli.md` | Two sections + two flag tables | ~80 |
| `docs/cheatsheet.md` | Automation-first + stale-fact fixes | ~40 |
| `docs/getting-started.md`, `docs/tutorials/00-quickstart-walkthrough.md` | Next-step pointers | ~30 |
| `docs/UPGRADING.md`, `CHANGELOG.md` | Behaviour-change entries | ~35 |
| **Docs subtotal** | | **~185** |
| **Total** | | **~1362** |

The earlier estimate was ~875; cron support adds roughly 490 lines across the new module, its renderers, and its tests. **This is well past the ≤500-line target and materially past the figure the one-PR waiver was agreed against**, so §6 revisits that decision rather than treating it as settled.

---

## 6. PR shape

**Decided: one PR, with the waiver extended to the ~1362-line figure.** Re-confirmed by the maintainer after cron support raised the estimate from ~875.

The PR body must carry a waiver line stating the split (~642 code / ~535 tests / ~185 docs) and that the diff is one intent — tests and docs are mandatory under CONTRIBUTING rules 5 and 6, and rule 6 forbids landing a CLI change whose documentation arrives in a different PR.

If a reviewer nonetheless asks for a split, two clean seams exist, in preference order. Recorded so the choice is not re-derived under review pressure:

1. **Cron out first** — `feat: cron expressions for scheduled automation` (~370 lines: the module, the three renderers, `--schedule`, tests, docs), then the wizard redesign (~990) on top. `cron_spec.py` is dependency-free and has no behavioural coupling to the wizard, so it is the cheapest thing to lift out.
2. **The `all` flip out first** — `feat: llmwiki all runs every stage by default` (~200 lines), leaving ~1160.

---

## 7. Deferred

- **#161** (`synth --estimate` derives doc part pages differently from `synth`) is adjacent — this feature's wizard points users at `synth --estimate` for cost framing — but it is a `bug`, and shipping it here would violate CONTRIBUTING rule 1. Its own PR.
