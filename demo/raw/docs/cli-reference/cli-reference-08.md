---
title: "CLI reference (part 8/8: watch — near-real-time maintain when sessions finish)"
slug: cli-reference-08
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 8 of 8 of **CLI reference** — watch — near-real-time maintain when sessions finish.

## `watch` — near-real-time maintain when sessions finish

Polls adapter session stores on an interval and runs maintain when a session looks finished. Uses per-adapter turn-complete heuristics (Claude `stop_reason`, Cursor last role, Codex events). Mid-tool / permission loops stay deferred until the adapter reports safe. Adapters without a finished-signal still trigger after a 2s mtime settle — not a multi-minute quiesce.

Single-flight: only one maintain iteration at a time (`sync` → `synthesize` → `build` by default). Changes that arrive during a run set a dirty flag and retry after it finishes. Sync may time out (~180s); synthesize and build have no timeout.

```bash
python3 -m llmwiki watch
python3 -m llmwiki watch --adapter claude_code cursor
python3 -m llmwiki watch --interval 10 --settle 3
python3 -m llmwiki watch --dry-run
python3 -m llmwiki watch --no-synthesize --no-build
python3 -m llmwiki watch --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--adapter NAME [NAME ...]` | Limit to specific adapters. Default: every adapter with a session store on disk. |
| `--interval SECONDS` | Poll interval. Default: `5`. |
| `--settle SECONDS` | Mtime settle before ready check for adapters without a finished-signal. Default: `2`. |
| `--dry-run` | Detect finished sessions only; do not run maintain. |
| `--no-synthesize` | Skip the synthesize step. |
| `--no-build` | Skip the build step. |
| `--vault PATH` | Maintain this vault instead of the repo. |

---

## `install-automation` — daily scheduler + optional agent hooks

Interactive wizard (or pass `--yes` for non-interactive) that writes OS scheduler unit files, optional agent sync hooks, and automation status for the site Home panel. Profiles: **A** = `sync` (auto-build on); **B** = `sync --no-auto-build` → `synth` → `build`; **C** = `all --with-sync --with-synth --skip-graph`. Asks for daily run time (default `08:00`). Linux systemd timers use `Persistent=true` so a missed run catches up after boot. Logs land under XDG state (`~/.local/state/llmwiki/` by default). Writes `.llmwiki/automation-status.json` under the vault for the Home panel. Agent hooks default to skip — press Enter at the prompt to install nothing; type `install` to opt in (not recommended; prefer the OS scheduler or `watch`).

```bash
python3 -m llmwiki install-automation
python3 -m llmwiki install-automation --yes --profile B --hour 9 --minute 30
python3 -m llmwiki install-automation --yes --profile C --watch-enabled
python3 -m llmwiki install-automation --yes --synth-backend ollama --units-dir ~/.config/systemd/user
python3 -m llmwiki install-automation --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--yes` | Non-interactive: use flags and defaults; never installs hooks. |
| `--profile {A,B,C}` | Scheduler command profile. Default: `A`. |
| `--hour N` | Daily run hour (24h). Default: `8`. |
| `--minute N` | Daily run minute. Default: `0`. |
| `--synth-backend NAME` | Synthesis backend for automation status (interactive mode also writes `synthesis.backend` to `config.json`). |
| `--units-dir PATH` | Directory for systemd unit / launchd plist files. Default: `.llmwiki/units/` under the repo. |
| `--watch-enabled` | Record `watch` as enabled in automation status (does not start `watch`). |
| `--force-platform {linux,macos,windows}` | Override platform detection for unit format. |
| `--vault PATH` | Vault root for `automation-status.json`. |

---

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
