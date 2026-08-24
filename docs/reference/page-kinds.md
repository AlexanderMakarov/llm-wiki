---
title: "Page kinds"
type: navigation
docs_shell: true
---

# Page kinds

Every wiki page declares a `type:` in its YAML frontmatter. The vocabulary is owned by `llmwiki/schema.py`: five knowledge kinds a reader searches by (`source`, `entity`, `concept`, `project`, `synthesis`) and two system kinds the build and query workflow emit (`navigation`, `context`). Lint (`frontmatter_validity`) and the `wiki_search` MCP filter both read that same list, so a value that is not in it is an error.

This page says what each kind is for, points at a real file in the committed [demo vault](../../demo/), and gives every frontmatter field a provenance. How those pages render on the compiled site is the [UI reference](ui.md); topic pages in particular are covered under [Topic pages](ui.md#topic-pages).

Lint requires only `title` and `type` (`frontmatter_completeness`). Everything else in the tables is what a producer actually writes, or what a person may add. Fields a producer never writes are listed as conventionally absent, with the reason.

## Provenance

| Value | Means | Producer in code |
|---|---|---|
| **synth** | Written when summarising a raw file into `wiki/sources/` | `llmwiki/synth/pipeline.py` `_build_source_page` (also the log-archive page when `wiki/log.md` exceeds 50 KB) |
| **harvest** | Written when collecting candidates from `[[wikilinks]]` on source pages | `llmwiki/candidates_harvest.py` `_stub_text` |
| **build** | Derived by the site build, or by a generator that writes wiki markdown from other pages | `llmwiki/build.py` `ensure_project_stubs`; `llmwiki/categories.py` |
| **human** | Only ever filled in by a person or an agent acting as one. No pipeline step generates it | `llmwiki init` seeds, saved answers, `_context.md`, opt-in schema fields, `llmwiki tags` |

Promote (`llmwiki candidates promote`) is a human gate: it moves a harvest stub into the trusted tree and rewrites `status: candidate` → `reviewed`. It does not invent a new kind. Empty `## Key Facts` are filled offline from source topic `fact:` bullets.

---

## `source`

One page per raw file, under `wiki/sources/<project>/`. Synth writes it from a session transcript or an added document. The body is a summary, claims, quotes, and `[[wikilinks]]` — not a copy of the transcript. The raw file is immutable; this page is the knowledge-layer stand-in.

**Demo.** [`demo/wiki/sources/01-installation/2026-08-10-01-installation.md`](../../demo/wiki/sources/01-installation/2026-08-10-01-installation.md) is a synthesised document page. A session-derived source is [`demo/wiki/sources/llm-wiki/2026-08-09-wikilink-resolution.md`](../../demo/wiki/sources/llm-wiki/2026-08-09-wikilink-resolution.md). The raw inputs remain [`demo/raw/docs/01-installation/01-installation.md`](../../demo/raw/docs/01-installation/01-installation.md) and [`demo/raw/sessions/llm-wiki/2026-08-09T23-12-llm-wiki-wikilink-resolution.md`](../../demo/raw/sessions/llm-wiki/2026-08-09T23-12-llm-wiki-wikilink-resolution.md).

Raw files also carry `type: source`. That is the input layer (`raw/sessions/`, `raw/docs/`), not this wiki kind. Synth copies eight fields onto the wiki page and leaves the rest on the raw file.

### Fields synth writes

| Field | Provenance | What it is |
|---|---|---|
| `title` | synth | Copied from the raw file's `title` |
| `type` | synth | Always `source` |
| `tags` | synth | Deterministic baseline (adapter / `session-transcript` / project slug / model family) merged with tags the model suggested in a `<!-- suggested-tags: … -->` line. On re-synth, existing tags on the wiki page are kept so a person's edits survive |
| `date` | synth | Copied from the raw file's `date` |
| `source_file` | synth | Copied from the raw file's `source_file`. Session transcripts write that field at convert time. Added documents write `source:` (original path) instead, so a wiki page synthesised from `raw/docs/` often has an empty `source_file` |
| `project` | synth | Copied from the raw file; for a document with no `project`, synth injects `docs` so the page lands under `wiki/sources/docs/` |
| `model` | synth | Copied from the raw file. On a session this is the model id (for example `claude-opus-5`). On a document it is usually empty. This is not the entity-schema JSON `model` block |
| `last_updated` | synth | UTC date of the synth run, `YYYY-MM-DD` |

### Conventionally absent

| Field | Why |
|---|---|
| `sources` | The page *is* the source. Provenance down to `raw/` is `source_file`, not a list of other wiki pages |
| `slug`, `sessionId`, `started`, `ended`, `cwd`, `gitBranch`, `permissionMode`, `description`, `user_messages`, `tool_calls`, `tools_used`, `tool_counts`, `token_totals`, `turn_count`, `hour_buckets`, `duration_seconds`, `is_subagent`, `entrypoint`, `promptSource`, `is_headless`, `agent` | Session-adapter fields. Convert (and the demo session generator, for `agent`) writes them on the raw transcript; `_build_source_page` does not copy them. The wiki filename uses the raw `slug` (and `date`) via `synth_page_filename`, but the wiki frontmatter has no `slug:` |
| `source`, `content_sha256`, `extractor` | Added-document fields. `llmwiki add` writes them on the raw file under `raw/docs/`; synth does not copy them |
| `status`, `confidence`, `lifecycle`, `last_verified` | No producer writes these on a source page |
| `topics` | Project pages use `topics:`; source pages use `tags:` (`tags_topics_convention`) |

---

## `entity`

A person, company, product, tool, or library. Harvest writes a stub under `wiki/candidates/entities/` when the same `[[Name]]` appears on enough source pages (default three). Kind, short description, and facts come from Connections topic bullets on those sources — no classify LLM call. A person then promotes it into `wiki/entities/`. The body is attributed fact bullets under `## Key Facts`; the opening description is the one harvest already recorded from the source pass.

**Demo.** [`demo/wiki/entities/Claude Code.md`](../../demo/wiki/entities/Claude Code.md) is a promoted entity. Pending harvest stubs remain under [`demo/wiki/candidates/entities/`](../../demo/wiki/candidates/entities/).

### Fields harvest writes

| Field | Provenance | What it is |
|---|---|---|
| `title` | harvest | The `[[wikilink]]` target name |
| `type` | harvest | `entity` (or `concept` — taken from the source topic bullet; a person can flip on promote) |
| `status` | harvest | `candidate` on the stub. `candidates promote` rewrites it to `reviewed` |
| `tags` | harvest | Always `[]`. A person fills tags later (`llmwiki tags add`) |
| `sources` | harvest | Slugs of the source pages that named this target — the evidence list |
| `last_updated` | harvest | UTC date of the harvest run |

Promote keeps those fields, fills an empty `## Key Facts` from source topic `fact:` bullets offline (no synthesis backend required), and does not add `confidence`, `lifecycle`, or a new `last_updated`.

### Opt-in model profile (human)

An entity with `entity_kind: ai-model` is picked up by the `/models/` index. Every field below is **human** — no synth, harvest, or build path writes them. Full schema: [Entity schema](entity-schema.md).

| Field | Provenance |
|---|---|
| `entity_kind` | human |
| `provider` | human |
| `model` | human (inline JSON: `context_window`, `max_output`, `license`, `released`) |
| `pricing` | human (inline JSON: `input_per_1m`, `output_per_1m`, `cache_read_per_1m`, `cache_write_per_1m`, `currency`, `effective`) |
| `modalities` | human |
| `benchmarks` | human |

### Conventionally absent

| Field | Why |
|---|---|
| `source_file`, `date`, `project`, `model` (session id) | Those belong on source pages. An entity points at sources through `sources:` |
| `topics` | Entities use `tags:` |
| `confidence`, `lifecycle`, `last_verified` | No producer writes them. Valid if a person adds them (`frontmatter_validity`) |
| `homepage`, `description` as project-stub fields | Those are the project-stub keys; an entity page does not get them from `ensure_project_stubs` |

---

## `concept`

An idea, framework, method, or theory. Same producer as `entity`: harvest reads a name whose source topic bullets mark it `concept` and writes `wiki/candidates/concepts/<Name>.md`. Promote moves it to `wiki/concepts/`. Flip-and-promote swaps entity ↔ concept and rewrites `type:` to match the destination folder.

**Demo.** [`demo/wiki/concepts/Adapters.md`](../../demo/wiki/concepts/Adapters.md) is a promoted concept. A pending concept stub is [`demo/wiki/candidates/concepts/Wiki Synthesis.md`](../../demo/wiki/candidates/concepts/Wiki Synthesis.md).

### Fields

The harvest table under [`entity`](#entity) applies unchanged, except `type` is `concept` and the stub lives under `candidates/concepts/`. There is no opt-in schema analogous to `entity_kind: ai-model`.

### Conventionally absent

The same absences as entity, plus every `entity_kind` / `provider` / `pricing` / `modalities` / `benchmarks` field — those are defined only for `type: entity`.

---

## `project`

A codebase or work stream, one page per session `project:` slug, under `wiki/projects/<slug>.md`. `ensure_project_stubs()` (`llmwiki/build.py`) writes a stub when `build --seed-project-stubs` is set, or when `sync` builds (sync always passes that flag). A bare `build` does not seed — it is read-only on `wiki/`. Existing files are never overwritten.

**Demo.** No committed project page. Sessions that would seed one are on disk under [`demo/raw/sessions/llm-wiki/`](../../demo/raw/sessions/llm-wiki/) (and the other project folders beside it). The stub `demo/wiki/projects/llm-wiki.md` appears after `llmwiki sync` or `llmwiki build --seed-project-stubs`.

### Fields the stub writer writes

| Field | Provenance | What it is |
|---|---|---|
| `title` | build | The project slug |
| `type` | build | Always `project` |
| `project` | build | The same slug, matching session `project:` |
| `topics` | build | Derived from session tags / `tools_used`, noise tags dropped. A person may edit afterwards; the stub is not rewritten |
| `description` | build | From the most recent session's summary or slug. Same edit rule as `topics` |
| `homepage` | build | Written as `""`. Any real URL is **human** |

### Conventionally absent

| Field | Why |
|---|---|
| `last_updated` | `ensure_project_stubs()` does not write it. Project freshness on the compiled site is derived from the project's sessions (oldest and newest session dates) at build time, not from a date on the stub |
| `date` | Same reason — no page-owned date |
| `sources` | Sessions *are* the evidence. Lint `claim_verification` treats a `## Sessions` section as a citation; the stub has none until a person adds one |
| `tags` | Project pages use `topics:`, not `tags:` (`tags_topics_convention`) |
| `status`, `confidence`, `lifecycle`, `last_verified`, `source_file`, `model` | No producer writes them on a project stub |
| `entity_kind` and the model-profile block | Those are entity-only |

---

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
