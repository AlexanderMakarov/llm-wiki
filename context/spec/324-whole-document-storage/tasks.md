# Tasks: Whole-document storage + synth stitch + offline migrate

- **Spec:** [`functional-spec.md`](functional-spec.md) · [`technical-considerations.md`](technical-considerations.md) — both Approved
- **Issue:** [#311](https://github.com/AlexanderMakarov/llm-wiki/issues/311)

**Standing constraints for every task.** Work only in the worktree `.claude/worktrees/feat-311-whole-document-storage` on branch `feat/311-whole-document-storage`. Vault-mutating commands target `$TMP_VAULT` (`.worktree-vault`) or an explicit scratch copy under the worktree; never the operator's live vault. Always drive `python3 -m llmwiki` from the worktree, never PATH `llmwiki`. Gates before any slice is called done: `ruff check llmwiki tests scripts` (or ruff on touched files) and targeted `pytest`. No new runtime deps. Session transcripts are out of scope. Pre-migration dual-layout polish is best-effort only.

---

- [x] **Slice 1: One raw file per new import (stop write-time chunking)**

  > Long `add` writes a single complete raw Markdown file; hash/dedup stay whole-document.
  - [x] Change `write_raw_doc` / add path in `llmwiki/add_doc.py` so new imports always write one file (no `-NN` series, no part titles/breadcrumbs). Keep `compute_content_hash` / `find_existing_by_hash` whole-body semantics. Keep or relocate section splitter for later synth reuse. **[Agent: generalPurpose]**
  - [x] Update `tests/test_add_doc.py` (and related) for single-file long docs; keep a fixture or note for legacy multi-file layout used by later migrate tests. **[Agent: generalPurpose]**
  - [x] Verify: targeted pytest green; add a long fixture doc into `$TMP_VAULT` and confirm one raw path; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 2: Backend usable-body budget API (no silent truncate as coverage)**

  > Shared budget so pipeline/estimate know how much body each backend can take.
  - [x] Add `usable_body_chars` (or equivalent) on `BaseSynthesizer`; implement for Claude CLI / Cursor CLI / Ollama (≈8k minus prompt/meta overhead) and Dummy (large). Wire `estimate.py` to the same API; stop treating bare `BODY_CHAR_CAP` / `[:8000]` as the only coverage path. **[Agent: generalPurpose]**
  - [x] Unit tests: budget returns finite positive values for capped backends; Dummy large enough for multi-section fixtures. **[Agent: generalPurpose]**
  - [x] Verify: targeted pytest green; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 3: Synth in-memory chunk + stitch → one wiki source page + atomic failure**

  > One document job; N backend calls; one canonical page; mid-chunk failure fails the whole doc.
  - [x] In `llmwiki/synth/pipeline.py`: for docs, chunk in memory to backend budget; call backend per chunk; stitch (Summary concat; Claims/Quotes exact-dedupe union; Connections union by target; tag curation + union); write **one** wiki page only after all chunks succeed. On any chunk failure: no complete-looking canonical write; state not done; do not overwrite curated pages. Do not auto-delete legacy `--part-*`. Keep legacy discovery helpers for pre-migrate vaults. **[Agent: generalPurpose]**
  - [x] Update estimate/pending/done predicates and progress so internal chunks are one document job. **[Agent: generalPurpose]**
  - [x] Tests: long doc on capped mock → N calls, one page, full coverage; fail on chunk 2 → pending, no complete page, curated preserved; sessions still single-call. Update `test_synth_raw_docs.py` / estimate / stub backlog as needed. **[Agent: generalPurpose]**
  - [x] Verify: targeted pytest green; optional synth on `$TMP_VAULT` with Dummy; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 4: Offline migrate `whole-document-storage`**

  > Preview; block apply on ambiguous groups; merge raw + wiki offline; recovery dir; idempotent.
  - [x] Implement `llmwiki/migrate_whole_document_storage.py` + register in `cli.py` `_MIGRATIONS`. Group via #305 base-slug + agreeing hash + wiki part paths; ambiguous → report; apply exits non-zero with no vault changes. Raw: write whole file; relocate `-NN` to `.llmwiki-whole-doc-recovery/<UTC>/…`. Wiki: same stitch + tag union; stubs/redirects; rewrite links/index/state; `refresh_synth_pending`. No LLM. **[Agent: generalPurpose]**
  - [x] Tests: preview lists groups; apply blocked on ambiguous; happy-path merge + recovery + idempotent re-run; Wiki corpus / findability one row per logical doc after migrate. **[Agent: generalPurpose]**
  - [x] Verify: targeted pytest green; migrate dry-run on a scratch multi-part vault; delete ephemeral artifacts. **[Agent: generalPurpose]**

- [x] **Slice 5: Docs + CHANGELOG + UPGRADING**

  > Operators know the new representation and how to migrate.
  - [x] Update `CHANGELOG.md` `[Unreleased]`, `docs/UPGRADING.md`, `docs/reference/cli.md` (migrate row), and any architecture/ui notes needed for Wiki findability / whole-doc storage. No personal vault paths. **[Agent: generalPurpose]**
  - [x] Verify: docs mention one raw file, backend-budget synth, migrate name, recovery dir, block-on-ambiguous, no mandatory mass re-synth. **[Agent: generalPurpose]**

- [ ] **Slice 6: Demo vault copy — before/after summary review package (operator gate)**

  > Operator reviews stitch quality on real multi-piece demo docs before smoke/local review.
  - [x] Copy shipped `demo/` to a throwaway dir under the worktree. Identify all multi-piece logical docs. Capture before Summary (+ Key Claims when present) per part. Run migrate preview then apply. Capture after canonical Summary (+ Key Claims). Write session-only review package `context/spec/324-whole-document-storage/demo-migrate-review.md` (do not commit if treated as review dump — follow `context/.gitignore` / operator preference). Present package to operator and **stop until they accept**. **[Agent: generalPurpose]**
  - [ ] If operator requests stitch-rule tweaks, apply them, re-run the demo-copy migrate review, and re-present. **[Agent: generalPurpose]**

- [ ] **Slice 7: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 324-whole-document-storage` and `@regression` if suitable for long-term regression. Prefer a stable slug filename (no GitHub issue digits in new test module names). **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
