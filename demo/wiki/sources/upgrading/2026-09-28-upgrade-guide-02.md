---
title: "Upgrade guide (part 2/8: Unreleased — source pages filed under a stale name (#265))"
type: source
tags: [wiki-add, raw-doc, session-transcript, upgrading, username-redaction, search-findability, source-page-paths, session-description]
date: 2026-09-28
source_file: 
project: upgrading
model: 
last_updated: 2026-09-29
---
## Summary

This upgrade guide documents four unreleased features for [[llmwiki]] with optional and required offline migrations. Users upgrading encounter new source page naming (`<date>-<slug>` format), page findability keyed to the frontmatter title instead of slug or filename, a changed default for username redaction in private vaults (now `false`), and session description sourcing from adapter metadata before content analysis.

## Key Claims

- Source pages previously filed under generic or filename-derived names will be skipped by synth until migrated to the new `<date>-<slug>` naming scheme; `migrate source-page-paths` atomically rewrites internal links, moves files, and updates synth state—handling collisions and ambiguous references as manual decisions
- Page findability (search API, MCP server, `page_findability` lint rule) now keys off the frontmatter `title` field; slug remains the identity for link resolution and filesystem location
- Username redaction defaults to `false` (`redact_username` in `redaction` config), preserving real home paths in private vaults; repositories that commit or publish `raw/` must explicitly set `"redact_username": true` to avoid exposing real usernames
- Session descriptions are assigned from adapter metadata (Claude Code: `customTitle` then `aiTitle`; Cursor: stored `name` field excluding `New Agent` placeholder) before falling back to content-based scoring of user prompts
- Number-shaped slugs (e.g., `"0123"`, `"68657849"`) previously caused doubled date formats in page names; new derivation preserves the written slug, eliminating duplication

## Key Quotes

> "every `synth` run reports `skipped N source(s) already claimed by a real page under another name`" — symptom indicating pages filed under stale names

> "Title is the findability key: `llmwiki search`, MCP `wiki_search`, and the `page_findability` lint rule judge findability by each page's frontmatter **title**, not by slug/filename" — central findability redesign

> "such repositories must set `"redact_username": true` under `redaction` in `config.json`" — requirement for public and committed vaults

> "Assigned names win: when an adapter exposes a session title, that becomes `description:`" — adapter metadata precedence rule

## Connections

- [[llmwiki]] (entity) — the system receiving these feature releases
  - fact: Four parallel optional/recommended offline migrations ease adoption of new page naming and metadata schemes
- [[Wiki Synthesis]] (concept) — synth behavior changes with new page naming
  - fact: `synth --estimate` correctly reports sources as done after `migrate source-page-paths` updates synth state
- [[Configuration]] (entity) — new `redaction.redact_username` config key
  - fact: Default shifted from implicit `true` (redact) to explicit `false` (preserve); public repositories must opt-in to redaction
- [[Frontmatter]] (entity) — title field becomes the primary discoverability index
  - fact: Upgrade makes title the searchable key across all discovery APIs and lint rules, replacing slug and bare wikilink matching
- [[Lint Rules]] (concept) — `page_findability` rule refactored
  - fact: No longer fails pages for missing wikilink anchor text; title-not-found and ranked-past-cap errors remain
- [[Wikilinks]] (concept) — cosmetic migration for display titles
  - fact: `migrate wikilink-titles` converts bare `[[slug]]` links to `[[slug|Title]]` for visual consistency with page titles
- [[Static Site]] (concept) — username redaction timing affects publication
  - fact: Repositories syncing via [[GitHub Actions]] must set redaction policy before next sync to avoid committing real home paths