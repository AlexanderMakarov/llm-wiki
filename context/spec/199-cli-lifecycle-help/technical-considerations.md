# Technical Specification: CLI help as a lifecycle map

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** Aleksandr Makarov

---

## 1. High-Level Technical Approach

Stay in the existing CLI package. Use stdlib `argparse` as it exists on Python 3.12 — no formatter subclass, no extra helper modules, no new runtime dependencies, no vault schema change.

Three mechanical pieces:

1. **Help surface** — grouped command map and canonical-loop reminder via the root parser’s `description` / `epilog` and `argparse.RawDescriptionHelpFormatter`. Long per-command text via each subparser’s `description`. Strip issue numbers from flag `help=` strings.
2. **Command set** — unregister `synthesize` and `consolidate-topics`. Point docs that still invoked them at `synth` (with `--sources-only` where that was the old alias default). No packaged slash command invokes the removed names.
3. **Migration wrapper** — one top-level `migrate` with nested names (`add_subparsers` on that parser). List when no name is given or `--list` is passed; run only when a name is given. Delete the six `migrate-*` subparsers. Existing handler functions and `scripts/migrate_*.py` stay; only the invocation shape changes.

Tests that existed only to cover a **removed** command or retirement stub are deleted. Do not replace them with assertions that the old name is “unknown.” Keep tests that still exercise a live feature (including migrations and `synth`), and point their argv at the new shape.

---

## 2. Proposed Solution & Implementation Plan

### Architecture

All parser wiring stays in `llmwiki/cli.py` (`build_parser`, `cmd_*`). Do not add `llmwiki/cli_help.py` or `llmwiki/cli_migrate.py`.

A small ordered sequence of migration records in `cli.py` (name, purpose, when-to-run sentence, extra `add_argument` calls, handler) is enough to register nested subparsers and to print the catalog. A comment on that sequence: add a new migration here, never as a new top-level command.

### Help (argparse 3.12 only)

Python 3.12 allows only one `add_subparsers` on a given parser, so the six lifecycle labels cannot be native argparse groups. The labelled list is ordinary help text.

| Need | Argparse feature |
|---|---|
| Keep line breaks in the group map and loop | `formatter_class=argparse.RawDescriptionHelpFormatter` on the root parser, and on each subparser whose `description` is more than one paragraph |
| Grouped one-liners | Root `description=` (headings from the functional spec, each live command once) |
| Canonical loop + “synth does not rebuild the site” | Root `epilog=` |
| Usage without `{init,sync,…}` | `add_subparsers(..., metavar="COMMAND")` |
| No second flat command list | Omit `help=` on top-level `add_parser` (`help is None` → argparse does not list that name under positional arguments). Do **not** pass `help=argparse.SUPPRESS` on subparsers (argparse prints `==SUPPRESS==`) |
| Long per-command help | That subparser’s `description=`; flags remain `add_argument(..., help=...)` without issue numbers or G-codes; define “adapter” in the same help string if the word is used |

`textwrap.dedent` (stdlib) is fine for those description strings.

A test must check that every key in the root subparsers `choices` appears in the root `description` exactly once, so the map cannot drift from `add_parser` names.

### Removed commands

- Drop subparsers `synthesize` and `consolidate-topics`.
- Delete `cmd_consolidate_topics` and the `deprecated_synthesize` branch. `cmd_synthesize` remains wired only to `synth`.
- Packaged `/wiki-synthesize` is retired, not kept as a deprecated alias (amended 2026-09-06, see Change Log): the command file is dropped from the agent kit and `install-agent-kit` ships one fewer command. `/wiki-synth` is the only synthesize entry point; what the old alias did is reached with `synth --sources-only`. Docs mention `/wiki-synthesize` only as a removed name.

### `migrate` contract

Stable nested names (no `migrate-` prefix):

| Name | Today’s command |
|---|---|
| `state` | `migrate-state` |
| `raw-redaction` | `migrate-raw-redaction` |
| `tools-used` | `migrate-tools-used` |
| `page-kinds` | `migrate-page-kinds` |
| `topic-kinds` | `migrate-topic-kinds` |
| `broken-provenance` | `migrate-broken-provenance` |

- `llmwiki migrate` and `llmwiki migrate --list` print the same catalog (name, purpose, when); exit 0; no vault writes. Implemented in the migrate handler when `migration` is unset and/or `--list` is set — not as a separate “doctor” probe of the vault.
- `llmwiki migrate --list <name>` is an error (list and apply are exclusive).
- `llmwiki migrate <name> [flags]` calls the existing handler with the same flags as today (`--vault`, `--dry-run`, …).
- No `--all`.
- Nested `add_subparsers(dest="migration", metavar="NAME", required=False)` so `migrate --help` lists names via argparse and `migrate <name> --help` shows that migration’s flags.
- Top-level `migrate-state` (and the other five) are not registered.

### Docs / schema

Same PR, current-tense only:

- `docs/reference/cli.md` — one `## \`migrate\`` section; grouped intro matching `--help`; live headings only. `test_reference_coverage.py` then matches the live tree.
- `docs/UPGRADING.md`, `CHANGELOG.md` under Unreleased, `docs/cheatsheet.md`, `docs/reference/slash-commands.md`.
- Tutorials and similar walkthroughs that still instruct `synthesize` or `consolidate-topics` (including `docs/tutorials/08-synthesize-with-ollama.md` where it still points at the old command).
- `AGENTS.md` and `CLAUDE.md`: new migrations register under `migrate` in `cli.py`, not as new top-level commands. The same sentence in the `migrate` section of `docs/reference/cli.md`.

### Tests for removed features — delete them

Do not keep or invert tests whose subject is a command or retirement behaviour we are deleting. There is no product value in asserting argparse’s generic “invalid choice” / unknown-command path for old names.

**Delete** (examples; grep for the old names and drop the cases, not the whole file when it still tests a live feature):

- E2E / acceptance that `consolidate-topics` still resolves, exits 2, or prints a retirement message (`tests/e2e/test_cli_smoke.py`, `tests/test_147_acceptance.py` and similar).
- Tests of the `synthesize` deprecated-alias path (`deprecated_synthesize`, default sources-only because the name was `synthesize`, warning text). Prefer covering that behaviour on `synth --sources-only` only if it is still a live flag; do not keep a test because the alias used to exist.
- `ALL_SUBCOMMANDS` / parser-choice lists: remove `synthesize`, `consolidate-topics`, and the six `migrate-*` names; add `migrate` (and `synth` if the tuple was missing it). Do not add the old names as negative parametrize cases.
- CLI reference / coverage expectations that a live `## \`consolidate-topics\`` or `## \`synthesize\`` heading must exist. Historical changelog lines may still mention the names; do not test those.

**Keep and retarget argv** when the *feature* remains:

- Migration dry-run / report tests: call `migrate <name> …` (or the handler function) instead of `migrate-…`.
- `synth` pipeline, `--estimate`, `--candidates-only`, `--sources-only` as flags on `synth`.
- Slash `/wiki-synth` behaviour. There is no `/wiki-synthesize` alias behaviour to cover — the packaged command set simply no longer ships that file, and the packaged-command count guards that.

New tests that *are* in scope: grouped headings and epilog in root `format_help()`; no `#\d+` in top-level help; every live subparser name appears in the description; `migrate` / `migrate --list` print the catalog without writing; `migrate <name> --dry-run` still reaches the existing handler.

---

## 3. Impact and Risk Analysis

- **System dependencies:** argparse tree is the contract for `test_reference_coverage`, slash/CLI parity, and e2e smoke. Migration *scripts* under `scripts/` and package `migrate_*` modules are unchanged.
- **Scripts using old CLI names:** UPGRADING + CHANGELOG mapping only. No compatibility aliases (per functional spec). No tests whose job is to document that breakage.
- **Stale group text vs registered parsers:** the description-vs-`choices` test.
- **Deleting retirement tests:** `test_147_acceptance` and related files must be edited so they still guard live #147 behaviour (known-names during synth, agent-kit wording) without requiring a `consolidate-topics` subcommand.

---

## 4. Testing Strategy

- Parser unit tests for `migrate`, `migrate --list`, `migrate raw-redaction --dry-run --vault …`.
- Help: `build_parser().format_help()` and subparser `format_help()` (no private formatter API).
- Doc parity: existing coverage tests green after heading rewrite.
- Regression: remaining migrate / synth tests use the new argv; removed-feature tests are gone, not rewritten as unknown-command cases.

---

## Change Log

### 2026-09-06 — `/wiki-synthesize` slash alias retired ([#214](https://github.com/AlexanderMakarov/llm-wiki/issues/214))

- **What changed:** this spec's §2 "Removed commands" decided to keep packaged `/wiki-synthesize` as a deprecated slash alias running `python3 -m llmwiki synth --sources-only`. That decision is reversed. The packaged command file is deleted, `install-agent-kit` ships 12 commands, and `/wiki-synth` is the only synthesize entry point; the old sources-only behaviour is reached with `--sources-only` on `synth`.
- **Why:** work on #214 trimmed the vault command surface, and the repo owner directed retiring the alias rather than carrying a second name for the same job.
- **Scope of the amendment:** §2 "Removed commands", the §1 command-set summary, and the §2 "Keep and retarget argv" testing note. The functional spec is unchanged: its R3 acceptance criteria concern the CLI `synthesize` subcommand, whose removal stands exactly as specified — only the packaged slash alias decision, which lived here, was reversed.
- **`tasks.md`:** Slice 2's checked items are left as written. They record accurately what shipped for #112; the alias they created was removed later under #214.
