---
title: "Command cheatsheet (part 1/2)"
slug: command-cheatsheet-01
project: command-cheatsheet
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/cheatsheet.md"
content_sha256: 2168a9b67d566f2f5b0f51a1fe92e58499d300f8d3d83dfdc71469582abfee80
---

> Part 1 of 2 of **Command cheatsheet**.

---
title: "Command cheatsheet"
type: navigation
docs_shell: true
---

# Command cheatsheet

Everything you need on one page. Slash commands work inside Claude
Code / Codex CLI; CLI commands run at your terminal.

## 30-second setup

From Claude Code, run these slash commands in order:

1. `/wiki-init` — scaffold raw/ wiki/ site/
2. `/wiki-sync` — ingest sessions from every auto-detected agent
3. `/wiki-graph` — build the AI knowledge graph
4. `/wiki-build` — compile the static site
5. `/wiki-serve` — browse at http://127.0.0.1:8765/

## Daily flow

| What you want | Slash command | CLI equivalent |
|---|---|---|
| Convert new session transcripts | `/wiki-sync` | `llmwiki sync` |
| Ingest a source file into the wiki | `/wiki-ingest <path>` | -- |
| Ask the wiki a question | `/wiki-query <question>` | -- |
| Edit one page surgically | `/wiki-update <page>` | -- |
| Find orphans + broken links | `/wiki-lint` | `llmwiki lint` |
| Triage candidate pages | -- | `llmwiki candidates list` |
| Build / rebuild the site | `/wiki-build` | `llmwiki build` |
| Serve locally | `/wiki-serve` | `llmwiki serve --open` |
| Interactive graph | `/wiki-graph` | `llmwiki graph` |
| AI knowledge graph | `/wiki-graph` | `llmwiki graph --engine graphify` |
| Self-reflection on wiki gaps | `/wiki-reflect` | -- |

## 12 CLI commands

| Command | Purpose |
|---|---|
| `init` | Scaffold `raw/` `wiki/` `site/` + seed 9 nav files |
| `sync` | Convert `.jsonl` sessions -> markdown -> wiki -> site |
| `build` | Compile `wiki/` markdown into `site/` HTML + AI exports (`llms.txt`, `sitemap.xml`, …) |
| `serve` | Start local HTTP server (default `:8765`) |
| `adapters` | List every adapter + its status |
| `graph` | Build the knowledge graph (Graphify default, builtin fallback) |
| `query` | Search the knowledge graph with a question |
| `all` | Full pipeline: optional sync/synth → build → graph → lint |
| `lint` | Run 14 wiki-quality rules |
| `candidates` | Approval workflow (list / promote / merge / discard) |
| `synth` | Synthesize sources + harvest entity/concept candidates |
| `synthesize` | *(deprecated)* alias for `synth --sources-only` |
| `version` | Print version |

## Knowledge graph

```bash
llmwiki graph                          # builtin wikilink graph (stdlib, zero deps)
llmwiki graph --engine graphify        # AI-powered: Leiden communities, confidence edges, god nodes
llmwiki graph --format json            # json only
llmwiki graph --format html            # interactive HTML only
```

Install Graphify: `pip install llm-notebook[graph]`

Graphify outputs to `graphify-out/`: `graph.json`, `graph.html`, `GRAPH_REPORT.md`.
Features: tree-sitter AST extraction, semantic analysis, community detection, confidence-scored edges.

## AI-consumable exports

`llmwiki build` writes every AI-consumable export into the output directory (default `site/`). There is no separate `export` subcommand — replace `llmwiki export all` with `llmwiki build`.

```bash
llmwiki build                          # HTML site + llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, ai-readme.md
```

## Quality

```bash
llmwiki lint                           # 17 structural rules
llmwiki lint --json --fail-on-errors   # CI-friendly
llmwiki lint --rules link_integrity,orphan_detection
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
llmwiki synth --sources-only           # legacy: sources only
llmwiki synth --check                  # probe backend (exit 0 if ok)
llmwiki synth --estimate               # cost (eligible sources) + Candidates (pre-run state)
llmwiki synth --force                  # re-synth everything, then harvest
llmwiki synthesize                     # deprecated → sources-only + warning
```

Auto-tags pages (up to 5 AI tags per page, near-dup rejection, stop-word filter).

## Adapters

```bash
llmwiki adapters                       # list every adapter + who fires on next sync
llmwiki adapters --wide                # untruncated descriptions
```

**Core** (auto-discovered, always loaded):

| Adapter | Source |
|---------|--------|
| `claude_code` | `~/.claude/projects/` |
| `codex_cli` | `~/.codex/sessions/` |

**Contrib** (load on-demand with `--adapter <name>`):

| Adapter | Source |
|---------|--------|
| `chatgpt` | `conversations.json` export |
| `copilot_chat` | VS Code workspaceStorage |
| `copilot_cli` | GitHub Copilot CLI |
| `cursor` | VS Code workspaceStorage |
| `gemini_cli` | `~/.gemini/` |
| `obsidian` | Obsidian vault `.md` files |
| `opencode` | OpenCode / OpenClaw sessions |

## Obsidian integration

```bash
# Sync wiki into an Obsidian vault
llmwiki sync --vault "~/Documents/Obsidian Vault/my-wiki"

# Build site from a vault
llmwiki build --vault "~/Documents/Obsidian Vault/my-wiki"

# Use the obsidian adapter to read from a vault
llmwiki sync --adapter obsidian
```

## Flags you'll actually use

| Flag | Command | What |
|---|---|---|
| `--since YYYY-MM-DD` | `sync` | Only sessions after that date |
| `--project <slug>` | `sync` | Restrict to one project |
| `--force` | `sync`, `synthesize` | Ignore state file, reconvert everything |
| `--force-resync` | `sync` | Override the newer-schema/corrupt-state guard (#29); implies `--force`, may duplicate `raw/` |
| `--fail-on-errors` | `lint` | Non-zero exit on error-severity issues |
| `--vault <path>` | `sync`, `build`, `synthesize`, `add`, `queue`, `all` | Operate on an external vault (also sets the active state file) |
| `--dir <path>` | `serve` | Directory to serve (usually `<vault>/site`) |
| `--engine graphify` | `graph` | AI-powered knowledge graph |
| `--host 0.0.0.0` | `serve` | Bind LAN-accessible (default: loopback-only) |
| `--status` | `sync` | Show last sync + per-adapter counters |

## Config files

| File | Purpose |
|---|---|
| `config.json` / `examples/sessions_config.json` | All settings (see below) |
| `.llmwikiignore` | Exclude patterns (git-ignore format) |
| `llmwiki-state.json` | Unified queue + sync + synth + quarantine state (auto; gitignored) |
| `llmwiki-state.js` | UI sidecar for the Home queue panel (vault root + copied into `site/` on build) |
| `.env` | Optional secrets for adapters that need them |
