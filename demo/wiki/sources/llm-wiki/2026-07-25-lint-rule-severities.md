---
title: "Sort the lint rules into errors, warnings and information"
type: source
tags: [session, session-transcript, llm-wiki, claude, lint-rules, build-blocking, severity-classification]
date: 2026-07-25
source_file: raw/sessions/llm-wiki/2026-07-25T18-19-llm-wiki-lint-rule-severities.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

The session categorized all 17 linting rules in llm-wiki by severity, determining which should fail a build. Four structural rules were designated as errors (missing required frontmatter, invalid page kind, catalog mismatches, broken provenance), nine as warnings (broken cross-references, stubs, near-duplicates, tag issues), and four as informational (e.g., orphan detection). The freshness rule was classified as a warning but noted as context-dependent—useful for active vaults but misleading on static content where it conflates staleness with quality.

## Key Claims

- There are 17 lint rules total: 4 structural errors, 9 warnings, and 4 informational signals
- Errors are rules where "the output is wrong"; warnings signal issues worth fixing but output remains valid
- The freshness rule should be a warning, not an error, because it measures elapsed time rather than actual quality problems
- Freshness detection arguably should not fire on fixed/archived corpus since it conflates staleness with quality issues

## Key Quotes

> "Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere."

> "They mean something is worth fixing but not that the output is wrong." — distinguishing warnings from errors

> "It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal." — explaining why freshness severity is context-dependent

## Connections

- [[Lint Rules]] — the core system whose severity levels were being classified for build integration