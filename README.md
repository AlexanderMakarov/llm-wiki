# llmwiki

> **LLM-powered knowledge base from your coding-agent session history.**
> Built on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

This repo is a **personal fork** ([AlexanderMakarov/llm-wiki](https://github.com/AlexanderMakarov/llm-wiki)) of [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki). It adds **OpenClaw** and **Cursor CLI** adapters, a **topic-first knowledge graph**, and a **vault-outside-the-repo** workflow so your sessions never land in git.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v1.3.82-10B981.svg)](CHANGELOG.md)

**Upstream demo site** (synthetic data only): [pratiyush.github.io/llm-wiki](https://pratiyush.github.io/llm-wiki/)

---

Claude Code, Codex CLI, Copilot, **Cursor**, **OpenClaw**, Gemini CLI, and Obsidian all leave transcripts on disk. **llmwiki** converts them to redacted markdown, builds a searchable static site, and exposes the corpus to MCP clients.

```bash
git clone git@github.com:AlexanderMakarov/llm-wiki.git
cd llm-wiki
./setup.sh
# create config.json (see below), then:
llmwiki sync && llmwiki build && llmwiki serve --vault /path/to/your-vault
```

---

## Personal data stays outside the repo

The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live on an external **vault** directory:

```text
/path/to/your-vault/          ← vault root (NOT …/wiki)
  raw/sessions/               ← converted transcripts
  wiki/                       ← LLM-maintained pages (sources/, index.md, …)
  site/                       ← built static HTML
  .llmwiki-state.json         ← local pipeline state (gitignored everywhere)
  .llmwiki-synth-state.json
  .llmwiki-topics.json        ← topic consolidation cache
```

### 1. `config.json` at the repo root (gitignored)

```json
{
  "vault": {
    "default_path": "/mnt/innerhdd/openclaw-obsidian"
  },
  "synthesis": {
    "backend": "agent_delegate"
  }
}
```

With `vault.default_path` set, **`sync` / `build` / `synthesize` / `consolidate-topics` / `all`** target the vault automatically — no `--vault` flag needed. Personal overrides merge over `examples/sessions_config.json` without editing tracked files.

### 2. `LLMWIKI_ROOT` for MCP and agents

Point at the **vault root** (the directory that contains `raw/` and `wiki/`):

```bash
export LLMWIKI_ROOT=/mnt/innerhdd/openclaw-obsidian
```

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "llmwiki": {
      "command": "/path/to/llm-wiki/.venv/bin/python",
      "args": ["-m", "llmwiki.mcp"],
      "env": {
        "LLMWIKI_ROOT": "/mnt/innerhdd/openclaw-obsidian",
        "PYTHONPATH": "/path/to/llm-wiki"
      }
    }
  }
}
```

**Claude Code** (gitignored `.claude/settings.local.json`):

```json
{ "env": { "LLMWIKI_ROOT": "/mnt/innerhdd/openclaw-obsidian" } }
```

### What stays gitignored

| Path | Why |
|---|---|
| `raw/` | Session transcripts |
| `wiki/sources/`, `wiki/entities/`, … | Your generated wiki pages |
| `wiki/projects/*` (except `demo-*.md`) | Per-project topic profiles |
| `site/` | Built HTML |
| `config.json` | Vault path + personal settings |
| `.llmwiki-*`, `.llmwiki-pending-prompts/` | Pipeline / agent-delegate scratch state |

See [docs/guides/existing-vault.md](docs/guides/existing-vault.md) for Obsidian/Logseq vault layouts.

---

## What you get

### Static site

- Session browser with search (Cmd+K), filters, syntax highlighting, dark mode
- Per-session `.html` + `.txt` + `.json` siblings for humans and agents
- Project pages with topic chips, activity heatmap, agent badges
- Site exports: `llms.txt`, `llms-full.txt`, `graph.jsonld`, sitemap, RSS

### Topic-first knowledge graph

The built-in graph is **topic-centric**, not a page mesh:

- **Nodes** = canonical topics (`OpenClaw`, `LLM-Wiki`, `Evrika`, …) derived from `[[wikilinks]]` in session summaries
- **Edges** = co-occurrence (how many sessions mention both topics)
- **Click a node** → side panel lists bridging sessions; **double-click** → `site/topics/<slug>.html`
- **Click an edge** → shared sessions between two topics

Pipeline:

```bash
llmwiki synthesize              # fills wiki/sources/ with wikilinks
llmwiki consolidate-topics      # one-time LLM pass → .llmwiki-topics.json (merge duplicates)
llmwiki build                   # writes site/graph.html + site/topics/
```

The consolidation step collapses near-duplicate spellings (`LLM-Wiki` / `LLMWiki` / `llm wiki`) into one node. Re-run after large ingest batches.

### MCP server

Twelve tools — query, grep, read page, lint, sync, export, confidence, lifecycle, dashboard, entity search, category browse:

```bash
python3 -m llmwiki.mcp
```

Set `LLMWIKI_ROOT` so tools read your vault, not the repo's demo wiki.

---

## Supported agents

Core adapters (auto-detected on `sync` when the session store exists):

| Agent | Adapter | Notes |
|---|---|---|
| [Claude Code](https://claude.com/claude-code) | `claude_code` | `~/.claude/projects/*/*.jsonl` |
| [Codex CLI](https://github.com/openai/codex) | `codex_cli` | `~/.codex/sessions/` |
| [Copilot Chat](https://github.com/features/copilot) | `copilot_chat` | VS Code workspaceStorage |
| [Copilot CLI](https://github.com/features/copilot) | `copilot_cli` | `~/.copilot/session-state/` |
| [Gemini CLI](https://ai.google.dev/gemini-api) | `gemini_cli` | `~/.gemini/` |
| [Obsidian](https://obsidian.md) (input) | `obsidian` | Markdown vault intake |

**Contrib adapters** (opt-in — pass `--adapter <name>` on sync):

| Agent | Adapter | Session store |
|---|---|---|
| **[OpenClaw](https://openclaw.ai)** | `openclaw` | `~/.openclaw/agents/*/sessions/*.jsonl` |
| **[Cursor CLI](https://cursor.com)** (`cursor-agent`) | `cursor_cli` | `~/.cursor/chats/<hash>/<uuid>/store.db` |
| Cursor IDE | `cursor` | IDE workspaceStorage (legacy) |
| OpenCode | `opencode` | Shared schema with OpenClaw |

```bash
llmwiki sync --adapter openclaw
llmwiki sync --adapter cursor_cli
llmwiki sync --adapter claude_code --adapter openclaw   # combine sources
llmwiki adapters --wide                                 # what's present on this machine
```

Enable a contrib adapter permanently in `config.json`:

```json
{ "adapters": { "openclaw": { "enabled": true }, "cursor_cli": { "enabled": true } } }
```

---

## Quick tutorial

```bash
llmwiki init                    # scaffold raw/ wiki/ site/ (repo or vault)
llmwiki sync                    # convert new sessions → vault raw/sessions/
llmwiki synthesize              # LLM summaries → vault wiki/sources/
llmwiki consolidate-topics      # optional: dedupe topic vocabulary
llmwiki build                   # vault raw/ + wiki/ → vault site/
llmwiki serve --vault /path/to/your-vault
```

One-shot:

```bash
llmwiki all --with-synth --graph-engine builtin
```

Useful flags:

- `--vault PATH` — override `config.json` default for one run
- `--adapter <name>` — limit sync to one source
- `--force` — re-convert sessions even if unchanged
- `llmwiki lint` — broken wikilinks, orphans, stale pages

---

## How it works

```
~/.claude/projects/*.jsonl
~/.openclaw/agents/*/sessions/*.jsonl
~/.cursor/chats/*/store.db
         │
         ▼  llmwiki sync  (→ vault when config.json set)
┌────────────────────────────┐
│  vault/raw/sessions/       │  immutable markdown (layer 1)
└─────────────┬──────────────┘
              ▼  llmwiki synthesize + agent ingest
┌────────────────────────────┐
│  vault/wiki/sources/       │  summaries with [[wikilinks]] (layer 2)
│  vault/wiki/index.md       │
└─────────────┬──────────────┘
              ▼  llmwiki build
┌────────────────────────────┐
│  vault/site/               │  static HTML + graph + topics/ (layer 3)
│  ├── sessions/…            │
│  ├── topics/evrika.html    │
│  ├── graph.html            │  topic co-occurrence viewer
│  └── llms.txt, …           │
└────────────────────────────┘
```

Agent workflows (`/wiki-sync`, `/wiki-ingest`, `/wiki-query`) are defined in [CLAUDE.md](CLAUDE.md) and [AGENTS.md](AGENTS.md).

---

## CLI reference

```bash
llmwiki init
llmwiki sync [--adapter NAME] [--vault PATH]
llmwiki build [--vault PATH]
llmwiki serve [--vault PATH]
llmwiki synthesize [--vault PATH]
llmwiki consolidate-topics [--complete reply.json]
llmwiki graph
llmwiki lint [--wiki-dir PATH]
llmwiki export all
llmwiki all [--with-synth]
llmwiki adapters [--wide]
llmwiki version
```

Shell shortcuts: `./sync.sh`, `./build.sh`, `./serve.sh`.

---

## Configuration

Shipped defaults: `examples/sessions_config.json`. Personal overrides: **`config.json`** (gitignored) at the repo root — merged on top. See [Configuration](#personal-data-stays-outside-the-repo) above and [docs/configuration.md](docs/configuration.md).

## `.llmwikiignore`

Skip projects or date ranges without touching config:

```
confidential-client/
*2025-*
```

---

## Documentation

| Topic | Link |
|---|---|
| Install + first build | [docs/getting-started.md](docs/getting-started.md) |
| External vault setup | [docs/guides/existing-vault.md](docs/guides/existing-vault.md) |
| Claude Code workflow | [docs/tutorials/03-use-with-claude-code.md](docs/tutorials/03-use-with-claude-code.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Full CLI | [docs/reference/cli.md](docs/reference/cli.md) |
| Agent-delegate synthesis | [docs/modes/agent/index.md](docs/modes/agent/index.md) |
| Upstream changelog | [CHANGELOG.md](CHANGELOG.md) |

Per-adapter docs: [Claude Code](docs/adapters/claude-code.md) · [Codex CLI](docs/adapters/codex-cli.md) · [Cursor](docs/adapters/cursor.md) · [Obsidian](docs/adapters/obsidian.md)

---

## Design principles

- **Stdlib first** — runtime dep is `markdown` only; optional `[graph]`, `[dev]`, `[e2e]` extras
- **Redact by default** — usernames, keys, tokens, emails stripped before wiki
- **Idempotent** — re-running sync/build is safe
- **Privacy by default** — localhost serve, no telemetry
- **Data outside git** — vault + gitignore, not "trust the contributor"

---

## Acknowledgements

- [Andrej Karpathy](https://twitter.com/karpathy) — [LLM Wiki idea](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Pratiyush](https://github.com/Pratiyush/llm-wiki) — upstream framework this fork extends

## License

[MIT](LICENSE) © Pratiyush (upstream); fork modifications © Alexander Makarov
