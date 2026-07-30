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
| `synthesize` | LLM-backed source-page synthesis with auto-tagging |
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
llmwiki synthesize                     # synthesize source pages
llmwiki synthesize --check             # probe backend (exit 0 if ok)
llmwiki synthesize --estimate          # cost preview, no API calls
llmwiki synthesize --force             # re-synth everything
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

## All configurable settings (sessions_config.json)

| Section | Key | Default | What |
|---|---|---|---|
| `vault` | `default_path` | `""` (must pass `--vault`) | Default Obsidian/Logseq vault path |
| `vault.layout` | `entities` | `Wiki/Entities` | Vault subfolder for entity pages |
| `vault.layout` | `concepts` | `Wiki/Concepts` | Vault subfolder for concept pages |
| `vault.layout` | `sources` | `Wiki/Sources` | Vault subfolder for source pages |
| `vault.layout` | `syntheses` | `Wiki/Syntheses` | Vault subfolder for synthesis pages |
| `vault` | `allow_overwrite` | `false` | Allow clobbering existing vault pages |
| `graph` | `default_engine` | `builtin` | Graph engine: `builtin` or `graphify` |
| `graph` | `format` | `both` | Graph output: `json`, `html`, or `both` |
| `serve` | `port` | `8765` | Dev server port |
| `serve` | `host` | `127.0.0.1` | Dev server bind address |
| `serve` | `open_browser` | `false` | Auto-open browser on serve |
| `build` | `out_dir` | `site` | Build output directory |
| `build` | `search_mode` | `auto` | Search index mode: `auto`, `tree`, `flat` |
| `build` | `synthesize` | `false` | Auto-synthesize overview on build |
| `schedule` | `build` | `on-sync` | When to auto-build: `on-sync`, `daily`, `manual` |
| `schedule` | `lint` | `manual` | When to auto-lint: `on-sync`, `daily`, `manual` |
| `synthesis` | `backend` | `dummy` | LLM backend: `dummy`, `ollama` |
| `synthesis` | `model` | `llama3.1:8b` | Model for synthesis |
| `synthesis` | `base_url` | `http://127.0.0.1:11434` | Ollama server URL |
| `synthesis` | `timeout` | `60` | Synthesis timeout (seconds) |
| `filters` | `live_session_minutes` | `60` | Skip sessions younger than N minutes |
| `truncation` | `tool_result_chars` | `500` | Max chars for tool results in output |

## Three-layer architecture

```
raw/     IMMUTABLE transcripts (source of truth, never modify)
wiki/    LLM-generated pages (you own this)
  sources/      one summary per raw source
  entities/     people, projects, tools (TitleCase.md)
  concepts/     ideas, patterns, decisions (TitleCase.md)
  syntheses/    saved query answers
  comparisons/  side-by-side diffs
  questions/    first-class open questions
site/    GENERATED static HTML (don't edit by hand)
```

## Common recipes

```bash
# Daily: sync + serve
llmwiki sync && llmwiki serve --open

# Nightly cron (one project)
llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)

# AI knowledge graph
pip install llm-notebook[graph]
llmwiki graph --engine graphify

# CI quality gate
llmwiki lint --json --fail-on-errors

# Export wiki to Obsidian vault
llmwiki sync --vault "~/Documents/Obsidian Vault/my-wiki"

# Full site rebuild with AI synthesis (exports included)
llmwiki build --synthesize
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Operation failed |
| `2` | Usage error (bad flags) |

## See also

- [CLI reference](reference/cli.md) -- every flag of every subcommand
- [Slash commands reference](reference/slash-commands.md) -- what each `/wiki-*` does
- [UI reference](reference/ui.md) -- every screen on the compiled site
- [Upgrade guide](UPGRADING.md) -- what changes between releases
