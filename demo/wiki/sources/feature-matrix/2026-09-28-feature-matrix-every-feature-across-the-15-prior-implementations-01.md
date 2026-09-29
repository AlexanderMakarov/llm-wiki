---
title: "Feature Matrix — Every Feature Across the 15 Prior Implementations (part 1/3)"
type: source
tags: [wiki-add, raw-doc, session-transcript, feature-matrix, competitive-audit, prior-art, input-adapters, feature-prioritization]
date: 2026-09-28
source_file: 
project: feature-matrix
model: 
last_updated: 2026-09-28
---
## Summary

This is a historical competitive audit and feature matrix from September 2026 cataloging every feature across 15 prior wiki-like implementations, rating each by value to [[llmwiki]] (1–5 stars) and marking which are novel vs. prior art. Organized into five categories—core workflows, [[Adapters]], page types, [[Static Site]] output/viewer, and distribution—the matrix maps each feature to a [[llmwiki]] phase (v0.1–v0.4 or "won't-have"). The document explicitly disclaims accuracy relative to the shipped product and recommends treating it as archive research rather than a live roadmap.

## Key Claims

- The Claude Code `.jsonl` adapter (B1) was a net-new invention with no prior art, marked as a God-level killer feature
- Multiple [[Static Site]] viewer features (command palette, client-side search, syntax highlighting, dark mode, keyboard shortcuts, breadcrumbs, collapsible sections, reading-progress bars) were invented by [[llmwiki]] with no prior art
- [[Adapters]] from Codex CLI and Cursor were shipped to production; [[Gemini CLI]] remains in scaffold phase
- [[Obsidian]] vault adapter, generic markdown, PDF ingestion, and web-clipper ingestion were mapped to v0.1–v0.4 phases with varying priorities
- Some features (Slack/Discord export, TUI browser, single-binary distribution) were explicitly marked "won't-have"
- [[Knowledge Graph]] visualization, comparison pages, and question-page templates were deferred to v0.2 phase

## Key Quotes

> "Status (2026-09): historical planning snapshot from the early competitive audit. Phase labels and 'prior art' rows are stale relative to the shipped product; there is no open GitHub issue dedicated to refreshing this file. Treat [`docs/feature-matrix.md`](feature-matrix.md) as archive research, not a live roadmap."

This self-aware disclaimer acknowledges the document's age and advises readers to consult the actual product state and current issues instead.

> "Method: Cloned and inspected every referenced repo. Listed every feature I found in any of them, rated each by target value to llmwiki (1–5), and marked which ones are already present in at least one reference implementation vs. which are a net-new invention for llmwiki."

Documents the rigorous competitive survey methodology across 15 implementations.

## Connections

- [[llmwiki]] (entity) — the subject of this feature audit and historical roadmap planning
  - fact: Inventor explicitly audited 15 prior implementations and rated 50+ features across five categories
  - fact: Multiple viewer and adapter features are marked as net-new (no prior art) innovations
  - fact: Distribution strategy includes `pip install`, Homebrew, PyPI, and Claude Code marketplace in phases v0.1–v0.3

- [[Adapters]] (entity) — section B systematically catalogs input adapters from various sources
  - fact: [[Codex CLI]] adapter shipped in production; [[Cursor]] (both Agent CLI and IDE) shipped to contrib
  - fact: [[Obsidian]] vault adapter, generic markdown, and [[Gemini CLI]] are v0.1–scaffold phases
  - fact: PDF and URL/web-clipper ingestion deferred to v0.3–v0.4

- [[Static Site]] (entity) — section D covers static output and viewer UI features
  - fact: Static HTML output with no dependencies or authentication rated God-level (v0.1)
  - fact: Command palette, global client-side search, syntax highlighting, dark mode, and keyboard shortcuts all listed as net-new with no prior art

- [[Knowledge Graph]] (concept) — interconnected navigation of wiki entries
  - fact: Knowledge graph visualization using vis.js deferred to v0.2 phase (D17)

  - fact: Vault adapter import mode and export-as-Obsidian both targeted v0.1; bidirectional sync planned v0.2