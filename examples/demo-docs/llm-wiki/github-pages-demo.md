---
title: "GitHub Pages self-demo"
slug: github-pages-demo
project: llm-wiki
type: source
tags: [raw-doc, demo, llmwiki, pages]
date: 2026-07-29
source: examples/demo-docs/llm-wiki/github-pages-demo.md
---

# GitHub Pages self-demo

The workflow `.github/workflows/pages.yml` builds a public demo from committed examples only:

1. `llmwiki init`
2. Seed `raw/sessions/` from `examples/demo-sessions/` (and test fixtures)
3. Seed `raw/docs/` from `examples/demo-docs/`
4. Seed pre-synthesized `wiki/sources/` from `examples/demo-wiki/`
5. Seed `usage/` from `examples/demo-usage/` (MCP telemetry fixtures)
6. `llmwiki build --out ./site` and deploy

## Why pre-synthesize

Running Claude inside Actions needs secrets, costs money every deploy, and makes the wiki non-deterministic. Docs are synthesized once locally with the maintainer's Claude backend; CI only copies the result.

## Enabling Pages on a fork

Settings → Pages → Source: **GitHub Actions**. Until that is set, automatic push deploys fail at `configure-pages`. Manual `workflow_dispatch` is enough for a smoke test after Pages is enabled.
