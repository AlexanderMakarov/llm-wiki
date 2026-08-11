---
title: "Synthesis backends (v1.4.0+)"
slug: synthesis-backends-v1-4-0
project: synthesis-backends-v1-4-0
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/modes/api/index.md"
content_sha256: 962f9d0bddb3b3d3727e86d2dc6fe77ccc0f74553e0bf1f6beef6fb440ba13df
---

---
title: "API mode"
type: navigation
docs_shell: true
---

> **LOCAL / CLI SYNTHESIS** — no Anthropic HTTP batch API.

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
`llmwiki synth --estimate`. Prompt-caching helpers in
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
llmwiki synth --check
llmwiki synth --estimate
llmwiki synth
```

## Read next

- [Pick your mode](../)
- [Configuration](../../configuration.md#synthesis-backend)
- [Upgrade guide](../../UPGRADING.md)
