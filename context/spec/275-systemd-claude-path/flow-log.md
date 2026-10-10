# Flow log — 275-systemd-claude-path (#275)

## fetch-bug
- Source: GitHub Issue [#275](https://github.com/AlexanderMakarov/llm-wiki/issues/275) — systemd catch-up can miss user PATH and skip Claude synthesis; labels `bug`, `self-heal`; state OPEN; no comments.
- Symptom: Persistent Maintain timer catch-up runs with minimal systemd user-manager PATH; `shutil.which("claude")` fails though `~/.local/bin/claude` exists; sync+build OK; synth skipped; service exit 1.

## resume-detection
- Issue open; no open PR for #275. SPEC_NAME: `275-systemd-claude-path` (fix-as-spec orphan). Related specs 010 / 198 do not claim PATH/backend-binary catch-up behavior.

## workspace
- Branch `fix/275-systemd-claude-path`, worktree `.claude/worktrees/fix-275-systemd-claude-path` from `origin/main` (`65b2862`).
- TMP_VAULT: worktree `.worktree-vault`; worktree `config.json` vault-only.

## diagnose
- Root cause: `render_systemd_service` sets no Environment/PATH; install writes `synthesis.backend` only; unset path → `resolve_claude_path` → `shutil.which` under minimal PATH fails (`claude_path.py`, `automation_install.py`, `cli.py` install path).
- Proposed fix: pin absolute `synthesis.claude.path` at install when backend is claude and no explicit path already set; tests with PATH=/usr/bin:/bin + fake ~/.local/bin/claude.

## classify
- Verdict: orphan gap — no functional-spec to amend (010/198 do not require PATH pinning). Conformance to acceptance criteria in the issue; skip amend-spec.
- Next: fix

## fix
- `llmwiki/cli.py`: `_maybe_pin_claude_path` + extend `_write_synth_backend`; call write from both interactive and `--yes` install paths.
- `tests/test_automation_install.py`: pin / minimal-PATH / no-overwrite nested+flat / warn-when-missing.
- Docs: `CHANGELOG.md`, `docs/reference/cli.md`, `docs/configuration.md`, `docs/configuration-reference.md`, `docs/UPGRADING.md`.


## verify-criteria
- TMP_VAULT: `--synth-backend claude` pins absolute `synthesis.claude.path`; survives `PATH=/usr/bin:/bin`; explicit path not overwritten.
- Safe smoke: `which` None under minimal PATH; `resolve_claude_path(~/.local/bin/claude)` OK. Operator authorized agent to run safe check and proceed.
- Next: local-review

## amend-spec
- Skipped (orphan; no functional-spec to amend).


## local-review
- Verdict: Approve; Blockers 0; Nits 1 (`.fake-local-bin` scratch — keep N1; deleted before commit). review.md session-only, not staged.
- Static gate: ruff + full pytest green.
- Issue link keyword for PR: `Closes #275` (all issue acceptance criteria delivered).

## commit-push
- Staging product files + flow-log; excluding review.md, config.json, .worktree-vault/, .fake-local-bin.
- Next: remote-gates (stop appending tracked flow-log after PR open).

