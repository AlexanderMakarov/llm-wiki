---
title: "CLI reference (part 11/15: install-agent-kit — copy packaged slash commands and skills (#109))"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, agent-kit, knowledge-graph, provenance-tracing, cli-reference]
date: 2026-09-07
source_file: raw/docs/reference-cli/cli-reference-11.md
project: reference-cli
model: 
last_updated: 2026-09-07
---
## Summary

This documentation page synthesizes part 11 of 15 of the [[llmwiki]] CLI reference, covering four commands: `install-agent-kit`, `version`, `query`, and `trace`. The primary focus is `install-agent-kit`, which copies packaged agent commands and skills to user-specified directories while preserving customizations through content-hash-based pruning and manifest tracking. Supporting commands enable version reporting, knowledge graph search via the optional Graphify extension, and provenance tracing back to raw transcripts.

## Key Claims

- `install-agent-kit` requires an explicit `--dest` directory and uses SHA256 content hashing to identify files llmwiki previously wrote, enabling safe pruning of retired commands.
- User customizations are never silently overwritten; files with differing content receive `.bak` backups before replacement.
- A `.llmwiki-agent-kit.json` manifest tracks installed file versions and digests, enabling safe re-installation and cleanup across package upgrades.
- Contributor-only commands (`fix-bug`, `maintainer`, `release`) and skills are excluded from the distributed kit and remain in the repository's `.claude/` directory.
- `query` requires the `llm-wiki-plus[graph]` extension (Graphify) and performs breadth-first graph traversal with configurable depth and token budget.
- `trace` walks wiki page provenance through frontmatter metadata back to raw transcripts, marking missing hops but completing successfully.

## Key Quotes

> "Pruning is gated on content, never on the name: a file is deleted only while it still hashes to a revision llmwiki is known to have written at that path."

This approach ensures user customizations and independently created files are never accidentally removed, even if similarly named to retired commands.

> "a customisation is never overwritten silently... saved as `<filename>.bak` beside it before the kit version is written"

The backup mechanism protects user modifications during upgrades, allowing safe recovery if needed.

> "Contributor-only commands... stay in this repository's `.claude/` tree and are not part of the kit."

Establishes the separation between distributed package commands and internal maintainer-only commands used in development.

## Connections

- [[llmwiki]] (project) — The CLI tool documented in this reference page.
  - fact: Provides `install-agent-kit`, `version`, `query`, and `trace` subcommands with specified flags and documented behaviors.

- [[Knowledge Graph]] (concept) — The `query` command provides search capabilities over the knowledge graph.
  - fact: Requires the optional Graphify extension and supports `--depth` and `--budget` flags to control traversal depth and output size.

## Contradictions

None identified.