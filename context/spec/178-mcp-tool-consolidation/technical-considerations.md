# Technical Specification: Consolidate the MCP Tool Surface (#196)

- **Functional Specification:** [`functional-spec.md`](./functional-spec.md) (Status: Approved)
- **Status:** Draft
- **Author(s):** 4ellendger
- **Ticket:** [#196](https://github.com/AlexanderMakarov/llm-wiki/issues/196)

---

## 1. High-Level Technical Approach

Shrink the MCP `TOOLS` list from twelve entries to six by **merging handlers**, not by deleting behaviour. Implementation is confined to `llmwiki/mcp/server.py`, `llmwiki/usage.py`, analytics renderers, tests, and docs — no new runtime dependencies, no vault file rewrites.

| # | Registered name | Action |
|---|---|---|
| 1 | `wiki_search` | Absorb query, list_sources, confidence, lifecycle, category_browse |
| 2 | `wiki_read_page` | Unchanged (keep name — avoids read-analytics churn) |
| 3 | `wiki_health` | Rename from `wiki_lint`; add `totals`; drop `wiki_dashboard` |
| 4 | `wiki_sync` | Unchanged |
| 5 | `wiki_export` | Unchanged |
| 6 | `wiki_add` | Unchanged |

**Ordering:** (A) telemetry canonical map first so analytics stays honest while tools are in flux; (B) `wiki_health`; (C) unified `wiki_search`; (D) delete retired tool schemas/handlers; (E) docs + tests sweep.

Baseline to record in the PR: `len(TOOLS)==12`, serialized `json.dumps(TOOLS)` length **7597** chars (measured on `origin/main` worktree).

---

## 2. Proposed Solution & Implementation Plan (The "How")

### 2.1 Telemetry canonical tool map (`llmwiki/usage.py`)

Add a single source of truth:

```python
CANONICAL_TOOL_ALIASES: dict[str, str] = {
    "wiki_query": "wiki_search",
    "wiki_list_sources": "wiki_search",
    "wiki_confidence": "wiki_search",
    "wiki_lifecycle": "wiki_search",
    "wiki_category_browse": "wiki_search",
    "wiki_lint": "wiki_health",
    "wiki_dashboard": "wiki_health",
    # Retired earlier — fold into search for display continuity
    "wiki_entity_search": "wiki_search",
}

def canonical_tool_name(tool: str) -> str:
    return CANONICAL_TOOL_ALIASES.get(tool, tool)
```

**Apply at aggregation time** (raw JSONL lines are never rewritten):

| Function | Change |
|---|---|
| `aggregate()` | Map `tool` before `per_tool` / `per_project_tool` bucketing |
| `day_buckets_from_records()` | Map before `by_tool[tool]` and before `RETRIEVAL_TOOLS` / read-kind checks |
| `page_retrievals()` | Treat mapped read tool as `wiki_read_page` (identity today; future-proof) |
| `value_summary()` | `RETRIEVAL_TOOLS` → canonical set `{wiki_search, wiki_read_page}`; `WRITE_TOOLS` unchanged; `ENTITY_TOOLS` → canonical entity-returning tools only (`wiki_search`, `wiki_read_page`, `wiki_export`) |

`is_entity_tool()` / `is_retrieval_tool()` should call `canonical_tool_name()` first so callers work on either raw or canonical names.

**Analytics renderer** (`llmwiki/viz_wiki_value.py`):

- Per-tool table already iterates `per_tool` from aggregated totals — no change needed once `aggregate()` maps names.
- Update value-card subtext from `query · search · read_page` to `search · read`.
- Optionally filter table to the six known live tools (hide `unknown` unless calls > 0).

**`daily.json` / `rollup.json`:** Stored `by_tool` keys in folded history may still carry retired names until the next compact rebuilds from raw logs. `refresh_daily()` recomputes live overlay from JSONL via `day_buckets_from_records()` (mapped). For folded days baked into `daily.json`, either (a) accept stale keys until next compact, or (b) remap keys when loading folded buckets — prefer **(b)** in `_normalize_day_bucket` so the Analytics heatmap `by_tool` series also shows canonical names only.

### 2.2 `wiki_health` (replaces `wiki_lint` + `wiki_dashboard`)

| File | Change |
|---|---|
| `llmwiki/mcp/server.py` | Rename tool schema `wiki_lint` → `wiki_health`; rename `tool_wiki_lint` → `tool_wiki_health` (keep thin alias during refactor if tests import old name temporarily). Delete `wiki_dashboard` schema + `tool_wiki_dashboard`. |
| `llmwiki/lint/report.py` or handler | After `render_json(outcome, total_pages)`, add top-level `totals` dict |

**`totals` shape** (cheap O(n) over `load_pages` + one directory glob):

| Field | Source |
|---|---|
| `wiki_pages` | `len(pages)` from lint's `load_pages` (same as `total_pages`) |
| `sources` | count of `wiki/sources/**/*.md` pages (or `type: source` pages) |
| `pending_candidates` | `len(list((wiki / "candidates").glob("*.md")))` — excludes `_context.md` if present via existing path helpers |

No per-type, lifecycle, or confidence breakdowns.

**Contract:** JSON lint report keys unchanged (`summary`, `issues`, `total_pages`, `disabled_rules`, `ran`) plus new sibling `totals`. Breaking rename of the *tool name* only — payload is a superset of today's `wiki_lint` JSON.

Optional `rules` and `min_refs` arguments unchanged.

### 2.3 Unified `wiki_search`

Replace five tool schemas with one expanded schema. Internal implementations (`tool_wiki_query`, `tool_wiki_list_sources`, `tool_wiki_confidence`, `tool_wiki_lifecycle`, `tool_wiki_category_browse`) become **private functions** called from `tool_wiki_search` — delete their `TOOLS` entries and `TOOL_IMPLS` keys.

**Dispatch contract** — explicit `mode` enum avoids the model guessing from parameter presence:

| `mode` | Required args | Optional args | Calls |
|---|---|---|---|
| `match` (default) | `term` | `kind`, `project`, `include_raw`, `format` | existing `tool_wiki_search` body; when `kind=source` + `project`, also covers `list_sources` |
| `extract` | `question` | `max_pages` | existing `tool_wiki_query` body |
| `filter` | `filter_by` | see below | confidence / lifecycle / category handlers |

`filter_by` values:

| `filter_by` | Args | Behaviour |
|---|---|---|
| `confidence` | `min_confidence`, `max_confidence` (defaults 0.0–1.0) | today's `wiki_confidence` |
| `lifecycle` | `state` (required) | today's `wiki_lifecycle` |
| `tag` | `tag` (optional), `min_count` (default 1) | `tag` set → pages for tag; omitted → tag counts |

**Validation:** Return `_err(...)` when required fields for the chosen mode are missing; when `mode=match` and `term` is empty, error (do not fall through to list-all).

**Schema size discipline:** One consolidated description paragraph; per-mode detail in property descriptions only. Reuse existing `PAGE_KINDS` enum for `kind`. Drop duplicate prose carried over from five separate tool descriptions.

**Hardening:** Preserve byte caps, hit caps, and archive exclusion from existing search/query implementations — route through the same helpers (`_read_capped`, `_SEARCH_HIT_CAP`, etc.).

**`project` filter:** Add to match mode schema (already used by `list_sources`); thread into search/list_sources scan.

### 2.4 Retired tools — hard removal

Following `wiki_entity_search` precedent: no MCP alias stubs. `handle_tools_call` for retired names returns the standard unknown-tool error.

Delete from `TOOLS` and `TOOL_IMPLS`:

- `wiki_query`, `wiki_list_sources`, `wiki_confidence`, `wiki_lifecycle`, `wiki_category_browse`, `wiki_lint`, `wiki_dashboard`

Update `tests/test_mcp_protocol.py` (expects 12 tools today) and `tests/test_mcp_enhanced.py` to expect **6** tools — update counts only, not a permanent ceiling test elsewhere.

### 2.5 Documentation

| File | Change |
|---|---|
| `docs/reference/mcp.md` | **New** — canonical six-tool reference, parameter tables per mode, migration table for every retired name |
| `docs/reference/cli.md` | Link to `mcp.md` from `usage` section |
| `docs/reference/ui.md` | Analytics §: six-tool surface; per-tool table shows canonical names |
| `docs/UPGRADING.md` | New breaking-change block (same shape as `wiki_entity_search` / `wiki_lint` entries) |
| `CHANGELOG.md` | `## [Unreleased]` entry |
| `llmwiki/exporters.py` (`ai-readme.md` generator) | Replace stale "7 tools" list with six tools + link to `docs/reference/mcp.md` |
| `llmwiki/mcp/__init__.py`, module docstring in `server.py` | Update tool list |
| `CONTRIBUTING.md` / CI reference coverage | Add `mcp.md` row if enforced |

### 2.6 Telemetry evidence (pre-merge)

Before deleting tools, run against a vault with real usage (operator live vault read-only, or `demo/usage/`):

```bash
python3 -m llmwiki usage --json --vault <vault>
```

Post per-tool `calls` and `zero_hit_rate` to issue #196 or PR body. If no retained telemetry exists, state that explicitly and cite demo generator stats as illustrative only.

---

## 3. Impact and Risk Analysis

- **System dependencies:** MCP server, usage aggregation, static site Analytics (`build.py` → `viz_wiki_value.py`), agent kit docs that name MCP tools.
- **Breaking MCP clients:** Any hardcoded tool name (`wiki_lint`, `wiki_query`, …) fails until updated. Documented in UPGRADING.
- **Analytics continuity:** Canonical map must run before any code path reads `per_tool` keys for display; folded `daily.json` remapping prevents ghost rows after compact.
- **Search schema complexity:** Mitigated by required `mode` enum; keep descriptions tight.
- **Health call cost:** One extra `load_pages` pass for totals is acceptable — lint already loads all pages; reuse the same `pages` dict inside `tool_wiki_health`.
- **Folded telemetry edge case:** `rollup.json` `per_tool` may contain retired keys until next `usage --compact`; `combined_totals()` should map when merging rollup + live, or remap on rollup load.

---

## 4. Testing Strategy

| Area | Tests |
|---|---|
| Tool surface | `tests/test_mcp_protocol.py` — `tools/list` returns 6 tools with `inputSchema` each; unknown retired name errors |
| Search modes | Extend `tests/test_mcp_enhanced.py` — match/extract/filter parity against today's per-tool fixtures; `kind=source` + `project` covers list_sources |
| Health | Rename `tests/test_mcp_lint_parity.py` coverage to `wiki_health`; assert `totals` keys present; parity with `lint --json` on shared keys |
| Telemetry map | `tests/test_mcp_usage.py` — aggregate records with retired names → single canonical `per_tool` row; merged calls/zero_hits |
| Archive / security | Keep `tests/test_archive_cold_storage.py` search/query paths working via unified search |
| Docs | `tests/test_102_acceptance.py`-style grep or extend acceptance for UPGRADING/CHANGELOG mentions |

No test asserts max tool count or payload byte ceiling (per functional spec §2.7).

Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` before push.
