---
title: "Configuration (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, configuration, config-json, redaction, session-filters, truncation-limits, adapter-config]
date: 2026-09-08
source_file: 
project: configuration
model: 
last_updated: 2026-09-08
---
## Summary

Part 1 of the Configuration guide documents how llmwiki loads local settings from a gitignored `config.json` (seeded from `examples/sessions_config.json`), the minimal redaction-only setup, and the top-level schema for `filters`, `redaction`, `truncation`, `drop_thinking_blocks`, and optional `adapters`. It explains why username redaction runs before `raw/` writes and how ingest filters (live sessions, project include/exclude, record types, headless runs, temp cwd) and truncation caps shape converted session markdown.

## Key Claims

- `config.json` is gitignored and auto-loaded by the converter when present; the documented minimum is a `redaction` block with `real_username` set to the output of `whoami` and `replacement_username` typically `USER`.
- `filters.live_session_minutes` (default 60) skips sessions with records newer than that window so `.jsonl` files are not read mid-write.
- `filters.exclude_headless` defaults to `true` and drops automated/headless agent launches (Claude SDK/promptSource, Cursor Agent CLI subagent/auto-review); OpenClaw is explicitly not skipped by this rule; the same filter applies at ingest and synthesis.
- `filters.exclude_temp_cwd` defaults to `false` so real work in git worktrees under `/tmp` is not silently dropped; enabling it is only for throwaway scratch/e2e temp dirs.
- Sync history can be bounded via optional top-level `since` (YYYY-MM-DD, #192), per-adapter `adapters.<name>.since` or `"all"`, with CLI `--since` overriding both for a single run (details deferred to configuration-reference).
- `redaction.extra_patterns` apply Python `re` regexes that replace matches with `<REDACTED>`, including bundled patterns for credential-like strings, `sk-…` keys, and email addresses.
- Truncation defaults cap tool results (500 chars), bash stdout (5 lines), write previews (5 lines), user prompts (4000 chars), and assistant text in the markdown body (8000 chars); `drop_thinking_blocks` defaults to `true`.

## Key Quotes

> "Replace `your-unix-username` with the output of `whoami`. The converter uses it to scrub paths like `/Users/<name>/…` or `/home/<name>/…` before writing to `raw/`." — establishes redaction as a pre-commit privacy gate for session export

> "Default OFF: a git worktree under /tmp is often real work, so we don't silently drop it." — rationale for `exclude_temp_cwd: false`

> "Skip automated / headless agent launches (default on)… Applies at ingest and synthesis." — headless filtering is a pipeline-wide policy, not sync-only

## Connections

- [[llmwiki]] (topic) — central subject: every tuning knob for sync/conversion behavior lives in `config.json`.
  - fact: Local config is gitignored and auto-loaded; defaults ship in `examples/sessions_config.json`.
- [[Adapters]] (topic) — optional `adapters` block documents per-source settings (example: Obsidian `vault_paths`, `exclude_folders`, `min_content_chars`) and per-adapter `since` overrides.
  - fact: Adapter-specific sync windows can override or disable the shared `since` gate with `"all"`.
- [[Claude Code]] (topic) — named in `exclude_headless` as sessions identifiable via SDK entrypoint / `promptSource`.
- [[Cursor]] (topic) — named in `exclude_headless` for Agent CLI via `subagentInfo` or `approvalMode=auto-review`.
- [[Wiki Synthesis]] (topic) — `exclude_headless` applies during synthesis as well as ingest, keeping headless noise out of downstream wiki passes.
