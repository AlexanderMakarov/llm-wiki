---
title: "CLI reference (part 19/19: Exit codes (conventions))"
slug: cli-reference-19
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/cli.md"
content_sha256: 80394a36c35bb48cc2c8a5640d51d9180b601f9274c4cb944e18a4be261b1dbc
---

> Part 19 of 19 of **CLI reference** — Exit codes (conventions).

## Exit codes (conventions)

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | Operation failed (user-visible error) |
| `2` | Usage error (bad flags, missing file, etc.) |
| `75` | Temporary stop: the synthesis backend's usage limit was reached (`synth`, `all`); retry after the reset |
| `130` | Interrupted with Ctrl+C after a clean stop (`synth`, `all`) |

Subcommands document their own non-zero exit conditions where relevant (`lint --fail-on-errors`).

---

## Related

- **[Slash commands](slash-commands.md)** — the `/wiki-*` surface used from Claude Code.
- **[UI reference](ui.md)** — every screen + nav surface on the compiled site.
- **[Configuration](../configuration.md)** · **[Full configuration reference](../configuration-reference.md)**.
