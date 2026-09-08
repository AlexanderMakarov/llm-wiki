# Functional Specification: Product principles and maintainer doc clarity

- **Roadmap Item:** Land architectural intentions from the product narrative into evergreen docs (README / PyPI surface, maintainer principles, getting-started for adding documents); relocate brand reference under maintainers; correct font and triage docs. Prompt-driven (no GitHub issue).
- **Status:** Approved
- **Author:** Aleksandr Makarov
- **Approval notes (2026-09-08):** Operator approved with amendments — skip all `/triage-issue` / TRIAGE doc changes (command file stays); leave Google Fonts CDN behavior unchanged; remove specific Python version from the DECLINED qmd-dependency entry; principles ↔ DECLINED alignment accepted.

---

## 1. Overview and Rationale (The "Why")

Someone who finds llmwiki on PyPI or GitHub today gets a competent feature list, but not the *intentions* that shaped the product: cross-tool session memory, documents as first-class input, cheap-to-leave-running, a human gate before entity pages become “facts,” and contradictions kept visible.

A separate draft essay exists outside the repo. It must **not** be committed as-is, and it must **not** carry personal vault metrics into git. The outcome we want is evergreen documentation that carries those intentions, so PyPI readers see “add documents,” maintainers share one principles page linked to the declined-ideas graveyard, and a few stale maintainer claims (fonts, triage slash command) stop misleading people.

Success looks like: the PyPI/README fold mentions adding documents; a short principles page exists under maintainer docs and links to declined ideas; brand guidance lives with other maintainer docs and states fonts honestly; triage docs no longer instruct people to run a retired slash command.

---

## 2. Functional Requirements (The "What")

### R1 — PyPI / README product story

- A visitor reading the project description (same text PyPI shows) understands that llmwiki is for searchable memory across tools and projects, not only “a wiki from documents.”
- That same page elevates adding documents (files, folders, web pages, PDFs) as a first-class capability alongside session sync, with concrete command examples in the main loop section.
- No personal vault statistics appear.
- No full essay is pasted into the README. A blog link may be added later if an external article is published; it is optional and not required for this change.
- **Acceptance Criteria:**
  - [ ] Given the README open in a browser or text view, when a reader scans the opening and “What you get,” then they see both session sync and document add called out.
  - [ ] Given the loop / quick-start command examples, when a reader looks for document intake, then they see examples covering a markdown file, a URL, a PDF, and a folder (or equivalent coverage).
  - [ ] Given a search of the changed docs for personal vault scale numbers from the draft essay, when checked, then none of those personal metrics appear.

### R2 — Maintainer principles page

- Maintainers and contributors can open one principles page that states: cheap-to-run defaults; measure-then-trim for synthesis cost; sessions plus documents; human review before entity/concept promotion; contradictions kept visible; analytics as a product signal without publishing private metrics.
- That page links to the declined-ideas list so “we already rejected X” is one hop away.
- CONTRIBUTING does **not** gain a link to the external article.
- **Acceptance Criteria:**
  - [ ] Given the new principles page, when a reader finishes it, then each intention above is present in plain language without personal vault numbers.
  - [ ] Given that page, when they follow the declined-ideas link, then they land on the existing declined-ideas document.
  - [ ] Given CONTRIBUTING, when searched for the article URL or essay path, then no such link exists.

### R3 — Discoverability from architecture and docs hub

- Architecture and the documentation hub point readers to the principles page.
- **Acceptance Criteria:**
  - [ ] Given the architecture doc and docs hub, when a reader looks for “why we shape the product this way,” then they find a link to principles.

### R4 — Getting started: add a document

- A new user following getting-started can add at least one non-session document and understand it joins the same wiki as sessions.
- **Acceptance Criteria:**
  - [ ] Given getting-started, when a user follows the add-document steps, then they see commands for common source kinds (file / URL / PDF / folder) and where results show up in the vault story.

### R5 — Brand system location and font honesty

- The editorial brand reference lives under maintainer docs (not a separate design folder).
- The typography rules state that Inter and JetBrains Mono are preferred faces with system fallbacks; they are not claimed as preinstalled on all major OSes; the project still avoids bundling font files into the package.
- Tests and in-repo doc links that pointed at the old path are updated.
- **Acceptance Criteria:**
  - [ ] Given a checkout of this change, when searching for the old design-folder brand path as a live link target, then live docs and the brand alignment test point at the new maintainer path.
  - [ ] Given the brand typography rules, when read, then they do not claim first-class OS preinstall for Inter / JetBrains Mono on all three major OSes.

### R6 — Declined-ideas wording: no pinned Python minor version

- The declined entry about shipping qmd as a dependency must not cite a specific Python version floor (that drifts from the real product floor).
- **Acceptance Criteria:**
  - [ ] Given that declined entry, when read, then it argues stdlib-Python / no Node runtime without naming a concrete Python version like 3.9+.

### R7 — Changelog and product context notes

- User-visible doc changes appear under Unreleased with a release-note bullet.
- Product context notes under `context/` are updated enough to satisfy the product-PR rule for maintainer/reference doc changes.
- **Acceptance Criteria:**
  - [ ] Given CHANGELOG Unreleased, when skimmed, then this docs work is listed.
  - [ ] Given the PR’s changed paths, when the product-notes gate applies, then `context/` contains a matching update for this work.

---

## 3. Scope and Boundaries

### In-Scope

- README / PyPI-facing copy updates for problem framing and document add.
- New maintainer principles page with link to declined ideas.
- Links from architecture and docs hub; getting-started add-document section.
- Move brand reference into maintainer docs; fix font claim; update live doc links and brand doc tests.
- Soften DECLINED qmd-dependency reason so it does not pin a Python version number.
- CHANGELOG + required `context/` touch; AWOS flow artifacts for this work.

### Out-of-Scope

- Committing the draft essay or any `docs/essays/` tree.
- Personal vault metrics, paths, or usernames in committed docs.
- Article link in CONTRIBUTING.
- Any TRIAGE / `/triage-issue` / maintainer slash-command inventory changes (skipped by operator decision; command file remains).
- Changing product runtime behavior (build CSS, Google Fonts CDN loading, candidate pipeline, CLI semantics) except documentation and tests that lock doc paths.
- Full demo-vault refresh of every historical raw doc that still cites the old brand path (leave for demo refresh).
