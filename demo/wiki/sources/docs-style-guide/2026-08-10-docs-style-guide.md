---
title: "Docs style guide"
type: source
tags: [wiki-add, raw-doc, session-transcript, docs-style-guide, documentation-style, tutorial-structure, editorial-standards, content-validation]
date: 2026-08-10
source_file: 
project: docs-style-guide
model: 
last_updated: 2026-08-11
---
## Summary

A comprehensive style guide for documentation in the [[llm-wiki]] project establishing unified voice, structure, and editorial standards. It enforces minimalist, evidence-first language; defines a mandatory tutorial skeleton with seven required sections in strict order; specifies code block and linking conventions; and prescribes an automated guardrail test that validates structural compliance.

## Key Claims

- All tutorials under `docs/tutorials/` must follow an identical skeleton with required sections in order: header, Why, Steps, Verify, Troubleshooting, Next. The `test_docs_structure.py` guardrail enforces this.
- The documentation voice should be minimalist and evidence-first: "Show the command. Show the expected output. Show a number. Everything else is vapor." Adjectives are prohibited without numeric evidence.
- Exclamation marks, emoji (except ✓/✗ in tables/headers), videos, custom callout syntax, TL;DR sections, and raw HTML are explicitly forbidden.
- Tutorial titles must match filenames exactly (`NN · Short verb phrase`); all relative links within `docs/` must resolve to real files; external links must use canonical URLs and tagged versions, never `master`.

## Key Quotes

> "**Evidence-first.** Show the command. Show the expected output. Show a number. Everything else is vapor." — encapsulates the entire editorial philosophy

> "Give numbers. '647 sessions, 93 sub-agents, 5 s incremental.'" vs. "Adjectives without numbers. 'Fast, scalable, robust.'" — concrete example of what counts as evidence

> "Don't narrate your narration. 'In this tutorial we'll…' is a tax on the reader. Start with the work." — justifies the task-oriented structure and rejects meta-commentary

## Connections

- [[llm-wiki]] — this is the authoritative style guide for the project's documentation

## Contradictions

None identified (no existing wiki topics to contradict).