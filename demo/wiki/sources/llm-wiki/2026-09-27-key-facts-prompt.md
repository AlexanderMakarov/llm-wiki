---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
tags: [session, session-transcript, llm-wiki, claude, fact-attribution, synthesis-prompt, hallucination-prevention, source-grounding, key-facts, source-attribution, prompt-engineering, wiki-synthesis, fact-verification]
date: 2026-09-27
source_file: raw/sessions/llm-wiki/2026-09-04T12-37-llm-wiki-key-facts-prompt.md
project: llm-wiki
model: claude-haiku-4-5
last_updated: 2026-10-01
---
## Summary

The session focused on constraining the Key Facts generation prompt to enforce source attribution and traceability. The revised prompt requires every fact to be attributed to a specific source session and forbids general knowledge beyond the supplied evidence. This approach yields fewer bullets but guarantees each is traceable; it returns no facts rather than inventing when evidence is absent.

## Key Claims

- The original Key Facts prompt allowed generation of statements from the model's general knowledge rather than exclusively from the supplied session evidence.
- The revised prompt mandates that every fact bullet is a complete statement attributed to a source page from the input evidence.
- When the supplied evidence cannot support any facts, the revised system returns nothing rather than generating plausible but unsourced statements.
- Adding auto-generated intro paragraphs was deferred because it would require its own distinct cost and quality evaluation.

## Key Quotes

> "Some Key Facts read like the model's general knowledge rather than anything from my sessions." — The observation that prompted the constraint tightening.

> "every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added however well known it is" — The new constraint exactly as stated.

> "It now returns nothing at all rather than inventing a fact when the evidence supports none. Fewer bullets, but each one is traceable." — The desired trade-off: verifiability over quantity.

> "Adding one would be a new generated field with its own cost and quality bar, so it is worth deciding deliberately rather than drifting into it." — Principled deferral of intro paragraph auto-generation.

## Connections

- [[Wiki Synthesis]] (concept) — Key Facts generation is part of the session-to-wiki conversion pipeline
  - fact: The Key Facts prompt was refined to enforce traceability during the synthesis process.

- [[Frontmatter]] (concept) — Key Facts appear as a generated field in wiki page metadata
  - fact: Each Key Fact in the frontmatter must be attributed to its source session.

- [[Wikilinks]] (concept) — Key Facts enable readers to discover related sessions through cross-references
  - fact: Attribution to source pages allows facts to become discovery points in the knowledge graph.

- [[Key Facts]] (entity) — auto-generated bullet points extracted from session transcripts, ensuring verifiable attribution
  - fact: The generation prompt enforces that no fact can be added beyond what the supplied evidence supports.
  - fact: When no evidence supports a fact, the system returns no bullet rather than inventing a plausible statement.

## Contradictions

None identified.