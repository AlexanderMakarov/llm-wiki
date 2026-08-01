---
title: "Agent mode"
type: navigation
docs_shell: true
---

> **AGENT MODE** — uses your existing Claude Code / Codex CLI session.

# Mode B · Agent

Runs synthesis + query **inside** the Claude Code or Codex CLI session
that's already open on your machine — no separate Anthropic API key.

## Status (v1.4.0+)

Slash commands (`/wiki-sync`, `/wiki-ingest`, `/wiki-query`, `/wiki-reflect`,
`/wiki-update`, `/wiki-lint`) still drive the agent workflow.

For **synthesis**, set `synthesis.backend` to **`claude`** (synchronous
`claude -p` CLI). The old `agent` / agent-delegate backend (pending-prompt
files + `synthesize --list-pending` / `--complete`) was **removed in v1.4.0**.

```json
{
  "synthesis": {
    "backend": "claude",
    "claude_model": "sonnet"
  }
}
```

Then run `llmwiki synth` (or `llmwiki add` / `llmwiki all --with-synth`).
One configured backend serves every command.

## Setup

```bash
mkdir -p ~/.claude/commands
cp .claude/commands/wiki-*.md ~/.claude/commands/
```

Open Claude Code, type `/wiki-sync`, and it runs. Ensure `claude` is on
`$PATH` (or set `synthesis.claude_path`).

## Daily flow

```
You: /wiki-sync
Claude: (runs python3 -m llmwiki sync, ingests new pages)

You: /wiki-query when did I last change the convert pipeline?
Claude: (reads wiki/index.md + the relevant source pages, synthesizes)

You: llmwiki synth   # or /wiki-all --with-synth
```

## Read next

- [Claude CLI backend notes](backend.md)
- [Configuration — synthesis backend](../configuration.md#synthesis-backend)
- [Upgrade guide](../UPGRADING.md)
