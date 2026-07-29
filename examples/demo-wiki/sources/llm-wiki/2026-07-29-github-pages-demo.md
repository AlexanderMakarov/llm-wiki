---
title: "GitHub Pages self-demo"
type: source
tags: [raw-doc, demo, llmwiki, pages, session-transcript, llm-wiki, github-actions, pre-synthesis, demo-deployment]
date: 2026-07-29
source_file: raw/docs/llm-wiki/github-pages-demo.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

The [[llm-wiki]] project uses a GitHub Pages deployment workflow that pre-synthesizes wiki content locally rather than running synthesis in CI. This approach avoids the costs, secret management overhead, and non-determinism of synthesizing in [[GitHub Actions]]. The workflow deploys committed example data (sessions, docs, and synthesized wiki sources), and fork users must explicitly enable [[GitHub Actions]] as the Pages source in repository settings before automatic deploys work.

## Key Claims

- The workflow builds demos exclusively from pre-committed example data—sessions, docs, and synthesized wiki sources—rather than generating content during deployment
- Pre-synthesizing content offline avoids the need for API credentials in CI, eliminates per-deployment costs, and ensures deterministic builds
- [[GitHub Pages]] on a fork requires explicit configuration (Settings → Pages → Source: GitHub Actions) to enable automatic workflow deploys

## Key Quotes

> "Running Claude inside Actions needs secrets, costs money every deploy, and makes the wiki non-deterministic." — the core rationale for offline synthesis

> "Docs are synthesized once locally with the maintainer's Claude backend; CI only copies the result." — how the strategy works in practice

## Connections

- [[llm-wiki]] — the project implementing this deployment strategy
- [[GitHub Pages]] — the static-site hosting platform  
- [[GitHub Actions]] — the CI system executing build and deploy

## Contradictions

None identified. The design is internally consistent: offline synthesis trades real-time interactivity for simplicity, cost control, and determinism.