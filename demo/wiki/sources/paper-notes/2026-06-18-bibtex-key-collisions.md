---
title: "Resolve citation key collisions on import"
type: source
tags: [session, session-transcript, paper-notes, claude, bibtex-keys, collision-detection, deduplication, data-import]
date: 2026-06-18
source_file: raw/sessions/paper-notes/2026-06-18T17-18-paper-notes-bibtex-key-collisions.md
project: paper-notes
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session identified and fixed a data loss bug in [[Paper Notes]] where importing two papers by the same author from the same year would silently overwrite one due to citation key collision. The fix appends a disambiguating suffix in stable order, reports collisions explicitly rather than silently, and preserves existing keys for backward compatibility. Duplicate detection by content was also clarified as distinct from collision resolution.

## Key Claims

- Citation keys were generated as `author+year`, causing collisions when multiple distinct papers by the same author in the same year were imported
- A disambiguating suffix is now appended in stable order to resolve collisions while maintaining reproducibility
- The importer now explicitly reports every collision resolved instead of silently overwriting one paper with another
- Existing citation keys are left unchanged to preserve backward compatibility with already-written citations
- Duplicate papers (identical content imported twice) are detected by content rather than key, and skipped as duplicates—distinct from collisions between two genuinely different papers

## Key Quotes

> "Keys were author plus year, so a collision overwrote. A disambiguating suffix is now appended in a stable order, and the importer reports every collision it resolved rather than resolving it quietly." — The root cause and implementation of the collision fix

> "Existing keys are left alone so citations already written do not shift." — Justification for backward compatibility

> "That is detected by content rather than key and skipped as a duplicate, which is different from a collision between two genuinely distinct papers." — Distinguishes two related but separate concerns

## Connections

- [[Paper Notes]] — the bibliography management project where citation key collisions were resolved