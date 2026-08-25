# Fix log — #161 `synth --estimate` re-derives doc part pages from the body

Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/161

## fetch-bug
Fetched issue #161 (OPEN, label `bug`, no comments). Symptom: `synth --estimate` and `synth` disagree on which document sources are pending, because the estimate rebuilds `<filename>--part-NN.md` paths from the current `_DOC_CHUNK_MAX_CHARS` while the run globs what is on disk. No linked issues; no attachments.

## resume-detection
No prior flow log, branch, or change request for #161. Fresh start.

## workspace
Branch `fix/161-estimate-doc-part-paths`, worktree `.claude/worktrees/fix-161-estimate-doc-part-paths` off `origin/main` @ 07f1462. Throwaway vault at `.worktree-vault` with a worktree-local `config.json`; live vault untouched.

## diagnose
Confirmed both code paths.
- Run: `llmwiki/synth/pipeline.py:1556` builds `targets` via `source_page_paths(...)`, which globs `<filename>--part-*.md` off disk (docstring #24 makes the disk-truth intent explicit).
- Estimate: `llmwiki/synth/estimate.py:456` calls `_chunk_markdown(body, _DOC_CHUNK_MAX_CHARS)` and synthesises the `expected` path list from the chunk count, then tests `all(ep.is_file() for ep in expected)`.
- `_chunk_markdown` / `_DOC_CHUNK_MAX_CHARS` are imported and used at exactly that one site, for two purposes: the `expected` path list (the defect) and `chunk_tokens` cost math (legitimate — a pending doc will be re-chunked at the current size by the next run).
- Second symptom in the same block, not named in the issue: `page_is_stub(ep)` and `page_needs_topics_rewrite(ep)` also iterate `expected`, so a stub or topics-stale page sitting in an on-disk part the current chunk count does not reach is invisible to the estimate's pending check. Sourcing paths from disk repairs this too.

## classify
**Conformance bug — no owning spec.** No `context/spec/*/functional-spec.md` documents how the estimate derives document target pages. Spec 001 (honest `--estimate` candidates) covers Candidates labelling, spec 006 covers Corpus wording, spec 009 covers one-call synthesis; spec 009's "Home counts match pages on disk" criterion is adjacent but is about post-interrupt Home counts, not estimate path derivation. The acceptance criteria that exist are correct — the code violates an implied invariant they never wrote down. No spec amendment; `amend-spec` stage skipped.

Next: fix (delegated), then regression test.

## fix
`llmwiki/synth/estimate.py` only (+3/-5 net in the docs loop of `synthesize_estimate_report`):
- added `source_page_paths` to the function-local `llmwiki.synth.pipeline` import block (kept function-local — the two modules import each other);
- `expected = source_page_paths(out_dir, filename, is_doc=True) or [out_dir / f"{filename}.md"]`, with the `or` fallback keeping a never-synthed doc pending.
`chunks = _chunk_markdown(...)` and the `chunk_tokens` / `ff_cost` / `inc_cost` math are deliberately untouched: a pending doc is re-chunked at the current size by the next run, so cost must still scale with the derived chunk count. Sessions loop untouched. `ruff` clean.

## regression-test
`tests/test_synthesize_estimate.py` (+179), four tests plus a `_expected_doc_pending()` helper that derives ground truth from `source_page_paths` + `page_is_stub` + `page_needs_topics_rewrite` rather than a hand-copied constant:
- `test_estimate_pending_when_disk_has_a_stub_part_beyond_current_chunk_count` — more parts on disk than the current chunker yields;
- `test_estimate_synthesized_when_disk_has_fewer_parts_than_current_chunk_count` — fewer parts on disk than the current chunker yields;
- `test_estimate_doc_cost_scales_with_chunk_count_not_parts_on_disk` — guards the retained `_chunk_markdown` cost math;
- `test_estimate_sessions_never_consult_the_doc_chunker` — sessions unaffected.
RED validated by temporarily restoring the body-derived `expected`: both direction tests failed (`assert 0 == 1`, "doc must be pending — part-03 is still a stub" / "doc is done — 2 real parts cover the whole doc"); the cost and sessions tests are unaffected by the revert, as expected. Fix restored byte-identical afterwards. Full suite: 4129 passed, 48 skipped, 0 failed; `ruff check llmwiki tests scripts` clean.

## verify-criteria
Driven for real through the CLI against the throwaway vault, not only unit tests.

Scenario: a doc whose on-disk page set is wider than the current chunk count reaches — `verifydoc.md` plus `--part-01..03`, where `part-03` is a real page whose Connections carry no parseable `(entity|concept)` kinds, so it needs the #147 topic rewrite, and every page the current 1-chunk derivation reaches is clean.

- Pre-fix `synth --estimate`: `Already synthesized: 1 of 1`, `docs 0 new` — priced no work at all.
- Post-fix `synth --estimate`: `Already synthesized: 0 of 1`, `docs 1 new`.
- Real `synth`: `Scanned 1, new 1, synthesized 1, skipped 0`.
So the pre-fix estimate under-reported against the run, and the post-fix estimate agrees with it.

The repro uses the topics-rewrite pending axis rather than literally changing `_DOC_CHUNK_MAX_CHARS`, because that axis is the one reachable through the CLI: `page_needs_topics_rewrite` is only ever evaluated over the derived target list, while `page_is_stub` is additionally backed by the disk-wide `stub_source_keys` scan that matches on `source_file` frontmatter and so masks the path-list gap for most stubs. Same root cause either way — a page the run's disk-derived list sees and the estimate's body-derived list does not.

Criteria: (1) both paths now derive doc targets from `source_page_paths` — met; (2) both directions covered by RED-validated tests — met; (3) cost math unchanged, guarded by a test — met; (4) sessions untouched — met.

Observed, out of scope, NOT fixed: the estimate treats pages-on-disk as done via `output_exists`, while the run keys its skip on synth state + mtime. A vault with pages but no state entry (hand-written pages, cleared state) makes the two disagree on a different axis, sessions included. That is not #161 and is not addressed here.

Next: smoke confirm with the user, then local review.

## smoke-confirm
Run against the live vault at the user's request, read-only. Pre-fix and post-fix estimates are byte-identical there (`1377 eligible sources`, `docs 231 new / 234 total`, `Incremental sync: $55.1495`), which is the expected result: the divergence needs an on-disk part set that disagrees with today's chunking, and the issue itself notes it is not reproducible from a stock vault. It also confirms the change causes no drift on real data. `llmwiki-state.json` changes on every estimate run — that is by design (`llmwiki/cli.py:1682` persists `synth.estimate` with an `updated_at` stamp for the site's Home/Analytics widgets), not a side effect of this fix.

## local-review
`review.md` in this directory (session-only, never committed — #159). Verdict **Request changes**: 2 Blockers, 4 Nits. Both blockers were Meta/CI rather than code — a missing `CHANGELOG.md` entry (`pr-lint / changelog` greps the diff for `CHANGELOG.md` on `fix:` PRs) and this log still being untracked (`pr-lint / awos-context` only counts paths present in the diff). The fix itself was approved: security, privacy, layer boundaries, dependency rules and the regression-test bar all pass. All four nits were accepted by the user and applied.

Known consequence of this fix, accepted and tracked separately (review N2): a run interrupted between parts leaves real parts and **no stub** for the part it never reached, because a source is recorded in state only once its page is written. The estimate now sees only the parts on disk, finds them all real, and reports the document as synthesized — while the run, having no state entry for that `rel`, re-synthesizes it. The body-derived list happened to be right there, because it asked for a part that was missing. The disk-derived list is still the correct call — it is what the run's own `targets` are, and the run has the identical blind spot once a state entry exists — but the estimate has no state+mtime axis, so disk truth alone cannot separate "complete" from "interrupted". This is the same root cause as the out-of-scope note above (`output_exists` vs the run's state+mtime skip) and belongs to that follow-up, not to #161.

## apply-findings
All four nits accepted by the user and applied.
- **N1** — `expected` now comes from a bare `source_page_paths(...)` with no `or`-fallback, and `output_exists = bool(expected) and not output_is_pending`. Behaviour-identical on every input (empty list → False both ways; non-empty → True both ways), drops three file probes on a path known to be absent, and makes the call site read exactly like the run's. Cost math still untouched.
- **N3** — the two direction tests' docstrings said an earlier `_DOC_CHUNK_MAX_CHARS` produced the on-disk part count, but the tests stub `_chunk_markdown` wholesale and exercise no chunk size. They now say what is actually simulated: the chunker yields N chunks for this body while a different set of pages sits on disk.
- **N4** — the cost test's `_docs_next_usd` helper patches inside `with monkeypatch.context() as m:`, so each measurement patches and unwinds cleanly instead of stacking a second mock on the first.
- **N2** — no code change; recorded above as a known consequence and filed as a follow-up issue.
`ruff check llmwiki tests scripts` clean; `pytest tests/test_synthesize_estimate.py` and the full `pytest tests/` both exit 0.

Follow-up issues filed:
- **#163** — `synth --estimate` calls a source done from pages on disk while `synth` uses state + mtime. The sibling of this bug: #161 settled *which pages a source owns*, #163 is *what makes a source done*, still answered two ways. Carries the interrupted-multi-part-doc case from review N2.
- **#164** — `/fix-bug` scattered per-bug artifacts across the `context/` root instead of a per-fix folder.

## rebase
Rebased onto `origin/main` (7 commits ahead; `main` had moved to 904cac4). None of them touch `llmwiki/`, `tests/`, or `scripts/`, so the green gate above still holds; no conflicts.

`main` had meanwhile adopted the layout #164 asked for (`chore: keep local reviews untracked; nest fix-bug artifacts (#159, #164)`, `chore: review follow-up — fix-as-spec dirs`). This fix's artifacts moved onto that convention: an orphan bug with no owning functional spec gets a fix-as-spec directory `context/spec/{issue}-{short-slug}/`, matching the migrated `context/spec/140-archive-cold-storage/`. So `context/fix-log-161.md` → `context/spec/161-estimate-doc-part-paths/flow-log.md`, and the local review → `review.md` beside it, which `context/.gitignore` keeps out of the commit. No `functional-spec.md` is invented here — the classify verdict stands: conformance bug, nothing to amend.

Next: commit and push, then open the PR.
