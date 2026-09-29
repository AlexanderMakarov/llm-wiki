---
title: "Resolve citation key collisions on import"
type: source
tags: [session, session-transcript, paper-notes, claude, bibtex-import, citation-key-collision, deduplication, stable-ordering, bibtex-collisions, citation-import, collision-resolution]
date: 2026-08-06
source_file: raw/sessions/paper-notes/2026-07-17T17-18-paper-notes-bibtex-key-collisions.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Two papers by the same author from the same year silently overwrote each other due to BibTeX key collisions. The fix appends disambiguating suffixes in stable order and reports all collisions to the user, with existing keys preserved to avoid breaking citations already written. Content-based duplicate detection distinguishes re-imported papers from distinct papers with matching author-year combinations. The change is interactive-session only; headless paths remain unaffected.

## Key Claims

- Citation keys were originally generated as author + year, causing silent overwrites when the same author published multiple papers in a single year
- The solution appends disambiguating suffixes in stable order and reports all resolved collisions instead of silently overwriting
- Existing keys are preserved to maintain backward compatibility with citations already written in source documents
- Duplicate detection is content-based rather than key-based, distinguishing between re-imported papers and distinct papers with matching author-year signatures  
- This change affects only interactive sessions; headless fixtures remain excluded from default synthesis
- All edge cases including a retry path from previous work are covered by the test suite

## Key Quotes

> "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly." — Core solution approach

> "Existing keys are left alone so citations already written do not shift." — Backward compatibility strategy

> "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers." — Distinguishes duplicate handling from collision resolution

> "No — headless fixtures stay excluded from default synth. This change is interactive-session only." — Defines operational scope

> "Init a throwaway vault, sync once, then search for the durable handle. If rank-1 is wrong, check title collisions first." — Verification strategy for fresh vaults

## Connections

- [[Paper-notes]] (entity) — Citation management project where BibTeX import collisions are resolved with stable suffix generation and collision reporting
  - fact: When the same author publishes multiple papers in one year, citation key collisions are now resolved with stable disambiguating suffixes
  - fact: Existing keys are preserved to maintain backward compatibility with already-written citations
  - fact: Content-based deduplication distinguishes re-imports from genuinely distinct papers with matching author-year signatures