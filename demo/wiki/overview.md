---
title: "Overview"
type: synthesis
sources: []
last_updated: "2026-08-10"
---

# Overview

This is the example vault that ships with llmwiki. Everything under `wiki/` here was produced by running the tool — `sync / add → synth → review candidates → build` — over real agent transcripts, so what you see is what the product actually generates rather than a mock-up of it.

The corpus covers llmwiki's own development: how the command line is structured, how the static site is generated, and how session transcripts are parsed by each adapter. It spans two projects — [[llm-wiki]] and `openclaw-main` — and two session sources, Claude Code and OpenClaw, because a vault normally draws from more than one agent.

The transcripts are real but anonymised: usernames, machine paths, private hostnames and neighbouring project names are replaced before anything is committed, and `scripts/curate_demo_sessions.py` re-audits the result on every run.

Pages under `entities/` and `concepts/` were not written by hand. They were harvested from the cross-references that the source summaries agreed on, then promoted through the candidate review gate — where three variants of the same idea were merged into [[WikiLinks]] and one off-topic candidate was discarded. That review step is a deliberate human gate, not an automatic promotion.

Because these pages come from the pipeline, they carry only what it produces: a title, attributed fact bullets under `## Key Facts`, and the sources that justified them. No page opens with a synthesised description, because nothing in llmwiki writes one.

The three layers are as [[CRITICAL_FACTS]] describes: `raw/` is immutable input, `wiki/` is the generated and human-reviewed layer, and `site/` is the static HTML built from both.

## Connections

- [[llm-wiki]] — the project most of these sessions belong to
- [[WikiLinks]] — how pages cross-reference each other
- [[StaticSiteGeneration]] — how `site/` is produced
- [[OpenClaw]] — the second session source represented here
- [[CRITICAL_FACTS]] — the invariants every page in this vault obeys
