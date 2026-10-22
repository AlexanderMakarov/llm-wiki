# Technical Specification: Doctor detects scheduled maintenance that no longer serves this vault

- **Functional Specification:** [functional-spec.md](functional-spec.md)
- **Status:** Completed
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Scheduler units become **per vault**: every OS job name carries a stable id derived from the resolved vault path, and every new wrapper pins `--vault <vault>` so a job never resolves its target from a checkout's `config.json` at run time (the root cause of the incident). A new pure module `llmwiki/automation_units.py` owns unit naming, discovery of installed units (per-vault and the legacy single `llmwiki-maintain` unit), wrapper parsing, liveness probes, deactivation and removal steps. `install-automation` uses it to write per-vault units, adopt the legacy unit when it serves the same vault, and guard against replacing a schedule that runs from another checkout. `llmwiki doctor` area L uses the same module to compare what the vault's status file declares with what the OS scheduler actually holds and whether the job has run recently. Heal-catalog entries cover every new finding and setup warning.

Systems touched: `automation_install.py`, new `automation_units.py`, `cron_spec.py`, `config_schedule.py`, `cli.py` (`install-automation`), `doctor/checks.py`, `doctor/runners.py`, `doctor/__init__.py` (confirm prompt), `doctor/models.py`, `doctor/heal_kb.json`, docs, CHANGELOG.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Unit naming and discovery — `llmwiki/automation_units.py` (new)

| Contract | Responsibility |
|---|---|
| `LEGACY_SYSTEMD = "llmwiki-maintain"`, `LEGACY_LAUNCHD = "com.llmwiki.maintain"` | Legacy names; `automation_install` constants move here. |
| `vault_unit_id(vault: Path) -> str` | `slug(basename)` + `-` + first 8 hex of sha1 over the resolved path (`os.path.normcase` first on macOS/Windows). Slug: lowercase, non `[a-z0-9]` → `-`, collapse repeats, trim, cap 24 chars, empty → `vault` (Cyrillic-only names become `vault-<hash>`). |
| `unit_names(vault: Path) -> UnitNames` | Frozen: `base` (`llmwiki-maintain-<id>`), `launchd_label` (`com.llmwiki.maintain.<id>`), `wrapper`, `service`, `timer`, `plist`, `task_xml`, `task_name`. |
| `InstalledUnit` (frozen) | `name, platform, legacy, wrapper_path, working_dir: Path\|None, target_vault: Path\|None, log_path: Path\|None, enabled: bool\|None, reason_unknown: str\|None`. |
| `discover_units(platform, *, home, run=run_scheduler_cmd, uid=None) -> DiscoveryResult` | `units: tuple[InstalledUnit, ...]`, `unavailable: str\|None`. |
| `unit_for_vault(vault, discovery) -> InstalledUnit \| None` | Per-vault id match first, else the legacy unit whatever its target. |
| `deactivate_unit(unit, *, run) -> str \| None` | Disable + remove files; returns error text or `None`. |
| `removal_steps(unit) -> list[str]` | Copy-pasteable OS-specific removal commands (R7). |
| `is_dev_checkout(root: Path) -> str \| None` | `"worktree"` when `root/.git` is a file, `"checkout"` when a dir, else `None`. |
| `run_scheduler_cmd(args)` | Moved from `automation_install._run_scheduler_cmd`; the single subprocess seam for install, CLI and doctor (injectable `run`). |

**Wrapper parsing.** `shlex.split` the wrapper line containing `-m llmwiki`: working dir = token after `cd`; target vault = token after `--vault`; log path = the redirect target after `>`. Without `--vault` (legacy units only), the target comes from `config_schedule.default_vault_for_checkout(wd)` (new: `<wd>/config.json` then `<wd>/examples/sessions_config.json`, mirroring `_load_sessions_config` precedence). Missing/unreadable wrapper or gone checkout → `target_vault=None` with `reason_unknown`; never guess.

**Per-platform inspection.**

| Platform | Discovery | Liveness |
|---|---|---|
| Linux | `~/.config/systemd/user/llmwiki-maintain*.service` → `ExecStart` wrapper, `WorkingDirectory` | `systemctl --user is-enabled <name>.timer`; missing systemctl / "Failed to connect" → unavailable |
| macOS | `plistlib` on `~/Library/LaunchAgents/com.llmwiki.maintain*.plist` → `ProgramArguments[1]`, `WorkingDirectory` | `launchctl print gui/<uid>/<label>`: rc 0 loaded; "Could not find service" unloaded |
| Windows | `schtasks /Query /FO CSV /NH` filtered to `\llmwiki-maintain*`, then `schtasks /Query /TN <name> /XML` → `Exec/Arguments`, `WorkingDirectory` (`xml.etree`, encoding declaration stripped, `errors="replace"`) | Task presence; any non-zero rc / parse error → unavailable |
| Other | — | unavailable |

### 2.2 Install — `automation_install.run_install` and `cli.cmd_install_automation`

- **Per-vault files.** Staging stays flat in `~/.automation` (or `--units-dir`) with unique names from `unit_names(vault_root)`. Activation uses the per-vault names on all three platforms.
- **Always pin `--vault`.** New units always pass `command_vault=vault_root`; `_scheduled_command_vault`'s "omit when equal to config default" no longer applies to the wrapper. Behaviour of the job is unchanged; only its target is explicit.
- **Status keys added** (`<vault>/.llmwiki/automation-status.json`): `installed_at` (reset on every successful activation, so a repair clears `stale_run`), `scheduler_unit`, `working_dir`, `target_vault` (private status file only, never printed), `adopted_legacy: bool`, `legacy_adopt_error: str|None`. Existing keys keep their meaning.
- **Legacy adoption (R1 AC3/AC4).** After the new unit activates, if the discovered legacy unit's `target_vault` resolves equal to `vault_root`, `deactivate_unit` it (systemd: `disable --now llmwiki-maintain.timer`, unlink `.sh/.service/.timer`, `daemon-reload`; launchd: `bootout`, unlink plist + `.sh`; Windows: `schtasks /Delete /TN llmwiki-maintain /F`, unlink staging xml + `.sh`) and print that it was replaced. Failure to deactivate does not fail the install: record `legacy_adopt_error` and print the manual step. Legacy units with unknown or other targets are untouched.
- **Guard (R2).** Before `run_install`, `unit_for_vault(vault_root)` → if a unit serving this vault has a `working_dir` ≠ `REPO_ROOT.resolve()`, print "current schedule runs from: …" / "new schedule would run from: …" (user's own terminal — full paths OK). Interactive (no `--yes`, TTY): `[y/N]` after `_confirm_plan`. `--yes` or non-TTY without `--force`: exit 2 with `install-automation: existing schedule runs from a different checkout; pass --force to replace it`.
- **`--force` flag** (new, `install-automation` only) skips the guard question; warnings still print.
- **Dev-checkout warning.** When `is_dev_checkout(REPO_ROOT)`: "the scheduled job will keep using this copy at <REPO_ROOT>; deleting or switching it breaks the schedule" (stronger wording for `worktree`). Printed before the TTY question and with `--force`.
- `_print_manual_scheduler_activation` takes names from `unit_names` instead of hardcoding. `setup.sh` needs no change (interactive path gets the guard).

### 2.3 Schedule interval — `cron_spec.cron_interval(spec) -> timedelta`

Largest gap between firings (generous, avoids false warnings): no day/month restriction → 1 day; weekdays only → largest cyclic gap between chosen weekdays (7 days for one); days-of-month set → 31 days; months restricted → 366 days.

### 2.4 Doctor — area L detectors (`doctor/checks.py`)

`check_automation(vault, *, now=None, discovery=None)` (injectable for tests). No status or no `job` → no findings.

| id | severity | tier | runner | Fires when |
|---|---|---|---|---|
| `automation.unit_missing` | error | dangerous | `install_automation` | Status declares a job; no per-vault unit and no legacy unit found. |
| `automation.points_elsewhere` | error | dangerous | `install_automation` | `unit_for_vault` target resolves to another vault. Message: "schedule <name> serves vault '<other basename>', not this vault '<this basename>'". |
| `automation.checkout_missing` | error | dangerous | `install_automation` | Unit targets this vault but its working dir / wrapper is gone. |
| `automation.not_active` (existing) | warning | dangerous | `install_automation` | Recorded not switched on (`scheduler_activated`/`scheduler_active`, falling back to `activated`/`active`; `None` is not inactive; note heuristics kept), or live probe says disabled/unloaded (message names the live state). |
| `automation.stale_run` | warning | dangerous | `install_automation` | Never ran after > 2× interval since `installed_at` (fallback `updated_at`; neither → skip); last run older than 2× interval (humanised age); last `EXIT:<n>` ≠ 0 (names log path). Log without EXIT and mtime < 6h = in progress → quiet. |
| `automation.check_unavailable` | info | guided | null | Scheduler cannot be inspected, or legacy unit target unknown. |
| `automation.orphan_unit` | warning | guided | null | One finding listing every discovered unit whose target vault dir no longer exists, with `removal_steps`. Fires on any vault. |
| `automation.setup_other_checkout` | warning | guided | null | Catalog-only entry for the R2 guard message (for `--error`). |
| `automation.setup_dev_checkout` | warning | guided | null | Catalog-only entry for the R2 dev-checkout warning. |

**Suppression:** when `unit_missing` / `points_elsewhere` / `checkout_missing` fires, skip `not_active` and `stale_run` (one cause, one finding). `orphan_unit` is independent. `_dedupe_findings` is unchanged (orphans aggregate into one finding).

**Last-run source order:** unit wrapper's log path → `status.log_path` → `vault_automation_log_path(vault)` → legacy `default_log_path()` (R5 AC5). Time = log mtime; result = last `EXIT:<n>` line.

**Backlog (R6).** `check_pipeline_backlog` appends "Scheduled maintenance is recorded for this vault but may not be reaching it — see the automation findings in this report." when the status has a `job`; the `synth` runner stays.

### 2.5 Doctor repair — `doctor/runners.py`, `doctor/__init__.py`, `doctor/models.py`

- `install_automation_argv(vault, status) -> list[str]`: `install-automation --vault <v> --yes --force --job … [--graph …] [--lint-fail …] --schedule … --synth-backend <status.synth_backend> [--watch-enabled]` from `plan_from_status` / `schedule_from_status`. Hooks are not reproduced (`--yes` never installs them); the fix text says so. Used by both display and dispatch (fixes today's non-TTY failure where the runner omits `--yes`).
- `Finding.runner_argv: tuple[str, ...] | None` (new optional field) so `_confirm_finding` stays generic: it prints `will run: <shlex.join(argv)>` and, for `install_automation`, `runs from: <REPO_ROOT>` plus the dev-checkout warning when applicable (doctor launched from a worktree would otherwise re-point the schedule there).
- Tier stays dangerous: `--yes` alone never applies it; non-TTY prints the plan.

### 2.6 Heal catalog — `doctor/heal_kb.json`

New entries for every id above with patterns covering exact message stems and symptoms ("schedule points at another vault", "automation not running", "scheduled maintenance missing", "last run failed", "leftover schedule", "different checkout", "worktree"). Placed before `automation.not_active`; that entry's broad `"install-automation"` pattern becomes `"declared but not active"` so setup messages don't match it. Guided entries keep `runner: null`.

### 2.7 Docs

`docs/reference/cli.md` (install-automation: per-vault units, `--force`, guard, dev-checkout warning, status fields; doctor area L findings), `docs/reference/state-persistence.md` (new status keys), `docs/UPGRADING.md` note (legacy single unit adopted on next install/repair for the vault it serves; vault rename → orphan + missing), `CHANGELOG.md` `[Unreleased]` Added/Changed/Fixed.

---

## 3. Impact and Risk Analysis

- **System Dependencies:** OS schedulers (systemd user, launchd, schtasks) via one subprocess seam; status file consumers (`build.render_automation_panel` reads only existing keys — unaffected); `setup.sh` interactive install; doctor heal loop and `--error` matcher.
- **Risks & Mitigations:**
  - *Duplicate jobs after upgrade* (legacy + per-vault both firing) → adoption removes legacy when it serves the same vault; doctor shows nothing extra because `unit_for_vault` prefers the per-vault unit, and an unadopted legacy unit targeting a missing vault surfaces as `orphan_unit`.
  - *Vault moved/renamed changes the id* → old unit becomes `orphan_unit`, new vault reports `unit_missing`; repair + removal steps resolve both; documented in UPGRADING.
  - *Symlinked paths* → always `resolve()` before hashing/comparing.
  - *False "not active" on headless Linux (no user bus)* → `check_unavailable` instead.
  - *Doctor repair run from a worktree re-points the schedule there* → confirm prompt shows "runs from" and the dev-checkout warning; tier is dangerous.
  - *Exact-string tests of `plan_command` output* change with pinned `--vault` → update them in the same change.
  - *Privacy* → other vault shown as basename only; full paths only in the user's own install terminal; tests use `tmp_path` and placeholders.
  - *Matcher order* → new entries before `not_active`; KB match tests assert each stem maps to the right id.

---

## 4. Testing Strategy

All subprocess calls go through the injected `run` fake (scripted `CompletedProcess`) with `home=tmp_path`; the existing `_fake_systemctl` PATH shim stays for end-to-end install. No real `systemctl`/`launchctl`/`schtasks`. Extend existing modules; no issue-number filenames.

- `tests/test_automation_install.py`: id stability and slug edge cases (Cyrillic, spaces, case); wrapper parse round-trip from `render_wrapper_script` with spaces/quotes/`&`; legacy wrapper without `--vault` + `<wd>/config.json`; plist/task-XML parsing from rendered fixtures; discovery-unavailable branches; two vaults → two unit sets, A keeps `--vault A`; legacy adoption (same vault: deactivate recorded, files removed, message; other vault: untouched); guard (TTY y/n, `--yes` without `--force` exits 2, `--force` proceeds with warning); dev-checkout warning for `.git` file and dir; `installed_at` reset.
- `tests/test_cron_spec.py`: `cron_interval` daily, multi-hour, Mon/Thu (4d), weekly, monthly, restricted months.
- `tests/test_doctor_checks.py`: positive + negative twin per finding (fails when the rule is removed); R3 key fix incl. legacy `activated: false`; suppression; no status → no findings; backlog wording with/without job.
- `tests/test_doctor_runners.py`: `install_automation_argv` mirrors status; confirm output contains exact argv and dev warning; `--yes` on non-TTY does not run it.
- `tests/test_doctor_kb_match.py`: each new message stem and symptom phrase maps to its id; setup-warning text no longer maps to `not_active`.
- `tests/test_doctor_acceptance.py`: catalog invariants for new entries; incident replay — real-vault install, then a legacy-style unit from a fake worktree targeting a test vault → doctor on real vault reports `points_elsewhere` (error) → repair through a fake runner calling `run_install` → fresh check has no automation error and the test vault's unit is untouched.
