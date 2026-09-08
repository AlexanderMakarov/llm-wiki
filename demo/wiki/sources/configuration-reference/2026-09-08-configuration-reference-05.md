---
title: "Configuration Reference (part 5/8)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration-reference]
date: 2026-09-08
source_file: 
project: configuration-reference
model: 
last_updated: 2026-09-08
---
Checking how other configuration-reference parts are summarized in the wiki for consistency.
<!-- suggested-tags: sessions-config, sync-filters, synthesis-backend, path-redaction, headless-exclusion -->

## Summary

Part 5 of the Configuration Reference documents `sessions_config.json` (and related) keys from **`filters`** through the start of optional ingest adapters: sync filtering and lookback, path redaction, transcript truncation, per-adapter overrides, scheduled build/lint, and the **`synthesis`** block (backend choice, concurrency, and nested settings for Claude, Cursor Agent CLI, and Ollama). It explains defaults such as **`exclude_headless: true`** (to break synthesis feedback loops), **`synthesis.backend: "dummy"`**, Claude **`lean: true`** for roughly ninefold lower synthesis cost, and that the legacy **`"agent"`** delegate backend was removed in v1.4.0.

## Key Claims

- **`filters.live_session_minutes`** (default 60) skips sessions newer than that window so sync does not read mid-write JSONL.
- **`filters.since`** is a shared sync lookback as `YYYY-MM-DD`; empty means no shared date gate; CLI **`--since`** overrides per run; **`adapters.<name>.since`** can inherit, override with a date, or use **`"all"`** for no gate on that source.
- **`filters.exclude_headless`** defaults to **true** and applies at both ingest and synthesis for coding-agent adapters (Claude SDK markers, Cursor Agent CLI `subagentInfo` / `approvalMode=auto-review`); OpenClaw is never skipped; the intent is to prevent automated synthesis feedback loops.
- **`filters.exclude_temp_cwd`** defaults to **false** because real work (e.g. git worktrees) often lives under `/tmp`-style paths.
- **`synthesis.backend`** accepts **`dummy`**, **`ollama`**, **`claude`** (sync `claude -p`), or **`cursor_cli`** (`agent -p`, #230); unknown values warn and fall back to **`dummy`**; one-run override via **`llmwiki synth --backend`** without writing config.
- **`synthesis.claude.lean`** defaults to **true** and strips agent scaffolding (tool schemas, MCP, skills, `CLAUDE.md`, system prompt) from each Claude synthesis call, described as ~9× cheaper per page; only explicit **`false`** opts out.
- Before v1.4.1, Claude and Ollama shared a single **`timeout`** key, which silently capped Claude pages at Ollama’s 60s default; nested **`synthesis.claude.timeout`** and **`synthesis.ollama.timeout`** are now separate (defaults 180s and 60s).
- **`meeting`** and **`jira`** adapters are opt-in (**`enabled: false`** by default); **`chatgpt`** appears in the same optional-adapter section (table truncated in this part).

## Key Quotes

> "Skip automated / headless launches across coding-agent adapters … Prevents the synthesis feedback loop. Applies at **both** ingest and synthesis." — rationale for default **`exclude_headless: true`**

> "Strip agent scaffolding (tool schemas, MCP, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured." — documentation for **`synthesis.claude.lean`**

> "The old `"agent"` / agent-delegate backend was removed in v1.4.0." — synthesis backend enum change

## Connections

- [[llmwiki]] (entity) — documents runtime configuration for sync, redaction, truncation, synthesis, and optional non-AI adapters.
  - fact: Default synthesis backend is **`dummy`**; production paths use **`claude`**, **`cursor_cli`**, or **`ollama`** with documented nested keys.
- [[Adapters]] (concept) — **`adapters.<name>`** overrides roots, **`enabled`**, optional **`since`**, and adapter-specific fields; meeting/Jira/ChatGPT are opt-in ingest sources.
  - fact: Per-adapter **`since`** inherits **`filters.since`** unless set to a date or **`"all"`**.
- [[Wiki Synthesis]] (concept) — **`synthesis.*`** controls backend, **`concurrency`** (1–16, default 2), **`overview_model`** for **`build --synthesize`**, and backend-specific model/timeouts.
  - fact: **`llmwiki synth --concurrency N`** and **`--backend`** override config for a single run without persisting changes.
- [[Ollama]] (entity) — **`synthesis.ollama`** sets model (default **`llama3.1:8b`**), **`base_url`**, timeout, and **`max_retries`** with exponential backoff on 5xx/timeout.
- [[Cursor]] (entity) — **`synthesis.cursor_cli`** backend (distinct from **`cursor_cli`** / **`cursor_ide`** ingest adapters) defaults model **`composer-2.5`** and 180s timeout; resolves **`agent`** then **`cursor-agent`** on **`$PATH`**.
- [[Claude Code]] (entity) — headless detection uses Claude SDK markers when **`exclude_headless`** is true; lean synthesis omits **`CLAUDE.md`** and related scaffolding from Claude **`claude -p`** calls.
