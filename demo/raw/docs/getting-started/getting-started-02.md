---
title: "Getting started (part 2/2: Auto-sync on session start (optional))"
slug: getting-started-02
project: getting-started
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/getting-started.md"
content_sha256: 2ba6346e0ced88bd5f133a3774ebabf5662876a6ac5ff41708562a1548e425ba
---

> Part 2 of 2 of **Getting started** — Auto-sync on session start (optional).

## Auto-sync on session start (optional)

To make sync happen automatically every time you start Claude Code, add a `SessionStart` hook to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "(python3 /absolute/path/to/llm-wiki/llmwiki/convert.py > /tmp/llmwiki-sync.log 2>&1 &) ; exit 0"
          }
        ]
      }
    ]
  }
}
```

The `( ... &) ; exit 0` pattern backgrounds the sync and makes sure it never blocks Claude Code starting.

## Next steps

- [architecture.md](architecture.md) — the 3-layer Karpathy + 8-layer build breakdown
- [configuration-reference.md](configuration-reference.md) — every CLI flag, env var, and config option
- [multi-agent-setup.md](multi-agent-setup.md) — running all 6 agents at once
- [privacy.md](privacy.md) — redaction + `.llmwikiignore` + localhost-only binding
- [deploy/github-pages.md](deploy/github-pages.md) — deploy to GitHub Pages
- [faq.md](faq.md) — common questions answered
- [troubleshooting.md](troubleshooting.md) — common errors and fixes
- [adapter-authoring.md](adapter-authoring.md) — write your own adapter
- [api-guide.md](api-guide.md) — use llmwiki as a Python library
- [adapters/claude-code.md](adapters/claude-code.md) — Claude Code adapter details
- [adapters/obsidian.md](adapters/obsidian.md) — use an Obsidian vault as an additional source
