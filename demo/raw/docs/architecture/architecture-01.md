---
title: "Architecture (part 1/3)"
slug: architecture-01
project: architecture
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/architecture.md"
content_sha256: f9d60b3a6d2545eb672aff3ec89271d5d5daf460c4cf2aa42001fe5d6fdfe471
---

> Part 1 of 3 of **Architecture**.

# Architecture

llmwiki has two overlapping structures:

1. The **Karpathy three-layer wiki** (conceptual): `raw/` → `wiki/` → `site/`
2. The **eight-layer build** (implementation): how responsibilities are distributed across Python modules, HTML templates, scripts, CI, etc.

This document covers both.

## Layer 1: Karpathy's three-layer wiki

From the [original LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f):

```
raw/           IMMUTABLE source documents
    ↓          (llmwiki converts .jsonl → .md here)
wiki/sources/  synthesized session summaries (LLM)
    ↓          (llmwiki synth — default also harvests candidates)
wiki/candidates/  PENDING review stubs for entities/concepts
    ↓          (agent /wiki-candidates → promote|merge|discard; site UI in #97)
wiki/entities/ concepts/   TRUSTED hubs (after review — never auto-promoted)
    ↓
site/          GENERATED static HTML
               (llmwiki builds here via `llmwiki build` — not part of `synth`)
```

Trusted entity/concept hubs require human-or-agent review of candidates. Synthesis alone can leave Home looking “finished” (Raw → Synthesized) while the knowledge layer is still empty — Home’s **Knowledge layer** table (**Candidates | Entities | Concepts**) and Analytics **Candidates to review** make that backlog visible (#84).

### raw/ — immutable layer

Everything under `raw/` is treated as source-of-truth. The converter writes to it; nothing else should. If a source is wrong, fix the converter, not the output.

The converter writes one markdown file per session under `raw/sessions/<project>/<date>-<slug>.md`. Each file has YAML frontmatter (project, started, model, tools_used, gitBranch, etc.) and a Conversation body rendered turn-by-turn.

### wiki/ — LLM-maintained layer

Your coding agent owns this layer entirely. It writes via the Ingest Workflow in [CLAUDE.md](../CLAUDE.md):

```
wiki/
├── index.md          catalog of all pages, updated on every ingest
├── log.md            append-only chronological record
├── overview.md       living synthesis across all sources
├── sources/          one summary page per raw source (kebab-case slug)
├── candidates/       pending entity/concept stubs (harvest; review before promote)
├── entities/         people, products, tools (TitleCase.md)
├── concepts/         ideas, frameworks, patterns (TitleCase.md)
├── projects/         codebases and work streams (kebab-case slug)
└── syntheses/        saved query answers (kebab-case slug)
```

Pages interlink via `[[wikilinks]]`. Contradictions are recorded, not silently overwritten. Pages compound over time — every new source makes the wiki richer.

### site/ — generated static layer

`llmwiki build` reads `raw/` (and `wiki/` if populated) and renders a complete static HTML site. Nothing here is hand-maintained. Safe to delete and regenerate any time.
