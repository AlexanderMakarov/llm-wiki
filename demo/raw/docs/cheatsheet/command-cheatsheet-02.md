---
title: "Command cheatsheet (part 2/2: Adapters)"
slug: command-cheatsheet-02
project: cheatsheet
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/cheatsheet.md"
content_sha256: e6ca298f4ad85f23bafd0499940f3b1e08825b0d0b77066af98d7d09137a327f
---

> Part 2 of 2 of **Command cheatsheet** — Adapters.

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
| `cursor` | Cursor IDE workspaceStorage (limited — #2) |
| `cursor_cli` | `~/.cursor/chats/` (Agent CLI) |
| `gemini_cli` | `~/.gemini/` |
| `obsidian` | Obsidian vault `.md` files (notes intake) |
| `opencode` | OpenCode / OpenClaw app-config sessions |
| `openclaw` | `~/.openclaw/agents/` |

Support map + headless rules: [multi-agent-setup.md](multi-agent-setup.md).

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
| `--since YYYY-MM-DD` | `sync` | One-run lookback (overrides `filters.since` / `adapters.*.since`) |
| `--project <slug>` | `sync` | Restrict to one project |
| `--force` | `sync`, `synth` | Ignore state file, reconvert / re-synth everything |
| `--force-resync` | `sync` | Override the newer-schema/corrupt-state guard (#29); implies `--force`, may duplicate `raw/` |
| `--fail-on-errors` | `lint` | Non-zero exit on error-severity issues |
| `--fail-on-warnings` | `lint` | Non-zero exit on warning-severity issues; pass both flags to gate on either |
| `--min-refs N` | `lint`, `synth`, `all` | How many distinct source pages must name a `[[wikilink]]` target before it earns a candidate page — and before an unresolved link to it is a finding (default: `3`) |
| `--no-sync`, `--no-synth` | `all` | Drop a stage from the run; `--no-synth` makes it LLM-free |
| `--lint-fail {never,errors,warnings}` | `all`, `install-automation` | Which quality findings end the run with exit `2` (default: `never`) |
| `--job {ingest,maintain}` | `install-automation` | What the daily job does — collect only, or also summarise |
| `--schedule "<cron>"` | `install-automation` | When the daily job runs, e.g. `"0 8 * * 1-5"` |
| `--vault <path>` | `sync`, `build`, `synth`, `lint`, `add`, `queue`, `all`, `migrate` | Operate on an external vault (also sets the active state file) |
| `--local-root <path>` | `build` | Value shown in place of a session's stored home directory (default: this machine's home) |
| `--engine graphify` | `graph` | AI-powered knowledge graph |
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
| `filters` | `since` | unset | Shared sync lookback (`YYYY-MM-DD`); omit = unlimited; see [configuration-reference.md](configuration-reference.md#sync-lookback) |
| `adapters.<name>` | `since` | unset | Per-source lookback (`YYYY-MM-DD` or `"all"`); omit = inherit shared |
| `truncation` | `tool_result_chars` | `500` | Max chars for tool results in output |

## Three-layer architecture

```
raw/     IMMUTABLE transcripts (source of truth, never modify)
wiki/    LLM-generated pages (you own this)
  sources/      one summary per raw source
  entities/     people, products, tools (TitleCase.md)
  concepts/     ideas, patterns, decisions (TitleCase.md)
  projects/     codebases and work streams (kebab-case slug)
  syntheses/    saved query answers
site/    GENERATED static HTML (don't edit by hand)
```

## Common recipes

```bash
# Daily, hands-off: schedule the whole loop
llmwiki install-automation --yes --job maintain --schedule "0 8 * * 1-5"

# Daily, by hand: the same loop as one run, then open site/index.html
llmwiki all

# Nightly cron (one project)
llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)

# AI knowledge graph
pip install llm-wiki-plus[graph]
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
