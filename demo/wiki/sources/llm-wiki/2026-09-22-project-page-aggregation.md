---
title: "Seed project pages from session metadata"
type: source
tags: [session, session-transcript, llm-wiki, claude, project-pages, metadata-driven, project-page-generation, frontmatter-driven, metadata-aggregation]
date: 2026-09-22
source_file: raw/sessions/llm-wiki/2026-09-02T22-11-llm-wiki-project-page-aggregation.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-28
---
## Summary

Project pages are now automatically generated from session frontmatter metadata rather than manually edited. The build system groups sessions by their `project` field and creates project stubs with auto-generated session lists. Project freshness is determined by the most recent session, not by an independent date on the stub itself.

## Key Claims

- Project pages are now automatically derived from the `project` field in session frontmatter
- Sessions are grouped by their project value during the build process, eliminating manual page maintenance
- Project pages carry no independent last-updated date; freshness is determined by the most recent session in that project
- The project field in frontmatter serves as a durable handle for search recovery

## Key Quotes

> "Project pages are now derived from session frontmatter rather than written by hand." — The core automation: elimination of manual editing workflow.

> "Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists." — The implementation mechanism.

> "A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it." — Design rationale for not dating project stubs independently.

## Connections

- [[Wiki Synthesis]] (entity) — Automated process for aggregating sessions by project metadata into generated page stubs.
  - fact: The build system groups sessions by their `project` field and generates one page per project.
- [[Frontmatter]] (entity) — Session metadata container with the `project` field that drives page generation.
  - fact: The `project` key is the canonical source for associating sessions to their project pages.
- [[Static Site]] (entity) — Generated project pages are output as part of the static wiki.
  - fact: Auto-derived project stubs are included in static site generation.