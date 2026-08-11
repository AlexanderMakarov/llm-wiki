---
title: "Editorial brand system (part 2/2: 5. Spacing)"
slug: editorial-brand-system-02
project: editorial-brand-system
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/design/brand-system.md"
content_sha256: 0f680d04e9f298ce1102d1684f5e7446e8f4987546a1cf95bbf1b9a8053ff22a
---

> Part 2 of 2 of **Editorial brand system** — 5. Spacing.

## 5. Spacing

No scale token yet — spacing is inlined in rules (padding/gap/margin). The
canonical steps used across the codebase:

- **2 px** — border-radius adjustments, hairline separators
- **4 px** — icon gaps, inline-code padding
- **8 px** — button padding, card inner gap (`gap-2`)
- **12 px** — paragraph spacing, list indent
- **16 px** — card padding (resting), section gap
- **24 px** — major section separators, hero padding
- **32–48 px** — page-level container padding at ≥ 768 px

A future token pass (`--space-1`…`--space-6`) is on the roadmap; until then,
stay inside this set when adding rules to keep the rhythm consistent.

---

## 6. Export consistency

All generated artifacts must inherit the same tokens:

| Artifact | Inherits |
|---|---|
| Static HTML site (`site/`) | Full CSS from `llmwiki/render/css.py` |
| Graph viewer (`site/graph.html`) | `--g-*` palette mirroring the main site |
| PDF export (future) | Print stylesheet adds explicit black-on-white + page breaks |
| Marp slide export | Keeps Inter + JetBrains Mono + `#7C3AED` accent |
| QMD export | Quarto theme sets body = Inter, mono = JetBrains Mono |
| Obsidian vault (via symlink) | Reads `.obsidian/themes/llmwiki.css` (future) |
| Screenshots in README | Taken in light mode for consistency |

### Social preview image

When a page links externally (OpenGraph / `twitter:image`):

- Background: `#0c0a1d` (dark bg)
- Heading: Inter 700, 72 px, `#e2e8f0`
- Accent stripe: `#7C3AED` 4 px × full width along the top
- Logo wordmark: "llm**wiki**" — Inter 800, 120 px, `#a78bfa` for "llm",
  `#e2e8f0` for "wiki"

---

## 7. Do / don't

**Do**
- Let the text breathe — line-height 1.7 for any paragraph > 3 lines.
- Keep cards borderless-ish — 1 px `--border-subtle` with `--shadow-card`.
- Use `--accent` for one thing per section (a link, a badge, a button —
  not all three).
- Flip the whole palette via `data-theme`, not per-component opt-ins.
- Match existing radius/shadow tokens before inventing new values.

**Don't**
- Don't mix mono and sans in the same run of prose. Pick Inter, drop into
  mono only for `code`.
- Don't use accent on body copy.
- Don't add a third shadow level.
- Don't use custom web fonts — Inter + JetBrains Mono are the only two.
- Don't build contrast into the HTML (e.g. `<span style="color:white">`);
  always go through a variable so the theme toggle works.

---

## 8. Changelog for this doc

When you change a token or add a scale step, add a one-line entry to
[`CHANGELOG.md`](../../CHANGELOG.md) under `### Changed` with the new token
name + value + where it's used. That keeps the brand history traceable in
the release notes.

## Related

- `llmwiki/render/css.py` — source of truth for every CSS variable
- `llmwiki/render/js.py` — theme toggle + palette sync logic
- `docs/reference/cache-tiers.md` — also uses the accent palette for badges
- `#115` — this issue
