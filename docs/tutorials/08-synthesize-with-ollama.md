---
title: "Synthesize wiki pages with Ollama"
type: tutorial
docs_shell: true
---

# 08 · Synthesize wiki pages with Ollama

**Time:** 15 min (including Ollama install).
**You'll need:** [Ollama](https://ollama.com/) running locally + at
least 8 GB RAM for `llama3.1:8b`.
**Result:** every new session's `wiki/sources/<slug>.md` is synthesized
by a local LLM instead of the dummy backend — no API key, no bill.

## Why this matters

The default `synthesis.backend` is `"dummy"` — fast, deterministic,
but the page it produces is a skeleton.  Good for tests, not for
reading.  When you want actual LLM-written summaries **without** a
Claude / OpenAI API key, point the pipeline at a local Ollama model.

## Steps

### 1. Install Ollama

macOS:

```bash
brew install ollama
ollama serve &   # background daemon on 127.0.0.1:11434
```

Linux: `curl -fsSL https://ollama.com/install.sh | sh` then `systemctl enable --now ollama`.

### 2. Pull a model

```bash
ollama pull llama3.1:8b     # 4.7 GB, fits on 8 GB RAM
# or
ollama pull mistral:7b      # 4.1 GB
```

### 3. Configure `sessions_config.json`

Create or edit `sessions_config.json` at your repo root:

```jsonc
{
  "synthesis": {
    "backend": "ollama",
    "ollama": {
      "model": "llama3.1:8b",
      "base_url": "http://127.0.0.1:11434",
      "timeout": 60,
      "max_retries": 3
    }
  }
}
```

Defaults if omitted: `llama3.1:8b` at `127.0.0.1:11434`, 60s timeout,
3 retries with exponential backoff.

### 4. Check the backend

```bash
llmwiki synth --check
```

Expected:

```
Backend: OllamaSynthesizer
Available: True
```

If `Available: False`, Ollama isn't running — `ollama serve &`.

### 5. Estimate cost (dry-run math)

```bash
llmwiki synth --estimate
```

Ollama backend cost is $0 — the estimator still shows token counts
so you can compare against an API run later:

```
Corpus:                785 eligible sources (785 sessions + 0 docs)
Already synthesized:   714 of 785 eligible sources
Source pages (current state): 700 on disk (700 sessions + 0 docs + 0 stubs)
New since last run:     71

Prefix: 3,944 tok  Model: llama3.1:8b  (local, $0)
```

### 6. Run synthesize

```bash
llmwiki synth
```

Each new raw session becomes a `wiki/sources/<project>/<YYYY-MM-DD>-<slug>.md`.
Expect 2–5 seconds per session on a modern MacBook.

### 7. Inspect the output

```bash
ls wiki/sources/<your-project>/ | head
cat wiki/sources/<your-project>/$(ls wiki/sources/<your-project>/ | head -1)
```

The frontmatter is the same as the dummy backend; the body is the
LLM's prose (one-paragraph summary + key claims + connections).

## Verify

```bash
llmwiki build
```

Open `site/index.html` and browse to a session page; the body should be an actual summary, not
the canned "Auto-synthesis — replace with actual quotes from the
session" placeholder.

## Troubleshooting

### `OllamaUnavailableError: connection refused`

Ollama isn't running. `ollama serve &` or check `lsof -i :11434`.

### `OllamaHTTPError: 404 /api/generate`

Old Ollama version. `ollama --version` — upgrade to 0.1.31+.

### Synthesize is slow (>30s per session)

Use a smaller model: `ollama pull llama3.1:8b-instruct-q4_0` and set
`"model": "llama3.1:8b-instruct-q4_0"` in the config. The q4_0
quantization is ~2.3 GB and ~3× faster.

### Model hallucinates facts about the session

Local models have lower accuracy. Run `llmwiki lint` after to catch
the obvious hallucinations (`frontmatter_validity`, `duplicate_detection`).

For higher quality, switch to API mode — the Claude API backend is
tracked under [#315](https://github.com/Pratiyush/llm-wiki/issues/315).

## Next

- **[Query your wiki](05-querying-your-wiki.md)** — `/wiki-query`
  synthesizes answers from the wiki you just populated.
- **[CLI reference — `synthesize`](../reference/cli.md#synthesize--llm-backed-source-page-synthesis)**
  for every flag.

## See also

- [Prompt caching + batch API](../reference/prompt-caching.md) — when
  you upgrade from Ollama to the Claude API, this is how to keep cost
  under control.
- [Ollama model library](https://ollama.com/library) — the full set of
  local models.
