---
title: "CLI reference (part 6/15: synth — synthesize sources + harvest candidates)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, source-synthesis, candidate-extraction, cost-estimation, auto-tagging]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-06.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This reference documentation describes the `synth` CLI command, which synthesizes pending sources into wiki pages and harvests entity/concept candidates. It implements a two-phase architecture: source summarization via LLM, then candidate harvesting via parsing only (zero LLM cost). The page documents all command-line flags, configuration options, cost estimation features, graceful interrupt handling, and auto-tagging support.

## Key Claims

- Synth runs a two-phase synthesis: (1) prepare known-names from existing wiki, (2) summarize each source with LLM, then (3) harvest candidates via parsing (zero LLM cost)
- Candidate harvesting reads only Connections bullets from already-synthesized sources; no classify LLM call is made
- The `--estimate` flag provides cost metrics in eligible-source units (not file counts) and shows pre-run candidate state (not a forecast)
- Ctrl+C gracefully drains in-flight synthesis and harvests completed work, exiting with code 130 (unless `--sources-only`)
- Auto-tagging embeds suggested tags as HTML comments in synthesizer output; the pipeline parses, strips, and merges them into frontmatter
- Candidates become harvestable when N or more distinct source pages name them (default: 3 via `--min-refs`)

## Key Quotes

> "A real sources pass is **two language-model jobs**, then bookkeeping: (1) prepare known-names once at the start of the run ... (2) **one** source-summary ask per queued raw file, with that frozen list in the prompt."

— Defines the two-phase cost model and known-names preparation.

> "Harvest after sources is a parser over those bullets — **no** classify LLM call; cost for harvest alone is **zero** LLM."

— Candidate extraction is free; no LLM inference required.

> "The synthesizer emits a `<!-- suggested-tags: prompt-caching, rag, github-actions -->` block as the first line of its response; the pipeline parses it, strips it from the body, and merges the tags into frontmatter"

— How auto-tagging flow works.

## Connections

- [[llmwiki]] (project) — synth is the primary synthesis command
  - fact: default behavior runs both source synthesis and candidate harvest
- [[Wiki Synthesis]] (concept) — synth implements automated source aggregation and connection extraction
  - fact: harvest phase uses only parsing, not LLM calls
- [[Knowledge Graph]] (concept) — synthesized candidates populate the graph
  - fact: candidates are extracted from Connections topic bullets
- [[Codex CLI]] (tool) — synth is a subcommand offering fine-grained control via flags
- [[Configuration Reference]] (documentation) — synth backend and concurrency are configurable