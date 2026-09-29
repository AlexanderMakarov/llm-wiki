---
title: "Reader API contract (v1.2+ preview) (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-reader-api, api-contract, static-site-first, build-outputs]
date: 2026-09-28
source_file: 
project: reference-reader-api
model: 
last_updated: 2026-09-28
---
## Summary

Part 1 of 3 of the Reader API contract (v1.2+ preview), which locks the data shapes currently output by the static build to prevent breaking changes to future clients (browser extensions, Raycast plugins, SPA readers, LLM agents). The document catalogs 16+ file types (HTML, JSON, markdown, sitemaps, RSS feeds, etc.) constituting the v1.0+ API surface, establishing that future interfaces will reuse these shapes through different transports rather than requiring new content pipelines.

## Key Claims

- llmwiki is and will remain static-site-first, with the static site serving as the primary API surface for all future clients
- The Reader API contract is frozen (status: contract-only) to protect the build pipeline and `sources/` content from drift caused by downstream client requirements (#116)
- The static build already generates 16+ standardized outputs to `site/`, including search indices, manifests, feed formats, and AI-friendly text representations, forming the v1.0+ API
- Future hosted/SPA readers and LLM agents will consume the same data shapes through different transports without requiring new content generation or pipeline changes

## Key Quotes

> "llmwiki is, and will stay, **static-site-first**." — Establishes the core architectural principle governing all API design decisions

> "Freezing this now protects the build pipeline (`site/` outputs) and the AI-facing markdown under `sources/` from drift (#116)." — Rationale for formalizing the contract early

> "Everything below in this doc describes the **future hosted/SPA surface** that will be fed by the same data shapes — no new content pipeline, just new transports." — Key principle: data reuse across interfaces

## Connections

- [[llmwiki]] (entity) — The project this API contract governs; specifies how the static build outputs will be consumed by future clients
  - fact: 16+ file types currently output by the build serve as the v1.0+ API surface
- [[Static Site]] (entity) — Remains the primary and permanent API surface; future interfaces will layer on top of it rather than replace it
  - fact: All clients (extensions, plugins, SPA readers, agents) consume the same static outputs through different transports
- [[Wiki Synthesis]] (concept) — The build pipeline protected by this contract; locking the API shape prevents breaking changes to downstream dependents
  - fact: The contract freezes output shapes to protect `site/` artifacts and `sources/` markdown from drift

## Contradictions

None identified.