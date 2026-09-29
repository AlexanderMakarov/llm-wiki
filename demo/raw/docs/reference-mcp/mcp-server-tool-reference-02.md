---
title: "MCP server — tool reference (part 2/2: Tool timeouts)"
slug: mcp-server-tool-reference-02
project: reference-mcp
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/mcp.md"
content_sha256: 78152500878de5c9290a49b276c854f20d2776ba621325ab7f77f2fe00e1fcd2
---

> Part 2 of 2 of **MCP server — tool reference** — Tool timeouts.

## Tool timeouts

Long-running MCP tools share one config section:

```json
{
  "mcp": {
    "tool_timeouts": {
      "wiki_add": 120,
      "wiki_sync": 120
    }
  }
}
```

| Key | Default | Applies to |
|---|---|---|
| `mcp.tool_timeouts.wiki_add` | `120` | `wiki_add` (convert + optional synth + site build) |
| `mcp.tool_timeouts.wiki_sync` | `120` | `wiki_sync` subprocess |

Missing or invalid values fall back to 120. For latency-sensitive add callers that do not need an immediate site refresh, pass `no_build: true`.


## Migration from retired tools (#196)

| Retired tool | Use instead |
|---|---|
| `wiki_query` | `wiki_search` with `mode=extract` or `question` |
| `wiki_list_sources` | `wiki_search` with `mode=match`, `list_sources=true` |
| `wiki_confidence` | `wiki_search` with `mode=filter`, `filter_by=confidence` |
| `wiki_lifecycle` | `wiki_search` with `mode=filter`, `filter_by=lifecycle` |
| `wiki_category_browse` | `wiki_search` with `mode=filter`, `filter_by=tag` |
| `wiki_lint` | `wiki_health` |
| `wiki_dashboard` | `wiki_health` (`totals` field) |
| `wiki_entity_search` (removed in 2.0) | `wiki_search` with `mode=match` and optional `kind` |

There are **no alias stubs** — calling a retired name returns an unknown-tool error. Historical telemetry rows keep the logged tool name; aggregation folds retired names into the canonical six-tool surface (see [`cli.md`](cli.md#usage--mcp-tool-usage-telemetry-vs-synthesis-cost-26)).
