---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
tags: [session, session-transcript, llm-wiki, claude, fact-attribution, synthesis-prompt, hallucination-prevention, source-grounding, key-facts, source-attribution, prompt-engineering, wiki-synthesis, fact-verification]
date: 2026-09-24
source_file: raw/sessions/llm-wiki/2026-09-04T12-37-llm-wiki-key-facts-prompt.md
project: llm-wiki
model: claude-haiku-4-5
last_updated: 2026-09-28
---
## Summary

Refined the Key Facts synthesis prompt to enforce strict source attribution. Every bullet must be a verifiable statement from the supplied evidence; general knowledge is forbidden. This produces fewer facts per page but ensures each is traceable to its source, and the synthesis returns nothing rather than hallucinating when evidence is thin.

## Key Claims

- The original Key Facts prompt allowed the model to include general knowledge not grounded in supplied evidence.
- The revised prompt forbids facts outside the supplied evidence and requires each bullet to be attributed to a source page.
- The trade-off is fewer bullets per page, but each one is verifiable and fully traceable.
- Synthesized pages do not currently include generated intro paragraphs; adding one would require an explicit feature decision, not accidental drift.

## Key Quotes

> "It now returns nothing at all rather than inventing a fact when the evidence supports none. Fewer bullets, but each one is traceable." — articulating the deliberate trade-off for reliability.

> "Adding one would be a new generated field with its own cost and quality bar, so it is worth deciding deliberately rather than drifting into it." — on intentional design over feature creep.

## Connections

- [[Wiki Synthesis]] (entity) — the process refined by enforcing attribution and traceability.
  - fact: Key Facts generation now forbids general knowledge and requires source attribution.
- [[llmwiki]] (entity) — the system whose synthesis pipeline was tightened.
  - fact: The Key Facts feature now produces fewer but more reliable bullets.
- [[Key Facts]] (entity) — the synthesized field improved in this session.
  - fact: Key Facts now require explicit attribution and reject hallucination.

## Contradictions

None identified. The session reports a deliberate improvement to an existing feature, not a correction to prior claims.