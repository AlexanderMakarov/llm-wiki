---
title: "State persistence"
type: navigation
docs_shell: true
---

# State persistence

Where llmwiki keeps durable counters, telemetry, and pipeline state in a vault. These files live beside `raw/`, `wiki/`, and `site/` — they are not merged into one blob. Each has a single job.

---

## Vault files (by role)

| Path | Role | Written by | Read by |
|---|---|---|---|
| `usage/mcp-<pid>-<start>.jsonl` | Live, append-only MCP logs — one file per MCP server process, so concurrent editors never contend on a shared write lock. | MCP server (`wiki_*` tools), on every tool call | `llmwiki usage`, `llmwiki usage --compact`, `llmwiki build` (Analytics live overlay) |
| `usage/rollup.json` | Lifetime MCP totals after monthly compact — the kept-forever aggregate once raw JSONL for past months is folded and deleted. | `llmwiki usage --compact` | `llmwiki usage`, `llmwiki build` (`combined_totals` → Analytics MCP table / value cards) |
| `usage/daily.json` | Per-day MCP counts that survive compact — `mcp_calls`, `retrievals`, `writes`, `session_reads`, `doc_reads`, `by_tool`, attribution counters, and related fields. | Compact (fold) + `llmwiki build` (live overlay refresh) | `llmwiki build` (Analytics Activity heatmaps: MCP calls, session/doc reads) |
| `llmwiki-state.json` | Synth queue, sync mtimes, cost estimate, Home pipeline snapshot (`synth.pipeline`), quarantine — separate from `usage/`; MCP telemetry never writes here. | `sync`, `synth`, `queue`, `migrate state`, related CLI; `llmwiki build` (one-shot `synth.pipeline` backfill when the key is missing — #70) | Same CLI family; `llmwiki build` (optional synth cost line on Analytics; Home State widget via `llmwiki-state.js` sidecar); `migrate tools-used` (origin lookup via sync keys) |
| `raw/sessions/*.md` frontmatter | Session-side signal — `tools_used`, `tool_counts`, dates — used for wiki-adoption heatmaps and best-effort session/day counts alongside MCP logs. | `llmwiki sync` / convert; `migrate tools-used` (tools fields only) | `llmwiki build` (session pages, Agents Activity heatmap, wiki-using session days); `migrate tools-used` |

Nothing in this table replaces anything else. `llmwiki build` reads `combined_totals()` (rollup + live JSONL), `daily.json`, and session frontmatter together when it renders Analytics.

---

## Data flow

```
MCP tool call
    → append one JSON line to usage/mcp-<pid>-<start>.jsonl

llmwiki usage --compact  (or scheduled compact)
    → fold retiring JSONL into usage/rollup.json
    → fold per-day buckets into usage/daily.json (folded_days)
    → delete the compacted JSONL files

llmwiki build
    → combined_totals = rollup + live JSONL not yet folded
    → daily series = folded_days + live overlay (no double-count)
    → session frontmatter → wiki-adoption / session-day heatmaps
    → render Analytics from the merged view
```

**Append** happens on every MCP tool call (best-effort; failures never break the call). **Compact** is explicit — `llmwiki usage --compact` — and rolls whole past months into numeric summaries before deleting the source logs. **Build** refreshes the live overlay from non-folded JSONL on every run so heatmaps and tables stay current without waiting for compact.

`llmwiki-state.json` follows a different lifecycle: sync and synth update it; it does not participate in MCP log folding.

When a durable sync lookback is set (`filters.since` / `adapters.<name>.since`, or CLI `--since`), successful sync **GCs** that adapter’s `sync.files` stamps whose stored mtime is before the lookback. Sessions skipped only because of lookback are never added to the map, so widening the window later can reconsider them. GC does not delete `raw/` and does not touch queue, synth, quarantine, or ops. See [configuration-reference.md — Sync lookback](../configuration-reference.md#sync-lookback).

---

## What is safe to delete

| Delete | When |
|---|---|
| `usage/mcp-*.jsonl` after compact | Safe — their totals already live in `rollup.json` and `daily.json`. |
| `usage/rollup.json` | **Not safe** if you care about lifetime MCP history — compact deletes the raw records that fed it. |
| `usage/daily.json` | **Not safe** if you care about historical daily heatmaps — folded days are not reconstructed from rollup alone. |
| `llmwiki-state.json` | Loses sync mtimes, synth queue, and cost estimate — only delete when intentionally resetting the vault. |
| `raw/sessions/*.md` | Immutable source layer — do not delete to "fix" analytics; re-sync or migrate instead. |

Regenerating `site/` is always safe — it is derived output.

---

## Related commands

- **[`llmwiki usage`](cli.md#usage--mcp-tool-usage-telemetry-vs-synthesis-cost-26)** — print folded totals; `--compact` performs the rollup + daily fold and deletes retired JSONL.
- **[`llmwiki migrate tools-used`](cli.md#tools-used--expand-callmcptool-frontmatter-from-origin-stores)** — expand `CallMcpTool` entries in already-synced raw frontmatter when the origin session file still exists (deterministic, no LLM, no wiki churn).

For upgrade steps after an Analytics layout change, see [`UPGRADING.md`](../UPGRADING.md).
