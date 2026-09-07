---
title: "Seed project pages from session metadata"
type: source
tags: [session, session-transcript, llm-wiki, claude, project-aggregation, frontmatter-driven-build, static-site-generation, path-identity]
date: 2026-09-01
source_file: raw/sessions/llm-wiki/2026-09-01T22-11-llm-wiki-project-page-aggregation.md
project: llm-wiki
model: claude-opus-5
last_updated: 2026-09-07
---
## Summary

The session introduced automatic generation of project pages from session frontmatter, eliminating manual maintenance of stale index pages. Sessions are now grouped by their `project` field at build time, and project stub pages are generated automatically with session lists. A key architectural consequence: project stubs inherit freshness from the most recent session rather than having independent timestamps. A design issue was identified: project identity currently derives from working directory paths, causing duplicate repository clones to appear as separate projects.

## Key Claims

- Project pages were previously maintained manually and became stale with each new session
- Project pages are now derived automatically from the `project` field in session frontmatter
- The build groups sessions by project value and generates project stub pages with session lists
- Project stubs do not have independent last-updated timestamps; their freshness comes from the most recent session they contain
- Project identity is currently path-based (derived from working directory), causing duplicate repository clones to produce separate projects
- A stable project identifier is needed to resolve the path-based identity limitation

## Key Quotes

> "Project pages are stale — I have to edit them whenever I add sessions." — the original problem statement

> "They are now derived. Every session carries a project in its frontmatter, so the build groups sessions by that value and writes a project stub for each one" — solution implemented

> "One consequence worth knowing: those stubs carry no last-updated date of their own. A project's freshness comes from its most recent session, because a date on the stub would be meaningless — nothing edits it." — architectural design decision

> "They currently produce two projects. The name comes from the working directory, so a second clone reads as separate work. Worth solving, but it needs a stable project identity rather than a path." — identified limitation

## Connections

- [[llmwiki]] (system) — the knowledge base platform being improved; this session enhanced automatic project page generation
  - fact: Project pages are now derived from session frontmatter rather than manually maintained
  - fact: The build automatically groups sessions by their `project` field into separate project indexes
- [[Static Site]] (system) — project pages are compiled into the static HTML output
  - fact: Project stub pages are generated during the build process as part of static site generation
- [[Session Metadata]] (concept) — structured frontmatter fields (including `project`) that drive project page aggregation
  - fact: The `project` field in session frontmatter is used to group sessions into project pages
- [[Frontmatter]] (concept) — YAML metadata structure at the top of session files containing project and other metadata
  - fact: Session frontmatter carries project, date, and other fields used by the build to organize content
- [[Knowledge Graph]] (system) — project pages serve as aggregation nodes within the wiki's knowledge structure
  - fact: Project pages connect related sessions together as nodes in the graph