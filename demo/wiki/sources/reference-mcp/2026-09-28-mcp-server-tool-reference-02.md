---
title: "MCP server — tool reference (part 2/2: Tool timeouts)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-mcp, tool-timeouts, tool-deprecation, mcp-configuration]
date: 2026-09-28
source_file: 
project: reference-mcp
model: 
last_updated: 2026-09-28
---
## Summary
Reference documentation for MCP server tool configuration, covering timeout settings for long-running tools (`wiki_add`, `wiki_sync`) and the migration path from eight deprecated query/browse/lint tools to six consolidated replacements. Notes that no backwards-compatibility stubs are provided; calling a retired tool name returns an unknown-tool error.

## Key Claims
- `wiki_add` and `wiki_sync` tools support 120-second timeout defaults via `mcp.tool_timeouts` configuration
- The `no_build: true` parameter on `wiki_add` skips site refresh for latency-sensitive callers
- Eight tools (`wiki_query`, `wiki_list_sources`, `wiki_confidence`, `wiki_lifecycle`, `wiki_category_browse`, `wiki_lint`, `wiki_dashboard`, `wiki_entity_search`) were retired with no alias stubs
- Calling a retired tool name returns an unknown-tool error instead of routing to a replacement
- `wiki_search` with mode and filter parameters consolidated four query/browse tools; `wiki_health` replaced lint/dashboard
- Retired tool names are preserved in historical telemetry rows but aggregated to six canonical tools during reporting

## Key Quotes
> "Missing or invalid values fall back to 120." — timeout configuration has sensible defaults
> "For latency-sensitive add callers that do not need an immediate site refresh, pass `no_build: true`." — optimization path for performance-critical clients
> "There are **no alias stubs** — calling a retired name returns an unknown-tool error." — breaking change with no backwards compatibility

## Connections
- [[MCP Server]] (entity) — the service exposing these tools
  - fact: Configures timeout behavior for long-running operations
  - fact: Consolidated eight tools into six with breaking API changes
- [[Wiki Synthesis]] (concept) — optional step triggered by `wiki_add` tool
  - fact: Can be skipped via `no_build: true` for immediate-response use cases