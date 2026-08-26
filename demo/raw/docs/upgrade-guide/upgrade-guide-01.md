---
title: "Upgrade guide (part 1/7)"
slug: upgrade-guide-01
project: upgrade-guide
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/UPGRADING.md"
content_sha256: 1edde415b51f8cacf9995db66240407df90211d0b78f27234d578b0f7b9b29e3
---

> Part 1 of 7 of **Upgrade guide**.

---
title: "Upgrade guide"
type: navigation
docs_shell: true
---

# Upgrade guide

How to upgrade between `llmwiki` releases.  Most releases are drop-in (`pip install -U llmwiki` or `brew upgrade llmwiki`) — this page documents the exceptions: schema migrations, config changes, and behaviour flips that affect what happens on your next `sync`.

The canonical per-release detail is [CHANGELOG.md](https://github.com/Pratiyush/llm-wiki/blob/master/CHANGELOG.md) — this guide focuses on "what might break".

## Unreleased — auto-generated `/vs/` model comparisons removed (#138)

- **No vault migration.** The `/vs/` surface was never called from `build_site` and never wrote `site/vs/` for a normal vault build. Rebuild as usual.
- **Optional cleanup.** If you hand-authored `wiki/vs/*.md` overrides from older docs, they are no longer read; delete or keep as personal notes. `/models/` is unchanged.

## Unreleased — page kinds `question` and `comparison` removed (#109)

- **`type: question` and `type: comparison` are no longer valid frontmatter.** They are gone from the `type:` vocabulary, so `llmwiki lint` reports a `frontmatter_validity` **error** on any page still declaring one, and `wiki_search` no longer offers them as a `kind` filter. Nothing in the product ever created such a page — `init` never scaffolded `wiki/questions/` or `wiki/comparisons/`, and no synth, harvest, or promote path wrote into them — so for almost every vault this is a no-op.
- **If you hand-wrote pages of either kind, run `llmwiki migrate-page-kinds --vault <your vault>`.** It retypes each page to `concept`, moves it into `wiki/concepts/` keeping the filename, deletes the legacy `_context.md`, and prunes `wiki/questions/` and `wiki/comparisons/` once they are empty. Inbound `[[wikilinks]]` resolve by filename, not by folder, so the move does not break a single link and no referring page is edited. Preview with `--dry-run`; a vault with no such page prints `nothing to migrate` and exits 0. A filename already taken in `wiki/concepts/` is never overwritten — that page is retyped where it stands and reported so you can settle the clash — and a legacy folder still holding other content is left in place and reported. Rebuild afterwards (`llmwiki build --vault <your vault>`) so `site/` picks up the new locations.
- **A folder you keep for your own reasons still works.** `reindex` catalogues any folder it finds under `wiki/`, so pages in a non-canonical folder stay listed in `wiki/index.md` and stay in the graph. Only the frontmatter `type:` value is constrained.

## Unreleased — trace provenance + lint `provenance_integrity` (#122)

- **New CLI: `llmwiki trace <page>`.** Prints the downward provenance chain from a wiki page to its source summaries and raw files (`sources:` / `source_file:` only). Missing hops are labelled; the walk still exits 0 unless the starting page cannot be resolved. See `docs/reference/cli.md` → `## trace`.
- **New lint rule `provenance_integrity` (errors).** After upgrading, `llmwiki lint` (and `llmwiki all`) may report **new errors** on pages whose `sources:` slugs or `source_file:` paths no longer resolve. Pages with no provenance fields are unchanged. The rule only reports — it does not prune or rewrite frontmatter. Guided repair ships with `doctor` (#110); until then, fix pointers by hand or leave the findings if the targets are truly gone.
- **Site Sources links.** Session and document pages turn provenance Sources into clickable links: built HTML when the hop compiled, otherwise the raw (or site copy) in a new tab with a “(raw)” mark. Topic pages list graph evidence under a collapsible **Sources** section (Sessions / Documents), not a separate frontmatter provenance panel. Rebuild with `llmwiki build` to see them.
- **No new MCP tool.** Agents that need the chain should call `llmwiki trace` (or read frontmatter via existing wiki tools). Do not expect a `wiki_trace` MCP entry.
