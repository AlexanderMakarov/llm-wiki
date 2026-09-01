# Flow log — 198-install-automation-activate (#198)

## fetch-bug — done

- Source: GitHub Issue [#198](https://github.com/AlexanderMakarov/llm-wiki/issues/198) — `install-automation` renders scheduler units but never activates them; site reports daily job that never runs.
- State: OPEN, labels `bug`, `important`. No comments. No linked PRs.
- Two defects in issue body: **A** installer render-only (this PR), **B** panel trusts plan not observed state (deferred to follow-up PR per issue suggestion).

## resume-detection — done

- Issue open; no merged fix. No prior `context/spec/198-*` directory.
- Owning spec `010-automation-profiles` is Completed but does not require OS scheduler activation — classification **divergence** (new behavior + status fields).
- `SPEC_NAME`: `198-install-automation-activate` (fix-as-spec).

## workspace — done

- Branch `fix/198-install-automation-activate`, worktree `.claude/worktrees/fix-198-install-automation-activate` from `origin/main` (`f118135`).
- Throwaway vault: `$WT/.worktree-vault` with worktree `config.json`.

## diagnose — done

- Root cause: `run_install()` (`automation_install.py:288–378`) writes units + `save_status()` only; no `systemctl`/`launchctl`/`schtasks`. CLI (`cli.py:1126–1131`) tells user to enable manually.
- Proposed fix: `activate_scheduler()` with `--activate`/`--no-activate`; copy units to platform location; read back state into `automation-status.json`.

## classify — done

- **Verdict: divergence** — spec 010 R5 requires files written, not activation; fix adds activation + honest status fields. Amend spec skipped (orphan fix-as-spec; no functional-spec to amend unless we document new AC later). Defect B (panel) out of scope for this PR.

## implement — done

- `activate_scheduler()` + `default_scheduler_units_dir()` in `automation_install.py`; `run_install(activate=True)` default; CLI `--activate`/`--no-activate`; tests with fake `systemctl` on PATH.
- Review fix B1: installed `.service`/plist re-rendered so `ExecStart` references `~/.config/systemd/user/llmwiki-maintain.sh`, not staging dir.
- E2E on this machine: timer enabled and active (waiting). Classification: **divergence**. Defect B deferred.

Next: commit-push → PR → CI.
