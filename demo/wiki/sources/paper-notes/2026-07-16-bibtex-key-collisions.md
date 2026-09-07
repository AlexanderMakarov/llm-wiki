---
title: "Resolve citation key collisions on import"
type: source
tags: [session, session-transcript, paper-notes, claude, bibtex-key-collisions, import-deduplication, stable-ordering]
date: 2026-07-16
source_file: raw/sessions/paper-notes/2026-07-16T17-18-paper-notes-bibtex-key-collisions.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

A paper bibliography importer was silently discarding data when multiple papers by the same author from the same year generated identical citation keys. The fix appends stable disambiguating suffixes to colliding keys, surfaces collisions in import reports instead of silently overwriting, and uses content-based duplicate detection to distinguish true duplicates (same paper re-imported) from collisions (distinct papers with the same key).

## Key Claims

- Citation keys were generated from `author+year`, causing silent data loss when the same author published multiple papers in one year
- Disambiguating suffixes in stable order (e.g., `a`, `b`, `c`) now distinguish colliding keys
- The importer explicitly reports every collision instead of silently overwriting
- Existing keys in the database are preserved to avoid breaking citations already embedded in notes
- Duplicate detection relies on content comparison, not key identity, allowing safe re-import of the same paper
- Collisions (distinct papers with identical keys) and duplicates (same paper imported multiple times) are handled as separate cases

## Key Quotes

> "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly."

Crystallizes the root cause and the two-part solution (suffixing and visibility).

> "Existing keys are left alone so citations already written do not shift."

Explains the backward-compatibility constraint: preserving key stability for already-written citations.

> "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers."

Clarifies the distinction: duplicates are content-based; collisions are key-based.

## Connections

None to canonical wiki topics; this is a self-contained domain-specific fix for academic bibliography management.

## Contradictions

None.