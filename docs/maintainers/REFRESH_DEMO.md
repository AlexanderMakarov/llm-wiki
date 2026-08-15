# Refresh the demo vault

`scripts/refresh_demo.py` is the one command that takes changed product documentation, summarises it into the example vault, and rebuilds the demo site.

It is a **local maintainer tool**. It never runs in CI, is not a CLI subcommand, and is not part of a packaged install.

## What it does

1. Reads the last-refreshed git revision from `demo/.demo-source-rev`.
2. Asks git which files under `docs/` changed since that revision (`git diff --name-status`) and which still have uncommitted working-tree edits (`git status --porcelain`), so a maintainer can preview before committing.
3. Builds a plan: added pages are added, deleted pages are removed, modified or renamed pages are removed and then re-added (llmwiki cannot update an already-ingested document in place).
4. Drives the existing CLI against `demo/`: `add` / `remove`, then once per run `synth --docs-only`, `build --out demo/site`, and `lint`.
5. Writes `HEAD` into `demo/.demo-source-rev`.
6. Prints the full lint report. Warnings do not fail the run; they are the maintainer's sight of warning-severity defects under the errors-only CI gate.

Maintainer docs under `docs/maintainers/` are not part of the product corpus and never enter the plan.

## Prerequisites

- A **git working copy** of this repository. Change detection is git history, not file timestamps. The command **cannot run from a release archive** (a downloaded tarball or an installed wheel has no `.git` and no recorded revision to diff against).
- A **working synthesis backend** (`synthesis.backend` in `config.json` set to `claude` or `ollama`, and that backend reachable). The script probes with `llmwiki synth --check` and stops with an actionable error before it touches the vault if nothing is reachable.

## Usage

From the repository root:

```bash
python3 scripts/refresh_demo.py --dry-run
python3 scripts/refresh_demo.py
python3 scripts/refresh_demo.py --force
python3 scripts/refresh_demo.py --base HEAD~5
```

| Flag | Effect |
|---|---|
| `--dry-run` | Print the plan and write nothing. Does not need a synthesis backend. |
| `--force` | Treat every product doc under `docs/` as changed (remove-then-add each). Use this for a first refresh when `demo/.demo-source-rev` does not exist yet. |
| `--base <rev>` | Diff against this revision instead of the SHA in `demo/.demo-source-rev`. |

The command reports the plan before it does any work. `--dry-run` is the preview that changes nothing.

## What this does not do

- It does not commit. After a real run, review `demo/raw/`, `demo/wiki/`, and `demo/.demo-source-rev` yourself.
- It does not run in GitHub Actions. CI builds and lints the committed demo; it never regenerates it. Wiki-checks also triggers on `docs/**`. If `demo/.demo-source-rev` is committed, that job prints `python3 scripts/refresh_demo.py --dry-run` so a docs change without a local refresh is visible — still no model, still no vault write.
- The committed pre-push hook reminds you when a push includes product markdown under `docs/` (not `docs/maintainers/`). The reminder does not fail the push; applying the plan is still a local `refresh_demo.py` run.
- It does not change how user vaults ingest documents. The remove-then-add workaround is demo-only.
