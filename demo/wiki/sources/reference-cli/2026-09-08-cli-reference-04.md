---
title: "CLI reference (part 4/15: graph — build the knowledge graph)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, knowledge-graph, lint-rules, wikilinks, graphify, provenance-integrity]
date: 2026-09-08
source_file: 
project: reference-cli
model: 
last_updated: 2026-09-08
---
## Summary

This reference slice documents `llmwiki graph` (builtin wikilink graph vs optional Graphify engine) and `llmwiki lint` (17 deterministic wiki-quality rules). The builtin graph writes `graph/graph.json` and interactive HTML under `graph/`, with viewer assets copied into `site/` on `build` for offline use. Lint covers structural integrity, catalog sync, link resolution with a harvest-aligned `--min-refs` default of 3, stub sources, provenance chains, and stale cross-page claims; vault-specific rule skips are configured in `llmwiki.json`.

## Key Claims

- `llmwiki graph` defaults to the **builtin** engine (stdlib wikilink graph); **graphify** needs `pip install graphifyy` (or `llm-wiki-plus[graph]`) and writes under `graphify-out/` before copying into `graph/` for build compatibility.
- Default graph output format is **`both`** (JSON and HTML); the builtin HTML path uses vis-network and is bundled into the static site on every `build`, not fetched from a CDN at view time.
- `llmwiki lint` runs **17 deterministic rules** with no LLM callback; `contradiction_detection`, `claim_verification`, and `summary_accuracy` are structural checks as of #72 (non-filler `## Contradictions`, sourced entity/concept claims, non-empty `summary:` frontmatter).
- `--min-refs` defaults to **3** so unresolved `[[wikilink]]` targets that the candidate harvest deliberately declined (fewer than three source mentions) are not reported as `link_integrity` gaps; `--min-refs 1` reports every unresolved link; `0` and negatives exit 2.
- `orphan_detection` treats inbound **wikilinks and resolvable catalog links** from `index.md` as non-orphan inbound edges; `link_integrity` resolves targets case- and punctuation-insensitively but does not substring-match.
- `provenance_integrity` (#122) emits **errors** for broken downward hops when `sources:` or `source_file:` is set, and points operators at `trace`, `synth`, or `migrate broken-provenance` without repairing.
- `stale_reference_detection` (#303 / #87) flags living wiki pages whose dated claims about a target are older than that target’s `last_updated`; `wiki/sources/` and `type: source` pages are excluded.

## Key Quotes

> "Builtin engine: Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html` (vis-network interactive viewer) plus sibling `graph-viewer.js` and `vis-network.min.js`. The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch." — offline graph UX tied to the static site pipeline

> "Default: `3` — the candidate harvest's own threshold, so a target the harvest deliberately declined is not a finding." — explicit alignment between lint and harvest significance

> "`contradiction_detection`, `claim_verification`, and `summary_accuracy` used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks" — lint behavior change and scope of “LLM” rules

## Connections

- [[llmwiki]] (entity) — CLI surface for graph generation and vault linting documented in this part of the reference.
  - fact: `graph` and `lint` are first-class subcommands with vault/`llmwiki.json` integration for lint rule disables.
- [[Knowledge Graph]] (concept) — Built by `llmwiki graph` (builtin wikilinks or Graphify with community detection and confidence-scored edges).
  - fact: Builtin output lives under `graph/`; Graphify uses tree-sitter for code and semantic analysis for docs, with outputs under `graphify-out/`.
- [[Wikilinks]] (concept) — Builtin graph engine is explicitly a wikilink graph; `link_integrity` and `orphan_detection` depend on resolved `[[…]]` targets.
  - fact: Case- and punctuation-insensitive resolution; significance threshold couples to `--min-refs` and harvest (#150).
- [[Static Site]] (concept) — Graph viewer assets are copied into `site/` on `build` for offline viewing.
  - fact: Interactive graph does not require a CDN fetch from the built site.
- [[Lint Rules]] (concept) — Seventeen named rules (`frontmatter_completeness` through `provenance_integrity`) with JSON reporting and CI-friendly exit codes.
  - fact: `--json` includes `ran` so partial `--rules` runs are not mistaken for full scans.
- [[Configuration]] (concept) — Vault `llmwiki.json` can disable inapplicable lint rules; `--wiki-dir` wins over `--vault` for wiki path while still reading config from the vault parent when applicable.
  - fact: Disabled rules appear in reports with recorded reasons.
