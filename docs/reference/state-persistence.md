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
| `usage/session-tokens.json` | Session Tokens aggregates for Analytics — lifetime totals, `by_agent` measured/known coverage, per-UTC-day × agent buckets (last-activity attribution), and slim per-session stubs for idempotent upsert. One file (not one file per session) so hot paths stay O(1) file opens. Empty / no-usage sessions are never stubs here. | `llmwiki sync` / convert (new or fingerprint-changed sessions with nonempty usage; metrics-only for filtered measurable sessions); `llmwiki migrate session-tokens` (historical backfill) | `llmwiki build` (bake Analytics Tokens + coverage); slim public `site/session-tokens.js` (aggregates only — no `sessions` ledger) for live Tokens refresh |
| `site/session-tokens.js` | Public `window.LLMWIKI_SESSION_TOKENS` snapshot: `totals`, `by_agent`, `days`, `attribution`, `updated_at`. Never embeds the vault `sessions` ledger (including metrics-only keys). | `sync` / convert upsert, `migrate session-tokens`, `build` | Analytics viewer JS updates the Tokens card without a full HTML rebuild |
| `~/.cursor/llmwiki-cursor-token-events.jsonl` (optional) | Cursor Agent turn usage captured by the managed POSIX `stop` hook (`llmwiki-cursor-token-stop.sh`, installed via `python3 -m llmwiki.cursor_token_events --install-hook`). The managed hook appends the **full** stop stdin JSON for latency; Python ingest writes minimized rows — both load. Joined by `conversation_id` on sync/migrate — `store.db` has no turn throughput fields. Keep local (not under `site/`). | Cursor `stop` hook | `cursor_cli` adapter (`normalize_records`) |
| `llmwiki-state.json` | Synth queue, sync mtimes, cost estimate, Home pipeline snapshot (`synth.pipeline`), ops stage stamps (`ops.last_synth_at`, `ops.last_build_at`, `ops.last_lint_*`), the latest failure of each pipeline part plus the scheduled job's run stamp and schedule (`outcomes`, read by the Home problems banner, #374), quarantine. Top-level sections this release does not know (from a newer llmwiki) are kept on write rather than dropped — separate from `usage/`; MCP telemetry never writes here. | `sync`, `synth`, `build`, `lint`, `queue`, `migrate state`, related CLI; `llmwiki build` (one-shot `synth.pipeline` backfill when the key is missing — #70) | Same CLI family; `llmwiki build` (optional synth cost line on Analytics; Home State widget via `llmwiki-state.js` sidecar); standalone `lint` updates this JSON and copies the site data sidecar without rewriting HTML (#234); `migrate tools-used` (origin lookup via sync keys) |
| `raw/sessions/*.md` frontmatter | Session-side signal — `tools_used`, `tool_counts`, `token_totals` (omitted when all buckets are zero), dates — used for wiki-adoption heatmaps, per-session Tokens cards, and best-effort session/day counts alongside MCP logs. | `llmwiki sync` / convert; `migrate tools-used` (tools fields only); `migrate session-tokens` (may patch `token_totals`) | `llmwiki build` (session pages, Agents Activity heatmap, wiki-using session days); `migrate tools-used` / `migrate session-tokens` |

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

`llmwiki-state.json` follows a different lifecycle: sync, synth, build, and lint update it; it does not participate in MCP log folding. Home **Pipeline state** reads stage stamps and lint error text from `ops.*` via the `site/llmwiki-state.js` sidecar. After a failed lint, `ops.last_lint_error` holds the full console-shaped note of the findings that tripped the fail policy (errors first), not a prefix of the full report, and `ops.last_lint_report` holds the full console report; a passing lint clears both (#256). Home displays at most 10 lines of the note and shows the report under **Linter output**. A bare `llmwiki lint` (outside `build`) refreshes the JSON and that data sidecar only — it does not rewrite site HTML. Automation settings live in `.llmwiki/automation-status.json`, not in this file.

`.llmwiki/automation-status.json` is written by `install-automation` and read by the Home Automation panel and `llmwiki doctor`. Besides the job and schedule settings and the `scheduler_*` activation keys, it records which schedule serves the vault: `scheduler_unit` (the vault's own unit name, `llmwiki-maintain-<slug>-<hash>`), `working_dir` (the llmwiki copy the job runs from), `target_vault` (the resolved vault the scheduled command names with `--vault`), `installed_at` (UTC time of the last successful activation, kept when a later install does not activate), `adopted_legacy` (whether that install switched off the legacy single `llmwiki-maintain` schedule) and `legacy_adopt_error` (why switching it off failed, else `null`). Doctor uses `installed_at` to tell a schedule that never ran from one that was just set up. See [`install-automation`](cli.md#install-automation--set-up-the-daily-job).

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
