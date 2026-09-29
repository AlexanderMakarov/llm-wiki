---
title: "Page kinds (part 3/3: synthesis)"
slug: page-kinds-03
project: reference-page-kinds
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/page-kinds.md"
content_sha256: dfa6fdd3b0463588ce7292deb4bd68ac2f7b553d5e4c09a8581092aebc9a492c
---

> Part 3 of 3 of **Page kinds** — synthesis.

## `synthesis`

A saved answer: a person or an agent read several wiki pages and wrote down the result. **Nothing in llmwiki generates a synthesis page automatically.** `synth` writes source pages; harvest writes candidates; build writes project stubs. None of those paths touch `wiki/syntheses/` or `wiki/overview.md` after `init` has seeded the overview.

`llmwiki init` seeds `wiki/overview.md` as `type: synthesis` with empty `sources` and an empty `last_updated`, and a body that says the page is maintained by the coding agent. Saved answers go under `wiki/syntheses/<slug>.md`. Both are **human** (an agent writing the page is still a person for provenance — there is no pipeline call).

**Demo.** The living overview is [`demo/wiki/overview.md`](../../demo/wiki/overview.md). There is no saved-answer page under `demo/wiki/syntheses/` yet — only the folder context stub. A page there appears when someone saves a query answer.

### Fields on a synthesis page

| Field | Provenance | What it is |
|---|---|---|
| `title` | human | `init` seeds `"Overview"` on `overview.md`; a saved answer's title is whatever the writer puts |
| `type` | human | `synthesis` |
| `sources` | human | `init` seeds `[]` on overview. A saved answer should list the pages it drew on; nothing fills this automatically |
| `last_updated` | human | `init` seeds `""` on overview. A writer dates the page |
| `tags` | human | Optional. Synthesis pages use `tags:`, not `topics:` |

### Conventionally absent

| Field | Why |
|---|---|
| `source_file`, `date`, `project`, `model` | Those are source-page fields. A synthesis cites wiki pages through `sources:` |
| `status` | Harvest only. Syntheses are never candidates |
| `topics`, `homepage`, `description` | Project-stub keys |
| `confidence`, `lifecycle`, `last_verified` | No producer writes them |

---

## `navigation`

Machinery, not a kind anyone searches *for*. Search still reaches these pages when unfiltered; the kind is omitted from the kind filter. `init` seeds several under `wiki/`; synth may archive a bloated log; a library can emit per-tag category pages.

**Demo.** [`demo/wiki/CRITICAL_FACTS.md`](../../demo/wiki/CRITICAL_FACTS.md) is the seeded invariants page. [`demo/wiki/index.md`](../../demo/wiki/index.md) and [`demo/wiki/log.md`](../../demo/wiki/log.md) are the catalog and the append-only log — `init` writes those two **without** frontmatter, and lint exempts them (`frontmatter_completeness` / `SYSTEM_PAGE_FILES`).

### Fields by producer

| Field | Provenance | Where it appears |
|---|---|---|
| `title` | human | `init` seeds it on `hints.md`, `hot.md`, `MEMORY.md`, `SOUL.md`, `CRITICAL_FACTS.md`, `dashboard.md` |
| `type` | human | Always `navigation` on those seeds |
| `last_updated` | human | `init` seeds `""` on the navigation seeds |
| `auto_maintained` | human | `init` writes `true` on `wiki/hot.md` |
| `max_lines` | human | `init` writes `200` on `wiki/MEMORY.md` |
| `title`, `type`, `auto_generated`, `last_updated` | synth | `_auto_archive_log` writes `wiki/log-archive-<year>.md` when `log.md` exceeds 50 KB, with `auto_generated: true` and today's date |
| `title`, `type`, `tag` | build | `llmwiki.categories` writes `wiki/categories/<tag>.md` (`type: navigation`, `tag: <tag>`). That library is not invoked by `build` or any CLI subcommand; a vault that never calls it has no per-tag pages. The demo has only the folder context stub |

Documentation pages compiled into the site docs hub (this file included) also use `type: navigation` plus `docs_shell: true`. `docs_shell` is **human** — the docs compiler (`llmwiki/docs_pages.py`) reads it and otherwise leaves the page alone. Those files live under `docs/`, not under `wiki/`.

### Conventionally absent on vault navigation pages

| Field | Why |
|---|---|
| Frontmatter on `index.md` / `log.md` | `init` / `reindex` seed them as markdown catalogs, not as typed pages. Lint skips them by filename |
| `sources`, `source_file`, `project`, `model`, `status`, `confidence`, `lifecycle` | Not part of any navigation seed or generator |
| `topics` | Not a project page |

---

## `context`

A `_context.md` file in a wiki folder. It tells an agent what the folder is for so a deep query can skip or enter it. `load_folder_context` reads `type: context` and a short body; lint flags a folder with more than ten pages and no stub (`find_uncontexted_folders`). Nothing creates these files automatically.

**Demo.** [`demo/wiki/syntheses/_context.md`](../../demo/wiki/syntheses/_context.md) and [`demo/wiki/categories/_context.md`](../../demo/wiki/categories/_context.md).

### Fields

| Field | Provenance | What it is |
|---|---|---|
| `title` | human | Folder label |
| `type` | human | `context` |

The context parser is key/value only — no lists, no nested JSON.

### Conventionally absent

| Field | Why |
|---|---|
| `last_updated`, `sources`, `tags`, `status`, `confidence`, `lifecycle`, `source_file`, `project`, `model` | `context_md.py` expects simple metadata, usually just `type: context`. Lint exempts `_context.md` from `frontmatter_completeness`, so even `title` is optional |
| Any harvest / synth / stub field | No pipeline writes `_context.md` |

---

## Fields no pipeline writes

These names appear in the code (lint, search facets, MCP `wiki_confidence` / `wiki_lifecycle`, `content_freshness`) but no synth, harvest, or build path writes them. They are **human** when present, and conventionally absent on every page the pipeline produces.

| Field | Who reads it | Valid values |
|---|---|---|
| `confidence` | `frontmatter_validity`, search facets, MCP `wiki_confidence` | Number in `[0.0, 1.0]`. Formula lives in `llmwiki/confidence.py`; nothing stores the result |
| `lifecycle` | `frontmatter_validity`, search facets, MCP `wiki_lifecycle` | `draft`, `reviewed`, `verified`, `stale`, `archived` (`llmwiki/lifecycle.py`) |
| `last_verified` | `content_freshness` prefers it over `last_updated` | ISO date. Never written by a producer |

`status` is the exception in this neighbourhood: harvest writes it (`candidate`); promote rewrites it (`reviewed`). It is not a lifecycle state.
