---
title: "Configuration (part 2/3: Synthesis backend)"
slug: configuration-02
project: configuration
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration.md"
content_sha256: 94ac6cbdc09d142adb44b67fe4e8fb1afc2956a82b7438f5476618e4ec72f3d8
---

> Part 2 of 3 of **Configuration** — Synthesis backend.

## Synthesis backend

`llmwiki synth` turns each raw session/document into a `wiki/sources/` page. Which LLM (if any) writes those pages is picked by `synthesis.backend` in `config.json`. Per-engine settings live in nested blocks (`synthesis.claude`, `synthesis.cursor_cli`, `synthesis.ollama`); legacy flat `claude_*` / Ollama keys still work as fallbacks. Override the backend for one run with `llmwiki synth --backend <name>` (does not write `config.json`).

```jsonc
{
  "synthesis": {
    // "dummy" (default) | "ollama" | "claude" | "cursor_cli"
    "backend": "cursor_cli",
    "cursor_cli": { "model": "composer-2.5", "timeout": 180 },
    "claude": { "model": "sonnet", "lean": true },
    "ollama": { "model": "llama3.1:8b" }
  }
}
```

| Backend | What it does | Needs |
|---|---|---|
| `dummy` | Canned stub page: metadata summary, one `[[ProjectEntity]]` link, plain-text `## Raw Mentions`. For previews/tests. | nothing |
| `ollama` | Local LLM over the Ollama HTTP API. Configure `synthesis.ollama.{model,base_url,timeout,max_retries}` (flat legacy keys still work). | running `ollama serve` |
| `claude` | Synchronous `claude -p` CLI calls (#16). Prefer nested `synthesis.claude.{model,path,timeout,lean,effort}`; flat `claude_*` keys remain as fallbacks. Default model `sonnet`. | `claude` on `$PATH` (or `synthesis.claude.path` / `claude_path`) |
| `cursor_cli` | Synchronous Cursor Agent CLI (`agent -p` / `cursor-agent`) (#230). Nested `synthesis.cursor_cli.{model,timeout}` only (default model `composer-2.5`). Binary from `$PATH` — no path key. Lean flags: `-p`, `--mode ask`, `--sandbox enabled`, `--allowed-tools truncated_tool_call` (shrinks tool schemas; still no empty system-prompt / empty-MCP switch). | `agent` or `cursor-agent` on `$PATH`, authenticated |

**Not the same as session ingest.** `synthesis.backend: cursor_cli` is the *generator* that writes wiki pages. The contrib adapters `cursor_cli` (Agent CLI chats under `~/.cursor/chats/`) and `cursor_ide` (IDE Composer / `state.vscdb`) only *ingest* transcripts into `raw/` — configuring one does not select the other.

Claude calls run in **lean mode** by default: tool schemas, MCP servers, skills, `CLAUDE.md`, and the agent system prompt are stripped from each invocation, since a synthesis call only reads stdout and can't use any of them. That is ~9x cheaper per page, measured — see [reference/synthesis-cost.md](reference/synthesis-cost.md) for the numbers and for why the Claude default model is `sonnet` rather than a cheaper model. Set `"lean": false` under `synthesis.claude` (or flat `"claude_lean": false`) to opt out. Cursor's lean set is ask + sandbox plus a tiny `--allowed-tools` allowlist (~25–30% less prompt than the full tool catalog on Composer); the agent system prompt still cannot be emptied for normal accounts.

The old `agent` / `agent_delegate` backend (pending-prompt files + `--list-pending` / `--complete`) was removed in v1.4.0 — use `claude` or `cursor_cli` instead.

Sanity-check what's active and what a run would cost:

```bash
llmwiki synth --check                    # prints the resolved backend + availability
llmwiki synth --estimate                 # cached-vs-fresh token + dollar estimate (+ candidate backlog)
llmwiki synth --backend cursor_cli --estimate   # one-run backend overlay (no config write)
llmwiki synth --sessions-only            # pending sessions only (skip docs)
llmwiki synth --docs-only                # pending docs only (skip sessions)
```

**Synthesis is incremental.** `<vault>/llmwiki-state.json` (`synth.files`) records an mtime per raw file; a nightly `sync`/`synthesize` only processes files that are new or changed since the last run — the daily LLM bill is proportional to new content, not to corpus size. `--force` re-runs everything (use after switching backends, e.g. to replace dummy-stub pages with real ones — pages with only stub links produce a topic graph with no edges).

**Downgrade protection:** `dummy` is the resolved default when `synthesis.backend` is unset (or a typo — unknown values warn and fall back), so a `--force` run in that state used to overwrite every real page with link-free stubs and silently empty the knowledge graph. The pipeline now refuses that downgrade: stub output is never written over a real page, even under `--force` — such pages are reported as `protected` in the run summary. To deliberately re-synthesize a real page, delete it first. (An unavailable backend does *not* fall back — the run aborts with an error.)

## Environment variables

| Variable | What it does |
|---|---|
| `LLMWIKI_CONFIG` | Override the config file path. Defaults to `./config.json` then `examples/sessions_config.json`. |

Vault content root is **`vault.default_path` in `config.json`** (not an env var). The removed `LLMWIKI_ROOT` env var is no longer read.
