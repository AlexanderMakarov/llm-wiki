---
title: "Seed project pages from session metadata"
type: source
tags: [session, session-transcript, llm-wiki, claude, project-pages, metadata-driven]
date: 2026-09-02
source_file: raw/sessions/llm-wiki/2026-09-02T22-11-llm-wiki-project-page-aggregation.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-08
---
## Summary

The assistant implemented automatic generation of project pages from session metadata rather than requiring manual maintenance. The build process now groups sessions by their `project` frontmatter field and generates project stubs with session lists. Project pages don't carry their own update timestamp—freshness is derived from the most recent session. A design issue remains: two clones of the same repository produce different project names because project identity is based on working directory path rather than a stable identifier.

## Key Claims

- Project pages are automatically generated from session frontmatter metadata instead of being manually edited
- Sessions are grouped by the `project` field in their metadata to create project stubs
- Project pages have no independent last-updated date; their freshness is determined by the most recent session they contain
- Different clones of the same repository currently create duplicate projects because project names are derived from the working directory path

## Key Quotes

> "They are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists." — Describes the core implementation strategy

> "One consequence worth knowing: those stubs carry no last-updated date of their own. A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it." — Explains a key design decision about temporal metadata

> "They currently produce two projects. The name comes from the working directory, so a second clone reads as separate work. Worth solving, but it needs a stable project identity rather than a path." — Identifies a known limitation

## Connections

- [[llmwiki]] (project) — The wiki system where project page aggregation was implemented
  - fact: Project pages are now automatically generated from session metadata rather than manually maintained
- [[Frontmatter]] (topic) — The session metadata format that drives project page generation
  - fact: The `project` field in session frontmatter is the primary key for grouping sessions into projects
- [[Static Site]] (topic) — The output format where project pages are deployed
  - fact: Project stubs are generated as part of the static site build process
- [[Wiki Synthesis]] (topic) — The automated process that groups and generates project content
  - fact: The build process groups sessions by project field and generates stubs with session lists
