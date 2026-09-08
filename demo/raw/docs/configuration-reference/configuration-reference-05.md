---
title: "Configuration Reference (part 5/8)"
slug: configuration-reference-05
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 5 of 8 of **Configuration Reference**.

| Section | Key | Type | Default | Description |
|---|---|---|---|---|
| `filters` | `live_session_minutes` | int | 60 | Skip sessions younger than this (prevents reading mid-write) |
| `filters` | `include_projects` | list | [] | If non-empty, only sync matching project slugs |
| `filters` | `exclude_projects` | list | [] | Skip projects containing these substrings |
| `filters` | `drop_record_types` | list | [3 types] | JSONL record types to discard |
| `filters` | `since` | string | unset (unlimited) | Shared sync lookback as absolute `YYYY-MM-DD`. Absent or empty = no shared date gate. Overridden per run by CLI `--since`. See [Sync lookback](#sync-lookback) |
| `filters` | `exclude_headless` | bool | true | Skip automated / headless launches across coding-agent adapters (Claude SDK markers; Cursor Agent CLI `subagentInfo` / `approvalMode=auto-review`; OpenClaw never skipped; others false until markers exist). Prevents the synthesis feedback loop. Applies at **both** ingest and synthesis. See [multi-agent-setup.md](multi-agent-setup.md#what-automated-headless-means) |
| `filters` | `exclude_temp_cwd` | bool | false | Opt-in: skip sessions whose `cwd` is a throwaway temp dir (`/tmp`, `/var/folders`, …). Off by default — a git worktree under `/tmp` is often real work |
| `redaction` | `real_username` | string | `$USER` | Your OS username (auto-detected if empty) |
| `redaction` | `replacement_username` | string | `USER` | Replacement in path redaction |
| `redaction` | `extra_patterns` | list | [3 regexes] | Additional Python regex patterns to redact |
| `truncation` | `tool_result_chars` | int | 500 | Max chars per tool result |
| `truncation` | `bash_stdout_lines` | int | 5 | Max lines from bash output |
| `truncation` | `write_content_preview_lines` | int | 5 | Max lines from Write tool preview |
| `truncation` | `user_prompt_chars` | int | 4000 | Max chars per user prompt |
| `truncation` | `assistant_text_chars` | int | 8000 | Max chars of assistant text |
| root | `drop_thinking_blocks` | bool | true | Drop `<thinking>` blocks from output |
| `adapters` | per-adapter | object | varies | Override adapter-specific settings (`roots`, `enabled`, optional `since`, plus adapter-specific fields) |
| `adapters.<name>` | `since` | string | unset (inherit) | Per-source lookback: `YYYY-MM-DD` override, or `"all"` for no date gate on that source. Omit the key to inherit `filters.since`. See [Sync lookback](#sync-lookback) |
| `schedule` | `build` | enum | `"on-sync"` | When `/wiki-build` runs. `on-sync` / `daily` / `weekly` / `manual` / `never`. |
| `schedule` | `lint` | enum | `"manual"` | When `/wiki-lint` runs. Same enum. |
| `synthesis` | `backend` | enum | `"dummy"` | Which synthesizer: `"dummy"` / `"ollama"` / `"claude"` (synchronous `claude -p`) / `"cursor_cli"` (Cursor Agent CLI `agent -p`, #230). Unknown values warn and fall back to `"dummy"`. The old `"agent"` / agent-delegate backend was removed in v1.4.0. One-run override: `llmwiki synth --backend <name>` (does not write config). Distinct from the `cursor_cli` / `cursor_ide` *ingest* adapters. See [configuration.md § Synthesis backend](configuration.md#synthesis-backend). |
| `synthesis` | `overview_model` | string | `"haiku"` | Model for the landing-page overview call in `build --synthesize` when the active backend is Claude. Prose-from-JSON, so the small model is the default. Overview follows the active synthesis backend (#230): `cursor_cli` / `ollama` use that engine; `dummy` or unavailable skips the LLM. See [reference/synthesis-cost.md](reference/synthesis-cost.md) |
| `synthesis` | `concurrency` | int | 2 | How many source pages `synth` synthesizes at once (range 1–16; `1` is strictly sequential). Bounds concurrent backend calls — for CLI backends that is concurrent subprocesses, which is why the ceiling exists. Unusable or out-of-range values warn and fall back to the default (out-of-range clamps to 16); a missing key is silent. `llmwiki synth --concurrency N` overrides it for one run |
| `synthesis.claude` | `model` (alias `claude_model`) | string | `"sonnet"` | Claude model id / alias. Nested `synthesis.claude.model` wins over flat `synthesis.claude_model`. |
| `synthesis.claude` | `path` (alias `claude_path`) | string | `""` | Path to the `claude` binary (overrides `$PATH`). Nested wins over flat. |
| `synthesis.claude` | `timeout` (alias `claude_timeout`) | int (s) | 180 | Per-page timeout for Claude. Nested wins over flat. Separate from `synthesis.ollama.timeout` — before v1.4.1 both backends shared one `timeout` key, so the Ollama default silently capped Claude pages at 60s. |
| `synthesis.claude` | `lean` (alias `claude_lean`) | bool | true | Strip agent scaffolding (tool schemas, MCP, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured. Nested wins over flat. Only an explicit `false` opts out. See [reference/synthesis-cost.md](reference/synthesis-cost.md). |
| `synthesis.claude` | `effort` (alias `claude_effort`) | enum | unset | `--effort` for Claude (`low`/`medium`/`high`/`xhigh`/`max`). Nested wins over flat. Extended thinking is billed as output at ~5x input; on Haiku it was 5,753 output tokens/page at the default vs 1,609 at `low`. Set `low` on small models. |
| `synthesis.cursor_cli` | `model` | string | `"composer-2.5"` | Cursor Agent CLI `--model` id (#230). Cheapest Composer id Agent CLI lists; pricing aliases in `model_pricing.csv` include `composer` and Grok effort/fast variants from [Cursor models & pricing](https://cursor.com/docs/models-and-pricing). |
| `synthesis.cursor_cli` | `timeout` | int (s) | 180 | Per-page timeout for the `cursor_cli` backend. No user-facing binary-path key — resolves `agent` then `cursor-agent` from `$PATH`. |
| `synthesis.ollama` | `model` (legacy flat `synthesis.model`) | string | `"llama3.1:8b"` | Ollama model name (pull via `ollama pull`). Nested `synthesis.ollama` is canonical; legacy flat `synthesis.model` / `timeout` / … still work but share a namespace with the other backends. |
| `synthesis.ollama` | `base_url` | string | `"http://127.0.0.1:11434"` | Ollama HTTP endpoint |
| `synthesis.ollama` | `timeout` (legacy flat `synthesis.timeout`) | int (s) | 60 | Per-request timeout |
| `synthesis.ollama` | `max_retries` | int | 3 | Exponential-backoff retry count on 5xx / timeout |
| `meeting` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `meeting` | `source_dirs` | list | `["~/Meetings"]` | Directories to scan |
| `meeting` | `extensions` | list | `[".vtt", ".srt"]` | File extensions to consider |
| `jira` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `jira` | `server` | string | — | Jira Cloud/Server URL |
| `jira` | `email` | string | — | Account email |
| `jira` | `api_token` | string | `""` | Prefer `api_token_env` + `.env` |
| `jira` | `jql` | string | sensible default | Query for tickets to sync |
| `jira` | `max_results` | int | 50 | Pagination cap |
| `chatgpt` | `enabled` | bool
