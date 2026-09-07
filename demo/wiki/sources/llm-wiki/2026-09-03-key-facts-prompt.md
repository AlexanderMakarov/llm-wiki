---
title: "Constrain the Key Facts prompt to attributed bullets"
type: source
tags: [session, session-transcript, llm-wiki, claude, wiki-synthesis, prompt-constraints, fact-attribution, key-facts]
date: 2026-09-03
source_file: raw/sessions/llm-wiki/2026-09-03T12-37-llm-wiki-key-facts-prompt.md
project: llm-wiki
model: claude-haiku-4-5
last_updated: 2026-09-07
---
## Summary

The [[Wiki Synthesis]] prompt for Key Facts output was tightened to require every bullet to be a complete statement fully attributed to specific source pages in the evidence, eliminating hallucinated general-knowledge facts. The change trades quantity for verifiability: fewer bullets, but each one traceable to its source. The session also clarified that intro paragraphs for wiki pages would require a deliberate design decision rather than automatic generation.

## Key Claims

- The original Key Facts prompt allowed the model to add well-known facts that weren't present in the supplied session evidence
- Rewriting the prompt to require complete statement-level attribution to specific source pages eliminates unsourced facts
- The tightened prompt returns fewer bullets but makes each one traceable to evidence
- No current system auto-generates intro paragraphs for wiki pages; adding one would require a separate cost/quality tradeoff decision

## Key Quotes

> "Some Key Facts read like the model's general knowledge rather than anything from my sessions." — The problem prompting the redesign

> "every bullet is a whole statement about the page's subject, attributed to the source page it came from, and that nothing outside the supplied evidence may be added however well known it is" — The new constraint on Key Facts generation

> "Fewer bullets, but each one is traceable." — The quality outcome of the prompt tightening

## Connections

- [[Wiki Synthesis]] (concept) — the core process improved in this session
  - fact: Key Facts bullets now must be complete statements explicitly attributed to source pages rather than standalone claims
- [[Claude Code]] (tool) — used to redesign and implement the tightened prompt
  - fact: Work was done on branch `feat/key-facts` using the Code agent

## Contradictions

None identified.