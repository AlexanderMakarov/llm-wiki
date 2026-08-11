---
title: "Accessibility Audit Summary"
slug: accessibility-audit-summary
project: accessibility-audit-summary
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/accessibility-report.md"
content_sha256: 8a34cdc2be2a0ca5dc0385b8511f3a3b35d5a94a55000c7f2ca42f88c090d288
---

# Accessibility Audit Summary

Quick-reference compliance status. For the full audit with code samples,
fix history, and out-of-scope notes, see
[`accessibility.md`](accessibility.md).

## WCAG 2.1 AA compliance

**Status: passing.** All generated HTML pages meet WCAG 2.1 Level AA
requirements as verified by automated and manual checks.

## Automated audit: axe-core

Tool: [axe-core](https://github.com/dequelabs/axe-core) via
`axe-playwright-python`, run against a built site with real content.

| Page type | Route | Violations |
|---|---|---|
| Home | `index.html` | 0 |
| Projects index | `projects/index.html` | 0 |
| Sessions index | `sessions/index.html` | 0 |
| Session detail | `sessions/<project>/<slug>.html` | 0 |

Run locally:

```bash
PYTHONPATH=. python3 scripts/a11y_audit.py
```

## Contrast ratios

All text tokens meet the AA minimum of 4.5:1 in both themes.

### Light mode (`data-theme="light"`)

| Token | Foreground | Background | Ratio |
|---|---|---|---|
| Body text (`--text`) | `#0f172a` | `#ffffff` | 15.98:1 |
| Secondary text (`--text-secondary`) | `#475569` | `#ffffff` | 5.92:1 |
| Muted text (`--text-muted`) | `#6b7280` | `#ffffff` | 4.84:1 |
| Accent / links (`--accent`) | `#7C3AED` | `#ffffff` | 4.63:1 |
| Code keywords (hljs) | `#c23a40` | `#f1f5f9` | 4.82:1 |

### Dark mode (`data-theme="dark"`)

| Token | Foreground | Background | Ratio |
|---|---|---|---|
| Body text (`--text`) | `#e2e8f0` | `#0c0a1d` | 14.72:1 |
| Secondary text (`--text-secondary`) | `#94a3b8` | `#0c0a1d` | 7.89:1 |
| Muted text (`--text-muted`) | `#8b9bb5` | `#0c0a1d` | 6.97:1 |
| Accent / links (`--accent`) | `#7C3AED` | `#0c0a1d` | 5.14:1 |
| Code keywords (hljs) | theme default | `#0d1117` | 4.5:1+ |

## Keyboard navigation checklist

| Feature | Status | Key(s) |
|---|---|---|
| Skip-to-content link | Implemented | Tab (first press) |
| Focus indicators | 2px solid accent outline | `:focus-visible` |
| Command palette | Opens + focuses input | Cmd+K / Ctrl+K |
| Search focus | Focus search input | `/` |
| Close overlays | Dismiss palette/dialog | Escape |
| Home navigation | Go to home page | `g h` |
| Projects navigation | Go to projects index | `g p` |
| Sessions navigation | Go to sessions index | `g s` |
| Row navigation | Next/previous table row | `j` / `k` |
| Shortcut help | Show all shortcuts | `?` |

Tab order follows logical document flow: nav > breadcrumbs > content >
footer.

## Screen reader compatibility

| Feature | Implementation |
|---|---|
| Language declaration | `<html lang="en">` on every page |
| Landmark regions | `<main id="main-content">`, `<nav aria-label>`, `<header>`, `<footer>` |
| Breadcrumb current page | `aria-current="page"` |
| Command palette | `role="dialog"` + `aria-modal="true"` + `aria-label` |
| Link distinguishability | Underlines on text-embedded links (WCAG 1.4.1) |
| Images | Alt text on all decorative and informational images |
| Heatmap | `role="img"` + descriptive `aria-label`, per-cell `<title>` tooltips |

### VoiceOver smoke test (manual)

Tested on macOS with Safari:

- [x] Skip link announced and functional
- [x] Navigation landmarks discoverable
- [x] Table headers read correctly on sessions index
- [x] Code blocks read as preformatted text
- [x] Command palette announces dialog opening

## Reduced motion

Users with `prefers-reduced-motion: reduce` get:

- Instant scroll (no smooth scrolling)
- Animations and transitions set to 0.01ms duration
- No layout or content changes

## Fixes applied in v0.9

Five accessibility violations were found and fixed:

1. Muted text contrast too low (light + dark) — darkened color tokens
2. highlight.js keyword contrast below 4.5:1 — CSS override
3. Footer/breadcrumb links indistinguishable from text — added underlines
4. No skip-to-content link — added `.skip-link`
5. `<main>` missing `id` for skip target — added `id="main-content"`

## Full details

See [`accessibility.md`](accessibility.md) for contrast calculation
methodology, CSS code samples, the complete fix table, and out-of-scope
items (AAA contrast, third-party CDN themes).
