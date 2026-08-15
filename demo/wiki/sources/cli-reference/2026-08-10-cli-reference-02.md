---
title: "CLI reference (part 2/8: build — compile the static HTML site)"
type: source
tags: [wiki-add, raw-doc, session-transcript, cli-reference, mcp-telemetry, caller-attribution, search-indexing]
date: 2026-08-10
source_file: 
project: cli-reference
model: 
last_updated: 2026-08-11
---
## Summary

This documentation covers three main [[llmwiki]] CLI subcommands: `build` (compiles wiki markdown to HTML and seven AI-consumable exports), `serve` (a stdlib-based local HTTP server), and `usage` (aggregates [[MCP]] telemetry logs against synthesis costs). The bulk of the content details the [[MCP]] telemetry and caller attribution system, which logs tool calls per-process without write contention and automatically attributes calls across different clients—notably [[Claude Code]] via env var with zero config, and [[Cursor]] via path heuristics with known gaps.

## Key Claims

- The `build` command generates markdown-to-HTML conversion plus seven AI-consumable exports (llms.txt, llms-full.txt, sitemap.xml, rss.xml, robots.txt, graph.jsonld, ai-readme.md) in a single invocation.
- [[MCP]] telemetry is logged per-process to vault-relative files (`mcp-<pid>-<start>.jsonl`) to eliminate write contention and lock pressure across multiple concurrent server processes (one per editor session).
- [[Claude Code]] (v2.1.139+) automatically provides caller attribution via the `CLAUDE_PROJECT_DIR` environment variable with zero configuration; spawning one server per session makes this a stable per-caller signal.
- [[Cursor]] currently fails zero-config caller attribution because its `roots/list` [[MCP]] call returns `Method not found` and it injects no workspace env var, leaving calls attributed via path heuristics or marked unattributed.
- Unattributed [[MCP]] calls are included in global totals but excluded from per-project displays and the site's "Heaviest project by MCP usage" card.
- Daily call aggregates in `usage/daily.json` track per-day totals by category (retrievals, writes, session reads, etc.) and survive the `--compact` archival operation to support Analytics activity heatmaps.

## Key Quotes

> "The MCP server logs one JSON record per tool call to a **per-process** file under `<vault>/usage/` (`mcp-<pid>-<start>.jsonl`), merged at read time. Several server processes run at once (one per editor session), so per-process files mean zero write contention and no lock on the hot path; telemetry never touches `llmwiki-state.json`."

This explains the architectural choice to avoid a centralized telemetry bottleneck when multiple clients query the wiki simultaneously.

> "Claude Code sets `CLAUDE_PROJECT_DIR` (≥ v2.1.139) into every stdio MCP server — zero config — and spawns one server per session, so it is a stable per-caller signal available at the first call."

Highlights how one client was explicitly designed to enable automatic caller attribution without user setup.

> "The server's own `os.getcwd()` is never used: a client may launch the server anywhere (Claude Code's desktop app uses `$HOME`), so it is unrelated to the caller's project."

Explains why the [[MCP]] server's working directory cannot serve as caller context—clients control where the server starts, making environment-based signals necessary.

## Connections

- [[llmwiki]] — the system being documented; these are its core CLI commands
- [[Claude Code]] — IDE with native support for automatic caller attribution via env var injection
- [[Cursor]] — IDE mentioned as lacking zero-config attribution signal; currently relies on path heuristics or remains unattributed
- [[MCP]] — Message Passing Protocol; the telemetry, tool calls, and caller attribution infrastructure

## Contradictions

None identified.