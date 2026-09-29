---
title: "08 · Synthesize wiki pages with Ollama"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-08-synthesize-with-ollama, synthesis-backend, local-inference, quantization]
date: 2026-09-28
source_file: 
project: tutorials-08-synthesize-with-ollama
model: 
last_updated: 2026-09-29
---
## Summary

This tutorial configures [[llmwiki]] to synthesize wiki pages using [[Ollama]], a local LLM runtime, instead of cloud APIs. It covers installation, model selection, configuration via `sessions_config.json`, and workflow for generating summaries at 2–5 seconds per session with zero cost but lower accuracy than commercial APIs. The guide includes troubleshooting, performance tuning with quantized models, and mitigation strategies like [[Lint Rules]] for accuracy issues.

## Key Claims

- The default synthesis backend is `"dummy"`, which is fast for testing but produces only skeleton pages.
- [[Ollama]] must run as a daemon on `127.0.0.1:11434`; llama3.1:8b requires 8 GB RAM and downloads 4.7 GB.
- Local LLM synthesis produces wiki summaries in 2–5 seconds per session on modern hardware.
- Quantized models like `llama3.1:8b-instruct-q4_0` (2.3 GB) run ~3× faster than full-precision models.
- Local models have lower accuracy and may hallucinate; [[Lint Rules]] can catch obvious errors.

## Key Quotes

> "every new session's `wiki/sources/<slug>.md` is synthesized by a local LLM instead of the dummy backend — no API key, no bill."
- Establishes the core value proposition: offline synthesis without cloud costs.

> "Local models have lower accuracy. Run `llmwiki lint` after to catch the obvious hallucinations"
- Highlights the accuracy–cost trade-off and a mitigation strategy.

## Connections

- [[llmwiki]] (entity) — the wiki system configurable to use local LLM synthesis.
  - fact: The default synthesis backend can be overridden via `sessions_config.json`.
- [[Ollama]] (entity) — local LLM runtime exposing `/api/generate` endpoint.
  - fact: Models are pulled from the Ollama library and run as a background daemon.
- [[Wiki Synthesis]] (concept) — process of converting raw sessions into structured wiki pages.
  - fact: Ollama backend supports synthesis workflow with configurable model and timeout.
- [[Configuration]] (entity) — settings for the synthesis pipeline.
  - fact: `synthesis.backend`, `ollama.model`, `base_url`, `timeout`, and `max_retries` are configurable.
- [[Lint Rules]] (concept) — validation checks catching synthesis errors.
  - fact: Lint rules can identify hallucinated facts introduced by local LLMs.
- [[Prompt Caching]] (concept) — optimization for cloud-based synthesis.
  - fact: Recommended when upgrading from Ollama to Claude API for cost efficiency.

## Contradictions

None identified.