---
title: "01 · Installation"
type: source
tags: [wiki-add, raw-doc, session-transcript, tutorials-01-installation, local-deployment, agent-adapters, python-setup]
date: 2026-10-01
source_file: 
project: tutorials-01-installation
model: 
last_updated: 2026-10-01
---
## Summary

This tutorial guides users through installing llmwiki from PyPI, source clone, or Docker on systems with Python 3.12+ and git. It emphasizes that llmwiki runs entirely locally with no telemetry, and provides verification steps to check installation and which agent adapters are configured on the user's machine.

## Key Claims

- llmwiki requires Python 3.12 or newer and git to run
- llmwiki is distributed on PyPI as `llm-wiki-plus` to avoid collision with an unrelated package already named `llmwiki`
- All session transcripts stay local on the user's machine with no telemetry, cloud accounts, or network calls at build time
- The `llmwiki adapters` command lists which AI agent session stores are configured on the user's system and which are available to sync
- Setup scripts (setup.sh on Unix-like systems, setup.bat on Windows) are idempotent and can be re-run safely

## Key Quotes

> "llmwiki runs **locally**. Every session transcript stays on your machine. No telemetry, no account, no network calls at build time."

This statement encapsulates the core value proposition and privacy model that differentiates llmwiki from cloud-based alternatives.

> "The PyPI distribution name is `llm-wiki-plus` (PyPI already has an unrelated `llmwiki`, and rejects `llm-wiki` as too similar)."

This explains a critical packaging decision that users must understand to correctly discover and install the tool.

## Connections

- [[llmwiki]] (entity) — the subject of installation and configuration taught in this tutorial
  - fact: Available via three distribution methods: PyPI (`llm-wiki-plus`), source clone, and Docker
  - fact: Verified using `llmwiki --version` and `llmwiki adapters` commands
- [[Adapters]] (concept) — the tutorial teaches users to check which AI agent session stores are configured on their system
  - fact: The `llmwiki adapters` command reveals which agents have session history available for the first sync

## Contradictions

None identified.