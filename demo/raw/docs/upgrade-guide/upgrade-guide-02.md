---
title: "Upgrade guide (part 2/7: Unreleased — entity-type taxonomy dropped, project page kind, one search tool (#102))"
slug: upgrade-guide-02
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 2 of 7 of **Upgrade guide** — Unreleased — entity-type taxonomy dropped, project page kind, one search tool (#102).

## Unreleased — entity-type taxonomy dropped, `project` page kind, one search tool (#102)

Four breaking changes ship together. Three need nothing from you; the fourth is the only one with a data decision, and it is optional.

- **Lint rule `entity_consistency` is gone, and an unknown `--rules` name now fails the run.** `llmwiki lint --rules entity_consistency` exits non-zero naming the unknown rule, where before it ran zero rules and reported a clean vault. Drop the rule from any script that pins it; plain `llmwiki lint` needs no change. The rule only ever demanded an `entity_type` value from a fixed seven-value list — removing it removes errors, not coverage.
- **`synth --allow-unclassified` is gone.** Harvest now always fails closed: an incomplete classification exits non-zero, names the pages it could not classify, distinguishes an unreachable backend from an incomplete reply from unreadable source pages, and writes nothing. Drop the flag and configure a backend that returns `name: entity|concept` lines (`synthesis.backend` set to `claude` or `ollama` in `config.json`).
- **MCP tool `wiki_entity_search` is gone; `wiki_search` absorbs it.** There is no alias — an agent config or script naming `wiki_entity_search` gets an unknown-tool error, so re-read the tool list. `wiki_search` takes `term` (required), an optional `kind` (one of `source`, `entity`, `concept`, `project`, `synthesis`, matched against frontmatter `type`; the internal `navigation` and `context` kinds are not offered as a filter, and an unfiltered search still reaches those pages), an optional `format`, and the existing optional `include_raw`. The two compose independently: `include_raw` decides whether `raw/sessions/` is scanned at all, `kind` filters frontmatter `type` in every corpus that is scanned. Raw transcripts declare `type: source`, so `kind=source` with `include_raw` returns matching source pages *and* the transcripts behind them, while a kind no transcript declares (`kind=project`) simply contributes nothing from the raw corpus rather than erroring. Results are page-level (`path — title` with matching lines indented beneath) instead of bare `file:line`, and pages matching by title or path sort above pages matching only in the body. The default response is prose, not JSON: a client that did `json.loads(text)["matches"]` should pass `format: "json"`, which returns `{term, kind, include_raw, pages: [{path, title, name_match, lines: [{line, text}]}], truncated, budget_exhausted, skipped_oversize_files}`. Both renderings report completeness in two fields — `truncated` when an output cap dropped matches, `budget_exhausted` when the byte budget stopped the scan short of the corpus.
- **`project` is a first-class page kind.** `type: project` is now accepted alongside `entity` and `concept`, new project stubs are written as `type: project` with no `entity_type`, and project pages are covered by claim verification and the graph relevance bonus.

### What needs no action

- **Pages that still carry `entity_type` keep it as inert metadata.** Nothing validates it, nothing reads it, and no migration ships. Leave the field or delete it — either way the vault lints the same.
- **`entity_kind: ai-model` is untouched.** It is a different field with a similar name and it still drives the AI-model index and info-cards. Do not sweep it away while cleaning up `entity_type`.
- **Project pages written by an earlier build stay valid.** `type: entity` on a page under `wiki/projects/` is still an accepted kind, the catalog's Projects section keys off the folder rather than the frontmatter, and claim verification and the graph bonus already covered `entity`. Nothing errors and nothing is dropped.

### Optional: re-stamp existing project pages

`ensure_project_stubs` only writes *missing* stubs, so project pages created before this change keep `type: entity` + `entity_type: project` indefinitely. That is valid but inconsistent with what the build writes today, and it has one visible effect: those pages answer `wiki_search kind=entity` rather than `wiki_search kind=project`. If you want the whole folder to declare its kind, edit the frontmatter of each file under `wiki/projects/` — set `type: project` and delete the `entity_type:` line, leaving the body alone:

```bash
sed -i.bak -e 's/^type: entity$/type: project/' -e '/^entity_type: project$/d' <vault>/wiki/projects/*.md
rm <vault>/wiki/projects/*.md.bak
llmwiki lint --vault <vault>          # expect no new errors
llmwiki build --vault <vault>         # refresh the site and search index
```

Frontmatter only — a project page whose body you have written by hand is not otherwise touched.

### Built search index

`site/search-index.json` (and its sharded siblings) no longer carry an `entity_type` key per entry or an `entity_type` bucket under `_facets`. The shipped site reads neither, so the browsable site is unaffected; only a client that reads the index file directly needs to adjust. `docs/reference/reader-api.md` drops the matching invariant from its data-model list, and the surviving invariants renumbered — cite an invariant by the field it constrains, not by its position in the list.

## Unreleased — honest already-synthesized counts (#81)

- **`synth --estimate` Corpus / Already synthesized count eligible sources**, not pages under `wiki/sources/`. Expect `Corpus: N eligible sources (S sessions + D docs)` and `Already synthesized: N of M eligible sources`. A separate `Source pages (current state): T on disk (Sess sessions + D docs + X stubs)` line is the on-disk `.md` file mix (not unique `source_file` keys) — it may differ from Already synthesized when bookkeeping and disk diverge.
- **Home Pipeline** captions the input table **Eligible sources** (not Files layer as the unit of the input columns) and adds an **On disk** column (Stubs row; Other when needed). There is no under-table Source pages note.

## Unreleased — honest estimate Candidates (#113)

- **`synth --estimate` Candidates is pre-run state**, not a preview of what the next run will harvest. The block is labelled `Candidates (pre-run state):` and notes that pending sources are not yet reflected.
- **After a successful real `synth`**, the CLI prints an end-of-run summary: `Synthesized:`, `Duration:`, optional `Tokens:` / `Cost:` when known. Harvest still prints Candidates once; the end summary does not repeat that line.
- Home Knowledge-layer **Candidates** still counts pending pages under `wiki/candidates/` — distinct from the estimate pre-run harvestable figure.
