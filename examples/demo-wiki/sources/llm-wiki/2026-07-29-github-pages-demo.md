---
title: "GitHub Pages self-demo"
type: source
tags: [raw-doc, demo, llmwiki, pages, session-transcript, llm-wiki, github-actions, ci-deployment, pre-synthesis]
date: 2026-07-29
source_file: raw/docs/llm-wiki/github-pages-demo.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

This document describes the automated GitHub Pages deployment pipeline for llm-wiki. The `.github/workflows/pages.yml` workflow copies pre-synthesized example content (sessions, docs, wiki sources, usage data) into a built site, deploying it without running Claude in CI. The key insight is that content synthesis happens locally with the maintainer's Claude backend; CI's role is only to assemble and publish the result, avoiding secrets, per-deploy costs, and non-determinism.

## Key Claims

- The GitHub Pages workflow seeds the demo from five committed example directories (`examples/demo-{sessions,docs,wiki,usage}/` and test fixtures), then runs `llmwiki build` to generate the site
- Running Claude synthesis inside GitHub Actions is problematic due to secret management, per-deploy costs, and loss of reproducibility
- Pre-synthesized docs eliminate the need to request Claude API access within CI pipelines
- Enabling GitHub Pages on a fork requires explicitly setting **Settings → Pages → Source: GitHub Actions** first; automatic push deploys fail without this configuration, though manual `workflow_dispatch` can smoke-test once enabled

## Key Quotes

> "Running Claude inside Actions needs secrets, costs money every deploy, and makes the wiki non-deterministic."
— Core justification for the pre-synthesis architecture

> "Docs are synthesized once locally with the maintainer's Claude backend; CI only copies the result."
— Describes the split between local work and CI responsibilities

## Connections

- [[GitHub Pages]] — the hosting platform for the public demo
- [[GitHub Actions]] — automates the build and deployment pipeline
- `llmwiki` CLI — invoked in the workflow (init, build, deploy steps)
- Example directories — committed templates and fixtures that seed each build

## Contradictions

- None identified.