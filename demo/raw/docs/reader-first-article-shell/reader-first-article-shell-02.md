---
title: "Reader-first article shell (part 2/2: Live adopters (#285))"
slug: reader-first-article-shell-02
project: reader-first-article-shell
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/reader-shell.md"
content_sha256: 7f06f85a318d1942e04d497c52e04ecc3320f7f905937a30e250e08bf13727b9
---

> Part 2 of 2 of **Reader-first article shell** — Live adopters (#285).

## Live adopters (#285)

Pages with `reader_shell: true` as of v1.1.0-rc8:

| Page | Why |
|---|---|
| [`demo/wiki/entities/ClaudeSonnet4.md`](../../demo/wiki/entities/ClaudeSonnet4.md) | Flagship model entity — has infobox-worthy pricing, benchmarks, modalities that map cleanly to the Wikipedia-style shell |
| [`demo/wiki/projects/llm-wiki.md`](../../demo/wiki/projects/llm-wiki.md) | Meta project page — showcases `reader_shell` on the framework's own canonical page |

To opt a page in, add `reader_shell: true` to its frontmatter and rebuild with `llmwiki build`. The shell renders infobox + table of contents + references rail automatically from the page's existing frontmatter + wikilinks.

## Related

- `llmwiki/reader_shell.py` — implementation
- `llmwiki/render/css.py` — where `READER_SHELL_CSS` gets appended
- `docs/design/brand-system.md` — the CSS tokens this shell inherits
- `docs/reference/cache-tiers.md` — sibling opt-in feature, now also has live adopters (#285)
- `#112` — this issue
- `#114` — static prototype hub (the sibling layout surface)
- `#285` — live-adoption polish for this + cache_tier
