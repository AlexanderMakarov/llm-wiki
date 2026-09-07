---
title: "UI reference (part 6/6: Accessibility)"
slug: ui-reference-06
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/ui.md"
content_sha256: 5d23c1e6e61b910eb88351ef022ce42f6dd7cb3ca86429dc3872a58de758d661
---

> Part 6 of 6 of **UI reference** — Accessibility.

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
