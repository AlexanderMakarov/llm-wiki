# Technical Specification: Whole-document storage + synth stitch + offline migrate

- **Functional Specification:** [functional-spec.md](./functional-spec.md)
- **Status:** Approved
- **Author(s):** 4ellendger

---

## 1. High-Level Technical Approach

Stop persisting length-driven splits. **`add` writes one raw file.** **`synth` chunks only in memory** using the **active backend’s usable body budget**, calls the backend per chunk, **stitches** into **one** wiki source page (deterministic; no final AI polish). Any mid-chunk failure fails the **whole document** (no complete-looking partial page; no overwrite of curated pages).

Legacy vaults stay operable enough (especially #305 site Documents). Perfect one-row Wiki findability comes from a new offline migrate: **`llmwiki migrate whole-document-storage`** — preview always; **apply blocked if any ambiguous group**; tag union + same stitch rules for prose; recoverable relocation of old raw parts; no mass re-synth.

Before treating the offline merge as good enough for ship, run migration on a **copy of the demo vault** and present the operator a before/after summary package for every document that was in pieces.

---

## 2. Proposed Solution & Implementation Plan (The "How")

### Architecture / modules

| Module | Change |
|---|---|
| `llmwiki/add_doc.py` | Stop write-time chunking; one file; keep hash/dedup; keep section splitter for synth reuse (or move to shared helper) |
| `llmwiki/synth/base.py` + backends + `estimate.py` | Shared **usable body budget** API; remove silent `[:8000]` as the coverage path |
| `llmwiki/synth/pipeline.py` | In-memory chunk → stitch → one write; atomic failure; keep legacy `--part-*` discovery helpers until migrate clears them |
| `llmwiki/migrate_whole_document_storage.py` (**new**) + `cli.py` `_MIGRATIONS` | Preview/apply/idempotent migrate |
| `remove_doc.py`, existing doc migrates, `raw_docs_site.py`, Wiki corpus | Compat with whole + legacy; post-migrate one corpus row |
| Docs | `UPGRADING.md`, `cli.md`, `CHANGELOG.md` |

### Identity contracts

- **New raw:** `raw/docs/<project>/<slug>.md` (full body; no part chrome)
- **Wiki canonical:** one `wiki/sources/…/<date>-<slug>.md`; **no new `--part-NN` writes**
- **`content_sha256`:** whole-document (already true today across parts)
- **State:** `docs::<rel>`; one key per new doc; migrate collapses part keys → whole-file key
- **`source_file`:** points at canonical whole raw path after migrate / new synth

### Synth algorithm

1. `usable_body_chars()` per backend (Claude/Cursor/Ollama ≈ 8k minus prompt/meta overhead; Dummy = large)
2. Section-aware chunk to that budget
3. Call backend per chunk **in memory**
4. **Stitch:** Summary concat; Claims/Quotes exact-dedupe union; Connections union by target; tags via existing curation + union of suggestions
5. **Atomicity:** only after **all** chunks succeed → write one page under lock; on any failure → no canonical write, state not done, curated untouched; diagnostics may show chunk index
6. On successful new synth, **do not** auto-delete legacy `--part-*` siblings — leave cleanup to migrate

### Migration algorithm

- **Name:** `whole-document-storage`
- **Group** by `#305` `base_slug_from_stem` + agreeing `content_sha256` + wiki `source_page_paths` / `--part-*`
- **Ambiguous** (gap, hash conflict, `foo.md`+`foo-01.md` clash, inconsistent wiki claims) → **list in preview; apply exits non-zero and changes nothing**
- **Raw:** write whole file if missing; relocate old `-NN` under `.llmwiki-whole-doc-recovery/<UTC>/…` (recoverable; never silent clobber of a different-hash whole file)
- **Wiki:** same stitch as synth + tag union; stubs/redirects from old part paths; rewrite links/index/state; `refresh_synth_pending`
- **No LLM**

### Locked assumptions

1. Migration subcommand name: `whole-document-storage`
2. Recovery dir: `.llmwiki-whole-doc-recovery/<UTC>/` under the vault
3. Leave legacy `--part-*` cleanup to migrate (no mid-synth auto-delete)
4. Stitch: exact-string claim dedupe, no AI
5. Demo-copy migrate + full before/after summary package for operator review (all multi-piece demo docs)
6. Review package content: wiki source **Summary** section, plus **Key Claims** when present (not full raw bodies)

---

## 3. Impact and Risk Analysis

### System Dependencies

- add → synth → estimate → migrate → build / Wiki corpus
- #305 site Documents / `raw_docs_site` grouping mostly unchanged; Wiki Ctrl+K corpus improves after migrate / new synth

### Potential Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Silent truncation if budget not wired | Tests: body ≫ 8k on capped-backend mocks; assert N calls and full coverage |
| Partial canonical on failure | Inject fail on chunk 2; assert no complete page; state pending; curated preserved |
| Ambiguous auto-merge | Apply blocked; tests for hash conflict / gap / clash |
| Raw data loss | Recovery dir + dry-run; never overwrite different-hash whole file |
| Weak offline stitch quality | **Operator gate:** demo vault copy before/after Summary (+ Key Claims) review |
| Orphan state keys | Assert part keys gone; whole key present after migrate |
| Estimate vs run disagreement | Shared chunk + budget |

---

## 4. Testing Strategy

### Automated

- Long add → one raw file; hash dedupe old↔new
- Long synth on capped backend mocks → N calls, one wiki page, full coverage
- Fail on chunk 2 → no complete page, pending, curated preserved
- Estimate matches N calls / one doc job
- Migrate: preview; blocked ambiguous; happy path + recovery + idempotent re-run; Wiki corpus one row
- Sessions never chunked; #305 acceptance still green

### Operator gate — demo migration quality review

Required before smoke-confirm / local review:

1. Copy shipped `demo/` to a throwaway directory (never mutate committed demo in place).
2. Identify every logical document that was stored in pieces.
3. Capture **before** wiki Summary (+ Key Claims when present) for each part/page of those documents.
4. Run `llmwiki migrate whole-document-storage` (preview, then apply) on the copy.
5. Capture **after** canonical Summary (+ Key Claims when present).
6. Present a review package to the operator (chat and/or session-only `demo-migrate-review.md` under the spec dir).
7. **Stop** until the operator accepts merge quality (or requests stitch-rule tweaks). Automated tests alone are not enough for this gate.
