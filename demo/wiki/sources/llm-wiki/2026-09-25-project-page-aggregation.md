---
title: "Seed project pages from session metadata"
type: source
tags: [session, session-transcript, llm-wiki, claude, project-pages, metadata-driven, project-page-generation, frontmatter-driven, metadata-aggregation]
date: 2026-09-25
source_file: raw/sessions/llm-wiki/2026-09-02T22-11-llm-wiki-project-page-aggregation.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-10-01
---
## Summary

Implemented automatic generation of project pages from session frontmatter. The build now groups sessions by their `project` field and generates project stubs with session lists, eliminating stale project pages that previously required manual updates.

## Key Claims

- Project pages are auto-generated from the `project` field in session frontmatter during the build process, rather than hand-written
- Sessions are grouped and associated with projects based on their frontmatter metadata
- Project pages do not have their own last-updated timestamp; they derive freshness from the most recent session they contain
- This eliminates the need to manually update project pages whenever a new session is added to the vault

## Key Quotes

> "Project pages are stale — I have to edit them whenever I add sessions." — Problem identified

> "They are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists." — Solution approach

> "A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it." — Design rationale for stateless project pages

## Connections

- [[llmwiki]] (entity) — wiki system implementing project page auto-generation
  - fact: Project pages are now derived from session metadata rather than manually maintained.
- [[Wiki Synthesis]] (concept) — process of aggregating sessions into structured wiki pages
  - fact: Sessions are automatically grouped by their `project` field during synthesis.
- [[Frontmatter]] (concept) — contains the `project` field that drives session grouping
  - fact: The `project` metadata value is the primary key for aggregation.
- [[Static Site]] (concept) — generated website containing auto-derived project pages
  - fact: Generated project stubs are compiled into the static site output.