---
title: "MCP Server"
type: concept
status: candidate
tags: []
sources: [2026-09-08-configuration-reference-01, 2026-09-08-configuration-reference-07, 2026-09-08-configuration-02, 2026-08-16-mcp-server-tools, 2026-08-16-mcp-server-tools, 2026-09-08-cli-reference-03, 2026-09-08-state-persistence, 2026-09-08-synthesis-cost-what-you-pay-per-page-and-why-01, 2026-09-08-synthesis-cost-what-you-pay-per-page-and-why-02, 2026-09-08-ui-reference-05, 2026-09-08-upgrade-guide-01, 2026-09-08-upgrade-guide-02]
last_updated: 2026-09-08
---

# MCP Server

MCP exposure is part of the product surface area usually covered alongside CLI in reference material.

## Key Facts

- No MCP-specific options appear in this part’s body. [[2026-09-08-configuration-reference-01]]
- JSON output always includes `disabled_rules` (empty when undeclared) and `ran` for checks that actually executed. [[2026-09-08-configuration-reference-07]]
- Tool vocabulary schema unified to a single constant to prevent divergence [[2026-08-16-mcp-server-tools]]
- Implements search, read-page, and query tools for wiki access [[2026-08-16-mcp-server-tools]]
- Page kinds vocabulary is unified in a single constant [[2026-08-16-mcp-server-tools]]
- Telemetry records include `tool`, `query`, `hits`, `resp_bytes`, `duration_ms`, and caller fields without blocking tool execution. [[2026-09-08-cli-reference-03]]
- MCP logging is append-only and isolated per PID/start file to avoid write contention. [[2026-09-08-state-persistence]]
- The documented live surface is six tools, with legacy names merged in aggregation. [[2026-09-08-ui-reference-05]]
- `wiki_lint` → `wiki_health`; query/list/confidence-style tools → `wiki_search` with `question`, `list_sources`, or `mode=filter`. [[2026-09-08-upgrade-guide-01]]

## Connections

Named by 12 source page(s), which is the evidence that
justified this candidate:

- [[2026-09-08-configuration-reference-01]]
- [[2026-09-08-configuration-reference-07]]
- [[2026-09-08-configuration-02]]
- [[2026-08-16-mcp-server-tools]]
- [[2026-08-16-mcp-server-tools]]
- [[2026-09-08-cli-reference-03]]
- [[2026-09-08-state-persistence]]
- [[2026-09-08-synthesis-cost-what-you-pay-per-page-and-why-01]]
- [[2026-09-08-synthesis-cost-what-you-pay-per-page-and-why-02]]
- [[2026-09-08-ui-reference-05]]
- [[2026-09-08-upgrade-guide-01]]
- [[2026-09-08-upgrade-guide-02]]
