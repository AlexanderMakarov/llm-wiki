# Analytics page: MCP usage + raw-documents enrichment (#27)

**Status:** approved design · **Date:** 2026-07-18 · **Branch:** `feat/analytics-mcp-usage-27`

## Goal

Make the static-site **Analytics** pages answer "is this wiki worth its cost, and
who actually uses it?" by surfacing MCP-usage telemetry (#26) and raw-document
data alongside the existing agent-session analytics. Both the **global**
`analytics.html` and the **per-project** `projects/<slug>.html` pages are updated.

This supersedes the original #27 MVP scope (per-tool/per-project call counts +
bytes served + corpus build cost). Two corrections from that scope:

1. **Bytes served is dropped** — it is a low-signal metric. We track *calls* and
   *items returned* instead.
2. **Raw-document data is added** — missing from the original ticket.

## Non-goals

- Static-site page-view tracking (`file://` — deliberately untracked).
- Any remote/analytics service.
- Corpus build **cost** in dollars — deferred; `synth.estimate` is a single
  overwritten snapshot, not summable history, so the "sum per-run cost" premise
  in the ticket does not hold against the current state shape. Out of scope here.
- Threading a real client session id into MCP telemetry (see "Session metric").

## Data available (verified in code)

- `llmwiki/usage.py` already merges per-process JSONL + kept-forever `rollup.json`
  into `combined_totals(content_root)` →
  `{total_calls, total_resp_bytes, per_tool:{calls,zero_hits,zero_hit_rate,resp_bytes}, per_project:{calls,resp_bytes}}`.
- Each telemetry record carries `tool`, `hits`, `resp_bytes`, `caller_project`,
  `server_pid`, `server_started`. **No client session id exists.**
- `hits` (via `mcp/server.py::_resolve_hits`) already = number of items a call
  returned. This is our "MCP answers" signal.
- Raw docs (`raw/docs/**`) carry a `project:` frontmatter field (written by
  `add_doc.py`, default = parent folder name) → raw docs are attributable to a
  project.
- `build.py::_agent_label(meta, path)` already classifies a session's producer
  (Claude / Cursor / Codex / Copilot).

## Design

### A. Telemetry aggregation — `llmwiki/usage.py`

Extend the aggregate shape (additive, backward-compatible). New fields default
to `0`/absent when read from an old `rollup.json`.

- **Items returned** (`items_returned`): sum of `hits`, **restricted to
  entity-returning tools**. Tracked per-tool and as a total.
  - Entity-returning allowlist: `wiki_query`, `wiki_search`,
    `wiki_list_sources`, `wiki_read_page`, `wiki_entity_search`,
    `wiki_category_browse`, `wiki_export`, `wiki_confidence`.
  - Excluded (calls still counted, items not): `wiki_lint`, `wiki_sync`,
    `wiki_lifecycle`, `wiki_dashboard`.
  - The allowlist lives as a module constant `ENTITY_TOOLS` so it is testable
    and single-sourced.
- **Server processes** (`server_processes`): distinct `(server_pid,
  server_started)` pairs that issued ≥1 call, per project and total. This is the
  honest name for "how many MCP client sessions used the wiki" — one llm-wiki MCP
  server process ≈ one editor session, but we do not claim it *is* a session.
  - Live aggregation collects the distinct set. The rollup persists a **count**
    per project (a process never spans a monthly fold boundary — `compact` only
    folds files whose newest record is in a *past* month — so counts are safely
    additive across rollup + live).
- `resp_bytes` stays in the aggregate for backward-compat but is **never
  rendered**.

New/changed functions:
- `aggregate()` — add `items_returned` (per_tool + total, entity tools only) and
  collect per-project `server_processes` as a set → count.
- `merge_aggregates()` — sum the new numeric fields.
- `_empty_totals()` / rollup helpers — seed the new fields.
- `ENTITY_TOOLS: frozenset[str]` module constant + a tiny
  `is_entity_tool(tool)` helper.

### B. Global Analytics page — `build.py::render_analytics`

1. Heatmap label "Activity · last 365 days" → **"Agents Activity · last 365 days"**.
2. Token stats (`viz_tokens.render_site_token_stats`): merge "Total tokens" +
   "Average per session" into **one card** ("Tokens" → value = total, sub =
   "avg N / session"). Clarify "Heaviest project" → **"Heaviest project (by
   tokens)"**.
3. New card **"Most MCP-active project"** = project with the most total llm-wiki
   MCP calls (value = call count, sub = project slug, links to its page). Absent
   when there is no telemetry.
4. New **"Wiki usage (MCP)"** section: a per-tool table (tool · calls · items
   returned · zero-hit rate) + totals, and a **raw documents** total. Static, "as
   of last build". Absent when there is neither telemetry nor raw docs.
5. **Recent activity** (`changelog_timeline.render_recent_activity`): replace
   bare "N processed" with a short explicit breakdown when the log detail
   provides it — `2 Claude · 1 Cursor · 0 docs`. Parsed from a structured
   `Processed:` detail line; falls back to the current "N processed" for legacy
   entries. (Log entries are written by the ingest workflow, not Python; the
   renderer just parses richer detail when present and degrades gracefully.)

### C. Per-project Analytics page — `build.py::render_project_page`

New stats block near the top of a project page:
- **Raw documents**: count of `raw/docs/**` files whose `project:` == this slug.
- **MCP calls**: total llm-wiki MCP calls attributed to this project.
- **MCP items returned**: total items across entity-returning tools.
- **MCP server processes**: distinct processes for this project.
- **Per-tool table**: tool · calls · items returned (entity tools show items;
  others show "—").
Block is omitted when the project has neither raw docs nor telemetry.

### D. Delivery

Numbers baked into the HTML at `llmwiki build` time. `build_site` computes
`usage.combined_totals(REPO_ROOT)` and the raw-doc-per-project counts once, and
threads them into `render_analytics` and `render_project_page`. No `.js` sidecar
for the MVP.

### E. Tests + CHANGELOG

- `tests/test_usage.py` (or existing usage test module): new aggregate fields,
  entity-tool restriction, rollup round-trip, backward-compat with an
  old-shape rollup.
- Build/render tests: MCP section renders with data, degrades to empty without,
  per-project block present/absent, recent-activity breakdown vs fallback.
- `CHANGELOG.md` entry.
- Rebuild the static site after implementation (hard rule #6).

## Component boundaries

- `usage.py` stays pure aggregation (no HTML). Returns render-ready dicts.
- `build.py` orchestrates: reads totals once, passes slices to renderers.
- Renderers (`viz_tokens`, `changelog_timeline`, `build.render_*`) stay
  presentation-only and degrade to empty on missing data — matching the existing
  "malformed data → empty card" convention.

## Open risk

- **Legacy `rollup.json`**: pre-existing rollups lack `items_returned` /
  `server_processes`. Telemetry is brand-new (#26 just merged), so real folded
  rollups are unlikely to exist; missing fields read as 0. Documented, accepted.
