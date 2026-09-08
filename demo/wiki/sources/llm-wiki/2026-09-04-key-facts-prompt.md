---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
tags: [session, session-transcript, llm-wiki, claude, fact-attribution, synthesis-prompt, hallucination-prevention, source-grounding]
date: 2026-09-04
source_file: raw/sessions/llm-wiki/2026-09-04T12-37-llm-wiki-key-facts-prompt.md
project: llm-wiki
model: claude-haiku-4-5
last_updated: 2026-09-08
---
## Summary

The synthesis prompt for generating [[Key Facts]] was tightened to require every fact to be attributed to a source document with supporting evidence. Previously the model would sometimes incorporate general knowledge; now it returns only statements traceable to supplied evidence, accepting that this reduces output volume. This trades breadth for verifiability.

## Key Claims

- The original Key Facts synthesis prompt allowed facts derived from model general knowledge rather than evidence from the sessions being summarized
- The revised prompt requires each bullet to be a complete statement about the subject, explicitly attributed to a source page, with no additions from external knowledge
- When evidence doesn't support a conclusion, the revised prompt returns empty rather than generating an unsupported fact
- Adding intro paragraphs to synthesized pages would require deliberate architectural decisions about cost and quality, not an automatic feature drift

## Key Quotes

> "Some Key Facts read like the model's general knowledge rather than anything from my sessions." — User identifies the core problem

> "every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added however well known it is" — The tightening principle

> "Fewer bullets, but each one is traceable." — Describes the tradeoff: reduced volume for increased verifiability

> "Adding one would be a new generated field with its own cost and quality bar, so it is worth deciding deliberately rather than drifting into it." — On future synthesized fields as intentional choices

## Connections

- [[Wiki Synthesis]] (process) — The session improves the prompt design for generating Key Facts, enforcing source attribution and preventing unsupported claims
- [[Key Facts]] (feature) — The specific synthesis output type being redesigned to ensure facts are grounded in evidence rather than model inference
