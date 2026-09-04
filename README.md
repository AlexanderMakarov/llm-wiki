# llmwiki

Your coding-agent sessions, compiled into a local wiki you can search, graph, and open as plain files.

[Live demo](https://alexandermakarov.github.io/llm-wiki/) · [Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![Version](https://img.shields.io/badge/version-v2.1.0-10B981.svg)](CHANGELOG.md)
[![CI](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/ci.yml)
[![Link check](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/link-check.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/link-check.yml)
[![Wiki checks](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/wiki-checks.yml/badge.svg?branch=main)](https://github.com/AlexanderMakarov/llm-wiki/actions/workflows/wiki-checks.yml)

llmwiki turns transcripts from Claude Code, Codex, Cursor, OpenClaw and others into redacted markdown, then builds a static site: session browser, topic graph, candidate review, MCP tools. Your data stays in a vault outside git. Nothing has to be running to read the site — open `site/index.html`.

## What you get

- **A searchable static site** — sessions, projects, topics, graph, analytics. Dark mode, Cmd+K search, syntax highlighting. Open the files; there is no server.
- **A knowledge layer** — `synth` writes source summaries and harvests entity/concept *candidates*. You review those on `/candidates.html` and apply decisions with `llmwiki candidates apply`. That review is a real gate, not an optional extra.
- **Exports agents can read** — `llms.txt`, `llms-full.txt`, JSON-LD, sitemap, RSS, plus an MCP server.
- **Your data never lands in git.** Transcripts, wiki pages and the built site live in a vault directory you choose. This repository is code plus a public [demo](demo/).

Page kinds and where each field comes from: [docs/reference/page-kinds.md](docs/reference/page-kinds.md). Every screen: [docs/reference/ui.md](docs/reference/ui.md).

## Install

Requires **Python ≥ 3.12** (CI runs 3.12 and 3.13). Runtime dependency is `markdown` only.

```bash
pip install llm-wiki
# or: brew install AlexanderMakarov/tap/llmwiki
llmwiki init --vault ~/llmwiki-vault
```

Point a gitignored `config.json` at the vault so later commands need no `--vault`:

```json
{
  "vault": { "default_path": "/home/USER/llmwiki-vault" }
}
```

From a clone, `./setup.sh` installs the package and reports which agents it can see. The clone itself is not a vault — bare `llmwiki init` / `sync` / `build` against this repository are refused; name `--vault` or `demo`.

**Agent commands** (slash commands and skills) ship inside the package. After install:

```bash
llmwiki install-agent-kit --dest ~/.claude
```

That is what a Homebrew or pip user runs so `/wiki-sync` and friends work from *their* project, not from this repository. See [docs/reference/cli.md](docs/reference/cli.md).

## The loop

```text
sync / add  →  synth  →  review candidates  →  build  →  open site/index.html
```

```bash
llmwiki sync                         # new transcripts → vault/raw/sessions/
llmwiki add notes.md                 # optional: drop a document into raw/docs/
llmwiki synth                        # source pages + harvest candidates
# open vault/site/candidates.html, set decisions, paste the printed command
llmwiki build                        # vault/wiki/ → vault/site/
```

`synth` does not rebuild the site. `build` does. `candidates apply` rebuilds after a successful batch so `/candidates.html` matches the wiki (`--no-rebuild` skips that). Candidate review is the human gate: a row starts with no decision, Apply assembles `llmwiki candidates apply --vault … --actions '…'`, and only that command writes the wiki.

One-shot: `llmwiki all --graph-engine builtin` runs the whole loop — sync → synth → build → graph → lint. Opt out of a stage with `--no-sync`, `--no-synth`, `--skip-graph`, or `--skip-lint`.

## Agents

One row per agent. **Supplies sessions** = `llmwiki sync` can read its transcript store. **Reads the wiki** = slash commands / MCP after `install-agent-kit` (any MCP client can also call `python3 -m llmwiki.mcp`). **Core** adapters run on a default `sync` when their store exists; **contrib** adapters need `--adapter <name>` or `adapters.<name>.enabled` in config.

| Agent | Supplies sessions | Reads the wiki | Core or contrib |
|---|---|---|---|
| Claude Code | `~/.claude/projects/*/*.jsonl` | slash commands, MCP | core (`claude_code`) |
| Codex CLI | `~/.codex/sessions/` | `AGENTS.md` workflow, MCP | core (`codex_cli`) |
| ChatGPT | contrib store | MCP | contrib (`chatgpt`) |
| Copilot Chat | VS Code workspaceStorage | MCP | contrib (`copilot_chat`) |
| Copilot CLI | `~/.copilot/session-state/` | MCP | contrib (`copilot_cli`) |
| Cursor IDE | workspaceStorage | MCP | contrib (`cursor`) |
| Cursor CLI | `~/.cursor/chats/` | MCP | contrib (`cursor_cli`) |
| Gemini CLI | `~/.gemini/` | MCP | contrib (`gemini_cli`) |
| Obsidian | markdown vault intake | wikilinks in the vault | contrib (`obsidian`) |
| OpenCode | shared OpenClaw schema | MCP | contrib (`opencode`) |
| OpenClaw | `~/.openclaw/agents/*/sessions/` | MCP | contrib (`openclaw`) |

```bash
llmwiki adapters --wide
llmwiki sync --adapter openclaw
```

## Configuration

Shipped defaults: [`examples/sessions_config.json`](examples/sessions_config.json). Personal overrides: gitignored `config.json` at the clone root, merged on top. Full keys: [docs/configuration.md](docs/configuration.md).

Skip projects or dates with a `.llmwikiignore` next to the vault (one path or glob per line).

## Documentation

| Topic | Link |
|---|---|
| Hub | [docs/index.md](docs/index.md) |
| Install + first vault | [docs/getting-started.md](docs/getting-started.md) |
| Page kinds | [docs/reference/page-kinds.md](docs/reference/page-kinds.md) |
| CLI | [docs/reference/cli.md](docs/reference/cli.md) |
| Site UI | [docs/reference/ui.md](docs/reference/ui.md) |
| Architecture | [docs/architecture.md](docs/architecture.md) |
| Upgrading | [docs/UPGRADING.md](docs/UPGRADING.md) |
| GitHub Pages | [docs/deploy/github-pages.md](docs/deploy/github-pages.md) |

This repository's `CLAUDE.md` and `AGENTS.md` are for people changing llmwiki itself. Vault workflows for users live in the installed agent kit.

## Acknowledgements

- [Andrej Karpathy](https://twitter.com/karpathy) — [LLM Wiki idea](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)
- [Pratiyush](https://github.com/Pratiyush/llm-wiki) — upstream this work extends

## License

[MIT](LICENSE) © Alexander Makarov; based on upstream [Pratiyush/llm-wiki](https://github.com/Pratiyush/llm-wiki)
