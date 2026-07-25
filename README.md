# llmwiki

> **LLM-powered knowledge base from your coding-agent session history.**
> Built on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

This repo is a **personal fork** ([AlexanderMakarov/llm-wiki](https://github.com/AlexanderMakarov/llm-wiki)) of [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki). It adds **OpenClaw** and **Cursor CLI** adapters, a **topic-first knowledge graph**, and a **vault-outside-the-repo** workflow so your sessions never land in git.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v1.4.0-10B981.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-2850%20passing-10B981.svg)](tests/)
[![CI](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/ci.yml)
[![Link check](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/link-check.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/link-check.yml)
[![Wiki checks](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/wiki-checks.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/wiki-checks.yml)
[![Docker](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/AlexanderMakarov/llm-wiki/pkgs/container/llm-wiki)

---

Claude Code, Codex CLI, Copilot, **Cursor**, **OpenClaw**, Gemini CLI, and Obsidian all leave transcripts on disk. **llmwiki** converts them to redacted markdown, builds a searchable static site, and exposes the corpus to MCP clients.

```bash
git clone git@github.com:AlexanderMakarov/llm-wiki.git
cd llm-wiki
./setup.sh
# create config.json (see below), then:
llmwiki sync && llmwiki build && llmwiki serve --dir /path/to/your-vault/site
```

---

## Personal data stays outside the repo

The git clone holds **code + demo seeds only**. Your transcripts, wiki pages, and built site live on an external **vault** directory:

```text
/path/to/your-vault/          ← vault root (NOT …/wiki)
  raw/sessions/               ← converted transcripts
  wiki/                       ← LLM-maintained pages (sources/, index.md, …)
  site/                       ← built static HTML
  llmwiki-state.json          ← unified queue + sync + synth + quarantine state
  llmwiki-state.js            ← UI sidecar for Home queue panel (file:// safe)
  .llmwiki-topics.json        ← topic consolidation cache
```

State is **one active file per process**, configured at CLI entry from `--vault` / `--state-file` / `vault.default_path` (see [docs/architecture.md](docs/architecture.md)). Library callers never re-read `config.json` for the state path.

### 1. `config.json` at the repo root (gitignored)

```json
{
  "vault": {
    "default_path": "/mnt/innerhdd/openclaw-obsidian"
  },
  "synthesis": {
    "backend": "dummy"
  }
}
```

With `vault.default_path` set, **`sync` / `build` / `synthesize` / `queue` / `lint`** target the vault automatically — no `--vault` flag needed. Personal overrides merge over `examples/sessions_config.json` without editing tracked files.

### 2. MCP and agents read the vault via `config.json`

Set `vault.default_path` in `config.json` (repo root). The MCP server and CLI resolve content reads/writes from that path — no `LLMWIKI_ROOT` environment variable.

**Cursor** (`~/.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "llmwiki": {
      "command": "/path/to/llm-wiki/.venv/bin/python",
      "args": ["-m", "llmwiki.mcp"],
      "env": {
        "PYTHONPATH": "/path/to/llm-wiki"
      }
    }
  }
}
```

Ensure `/path/to/llm-wiki/config.json` contains your `vault.default_path`.

### Manual queue (no SessionStart auto-sync)

```bash
llmwiki queue status
llmwiki queue run --limit 20
llmwiki migrate-state   # one-time: merge legacy .llmwiki-* into llmwiki-state.json
# or: python3 scripts/migrate_state_v1_4_0.py --state-file /path/to/vault
```

Requires **Python ≥ 3.12**.

### What stays gitignored

| Path | Why |
|---|---|
| `raw/` | Session transcripts |
| `wiki/sources/`, `wiki/entities/`, … | Your generated wiki pages |
| `wiki/projects/*` (except `demo-*.md`) | Per-project topic profiles |
| `site/` | Built HTML |
| `config.json` | Vault path + personal settings |
| `.llmwiki-*` (legacy) | Pre-migration pipeline scratch — run `scripts/migrate_state_v1_4_0.py` |

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

Set `vault.default_path` in `config.json` so tools read your vault, not the repo's demo wiki.

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
llmwiki serve --dir /path/to/your-vault/site
```

One-shot:

```bash
llmwiki all --with-synth --graph-engine builtin
```

Useful flags:

- `--vault PATH` — override `config.json` default for one run (`sync` / `build` / `synthesize` / `add` / `queue` / `all`)
- `--adapter <name>` — limit sync to one source
- `--force` — re-convert / re-synthesize even if unchanged
- `--force-resync` (`sync`) — override the newer-schema / corrupt-state guard (#29) and reconvert from scratch; implies `--force`
- `llmwiki serve --dir PATH` — serve a built `site/` (no `--vault` on serve)
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
llmwiki init [--vault PATH]
llmwiki sync [--adapter NAME] [--vault PATH] [--force] [--force-resync] [--status]
llmwiki add <url|file|folder>... [--vault PATH] [--no-synthesize] [--no-build]
llmwiki build [--vault PATH] [--out PATH]
llmwiki serve [--dir PATH] [--port N]          # serve a built site/; no --vault
llmwiki synthesize [--vault PATH] [--check] [--estimate] [--force]
llmwiki consolidate-topics [--complete reply.json] [--vault PATH]
llmwiki queue {status|enqueue|run} [--vault PATH] [--state-file PATH]
llmwiki migrate-state [--state-file PATH]
llmwiki migrate-raw-redaction --vault PATH [--dry-run]  # #56: USER-mask encoded paths in raw/
llmwiki graph [--engine builtin|graphify]
llmwiki lint [--wiki-dir PATH]
llmwiki export all
llmwiki all [--with-synth] [--vault PATH]
llmwiki adapters [--wide]
llmwiki version
```

Shell shortcuts: `./sync.sh`, `./build.sh`, `./serve.sh`. Full flag tables: [docs/reference/cli.md](docs/reference/cli.md).

## Adding documents

`llmwiki add` drops any URL, file, or folder into the wiki:

```bash
llmwiki add https://blog.example.com/post ./notes.md ./research-folder
llm-wiki-add https://docs.example.com/guide   # same thing, shorter
```

**Install (from the clone root)** — an editable install generates the `llmwiki` and `llm-wiki-add` console scripts and pulls the conversion extras (trafilatura + markitdown with its PDF/DOCX/PPTX/XLSX backends):

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[add]'
```

To call them from **any terminal and any folder**, put the scripts on PATH — either add `.venv/bin` to PATH, or drop two-line wrappers into `~/.local/bin`:

```bash
printf '#!/usr/bin/env bash\nexec %s "$@"\n' "$PWD/.venv/bin/llm-wiki-add" \
  > ~/.local/bin/llm-wiki-add && chmod +x ~/.local/bin/llm-wiki-add
```

With `vault.default_path` set in `config.json`, documents land in your vault no matter where you run the command from.

URLs are fetched with `Accept: text/markdown` first — sites behind Cloudflare's [Markdown for Agents](https://developers.cloudflare.com/fundamentals/reference/markdown-for-agents/) return ready-made Markdown. HTML pages are extracted with [trafilatura](https://trafilatura.readthedocs.io/) when installed (the `[add]` extra above) and a stdlib converter otherwise. JavaScript-rendered pages escalate to a headless browser when playwright is available (`.venv/bin/pip install -e '.[e2e]' && .venv/bin/playwright install chromium`).

Documents land under `raw/docs/<slug>/`, split at section boundaries into ~7k-char chunks. The separation is deliberate: each chunk becomes one synthesis input that fits the model's context window, so one huge page can't overload or OOM a synthesis pass — splits happen at `#`/`##` headings (never mid-sentence, not a hard 7000-char slice). After writing, one synthesis pass and one site build run for the whole batch (`--no-synthesize` / `--no-build` to skip). `raw/` stays immutable: re-adding a document never overwrites — the slug gets a `-2`, `-3`, … suffix.

**Synthesis is synchronous and uses the one backend configured for the whole repository** (`synthesis.backend` in `config.json`: `claude` for `claude -p` CLI calls, default `claude_model=sonnet`; `ollama` for a local server; `dummy` offline — change it there any time). `add` synthesizes **only the documents it just wrote** (not the whole unsynthesized backlog). If the backend can't produce the wiki page in the same run, `add` **rolls the raw doc back** and exits non-zero — no half-added documents that nothing on the machine would ever synthesize later. `--no-synthesize` is the explicit opt-out that keeps raw-only docs.

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
| Documentation hub | [docs/index.md](docs/index.md) |
| End-to-end setup guide | [docs/tutorials/setup-guide.md](docs/tutorials/setup-guide.md) |
| Install + first build | [docs/getting-started.md](docs/getting-started.md), [docs/tutorials/01-installation.md](docs/tutorials/01-installation.md) |
| External vault setup | [docs/guides/existing-vault.md](docs/guides/existing-vault.md) |
| Claude Code workflow | [docs/tutorials/03-use-with-claude-code.md](docs/tutorials/03-use-with-claude-code.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Full CLI | [docs/reference/cli.md](docs/reference/cli.md) |
| Upgrade / state migration | [docs/UPGRADING.md](docs/UPGRADING.md) |
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

[MIT](LICENSE) © Alexander Makarov; based on upstream [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki)
