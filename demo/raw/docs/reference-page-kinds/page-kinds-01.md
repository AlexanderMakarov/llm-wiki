---
title: "Page kinds (part 1/3)"
slug: page-kinds-01
project: reference-page-kinds
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/page-kinds.md"
content_sha256: dfa6fdd3b0463588ce7292deb4bd68ac2f7b553d5e4c09a8581092aebc9a492c
---

> Part 1 of 3 of **Page kinds**.

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
