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

## local-review

- Smoke confirmed by operator (migrate applied on live vault; kept stitched, no mark-unsynth)
- Pre-hash ambiguity false positive fixed (`5e565d4` / rebased)
- Review file: `context/spec/324-whole-document-storage/review.md` (session-only, not committed)
- Operator chose keep-all; findings applied (see `## fix (local-review keep-all)`)

## fix (local-review keep-all)

- N1: real usable body budget — `synthesis.<backend>.usable_body_chars` / `context_window_tokens`; order explicit chars → window tokens → backend knowledge (Claude alias table, Ollama `/api/show` `num_ctx` capped by trained context, Cursor none) → 8192-token default; formula `max(1000, (window − scaffolding − 2000 − 2600 − working margin) × 2.05)` with per-class scaffolding/margin (Ollama 500 / max(2048, 10%); Claude lean 890 / max(8192, 25%); Claude non-lean + Cursor 35000 / max(16384, 35%)), no extra cap. Ollama always sends `options.num_ctx`. Sessions / harvest evidence keep the 8000-char send cap via `body_cap`; documents use `synthesize_document_chunk`. Dead `CAPPED_USABLE_BODY_CHARS` / `BODY_CHAR_CAP` / `_BODY_CHAR_CAP` aliases and `add_doc` chunker re-exports removed (N4)
- N5: 512 KiB Markdown cap (`doc_size_error`) enforced in `add_sources` (incl. dry-run), `write_raw_doc` and `_synthesize_one` (legacy raw docs; no backend call)
- B1: migrate validates `project`/`date` as safe path segments and checks `resolve().is_relative_to` the vault roots; unsafe → ambiguous. B2: whole-file existence from the filesystem (`lexists`), unreadable → ambiguous, exclusive create, never overwrite
- N2: migrate reuses `_rewrite_sources_list(..., dedupe=True)` from `migrate_source_page_paths`
- N3: `context/.gitignore` ignores `**/demo-*-review.md`
- Docs: `configuration.md`, `configuration-reference.md`, `reference/synthesis-cost.md`, `reference/cli.md`, `UPGRADING.md`, CHANGELOG #311 entry

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

## implement (slice 4)

- `llmwiki/migrate_whole_document_storage.py` + CLI `_MIGRATIONS` / `cmd_migrate_whole_document_storage`
- Preview lists clear + ambiguous; apply blocked (non-zero, no writes) while ambiguous; recovery under `.llmwiki-whole-doc-recovery/<UTC>/`; offline stitch + tag union; idempotent
- Tests cover preview, ambiguous block, happy path, Wiki findability one row

## implement (slice 5)

- `CHANGELOG.md` `[Unreleased]`; `docs/UPGRADING.md` migrate steps (recovery dir, block-on-ambiguous, no mandatory mass re-synth)
- `docs/reference/cli.md` migrate `whole-document-storage` row + `add` / `synth` notes
- Architecture / ui / mcp notes for one raw file + Wiki findability
- Slice 5 marked `[x]` in `tasks.md`

## implement (post-slice-4 enhancement)

- Optional re-synth queue after migrate apply: lists merged docs; TTY asks once (all-or-nothing, default/EOF/non-TTY keep stitched); `--mark-unsynth` drops whole `docs::` keys + `refresh_synth_pending` without prompting; `--keep-stitched` explicit no-op. No LLM call; apply path unchanged (done state written first)
- `mark_unsynth` / `merged_document_paths` in `migrate_whole_document_storage.py`; `_offer_mark_unsynth` in `cli.py`; docs + CHANGELOG + `_MIGRATIONS` blurb updated

## fix (smoke: pre-hash part groups)

- `_check_raw`: all-empty `content_sha256` is clear; only conflicting non-empty or mixed empty/non-empty stay ambiguous. Whole-file clash compares computed body hashes when either side lacks the field (empty vs empty is not a clash).
- `_whole_raw_text`: fill missing hash via `compute_content_hash` on the joined body. `print_report` adds per-reason **What to do** hints and states clear groups are not applied while blocked.
- UPGRADING / cli / CHANGELOG note pre-hash parts; tests cover apply success + hash conflict still blocks.
