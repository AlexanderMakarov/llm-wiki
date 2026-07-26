---
title: "Claude CLI synthesis backend"
type: docs
docs_shell: true
docs_passthrough: true
---

> **AGENT / CLI MODE** — synchronous `claude -p` synthesis.

# Claude CLI synthesis backend

v1.4.0 uses **`synthesis.backend: claude`** for agent-friendly synthesis.
Each page is synthesized with a single `claude -p -` invocation — no
pending-prompt files, no `--list-pending` / `--complete` round-trip.

## One-line enable

```json
{
  "synthesis": {
    "backend": "claude",
    "claude_model": "sonnet"
  }
}
```

Optional: `claude_path` (binary path), `timeout` (seconds, default 180).

## How it works

1. `llmwiki synthesize` (or `add` / `all --with-synth`) resolves the backend.
2. For each new/changed raw file, the pipeline renders the source-page prompt.
3. `ClaudeCLISynthesizer` shells out to `claude -p -` with the prompt on stdin.
4. The wiki page is written immediately under `wiki/sources/`.

## CLI

```bash
python3 -m llmwiki synthesize --check      # is claude available?
python3 -m llmwiki synthesize --estimate   # cost preview
python3 -m llmwiki synthesize              # run
python3 -m llmwiki synthesize --force      # re-synth everything
```

## Removed (v1.4.0)

| Old | Replacement |
|---|---|
| `synthesis.backend: agent` / `agent_delegate` | `claude` |
| `synthesize --list-pending` | n/a — synthesis is synchronous |
| `synthesize --complete <uuid>` | n/a |
| `.llmwiki-pending-prompts/` | migrated into `llmwiki-state.json` / deleted |

See [UPGRADING.md](../UPGRADING.md) for the one-time state migration.

## Invariants

- Works with or without `ANTHROPIC_API_KEY` (uses the Claude Code CLI subscription when available).
- One backend serves `sync` auto-paths, `synthesize`, `add`, and `all --with-synth`.
- Unavailable backend aborts the run (no silent dummy overwrite of real pages).
