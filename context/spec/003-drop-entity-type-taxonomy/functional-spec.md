# Functional Specification: Drop the entity-type taxonomy, make Project a page kind, unify wiki search

- **Roadmap Item:** Drop hardcoded entity_type taxonomy (#102) — stop validating the old seven-value list that harvest stamps as `unknown` and that then fails lint after promote.
- **Status:** Completed
- **Author:** AWOS `/implement-feature` (interviewed with the maintainer, 2026-08-04)
- **Ticket:** [#102](https://github.com/AlexanderMakarov/llm-wiki/issues/102)

---

## 1. Overview and Rationale (The "Why")

Every wiki page can carry a label describing what kind of thing it is — one of seven fixed values (person, org, tool, concept, api, library, project). The wiki refuses any other value, including "unknown".

Three things are wrong with that label, and they compound:

**It punishes people for using the review workflow correctly.** When the wiki proposes new pages for review, it marks every proposed *entity* page as "unknown". "Unknown" is not one of the seven accepted values. So the moment a reviewer approves those pages — doing exactly what the tool asks — the wiki's own quality check reports an error on each one. A clean, fully-reviewed vault is guaranteed to show one error per approved entity. The failure is not occasional; it is total.

**The label mixes two different ideas.** Some of the seven values describe *what a page is about* (person, org, tool). Others name *what kind of page it is* — "concept" and "project" already have their own folders and their own sections in the wiki catalog. Asking a page to be an entity whose type is "concept" is self-contradictory, and asking it to be an entity whose type is "project" is a workaround for something the wiki simply cannot say: **there is no such thing as a Project page.** Every project page in a vault currently claims to be an entity, because "project" was not an available kind. The label was never a taxonomy — it was a substitute for a missing page kind.

**Nothing actually uses it.** No behaviour anywhere depends on the value. It exists to be checked against itself, and to be offered as a filter that agents rarely need.

Removing the label alone would leave the deeper problem in place, so this change also makes **Project a real page kind**, alongside Entity and Concept. That kills the last reason anything writes the label, and lets project pages stop pretending to be entities.

Removing the label also empties out the one filter agents had for narrowing a search by page kind. Rather than leave agents with no way to ask for "concepts named X" — something they never had, since only entities ever got a dedicated lookup — the two overlapping search tools are folded into **one search** that can filter by page kind. Agents get a better search than before, and migrate once rather than twice.

**Desired outcome:** a fully reviewed vault lints clean; project pages say they are projects; agents have one obvious way to search; and a wiki about any subject is no longer told its pages must be one of seven things.

**Success is measured by:** approving every pending page produces zero quality errors attributable to approval; no newly created page carries the label; and a search for a name returns matching pages of any kind, narrowable by kind.

---

## 2. Functional Requirements (The "What")

### R1 — Pages are never judged on the entity-type label

The wiki stops checking the label entirely. Pages that already carry it keep it as harmless leftover text.

- **Acceptance Criteria:**
  - [x] Given a page whose frontmatter carries `entity_type` with any value at all (including `unknown` and values outside the old seven), when the user runs the quality check, then nothing is reported about that field.
  - [x] Given an entity page with no `entity_type` field, when the user runs the quality check, then nothing is reported about its absence.
  - [x] Given a vault where every pending page has been approved into the wiki, when the user runs the quality check, then it reports no problems caused by that approval.
  - [x] Given the user asks for the check that previously enforced this label by name, then the wiki reports that no such check exists, rather than silently running nothing.

### R2 — Nothing creates the label any more

Both places that stamped the label stop doing so.

- **Acceptance Criteria:**
  - [x] Given the user runs the synthesis step and new pages are proposed for review, when the user opens any newly proposed page, then it carries no `entity_type` field.
  - [x] Given the user builds the site with project stubs seeded, when the user opens a newly created project page, then it carries no `entity_type` field.
  - [x] Given a vault with no pages at all, when the user completes a full run from sync through build, then no file anywhere under the wiki contains an `entity_type` field.

### R3 — Project is a first-class page kind

Project joins Entity and Concept as a kind a page may declare. The project folder and catalog section already exist; this makes the pages themselves honest.

- **Acceptance Criteria:**
  - [x] Given a page declares its kind as Project, when the user runs the quality check, then the kind is accepted and no "invalid kind" problem is reported.
  - [x] Given the user builds the site with project stubs seeded, when the user opens a newly created project page, then it declares its kind as Project rather than Entity.
  - [x] Given the existing project pages in the vault, when the user opens any of them, then it declares its kind as Project and carries no `entity_type` field.
  - [x] Given a project page makes claims, when the user runs the quality check, then those claims are checked exactly as they are on entity and concept pages — project pages do not silently drop out of quality checking.
  - [x] Given the user builds the knowledge graph, when project pages are ranked, then they carry the same weight entity and concept pages carry — project pages do not silently lose ranking.
  - [x] Given the wiki catalog is regenerated, when the user opens it, then project pages still appear under the Projects section with an accurate count.

### R4 — One search, able to narrow by page kind

The two overlapping search tools available to agents become a single search. It finds pages by name and by their text, and can be narrowed to one kind of page.

- **Acceptance Criteria:**
  - [x] Given an agent lists the tools the wiki offers, then exactly one search tool is present and no separate entity-search tool exists.
  - [x] Given an agent searches for a term without narrowing by kind, then matching pages of every kind are returned — entities, concepts, projects, sources and the rest.
  - [x] Given an agent narrows the search to concepts, then only concept pages are returned, and entity and project pages matching the same term are not.
  - [x] Given a term that matches one page's name and appears only in another page's body, when the agent searches, then the page matching by name is listed before the page matching only in its body.
  - [x] Given a match, when results are returned, then each result identifies the page it belongs to and shows the matching lines beneath it, rather than listing bare line matches with no page context.
  - [x] Given an agent asks to narrow by kind and to include raw session transcripts in the same request, then both requests are honoured — the kind narrows every corpus searched, so narrowing to sources returns matching source pages together with the matching raw transcripts (which are themselves sources), and narrowing to a kind no transcript carries simply returns nothing from the raw transcripts rather than an error.
  - [x] Given an agent calls the removed entity-search tool by its old name, then it receives an unknown-tool error rather than a silent no-op.

### R5 — Incomplete classification stops the run

When the wiki cannot decide whether a proposed page is an entity or a concept, it stops and explains, instead of guessing. The option to proceed on a guess is withdrawn.

- **Acceptance Criteria:**
  - [x] Given the classifier cannot be reached at all, when the user runs the synthesis step, then it stops, states that the classifier was unreachable, and creates no pages.
  - [x] Given the classifier answers but leaves some names out, when the user runs the synthesis step, then it stops, names the specific pages it could not classify, states that the answer was incomplete, and creates no pages.
  - [x] Given source pages cannot be read, when the user runs the synthesis step, then it stops and says which pages could not be read, distinctly from a classifier problem.
  - [x] Given the user looks for an option to proceed despite unclassified names, then no such option exists in the command's help or documentation.
  - [x] Given every name is classified successfully, when the user runs the synthesis step, then pages are created and no warning about unknown or unclassified pages is printed.

### R6 — The entity-type filter disappears from browsing

The site's browse filters and the agent-facing summary no longer offer to filter by entity type.

- **Acceptance Criteria:**
  - [x] Given the user opens the browse panel on the built site, then no filter for entity type is offered, and the remaining filters continue to work.
  - [x] Given an agent reads the wiki summary, then it contains no entity-type breakdown and no statement that the field must be one of a fixed set of values.

### R7 — Documentation matches the new behaviour

- **Acceptance Criteria:**
  - [x] Given the user reads the command reference, the agent-facing reference, the contributor schema guide, the setup tutorial, and the vault templates, then none of them instructs anyone to set an entity type or to filter by one.
  - [x] Given the user reads the release notes, then they record — as breaking changes — the removed quality check, the removed command option, the removed and merged search tools, and the new Project page kind.
  - [x] Given the vault template for new entity pages is used, then it does not prompt for an entity type.

---

## 3. Scope and Boundaries

### In-Scope

- Removing all checking of the entity-type label, and the dedicated check that required it to be present.
- Stopping both places that write the label: proposed-page creation during synthesis, and project stub creation during build.
- Adding Project as a page kind a page may declare, accepted by the quality check.
- Rewriting the project pages tracked in this repository to declare Project and drop the label.
- Including project pages in the quality checks and graph ranking that currently cover only entities and concepts.
- Folding the two agent-facing search tools into one search with a page-kind filter, page-level results, and name matches ranked first; removing the old tool names outright with no aliases.
- Withdrawing the option that let synthesis proceed with unclassified names, and replacing the run's misleading warning with a clear, cause-specific failure.
- Removing the entity-type filter from the site's browse panel and the agent-facing summary.
- Updating all affected documentation, templates, release notes, and tests.

### Out-of-Scope

- **The AI-model page schema.** Pages describing AI models use a *different, similarly named* field (`entity_kind: ai-model`) that drives the model index and info-cards. It is a live feature and is not touched by this work. Do not conflate the two fields.
- **A cleanup command for other people's vaults.** Pages elsewhere that still carry the label simply stop being flagged; no migration tool ships. Project pages in other vaults keep declaring Entity, which remains valid.
- **Classifying proposed pages as projects.** Proposal remains a two-way entity-or-concept decision. Projects come from session metadata during build, never from harvesting links.
- **New agent-facing tools** beyond merging the two that exist.
- **Restoring an entity-type filter anywhere**, under any name, on any surface.
- **Other roadmap items**, which are addressed in their own specifications.

### Assumptions

- Agents re-read the available tool list each session, so removing tool names outright costs at most one interrupted session — accepted deliberately in preference to carrying deprecated aliases with no removal date.
- Leftover labels on existing pages elsewhere are harmless once nothing checks them, so no data migration is required outside this repository's own vault.
