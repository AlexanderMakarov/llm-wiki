# Functional Specification: Topic pages show what the wiki knows about a topic

- **Roadmap Item:** Phase 3 — Visual knowledge depth: "Topic pages show kind, freshness, and Key Facts (#108): Entity/concept content reaches readers; project topics route to project pages; graph panel shows the same metadata."
- **Status:** Completed
- **Author:** AWOS `/implement-feature` (issue #108)

---

## 1. Overview and Rationale (The "Why")

A reader exploring the knowledge map double-clicks a bubble and lands on a page that tells them almost nothing: a count of sessions, a count of connections, and two lists of links. They cannot tell whether the bubble is a person, an idea, or a codebase. They cannot tell whether it was last touched this week or a year ago. And the facts the wiki has actually collected and a human has actually reviewed — the most valuable layer in the whole product — do not appear at all.

This matters more than a cosmetic gap. People and ideas get **no page of their own** anywhere on the browsable site. The topic page is the only surface where that curated content could ever reach a human reader, and today it shows none of it. The product promises "a visual representation of saved knowledge areas so a human can understand the landscape in a few seconds and then explore in depth" — the landscape works, the depth does not.

Projects have the opposite problem: they already have a rich page (activity heatmap, tool-call chart, token timeline, session cards) that a reader arriving from the map never sees, because the map sends them to a stripped-down topic page instead.

The map itself hides the same information one level earlier. Codebases are drawn in the same colour as unfiled names — the two most different things in the map — so the legend offers distinct labels against swatches a reader cannot tell apart.

**Desired outcome:** opening any bubble in the map answers, within a second — what kind of thing is this, how current is it, how connected is it, and what does the wiki know about it. For projects, it answers those questions on the full project page rather than a thin substitute. And the map answers the first of those questions before anything is clicked.

**Success measures:**
- A reader can name the kind of any topic without opening the underlying wiki file, and can tell kinds apart in the map by colour alone.
- The recorded content of people and idea pages becomes reachable from the browsable site for the first time.
- Opening a project from the map and opening it from the Projects tab land on the same page.
- No page shows an invented date, an empty section heading, or an error when the underlying information is absent.

---

## 2. Functional Requirements (The "What")

### FR1 — Every topic page opens with an identity line

- **As a** reader arriving from the knowledge map, **I want** the top of the page to tell me what this thing is and how big it is, **so that** I can decide in one glance whether to read on.

The identity line sits directly under the topic's title and carries, in order: a chip naming the kind, the dates (FR2), how many topics it connects to, how many sessions mention it, and the short name used in its web address.

In practice a topic is an Entity, a Concept, a Project, or nothing yet. A topic no page describes is labelled **Unclassified topic** rather than left blank — the absence of a page is itself a fact worth showing, and a reader seeing no chip cannot tell whether the topic is unclassified or whether the page simply failed to say. The wiki recognises further kinds, but no page of those kinds can currently be reached from a topic; they are handled generically rather than designed for.

- **Acceptance Criteria:**
  - [x] Given a topic described by an Entity, Concept or Project page, when I open its page, then the title is followed by a chip naming that kind.
  - [x] Given any topic page, when I open it, then the identity line shows how many topics it is connected to and how many sessions mention it.
  - [x] Given any topic page, when I open it, then the identity line shows the short name used in the page's web address.
  - [x] Given a topic with **no** backing wiki page, when I open its page, then the chip reads **Unclassified topic**, the remaining information still renders, and there is no blank field, placeholder, or error anywhere on the page.
  - [x] Given a topic described by a page of any other kind the wiki recognises, when I open its page, then it shows the same identity line with that kind named — no special handling and no error.

### FR2 — Freshness comes from real evidence, and is never invented

- **As a** reader, **I want to** know when a topic was last active and when it was last reviewed by a person, **so that** I can judge how much to trust what I am reading.

Two different facts, shown as two different things. **Activity** is derived from the sessions that mention the topic: the oldest one is when it was first seen, the newest is when it was last seen. **Review** is the date the topic's own wiki page records for itself, which is when a human or agent last curated it.

- **Acceptance Criteria:**
  - [x] Given a topic mentioned by at least one session, when I open its page, then it shows the date of the oldest session that mentions it and the date of the newest.
  - [x] Given a topic whose backing wiki page records its own last-reviewed date, when I open its page, then that date is shown as well, labelled so it reads as distinct from the session activity dates.
  - [x] Given a topic with no session dates and no recorded review date, when I open its page, then no date is shown at all — no placeholder, no "unknown", and no date taken from anywhere else.
  - [x] Given a project, when I open its page, then it shows a created date taken from its oldest session and an updated date taken from its newest session, and both stay correct as new sessions arrive without anyone editing anything by hand.

### FR3 — The curated content reaches the reader

- **As a** reader, **I want to** see what the wiki has recorded about a person or idea on the page I land on, **so that** the reviewed knowledge is actually usable without opening files by hand.

This content is the payload of an entity or concept page; the link lists are context. It therefore appears above the connections. The page shows whatever the recorded content is — a list of facts today, coherent prose if the wiki later records it that way — without imposing a shape of its own.

- **Acceptance Criteria:**
  - [x] Given a topic that is an Entity or a Concept whose backing page records content about the subject, when I open its page, then that content appears in full, formatted as it is written, positioned above the connected-topics list.
  - [x] Given a backing page whose recorded content is empty or absent, when I open its page, then no heading for it appears at all — not an empty section.
  - [x] Given a backing page that carries introductory text above that content, when I open its page, then the text is shown above it rather than discarded.
  - [x] Given content that references other topics, when I open the page, then those references are shown as working links to the referenced topic pages, and a reference to something with no page of its own is shown as plain text rather than a dead link.

### FR4 — Project topics take the reader to the project page

- **As a** reader who clicks a codebase in the map, **I want** the real project page, **so that** I get the same depth I would get from the Projects tab.

A topic is only ever labelled a Project because its name, or one of the alternative spellings sessions used for it, already matched a project's own page. That match therefore identifies **which** project it is; nothing needs to be guessed from the spelling.

- **Acceptance Criteria:**
  - [x] Given a topic labelled Project, when I open it from the map, then I arrive at the page of the project it matched — including when the spelling sessions used for it differs from that project's own short name.
  - [x] Given a project that has a page in the wiki but no page on the site — because no session has been recorded against it — when I open its topic from the map, then I get an ordinary topic page with its identity line, connections and sessions, with no error and no broken link.

### FR5 — Project pages gain the connections readers would otherwise lose

- **As a** reader sent to a project page from the map, **I want to** see what topics the project touches, **so that** nothing is lost by being sent here instead of to a topic page.

- **Acceptance Criteria:**
  - [x] Given a project page, when I open it, then it shows a **Project** kind chip in its header, so a reader who arrived by clicking a project in the map sees the same kind label they would have seen on a topic page.
  - [x] Given a project page, when I open it, then it shows a Connected topics list in the same form as on topic pages, positioned immediately above the list of sessions.
  - [x] Given a project with no connected topics, when I open its page, then no Connected topics heading appears — not an empty section.

### FR6 — Every kind is visually distinct in the map

- **As a** reader scanning the map, **I want** each kind to have its own colour, **so that** I can tell a codebase from an idea from an unfiled name without clicking anything.

Entities and concepts already have their own colours. Projects do not — they share a colour with topics that no page describes, which are the least similar things in the map: one is a codebase the reader can open and explore, the other is a name nobody has written about yet. The legend lists them separately regardless, so it presents two labels against one swatch.

Every kind is equally saturated — nothing is muted. A topic no page describes is a normal citizen of the map, not a faded placeholder.

| Kind | Colour | |
| --- | --- | --- |
| Sources | violet | `#7c3aed` — existing |
| Entities | blue | `#2563eb` — existing |
| Concepts | green | `#059669` — existing |
| Syntheses | amber | `#d97706` — existing |
| Projects | magenta | `#db2777` — new |
| Questions | cyan | `#0891b2` — new |
| Comparisons | brown | `#b45309` — new |
| Undescribed | lime | `#65a30d` — new |

Red is deliberately absent: the map already uses it for two states — a page nothing links to, and a live search hit. A kind sharing that colour would make undescribed topics read as errors.

- **Acceptance Criteria:**
  - [x] Given a map containing projects and topics that no page describes, when I look at it, then the two are drawn in visibly different colours.
  - [x] Given a map containing topics of several kinds, when I look at it, then no two kinds share a colour.
  - [x] Given the legend, when I read it, then each entry's swatch matches the colour used for that kind in the map, and no two entries share a swatch colour.
  - [x] Given the map in either light or dark theme, when I look at it, then every kind's colour remains distinguishable from the others.

### FR7 — The map's side panel says the same things as the page

- **As a** reader skimming the map, **I want** the panel that opens on a single click to carry the same identity information, **so that** I can triage without opening every page.

- **Acceptance Criteria:**
  - [x] Given any topic in the map, when I select it, then the side panel names its kind alongside the session and connection counts it already shows.
  - [x] Given a topic with recorded dates, when I select it in the map, then the panel shows the same freshness information the topic page shows.
  - [x] Given a topic with no backing wiki page, when I select it in the map, then the panel labels it **Unclassified topic**, omits the review date, and shows no empty rows or error.

### FR8 — Topics with no page of their own still work

- **As a** user whose wiki is partly curated, **I want** every page to render, **so that** an unfinished vault is still browsable.

A topic exists because a source page mentions it, not because anyone has written a page about it. Names awaiting review, and names a reviewer declined, therefore stay in the map indefinitely with nothing behind them. This is the normal resting state of a working vault, not a rare fault.

- **Acceptance Criteria:**
  - [x] Given a topic that no wiki page describes, when I open its page, then it renders with its connections and sessions, is labelled **Unclassified topic**, shows no review date, and contains no empty section heading and no field label with nothing after it.
  - [x] Given a wiki mixing described and undescribed topics, pages with and without recorded content, and pages with and without dates, when the site is generated, then it completes without error and every topic page opens.

### FR10 — Opening a topic behaves consistently

- **As a** reader, **I want** links to behave the way links behave everywhere else in the site, **so that** I do not lose my place unexpectedly.

Everywhere in the generated site a link opens in the current tab. The map is the exception: it opens a new tab from the side panel, from the right-click menu, and on double-click. Only the double-click — a deliberate "take this somewhere else" gesture — should do that.

- **Acceptance Criteria:**
  - [x] Given the map's side panel, when I use its Open page link, then the page opens in the current tab.
  - [x] Given the map's right-click menu, when I choose its open action, then the page opens in the current tab.
  - [x] Given a session link in the side panel, when I follow it, then it opens in the current tab.
  - [x] Given a node in the map, when I double-click it, then its page opens in a new tab.

### FR11 — Search names the kind, not just "topic"

- **As a** reader searching, **I want** a result to say what kind of thing it is, **so that** the search results agree with the map and the topic pages.

A search result for an entity reads "Entity", not "Topic". The underlying result type stays as it is, so existing filters keep working.

- **Acceptance Criteria:**
  - [x] Given a search result for a topic backed by an entity page, when I look at it, then it is labelled Entity rather than Topic.
  - [x] Given a search result for a topic no page describes, when I look at it, then it is labelled consistently with what the map and topic page call it.
  - [x] Given the existing type filter for topics, when I use it, then it still matches every topic result.

### FR9 — The change is documented

- **Acceptance Criteria:**
  - [x] Given the change ships, then `CHANGELOG.md` describes it under `## [Unreleased]`.
  - [x] Given the change ships, then `docs/reference/ui.md` gains a section describing topic pages, which it does not document today, and its Projects and Graph sections describe the connections list and the per-kind colours.
  - [x] Given a reader consults the documentation, then it states which information on a topic page comes from sessions and which comes from the topic's own page.

---

## 3. Scope and Boundaries

### In-Scope

- The identity line (kind, dates, connection counts, short name) on every topic page.
- Session-derived first-seen / last-seen dates for every topic, and created / updated dates for projects.
- The recorded content of Entity and Concept pages, and any introductory text above it, on their topic pages.
- Project topics resolving to their project page, with a clean fallback when the project has no site page.
- A Connected topics list on project pages.
- A distinct colour per kind in the knowledge map and its legend.
- Kind and freshness in the knowledge map's side panel.
- `CHANGELOG.md` entry and `docs/reference/ui.md` updates.

### Out-of-Scope

- **How sessions are grouped into projects — [#126](https://github.com/AlexanderMakarov/llm-wiki/issues/126).** A project's identity is derived from the folder path a session ran in, so the same project reached through a clone or a git worktree becomes two separate projects, and a one-word project name can split across two coding agents. Changing it would rewrite project identity, page addresses and stored session records — a different concern from displaying what is already known.
- **Naming the coding agents that worked on a project.** Sessions are grouped without regard to which agent produced them, so a project page can already hold sessions from several agents — but only when the adapters happen to derive the same name for the folder. Until #126 makes that reliable, a list of agents on a project page would be right by luck. Deferred with #126.
- **Whether the wiki records prose or a fact list — [#109](https://github.com/AlexanderMakarov/llm-wiki/issues/109).** What a page records about its subject is decided when the wiki is written, not when it is displayed; this change shows whatever is there. Folded into #109 alongside the demo rebuild, where the result becomes visible.
- **Kind-specific layouts for Question, Comparison, Synthesis and Source.** No page of those kinds can currently reach a topic — nothing writes into `wiki/questions/` or `wiki/comparisons/` at all, and synthesis pages are not referenced by the source summaries the map is built from. They are handled generically so they never break, and whether they should exist is a question for the fork-residue inventory ([#109](https://github.com/AlexanderMakarov/llm-wiki/issues/109) settles it), not for this change.
- **New metadata fields on wiki pages.** This change displays information the wiki already holds, plus dates derived from sessions it already has. Richer per-kind metadata is deferred to its own issue.
- **Documenting every page kind and where its metadata comes from — [#109](https://github.com/AlexanderMakarov/llm-wiki/issues/109).** This change documents the topic and project pages it touches; the full per-kind reference rides with the demo rebuild.
- **Giving entities and concepts their own site pages.** The topic page remains their only surface; this change makes that surface useful rather than adding a new one.
- Every other roadmap item — Phase 1 honest pipeline reporting (#81, #113), fork residue cleanup (#107), migration inventory, Phase 2 documentation and `llmwiki doctor` (#112, #110), Cursor session parsing (#2), Cursor-compatible AWOS (#114), and everything under Later/deferred.
