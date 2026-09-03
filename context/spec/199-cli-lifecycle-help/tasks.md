# Tasks: CLI help as a lifecycle map (#112)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Drive `python3 -m llmwiki` from this worktree. Mutating commands use `$TMP_VAULT` (`.worktree-vault`). Never write the operator's live vault.

Hired specialists: none for Python CLI — implementation tasks use **general-purpose**. QA slice uses **testing-expert**.

---

- [ ] **Slice 1: One `migrate` command lists and runs the six repairs**

  > End state: `llmwiki migrate` / `migrate --list` print the catalog and write nothing; `llmwiki migrate <name> --dry-run` reaches the existing handlers; top-level `migrate-*` names are gone; tests of those old subcommand names are deleted, not inverted.

  - [ ] In `llmwiki/cli.py` only: ordered migration records; nested `add_subparsers` under `migrate` (`state`, `raw-redaction`, `tools-used`, `page-kinds`, `topic-kinds`, `broken-provenance`); `--list`; list-when-unnamed; error if `--list` and a name together; same flags as today on each nested parser; delete the six top-level `migrate-*` subparsers; keep existing `cmd_migrate_*` handlers. Comment on the registry: add new migrations here, never as a new top-level command. **[Agent: general-purpose]**
  - [ ] Retarget live migration tests to `migrate <name> …` (or the handler). Delete tests whose only subject was a top-level `migrate-*` command name. Update `ALL_SUBCOMMANDS` / parser choice lists. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m llmwiki migrate` and `migrate --list` against `$TMP_VAULT` print all six names and do not write; `migrate raw-redaction --dry-run --vault "$TMP_VAULT"` still reports; `python3 -m pytest` on the touched migrate tests `-q`; `ruff check llmwiki/cli.py` and the touched test files. No leftover screenshots. **[Agent: general-purpose]**

- [ ] **Slice 2: Drop `synthesize` and `consolidate-topics`**

  > End state: those names are not registered; `synth` is the only synthesize entry; `/wiki-synthesize` runs `synth --sources-only`; retirement/alias tests are deleted.

  - [ ] Unregister `synthesize` and `consolidate-topics`. Delete `cmd_consolidate_topics` and the `deprecated_synthesize` branch. Wire `cmd_synthesize` only to `synth`. Point `llmwiki/agent_kit/commands/wiki-synthesize.md` at `python3 -m llmwiki synth --sources-only`. **[Agent: general-purpose]**
  - [ ] Delete tests for the alias and the retirement stub (`consolidate-topics` still-resolves / exit 2, `deprecated_synthesize`, coverage that required live `## synthesize` / `## consolidate-topics` headings). Keep live `synth` / known-names / slash-synth tests; retarget argv. Update `ALL_SUBCOMMANDS`. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest` on remaining synth / 147 / smoke / slash-parity tests that you touched `-q`; `ruff check` on touched files. **[Agent: general-purpose]**

- [ ] **Slice 3: `--help` is a lifecycle map with full per-command prose**

  > End state: top-level help uses the six groups + loop epilog; no issue numbers; each remaining command’s `--help` has a real description; argparse-only (`RawDescriptionHelpFormatter`; omit top-level `help=` on `add_parser`).

  - [ ] Root parser: `RawDescriptionHelpFormatter`, grouped `description`, loop `epilog`, `add_subparsers(..., metavar="COMMAND")`, no `help=` on top-level `add_parser`. Each subparser: `formatter_class=RawDescriptionHelpFormatter` and a multi-paragraph `description` (purpose, loop position, non-effects; rare called out first for `migrate` and `queue`). Strip `#N` / G-codes from flag `help=`; define “adapter” inline where used. `migrate --help` explains list vs apply. **[Agent: general-purpose]**
  - [ ] Tests: root `format_help()` contains the six headings and the epilog; every live subparser name appears in the description exactly once; top-level help has no `#\d+`; `synth` / `candidates` / `queue` / `all` / `migrate` `--help` cover the spec sentences. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m llmwiki --help` and a sample of subcommand `--help`; `python3 -m pytest` on the new help tests `-q`; `ruff check` on touched files. **[Agent: general-purpose]**

- [ ] **Slice 4: Docs, upgrade notes, and agent schema match the live CLI**

  > End state: CLI reference, cheatsheet, slash docs, tutorials that taught dead names, UPGRADING, CHANGELOG, AGENTS.md, CLAUDE.md agree with `--help`.

  - [ ] Rewrite `docs/reference/cli.md` (grouped intro, one `## \`migrate\`` section, no live headings for removed names). Update `docs/UPGRADING.md`, `CHANGELOG.md` Unreleased, `docs/cheatsheet.md`, `docs/reference/slash-commands.md`, tutorials that still instruct `synthesize` or `consolidate-topics`. Map old `migrate-*` → `migrate <name>`. **[Agent: general-purpose]**
  - [ ] AGENTS.md and CLAUDE.md: new migrations register under `migrate` in `cli.py`, not as new top-level commands. Same note in the CLI reference migrate section. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_reference_coverage.py tests/test_cli_doc_parity.py tests/test_docs_structure.py tests/test_tutorial_ux.py -q` (and any other doc-guard tests that fail); `ruff check` if Python tests changed. **[Agent: general-purpose]**

- [ ] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: [spec-directory]` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
