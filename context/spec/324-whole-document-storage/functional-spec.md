# Functional Specification: Whole documents in storage, one summary page, offline migration

- **Roadmap Item:** Store documents whole and chunk only during synthesis, with legacy migration ([GitHub Issue #311](https://github.com/AlexanderMakarov/llm-wiki/issues/311))
- **Status:** Approved
- **Author:** 4ellendger

---

## 1. Overview and Rationale (The "Why")

When someone imports a long document, today’s product often stores it as several files and produces several wiki summary pages (one per piece). That makes one runbook look like many documents in storage, provenance, navigation, and especially keyboard search (Ctrl+K Wiki), even after the site already learned to show one reading page for the raw side ([#305](https://github.com/AlexanderMakarov/llm-wiki/issues/305)).

**Desired outcome.** A newly imported document is stored as one complete original. Summarization may still process it in pieces behind the scenes so no content is silently dropped, but the knowledge layer ends with **one** summary page for that document. Owners of older vaults get a documented migration that turns clear multi-piece sets into that same one-document shape **without** requiring a full AI re-summarization of every legacy document. After migration (or for new work), Ctrl+K Wiki no longer lists many part-rows for the same logical document.

**How we measure success.** Checks confirm: new long imports stay one stored file; synthesis covers the whole text under the active summarizer’s input budget with no silent truncation; one summary page results; duplicate detection still keys off the whole document across old and new layouts; estimates/progress/retries treat internal pieces as one document job and treat mid-document failures as whole-document failures; pre-migration vaults stay usable enough to operate; migration previews, validates, refuses ambiguous groups until resolved, is safe to rerun, preserves recoverable originals under the immutability contract, merges tags by union and prose by offline rules, and leaves Wiki search with one entry (or redirects) per logical document — without mandatory mass re-summarization from raw.

---

## 2. Functional Requirements (The "What")

- **As a vault owner, I want newly imported documents stored as one complete original**, so that storage and provenance match “one document,” not an implementation detail about length.
  - **Acceptance Criteria:**
    - [ ] Given I import a short document, when import finishes, then I have one complete stored original for it.
    - [ ] Given I import a long document (longer than today’s historical split threshold), when import finishes, then I still have **one** complete stored original — not a numbered series of stored pieces.
    - [ ] Given that stored original, when I inspect its identity/provenance, then it refers to this one document as a whole.

- **As a vault owner, I want summarization to respect the chosen summarizer’s usable input size and still cover the whole document**, so that long documents are not silently truncated when different backends accept different amounts of text at once.
  - **Acceptance Criteria:**
    - [ ] Given I have configured a summarizer (backend), when a document is longer than **that summarizer’s** usable input budget (prompt and metadata overhead included), then the product splits the work into as many internal pieces as that budget requires — the split size is **backend-specific**, not a single global “one size for everyone.”
    - [ ] Given that run completes successfully, when I inspect the outcome, then no portion of the document was discarded solely because of that input-size limit (every portion was processed under that backend’s budget).
    - [ ] Given estimates and progress for that run, when I watch them, then they describe **one document job** (internal pieces are not separate documents the owner must track).

- **As a vault owner, I want one canonical wiki summary page per document after summarization**, so that the knowledge layer matches “one document.”
  - **Acceptance Criteria:**
    - [ ] Given a newly summarized document (short or long), when summarization succeeds, then exactly one canonical summary page represents it.
    - [ ] Given that page, when I follow provenance, then it points back to the complete stored original.
    - [ ] Given a long document summarized in internal pieces, when the canonical page is written, then useful structure from the pieces is assembled by **fixed stitching rules** (sections, claims, quotes, connections) — **not** by an extra final AI “polish” pass.
    - [ ] Given Ctrl+K Wiki / site Wiki findability after that summarization, when I search for the document, then I do not see multiple part-style summary rows for that same logical document.

- **As a vault owner, I want a failure during any internal piece of a long-document summarization to be handled as a failure of that whole document**, so that I never get a falsely “done” document or a half-written canonical page.
  - **Acceptance Criteria:**
    - [ ] Given a long document is being summarized in several internal pieces, when any piece fails (backend error, token/limit exhaustion, timeout, or similar), then the **entire document** is treated as not successfully summarized — not “first pieces OK, later pieces missing.”
    - [ ] Given that failure, when I look at status/progress, then I can tell **which document** failed and that the run did not complete for it (internal piece index may be shown for diagnosis, but success is whole-document).
    - [ ] Given no prior canonical summary (or only a pending/stub), when a mid-document failure happens, then I do **not** get a canonical page that looks complete while covering only a prefix of the document.
    - [ ] Given a curated canonical summary already exists, when a mid-document failure happens, then that curated page is **not** overwritten by a stub or by a partial stitch of only the pieces that succeeded.
    - [ ] Given I retry later (same backend or after fixing limits/errors), when the retry completes successfully for that document, then I end with one complete canonical summary under the normal stitch rules.
    - [ ] Given estimates and retries, when a document failed part-way, then it remains in the pending/retry set for that document as a whole (not marked done because early pieces succeeded).

- **As a vault owner with an older split vault, I want basic continuity until I migrate**, so that I am not stuck, while still treating migration as the expected path.
  - **Acceptance Criteria:**
    - [ ] Given a vault that still has multi-piece storage and/or multi-piece summary pages, when I build or search **before** migrating, then the vault remains **usable enough** to operate (browse/build/search do not hard-require migration first).
    - [ ] Perfect parity with the post-migration “one summary row / one identity” experience is **not** required before migration; docs may state that owners are expected to run the migration when they adopt this release’s document model.

- **As a vault owner, I want a documented migration that I can preview and re-run safely**, so that I can move to the one-document representation with confidence.
  - **Acceptance Criteria:**
    - [ ] Given I run migration in preview mode, when it finishes, then I see which groups it would unify, what would be preserved/redirected, and which groups are ambiguous — with **no** vault changes from preview alone.
    - [ ] Given clear, ordered groups, when I apply migration, then each group becomes one canonical stored identity and one canonical summary page (or redirects to it), using **offline** merge rules: **tags are unioned**; **prose is merged by fixed rules** (no AI merge pass in this work).
    - [ ] Given an ambiguous group (unclear membership or order), when I try to apply migration, then migration **refuses to proceed** until I resolve that ambiguity; it does not auto-merge ambiguous groups and does not silently skip them while reporting success for the whole vault.
    - [ ] Given migration runs, when originals need preserving under the immutability contract, then recoverable pre-migration material remains available per the documented recovery strategy.
    - [ ] Given I run migration again after a successful run, when nothing new needs changing, then the second run is a no-op (idempotent) and does not corrupt the canonical pages.
    - [ ] Given migration completes for a document’s clear group, when I use Ctrl+K Wiki / site Wiki findability, then I do not see multiple part-style summary rows for that logical document — one canonical summary (or redirects to it) represents it.
    - [ ] Given links/catalog entries that pointed at old part summary paths, when I follow them after migration, then they resolve to the canonical document summary (and to a section when that mapping is available).

- **As a vault owner, I want duplicate detection to stay document-based across layouts**, so that re-importing the same document does not create a false second identity just because storage shape changed.
  - **Acceptance Criteria:**
    - [ ] Given the same document content, when I compare identity/deduplication before and after the new storage layout (and across a migrated vault), then matches are at the **whole-document** level, not per historical piece.

---

## 3. Scope and Boundaries

### In-Scope

- One complete stored original per newly imported document
- Backend-aware internal splitting for summarization only; full coverage under that backend’s budget; stitch into one canonical summary page (no final AI polish pass for new runs)
- Whole-document success/failure for multi-piece summarization (including backend errors and token/limit exhaustion between pieces)
- Estimates, progress, pending/stub detection, retries, force runs, and synthesis state treating internal pieces as one document job
- Best-effort readability of legacy multi-piece vaults before migration (not a guarantee of full one-document findability until migrate)
- Documented `migrate` path: preview, validation, block on ambiguity, offline tag-union + rule-based prose merge, recovery, idempotence, link/catalog/state updates, Wiki findability without mandatory full re-summarization of raw documents
- Tests and user-facing docs / changelog for the new representation and migration

### Out-of-Scope

- Session transcripts (splitting/storage rules for agent sessions)
- Changing the already-shipped site unified raw document reader behavior from #305 (except insofar as Wiki/search corpus consequences of one summary page are in scope here)
- An AI “final polish” pass for newly summarized long documents
- An AI merge pass during legacy migration (offline rules only in this delivery)
- Mass mandatory re-summarization of every legacy document from raw as the migration success path (operators may still choose a force re-synth later; that remains optional)
- A fully polished long-term dual-layout experience; migration is the supported end state
