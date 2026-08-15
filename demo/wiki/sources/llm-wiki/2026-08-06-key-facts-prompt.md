---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
tags: [session, session-transcript, llm-wiki, claude, fact-attribution, prompt-engineering, synthesis-quality, hallucination-prevention]
date: 2026-08-06
source_file: raw/sessions/llm-wiki/2026-08-06T12-37-llm-wiki-key-facts-prompt.md
project: llm-wiki
model: claude-haiku-4-5
last_updated: 2026-08-11
---
## Summary

Improved the [[Key Facts]] synthesis component by tightening the prompt to require that every bullet is sourced from session evidence rather than the model's general knowledge. The new approach prevents hallucinated facts at the cost of sometimes returning empty results, but ensures each fact is traceable to its source pages.

## Key Claims

- The original [[Key Facts]] synthesis prompt allowed models to generate statements from general knowledge without requiring session evidence
- Rewriting the prompt to mandate attribution to source pages prevents hallucinated facts
- The new prompt refuses to generate facts when evidence doesn't support them, resulting in fewer but fully traceable bullets
- Decisions to add new generated fields (like intro paragraphs) should be deliberate design decisions rather than incremental drift

## Key Quotes

> "every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added" — describes the tightened synthesis constraint

> "Fewer bullets, but each one is traceable." — the quality/quantity tradeoff of the fix

> "it is worth deciding deliberately rather than drifting into it" — on why adding new generated fields requires explicit design decisions

## Connections

- [[Wiki Synthesis]] — this session improved the quality and attribution standards of the [[Key Facts]] synthesis component
- [[Key Facts]] — the wiki section being enhanced to require traceable sourcing from session evidence