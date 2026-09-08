---
title: "UI reference (part 6/6: Accessibility)"
slug: ui-reference-06
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/ui.md"
content_sha256: 7eb6298d7f4ad87999fa2453589b551356412dea6a6e4d19fc218921bf71850b
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
