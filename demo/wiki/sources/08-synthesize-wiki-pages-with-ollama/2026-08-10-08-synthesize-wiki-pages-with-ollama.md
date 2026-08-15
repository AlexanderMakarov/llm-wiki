---
title: "08 · Synthesize wiki pages with Ollama"
type: source
tags: [wiki-add, raw-doc, session-transcript, 08-synthesize-wiki-pages-with-ollama, local-llm, wiki-synthesis, configuration]
date: 2026-08-10
source_file: 
project: 08-synthesize-wiki-pages-with-ollama
model: 
last_updated: 2026-08-11
---
## Summary

This tutorial explains how to configure [[llmwiki]] to synthesize wiki pages using a locally-running [[Ollama]] model instead of the dummy backend or cloud APIs. Users install Ollama, pull a model like llama3.1:8b (4.7 GB on 8 GB RAM), and update sessions_config.json to enable real LLM-written summaries at zero API cost with 2–5 second latency per page on modern hardware.

## Key Claims

- The dummy backend is deterministic and fast but produces skeleton pages; Ollama provides real LLM-written summaries at $0 cost
- llama3.1:8b (4.7 GB) fits in 8 GB RAM; mistral:7b (4.1 GB) and q4_0-quantized variants offer smaller alternatives for constrained hardware
- Synthesis takes 2–5 seconds per session on a modern MacBook; q4_0 quantization reduces model size to ~2.3 GB and speeds up synthesis by ~3×
- The `llmwiki synth --check` command verifies Ollama backend availability; `--estimate` shows token counts ($0 locally, useful for comparing against API cost)
- Local models hallucinate more facts than API-backed synthesis; `llmwiki lint` should be run afterward to catch common errors

## Key Quotes

> "Good for tests, not for reading" — describing the dummy backend's skeleton output, explaining why Ollama synthesis matters

> "no API key, no bill" — the core value proposition of running synthesis locally

> "2–5 seconds per session on a modern MacBook" — real-world performance expectation for capacity planning

## Connections

- [[llmwiki]] — the CLI tool whose synthesis feature is configured in this tutorial
- [[Ollama]] — the local LLM inference framework that becomes the synthesis backend
- [[Claude API]] — the cloud alternative for synthesis; offers higher accuracy but requires API key and billing

## Contradictions

None identified. The tutorial explicitly acknowledges the accuracy/cost tradeoff: local models are cheaper but less accurate, and recommends running `llmwiki lint` afterward to catch hallucinations.