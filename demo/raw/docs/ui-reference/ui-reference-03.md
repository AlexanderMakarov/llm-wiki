---
title: "UI reference (part 3/5: Topic pages)"
slug: ui-reference-03
project: ui-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/ui.md"
content_sha256: 091e560125d91e049c14221fb0d035f09dac5d63e4986142a6252af727a37d58
---

> Part 3 of 5 of **UI reference** — Topic pages.

## Topic pages

URLs: `/topics/<slug>.html`, `/topics/index.html`

A **topic** is a `[[wikilink]]` target found in `wiki/sources/*.md`, with spelling variants clustered into one canonical name. Topics are therefore *not* wiki pages: a topic exists because sessions cited the name, and a topic page renders whether or not any page under `wiki/` describes it — an un-promoted candidate, or a name a reviewer declined, keeps its page indefinitely. Reach them by double-clicking a node in the [Graph](#graph), from `⌘K` (`type:topic`), from `topics/index.html`, or from the Connected topics list on any other topic or project page.

`/topics/index.html` lists every topic by reach — session count and link count per row.

Two thresholds decide which topics get a page: a topic mentioned by fewer than 2 sessions is dropped from the graph, and a vault yielding fewer than 5 topic nodes falls back to the page graph, in which case `build` writes no topic pages at all.

### Layout

The title, then an **identity line** of ` · `-separated parts in this order — each date part dropped entirely when its source is absent, never filled with a placeholder:

`Entity` chip · `Active 2026-01-09 – 2026-07-30` · `Reviewed 2026-08-01` · `7 connected topics` · `12 sessions` · `<slug>`

The kind chip names the singular kind — Entity, Concept, Project, Synthesis, Source — or `Unclassified topic` when no wiki page describes it. The chip is never dropped: the absence of a backing page is itself a fact, and a missing chip would leave a reader unable to tell an unclassified topic from a page that failed to render one. Below the identity line:

- **Also tagged as** — the alternative spellings sessions used before clustering merged them under this name.
- **Page content** — the backing wiki page's body (see below). Absent when no page backs the topic or the page records nothing.
- **Connected topics** — topics sharing at least one session, strongest first, each with its shared-session count. Renders `No connected topics.` rather than disappearing.
- **Sessions** — every session mentioning the topic, linked to its compiled session page; a session with no compiled page is listed as text marked `(no page)`.

### Where each fact comes from

This is the distinction to keep straight: **sessions supply reach and activity, the topic's own wiki page supplies kind, review date and content.** Neither substitutes for the other, and neither is invented.

| On the page | Comes from | Present when |
|---|---|---|
| `Active <first> – <last>` | the `date` frontmatter of the sessions that mention the topic — oldest to newest, collapsing to one date when they agree | at least one such session carries a date |
| `N sessions` + the Sources list (Sessions / Documents) | the same set of evidence pages from the graph, partitioned by compiled URL | always |
| `N connected topics` + the Connected topics list | co-occurrence: two topics share an edge when a session mentions both | always (the count can be `0`) |
| Kind chip | the `wiki/` folder holding the page that backs the topic — `entities/` → Entity, `concepts/` → Concept, and so on. The folder is the only kind signal the schema carries; frontmatter `type` is not consulted | always — `Unclassified topic` when no page's slug or title matches the topic's canonical spelling or one of its aliases |
| `Reviewed <date>` | that page's `last_updated` frontmatter | the page records one |
| Page content | that page's body | the page has a body left after the omissions below |

A topic with no backing page therefore shows no review date and no content, and its chip reads `Unclassified topic` — and one whose page omits `last_updated` shows no review date even while sessions supply activity dates.

### Page content

The topic page is the only browsable surface for entity and concept pages, so it renders their content above the link lists. What survives is everything after the page's own leading `# H1`, minus `## Connections`, `## Sessions`, and `## Sources` — the topic page renders Connected topics and a collapsible Sources evidence list (Sessions vs Documents) itself from the graph, so the page's hand-written versions would only duplicate them.

- **Heading-agnostic.** Nothing is keyed to `## Key Facts`; a renamed, reordered, or newly added section reaches the reader as written, as does introductory prose sitting above the first heading.
- **No empty sections.** A heading with nothing under it is dropped rather than rendered as a bare heading — innermost first, so a `##` whose only child `###` was itself empty goes too.
- **`[[wikilinks]]` resolve.** A target naming a topic links to wherever that topic resolved (its topic page, or the project page a project topic routes to); a target naming a session with a compiled page links to it; anything else degrades to the plain text it wrapped rather than a dead link. Code spans and fenced blocks are left exactly as written — a page documenting wikilink syntax keeps its example.

### Project topics route to the project page

A topic backed by a page under `wiki/projects/` links to `/projects/<slug>.html` — the full [project detail page](#project-detail-projectsslughtml) with its heatmap, session cards and charts — rather than to a thin topic page. The rewrite is applied once at build time and every surface honours it: the map's double-click target, the search index entry, Connected topics lists on topic pages and on project pages, `topics/index.html`, and `[[wikilinks]]` cited inside page content.

The match itself identifies which project it is, so an alias spelling routes as correctly as the canonical one. The rewrite is skipped when the build wrote no page for that project: `wiki/projects/` is seeded from stubs while `site/projects/` comes from session groups, so a project page with no recorded sessions keeps its ordinary topic page rather than being handed a link that 404s.

---

## Docs hub

URL: `/docs/index.html`

The editorial entry point — you're reading a page compiled from the same pipeline. Covered in detail by [`tutorials/01-installation.md`](../tutorials/01-installation.md) onward. See also [`style-guide.md`](../style-guide.md).

---
