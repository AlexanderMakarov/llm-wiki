---
title: "What is llmwiki"
type: source
tags: [raw-doc, demo, llmwiki, session-transcript, llm-wiki, knowledge-base, session-synthesis, immutable-transcripts, static-site-gen]
date: 2026-07-29
source_file: raw/docs/llm-wiki/what-is-llmwiki.md
project: llm-wiki
model: 
last_updated: 2026-07-29
---
## Summary

llmwiki is a three-layer system that converts coding-agent session transcripts into queryable personal knowledge bases. It maintains immutable raw transcripts, synthesizes them into a cross-linked wiki with LLM-generated summaries and entities, and generates browsable static HTML—enabling future sessions and humans to reference historical decisions without uploading data to third-party services.

## Key Claims

- Long agent sessions accumulate valuable context (decisions, tool choices, project history) that gets buried unless actively made queryable
- The system architecture uses three immutable layers: `raw/` (source transcripts never edited by hand), `wiki/` (LLM-maintained synthesis), `site/` (generated HTML output)
- llmwiki avoids third-party memory products by keeping all history locally searchable and queryable by the next agent session
- The public demo uses only synthetic/invented sessions and fixture data, not real user transcripts

## Key Quotes

> "Long agent sessions bury decisions, tool choices, and project context. llmwiki makes that history queryable — by you and by the next agent session"

Articulates the core problem llmwiki solves: making session history an asset instead of ephemeral logs.

> "Agent-owned synthesis: source summaries, entities, concepts, index, overview, log"

Describes the structured knowledge artifacts the wiki layer creates from raw transcripts.

## Connections

- [[llm-wiki]] — the product this page introduces
- [[Claude]] — primary agent runtime that feeds sessions into the wiki
- [[Karpathy]] — inspiration for the three-layer personal knowledge base
- [[MCP]] — how editors query the wiki without leaving the IDE
- [[GitHub Pages]] — public demo hosting for this repository
- [[synthesis]] — how raw docs and sessions become wiki source pages

## Contradictions

None identified (foundational documentation for a new system).