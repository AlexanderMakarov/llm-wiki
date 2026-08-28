---
title: "OpenCode / OpenClaw adapter"
type: navigation
docs_shell: true
---

# OpenCode / OpenClaw adapter

Reads `.jsonl` session transcripts written by the
[OpenCode](https://github.com/sst/opencode) / OpenClaw agents —
both use an identical schema.

Runs on bare `llmwiki sync` when OpenCode / OpenClaw app-config session dirs exist on disk.

## Session store

The adapter auto-detects the store across platforms:

- **Linux:** `~/.config/opencode/sessions/` and `~/.config/openclaw/sessions/`
- **macOS:** `~/Library/Application Support/opencode/sessions/` and
  `~/Library/Application Support/openclaw/sessions/`
- **Windows:** `%APPDATA%\opencode\sessions\` and `%APPDATA%\openclaw\sessions\`

Both nested (`<project>/<session>.jsonl`) and flat
(`<project>-<session>.jsonl`) layouts are handled.

## What it reads

Each session is a JSONL stream of `{role, content}` records:

```json
{"role": "user",      "content": "start a new feature"}
{"role": "assistant", "content": "…"}
{"role": "tool",      "content": "…"}
```

`normalize_records()` translates that schema into the Claude-style
`{type, message: {role, content}}` that the shared renderer expects:

| OpenCode role | Claude-style type | Claude-style role |
|---|---|---|
| `user` | `user` | `user` |
| `assistant` | `assistant` | `assistant` |
| `tool` | `user` | `tool` (preserved so the renderer can show tool turns distinctly) |

## Enable it

```bash
python3 -m llmwiki sync --adapter opencode
```

To turn it off after enabling via config:

```jsonc
{ "adapters": { "opencode": { "enabled": false } } }
```

## Automated (headless) sessions

No verified automation-launch markers in the store today — sessions are treated as **not** headless under `filters.exclude_headless`. See [Multi-agent setup](../multi-agent-setup.md#what-automated-headless-means).

## Output layout

Standard `raw/sessions/<YYYY-MM-DDTHH-MM>-<project>-<slug>.md`.

## Code

- `llmwiki/adapters/contrib/opencode.py`
- Tests: `tests/test_opencode_adapter.py` (23 cases)
- Issue history: #43 (initial)

## See also

- [All adapters](../../README.md#works-with) — comparison table of
  every agent adapter llmwiki supports out of the box.
