# Tasks: Automation never fails silently (#374)

- [ ] **Slice 1: One red banner at the top of Home, holding the lint note**
  - [ ] `raw_docs_site.render_dashboard_body`: add the empty `#llmwiki-problems` mount (`role="alert"`, `hidden`) as the first child of `.queue-widget`, above the Automation panel. **[Agent: python-development:python-pro]**
  - [ ] `render/js.py`: add `renderProblemsBanner(snapshot)` (called from `renderQueueTrace`) that builds entries with `textContent` only, in the order Schedule, Sync, Synth, Build, Run, Lint; first entry type is Lint, using today's `[error]` condition and 10-line cap; hide when empty; report a malformed snapshot via `window.__llmwikiReportError`. Remove the `state-lint-banner` block from the Knowledge table. CSS reuses `.error-banner` tokens (light + dark). **[Agent: general-purpose]**
  - [ ] Update `tests/test_state_widget.py` (mount is first in `.queue-widget`; old lint note gone; banner code present). **[Agent: python-development:python-pro]**
  - [ ] Verify: build `$TMP_VAULT` with a recorded lint error, open `site/index.html` with Playwright, confirm one red banner at the top with a "Lint" entry and no note under the tables, check light and dark, then delete screenshots and scripts. **[Agent: general-purpose]**

- [ ] **Slice 2: A failed synth in `all` shows as a "Synth" entry**
  - [ ] `state_store`: register `outcomes` in `default_state()` and `_ensure_shape` (dict only; drop malformed parts). **[Agent: python-development:python-pro]**
  - [ ] New `llmwiki/run_outcomes.py`: `record_failure`, `record_clean` (sidecar copy after each write, `detail` capped at 8 KB), summary-string builders. **[Agent: python-development:python-pro]**
  - [ ] Synthesizers: `unavailable_reason()` on `BaseSynthesizer`, overridden by claude / cursor_cli / ollama; the CLI line becomes `error: backend <name> is not available: <reason>` (stable prefix); update `heal_kb.json` and doctor's `synth.backend_unavailable` message. **[Agent: python-development:python-pro]**
  - [ ] `pipeline.run_pipeline`: record synth right after it finishes — unavailable / harvest rc ≠ 0 → entire; source errors / usage limit / interrupted → partial with counts; clean → clear; `--no-synth` leaves it. **[Agent: python-development:python-pro]**
  - [ ] Banner renders Synth entries ("did not run: …", "k of n sources failed", "stopped at the AI provider's usage limit after s of n sources") with time, detail and log path. **[Agent: general-purpose]**
  - [ ] Verify: pytest for unavailable / partial / usage-limit / clean against `$TMP_VAULT`; run `python3 -m llmwiki all --vault $TMP_VAULT` with an unreachable backend, refresh the built Home with Playwright without rebuilding and see the "Synth — did not run" entry; delete artifacts. **[Agent: general-purpose]**

- [ ] **Slice 3: Sync, Build and whole-run failures in `all`**
  - [ ] `run_outcomes.sync_failure_from_state` (per-run `errored` counters read only after rc 0; quarantine entries with `last_seen >= run start`). **[Agent: python-development:python-pro]**
  - [ ] `pipeline.run_pipeline`: `try/finally` from vault resolution around `pipeline_lock`; record sync (rc ≠ 0 → entire; errored adapters → partial) and build (rc ≠ 0 or exception → entire; non-default `--out` leaves it); `run` entry for exceptions, lock timeout, graph rc ≠ 0, lint rc 2 without a lint record, unexplained non-zero rc; rc 0 clears `run`; every `--fail-fast` return records first. **[Agent: python-development:python-pro]**
  - [ ] Verify: pytest for adapter errors → partial sync, build raising → Build + Run entries, lock timeout → Run, lint-policy-only rc 2 → no Run entry, clean run clears everything; Playwright on a built `$TMP_VAULT` shows Sync and Build entries; delete artifacts. **[Agent: general-purpose]**

- [ ] **Slice 4: Manual full runs record and clear; partial runs do not**
  - [ ] `cmd_synthesize`: record on a default run; never with `--path`, `--sessions-only`, `--docs-only`, `--sources-only`, `--candidates-only`, `--estimate`, `--check`. **[Agent: python-development:python-pro]**
  - [ ] `cmd_sync`: record on a default run (not `--adapter`, `--since`, `--project`, `--recent`, `--status`, dry runs); record its auto-build's rc as Build. `cmd_build`: record on the default `--out` only. **[Agent: python-development:python-pro]**
  - [ ] Verify: pytest — a Synth entry clears after a clean default `synth`, survives `--path` / `--estimate` / `--check` / `--sources-only`; sync auto-build failure records Build; delete artifacts. **[Agent: general-purpose]**

- [ ] **Slice 5: Missed scheduled runs and outdated setups are shown**
  - [ ] `run_outcomes`: `is_scheduled_run`, `stamp_scheduled_run` (at the end of the run, `last_run_at` + `exit_code` together), `configure_schedule`, `clear_schedule`, `setup_outdated` record/clear. **[Agent: python-development:python-pro]**
  - [ ] `run_pipeline` and `cmd_sync` stamp marked runs in their `finally`; both record `setup_outdated` when `automation-status.json` exists for the vault and the marker is missing. **[Agent: python-development:python-pro]**
  - [ ] `automation_install`: wrapper exports `LLMWIKI_SCHEDULED_RUN=1`; install calls `configure_schedule(interval_s=cron_interval(...), grace_s=7200, installed_at, log_path)`; removing the job or setting it to none calls `clear_schedule`. **[Agent: python-development:python-pro]**
  - [ ] Banner: "Schedule — overdue" when `now − (last_run_at or installed_at) > interval_s + grace_s`, with last run and "expected by"; re-evaluated every minute; "Schedule — setup outdated: re-run llmwiki install-automation". **[Agent: general-purpose]**
  - [ ] Verify: pytest for stamp/marker/configure/clear/outdated; Playwright on a built `$TMP_VAULT` with an old stamp shows overdue, a fresh one does not, and an open page turns overdue on the minute re-check with a fake clock; delete artifacts. **[Agent: general-purpose]**

- [ ] **Slice 6: The scheduled job finds every outside program, and doctor names a missing one**
  - [ ] `automation_install.render_wrapper_script`: before `set -euo pipefail`, source the login profile non-interactively (stdin `/dev/null`, errors ignored); then `export PATH=<recorded dirs>:"$PATH"` — `shutil.which` for the backend's binaries (`claude`; `agent` / `cursor-agent`) plus the interpreter's folder, absolute, existing, deduplicated, `shlex.quote`d; record them as `program_dirs` in `automation-status.json`. Keep the Claude pin's `Path.absolute()` (done). **[Agent: python-development:python-pro]**
  - [ ] Doctor area L: `automation.interpreter_missing`, `automation.program_dir_missing`, `automation.setup_outdated`, each with a `heal_kb.json` row (repair: re-run `install-automation`). **[Agent: python-development:python-pro]**
  - [ ] Verify: pytest for wrapper text (profile block, quoted prepend, never the whole install-time PATH), doctor findings, and the existing pin test; run `install-automation --yes --job maintain --synth-backend claude --no-activate --units-dir <scratch> --vault $TMP_VAULT` with a synthetic launcher layout and inspect the wrapper; delete artifacts. **[Agent: general-purpose]**

- [ ] **Slice 7: Docs and release notes**
  - [ ] `docs/reference/ui.md` (banner replaces the lint note; published sidecar may hold paths), `docs/reference/cli.md` (wrapper environment, error line), `docs/configuration-reference.md` (`LLMWIKI_SCHEDULED_RUN`), `docs/reference/state-persistence.md` (`outcomes`), `docs/UPGRADING.md` (re-run `install-automation` once), CHANGELOG *Added* entry under `[Unreleased]`. **[Agent: general-purpose]**
  - [ ] Verify: `ruff check llmwiki tests scripts`, full `python3 -m pytest tests/ -q`, docs CLI-coverage check green. **[Agent: general-purpose]**

- [ ] **Slice 8: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 374-no-silent-automation-failure` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
