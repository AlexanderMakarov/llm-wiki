# Flow log — 206-automation-config-isolation (#206)

## fetch-bug — done

- Source: GitHub Issue [#206](https://github.com/AlexanderMakarov/llm-wiki/issues/206) — install-automation timer can ignore primary config lookback and dump full Cursor IDE history.
- State: OPEN, labels `bug`, `important`.
- Operator also cleaned live vault of lookback-violating `cursor-ide` sessions and disabled the broken user timer (out of band).

## resume-detection — done

- Issue open; no merged fix. Allocated fix-as-spec `206-automation-config-isolation`.
- Related completed specs: `177-sync-lookback` (#192), `010-automation-profiles` (#156), prior fix-as-spec `198-install-automation-activate`.

## workspace — done

- Branch `fix/206-automation-config-isolation`, worktree `.claude/worktrees/fix-206-automation-config-isolation` from `origin/main`.
- Throwaway vault: `$WT/.worktree-vault` with worktree-local `config.json` (not primary).

## diagnose — done

- Root cause: `cmd_install_automation` bakes `working_dir=REPO_ROOT` into the wrapper; scheduled `python3 -m llmwiki` then loads `config.json` from that same checkout (`config_schedule._USER_CONFIG`). Install from a linked worktree → empty worktree config → unlimited lookback on live vault.
- No `LLMWIKI_CONFIG` / config-path escape hatch (`LLMWIKI_ROOT` removed).
- Minimal fix: resolve git **main worktree** (or refuse linked worktree) for automation `working_dir` so timers always use the operator’s primary `config.json`.

## classify — done

- **Verdict: divergence** — lookback (#177) behaves correctly when config loads; defect is install-time root / worktree isolation, incomplete in #010/#198. Fix-as-spec `206-automation-config-isolation`; **no functional-spec to amend** (orphan). Document in CHANGELOG + install docs.

## implement — done

- Added `resolve_main_worktree(path)` in `llmwiki/automation_install.py`: returns `path` unchanged when it is not inside a git repo; returns the main worktree's path (first `worktree` line of `git worktree list --porcelain`, run from `path`) when `path` is a linked worktree; falls back to `path` with a stderr warning if git is missing or detection fails.
- `cmd_install_automation` (`llmwiki/cli.py`) now computes `working_dir = resolve_main_worktree(REPO_ROOT)` once, uses it for both the pre-write `_confirm_plan` command preview and the `run_install({"working_dir": ...})` call baked into the wrapper script, and prints a one-line notice when it differs from `REPO_ROOT`. No `LLMWIKI_ROOT` reintroduced.
- Tests: `tests/test_automation_install.py` — real `git init` / `git worktree add` fixtures cover non-git passthrough, main-worktree identity, and linked→main resolution; a monkeypatched `subprocess.run` covers the detection-failure fallback + warning; a monkeypatched `shutil.which` covers the missing-git case. Full suite (`pytest tests/ -q`) and `ruff check llmwiki tests scripts` both green.
- Docs: `docs/reference/cli.md` (`install-automation` section) and `CHANGELOG.md` under `## [Unreleased]` → `### Fixed`.

Next: commit-push → PR → CI.
