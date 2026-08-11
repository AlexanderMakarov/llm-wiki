---
title: "UI reference (part 5/5: Accessibility)"
slug: ui-reference-05
project: ui-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/ui.md"
content_sha256: 091e560125d91e049c14221fb0d035f09dac5d63e4986142a6252af727a37d58
---

> Part 5 of 5 of **UI reference** — Accessibility.

## Accessibility

WCAG 2.1 AA targeted across the whole site. Specifics in [`../accessibility.md`](../accessibility.md). Notable:

- Every image has an `alt` attribute
- Skip-to-content link appears on every page on keyboard focus
- Focus ring uses the accent colour with 2 px outline + 2 px offset
- `prefers-reduced-motion` honoured (all transitions collapse to 0.01 ms)
- Muted text hits ≥ 4.8:1 contrast in light and ≥ 6.9:1 in dark

---

## Related

- **[CLI reference](cli.md)** — every `python3 -m llmwiki …` subcommand.
- **[Slash commands reference](slash-commands.md)** — the `/wiki-*` surface.
- **[Reader API contract](reader-api.md)** — stable shape of every file the build writes.
- **[Reader-first article shell](reader-shell.md)** — opt-in Wikipedia-style layout for individual pages.
