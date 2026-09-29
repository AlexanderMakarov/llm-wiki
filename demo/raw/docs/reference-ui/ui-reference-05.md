---
title: "UI reference (part 5/8: Project topics route to the project page)"
slug: ui-reference-05
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/ui.md"
content_sha256: 7656740cdc53f26b667601ea5fc167c1f813f61908c1f46377e210d82e1e05bf
---

> Part 5 of 8 of **UI reference** — Project topics route to the project page.

The topic page is the only browsable surface for entity and concept pages, so it renders their content above the link lists. What survives is everything after the page's own leading `# H1`, minus `## Connections`, `## Sessions`, and `## Sources` — the topic page renders Connected topics and a collapsible Sources evidence list (Sessions vs Documents) itself from the graph, so the page's hand-written versions would only duplicate them.

- **Heading-agnostic.** Nothing is keyed to `## Key Facts`; a renamed, reordered, or newly added section reaches the reader as written, as does introductory prose sitting above the first heading.
- **No empty sections.** A heading with nothing under it is dropped rather than rendered as a bare heading — innermost first, so a `##` whose only child `###` was itself empty goes too.
- **`[[wikilinks]]` resolve.** A target naming a topic links to wherever that topic resolved (its topic page, or the project page a project topic routes to); a target naming a session with a compiled page links to it; anything else degrades to the plain text it wrapped rather than a dead link. Code spans and fenced blocks are left exactly as written — a page documenting wikilink syntax keeps its example.

### Project topics route to the project page

A topic backed by a page under `wiki/projects/` links to `/projects/<slug>.html` — the full [project detail page](#project-detail-projectsslughtml) with its heatmap, session cards and charts — rather than to a thin topic page. The rewrite is applied once at build time and every surface honours it: the map's double-click target, the search index entry, Connected topics lists on topic pages and on project pages, `topics/index.html`, and `[[wikilinks]]` cited inside page content.

The match itself identifies which project it is, so an alias spelling routes as correctly as the canonical one. The rewrite is skipped when the build wrote no page for that project: `wiki/projects/` is seeded from stubs while `site/projects/` comes from session groups, so a project page with no recorded sessions keeps its ordinary topic page rather than being handed a link that 404s.

The `type:` vocabulary on the backing wiki page, and the origin of every frontmatter field, is [Page kinds](page-kinds.md).

---
