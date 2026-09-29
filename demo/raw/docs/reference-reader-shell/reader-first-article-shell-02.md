---
title: "Reader-first article shell (part 2/2: Live adopters (#285))"
slug: reader-first-article-shell-02
project: reference-reader-shell
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/reader-shell.md"
content_sha256: cfc45f4b173a60fe62fd29d9768ed78d42f7b977e8132143e6e095ff47c9a66f
---

> Part 2 of 2 of **Reader-first article shell** — Live adopters (#285).

## Live adopters (#285)

Pages with `reader_shell: true` as of v1.1.0-rc8:

| Page | Why |
|---|---|
| [`demo/wiki/entities/Claude Code.md`](../../demo/wiki/entities/Claude%20Code.md) | Flagship model entity — infobox-worthy pricing, benchmarks, and modalities map cleanly to the Wikipedia-style shell |

Project pages such as `demo/wiki/projects/llm-wiki.md` are seeded at build time, not committed — set `reader_shell: true` there after `llmwiki build --seed-project-stubs`.

To opt a page in, add `reader_shell: true` to its frontmatter and rebuild with `llmwiki build`. The shell renders infobox + table of contents + references rail automatically from the page's existing frontmatter + wikilinks.

## Related

- `llmwiki/reader_shell.py` — implementation
- `llmwiki/render/css.py` — where `READER_SHELL_CSS` gets appended
- `docs/maintainers/brand-system.md` — the CSS tokens this shell inherits
- `docs/reference/cache-tiers.md` — sibling opt-in feature, now also has live adopters (#285)
- `#112` — this issue
- `#114` — static prototype hub (the sibling layout surface)
- `#285` — live-adoption polish for this + cache_tier
