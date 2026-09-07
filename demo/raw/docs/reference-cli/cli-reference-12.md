---
title: "CLI reference (part 12/15: all — run the full pipeline)"
slug: cli-reference-12
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 12 of 15 of **CLI reference** — all — run the full pipeline.

## `all` — run the full pipeline

The one command to run after agent sessions land. It runs every stage in order — `sync` → `synth` → `build` → `graph` → `lint` — so a scheduled job is a bare `llmwiki all` rather than a trail of flags. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step.

Every stage runs by default and every stage has an opt-out flag: `--no-sync`, `--no-synth`, `--skip-graph`, `--skip-lint`. `synth` is the only stage that can call an LLM; with the default `dummy` synthesis backend it makes no provider call at all, and `--no-synth` turns it off outright.

```bash
python3 -m llmwiki all                          # every stage
python3 -m llmwiki all --no-synth               # no LLM calls
python3 -m llmwiki all --no-sync --no-synth     # build → graph → lint only
python3 -m llmwiki all --graph-engine builtin   # skip optional graphify
python3 -m llmwiki all --skip-graph --lint-fail warnings   # fail CI on any lint issue
```

### Flags

| Flag | What |
|---|---|
| `--out DIR` | Output dir for `build`. Default: `site/`. |
| `--search-mode {auto,tree,flat}` | Forwarded to `build`. Default: `auto`. |
| `--graph-engine {builtin,graphify}` | Forwarded to `graph`. Default: `graphify`. |
| `--no-sync` | Skip the sync step (do not convert new agent sessions first). |
| `--no-synth` | Skip the synth step, so the run makes no LLM calls. |
| `--synth-force` | Pass `--force` to synth (re-synthesize every session). |
| `--skip-graph` | Skip the graph step entirely (useful when graphify is not installed). |
| `--skip-lint` | Skip the lint step entirely. |
| `--lint-fail {never,errors,warnings}` | When lint findings fail the run with exit `2`. Default: `never`. |
| `--strict` | Spelling for `--lint-fail warnings`. When both are given, the stricter wins. |
| `--fail-fast` | Stop at the first non-zero step. Default: continue, report the worst exit code. |
| `--with-sync`, `--with-synth` | Deprecated and inert — the stages they used to enable now run by default. Accepted so an already-installed scheduled command keeps parsing; each prints a one-line notice. |
| `--vault PATH` | Run every step against this vault instead of the repo. |

### Lint failure policy

`lint` always prints its findings. `--lint-fail` decides whether those findings end the run:

| Policy | Fails when |
|---|---|
| `never` (default) | Never — findings are reported and the run still exits `0`. |
| `errors` | Lint reported at least one error-severity issue. |
| `warnings` | Lint reported at least one error **or** warning. |

### Conflicting flags

`--no-synth` wins over `--with-synth`, and `--no-sync` wins over `--with-sync`, in any order on the command line — the deprecated `--with-*` aliases are inert and cannot re-enable a stage you just switched off. `--strict` and `--lint-fail` resolve to whichever of the two is stricter.

Exit codes:

- `0` — every step succeeded.
- non-zero — forwarded from the first (or worst) failing step.
- `2` — the lint failure policy was met, or a required directory was missing.

---

## `watch` — near-real-time maintain when sessions finish

Polls adapter session stores on an interval and runs maintain when a session looks finished. Uses per-adapter turn-complete heuristics (Claude `stop_reason`, Cursor last role, Codex events). Mid-tool / permission loops stay deferred until the adapter reports safe. Adapters without a finished-signal still trigger after a 2s mtime settle — not a multi-minute quiesce.

Single-flight: only one maintain iteration at a time (`sync` → `synth` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes. Sync may time out (~180s); synth and build have no timeout.

```bash
python3 -m llmwiki watch
python3 -m llmwiki watch --adapter claude_code cursor
python3 -m llmwiki watch --interval 10 --settle 3
python3 -m llmwiki watch --dry-run
python3 -m llmwiki watch --no-synthesize --no-build
python3 -m llmwiki watch --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to / load specific adapters. Default: every ingest-ready coding-agent source with a present store and no `enabled: false`. Notes intake still needs `enabled: true`. See [multi-agent-setup.md](../multi-agent-setup.md). |
| `--interval SECONDS` | Poll interval. Default: `5`. |
| `--settle SECONDS` | Mtime settle before ready check for adapters without a finished-signal. Default: `2`. |
| `--dry-run` | Detect finished sessions only; do not run maintain. |
| `--no-synthesize` | Skip the synthesize step. |
| `--no-build` | Skip the build step. |
| `--vault PATH` | Maintain this vault instead of the repo. |

---
