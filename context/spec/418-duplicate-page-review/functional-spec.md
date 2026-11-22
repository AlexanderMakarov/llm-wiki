# Functional Specification: Review possible duplicate curated pages in one batch

- **Roadmap Item:** [#365](https://github.com/AlexanderMakarov/llm-wiki/issues/365) — Review possible duplicate curated pages in one batch (merge or keep distinct)
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

Reviewed wiki pages sometimes exist twice for the same subject under different names (short vs long tool name, spelling variants, singular vs plural). Sessions and links split across the two pages, so search, topic views, and query answers only see half the story on each page. Automatic folding is wrong about half the time, so a human must decide.

**Desired outcome:** One place — the same Candidates review surface already used for stubs — lists every suspected duplicate pair. The reviewer decides all pairs in one batch: merge one page into the other, or mark them as distinct so the suspicion does not return.

**Success:** After a review pass and a site rebuild, true duplicates become one page with combined evidence; false positives stay as two pages and do not reappear on the list; no extra language-model call is introduced for this feature.

---

## 2. Functional Requirements (The "What")

### 2.1 Detect and show suspected pairs

- **As a** wiki reviewer, **I want to** see every pair of already-published pages the system suspects are the same subject, **so that** I do not have to hunt for splits by hand.
  - **Acceptance Criteria:**
    - [ ] Given two live curated pages whose names the vocabulary treats as the same topic (or folds onto one shared topic), when I open the Candidates page or run the candidates list command, then a “Possible duplicate pages” section lists that pair with both titles, kinds, links to both pages, session counts, and any short description the vocabulary already has.
    - [ ] Given no such pairs, when I open that section or list, then it is empty or absent — not an error.
    - [ ] Detection does not require a new language-model call beyond whatever synthesis already does for known-names consolidation.

### 2.2 Decide in one batch

- **As a** wiki reviewer, **I want to** choose per pair — merge first into second, merge second into first, keep distinct, or leave undecided — and apply all choices with one action, **so that** I can clear the backlog the same way I clear candidate stubs.
  - **Acceptance Criteria:**
    - [ ] Given several listed pairs, when I set a decision on each and run the single batch-apply command shown on the page, then every decided pair is processed and undecided pairs remain listed.
    - [ ] The Candidates page shows the one command to run after choices are made (same pattern as today’s candidate apply).

### 2.3 Merge one live page into another

- **As a** wiki reviewer, **I want to** merge page A into page B, **so that** evidence, links, and aliases live on one survivor.
  - **Acceptance Criteria:**
    - [ ] Given I choose merge A into B, when apply finishes and I rebuild the site, then B shows the combined sources and connections, A’s distinctive prose appears under a dated section on B, A’s name is listed among B’s aliases, links that pointed at A now point at B (display text preserved where it differed), A is no longer a live page, and the duplicate list no longer offers that pair.
    - [ ] Given A and B have different kinds (for example concept vs project), when I merge A into B, then the merge is allowed and B keeps B’s kind.
    - [ ] Merge does not call a language model.

### 2.4 Keep distinct (durable)

- **As a** wiki reviewer, **I want to** mark two pages as different subjects, **so that** they never reappear as a suspected pair and the vocabulary stops folding their names together.
  - **Acceptance Criteria:**
    - [ ] Given I choose keep distinct for a pair, when I run synthesis again later (including after a vocabulary refresh), then that pair does not reappear on the duplicate list.
    - [ ] Given keep distinct was recorded, when later consolidation runs, then those two curated names are not folded onto each other.

### 2.5 Curated titles stay fixed at consolidation time

- **As a** wiki reviewer, **I want** already-reviewed page titles treated as fixed names during the existing known-names consolidation, **so that** the system stops proposing folds between two curated pages before I have to dismiss them.
  - **Acceptance Criteria:**
    - [ ] Given two live curated pages, when known-names consolidation runs (the existing single call), then it does not fold one curated title onto the other as if they were spelling variants of one topic — unless a prior merge already settled that name onto a survivor.
    - [ ] This behavior uses the existing consolidation call only; it does not add a second language-model call.

### 2.6 Agent kit, doctor, and lint awareness

- **As an** operator or agent following the candidate-review workflow, **I want** pending duplicate pairs mentioned wherever candidate review is already mentioned, **so that** I do not miss them.
  - **Acceptance Criteria:**
    - [ ] The agent-kit candidates command/docs mention checking possible duplicate pages alongside stub review.
    - [ ] Doctor and lint surface a clear finding when one or more duplicate pairs are pending review (count and how to open the list).

---

## 3. Scope and Boundaries

### In-Scope

- Detecting suspected pairs from existing vocabulary / page data (no new LLM call)
- Candidates site section + CLI list + batch apply for merge / keep distinct / undecided
- Live-page merge (including different kinds; survivor keeps its kind)
- Durable keep-distinct that survives cache refresh
- Feeding curated titles as fixed into the **existing** consolidation path
- Agent-kit `/wiki-candidates`, doctor, and lint mentions of pending pairs
- Docs / changelog as needed for a user-visible change

### Out-of-Scope

- Any **additional** language-model call dedicated to duplicate detection or merge
- Automatic unsupervised merging of curated pages
- Merging two entire vaults (`/wiki-merge`)
- Redesigning candidate stub harvest itself
- Undoing keep-distinct via a dedicated UI in this ticket (ledger/archive repair remains the escape hatch if ever needed)
- Changing search ranking or MCP query algorithms beyond the effect of merged/aliased pages
