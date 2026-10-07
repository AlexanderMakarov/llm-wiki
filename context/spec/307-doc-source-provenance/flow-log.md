# Flow log — 307-doc-source-provenance

Orphan fix-as-spec for https://github.com/AlexanderMakarov/llm-wiki/issues/307.

## fetch-bug
- BUG_ID: 307
- Title: bug(synth): document source pages have empty provenance and receive session-transcript tags
- Labels: bug, important, self-heal
- Symptom: wiki source pages from document ingest get empty `source_file:` and `session-transcript` despite `raw-doc` inputs under `raw/docs/`.
- Next: resume-detection

## resume-detection
- Issue OPEN; no PR for #307.
- No pre-existing owning functional-spec for this exact behaviour; related: `007-trace-provenance` (requires populated `source_file`), `304-unified-document-pages`.
- SPEC_NAME: `307-doc-source-provenance`
- BRANCH: `fix/307-doc-source-provenance`
- WT: `.claude/worktrees/fix-307-doc-source-provenance`
- Next: workspace

## workspace
- Worktree + throwaway vault created from origin/main.
- TMP_VAULT: worktree `.worktree-vault` (absolute path in worktree `config.json`).
- Next: diagnose

## diagnose
- Reproduced with DummySynthesizer on raw/docs input: empty `source_file:`, tags include `session-transcript` alongside `raw-doc`.
- Root cause 1: docs branch of `synthesize_new_sessions` never injects `source_file` into meta; `_build_source_page` copies blank. Sessions get it from convert frontmatter; `add_doc._frontmatter` writes `source:` not `source_file`.
- Root cause 2: `_derive_baseline_tags` stamps `session-transcript` unless that tag or `claude-code` already present — ignores `raw-doc`/`wiki-add`.
- Fix shape: inject `source_file: raw/docs/<rel>` in docs discovery meta; skip session stamp for documents; update `docs/reference/page-kinds.md` which currently documents the empty field as expected.
- Next: classify

## classify
- Verdict: **conformance** (code violates correct provenance expectation in `007-trace-provenance`; `page-kinds.md` row that describes empty `source_file` is bug-codifying docs, not an AWOS functional-spec to amend).
- No functional-spec amendment; update reference docs + CHANGELOG in the fix PR.
- Next: fix

## fix
- Specialist edited `llmwiki/synth/pipeline.py` (`raw_source_key`, docs meta injection, `is_doc` through `_derive_baseline_tags`), plus `remove_doc.py` prose, `docs/reference/page-kinds.md`, `CHANGELOG.md`.
- Next: regression-test

## regression-test
- Extended `tests/test_synth_pipeline.py`, `tests/test_synth_raw_docs.py`, `tests/cli/test_add.py`, `tests/test_mcp_wiki_add.py` (no new digit-prefixed filenames).
- CLI `add --synthesize` and MCP `wiki_add(synthesize=true)` both covered; revert of fix fails the new assertions.
- Next: verify-criteria

## verify-criteria
- Throwaway vault DummySynthesizer: doc page `source_file: raw/docs/verify307/verify-guide.md`, tags `[wiki-add, raw-doc, verify307]` (no `session-transcript`); session page keeps transcript tag + session provenance. `CRITERIA_OK`.
- `llmwiki lint --rules provenance_integrity` → 0 issues.
- Targeted regression pytest green.
- Live apply (operator-authorized): `migrate doc-source-provenance` filled 252 claims, stripped 252 `session-transcript` tags; second run idle; provenance_integrity 0 issues; sample page claims `raw/docs/scripts/…` without session stamp.
- Next: local-review

## migrate
- Added `llmwiki migrate doc-source-provenance` (package module + CLI + docs + tests) for offline heal of blank doc `source_file` and stale `session-transcript`.
- Next: local-review

## fix
- `llmwiki/synth/pipeline.py`: new `DOCS_REL_PREFIX` + `raw_source_key(rel, is_doc=…)` is the single derivation for the `raw/…` key; the skip/dedup guard's inline expression now calls it, and the docs discovery branch injects the same value as `meta["source_file"]` (only when the raw doc does not declare one — raw/ is never written to, and a re-synth heals a page an older release left blank). Separators are normalised to `/` so the claim matches `remove_doc._source_file_key` on Windows too.
- `_derive_baseline_tags(meta, *, is_doc=False)`: a document gets the `raw-doc` stamp (when neither `raw-doc` nor `wiki-add` is already present) instead of `session-transcript`, which also keeps the never-empty invariant for a frontmatter-less raw doc. `is_doc` is threaded explicitly from `_synthesize_one` → `_build_source_page` → here rather than re-sniffed from tags, so the discovery that knows the corpus is the one that decides. Default `False` keeps every session path and existing caller unchanged.
- Side effect worth noting: `graph._compute_site_url` now takes its `source_file` branch for document pages, so a flat doc under a named project links to `documents/<rel>.html` (verified on disk) instead of the tag-fallback's `documents/<project>/<stem>.html`, which did not exist.
- Carried-over limitation: #351 tag preservation treats existing frontmatter tags as curation, so re-synthesising a pre-fix document page heals `source_file` but keeps its stale `session-transcript`. Recorded in the CHANGELOG entry and the `page-kinds.md` `tags` row rather than fixed by stripping tags.
- Docs: `docs/reference/page-kinds.md` `tags` + `source_file` rows rewritten (they documented the bug as intended); `remove_doc.py` module and `_owned_by` docstrings no longer claim doc pages carry an empty `source_file` (the empty-value allowance stays, for pre-fix pages). `demo/` is a committed point-in-time snapshot of the docs and was left alone.
- Verified on the throwaway vault with `--backend dummy`: doc page claims `raw/docs/field-notes/widget-guide.md` with `tags: [wiki-add, raw-doc, field-notes]`; bare frontmatter-less doc claims `raw/docs/bare.md` with `tags: [raw-doc, docs]`; session page unchanged (`session-transcript, demo, claude`); `lint --rules provenance_integrity` 0 issues; `ruff check` clean; synth/estimate/remove-doc/migrate test modules pass.
- No regression tests written here — next stage (testing-expert).
- Next: test

## migrate
- Closes the carried-over limitation above: new offline `llmwiki migrate doc-source-provenance --vault <vault> [--dry-run]` (`llmwiki/migrate_doc_source_provenance.py`, registered in `cli._MIGRATIONS`).
- Forward derivation only, same as `remove_doc._source_pages_for`: each `raw/docs/` file (via `_discover_raw_docs`, so `_`-prefixed files are skipped like synth) → `synth_page_filename` + `source_page_paths(…, is_doc=True)` → expected claim from `raw_source_key` (or the raw doc's own `source_file`, mirroring synth). Blank claim on a matched page is filled through `migrate_broken_provenance._rewrite_source_file_line` (shared, not re-implemented).
- A page counts as a document by that match, a `raw/docs/` claim, or a `raw-doc` / `wiki-add` tag: `session-transcript` is dropped (inline or block `tags:`) and `raw-doc` is added when no document tag is left. Pages claiming `raw/sessions/` (or any other non-`raw/docs/` root) are skipped. Two raw docs deriving to one blank-claim page → reported ambiguous, page unchanged. Doc-tagged page with no forward match → reported unmatched, claim stays blank, tag still stripped. Stubs included.
- After apply with changes: `refresh_synth_pending` + `migrate | doc source provenance` log entry, like `migrate source-page-paths`. `source-page-paths` "When" text now says to run this first when doc claims are blank.
- Tests: `tests/test_migrate_doc_source_provenance.py` (9 cases); `tests/test_112_acceptance.py` name sets extended. Docs: CHANGELOG #307 entry, `docs/reference/cli.md`, `docs/UPGRADING.md`, `docs/reference/page-kinds.md`.
- Verified on the throwaway vault: seeded a pre-fix doc page (blank claim + `session-transcript`); dry-run wrote nothing, apply filled `raw/docs/smoke307/smoke-guide.md` and dropped the tag, second run printed `nothing to migrate`, raw file hash unchanged, `lint --rules provenance_integrity` 0 issues.
- Next: local-review

## local-review
- Verdict: keep-all. Applied N1 and N2; B1 is sequencing (commit after review), not product code.
- N1: `synth/estimate.py` derives every session and doc key through `raw_source_key` / `DOCS_REL_PREFIX` (added to its existing lazy `synth.pipeline` import, so no new module or cycle). POSIX keys unchanged; Windows separators now normalised like synth's claims. Test: `test_estimate_source_file_keys_match_synth_claims`.
- N2: `provenance_integrity` hints `llmwiki add` / `llmwiki remove` for a missing `raw/docs/` file instead of `migrate broken-provenance` (kept for `raw/sessions/`). Test: `test_provenance_integrity_missing_raw_doc_hints_add_or_remove`; `docs/reference/cli.md` paragraph updated.
- Next: commit

## commit-push
- Staging product fix + migrate + review finding fixes (N1 estimate raw_source_key, N2 provenance hint) + flow prompt fix for empty HEAD review (#307 hit).
- review.md session-only, not staged.
- Next: remote-gates (PR + CI)
