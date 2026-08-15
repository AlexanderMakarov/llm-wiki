---
title: "05 · Query your wiki"
type: source
tags: [wiki-add, raw-doc, session-transcript, 05-query-your-wiki, slash-commands, wiki-querying, lint-rules, knowledge-graph]
date: 2026-08-10
source_file: 
project: 05-query-your-wiki
model: 
last_updated: 2026-08-11
---
## Summary

Tutorial documenting the nine slash commands that make [[llmwiki]] useful for querying, linting, and maintaining a personal knowledge wiki. The commands support a query workflow (ask, save, cross-check) and a review workflow (triage candidates) around a core principle of no destructive operations without explicit intent.

## Key Claims

- [[llmwiki]] provides nine slash commands (`/wiki-query`, `/wiki-sync`, `/wiki-ingest`, `/wiki-candidates`, `/wiki-lint`, `/wiki-graph`, `/wiki-build`, `/wiki-serve`, `/wiki-update`, `/wiki-reflect`) for querying and maintaining a wiki
- The ingest is one-time; the real payoff is asking "have I solved this before?" via `/wiki-query`
- `/wiki-query` answers questions by synthesizing from cache-tier-L1 pages and relevant sources, with inline wikilinks that can be saved as first-class wiki pages for future search
- `/wiki-graph` visualizes the knowledge graph; central answer hubs indicate good integration, while orphaned pages signal missing links
- `/wiki-lint` categorizes issues as errors (frontmatter/enum violations; must fix), warnings (broken wikilinks), or info (orphans/aged candidates); runs on the CLI via `python3 -m llmwiki lint`
- `/wiki-candidates` triages new entities non-destructively: promote to `wiki/entities/`, merge into existing page, or discard to archive with reason
- No slash command rewrites user-owned files without explicit prompting

## Key Quotes

> "The ingest is one-time. The payoff is when you ask 'have I solved this before?' and get a confident answer grounded in your own session history." — the core value proposition of the wiki system

> "Nothing destructive without explicit intent. No slash command ever rewrites a file you own without prompting first." — foundational safety principle

> "If your new answer is central to many sessions, it'll be a hub. If it's floating on the edge with no inbound links, the ingest missed something." — how to use graph topology to validate answer coverage

## Connections

- [[llmwiki]] — the core tool; its query interface is the subject of this tutorial

## Contradictions

(none identified)