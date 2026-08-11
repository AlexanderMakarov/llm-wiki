---
title: "Command cheatsheet (part 2/2: All configurable settings (sessions_config.json))"
slug: command-cheatsheet-02
project: command-cheatsheet
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/cheatsheet.md"
content_sha256: 2168a9b67d566f2f5b0f51a1fe92e58499d300f8d3d83dfdc71469582abfee80
---

> Part 2 of 2 of **Command cheatsheet** — All configurable settings (sessions_config.json).

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
  entities/     people, products, tools (TitleCase.md)
  concepts/     ideas, patterns, decisions (TitleCase.md)
  projects/     codebases and work streams (kebab-case slug)
  syntheses/    saved query answers
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
