---
title: "CLI reference (part 15/15: Exit codes (conventions))"
slug: cli-reference-15
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 15 of 15 of **CLI reference** — Exit codes (conventions).

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |

Subcommands document their own non-zero exit conditions where relevant (`lint --fail-on-errors`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
