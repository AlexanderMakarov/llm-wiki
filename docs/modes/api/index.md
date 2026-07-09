---
title: "API mode"
type: navigation
docs_shell: true
---

<div style="background: #7C3AED; color: white; padding: 8px 16px; border-radius: 6px; font-weight: 600; margin-bottom: 24px;">LOCAL / CLI SYNTHESIS — no Anthropic HTTP batch API.</div>

# Synthesis backends (v1.4.0+)

The planned Anthropic HTTP **API mode** (batch + prompt-cache backend)
and the agent-delegate pending-prompt flow were **not shipped** as
production backends. v1.4.0 supports:

| Backend | Config | Docs |
|---|---|---|
| `dummy` | default | offline stubs for tests |
| `ollama` | `synthesis.backend: ollama` | [Tutorial 08](../../tutorials/08-synthesize-with-ollama.md) |
| `claude` | `synthesis.backend: claude` | [Agent / Claude CLI](../agent/) |

Cost estimates still use the rate card in `model_pricing.csv` /
`llmwiki synthesize --estimate`. Prompt-caching helpers in
`llmwiki/cache.py` remain for estimate math; there is no
`sync --batch` or `.llmwiki-batch-state.json` path.

## Setup (Claude CLI)

```json
{
  "synthesis": {
    "backend": "claude",
    "claude_model": "sonnet"
  }
}
```

```bash
llmwiki synthesize --check
llmwiki synthesize --estimate
llmwiki synthesize
```

## Read next

- [Pick your mode](../)
- [Configuration](../../configuration.md#synthesis-backend)
- [Upgrade guide](../../UPGRADING.md)
