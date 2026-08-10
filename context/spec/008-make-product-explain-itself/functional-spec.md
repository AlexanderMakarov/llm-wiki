# Functional Specification: Make the product explain itself

- **Roadmap Item:** Phase 2 — Make the product self-explanatory → "README as a product page (#109)"
- **Status:** Approved
- **Author:** 4ellendger
- **Issue:** [#109](https://github.com/AlexanderMakarov/llm-wiki/issues/109)
- **Date:** 2026-08-09

---

## 1. Overview and Rationale (The "Why")

A newcomer evaluating llmwiki looks in three places — the README, the public demo site, and the documentation — and today all three misrepresent the product. They fail for one shared reason: **the demo was written by hand, not produced by the tool.**

The demo's knowledge pages open with a descriptive paragraph. The product never writes one; it writes attributed fact bullets and nothing else. A visitor therefore forms an expectation the tool cannot meet, and their own first wiki looks broken by comparison. The README compounds this by opening with the story of how this fork came to be instead of what the reader gets. And no document anywhere says what a wiki actually contains — which kinds of page exist, what each carries, or where that information came from.

Two further problems share the same root. The repository root doubles as a working vault, so it is unclear which folders are the product, which are the demo, and which are somebody's local data. And the agent instructions at the top of the repo are written for a person who has cloned it — yet users who install through Homebrew or pip get the command-line tool with none of those agent commands, and are implicitly expected to run their agent sessions inside our repository. That expectation is wrong and it is the reason packaged installs feel incomplete.

None of these can be fixed independently. A README written against a fabricated demo advertises something users will not recognise. A page-kind reference written from the same demo documents behaviour that does not exist. And neither can be written at all until the repository makes clear what the demo is. Rebuilding the demo through the real pipeline is what produces the honest material everything else depends on.

**Desired outcome:** every surface a newcomer meets is either genuine product output, or an accurate description of it — and a user who installs the tool never needs to visit our repository.

**Success is measured by:**

- A reader can predict what their own wiki will look like from the demo alone.
- Every folder the product creates can actually be filled.
- Every field on a documented page has a stated origin.
- Someone who installs through Homebrew gets the full experience, including the agent commands, without cloning anything.

---

## 2. Functional Requirements (The "What")

### R1 — The repository separates the product, the demo, and the contributor's workspace

- **As a** newcomer opening the repository, **I want** to see immediately which folders are the product and which are an example, **so that** I do not mistake demonstration content for something I am supposed to edit.
  - **Acceptance Criteria:**
    - [ ] The demo lives in one self-contained folder holding its own source material, its knowledge pages, and its built site. Nothing about the demo sits loose at the top level.
    - [ ] The repository root is no longer usable as a knowledge base itself — building or synthesising without naming a target no longer scatters working folders across the root.
    - [ ] The outdated video assets are removed.
    - [ ] The hand-written interface surface descriptions currently sitting in their own top-level folder are relocated under the documentation folder.
    - [ ] The contributor workspace folder that holds specifications and delivery records stays where it is, and is identified in the contributor guide as contributor tooling.
    - [ ] A newcomer reading the top-level folder listing can tell, without opening anything, which folder is the demo.

### R2 — The demo is genuine output of the tool, about the tool

- **As a** newcomer browsing the public demo, **I want** the example wiki to be real output of the tool describing the tool, **so that** I can trust it as a preview of what I will get.
  - **Acceptance Criteria:**
    - [ ] The demo's source material is the project's own documentation, rather than invented unrelated projects.
    - [ ] Every knowledge page in the demo was produced by running the tool, not typed by a person.
    - [ ] No page in the demo has a layout the tool cannot produce. In particular, no knowledge page opens with a descriptive paragraph.
    - [ ] Opening any demo knowledge page shows a title, then facts, with each fact linking back to the material it came from.
    - [ ] The demo covers llmwiki's own subject matter — its commands, its browsable site, and how it reads agent sessions.

### R3 — One command refreshes the demo, and only redoes what changed

- **As a** maintainer who has just edited the documentation, **I want** one command that refreshes the demo, **so that** keeping it current is routine rather than a project.
  - **Acceptance Criteria:**
    - [ ] A single documented command refreshes the demo end to end: take in the changed documentation, summarise it, rebuild the site.
    - [ ] Which documents count as changed is read from the project's own version history. It is **not** judged by file timestamps, and the command keeps no separate record of its own for this purpose.
    - [ ] Two people running the command at the same revision agree on what needs redoing, and so does a fresh copy of the repository.
    - [ ] Editing one documentation page and re-running the command re-summarises **only** that page. Untouched pages are left alone.
    - [ ] Adding a documentation page adds exactly one corresponding demo page. Deleting one removes its demo page and everything derived from it, leaving no orphans behind.
    - [ ] A documentation page that has been edited but not yet committed is still picked up, so a maintainer can preview before committing.
    - [ ] Refreshing an edited page keeps that page's existing address, so links to it from other demo pages keep working.
    - [ ] Running the command twice with no documentation changes does nothing the second time, and never leaves a duplicate copy of a document behind.
    - [ ] The command reports what it is about to redo before doing it, and offers a preview mode that changes nothing.
    - [ ] Refreshing is a local activity. The automated build never attempts it and never needs an AI model.
    - [ ] The documentation for the command states what the maintainer needs available beforehand, and what happens if it is missing.
    - [ ] A follow-up issue records the underlying product gap — that llmwiki itself cannot update an already-ingested document in place, which is why the demo has to work around it.

  - **Known constraint this requirement works around:** adding an already-ingested document again does not update it. It lands a second copy under a new address and leaves the original in place; only removing the original first preserves the address. Verified by experiment. The demo refresh therefore has to remove and re-add each changed document rather than simply re-adding it. Nothing in this work changes that behaviour for user vaults.

### R4 — The demo is provably clean

- **As a** maintainer, **I want** the demo checked automatically, **so that** a broken example cannot reach the public site.
  - **Acceptance Criteria:**
    - [ ] After regeneration, running the quality check against the demo reports zero errors.
    - [ ] The same check runs automatically on every change, and fails the build when the demo reports an error.
    - [ ] Warnings are printed for the maintainer to read, but do not fail the build. One warning is expected by design and is not a defect: the freshness check reports how long ago a page was last updated, which on a committed demo measures nothing but elapsed time and would otherwise turn the build red on a timer.
    - [ ] The failure message identifies which demo page is at fault.
    - [ ] A follow-up issue proposes letting a vault opt out of individual quality rules, so the demo can enforce warnings too once the freshness check can be excluded.

### R5 — The demo site is published automatically

- **As a** newcomer, **I want** to browse a live demo without installing anything, **so that** I can evaluate the product in a browser.
  - **Acceptance Criteria:**
    - [ ] The demo site is published to GitHub Pages automatically when changes land.
    - [ ] Publishing uses the committed demo content and needs no AI model.
    - [ ] The README links to the published demo.

### R6 — A knowledge page records attributed facts, and nothing the tool cannot produce

- **As a** reader of any wiki page, **I want** the page body to be exactly what the tool can generate, **so that** the demo, the documentation, and my own wiki all agree.
  - **Acceptance Criteria:**
    - [ ] Knowledge pages keep their current shape: attributed fact bullets under a facts heading, with no synthesised introductory paragraph.
    - [ ] This specification records that a synthesised description was considered and deliberately not adopted, with the reason.
    - [ ] A follow-up issue exists proposing a description-generating step, so the idea is tracked rather than lost — [#137](https://github.com/AlexanderMakarov/llm-wiki/issues/137).

### R7 — Only page kinds that can be filled are advertised

- **As a** user opening a new wiki, **I want** every folder the tool creates to be one that can hold something, **so that** empty folders do not imply missing features.
  - **Acceptance Criteria:**
    - [ ] Open questions and comparisons are removed as page kinds: a new wiki no longer creates those folders, no export mentions them, no view offers them as a category or colour, and no document describes them.
    - [ ] Both removals are recorded in the declined-decisions log with the date and a one-line reason.
    - [ ] The site's existing automatically generated model comparison view is unaffected — it is a different feature that happens to share a name.
    - [ ] Saved answers remain available, and every place describing them says plainly that they are written by an agent or a person, not generated automatically.
    - [ ] An existing wiki that already contains the removed folders still builds and passes its quality check after upgrading, without the user having to delete anything by hand.

### R8 — A reference explains what a wiki contains and where each field comes from

- **As a** user or contributor, **I want** one page describing every kind of page and the origin of every field on it, **so that** I can tell what the tool decided from what I am expected to fill in.
  - **Acceptance Criteria:**
    - [ ] A documentation page describes every surviving page kind, each illustrated with a real example taken from the rebuilt demo.
    - [ ] For every field on every kind, the page states its origin: written when summarising, written when collecting candidates, worked out by the site build, or only ever filled in by a person.
    - [ ] Fields that are conventionally absent are called out as intentionally absent, with the reason — including that project pages carry no freshness date of their own, so a project's freshness comes from its sessions.
    - [ ] The interface reference covers topic pages. *(Already satisfied by #108 / PR #128 — verify, do not rewrite.)*

### R9 — The README is a product page

- **As a** newcomer, **I want** the README to open with what I get, **so that** I can decide whether the tool is for me without reading its history.
  - **Acceptance Criteria:**
    - [ ] The README opens by explaining what the reader ends up with, before any command block, and the "what you get" material appears near the top.
    - [ ] No fork or lineage history appears at the top; attribution appears only under Acknowledgements and License.
    - [ ] The stated Python version matches what the project actually requires and what the automated checks run.
    - [ ] There is one agent table with one row per agent, showing whether it can supply sessions, whether it can read the wiki, and whether it is built in or opt-in. Claude Code and Codex CLI are the only built-in suppliers; Copilot Chat, Copilot CLI, Gemini CLI, Obsidian, Cursor, Cursor CLI, OpenClaw, OpenCode and ChatGPT are all opt-in.
    - [ ] Managing a wiki is explained in plain words as sync or add → summarise → review suggestions → build, with the review step described as a real gate a person passes through.
    - [ ] No fact appears twice: the duplicated tutorial, how-it-works and command-list material is reduced so each point is stated once.
    - [ ] The manual-queue material and the per-path exclusion table are removed or reduced to a single sentence, with any surviving detail moved into a real documentation page.
    - [ ] Every link in the README and in changed documentation resolves, and the automated link check passes for the files this work touches.

### R10 — Users get the agent commands without cloning the repository

- **As a** user who installed through Homebrew, **I want** the agent commands available on my machine, **so that** I can use llmwiki from my own projects instead of working inside somebody else's repository.
  - **Acceptance Criteria:**
    - [ ] The user-facing agent commands and skills live in their own dedicated folder, clearly separate from the contributor ones. Contributor-only material — the delivery workflow, release, triage, testing and build-diagnosis helpers — is not part of it.
    - [ ] Those user-facing files travel inside the installable package, so a Homebrew or pip install carries them. This is what makes a packaged install complete.
    - [ ] A documented command installs them onto the machine so any agent can use them from any directory, and reports where it placed them.
    - [ ] Re-running that command after an upgrade refreshes the installed copies and says what it changed.
    - [ ] The command does not overwrite a user's own customisations without warning.
    - [ ] After installing, a user can operate their own knowledge base from their own project folder, with this repository nowhere involved.
    - [ ] The contributor-facing agent instructions at the top of the repository state plainly that they are for people working on llmwiki itself, and point users at the installed commands instead.
    - [ ] The user-facing commands make no reference to paths that only exist inside this repository.
    - [ ] The existing agent-plugin description files are either corrected to match reality or removed. They must not remain in the repository describing an author, a supported language version, and file locations that are all wrong.

### R12 — The wiki is a static site with no server

- **As a** user, **I want** my wiki to be plain files I can open, **so that** nothing has to be running for me to read it and nothing consumes resources when I am not using it.
  - **Acceptance Criteria:**
    - [ ] The product no longer ships a command that starts an HTTP server, and the one-click serve helper scripts are gone.
    - [ ] A built site is fully usable by opening its home page as a file: navigation, project pages, session pages, topic pages, search and the graph all work with nothing running.
    - [ ] A built site needs no network either. Every script and stylesheet it loads ships with the site, including the code-highlighting library and its light and dark themes. Opening the site offline gives the same result as opening it online.
    - [ ] Reviewing candidates is possible entirely from the command line, and no review capability is lost — the batch action format the old review page posted is already accepted by the command line.
    - [ ] The candidates page still lists what is pending and states plainly how to act on it, rather than offering controls that cannot work.
    - [ ] No document, agent instruction, or built page tells a reader to start a server in order to view their wiki. Every such place says to open the site instead.
    - [ ] A user who previously started a server is told what to do instead, in the upgrade notes.

### R13 — What the site shows for a local path is an explicit choice

- **As a** maintainer publishing a site, **I want** the paths it displays to be something I chose, **so that** the same knowledge base always produces the same pages no matter who builds it.
  - **Acceptance Criteria:**
    - [ ] Building the same knowledge base twice, on two different machines, produces the same displayed paths.
    - [ ] The value shown in place of a stored home directory is a build-time input: taken from the current run by default, and replaceable with a fixed string.
    - [ ] The demo and the automated publish both supply that fixed string, so a published page never shows whoever happened to build it.
    - [ ] The displayed value is no longer worked out by undoing the redaction applied when the session was imported, so the two can no longer disagree.
    - [ ] Only path-shaped values are substituted. Free prose carried over from a session is left alone.
    - [ ] A person browsing their own site locally still sees paths they can act on, without extra configuration.

### R11 — Delivery order

- **As a** reviewer, **I want** the work split so each review is tractable while the dependency order still holds.
  - **Acceptance Criteria:**
    - [ ] Stage A delivers R1, R6 and R7 — repository layout, page body decision, page kinds settled. These decide what the demo can contain.
    - [ ] Stage B delivers R2, R3, R4 and R5 — the rebuilt demo, its regeneration command, its quality gate, and its publication.
    - [ ] Stage C also delivers R13 — displayed local paths become an explicit build input — because the demo cannot be published deterministically until it does.
    - [ ] Stage C delivers R12 first — the server is removed and candidate review moves to the command line — then R8, R9 and R10: the reference page, the README, and the user-facing command split. R12 leads because the documents written afterwards must describe a static-file product.
    - [ ] Each stage builds on the previous one on a single branch chain, preserving the issue's required ordering.
    - [ ] Stage C cites the demo produced in Stage B for its examples.

---

## 3. Scope and Boundaries

### In-Scope

- Moving the demo into one self-contained folder and clearing the repository root of vault-shaped working folders.
- Removing outdated video assets and relocating the interface surface descriptions under the documentation folder.
- Replacing the demo corpus with material about llmwiki, generated by running the tool over the project's own documentation.
- A local, documented, incremental demo-refresh command whose change detection reads the project's own version history.
- A quality gate on the demo, enforced locally and automatically.
- Publishing the demo site automatically.
- Removing open questions and comparisons as page kinds wherever they are created, exported, coloured, listed or described; keeping saved answers and describing them honestly.
- A reference page covering page kinds and field origins.
- Rewriting the README as a product page.
- Separating contributor instructions from user-facing agent commands, packaging the latter, and providing an install command.
- Recording removals in the declined-decisions log, and filing a follow-up issue for a description-generating step.

### Out-of-Scope

- **A synthesised description on knowledge pages** — considered and deliberately not adopted. No step in llmwiki produces one: the summarising prompt mandates attributed bullets with no preamble, and a newly harvested page is seeded as a title plus an empty facts heading. Adding one would be a new AI-generated field with its own per-page cost and quality bar, so it is deferred to [#137](https://github.com/AlexanderMakarov/llm-wiki/issues/137) rather than folded into this epic (R6).
- **Producers for open questions and comparisons** — those kinds are being removed instead.
- **Link-check hygiene as a project (#107)** — a separate ticket that should land first; this work owns only the links in files it changes.
- **The site's automatically generated model comparison view** — unrelated to the comparisons page kind, left alone.
- **Rewriting the topic-pages section of the interface reference** — already delivered by #108.
- **Regenerating the demo automatically** — explicitly rejected; regeneration stays a local maintainer activity.
- **Changing how any user's knowledge base decides what is out of date** — explicitly rejected. The demo's version-history-based change detection applies to the demo alone; user vaults keep today's behaviour untouched.
- **Giving the product a way to update an already-ingested document in place** — a real gap, worked around by the demo refresh and recorded as a follow-up issue (R3).
- **Changing how sessions are read from any agent** — adapters are untouched.
- Everything else on the roadmap: honest estimate preview (#113), migration inventory, CLI help as a lifecycle map (#112), health check (#110), Cursor session parsing (#2), Cursor-compatible AWOS (#114), MCP protocol upgrade (#78), Cowork ingest (#31), chat ingest (#32), project aggregation (#126).

### Open Points for Approval

- **The contributor workspace folder stays.** It was listed for removal, but it holds this specification and the delivery record, and it is contributor tooling rather than vault content — so it is treated as belonging on the contributor side of the split. Overrule here if you want it moved or removed.
- **The demo refresh only sees committed and working-copy changes.** Reading change from version history means the command must be run inside a working copy of the repository. That matches "local maintainer activity", but it does mean the demo cannot be refreshed from a downloaded release archive.
