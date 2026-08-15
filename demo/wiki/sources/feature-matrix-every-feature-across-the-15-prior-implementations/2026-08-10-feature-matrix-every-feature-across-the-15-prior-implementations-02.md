---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 2/3: G · Infrastructure)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix-every-feature-across-the-15-prior-implementations, implementation-phases, privacy-redaction]
date: 2026-08-10
source_file: 
project: feature-matrix-every-feature-across-the-15-prior-implementations
model: 
last_updated: 2026-08-11
---
## Summary

This document is part 2 of a 3-part comprehensive feature matrix comparing functionality across 15 prior LLM wiki implementations. It catalogs 60+ features across infrastructure (G), search/discovery (H), testing (I), CI/CD (J), documentation (K), configuration (L), privacy & security (M), UX (N), and operational concerns (O). Features are ranked by value (1–5 stars), traced to prior art where it exists, and mapped to implementation phases (v0.1 MVP, v0.2 near-term, v0.3 longer-term, or explicit "won't"). Notable findings: several privacy features and search capabilities are claimed to be novel, MCP server integration is marked as high-priority (5-star, v0.2), and snapshot-based adapter testing is explicit over prior work.

## Key Claims

- **MCP server integration** (expose wiki as tools to agents) is a 5-star priority scheduled for v0.2, indicating it is core to the product strategy — Prior art: bitsofchris, lucasastorian
- **Client-side fuzzy search with JSON index** (H1) has no documented prior art and is rated 5-star for v0.1, suggesting the team sees novelty in this specific implementation choice
- **Privacy redaction features** (username, API keys, email) are all rated 5-star and show "**None**" for prior art, implying these are bespoke hardened features for llmwiki
- **Snapshot testing for adapters** (I2) is explicitly noted as having no prior art precedent despite 5-star value, suggesting a novel testing methodology
- The roadmap explicitly defers several features to "won't" (e.g., Supabase/Postgres backend G6, Sentry tracking G7, loading states N7), making tradeoffs explicit
- **Gitleaks secret scanning in CI** (I6, J-level) appears across both Testing and CI/CD sections, indicating it is treated as a critical gate across the pipeline

## Key Quotes

> "**MCP server (expose wiki as tools to agents)** — ⭐⭐⭐⭐⭐ — bitsofchris, lucasastorian — v0.2"

This signals that agent integration (making the wiki queryable by other LLMs via MCP) is a core design goal for near-term release, borrowed from established prior art but prioritized highly.

> "**Client-side search index (JSON + fuzzy matcher)** — ⭐⭐⭐⭐⭐ — **None** — v0.1"

Indicates the team chose to build its own fuzzy search rather than depend on server-side FTS, and considers this fundamental enough for MVP.

## Connections

- [[LLM Wiki]] — this is the feature roadmap and design specification for the system
- [[MCP Integration]] — called out as 5-star priority, appears in both infrastructure (G4) and documentation (K9)
- [[Privacy by Design]] — section M establishes redaction, gitleaks scanning, and local-only operation as non-negotiable
- [[Snapshot Testing]] — section I2 suggests a novel testing strategy for adapters with no prior art

## Contradictions

None identified; this is a forward-looking specification with no prior wiki pages to contradict.