---
title: "Command cheatsheet (part 1/2)"
slug: command-cheatsheet-01
project: cheatsheet
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/cheatsheet.md"
content_sha256: e6ca298f4ad85f23bafd0499940f3b1e08825b0d0b77066af98d7d09137a327f
---

> Part 1 of 2 of **Command cheatsheet**.

---
title: "Command cheatsheet"
type: navigation
docs_shell: true
---

# Command cheatsheet

Everything you need on one page. Slash commands work inside Claude Code / Codex CLI; CLI commands run at your terminal.

## 30-second setup

From Claude Code, run these slash commands in order:

1. `/wiki-init` — scaffold raw/ wiki/ site/
2. `/wiki-sync` — ingest sessions from every auto-detected agent
3. `/wiki-graph` — build the AI knowledge graph
4. `/wiki-build` — compile the static site
5. Open `site/index.html` — the site is plain files, nothing to run
6. `llmwiki install-automation` — hand that loop to a daily job so you never repeat it

## Keeping it current

Set the daily job up once and llmwiki keeps itself up to date. The wizard asks what the job should do (collect sessions only, or also summarise them), offers the optional extras, and shows you the exact command line before it writes anything.

```bash
llmwiki install-automation                                   # interactive wizard
llmwiki install-automation --yes --job ingest                # collect sessions + rebuild the site; no AI provider, no cost
llmwiki install-automation --yes --job maintain --schedule "0 8 * * 1-5"   # also summarise; weekdays at 08:00
llmwiki install-automation --yes --job maintain --graph builtin --lint-fail errors
```

`--job maintain` sends session text to your AI provider — run `llmwiki synth --estimate` first to see what a run costs. Re-running the command replaces the existing job instead of adding a second one. Full flag table: [CLI reference](reference/cli.md#install-automation--set-up-the-daily-job).

For a one-off run of the same pipeline by hand:

```bash
llmwiki all                            # sync → synth → build → graph → lint
llmwiki all --no-synth                 # same run, no LLM calls
llmwiki all --skip-graph --skip-lint   # sync → synth → build only
llmwiki all --lint-fail errors         # exit 2 when lint reports an error
```

## One step at a time

| What you want | Slash command | CLI equivalent |
|---|---|---|
| Convert new session transcripts | `/wiki-sync` | `llmwiki sync` |
| Ingest a source file into the wiki | `/wiki-ingest <path>` | -- |
| Ask the wiki a question | `/wiki-query <question>` | -- |
| Edit one page surgically | `/wiki-update <page>` | -- |
| Find orphans + broken links | `/wiki-lint` | `llmwiki lint` |
| Triage candidate pages | -- | `llmwiki candidates list` |
| Build / rebuild the site | `/wiki-build` | `llmwiki build` |
| Interactive graph | `/wiki-graph` | `llmwiki graph` |
| AI knowledge graph | `/wiki-graph` | `llmwiki graph --engine graphify` |
| Self-reflection on wiki gaps | `/wiki-reflect` | -- |

## CLI commands you'll use most

`llmwiki --help` lists every subcommand in six lifecycle groups (Start here → Daily loop → Run the loop for me → Look around → Take things out → Rare). One-time vault repairs live under `migrate <name>`, not top-level `migrate-*`. These are the ones that carry the daily loop:

| Command | Purpose |
|---|---|
| `init` | Scaffold `raw/` `wiki/` `site/` + seed 9 nav files |
| `install-automation` | Set up the daily job that runs the loop for you |
| `all` | Whole pipeline in one run: sync → synth → build → graph → lint (opt out per stage) |
| `sync` | Convert `.jsonl` sessions -> markdown -> wiki -> site |
| `synth` | Synthesize sources + harvest entity/concept candidates |
| `candidates` | Approval workflow (list / promote / merge / discard) |
| `build` | Compile `wiki/` markdown into `site/` HTML + AI exports (`llms.txt`, `sitemap.xml`, …) |
| `graph` | Build the knowledge graph (Graphify default, builtin fallback) |
| `lint` | Run 17 wiki-quality rules |
| `query` | Search the knowledge graph with a question |
| `add` | Add a URL, file, or folder to the wiki |
| `watch` | Near-real-time sync → synth → build when a session finishes |
| `adapters` | List every adapter + its status |
| `migrate` | List or apply a named one-time vault repair (`migrate --list`) |
| `version` | Print version |

## Knowledge graph

```bash
llmwiki graph                          # builtin wikilink graph (stdlib, zero deps)
llmwiki graph --engine graphify        # AI-powered: Leiden communities, confidence edges, god nodes
llmwiki graph --format json            # json only
llmwiki graph --format html            # interactive HTML only
```

Install Graphify: `pip install llm-wiki-plus[graph]`

Graphify outputs to `graphify-out/`: `graph.json`, `graph.html`, `GRAPH_REPORT.md`.
Features: tree-sitter AST extraction, semantic analysis, community detection, confidence-scored edges.

## AI-consumable exports

`llmwiki build` writes every AI-consumable export into the output directory (default `site/`). There is no separate `export` subcommand — replace `llmwiki export all` with `llmwiki build`.

```bash
llmwiki build                          # HTML site + llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, ai-readme.md
```

## Quality

```bash
llmwiki lint                           # 17 wiki-quality rules
llmwiki lint --json --fail-on-errors   # CI-friendly
llmwiki lint --rules link_integrity,orphan_detection
llmwiki lint --vault /path/to/vault --fail-on-warnings   # rules switched off in <vault>/llmwiki.json never run
```

## Candidate workflow

```bash
llmwiki candidates list                # show all candidates
llmwiki candidates list --stale        # only stale (>30 days)
llmwiki candidates promote --slug Foo  # promote to wiki
llmwiki candidates merge --slug A --into B
llmwiki candidates discard --slug X --reason "hallucinated"
```

## LLM synthesis

```bash
llmwiki synth                          # sources + candidates
llmwiki synth --sources-only           # sources only (legacy synthesize default)
llmwiki synth --check                  # probe backend (exit 0 if ok)
llmwiki synth --estimate               # cost (eligible sources) + Candidates (pre-run state)
llmwiki synth --force                  # re-synth everything, then harvest
```

Auto-tags pages (up to 5 AI tags per page, near-dup rejection, stop-word filter).
