---
title: "Resolve citation key collisions on import"
type: source
tags: [session, session-transcript, paper-notes, claude, bibtex-import, citation-key-collision, deduplication, stable-ordering]
date: 2026-07-17
source_file: raw/sessions/paper-notes/2026-07-17T17-18-paper-notes-bibtex-key-collisions.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

Fixed a silent data loss bug in bibtex import where papers by the same author/year overwrote each other. The solution uses stable-ordered suffix disambiguation for colliding keys, preserves existing keys for citation stability, and detects true duplicates by content hash rather than key collision.

## Key Claims

- Citation keys based on author+year alone cause silent data loss when importing multiple distinct papers from the same author/year
- Disambiguating suffixes appended in stable order resolve collisions deterministically
- The importer now reports all collisions rather than silently resolving them
- Existing keys are preserved to avoid breaking citations already written in documents
- True duplicates are detected by content hash, not key collision

## Key Quotes

> "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly."

> "Existing keys are left alone so citations already written do not shift."

> "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers."

## Connections

- [[Bibtex Import]] (system) — the bibliography import pipeline for paper-notes
  - fact: Original citation key scheme (author+year) creates collisions for distinct papers by same author/year
  - fact: Stable suffix ordering disambiguates keys deterministically
  - fact: Collisions now generate warnings instead of silent overwrites
  - fact: Existing keys are preserved for citation stability
- [[Collision Resolution]] (technique) — handling deterministic key generation with duplicate metadata
  - fact: Content-based duplicate detection distinguishes true duplicates from collision cases, requiring separate handling
