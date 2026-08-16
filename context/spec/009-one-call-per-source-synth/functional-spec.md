# Functional Specification: One synthesis pass per source — topics, kind, facts, and description together

- **Roadmap Item:** GitHub Issue [#147](https://github.com/AlexanderMakarov/llm-wiki/issues/147) — collapse synthesis so each source is read by the language model once; harvest, promote, and name-deduping become work over what that pass already wrote. Also covers interrupt recovery from [#145](https://github.com/AlexanderMakarov/llm-wiki/issues/145).
- **Status:** Approved
- **Author:** AWOS `/implement-feature` (issue #147)

---

## 1. Overview and Rationale (The "Why")

Turning a conversation into wiki knowledge currently asks the language model **four** times about the same material: once to summarise the source, again to guess whether each name is a person/product or an idea, again to write facts when a reviewer promotes a pending page, and again in a separate “merge duplicate names” pass. Three of those happen *after* the model has already read the source.

That shows up as cost, wait, and a broken review path: **promoting a pending person or idea refuses unless a language model is configured**, so a reviewer with no model set up cannot finish review. Duplicate spellings of the same name wait on that extra merge-duplicates command. And if a long synthesis run is interrupted, the source pages already written sit unused: pending names are not collected from them, Home’s “synthesized” counts stay at zero, and restarting does not pick up the names those pages already discovered.

**Desired outcome:** each source is summarised **once**. That same answer already says, for every person or idea it names, what kind of thing it is, which facts this source supports, and a short description. Collecting pending names, promoting them, and avoiding duplicate spellings are then ordinary bookkeeping over those recorded answers — including with no language model configured. A long run can be stopped with Ctrl+C and continued; the second run starts knowing the names the first run already found.

**Success is measured by:** a catch-up synthesis of N sources makes N language-model asks for those sources, plus **one** known-names ask at the start of the run — not a classify/facts/dedupe ask per name or per promote; a reviewer with no language model configured can promote and get a fact list; interrupting and restarting a 100-source run collects pending names from what was written and the second run’s known-names list includes them; Home’s synthesized counts match the pages on disk after the next site rebuild; the old merge-duplicates command is gone from help and from agent instructions.

Honest accounting: **one amortised language-model ask per synthesis run** (prepare the known-names list from what is already in the wiki) **plus one ask per new source**. Harvest and promote add none. The known-names ask is not repeated mid-run.

---

## 2. Functional Requirements (The "What")

### FR1 — One language-model pass per source produces the summary and the topic details

- **As an** operator, **I want** each source summarised in a single pass that also records, for every person or idea it names, whether it is a person/product or an idea, the facts this source supports, and a short description, **so that** later steps do not re-read the same conversation.

The known list of people and ideas already in the wiki is prepared once at the start of the run (FR5) and shown to every source pass so the model reuses existing names instead of inventing near-duplicate spellings.

- **Acceptance Criteria:**
  - [ ] Given a pending source, when synthesis writes its summary, then that summary names the people and ideas it is about and, for each, records a kind (person/product vs idea), the facts this source supports, and a short description — without a second language-model ask for that source.
  - [ ] Given a vault that already has people and ideas on file, when a new source is synthesized, then the pass can see those existing names and prefers them over a new spelling of the same thing.
  - [ ] Given a source that names nothing worth filing, when it is synthesized, then it still gets a normal summary and does not invent empty people or ideas.

### FR2 — Existing summaries are rewritten once so the vault matches the new shape

- **As an** operator upgrading a vault that already has source summaries, **I want** the next synthesis run to rewrite those summaries so they carry the same per-topic details as new ones, **so that** I do not keep two generations of pages.

After that catch-up, only sources that are new or otherwise out of date are synthesized, as today.

- **Acceptance Criteria:**
  - [ ] Given a vault whose source summaries were written before this change, when the operator runs synthesis, then those summaries are treated as out of date and rewritten with the per-topic details in FR1.
  - [ ] Given a vault whose source summaries already carry those details and are otherwise up to date, when the operator runs synthesis, then those sources are not rewritten again.

### FR3 — Collecting pending names does not ask the language model

- **As an** operator, **I want** pending people and ideas collected by counting how often they are named across source summaries and reading the kind already recorded there, **so that** harvest does not cost a second pass over material already paid for.

- **Acceptance Criteria:**
  - [ ] Given source summaries that already record kind and facts per named topic, when pending names are collected, then each pending page’s kind matches what those summaries recorded — with no extra language-model ask.
  - [ ] Given the same sources, when pending names are collected, then the pending page’s fact list is the facts those sources already recorded for that name, concatenated, with no extra language-model ask.
  - [ ] Given a reviewer with no language model configured, when they run synthesis in a mode that only collects pending names from existing summaries, then collection still completes.

### FR4 — Promoting works with no language model configured

- **As a** reviewer, **I want** to promote a pending person or idea and keep the facts already collected on that page, **so that** review does not depend on a model being available.

Pending pages and promoted pages share the same shape: promote is a move, not a rewrite. Facts a reviewer already edited are not overwritten.

This must not go back to assembling a “fact” by clipping a sentence near a name in a source page. That path produced fragments about the wrong subject and was replaced because it looked like prose while being untrustworthy. Facts stay authored in the source pass (FR1), then copied.

- **Acceptance Criteria:**
  - [ ] Given a pending page that already lists facts from its sources, when the reviewer promotes it with no language model configured, then the promoted page exists, carries those facts, and the pending page is gone.
  - [ ] Given a pending page whose fact list a reviewer has already edited, when they promote it, then the edited facts are what appear on the promoted page.
  - [ ] Given promote, when it fills facts, then it does not invent bullets by clipping text near a name in a source page.

### FR5 — The known-names list is prepared once per synthesis run, before any new source

- **As an** operator synthesizing many sources, **I want** one known-names list for the whole run, **so that** in-flight pages are never cancelled and I am not billed a second list-building pass mid-run.

At the **start** of each synthesis run the language model is asked **once** to prepare that list from people, ideas, and pending names already in the wiki (canonical spellings, kind, and a short description). That ask replaces the old classify-each-name, write-facts-on-promote, and merge-duplicates prompts. The list is **not** rebuilt when a new pending name appears during that same run. Names discovered in this run become visible to synthesis only on the **next** run (including a restart after Ctrl+C), when job 1 runs again over the pages now on disk.

Consequence, accepted: if 100 sources are synthesized in one uninterrupted run, a spelling discovered in the first source is not on the known-names list for the hundredth source of that same run. Stopping and restarting is how the list converges.

- **Acceptance Criteria:**
  - [ ] Given a synthesis run of many pending sources, when it starts, then the known-names list is prepared before the first new source is summarised, and that same list is what every source of the run sees — it is not rebuilt part-way through.
  - [ ] Given a vault that already has people, ideas, or pending names, when that preparation runs, then the list carries canonical spellings, a kind (person/product vs idea), and a short description, without a separate classify, facts-on-promote, or merge-duplicates command.
  - [ ] Given that run is interrupted and the operator starts synthesis again, when the second run begins, then its known-names list is prepared from disk including people, ideas, and pending names produced from the pages the first run wrote.
  - [ ] Given pages already in flight when the operator presses Ctrl+C, when shutdown proceeds, then those in-flight pages are allowed to finish rather than being cancelled.
  - [ ] Given a vault with no people or ideas on file yet, when synthesis starts, then preparation does not invent a list, and new sources still summarise.

### FR6 — Interrupting synthesis still collects pending names and leaves counts honest

- **As an** operator who stops a long run with Ctrl+C, **I want** pending names collected from the source pages already written, and Home’s counts to match the disk after the next site rebuild, **so that** paid work is not thrown away and I do not need a costing command to unstick the dashboard.

- **Acceptance Criteria:**
  - [ ] Given a multi-source synthesis interrupted after some pages have been written, when the command exits, then pending names have been collected from those written pages (or the operator is shown the exact one-line command that collects them), and the wiki’s pending-names folder is not left empty solely because the run did not finish.
  - [ ] Given that interrupted run, when it exits, then sources whose pages were not successfully written are not recorded as finished — a restart synthesizes them.
  - [ ] Given source pages on disk after an interrupt, when the operator rebuilds the site, then Home’s synthesized counts match the pages on disk — they do not stay at zero until someone runs a costing/estimate command.

### FR7 — The separate merge-duplicates command is gone

- **As an** operator (or an agent following project instructions), **I want** duplicate names handled by synthesis seeing the known-names list, **so that** I am not sent through a separate prompt-file / paste-the-reply command.

The old merge-duplicates command disappears from help and from agent skills/commands. Those instructions tell the agent to run synthesis (and review pending names), not to call a leftover consolidate step.

- **Acceptance Criteria:**
  - [ ] Given the product’s command list / help, when the operator looks up how to merge duplicate topic names, then that old command is not offered.
  - [ ] Given someone still types the old command, when they run it, then they see a clear message that synthesis now keeps names unique and that the command is gone — not a prompt file to fill in.
  - [ ] Given the project’s agent skills and slash commands that used to tell the agent to run that merge-duplicates step, when they are followed, then they tell the agent to run synthesis / review pending names instead of a separate consolidate function.

### FR8 — Topic pages get a description from the source pass, and it is not auto-rewritten from later facts

- **As a** reader (and as a reviewer), **I want** a pending or promoted page to open with the short description the source pass already wrote, **so that** the page is readable without another language-model ask.

That opening paragraph is **not** rebuilt when more facts accumulate, and there is no “rewrite descriptions now” command. Reviewers can edit it by hand. Stitched descriptions after merging two pages remain a separate issue.

- **Acceptance Criteria:**
  - [ ] Given sources that recorded a description for a name, when that name becomes a pending page, then the page opens with a description taken from those recordings, with no extra language-model ask.
  - [ ] Given more facts are later added to that page from new sources, when the operator looks at the opening paragraph, then it has not been silently rewritten just because the fact count grew.
  - [ ] Given two pages are merged, when the result is saved, then this change does not add a language-model rewrite of the combined description.

### FR9 — Progress and failure reporting stay understandable

- **As an** operator watching synthesis, **I want** the existing start line, per-page progress, and interrupt message to keep making sense, **so that** the cheaper pipeline does not become a silent one.

- **Acceptance Criteria:**
  - [ ] Given a run of several sources, when it starts, then the operator still sees how many sources will be synthesized, which synthesizer is in use, and how many pages run at once — before the first page result.
  - [ ] Given Ctrl+C, when in-flight pages drain, then the operator still sees how many sources finished and how many in-flight pages were waited on, and then sees that pending names were collected (or the recovery command).
  - [ ] Given a source whose pass fails, when the run continues, then that failure is reported, the source is not marked finished, and other sources still complete.

### FR10 — The change is documented

- **Acceptance Criteria:**
  - [ ] Given the change ships, then `CHANGELOG.md` describes it under `## [Unreleased]`, including that promote no longer needs a language model and that the merge-duplicates command is gone.
  - [ ] Given the CLI reference and getting-started / lifecycle docs, when a reader looks up synthesis, harvest, and promote, then they describe one pass per source and bookkeeping afterwards — not four language-model steps.
  - [ ] Given agent skills and slash commands for synthesis and candidate review, when they are followed, then they match FR4 and FR7.

---

## 3. Scope and Boundaries

### In-Scope

- One amortised language-model job per synthesis run that prepares the known-names list (canonical names, kind, short description) from what is already in the wiki, before any new source is summarised.
- One language-model pass per new source that emits the summary plus, for each named person or idea, kind, the facts this source supports, and a short description.
- One-time rewrite of existing source summaries that lack that shape.
- Collecting pending names and promoting them as bookkeeping over those recordings, including with no language model configured.
- The known-names list is not rebuilt mid-run; a restart (including after Ctrl+C) prepares it again from disk.
- On interrupt: finish in-flight pages, collect pending names from what was written, do not mark unfinished sources done, and make Home counts match disk on the next site rebuild (#145).
- Removing the merge-duplicates command from help and from agent instructions; a clear message if it is still typed.
- Documentation, changelog, and skill/command updates for the above.

### Out-of-Scope

- **Rewriting a topic’s opening paragraph from its fact list, on a fact-count threshold or on demand.** Cancelled in this spec; descriptions come from the source pass and stay until a human edits them.
- **Rebuilding the known-names list in the middle of a run** (waves, or “2 new pending names → refresh”). Convergence is interrupt-and-restart (or the next day’s run), not a mid-run second list-building pass.
- **Stitched descriptions after merge — [#148](https://github.com/AlexanderMakarov/llm-wiki/issues/148).** Merge may still concatenate opening paragraphs; rewriting them into one paragraph is a separate issue.
- **Re-proposing names a reviewer already discarded — [#146](https://github.com/AlexanderMakarov/llm-wiki/issues/146).** This change does not teach harvest to read recorded discard reasons.
- **Order of mixed promote/merge/discard in one review batch — [#149](https://github.com/AlexanderMakarov/llm-wiki/issues/149).**
- **Changing how many pages synthesize at once.** Parallel synthesis stays as it is today.
- **Reintroducing fact bullets clipped from sentences near a name** (the path #103 removed).
- Every other roadmap item — honest `--estimate` (#113), docs-link hygiene (#107), README/CLI map (#109 leftover, #112), `llmwiki doctor` (#110), Cursor session parsing (#2), and Later/deferred items.
