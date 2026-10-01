---
title: "Resolve citation key collisions on import"
type: source
tags: [session, session-transcript, paper-notes, claude, bibtex-import, citation-key-collision, deduplication, stable-ordering, bibtex-collisions, citation-import, collision-resolution, duplicate-detection]
date: 2026-08-09
source_file: raw/sessions/paper-notes/2026-07-17T17-18-paper-notes-bibtex-key-collisions.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

The session fixes a bug in the paper-notes adapter of [[llmwiki]] where importing two papers by the same author from the same year silently overwrote one due to citation key collisions. The fix appends stable disambiguating suffixes to colliding keys and reports each collision transparently, while preserving existing keys to avoid breaking citations. Content-based duplicate detection distinguishes true re-imports (same paper) from key collisions (distinct papers sharing a key). The change is scoped to interactive sessions only.

## Key Claims

- Citation keys based on "author+year" format caused silent overwrites when multiple papers from the same author in the same year were imported
- The fix appends disambiguating suffixes in stable order and makes the importer report every collision rather than silently resolving it
- Existing citation keys are left unchanged to preserve citations already written in notes
- Duplicate detection uses content comparison rather than key matching to identify re-imported papers
- The collision-handling logic is scoped to interactive sessions only and does not affect headless/automated synth workflows
- Behavior is locked in with automated tests to prevent regression

## Key Quotes

> "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly."
— Core fix strategy: the problem, solution approach, and change in user-facing behavior.

> "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers."
— Distinguishes duplicate detection (re-import of same paper) from key collisions (two different papers sharing a key).

## Connections

- [[llmwiki]] (entity) — the wiki system that includes the paper-notes adapter
  - fact: paper-notes is a component within llmwiki that ingests academic papers via BibTeX
- [[Adapters]] (entity) — pluggable ingestion components for external data sources
  - fact: paper-notes follows the adapter pattern to transform BibTeX imports into wiki pages
- [[Paper Notes]] (entity) — the academic paper citation handler adapter within llmwiki
  - fact: manages citation key generation and deduplication for imported papers
- [[Citation Key Collisions]] (concept) — when multiple distinct sources receive the same identifier during import
  - fact: occurs in BibTeX when author and year are not unique enough to distinguish papers
- [[Duplicate Detection]] (concept) — identifying and skipping re-imported content during ingestion
  - fact: uses content hashing rather than key matching to distinguish true re-imports from legitimate collisions

## Contradictions

None identified.