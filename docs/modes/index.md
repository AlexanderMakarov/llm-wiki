---
title: "Pick your mode"
type: navigation
docs_shell: true
---

# Pick your mode

llmwiki synthesis backends share the same three-layer pipeline
(`raw/` → `wiki/` → `site/`) but differ on *who calls the LLM*:

| | **Ollama** | **Claude CLI** | **Dummy** |
|---|---|---|---|
| **How synthesis runs** | Local HTTP (`ollama serve`) | `claude -p` CLI | Offline stubs |
| **API key needed** | No | No (Claude Code CLI / subscription) | No |
| **Best for** | Fully local / air-gapped | Daily agent workflow | Tests / dry previews |

## When to pick which

- **You use Claude Code daily:** set `synthesis.backend: claude` (see [Agent mode](agent/)).
- **You want fully local models:** set `synthesis.backend: ollama` — [Tutorial 08](../tutorials/08-synthesize-with-ollama.md).
- **You're evaluating offline:** leave `dummy` (default).

The old **agent-delegate** pending-prompt mode (`--list-pending` /
`--complete`) was removed in v1.4.0. Anthropic HTTP batch / API-mode
scaffolding was also removed — use `claude` or `ollama` instead.

## The backends share

Everything except synthesis:

- Adapters (`claude_code`, `codex_cli`, `cursor`, `gemini_cli`, `copilot_chat`, `obsidian`, …) work identically.
- The static site, graph viewer, lint rules — all backend-agnostic.
- `config.json` / `sessions_config.json` is the same file; only `synthesis.backend` differs.

## Read next

- [Claude CLI / agent workflow](agent/)
- [Configuration — synthesis backend](../configuration.md#synthesis-backend)
- [Upgrade guide](../UPGRADING.md)
