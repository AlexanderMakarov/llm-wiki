---
title: "CLI reference (part 12/19: source-page-paths — move source pages filed under a stale name)"
type: source
tags: [wiki-add, raw-doc, session-transcript, reference-cli, link-integrity, archived-candidates, offline-migration, source-page-paths]
date: 2026-10-01
source_file: 
project: reference-cli
model: 
last_updated: 2026-10-01
---
## Summary

This is part 12 of the [[llmwiki]] CLI reference, documenting two offline migration commands: `migrate discarded-topic-links` removes or redirects orphaned links to archived candidates (with special protection for merged pages), and `source-page-paths` relocates source pages when their filenames diverge from current naming conventions. Both operate without LLM calls or network access, support dry-run validation, and are idempotent.

## Key Claims

- The `discarded-topic-links` command flattens links to archived candidates outside `wiki/archive/` into plain text (preserving labels) or points them to live pages via `--redirect` flags, which also record aliases on the target page.
- Merged candidates (marked with `Reason: merged into <target>`) are guarded: their links remain in place unless `--force` is explicitly passed, protecting links whose target page no longer answers to the old name.
- The migration is idempotent: a second run reports `nothing to migrate` when no orphaned links or nested stubs remain.
- Nested candidate stubs with slashes in their names (`A/B thing`) are relocated to flat paths (`candidates/<kind>/A-B thing.md`); conflicts are reported instead of overwritten.
- `source-page-paths` solves the problem of source pages filed under stale names that cause synth's duplicate guard to skip them on every run, reported as already claimed by a real page under a different filename.

## Key Quotes

> "No language model, no network call, `raw/` never written." — Both migrations operate offline without invoking synthesis or modifying ingested raw documents.

> "Merged names are guarded." — Links to pages explicitly merged by a reviewer are protected unless the operator explicitly passes `--force`, preventing accidental loss of merge history.

> "Idempotent: a second run finds nothing to rewrite and prints `nothing to migrate`" — The operation is safe to repeat; no changes are applied if already complete.

## Connections

- [[llmwiki]] (entity) — the core system these migration commands maintain and repair.
  - fact: Both commands operate directly on vault structure (`wiki/sources/`, `wiki/candidates/`, `wiki/archive/`) without invoking the LLM or synthesis pipeline.
- [[Wiki Synthesis]] (concept) — these migrations ensure consistency between raw ingested sources and their derived pages.
  - fact: `source-page-paths` fixes the problem where source pages with stale filenames cause synth to skip them as duplicates, breaking `synth --estimate` reporting.

## Contradictions

None identified.