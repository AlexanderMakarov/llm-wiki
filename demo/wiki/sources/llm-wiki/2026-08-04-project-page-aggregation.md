---
title: "Seed project pages from session metadata"
type: source
tags: [session, session-transcript, llm-wiki, claude, project-aggregation, frontmatter-extraction, path-identity]
date: 2026-08-04
source_file: raw/sessions/llm-wiki/2026-08-04T22-11-llm-wiki-project-page-aggregation.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-08-11
---
## Summary

Project pages are now automatically generated from session frontmatter at build time, eliminating manual maintenance. The build system groups sessions by their `project` field and creates project stubs with dynamically-generated session lists. A known limitation: project identity derives from working directory paths, so multiple clones could generate duplicate projects.

## Key Claims

- Project pages are now derived automatically from session frontmatter rather than manually edited, solving staleness
- The build groups sessions by their `project` frontmatter field and generates one project stub per unique value, with session lists auto-populated from what exists
- Project stubs carry no last-updated date of their own; a project's freshness is determined by its most recent session's date
- Project identity is currently path-based (working directory), so different clones of the same repository will create separate projects with different names

## Key Quotes

> "Project pages are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one, with the session list generated from what actually exists."

Demonstrates that the solution eliminates manual page updates.

> "A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it."

Clarifies the decision to derive project recency from session timestamps rather than stub timestamps.

> "The name comes from the working directory, so a second clone reads as separate work. Worth solving, but it needs a stable project identity rather than a path."

Identifies a design limitation requiring stable project identity rather than path-based identity.

## Connections

- [[Session Frontmatter]] — the `project` field in session metadata drives aggregation
- [[Project Pages]] — automatically generated from grouped sessions, replacing manual editing
- [[Build System]] — groups sessions by project and generates page stubs programmatically

## Contradictions

None identified.