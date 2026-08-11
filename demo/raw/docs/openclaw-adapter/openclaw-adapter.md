---
title: "OpenClaw adapter"
slug: openclaw-adapter
project: openclaw-adapter
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/adapters/openclaw.md"
content_sha256: 0f899ec3b2d6dbaa147acf27a815d8bdda1de28764f0b963f89a307c01483d2c
---

---
title: "OpenClaw adapter"
type: navigation
docs_shell: true
---

# OpenClaw adapter

Reads `.jsonl` session transcripts written by the [OpenClaw](https://openclaw.ai) agent gateway (native store under `~/.openclaw/agents/`, not the OpenCode app-config layout — that is the separate [`opencode`](opencode.md) adapter).

**AI-session adapter** (`is_ai_session = True`) — fires by default when its session store is present on disk.

## Session store

Default root: `~/.openclaw/agents/` (same path on Linux, macOS, and Windows via `Path.home()`).

Layouts accepted under each configured root:

- **Native install:** `<agent>/sessions/<uuid>.jsonl`
- **Vault inbox mirror:** `<agent>/<uuid>.jsonl` (no `sessions/` segment) — used when another host copies transcripts into a Syncthing vault at e.g. `<vault>/.openclaw-sessions-inbox/`

Skipped (not conversation transcripts): `*.trajectory.jsonl`, `*.checkpoint.*.jsonl`, and anything under a `_quarantine/` directory.

Override the search roots in `config.json`:

```json
{
  "adapters": {
    "openclaw": {
      "roots": ["~/.openclaw/agents", "<vault>/.openclaw-sessions-inbox"]
    }
  }
}
```

## What it reads

Each session is a JSONL stream of typed OpenClaw records. Only `type == "message"` rows become conversation turns; user `content` lists are flattened to strings for the shared renderer.

## Enable it

Works out-of-the-box if OpenClaw has written sessions under `~/.openclaw/agents`. Point `roots` at a vault inbox when transcripts are mirrored there instead.

## Output layout

Standard `raw/sessions/<YYYY-MM-DDTHH-MM>-openclaw-<agent>-<slug>.md` (project slug is `openclaw-<agent>`).

## Code

- `llmwiki/adapters/contrib/openclaw.py`
- Tests: `tests/test_openclaw_cursor_cli_adapters.py`

## See also

- [OpenCode / OpenClaw (app-config) adapter](opencode.md) — shared schema under `~/.config/openclaw/sessions/`
- [Configuration reference](../configuration-reference.md) — `adapters.openclaw.roots`
- [All adapters](../../README.md#works-with)
