---
title: "Upgrade guide (part 1/5)"
slug: upgrade-guide-01
project: upgrading
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/UPGRADING.md"
content_sha256: 79fd93bf709421f37aa05c27a435cd601ed7f0443274f4ab0c06dc082831e232
---

> Part 1 of 5 of **Upgrade guide**.

---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases. Most releases are drop-in (`pip install -U llm-wiki-plus` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is [CHANGELOG.md](https://github.com/AlexanderMakarov/llm-wiki/blob/main/CHANGELOG.md) — this guide focuses on "what might break".

## 2.2.0 — install from PyPI as `llm-wiki-plus` (#210)

The published distribution is **`llm-wiki-plus`** (`llmwiki` and `llm-wiki` are unavailable on PyPI). The import and CLI stay `llmwiki`.

```bash
pip install -U llm-wiki-plus
llmwiki --version   # → 2.2.0
```

Optional graph extra: `pip install 'llm-wiki-plus[graph]'`. Re-run `llmwiki install-agent-kit --dest PATH` after upgrade so retired slash commands (`/wiki-export-marp`, `/wiki-synthesize`) are pruned from an older kit install (#214). Prefer `/wiki-synth` (add sources-only when you want the old synthesize path).

## 2.1.0 — CLI help as a lifecycle map (#112)

`llmwiki --help` is grouped into six lifecycle sections. Command renames that affect scripts and muscle memory:

| Old name | Replacement |
|---|---|
| `synthesize` | `synth` (old default was sources-only; today's `synth` does sources + harvest unless you pass `--sources-only`) |
| `consolidate-topics` | gone — `synth` prepares known names at the start of each sources pass |
| `migrate-state` | `migrate state` |
| `migrate-raw-redaction` | `migrate raw-redaction` |
| `migrate-tools-used` | `migrate tools-used` |
| `migrate-page-kinds` | `migrate page-kinds` |
| `migrate-topic-kinds` | `migrate topic-kinds` |
| `migrate-broken-provenance` | `migrate broken-provenance` |

List migrations with `llmwiki migrate` or `llmwiki migrate --list`. Nothing runs until you pick a name. Prefer `--dry-run` first. The `/wiki-synthesize` slash alias is retired — `/wiki-synth` is the command, and `synth --sources-only` is the flag for the sources-only pass.

## 2.1.0 — durable sync lookback (#192)

Optional shared `filters.since` and per-adapter `adapters.<name>.since` (`YYYY-MM-DD`, or `"all"` to skip the date gate for one source). Unset still means unlimited history.

- **Set a lookback before enabling a long-retention store** so the first bare sync does not convert years of history. CLI `--since` still overrides for one run.
- **`llmwiki configure-sources`** asks shared start date first (Enter = today−30, or keep a stored date), then per source shows **Sessions · Earliest · In last 30 days** before Enable / path / start date. Enable means the source is on the next bare `sync` (Cursor IDE included). Skipped interviews invent no dates.
- **The next successful sync with a durable lookback** prunes that coding-agent adapter’s `sync.files` stamps older than the window (CLI `--since` does not GC; notes intake is not GC’d). Lookback-only skips are never remembered as done, so widening the date later can pick them up. GC does not delete `raw/` or queue/synth/quarantine/ops.
- **Cursor IDE registry name is `cursor_ide`** (was `cursor`) so it is distinct from `cursor_cli`. `--adapter cursor` and a legacy `adapters.cursor` config block still work. Prefer `adapters.cursor_ide` in new configs. Existing `sync.files` keys prefixed `cursor::` are rewritten to `cursor_ide::` on the next state load so Composer threads are not re-converted.
- **`llmwiki adapters` enabled column is yes/no** (will the next bare sync include this source). The old `active` column and `auto` / `explicit` / `off` labels are gone.
Keys and inheritance: [configuration-reference.md — Sync lookback](configuration-reference.md#sync-lookback).

## 2.1.0 — MCP tool consolidation (#196)

The stdio MCP server registers **six** tools: `wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`. There are no alias stubs for retired names.

| Retired | Replacement |
|---|---|
| `wiki_query` | `wiki_search` with `question` or `mode=extract` |
| `wiki_list_sources` | `wiki_search` with `list_sources=true` |
| `wiki_confidence` / `wiki_lifecycle` / `wiki_category_browse` | `wiki_search` with `mode=filter` and the matching `filter_by` |
| `wiki_lint` | `wiki_health` (same lint JSON keys; adds `totals`) |
| `wiki_dashboard` | `wiki_health` (`totals` field) |

Full parameter tables: [mcp.md](reference/mcp.md). Historical telemetry rows keep the logged tool name; `llmwiki usage` and Analytics fold retired names into the canonical six-tool surface.
