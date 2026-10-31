# Technical Specification: Automation never fails silently

- **Functional Specification:** [functional-spec.md](functional-spec.md)
- **Status:** Approved
- **Author(s):** Alexander Makarov

---

## 1. High-Level Technical Approach

Every pipeline part records its latest outcome in a new `outcomes` section of `<vault>/llmwiki-state.json`. The state store already rewrites `<vault>/llmwiki-state.js` on every write, and `copy_state_sidecar_to_site` puts it into `site/`, which Home loads with a plain `<script>`: a browser refresh shows a new outcome without a rebuild — the route the lint note already uses (#256).

Writers: `run_pipeline` (`all`, the Maintain job), and full manual runs of `sync`, `synth`, `build`. A clean finish deletes the part's entry; partial or trial runs leave it alone.

The scheduled job marks its runs with `LLMWIKI_SCHEDULED_RUN=1`, exported by the wrapper. Marked runs stamp `outcomes.scheduled`; `install-automation` stores the schedule's interval and grace there, and the browser computes "overdue" at view time, so a job that never runs at all still shows. A vault whose installed schedule predates the marker gets a "setup outdated" entry.

Home gets one red banner, rendered by JS at the top of the dashboard from `outcomes` plus the existing `ops.last_lint_error`; the old lint note inside the Knowledge table is removed.

Outside programs: the wrapper loads the user's login profile at run time and prepends the folders of the programs the vault's backend needs, recorded at install. Each synthesizer can explain why it is unavailable, and that reason feeds the pipeline error line, the banner and doctor. The Claude pin keeps the launcher symlink (`Path.absolute()`, already in the working tree).

Systems touched: `state_store.py`, new `run_outcomes.py`, `pipeline.py`, `cli.py` (`cmd_sync`, `cmd_synthesize`, `cmd_build`, `install-automation`), `convert.py` (read-back only), `automation_install.py`, `automation_plan.py` / `automation_status.py`, `synth/{base,claude_cli,cursor_cli,ollama}.py`, `doctor/checks.py`, `doctor/heal_kb.json`, `raw_docs_site.py`, `render/js.py`, `render/css.py`, docs, CHANGELOG.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 State — `outcomes` section (`llmwiki/state_store.py`)

`default_state()` gains `"outcomes": {}`; `_ensure_shape` copies it when it is a dict (today it keeps only `queue/sync/synth/quarantine/ops/meta`, so an unregistered section is silently dropped on every write) and drops malformed members.

| Key | Shape | Written by |
|---|---|---|
| `outcomes.parts.<part>` — `part` ∈ `sync`, `synth`, `build`, `run` | `{scope: "entire"\|"partial", summary: str, detail: str, at: ISO-UTC, log_path: str, done: int\|null, total: int\|null, items: [str]}` | `run_outcomes.record_failure`; removed by `record_clean` |
| `outcomes.scheduled` | `{interval_s: int, grace_s: int, installed_at: ISO-UTC, marker: 1, last_run_at: ISO-UTC\|null, exit_code: int\|null, log_path: str}` | `install-automation` (config fields), marked runs (`last_run_at`, `exit_code`) |
| `outcomes.setup_outdated` | `{at, detail}` | any `all`/`sync` run that finds an installed schedule without the marker |

- Members that are not dicts, or parts without `scope`/`summary`, are dropped by `_ensure_shape`.
- `detail` is capped at 8 KB on write (the whole state is inlined into `llmwiki-state.js`). The browser shows its first 10 lines, then `…`.
- Lint stays in `ops.last_lint_*`; the banner reads it, nothing is duplicated.

### 2.2 Recording API — `llmwiki/run_outcomes.py` (new)

| Function | Responsibility |
|---|---|
| `record_failure(part, *, scope, summary, detail, log_path, done=None, total=None, items=(), state_file=None, site_dir=None, when=None)` | Upsert `outcomes.parts[part]` via `update_state` (its flock makes the read-modify-write atomic; `cmd_synthesize` holds no `pipeline_lock`, last writer wins), then `copy_state_sidecar_to_site`. |
| `record_clean(part, *, state_file=None, site_dir=None)` | Delete `outcomes.parts[part]`; copy sidecar. No-op write when absent. |
| `stamp_scheduled_run(*, exit_code, log_path, when=None, state_file=None, site_dir=None)` | Set `last_run_at` and `exit_code` together. Called once, at the end of a marked run (a run killed earlier leaves the old stamp and becomes overdue — spec 2.5/2.6). |
| `configure_schedule(*, interval_s, grace_s=7200, installed_at, log_path, state_file)` / `clear_schedule(state_file)` | Written by `install-automation`; cleared when the job is removed or set to none, so "no job → no entry" holds. |
| `is_scheduled_run() -> bool` | `os.environ.get("LLMWIKI_SCHEDULED_RUN") == "1"`. |
| `sync_failure_from_state(state, *, run_started_at) -> SyncOutcome` | From this run's `sync.counters` (`errored` per adapter; per run because `save_sync_meta` replaces them) and `quarantine.entries` with `last_seen >= run_started_at`: `k of m session sources failed (names)`, first error lines. |

Summary strings are stable, plain English, built only here: `did not run: <reason>`, `failed`, `k of m sources failed`, `k of m session sources failed (<names>)`, `stopped at the AI provider's usage limit after s of n sources`, `interrupted after s of n sources`, `run failed (exit <rc>)`.

### 2.3 Pipeline (`llmwiki/pipeline.py` `run_pipeline`)

- `try/finally` from right after vault resolution (line ~293), **around** the `with pipeline_lock(...)` — so a lock timeout, `_load_sessions_config` or `resolve_backend` exception is recorded too. Failures before vault resolution have no vault to write to; the overdue entry covers them.
- Each stage records right after it finishes, before any `--fail-fast` return:

| Stage | Entire failure | Partial failure | Clean |
|---|---|---|---|
| Sync | `convert_all` rc ≠ 0 (adapter selection / no stores) — counters are stale then, not read | any adapter `errored > 0` (rc stays 0: `fail_on_errors` is off) | neither |
| Synth (+harvest) | backend unavailable (`did not run: <unavailable_reason>`); `run_harvest` rc ≠ 0 | `summary["errors"]`; `usage_limit` (75); `interrupted` (130) | none of these |
| Build | rc ≠ 0 or exception | — | rc 0 |
| Lint | — (already recorded by `record_lint_ops`) | — | — |

- `run` entry in `finally`: exception (traceback's last line as detail), graph rc ≠ 0 (summary names the graph step), lint rc 2 **without** `record_lint_ops` having run (missing wiki / bad settings / unknown rule), or any other non-zero overall rc not explained by a recorded part or the lint policy trip. Overall rc 0 clears `run`.
- `--no-sync` / `--no-synth` leave those parts untouched; `all --out <non-default>` does not touch `build`.
- Marked runs call `stamp_scheduled_run` in the same `finally`. Exit codes are unchanged.

### 2.4 Standalone commands (`llmwiki/cli.py`)

| Command | Records when | Never records (partial / trial) |
|---|---|---|
| `cmd_sync` | default run; its auto-build records `build` (its rc is currently ignored — now recorded) | `--adapter`, `--since`, `--project`, `--recent`, `--status`, dry runs |
| `cmd_synthesize` | default run (sources + harvest) | `--path`, `--sessions-only`, `--docs-only`, `--sources-only`, `--candidates-only`, `--estimate`, `--check` |
| `cmd_build` | default `--out` | non-default `--out` |

A scheduled `sync` job (ingest plan) goes through `cmd_sync`, so it also calls `stamp_scheduled_run`.

### 2.5 Schedule marker, overdue, outdated setup

- `render_wrapper_script` (`llmwiki/automation_install.py`) adds `export LLMWIKI_SCHEDULED_RUN=1`. Chosen over a `--scheduled` flag: `plan_command` output stays stable, an older binary ignores the variable instead of failing argparse, and doctor detects it with a line match. The Windows task runs the same bash wrapper; launchd runs it via `/bin/bash`.
- `install-automation` calls `configure_schedule(interval_s=cron_interval(parse_cron(schedule)), …)`. `cron_interval` is the largest gap rounded up to whole days (daily → 1 day); the banner says "expected by <last_run_at + interval + grace>" — a due-by time, not the exact next firing (documented).
- Browser: overdue when `now − (last_run_at or installed_at) > interval_s + grace_s`. Evaluated when Home renders and re-evaluated once a minute (`setInterval`, clock comparison only — no new reads), so a Home tab left open turns red when the deadline passes without a refresh.
- Outdated setup: `all` / `sync` find `automation-status.json` for this vault while `outcomes.scheduled.marker` is absent → `outcomes.setup_outdated` → banner entry "Schedule — setup outdated: re-run `llmwiki install-automation`". Cleared by `configure_schedule`. Doctor reports the same.

### 2.6 Outside programs

- **Wrapper environment**, in order, before `set -euo pipefail`:
  1. Load the login profile non-interactively: source `~/.profile` (or `~/.bash_profile`) with stdin from `/dev/null`, errors ignored, output into the log.
  2. Prepend recorded program folders: at install, `shutil.which` for the binaries the vault's backend needs (`claude`; `agent` / `cursor-agent`), plus the folder of the interpreter. Each folder is deduplicated, must exist, must be absolute, and is `shlex.quote`d: `export PATH=<dirs>:"$PATH"`. Never the whole install-time `PATH` (it would freeze venvs, worktrees and IDE temp folders; empty or relative entries would resolve against the working directory).
  3. The recorded folders also go into `automation-status.json` (`program_dirs`) for doctor.
- **`unavailable_reason() -> str`** on `BaseSynthesizer` (default `"not available"`), overridden:
  - claude: pinned file missing (`<path> does not exist — point synthesis.claude.path at the claude launcher or remove it`), or not on `PATH`.
  - cursor_cli: `agent` / `cursor-agent` not on `PATH`.
  - ollama: `server <url> did not answer — start it (ollama serve) or change synthesis.backend`.
- CLI error line keeps its stable prefix and appends the reason: `error: backend <name> is not available: <reason>`. The `synth.backend_unavailable` patterns in `heal_kb.json` keep matching; the doctor message uses the same reason.
- **Doctor area L** (`llmwiki/doctor/checks.py`, beside the wrapper-is-gone check): `automation.interpreter_missing` (the wrapper's interpreter no longer exists); `automation.program_dir_missing` (a recorded folder disappeared); `automation.setup_outdated` (wrapper lacks the `LLMWIKI_SCHEDULED_RUN` line). Each gets a `heal_kb.json` row; the repair is re-running `install-automation`.
- Claude pin (`_maybe_pin_claude_path`): `Path.absolute()` — keeps the launcher symlink (done; regression test exists).

### 2.7 Home banner

- `render_dashboard_body` (`llmwiki/raw_docs_site.py`) adds an empty `<div id="llmwiki-problems" role="alert" hidden>` as the first child of `.queue-widget`, above the Automation panel.
- `render/js.py`: `renderProblemsBanner(snapshot)` — called from `renderQueueTrace` — builds entries in a fixed order (Schedule, Sync, Synth, Build, Run, Lint). Each entry: `<Part> — <summary>`, time, detail (first 10 lines + `…`), log path. Built with `textContent` only (detail is arbitrary error text). Hidden when empty. A malformed `outcomes` goes to `window.__llmwikiReportError`.
- Lint entry uses today's condition (`/^\s*\[error\]/m` on `ops.last_lint_error`) and the same note; the `state-lint-banner` block inside the Knowledge table is removed in the same change. "Linter output" stays.
- CSS reuses `.error-banner` danger tokens; light and dark checked.

### 2.8 Docs and catalog

`docs/reference/ui.md` (Home banner replaces the lint note), `docs/reference/cli.md` (install-automation wrapper environment; error line), `docs/configuration-reference.md` (`LLMWIKI_SCHEDULED_RUN`), `docs/reference/state-persistence.md` (`outcomes`), `docs/UPGRADING.md` (re-run `install-automation` once; the banner says so until then), CHANGELOG (#275's unreleased entry already rewritten for the pin; new *Added* entry for the banner), `heal_kb.json` rows.

---

## 3. Impact and Risk Analysis

- **System dependencies:** state shape (all writers go through `_ensure_shape`); the Home JS widget; the installer's wrapper; doctor area L; every synthesizer.
- **Risks & mitigations:**
  - *Login profile hangs or misbehaves* → stdin is `/dev/null`, non-interactive, errors ignored, sourced before `set -e`; recorded folders still apply when the profile adds nothing.
  - *Upgrade gap* → old wrappers lack the marker; the outdated-setup entry and doctor say "re-run install-automation" instead of a silent missing check.
  - *Paths published with the site* → `log_path` and `detail` can hold home paths and ship in `site/llmwiki-state.js`, as `ops.last_lint_error` already does; documented in `ui.md` / `state-persistence.md`.
  - *Sidecar size* → `detail` capped at 8 KB.
  - *Concurrent writers* (manual synth during a scheduled run) → per-part read-modify-write under `update_state`'s flock; last writer wins, which is the latest outcome.
  - *False "partial" from stale data* → sync counters are read only after a successful `convert_all`; quarantine entries are filtered by this run's start time.
  - *Approximate due-by time* (`cron_interval` rounds up to days) → shown as "expected by", documented.

---

## 4. Testing Strategy

- **Unit:** `run_outcomes` record/clear/stamp/configure; `_ensure_shape` keeps `outcomes` and drops malformed members; `sync_failure_from_state` with per-run counters and old quarantine entries; `unavailable_reason` per backend; wrapper text (marker line, profile block, quoted prepend, no full `PATH`); `_maybe_pin_claude_path` keeps the symlink (exists).
- **Pipeline acceptance** (extend `tests/test_234_pipeline_acceptance.py`, `tests/test_181_synth_clean_stop.py`): backend unavailable → entire synth; 1 of 7 sources failed → partial; usage limit → partial with counts; adapter errors → partial sync; build raises → entire build plus a `run` entry; lock timeout → `run` entry; clean run clears; `--fail-fast` still records; `--no-synth` leaves synth untouched; lint-policy-only rc 2 → no `run` entry.
- **Standalone:** a default synth clears; `--path`/`--estimate`/`--check`/`--sources-only` do not; sync auto-build failure is recorded.
- **Schedule:** a marked run stamps `last_run_at`/`exit_code`; an unmarked one does not; an install without the marker → `setup_outdated`; uninstall clears `scheduled`.
- **Doctor:** each new area-L finding; `synth.backend_unavailable` carries the reason.
- **Home:** extend `tests/test_state_widget.py` (banner mount first in `.queue-widget`, old lint note gone); one Playwright test under `tests/e2e/` on a built `$TMP_VAULT/site` — banner entries for synth + lint, refresh after a new sidecar shows a new entry without a rebuild, overdue entry from an old stamp, an open page turning overdue on the minute re-check with a fake clock, empty state hides the banner, light and dark.
- Each new rule's test is proven red with the rule removed.
