# Functional Specification: Findability by page title

- **Roadmap Item:** [#259](https://github.com/AlexanderMakarov/llm-wiki/issues/259) — findability is by page title; stop treating raw link text / file names as the findability test
- **Status:** Approved
- **Author:** Aleksandr Makarov

---

## 1. Overview and Rationale (The "Why")

Operators and agents need a clear rule for “can I find this page?” Today the quality check sometimes fails because someone linked a page by its **file name**, and the checker then searched for that file name as if it were a natural question — even when the page already has a good human title in the page’s metadata.

**Problem:** File names are for the filesystem and for making links resolve. They are not how people or agents should judge whether a page is findable. The **title** on the page (matching the language and wording of the content) is the findability key.

**Desired outcome:** Searching and the findability quality check ask “does this page’s **title** find the page?” File-name-only link text is not a findability failure. A separate, **offline** upgrade can rewrite existing bare file-name links so readers see the title while the link still points at the same file — with **no paid language-model use**.

**Success:** Vaults stop getting spurious “cannot find page” quality errors for file-name links; real title problems still surface; docs state title vs file-name roles clearly.

---

## 2. Functional Requirements (The "What")

1. **Findability quality check uses the page title**
   When checking whether a wiki page is findable, the product searches using that page’s **title** (from its page metadata). If a good title cannot find the page (missing from results or ranked too far down the result list), that remains a real finding — do not weaken or hide it.
   - **Acceptance Criteria:**
     - [ ] Given a page whose title, when searched, does not return that page in the allowed result window, the findability check still reports a problem.
     - [ ] Given a page that is only linked elsewhere by file name (not by title text), the findability check does **not** report a problem solely because searching that file-name string failed.

2. **Stop searching raw link text for findability**
   Whether a `[[…]]` link resolves to a real page stays a separate “broken link” concern. Findability must not ask “if I search the exact characters inside the brackets, do I get the target?” when those characters are just the file name.
   - **Acceptance Criteria:**
     - [ ] Given a hub page that lists many sources as file-name links that resolve correctly, running the findability check does not emit errors of the form “wikilink '<file-name>' did not return resolved target … results cut short”.

3. **Documented contract for operators and agents**
   Product docs state: title = findability key; file name / slug = filesystem and link-resolution metainfo; preferred visible link shows the title while still pointing at the file.
   - **Acceptance Criteria:**
     - [ ] A reader of the findability / search docs can answer “do we judge findability by title or by file name?” without reading source code.

4. **Offline migration for existing bare file-name links**
   Provide a migration operators can run that walks the wiki and, where a link is only the target’s file name, rewrites it so the **visible** text is that target’s title while the link still resolves to the same page. Uses only titles already stored on disk — **zero language-model tokens**.
   - **Acceptance Criteria:**
     - [ ] Running the migration does not call a language-model backend.
     - [ ] After migration, a sample bare file-name link becomes a link whose visible text is the target page’s title (or is left unchanged with a clear report when no title is available).
     - [ ] The migration is listed with other vault migrations and mentioned in the upgrade notes.

---

## 3. Scope and Boundaries

### In-Scope

- Findability check behavior (title-based; no raw file-name-as-query findability failures)
- Docs for title vs file-name / slug roles
- Offline migration + upgrade notes for existing bare file-name links

### Out-of-Scope

- Changing how broken / unresolved links are reported (separate integrity check)
- Softening or removing title-not-found / ranked-too-low findability errors
- Requiring language-model re-synthesis to fix titles (job 2 remains the place good titles are written; this work does not pay for rewrites)
- Browser site search palette and ranking algorithm overhauls
- Other roadmap items
