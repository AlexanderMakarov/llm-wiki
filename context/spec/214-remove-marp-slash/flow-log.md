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

Delegated to `general-purpose`. Deleted `wiki-export-marp.md` and `wiki-synthesize.md` from the kit (12 commands ship), removed `write_marp()` (83 lines) from `llmwiki/exporters.py`, deleted `LEGACY_SLASH_FILES` and `SLASH_CLI_ALIASES` with their dead branch from `tests/test_slash_cli_parity.py`, dropped the alias from `tests/test_palette_indexes.py`, split `tests/test_reference_coverage.py` to follow the doc split, moved the contributor commands into the maintainer guide, and updated `CLAUDE.md`, `docs/UPGRADING.md`, `docs/maintainers/README.md`, `wiki-synth.md`.

Verified independently: `install-agent-kit` installs 12 commands, no marp or synthesize; zero `write_marp` / `LEGACY_SLASH_FILES` / `export-marp` residue in `llmwiki/`, `tests/`, `docs/reference/`.

### Gap found in the delivered fix

`tests/test_reference_coverage.py` asserts the slash surface in ONE direction only (`shipped - documented`). The reverse (`documented - shipped`) is unasserted, so the reference doc may still advertise a command that `install-agent-kit` does not ship — which is precisely how #214 survived. Proved empirically: re-adding a `### /wiki-export-marp` section to the reference left all 17 tests passing. The CLI half of the same file checks both directions (lines 55 and 62); only the slash half is asymmetric. Closing this is the `regression-test` stage's deliverable.

### Rework

The doc restructure of `docs/reference/slash-commands.md` was lost when the orchestrator ran `git checkout` on that file to undo a temporary probe edit. Redone as a separate stage — see `rebase` below. All other fix output survived.

## rebase

Branch was 8 commits behind after PR #217 (`#209` release skill) and PR #216 (`#186`) merged on 2026-09-05. Rebased onto `origin/main` @ `b191730`.

One conflict, in `docs/maintainers/README.md`: upstream rewrote the trailing "source of each command" sentence to add `.cursor/commands/`, while this branch rewrote it to point at the new `slash-commands.md`. Resolved by merging both intents — neither side lost.

PR #217 also rewrote `docs/reference/slash-commands.md` (the `/release` section) and the maintainer README's Slash-commands list. Because the lost restructure meant this branch carried that file unchanged, git took upstream's copy cleanly, so the restructure is being redone against #217's current content rather than the stale text. The `/release` write-up predates #217 and was reconciled in the same pass.

Next stage: `regression-test` (testing-expert), then `verify-criteria`.

## prune

**Why it is in this PR at all.** Deleting `wiki-export-marp.md` and `wiki-synthesize.md` from the packaged kit stops *new* installs from getting them — and does nothing at all for the machines that already have them. `install-agent-kit` only ever wrote files; it never removed one. So on every destination populated by an earlier install, `/wiki-export-marp` keeps appearing in the agent's command list and keeps failing, which is the exact user-visible symptom #214 was filed about. The retirement is inert without a prune. The owner weighed splitting the prune into a follow-up issue against shipping it here and chose to fold it into PR #218: a fix that does not reach existing installs is not a fix, and a second PR would leave the gap open for a release cycle.

**Two mechanisms, deliberately.** A prune needs to know what llmwiki put in the destination, and there are two disjoint populations:

1. `<dest>/.llmwiki-agent-kit.json` — an install manifest, new in this change. It records the version and a `path → sha256` of everything the run installed, so a *future* removal needs no code change: any manifest path the kit no longer ships is stale by construction. This is the durable mechanism.
2. `llmwiki.agent_kit.RETIRED_PATHS` — a packaged list of paths the kit has dropped, each mapped to the digests of every revision ever shipped there. The manifest is blind to installs that predate it, and every install on the planet predates it, so the retired list is the only thing that reaches today's actual residue. It is the transitional mechanism.

Both exist because neither alone covers the field: the manifest is right for the future and empty for the present; the retired list is right for the present and would grow forever if relied on.

**Digest gating and no backups — decided in response to review 2.** The first implementation matched on the *name* and copied each victim to `<name>.bak` before unlinking. Review 2 filed two blockers against it: a user's own hand-written file at a retired name was deleted despite the docstring, CLI help, `docs/reference/cli.md` and CHANGELOG all promising "a file this command never installed is never touched" (B2); and the `.bak` write was unconditional, so a prune could overwrite an older backup that was holding the user's real customisation (B1). The owner's ruling settled both at once: **don't create any backups — just remove if it is ours.**

So provenance moved from the name to the content. A path is eligible only while its bytes still hash to something llmwiki is known to have written there — a manifest digest recorded at install time, or one of the shipped revisions in `RETIRED_PATHS`. An unrecognised digest is not deleted and not backed up; it is left alone and surfaced in `report["kept"]` as *"retired, but modified — left in place"*. That single rule covers all three populations the review worried about: a user's unrelated file at the same name, a retired command someone customised, and a manifest path edited since install. And because the only bytes the prune can ever remove are bytes we ourselves wrote and that nobody has touched since, there is nothing worth backing up — the `.bak` write was deleted. (The *overwrite* backup in `run_install`, which saves a differing file before writing the kit version over it, predates this branch and is untouched.) The digests for the two retired paths were recovered from git history of the deleted files: 1 revision for `commands/wiki-export-marp.md`, 5 for `commands/wiki-synthesize.md`.

**Blast radius.** `--dest` is typically `~/.claude` — not a directory llmwiki owns, but a shared agent directory holding the user's own commands and skills alongside those of every other tool they use. That is why the guarantee had to be real rather than merely documented, why manifest entries are validated (absolute paths, `..` segments, anything outside `commands/`/`skills/`, and anything resolving outside `dest` are all ignored), why only files are unlinked and never directories, why an older list-shape manifest carrying no digests authorises no deletion at all, and why `--dry-run` reports the full prune without touching disk.

## doc-scope correction

The restructure first landed the contributor half as a new page under `docs/maintainers/`, justified by a parity test asserting it against `.claude/commands/`. The owner rejected that: *"If we need a piece of documentation just to implement a test for this then this is a wrong move. We need documentation to help people, tests are not a reason for new docs."* The maintainer README already had a `## Slash commands` section for exactly that audience, so the new page was pure duplication with a test bolted on to keep the duplicate honest.

Reverted: the page is gone, its content folded into that README section (what each of the five commands is for, which are hand-written governance versus AWOS-generated from `context/product/delivery-flow.md`, which agent surfaces carry them, and how the `/awos:*` layer differs), and the two parity tests that only policed the deleted page were dropped. The vault-side parity tests — both directions, the count, and the summary-table order for `docs/reference/slash-commands.md` — stay: they guard a promise made to users about what `install-agent-kit` puts on their machine, which is a reader-facing contract rather than a doc invented for a test.
