---
title: "UI reference (part 4/8: Topic pages)"
slug: ui-reference-04
project: reference-ui
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/reference/ui.md"
content_sha256: 7656740cdc53f26b667601ea5fc167c1f813f61908c1f46377e210d82e1e05bf
---

> Part 4 of 8 of **UI reference** — Topic pages.

## Topic pages

URLs: `/topics/<slug>.html`, `/topics/index.html`

Two things make a **topic**. A name sessions cited: a `[[wikilink]]` target found in `wiki/sources/*.md`, with spelling variants clustered into one canonical name. Or — since #248 — a curated page that describes one: every page under `wiki/entities/` and `wiki/concepts/` becomes a topic whether or not any session cites it, so promoting a candidate always produces something a reader can open. A topic is therefore not the same thing as a wiki page in either direction: a derived topic renders whether or not any page under `wiki/` describes it — an un-promoted candidate, or a name a reviewer declined, keeps its page indefinitely — while every curated entity and concept gets one regardless of reach. Two page sets stay out: `wiki/archive/` (cold storage is never published) and `_`-prefixed folder-context stubs such as `wiki/entities/_context.md`, which exist only to orient an assistant.

**One topic gets no page: the one with nothing to show.** A topic is skipped when it has *no connected topics* **and** *no content of its own* — no edge in the co-occurrence graph, and nothing left of its backing page once the title, `## Connections`, `## Sessions` and `## Sources` are removed (a topic no page backs has no content of its own either). The page would carry a name, `No connected topics.` and an empty evidence list, which helps neither a reader nor an agent. Both halves are required: a reviewed page nobody co-cites still shows what it records, and a page recording nothing still shows the neighbourhood it sits in. The skip is computed once, over the node list the whole build reads, so a skipped topic has no page, no `⌘K` entry, no row or count on `/topics/index.html`, and no node in the graph — and its wiki page stays searchable in the Wiki result group with no link on the row (its corpus `url` is `null`), because the assistant still reads it. Reach topics by double-clicking a node in the [Graph](#graph), from `⌘K` (`type:topic`), from the **Topics** nav entry, or from the Connected topics list on any other topic or project page.

`/topics/index.html` lists every topic in three sections, in this order — **Entities**, **Concepts**, **Other topics** — each heading carrying that section's count. Rows keep today's reach ordering (session count, then link count) *within* each section, and a curated row carries the same kind chip the topic page's identity line shows, so a reviewed page is distinguishable from a name sessions happened to mention. An empty section renders its heading and `No topics in this group.` rather than disappearing. There are no filter or sort controls.

Three numbers are easy to conflate here. They gate different things, and only the first is configurable per vault:

| Constant | Value | Gates | Per-vault? |
|---|---|---|---|
| `DEFAULT_MIN_REFS` (`llmwiki/vault_settings.py`) | 3 | how many pages must cite a name before harvest materialises a candidate stub, and before `link_integrity` calls an unresolved link a defect | **yes** — via `llmwiki.json` |
| `min_sessions` (`llmwiki/topics.py`) | 2 | how many sessions must mention a *derived* name before it becomes a graph node | no |
| `_TOPIC_GRAPH_MIN_NODES` (`llmwiki/build.py`) | 5 | whether `graph.html` renders the topic graph at all, or falls back to the page graph | no |

A curated entity or concept page is exempt from `min_sessions`: it is seeded as a node with whatever session count it has, including zero (#248). And topic *pages* no longer follow the third number — `build` writes `topics/<slug>.html` whenever the graph carries a curated-backed node, so a vault too small for the topic viewer still gets pages for its entities and concepts while `graph.html` falls back to the page graph. The `⌘K` index carries exactly the topic pages that build wrote — which, since a vault can hold a curated page with neither content nor connections, can be fewer than the vault's curated pages.

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
