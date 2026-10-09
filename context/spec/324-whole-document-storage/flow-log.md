# Flow log — 324-whole-document-storage

Feature delivery for https://github.com/AlexanderMakarov/llm-wiki/issues/311 via `/implement-feature`.

## fetch-ticket

- Issue #311 open; labels: `enhancement`, `self-heal` (no `bug` → `/implement-feature`)
- Related: #305 / PR #312 (site unified documents) already merged; this ticket owns vault storage + synth + migrate

## resume-detection

- No prior `311-*` / `whole-document-storage` spec; starting from `/awos:spec`

## workspace

- Branch: `feat/311-whole-document-storage`
- Worktree: `.claude/worktrees/feat-311-whole-document-storage`
- Throwaway vault: `.worktree-vault` (worktree `config.json`)

## specs (functional)

- `functional-spec.md` approved by operator → written
- Decisions locked: stitch-only for new synth (no final AI polish); migration blocks on ambiguous groups; offline tag-union + rule-based prose merge (no AI merge); backend-specific input budgets; whole-document failure semantics; best-effort pre-migration usability

## specs (tech)

- `technical-considerations.md` approved → written
- Extra gate: demo vault copy migrate + before/after Summary (+ Key Claims) package for operator review
- Locked: migrate name `whole-document-storage`; recovery `.llmwiki-whole-doc-recovery/<UTC>/`; no mid-synth `--part-*` auto-delete

## specs (tasks)

- `tasks.md` written (7 slices; no draft-approval gate under `/implement-feature`)
- Next: commit specs, then `/awos:implement`

## implement (slice 1)

- `write_raw_doc` / `add_sources` dry-run: one complete raw file; no `-NN` / part chrome
- `chunk_markdown_by_sections` kept for synth reuse; hash/dedup still whole-body
- `tests/test_add_doc.py`: long-doc single-file coverage + `write_legacy_multipart_raw_doc` helper
- Verified: ruff + 97 `test_add_doc` tests; TMP vault long add → one raw path; ephemeral vault removed

## implement (slice 2)

- `BaseSynthesizer.usable_body_chars()` + `CAPPED_USABLE_BODY_CHARS` (7000) / `DUMMY_USABLE_BODY_CHARS`
- Claude CLI / Cursor CLI / Ollama override capped; Dummy large; send-time truncate uses budget
- `estimate.py` bills and doc-chunks via same API (`backend=` / `usable_body_chars=`)
- Tests in `test_synth_backends_shared.py` + `test_synthesize_estimate.py`; ruff + targeted pytest green

## implement (slice 3)

- `llmwiki/doc_chunking.py`: shared section chunker moved out of `add_doc` (re-exported there); chunks now strictly ≤ budget; `pipeline._chunk_markdown` delegates to it (estimate uses the same function)
- `llmwiki/synth/stitch.py`: deterministic stitch (Summary concat; Claims/Quotes/other sections exact-dedupe union; Connections union by target; tag union via `_build_source_page(suggested_tags=)`)
- `_synthesize_one`: chunk to `min(backend.usable_body_chars(), doc_chunk_max_chars)`, one page written only after all chunks succeed; any chunk error / usage limit / stop → whole doc fails (no write, no state); `chunks` / `failed_chunk` diagnostics
- `source_pages_for_backlog`: a real canonical page supersedes legacy `--part-NN` siblings for pending checks; synth never deletes parts; `source_page_paths` kept for pre-migrate discovery
- Estimate: one doc job per doc, `unsynth_items[*].chunks`, `new_doc_calls`; `refresh_synth_pending(backend=)`
- Tests: `tests/test_whole_document_synth.py` (new), updated `test_synth_raw_docs`, `test_stub_backlog`, `test_81_acceptance`; fixed `test_mcp_add_cli_proxy` (stale Slice 1 expectation)
