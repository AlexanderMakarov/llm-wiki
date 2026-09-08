---
title: "Sort the lint rules into errors, warnings and information"
type: source
tags: [session, session-transcript, llm-wiki, claude, lint-rule-severity, build-gates, validation-levels]
date: 2026-08-23
source_file: raw/sessions/llm-wiki/2026-08-23T18-19-llm-wiki-lint-rule-severities.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The session categorized 17 lint rules by failure impact to determine build-blocking severity. Four structural issues—missing required frontmatter, invalid page kinds, catalog-disk disagreement, and broken provenance—should error; nine violations (broken [[Wikilinks]], stubs, duplicates, tag conventions) should warn; four are informational only. Freshness (time-since-update) was debated as context-dependent: meaningful for living vaults but measuring elapsed time rather than quality on static/committed corpuses.

## Key Claims

- Four lint rules should error and block builds: missing required frontmatter, invalid page kind, catalog-disk mismatch, and broken provenance pointers
- Nine lint rules should warn: broken [[Wikilinks]], stub pages, near-duplicate detection, and tag convention violations
- Four lint rules are informational only
- Freshness (time-since-last-update) should warn, not error
- Freshness is a meaningful signal for living vaults but measures elapsed time rather than quality on static/committed corpuses

## Key Quotes

> "Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere." — defines which violations block the build

> "On anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal." — explains why freshness severity is corpus-dependent

## Connections

- [[Lint Rules]] (system) — validation framework for categorizing vault issues by build impact
  - fact: 17 rules categorized into error (4), warning (9), and informational (4) levels
- [[llmwiki]] (project) — system implementing lint validation
  - fact: Contains lint rules that validate vault structure and generated output consistency
- [[Static Site]] (product) — the output format being validated
  - fact: Lint rules ensure consistency between vault structure and generated site
- [[Frontmatter]] (feature) — required document metadata
  - fact: Missing required frontmatter is a build-blocking lint error
- [[Wikilinks]] (feature) — semantic cross-references between pages
  - fact: Broken cross-references are lint warnings, not build-blocking errors
