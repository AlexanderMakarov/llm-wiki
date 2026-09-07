---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, competitive-audit, product-design, adapters]
date: 2026-09-07
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-07
---
## Summary

A comprehensive competitive audit across 15 prior knowledge-base and wiki implementations, cataloging ~80+ features rated by value to [[llmwiki]] on a 1–5 star scale and marking which are novel innovations vs. existing patterns. The document explicitly disclaims itself as a historical planning snapshot from early 2026-09 and directs readers to treat it as archive research rather than current roadmap, with current priorities tracked in separate product documents and open issues.

## Key Claims

- Multiple UI/UX features in the viewer layer are marked with no documented prior art: command palette, global client-side search, syntax highlighting, dark mode toggle, keyboard shortcuts (/, `g h`, `j/k`), and breadcrumbs—positioning these as llmwiki innovations.
- The [[Claude Code]] `.jsonl` adapter (feature B1) is rated ⭐⭐⭐⭐⭐ (god-level) with no prior art, identified as a killer differentiator feature.
- [[Codex CLI]] adapter and [[Cursor]] adapters (CLI and IDE modes) are listed as shipped at the time of this audit, contradicting the document's own staleness warning.
- Features rated ⭐⭐⭐⭐⭐ (god-level) are framed as essential—where llmwiki "is pointless" without them—including wiki-ingest, wiki-query, wiki-lint, static HTML output, and core command palette/search affordances.
- Five architectural layers organize the feature set: core workflows (A), input [[Adapters]] (B), page types/templates (C), output/viewer (D), and distribution (E), with adapter integrations ranging from shipped (Codex CLI, Cursor) to planned (Gemini CLI, PDF, web-clipper).

## Key Quotes

> "Status (2026-09): historical planning snapshot from the early competitive audit. Phase labels and 'prior art' rows are stale relative to the shipped product… Treat `docs/feature-matrix.md` as archive research, not a live roadmap — prefer `context/product/roadmap.md` and open issues for current priorities."

This disclaimer explicitly marks the document as obsolete relative to the shipped product, warning readers against using it for current planning decisions.

## Connections

- [[llmwiki]] (system) — subject of competitive analysis, organized into five architectural layers
  - fact: god-level features (⭐⭐⭐⭐⭐) include wiki-ingest, wiki-query, wiki-lint, [[Static Site]] HTML output, command palette, and global search.
- [[Adapters]] (concept) — section B catalogs 11 input adapters; Codex CLI and Cursor (both CLI and IDE) marked shipped; Claude Code `.jsonl` adapter rated as killer feature with no known prior implementations.
  - fact: B7 (OpenCode/OpenClaw) listed as shipped contrib; B6 (Gemini CLI) listed as scaffold contrib; B8–B11 (PDF, URL, images, Slack/Discord) planned for v0.3–v0.4 or rejected.
- [[Knowledge Graph]] (feature) — features A6 (wiki-graph networkx/vis.js, v0.2) and D17 (knowledge graph visualization, v0.2) rated as should-haves.
- [[Claude Code]] (tool) — feature B1 (`.jsonl` adapter) identified as unique killer differentiator, ⭐⭐⭐⭐⭐.
- [[Codex CLI]] (tool) — feature B2 marked "shipped (production)" at time of audit.
- [[Cursor]] (tool) — features B5 (Agent CLI) and B5b (IDE adapter) marked "shipped (contrib)".
- [[Obsidian]] (tool) — features B3 (vault input mode) and D18 (export/bidirectional viewer) reference Obsidian integration across input and output layers.

## Notes

- The document marks features B2 (Codex CLI), B5–B5b (Cursor), B6–B7 (Gemini, OpenCode adapters) as "shipped" or "scaffold", yet simultaneously warns that "phase labels and prior art rows are stale relative to the shipped product." Readers must verify actual status in current product releases and [[llmwiki]] open issues rather than treating this matrix as authoritative for deployment or feature availability.