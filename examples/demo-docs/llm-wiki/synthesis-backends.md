---
title: "Synthesis backends"
slug: synthesis-backends
project: llm-wiki
type: source
tags: [raw-doc, demo, llmwiki, synthesis]
date: 2026-07-29
source: examples/demo-docs/llm-wiki/synthesis-backends.md
---

# Synthesis backends

`synthesis.backend` in `config.json` (overlaying `examples/sessions_config.json`) selects how `wiki/sources/` pages are filled:

| Backend | When to use |
|---|---|
| `dummy` | Offline CI / scaffolding — stub pages only |
| `ollama` | Local models, no cloud |
| `claude` | Claude Code CLI (`claude -p`) — default quality path for maintainers |

## Claude tips

- Prefer a cheap model for docs (`haiku`) and lean prompts (`claude_lean: true`).
- `llmwiki synthesize --docs-only` skips session backlog when you only added documents.
- `llmwiki synthesize --estimate` shows token/$ cost before a full run.
- `--vault <path>` isolates state so a demo staging vault does not share idempotency with your personal Obsidian vault.
