# Flow log — #214 remove /wiki-export-marp (and /wiki-synthesize)

Fix-as-spec directory (#164). Orphan bug: no functional-spec of its own.
Owning spec for the divergence half: `context/spec/199-cli-lifecycle-help/`.

## fetch-bug

Issue [#214](https://github.com/AlexanderMakarov/llm-wiki/issues/214) — `install-agent-kit` ships `/wiki-export-marp`, which runs `python3 -m llmwiki export-marp`, a subcommand removed in v1.2.0. Labels: `bug`, `important`. State: OPEN. Owner comment ties it to #215 (same v1.2.0 removal, documentation half).

## resume-detection

No prior branch, PR, or spec directory. Fresh start. `SPEC_NAME` = `214-remove-marp-slash`.

## workspace

- Branch: `fix/214-remove-marp-slash` off `origin/main` @ `63a1868`
- Worktree: `.claude/worktrees/fix-214-remove-marp-slash`
- Throwaway vault: `$WT/.worktree-vault`, worktree-local `config.json` points at it

## diagnose

Reproduced. `install-agent-kit --dest <tmp>` installs 14 commands including `wiki-export-marp.md`, whose body (line 12) runs `python3 -m llmwiki export-marp --topic "$ARGUMENTS"`. The CLI rejects it: `invalid choice: 'export-marp'`.

Root cause: v1.2.0 removed the `export-marp` subcommand but left three residues — the packaged slash file, `write_marp()` in `llmwiki/exporters.py:491` (confirmed zero callers; not reached by `export_all`), and a live entry in `docs/reference/slash-commands.md`. The parity guardrail that should have caught it was silenced by a `LEGACY_SLASH_FILES` allowlist whose own comment records the defect.

No dead test coverage for `write_marp()` exists — no test imports it.

## classify

**Divergence** (widened from conformance by owner decision).

- The marp half alone is conformance: nothing decided to keep it.
- The owner also directed retiring `/wiki-synthesize` to reduce the vault command surface. Spec 199 explicitly decided to keep it (`technical-considerations.md:52`; `tasks.md:23` checked off). Reversing that is a divergence, so spec 199 gets amended in the `amend-spec` stage and the PR carries a §9 divergence comment.

## decisions

Taken by the owner via AskUserQuestion:

1. **Removal scope** — marp **and** `/wiki-synthesize`. Vault commands 14 → 12.
2. **Doc shape** — `docs/reference/slash-commands.md` becomes vault-only: one flat list, no group table, one honest count. Governance (`/maintainer`, `/release`, `/triage-issue`) and AWOS delivery (`/fix-bug`, `/implement-feature`) move to `docs/maintainers/`.
3. **Test scope** — the docs-parity test asserts the doc set equals the `install-agent-kit` set in both directions plus the count. AWOS and governance commands are development-only and are **never** asserted.

Next stage: `fix`.

## fix

Delegated to `general-purpose`. Deleted `wiki-export-marp.md` and `wiki-synthesize.md` from the kit (12 commands ship), removed `write_marp()` (83 lines) from `llmwiki/exporters.py`, deleted `LEGACY_SLASH_FILES` and `SLASH_CLI_ALIASES` with their dead branch from `tests/test_slash_cli_parity.py`, dropped the alias from `tests/test_palette_indexes.py`, split `tests/test_reference_coverage.py` to follow the doc split, created `docs/maintainers/slash-commands.md`, and updated `CLAUDE.md`, `docs/UPGRADING.md`, `docs/maintainers/README.md`, `wiki-synth.md`.

Verified independently: `install-agent-kit` installs 12 commands, no marp or synthesize; zero `write_marp` / `LEGACY_SLASH_FILES` / `export-marp` residue in `llmwiki/`, `tests/`, `docs/reference/`.

### Gap found in the delivered fix

`tests/test_reference_coverage.py` asserts the slash surface in ONE direction only (`shipped - documented`). The reverse (`documented - shipped`) is unasserted, so the reference doc may still advertise a command that `install-agent-kit` does not ship — which is precisely how #214 survived. Proved empirically: re-adding a `### /wiki-export-marp` section to the reference left all 17 tests passing. The CLI half of the same file checks both directions (lines 55 and 62); only the slash half is asymmetric. Closing this is the `regression-test` stage's deliverable.

### Rework

The doc restructure of `docs/reference/slash-commands.md` was lost when the orchestrator ran `git checkout` on that file to undo a temporary probe edit. Redone as a separate stage — see `rebase` below. All other fix output survived.

## rebase

Branch was 8 commits behind after PR #217 (`#209` release skill) and PR #216 (`#186`) merged on 2026-09-05. Rebased onto `origin/main` @ `b191730`.

One conflict, in `docs/maintainers/README.md`: upstream rewrote the trailing "source of each command" sentence to add `.cursor/commands/`, while this branch rewrote it to point at the new `slash-commands.md`. Resolved by merging both intents — neither side lost.

PR #217 also rewrote `docs/reference/slash-commands.md` (the `/release` section) and the maintainer README's Slash-commands list. Because the lost restructure meant this branch carried that file unchanged, git took upstream's copy cleanly, so the restructure is being redone against #217's current content rather than the stale text. The `/release` section already copied into `docs/maintainers/slash-commands.md` predates #217 and is being reconciled in the same pass.

Next stage: `regression-test` (testing-expert), then `verify-criteria`.
