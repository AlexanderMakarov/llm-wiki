# Functional Specification: Complete documents on one site page

- **Roadmap Item:** Show complete documents on the static site regardless of on-disk chunking ([GitHub Issue #305](https://github.com/AlexanderMakarov/llm-wiki/issues/305))
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

People who import long documents into their knowledge base often end up with those documents split into several pieces for technical reasons. On the browsable site today, each piece looks like its own document: the Documents list shows generated file names (sometimes opaque identifiers), and opening any entry shows only that piece — not the full document. Keyboard search (Ctrl+K) and the Documents sidebar also disagree about titles and how many entries a multi-part document should have.

That breaks the reading experience the site is meant to provide. A person who wants to read or search an imported document should meet **one** document with a readable title and its full text, whether the vault happens to store it as one file or many parts. Folder browsing (project folders and per-document folders that already exist on disk) must keep working for vaults that use it — without maintaining a second, divergent catalog of “what a document is.”

**Desired outcome.** Opening a document anywhere on the site — Documents navigation, search, or an old link to a part — lands on one canonical reading page that shows the complete document. The Documents sidebar lists one titled entry per logical document (still nested under folders when the vault has them) and can be filtered quickly from the **same document catalog** Ctrl+K uses. Search treats chunks as parts of that same document, not as separate documents.

**How we measure success.** Manual checks on a vault that includes both a single-file document and a multi-part document confirm: full text on one page; one sidebar entry with a readable title; filter by prefix then substring with a clear empty state; search opens the unified page (optionally at a section); old part links still reach the right place; folder nesting still appears when present; the site works when opened as local files (`file://`); and no vault source or wiki pages are rewritten to achieve this.

---

## 2. Functional Requirements (The "What")

- **As a reader, I want each imported document to open as one complete reading page**, so that I can read the whole document without jumping between part pages.
  - **Acceptance Criteria:**
    - [ ] Given a document stored as a single file, when I open it from Documents navigation or search, then I see its complete content on one page.
    - [ ] Given a document stored as multiple ordered parts, when I open it from Documents navigation or search, then I see every part’s content on that same page, in the correct order, with nothing missing.
    - [ ] Given that unified reading page, when I look at the body, then I can jump to sections via in-page anchors, and repeated generated part titles and part breadcrumbs are not shown as separate document chrome.
    - [ ] Given unrelated documents that happen to sit next to each other in storage (including different documents under the same project folder), when the site is built, then they are not combined into one reading page.

- **As a reader, I want the Documents sidebar to list one entry per logical document under a readable title, still nested in folders when the vault has them**, so that I can find documents without decoding storage filenames and without losing project/folder browsing.
  - **Acceptance Criteria:**
    - [ ] Given several multi-part documents and several single-file documents, when I open the Documents view, then each logical document appears exactly once (not once per part).
    - [ ] Given a sidebar entry, when I read its label, then I see the document’s readable title rather than a generated or UUID-like storage filename.
    - [ ] Given I select a sidebar entry, when the page opens, then it is that document’s unified reading page.
    - [ ] Given documents that live under folders (for example a project folder, or one folder per document), when I use the Documents sidebar, then that folder nesting is still available — we do not remove folder browsing for vaults that already use it.
    - [ ] Given the Documents sidebar appears on Raw, Home (when it shows documents), or an individual document page, when I use it, then the same logical-document rules and titles apply.

- **As a reader, I want to filter the Documents sidebar by what I type, with the most relevant titles first**, so that I can narrow a long list quickly.
  - **Acceptance Criteria:**
    - [ ] Given the Documents sidebar, when I look at it, then there is a quick filter input.
    - [ ] Given I type text into the filter, when matching runs (case-insensitive), then a title matches if it **starts with** my text or **contains** my text anywhere in the title.
    - [ ] Given both kinds of matches exist, when the filtered list is shown, then **all starts-with matches appear first**, and **contains-only matches appear after them** (ordering among document entries; folder nesting still wraps those entries as below).
    - [ ] Given a match that lives under one or more parent folders (including deep nesting), when the filter is applied, then **every ancestor folder of that match stays visible** in the sidebar so the document’s place in the grouping is clear — non-matching sibling documents (and branches with no matches) are hidden.
    - [ ] Given a visible matching document title, when the filter is non-empty, then the matching substring is **highlighted** in the document name (case-insensitive match to what I typed).
    - [ ] Given my filter matches nothing, when the list updates, then I see the empty-result copy **No documents match**.

- **As a reader, I want the Documents quick filter and Ctrl+K search to share one document catalog**, so that titles and “one document vs many parts” never diverge between the two surfaces.
  - **Acceptance Criteria:**
    - [ ] Given the same vault build, when I compare document titles in the Documents sidebar (including after filtering) with document hits from Ctrl+K, then readable titles and which items count as one logical document agree.
    - [ ] Given I use the Documents quick filter, when matching runs, then it uses that shared document catalog (the same catalog Ctrl+K uses for documents), not a second independent title list.
    - [ ] Given folder nesting is shown in the sidebar, when titles and links are shown, then they come from the same logical-document identity as Ctrl+K — any nested tree view is only a layout of that shared catalog, not a rival definition of documents.
    - [ ] Kind / type filter chips for sessions, topics, entities, concepts, or candidates are **not** required in this change (typed filters that already exist in Ctrl+K may remain as they are).

- **As a reader using search, I want document hits to open the unified document page**, so that search never presents document parts as separate documents.
  - **Acceptance Criteria:**
    - [ ] Given search finds text that lives in a multi-part document, when I open that result, then I land on the unified document page (not a standalone part page presented as its own document).
    - [ ] Given the match falls in a later section, when I open the result, then I may land at the matching section anchor on that unified page.
    - [ ] Given a multi-part document, when I search for its title or content, then I do not see duplicate document entries — one per chunk — for that same logical document.

- **As a reader with old bookmarks or links, I want links to individual parts to still work**, so that existing references keep landing in the right place.
  - **Acceptance Criteria:**
    - [ ] Given an existing link that pointed at an individual raw part page, when I open it after this change, then I still reach the corresponding unified document (and the relevant section when that part maps to one).

- **As a reader who opens the site as local files, I want this behavior to work without a web server**, so that the usual offline browse path keeps working.
  - **Acceptance Criteria:**
    - [ ] Given the built site is opened via `file://`, when I use Documents navigation, filter, search, and part links as above, then the same unified-document behavior holds.

- **As a vault owner, I want this improvement without rewriting my sources or wiki**, so that a site rebuild alone is enough.
  - **Acceptance Criteria:**
    - [ ] Given a vault with existing raw documents and wiki pages, when the site is rebuilt with this feature, then raw files, wiki source pages, and synthesis state are not rewritten to provide these improvements.

---

## 3. Scope and Boundaries

### In-Scope

- One canonical reading page per logical document on the static site, assembling multi-part content in order when needed
- Documents sidebar: one entry per logical document, readable titles, folder nesting preserved when present, quick filter with starts-with-then-contains ordering, ancestor folders kept for matches, substring highlight in titles, and empty state **No documents match**
- One shared document catalog for Ctrl+K and the Documents quick filter (same logical documents and titles); nested Documents tree is only a layout view of that catalog when kept
- Search results that open the unified document (optional section anchor) without treating chunks as separate documents
- Compatibility of existing part-page links with the unified reading experience
- Behavior under `file://` browsing
- Verification covering both single-file and multi-part representations, including unrelated documents that share a project folder

### Out-of-Scope

- Changing how documents are stored on disk, ingestion chunking, synthesis input budgets, synthesis output layout, or vault migration — those belong to [#311](https://github.com/AlexanderMakarov/llm-wiki/issues/311)
- Rewriting raw files, wiki pages, or synthesis state as part of this work
- New Ctrl+K kind/type filter chips (sessions, documents, topics, entities, concepts, candidates) — follow-up; existing typed query syntax may stay unchanged
- Removing folder browsing / project-folder support from the Documents sidebar
- Other roadmap items not named in issue #305
