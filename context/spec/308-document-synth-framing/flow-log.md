# Flow log — 308-document-synth-framing

Orphan fix-as-spec for https://github.com/AlexanderMakarov/llm-wiki/issues/308.

## fetch-bug
- BUG_ID: 308
- Title: bug(synth): document summaries use session framing and alter or invent source claims
- Labels: bug, self-heal
- Symptom: Synthesis treats `raw/docs/` inputs as coding-session transcripts; invents session narrative, weakens modal/logical operators, drops internal contradictions, and attributes unsupported connection facts from wiki topic vocabulary.
- Related: #307 (provenance/tags — separate), #305 (combined-page display — separate)
- Next: resume-detection

## resume-detection
- Issue OPEN; no PR for #308.
- No pre-existing owning functional-spec for document-aware source-page prompting; related specs (`009-one-call-per-source-synth`, `304-unified-document-pages`, `307-doc-source-provenance`) do not own this prompt contract.
- SPEC_NAME: `308-document-synth-framing`
- BRANCH: `fix/308-document-synth-framing`
- WT: `.claude/worktrees/fix-308-document-synth-framing`
- Next: workspace

## workspace
- Worktree + throwaway vault created from origin/main.
- TMP_VAULT: worktree `.worktree-vault` (absolute path in worktree `config.json`).
- Next: diagnose

## diagnose
- Reproduced (read-only): `_load_prompt_template()` always loads `source_page.md`; docs path still gets the same template via `_synthesize_one` / `synthesize_document_chunk`.
- Root cause: `llmwiki/synth/pipeline.py` — no kind-based prompt selection; `prompts/source_page.md` is session-only contract.
- Fix shape: add `document_page.md`; select by `is_doc`; estimate + vault override + tests + CHANGELOG/docs; optional dual PER_PAGE_MARKER; synthetic `tests/fixtures/docs_synth/` for document-focused eval snippets.
- Next: classify

## classify
- Verdict: **orphan / no functional-spec to amend** — no pre-existing AWOS owning spec for document-aware source-page prompting (`009`, `304`, `307` adjacent only).
- Spec amendment: skip. Document via CHANGELOG + synth/prompt reference docs in the fix PR.
- Next: fix

## fix
- Added `llmwiki/synth/prompts/document_page.md` (marker `## Document to synthesize`); `split_prompt_template` accepts both markers (`PER_PAGE_MARKERS`).
- `_load_prompt_template(kind)` with per-kind vault override (`wiki/prompts/document_page.md`); no cross-kind fallback. Vocabulary injected into both; selection by `item["is_doc"]` at submit.
- Multi-chunk docs send `chunk: i of N` in meta (backend call only, not page frontmatter).
- Estimate prices doc chunks with the document template (`doc_template_tokens`); cached-prefix write counted once per template.
- DummySynthesizer left unchanged: "Auto-synthesized from session" is the stub-detection marker.
- Fixtures: `tests/fixtures/docs_synth/` (5 docs + `expectations.json`); tests: `tests/test_document_synth_prompt.py`, split marker in `tests/test_synth_claude_cli.py`.
- Next: regression-test

## fix
- Specialist added `document_page.md`, kind-based `_load_prompt_template`, dual PER_PAGE_MARKERS, estimate pricing, docs/CHANGELOG, fixtures.
- Next: regression-test

## regression-test
- Extended `tests/test_document_synth_prompt.py`: anti-import rule assertion + topic-desc reaches document prompt with anti-import rule; RED-validated.
- Selection + fidelity rule tests already mutation-checked.
- Next: verify-criteria

## verify-criteria
- Touched criteria (issue Expected): document-aware prompt selection for raw/docs; fidelity rules in document_page.md; internal-contradiction contract; fact-from-input / no-desc-as-evidence; synthetic fixtures under tests/fixtures/docs_synth/.
- Evidence: `_load_prompt_template(kind=document)` returns document contract; pytest `tests/test_document_synth_prompt.py` green; ruff green.
- Classification: orphan — skip amend-spec.
- Next: smoke-confirm (user)

## verify-criteria (smoke)
- Operator confirmed LGTM after live re-synth with revised standalone document_page.md (no session-contrast framing).
- Evidence: Summary attributes provenance/status to the document; no "This session…" framing.
- Classification unchanged: orphan — skip amend-spec.
- Next: local-review

## local-review
- Verdict: Approve (0 Blockers, 5 Nits). Path: context/spec/308-document-synth-framing/review.md (session-only, not committed).
- Keep/drop: keep all. N1: delete smoke backups; keep `git add -A` so leftover vault backups would surface. N3: short UPGRADING note (1–2 sentences). N4: unwrap document_page.md prose. N5: estimate Per page shows session/document prompt tokens when docs in scope.
- Next: commit-push

## commit-push
- Issue link keyword: `Closes #308` — delivers document-aware prompt selection, fidelity contract, fixtures, estimate pricing, UPGRADING note; related #307/#305 remain separate.
- Next: remote-gates
