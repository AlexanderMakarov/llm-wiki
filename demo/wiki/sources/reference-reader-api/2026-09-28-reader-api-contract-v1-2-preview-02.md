---
title: "Reader API contract (v1.2+ preview) (part 2/3: Future endpoint contract)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-reader-api, api-specification, data-invariants, versioning-strategy]
date: 2026-09-28
source_file: 
project: reference-reader-api
model: 
last_updated: 2026-09-28
---
## Summary

This document specifies the [[Reader API]] (v1.2+) contract—a JSON wrapper over files already produced by `llmwiki build`. It defines four endpoints (bootstrap, article, search, sync) with explicit client contracts, establishes data model invariants for client dependencies, and outlines versioning and content negotiation strategies for static site delivery.

## Key Claims

- The Reader API's four endpoints map 1:1 to files already produced by `llmwiki build`; the server acts as a thin JSON wrapper over static content.
- Slugs are stable identifiers set at ingest time and never change on rebuild; renames produce a new slug with a redirect stub.
- The `cache_tier` field is constrained to one of four values: L1, L2, L3, L4 (defaults to L3 when missing).
- The `lifecycle` field must be one of: draft, reviewed, verified, stale, archived.
- The `confidence` field, when present, must be in the range [0, 1]; never represented as a percentage.
- Breaking changes to the API bump the major version (v1 → v2) while keeping the previous version live for one minor release.
- The `/api/v1/bootstrap` endpoint is cacheable for 5 minutes and never returns partial data during rebuilds.
- Wikilinks in API responses resolve to slugs, not URLs; clients perform final URL resolution via the index.

## Key Quotes

> "Every endpoint below maps 1:1 to a file that `llmwiki build` already produces. The server is a thin JSON wrapper; the content model is what's already on disk." — Clarifies that the Reader API is a data format adapter over existing build artifacts, not a new computational layer.

> "Safe to cache for 5 minutes. Never returns partial data — if the site rebuilds mid-request, the server serves the previous full payload until the new one is ready." — Establishes cache semantics and consistency guarantees for safe client-side caching.

> "The reader MUST gracefully render when optional fields are missing (a newly ingested page may not have `confidence` or `cache_tier` yet)." — Specifies client robustness requirements for handling incomplete metadata during incremental ingestion.

## Connections

- [[Reader API]] (entity) — the JSON API wrapper being formally specified
  - fact: Four endpoints (bootstrap, article, search, sync) map 1:1 to files produced by `llmwiki build`.
- [[llmwiki]] (entity) — the system whose build artifacts the Reader API wraps
  - fact: The Reader API serves static files already produced during the llmwiki build phase.
- [[Static Site]] (entity) — the static site delivery model preserved by the API contract
  - fact: The API maintains existing static paths and uses content negotiation to avoid disrupting caches and proxies.
- [[Wiki Synthesis]] (concept) — the build process that generates files the API exposes
  - fact: Bootstrap and article endpoints serve metadata and content created during the synthesis phase.
- [[Knowledge Graph]] (concept) — the graph structure accessible through API wikilinks
  - fact: Wikilinks in API responses resolve to slugs rather than URLs, allowing clients to navigate the graph.

## Contradictions

None identified.