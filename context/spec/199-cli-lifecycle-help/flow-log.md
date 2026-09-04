# Flow log — 199-cli-lifecycle-help

## fetch-ticket

- Issue [#112](https://github.com/AlexanderMakarov/llm-wiki/issues/112) (open): CLI help as a lifecycle map.
- Operator add-on: remove unused/useless CLI commands; later: wrap `migrate-*` into one `migrate`; rewrite tutorials that still teach `synthesize` / `consolidate-topics`.
- Next: resume-detection / workspace.

## resume-detection

- Issue open; no existing spec or merged PR for #112.
- Next: workspace.

## workspace

- Branch `feat/112-cli-lifecycle-help`.
- Worktree `.claude/worktrees/feat-112-cli-lifecycle-help`.
- Throwaway vault `.worktree-vault` via worktree `config.json`.
- Next: specs.

## specs (functional)

- User choices: remove `consolidate-topics` and `synthesize`; six help groups (Start here / Daily loop / Run the loop for me / Look around / Take things out / Rare); long per-command help; single `migrate` with list-then-apply; tutorials that teach dead names rewritten.
- Wrote `context/spec/199-cli-lifecycle-help/functional-spec.md` (Approved; Author Aleksandr Makarov).
- Next: `/awos:tech` (await operator approval of technical-considerations.md).

## specs (technical, draft)

- Operator: no `cli_help.py` / custom formatter — Python 3.12 argparse only (`RawDescriptionHelpFormatter`, `description`/`epilog`, omit subparser `help=` so the grouped map is not duplicated; nested `migrate` subparsers).
- Operator: delete tests whose subject is a removed command; do not invert them into unknown-command assertions. Retarget tests of live features (`synth`, `migrate <name>`).
- Wrote `context/spec/199-cli-lifecycle-help/technical-considerations.md` (Draft).
- Next: operator approval of technical-considerations.md, then `/awos:tasks`.

## specs (technical, approved)

- Operator lgtm on argparse-only + delete tests for removed features.
- Status Approved; wrote `tasks.md` (5 slices: migrate wrapper, drop dead commands, help map, docs/schema, Feature Testing & Regression via testing-expert). Implementation tasks: general-purpose (no Python CLI specialist).
- Next: commit-specs.

## commit-specs

- Commit `context/spec/199-cli-lifecycle-help/` on `feat/112-cli-lifecycle-help`.
- Next: implement.

## implement

- Slices 1–5 complete in worktree: migrate wrapper; drop synthesize/consolidate-topics; lifecycle help + tests; docs/schema; acceptance tests (`tests/test_112_acceptance.py`, `tests/test_cli_lifecycle_help.py`).
- Static gate: `ruff check` clean; full `pytest tests/ -q` green.
- Next: verify / user smoke confirm (no local review until confirmed).

