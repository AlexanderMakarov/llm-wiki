---
title: "Reader API contract (v1.2+ preview) (part 3/3: Migration path — static → hosted)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-reader-api, static-to-hosted, file-based-api, multi-tenant]
date: 2026-09-28
source_file: 
project: reference-reader-api
model: 
last_updated: 2026-09-28
---
## Summary

This specification outlines a three-phase migration strategy for accessing LLM Wiki content: phase 1 (current) uses static files and exports consumed by external tools; phase 2 wraps these files behind `/api/v1/*` routes via a separate service; phase 3 (v1.3+) enables multi-tenant hosting with per-user auth. The design preserves the static-file generator model—every API endpoint maps to an existing build output, requiring no rewrites to the build pipeline.

## Key Claims

- The current `llmwiki build` outputs HTML, markdown sources, and site-level AI exports that external tools consume directly
- A separate API service can wrap these static files behind `/api/v1/*` routes without modifying `llmwiki/build.py`
- Multi-tenant hosted readers in v1.3+ can reuse the same API routes with per-user authentication without changing the content pipeline
- Every API endpoint in the contract corresponds to a file that `llmwiki/build.py` already produces

## Key Quotes

> "At no point does the contract require a rewrite of `llmwiki/build.py` — every endpoint maps to something build.py already emits."

This captures the core architectural principle: the API contract layers atop existing build outputs, enabling phased migration without disrupting content generation.

> "No new data, just routing — llmwiki itself stays a static-file generator."

The design preserves the static-file nature of the wiki while adding uniform API access, enabling simpler evolution.

## Connections

- [[llmwiki]] (entity) — the static wiki generator providing all content referenced by the API contract
  - fact: Every API endpoint maps to output from `llmwiki/build.py`, `exporters.py`, or `raw_docs_site.py`
  - fact: The build system requires no modifications across all three migration phases
- [[Static Site]] (entity) — the file-based output format serving as the foundation for the API contract
  - fact: External tools currently consume HTML, markdown, and site-level exports directly
  - fact: Phase 2 adds uniform `/api/v1/*` routing over the same files without changing build outputs
- [[Reader API]] (entity) — the contract defining three-phase programmatic access to wiki content
  - fact: Phase 1 (current): external tools read files directly; Phase 2: same files behind API routes; Phase 3: multi-tenant hosting with per-user auth

## Contradictions

None identified in this session.