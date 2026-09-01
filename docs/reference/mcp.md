---
title: "MCP server — tool reference"
type: navigation
docs_shell: true
---

# MCP server — tool reference

The llmwiki **MCP** server (`python3 -m llmwiki.mcp`) exposes six production tools over stdio (JSON-RPC 2.0). Connect it from Claude Code, Cursor, Codex, or any MCP client so agents can search, read, lint, sync, export, and add to your wiki without shelling out to the CLI. Every tool is implemented in `llmwiki/mcp/server.py`; telemetry is local-only under `<vault>/usage/` (see [State persistence](state-persistence.md) and the Analytics MCP table in [UI reference](ui.md)).

## Tools

| Tool | Purpose |
|---|---|
| `wiki_search` | Find, list, filter, and extract wiki content (unified search surface) |
| `wiki_read_page` | Read one page by vault-relative path |
| `wiki_health` | Run lint checks and return headline wiki totals |
| `wiki_sync` | Pull new agent sessions into `raw/sessions/` (dry-run by default) |
| `wiki_export` | Return a built `site/` export (`llms-txt`, `jsonld`, …) |
| `wiki_add` | Ingest one URL, file, or literal content into `raw/docs/` |

## `wiki_search`

Dispatch is controlled by `mode` (or by supplying `question` alone, which implies extract mode).

### `mode=match` (default)

Literal substring search over wiki pages (and optionally `raw/sessions/`).

| Argument | Required | Description |
|---|---|---|
| `term` | yes* | Case-insensitive substring to find in titles, paths, and bodies |
| `list_sources` | no | When `true`, list `raw/sessions/` metadata instead of searching |
| `project` | no | With `list_sources=true`, filter sessions whose project slug contains this string |
| `kind` | no | Restrict to one frontmatter `type` (`source`, `entity`, `concept`, `project`, `synthesis`) |
| `include_raw` | no | Also scan `raw/sessions/` (default `false`) |
| `format` | no | `text` (default) or `json` |

\* Not required when `list_sources=true`.

### `mode=extract`

Answer a natural-language question from `wiki/index.md`, `wiki/overview.md`, and matching pages.

| Argument | Required | Description |
|---|---|---|
| `question` | yes | Question or keywords |
| `max_pages` | no | Cap on returned pages (default `5`) |

### `mode=filter`

Metadata filters over loaded wiki pages.

| `filter_by` | Required args | Optional args |
|---|---|---|
| `confidence` | — | `min_confidence` (default `0.0`), `max_confidence` (default `1.0`) |
| `lifecycle` | `state` | — |
| `tag` | — | `tag` (drill into one tag), `min_count` (default `1`) |

## `wiki_health`

Same JSON payload as `llmwiki lint --json` (`summary`, `issues`, `total_pages`, `disabled_rules`, `ran`), plus a `totals` object:

| Field | Meaning |
|---|---|
| `wiki_pages` | Pages loaded for lint |
| `sources` | Source pages under `wiki/sources/` (or `type: source`) |
| `pending_candidates` | Markdown stubs in `wiki/candidates/` (excluding `_context.md`) |

Optional: `rules` (subset of checks), `min_refs` (broken-link threshold; default matches harvest).

## `wiki_sync`

Defaults to **dry-run**. To write, pass `dry_run: false` **and** `confirm: true`.

## `wiki_export`

`format` is one of `llms-txt`, `llms-full-txt`, `jsonld`, `sitemap`, `rss`, `manifest`, or `list` (catalog of files present under `site/`). Run `llmwiki build` first when exports are missing.

## `wiki_add`

Exactly one of `url`, `path`, or `content` is required. Optional: `title`, `project`, `tags`, `note`.

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
