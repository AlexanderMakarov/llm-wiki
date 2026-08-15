---
title: "07 · Example workflows"
type: source
tags: [wiki-add, raw-doc, session-transcript, 07-example-workflows, prompt-caching, github-pages, obsidian-integration, cost-estimation]
date: 2026-08-10
source_file: 
project: 07-example-workflows
model: 
last_updated: 2026-08-11
---
## Summary

The tutorial presents four end-to-end workflows for adopting [[llm-wiki]] across different user types: solo developers using [[Claude Code]] for daily sync/query, teams with shared wikis deployed via [[GitHub Pages]] on CI, existing [[Obsidian]] users adding wiki pages as a vault overlay, and users previewing costs before enabling paid synthesis backends. It recommends choosing a single workflow to start with and provides specific cadences, command sequences, and verification signals for each.

## Key Claims

- The daily developer loop costs ~5 minutes upfront setup and ~30 seconds per day in sync/query overhead.
- Team wikis achieve non-destructive, conflict-free merging because each session gets a unique `<date>-<slug>` filename.
- [[Prompt Caching]] reuses stable prefixes (schema, index, overview) across all sessions, delivering 50–90 % cost savings on Anthropic synthesis.
- The DummySynthesizer provides free, offline wiki functionality (with canned synthesis text) as a preview before enabling Ollama or Anthropic backends.
- Users should start with Workflow 1 (solo/daily) for one week, then move to Workflow 2 (team) only when a second person requires it.

## Key Quotes

> "Pick the workflow that matches your day-job and copy it." — establishes pragmatism: these are copy-paste-ready, not prescriptive templates.

> "Two devs sync to separate branches, each gets their own set of `wiki/sources/<project>/<date>-<slug>.md` files. Merging is conflict-free because every session has a unique timestamp." — core architectural insight enabling frictionless team collaboration.

> "Cache-control plumbing in `llmwiki/cache.py` ensures Anthropic prompt-caching reuses the stable prefix (CLAUDE.md schema + index + overview) across every session — that's where the 50–90 % savings come from." — explains how the cost optimization mechanism works.

> "Don't try to run all four. Start with Workflow 1 (solo / daily) for a week." — adoption best practice to prevent overwhelm.

## Connections

- [[Claude Code]] — the primary interface for Workflow 1 ("80 % of their coding"); links to [[Tutorial 03]]
- [[Obsidian]] — Workflow 3 allows existing vault users to overlay llm-wiki without migration
- [[Prompt Caching]] — the technical foundation for Workflow 4's cost estimation and ongoing 50–90 % savings
- [[GitHub Pages]] — deployment mechanism in Workflow 2; triggered on master push via CI workflow

## Contradictions

None detected. Workflows are presented as complementary entry points for different user types and adoption phases.