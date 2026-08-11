---
title: "Configuration Reference (part 3/4)"
slug: configuration-reference-03
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/configuration-reference.md"
content_sha256: 7cc907826ce49fb66b474eaa7bcf6d0d7266d2ba89c92ce2acdfe2a0f97b84f5
---

> Part 3 of 4 of **Configuration Reference**.

| Section | Key | Type | Default | Description |
|---|---|---|---|---|
| `filters` | `live_session_minutes` | int | 60 | Skip sessions younger than this (prevents reading mid-write) |
| `filters` | `include_projects` | list | [] | If non-empty, only sync matching project slugs |
| `filters` | `exclude_projects` | list | [] | Skip projects containing these substrings |
| `filters` | `drop_record_types` | list | [3 types] | JSONL record types to discard |
| `filters` | `exclude_headless` | bool | true | Skip headless `claude -p` / Agent-SDK sessions (`entrypoint=sdk-cli` or `promptSource=sdk`). Prevents the synthesis feedback loop. Applies at **both** ingest (never converted) and synthesis (a headless session already in `raw/` is never synthesized and never counted as backlog) |
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
| `adapters` | per-adapter | object | varies | Override adapter-specific settings |
| `schedule` | `build` | enum | `"on-sync"` | When `/wiki-build` runs. `on-sync` / `daily` / `weekly` / `manual` / `never`. |
| `schedule` | `lint` | enum | `"manual"` | When `/wiki-lint` runs. Same enum. |
| `synthesis` | `backend` | enum | `"dummy"` | Which synthesizer: `"dummy"` / `"ollama"` / `"claude"` (synchronous `claude -p` CLI). Unknown values warn and fall back to `"dummy"`. The old `"agent"` / agent-delegate backend was removed in v1.4.0. See [configuration.md § Synthesis backend](configuration.md#synthesis-backend). |
| `synthesis` | `claude_model` | string | `"sonnet"` | Model alias for the `claude` backend |
| `synthesis` | `claude_path` | string | `""` | Optional path to the `claude` binary |
| `synthesis` | `claude_timeout` | int (s) | 180 | Per-page timeout for the `claude` backend. Separate from `synthesis.ollama.timeout` — before v1.4.1 both backends shared one `timeout` key, so the Ollama default silently capped claude pages at 60s |
| `synthesis` | `claude_effort` | enum | unset | `--effort` for the `claude` backend (`low`/`medium`/`high`/`xhigh`/`max`). Extended thinking is billed as output at ~5x input; on Haiku it was 5,753 output tokens/page at the default vs 1,609 at `low`. Set `low` on small models |
| `synthesis` | `overview_model` | string | `"haiku"` | Model for the landing-page overview call in `build --synthesize`. Prose-from-JSON, so the small model is the default. See [reference/synthesis-cost.md](reference/synthesis-cost.md) |
| `synthesis` | `concurrency` | int | 2 | How many source pages `synth` synthesizes at once (range 1–16; `1` is strictly sequential). Bounds concurrent backend calls — for the `claude` backend that is concurrent subprocesses, which is why the ceiling exists. Unusable or out-of-range values warn and fall back to the default (out-of-range clamps to 16); a missing key is silent. `llmwiki synth --concurrency N` overrides it for one run |
| `synthesis` | `claude_lean` | bool | true | Strip agent scaffolding (tool schemas, MCP servers, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured. Only an explicit `false` opts out. See [reference/synthesis-cost.md](reference/synthesis-cost.md) |
| `synthesis.ollama` | `model` | string | `"llama3.1:8b"` | Ollama model name (pull via `ollama pull`). This nested block is canonical; the legacy flat `synthesis.model` / `timeout` / … still work but share a namespace with the other backends |
| `synthesis.ollama` | `base_url` | string | `"http://127.0.0.1:11434"` | Ollama HTTP endpoint |
| `synthesis.ollama` | `timeout` | int (s) | 60 | Per-request timeout |
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
| `chatgpt` | `enabled` | bool | false | Opt-in; requires explicit `conversations_json` |
| `chatgpt` | `conversations_json` | string | — | Path to export file |
| `web_clipper` | `enabled` | bool | false | Obsidian Web Clipper intake path |
| `web_clipper` | `watch_dir` | string | `"raw/web"` | Directory to watch |
| `web_clipper` | `extensions` | list | `[".md"]` | File extensions to pick up |
| `web_clipper` | `auto_queue` | bool | true | Auto-enqueue into unified `llmwiki-state.json` queue |
| `site` | `github_repo` | string | `""` | Optional `owner/name` for CHANGELOG / edit-on-GitHub / source-code links in compiled docs. Empty = detect from `git remote get-url origin`, else `Pratiyush/llm-wiki` |
