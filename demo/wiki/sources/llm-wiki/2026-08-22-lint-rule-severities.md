---
title: "Sort the lint rules into errors, warnings and information"
type: source
tags: [session, session-transcript, llm-wiki, claude, lint-severities, build-blocking-rules, vault-quality]
date: 2026-08-22
source_file: raw/sessions/llm-wiki/2026-08-22T18-19-llm-wiki-lint-rule-severities.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary
Reviewed all 17 linting rules in llmwiki and categorized them by severity: 4 structural errors that must block builds, 9 warnings worth fixing but not blocking, and 4 informational checks. The freshness rule was determined to be a warning (not error) because it measures elapsed time on a fixed corpus rather than actual quality, though it provides genuine value on actively-maintained vaults.

## Key Claims
- There are 17 distinct lint rules across llmwiki
- Four rules are structural errors that should block builds: missing required frontmatter, invalid page kind, catalog-disk disagreement, and invalid provenance references
- Nine rules are warnings (broken wikilinks, stubs, near-duplicates, tag convention violations)
- Four rules are informational (e.g., orphan detection)
- The freshness rule measures elapsed time rather than quality on fixed/committed corpora
- Freshness provides genuine signal only on actively-maintained (living) vaults

## Key Quotes
> "It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal."
— Explains the context-dependent nature of the freshness lint rule

## Connections
- [[Lint Rules]] (feature) — The quality-checking system for wiki builds, now categorized by severity (error/warning/info)
- [[Static Site]] (system) — The compiled output being validated by lint rules
- [[Wikilinks]] (syntax) — One class of lint violations detects broken cross-reference links
- [[Frontmatter]] (format) — Required metadata fields; missing values are build-blocking errors

## Contradictions
(None identified.)