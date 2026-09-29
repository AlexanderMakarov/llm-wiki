---
title: "Sort the lint rules into errors, warnings and information"
type: source
tags: [session, session-transcript, llm-wiki, claude, lint-rule-severity, build-gates, validation-levels, build-blocking, error-vs-warning, severity-classification]
date: 2026-09-12
source_file: raw/sessions/llm-wiki/2026-08-23T18-19-llm-wiki-lint-rule-severities.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

The session categorized all seventeen lint rules in the llm-wiki validator by whether they should block a build (errors), issue warnings, or be informational. Four structural rules were marked as errors (missing frontmatter, invalid page kind, catalog mismatch, broken provenance); nine were set as warnings (broken cross-references, stubs, near-duplicates, tag conventions); and four as informational (orphan detection and similar). The "freshness" rule was classified as a warning with a note that it may not be suitable for fixed corpora. All tests passed after the classification was implemented.

## Key Claims

- Four lint rules are structural errors: missing required frontmatter, invalid page kind, catalog disagreement with disk, and provenance pointing to nowhere.
- Nine lint rules are warnings that signal work worth doing but do not invalidate the output: broken cross-references, stub pages, near-duplicate detection, and tag conventions.
- Four lint rules are informational, including orphan detection, which fires frequently on young vaults and should not block builds.
- The "freshness" rule measures elapsed time on fixed corpora and should be a warning, possibly disabled entirely on non-living vaults.
- The retry path handles an edge case discovered in the previous week; a note was added to the [[Frontmatter]] page to prevent rediscovery.

## Key Quotes

> "Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere."

> "Nine are warnings — broken cross-references, stub pages, near-duplicate detection, tag conventions. They mean something is worth fixing but not that the output is wrong."

> "Warning, and arguably it should not fire at all on a fixed corpus. It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality."

## Connections

- [[Lint Rules]] (concept) — the session establishes severity levels (error, warning, informational) for all lint rule categories.
  - fact: Four lint rules are structural errors that block builds.
  - fact: Nine lint rules generate warnings for fixable issues.
  - fact: Four lint rules are informational and do not block output.
- [[Static Site]] (entity) — lint rules enforce quality of the generated static wiki output.
  - fact: Build-blocking rules ensure structural correctness before generation.
- [[Frontmatter]] (entity) — missing required frontmatter is one of the four error-level lint rules.
  - fact: An edge case related to freshness and frontmatter was addressed with a retry path.
- [[Wikilinks]] (entity) — broken cross-references are classified as a warning-level lint rule.