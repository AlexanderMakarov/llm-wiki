---
title: "Editorial brand system (part 2/2: 5. Spacing)"
type: source
tags: [wiki-add, raw-doc, session-transcript, design-brand-system, design-tokens, spacing-scale, color-palette, typography, brand-guidelines, export-consistency, theme-system]
date: 2026-09-07
source_file: 
project: design-brand-system
model: 
last_updated: 2026-09-07
---
## Summary

This page establishes design guidelines and token inheritance rules for the [[llmwiki]] brand system. It prescribes a 7-step canonical spacing scale (2–48 px), requires all export formats to inherit CSS tokens from `llmwiki/render/css.py`, and mandates theme switching via `data-theme` rather than per-component overrides. Changes to tokens must be logged in the changelog.

## Key Claims

- Spacing uses an inlined canonical scale (2, 4, 8, 12, 16, 24, 32–48 px) pending a future tokenization pass (`--space-1`…`--space-6`).
- All output formats (HTML, PDF, QMD, Obsidian, graph viewer, screenshots) must inherit CSS tokens from `llmwiki/render/css.py` as a single source of truth.
- Theme switching must use `data-theme` attribute at the root element, not per-component opt-ins.
- Only Inter and JetBrains Mono fonts are permitted; no custom web fonts allowed.
- Contrast and colors must use CSS variables, not hardcoded HTML `style` attributes, to enable theme toggling.
- Social preview images (OpenGraph/Twitter) follow a fixed design: dark background `#0c0a1d`, 4 px accent stripe `#7C3AED`, two-tone wordmark.

## Key Quotes

> "Flip the whole palette via `data-theme`, not per-component opt-ins." — core architectural principle for consistent theme switching across all outputs.

> "Always go through a variable so the theme toggle works." — rationale for banning hardcoded color values and ensuring accessibility.

## Connections

- [[llmwiki]] (project) — the system being designed; render modules in `llmwiki/render/` implement these rules.
- [[Static Site]] (topic) — the primary output format that inherits the full CSS token system.
- [[Obsidian]] (topic) — an export target that will eventually integrate via `.obsidian/themes/llmwiki.css`.
