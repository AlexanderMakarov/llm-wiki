---
title: "Sort the lint rules into errors, warnings and information"
type: source
tags: [session, session-transcript, llm-wiki, claude, lint-rule-severity, build-gates, validation-levels, build-blocking, error-vs-warning, severity-classification, build-failures, wiki-validation]
date: 2026-09-15
source_file: raw/sessions/llm-wiki/2026-08-23T18-19-llm-wiki-lint-rule-severities.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Categorized all 17 lint rules into three severity levels for build gating: four errors enforce structural correctness (missing frontmatter, invalid page kind, catalog mismatch, broken provenance), nine warnings flag quality issues (broken cross-references, stubs, near-duplicates, tag conventions, freshness), and four informational rules provide metadata signals on young vaults (orphan detection). Decided freshness should warn, not error, because it measures elapsed time on fixed corpora rather than content quality. Implementation was validated with pytest coverage.

## Key Claims

- Four lint rules should be errors: missing required frontmatter, invalid page kind, catalog disagreement with disk, broken provenance
- Nine lint rules should be warnings: broken cross-references, stub pages, near-duplicate detection, tag conventions, and freshness
- Four lint rules should be informational: orphan detection and similar vault metadata signals that fire constantly on young vaults
- The freshness rule must be a warning, not an error, because it measures elapsed time on fixed corpora rather than content quality
- Severity-level categorization was implemented with pytest coverage to lock the behavior

## Key Quotes

> "Four are structural and should be errors: missing required frontmatter, an invalid page kind, a catalog that disagrees with what is on disk, and provenance that points nowhere."

> "Nine are warnings — broken cross-references, stub pages, near-duplicate detection, tag conventions. They mean something is worth fixing but not that the output is wrong."

> "Warning, and arguably it should not fire at all on a fixed corpus. It reports how long ago a page was last updated, so on anything committed and left alone it measures elapsed time rather than quality. On a living vault it is a genuine signal."

## Connections

- [[Lint Rules]] (entity) — Framework for categorizing wiki violations by severity
  - fact: All 17 lint rules categorized into error (4), warning (9), and informational (4) levels
  - fact: Error-level rules enforce structural properties that cannot be violated in output

- [[llmwiki]] (entity) — CLI that enforces lint rules during builds
  - fact: Severity levels determine whether violations block the build or only warn

- [[Frontmatter]] (concept) — YAML metadata that lint rules validate
  - fact: Missing required frontmatter is an error-level violation that blocks builds

- [[Wikilinks]] (concept) — Cross-reference syntax that lint rules validate
  - fact: Broken cross-references are warning-level violations that don't block builds

- [[Static Site]] (concept) — Generated output gated by lint violation severity
  - fact: Error-level violations prevent site generation; warnings allow generation with quality signal