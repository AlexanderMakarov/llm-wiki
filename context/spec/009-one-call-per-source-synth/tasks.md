# Tasks: One synthesis pass per source (#147 / #145)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Every slice leaves `llmwiki` runnable. Slices are ordered so parsers and offline harvest/promote land before the two LLM jobs and before interrupt behaviour changes.

**Standing constraints:** stdlib only — no new runtime dependencies. Imports at module top. Public functions carry a docstring. No real session data, no absolute home paths, no vault roots in code, tests, or docs — use `/home/USER/…`, `<vault>` placeholders.

**Vault rules:** `python3 -m llmwiki` from the worktree only. Mutating commands target `<worktree>/.worktree-vault` or a `tmp_path` — never the operator's live vault.

---

- [x] **Slice 1: Source topic bullets are parseable without a model**

  > Parser + rewrite detector. Nothing user-visible yet; harvest still classifies. Pins the job-2 contract before any consumer moves.
  - [x] Add `llmwiki/source_topics.py` with `TopicRecord` (`name`, `kind: str | None`, `description`, `facts: list[str]`), `parse_source_topics(body: str) -> list[TopicRecord]`, and `source_page_needs_topics_rewrite(body: str) -> bool`. Parse `- [[Name]] (entity|concept) — description` plus nested `- fact:` lines. Invalid kind → `kind=None`. `source_page_needs_topics_rewrite` is true when harvestable `[[wikilinks]]` exist but no record has a usable kind. Docstrings state the contract. Import nothing from harvest/pipeline (leaf module). **[Agent: general-purpose]**
  - [x] Add `tests/test_source_topics.py` covering: happy path (entity + concept, two facts); missing kind → rewrite needed; kind present → rewrite not needed; invalid kind; description-only; facts-only; Connections heading with old `- [[Name]] — how` bullets (rewrite needed); empty body. **[Agent: general-purpose]**
  - [x] Verify: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_source_topics.py -q`. Delete any scratch files. **[Agent: general-purpose]**

- [x] **Slice 2: Harvest copies kind, facts, and description — no classifier**

  > FR3. `--candidates-only` works with Dummy / no backend. Candidate `## Connections` stays the evidence list.
  - [x] In `llmwiki/candidates_harvest.py`, stop calling `classify_names` on the default `run_harvest` path. Kind from `parse_source_topics` across citing sources (majority; tie → first sorted slug; existing stub folder wins). Key Facts = concatenated `fact` lines each suffixed `[[source-slug]]`. Description = first non-empty bullet description in sorted slug order, as the paragraph between H1 and `## Key Facts`. Preserve `_preserved_body` (do not overwrite prose above `## Connections`). `backend=` may remain on the signature and must be ignored for classification. Harvest returns success when `backend is None`. Remove fail-closed refuse-when-backend-unreachable. **[Agent: general-purpose]**
  - [x] Update `tests/test_candidates_harvest.py` (and any classifier-specific tests): Dummy/None backend still writes stubs; kind/facts/description match fixture source bullets; spy that `synthesize_source_page` is not called for classification; existing stub folder is not re-filed. **[Agent: general-purpose]**
  - [x] Verify: seed a `tmp_path` vault with two source pages naming the same `[[Foo]]` with parseable bullets, run harvest with Dummy, assert the stub. `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_candidates_harvest.py tests/test_source_topics.py -q`. Delete the scratch vault. **[Agent: general-purpose]**

- [x] **Slice 3: Promote is a move and works with no model**

  > FR4. Review no longer depends on `key_facts.md`.
  - [x] In `llmwiki/candidates.py` `promote` (and flip-promote / site caller): if Key Facts empty, fill from `parse_source_topics` on `sources:` pages; if still empty, leave empty. Never call `synthesize_key_facts`, never raise `KeyFactsBackendError` from promote, never use mention-clip helpers on this path. Keep `rewrite_key_facts` as the opt-in CLI that still requires a backend. **[Agent: general-purpose]**
  - [x] Update `tests/test_candidates.py` and site-API tests that expect `KeyFactsBackendError` on promote: Dummy/None promote succeeds; non-empty reviewer Key Facts preserved; empty facts filled from source bullets; mention-clip helpers not invoked. **[Agent: general-purpose]**
  - [x] Verify: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_candidates.py tests/test_candidates_harvest.py -q`. **[Agent: general-purpose]**

- [x] **Slice 4: Job 1 prepares known-names once; consolidate-topics CLI is retired**

  > FR5 + FR7. `synth` prepares the list before any source; the old command prints a retirement message.
  - [x] Extend `llmwiki/synth/prompts/topic_consolidation.md` (or the renderer in `topics_consolidate.py`) so the reply includes `kind` (`entity` | `concept`) per canonical topic. `prepare_known_names(wiki_dir, backend)` in pipeline or `topics_consolidate.py`: skip when Dummy / `not is_llm` / no topics; on success `parse_and_cache`; on failure warn and fall back to heuristic `_inject_vocabulary`. Call it once in `synthesize_new_sessions` before the executor, only when job 2 will run. Vocab prefix remains byte-identical for every page of the run. **[Agent: general-purpose]**
  - [x] Retire `cmd_consolidate_topics`: keep the subparser name; print that synthesis now prepares names and the command is gone; exit 2; `--complete` must not write the cache. Update `tests/e2e/test_cli_smoke.py` accordingly. **[Agent: general-purpose]**
  - [x] Tests: Dummy run does not call an extra `synthesize_source_page` for job 1; a fake `is_llm` backend is invoked **once** before workers; injected `{vocabulary}` is identical for two sources in one run; `consolidate-topics` exits 2 with the retirement message. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m llmwiki consolidate-topics --vault <scratch>` exits 2; Dummy `synth --sources-only` still synthesizes. `ruff check llmwiki tests scripts` and the new/updated tests `-q`. Delete scratch. **[Agent: general-purpose]**

- [x] **Slice 5: Job 2 emits kind/facts/description; old source pages are rewritten once**

  > FR1 + FR2. Dummy fixtures must emit the new bullet shape so harvest in later slices stays honest.
  - [x] Update `llmwiki/synth/prompts/source_page.md` Connections example to the `- [[Name]] (entity) — description` / `- fact:` shape. Update `DummySynthesizer` / `base.py` fallback body to match so tests and `--sources-only` Dummy runs produce parseable bullets. **[Agent: general-purpose]**
  - [x] In skip logic of `synthesize_new_sessions`, treat `source_page_needs_topics_rewrite` on the existing/claimed page as not-skip; write over that path. After the new shape is present and mtime is current, skip. **[Agent: general-purpose]**
  - [x] Tests: Dummy output parses with `parse_source_topics`; a Connections-only existing page is queued despite current state mtime; a page with parseable kinds is skipped. **[Agent: general-purpose]**
  - [x] Verify: scratch vault with one old-shape source page + matching raw; Dummy synth rewrites it; second run skips. `ruff check` + targeted pytest. Delete scratch. **[Agent: general-purpose]**

- [x] **Slice 6: Interrupt harvests; Home counts recover on build**

  > FR6 / #145. Ctrl+C then restart is how job 1 sees new names.
  - [x] KeyboardInterrupt in the drain: `_record_abandoned_pages` only when `written` files exist; `refresh_synth_pending`; gated index rebuild; `summary["interrupted"]=True`; **return** (do not re-raise). CLI: harvest unless `--sources-only` (print `llmwiki synth --candidates-only` then); exit 130. **[Agent: general-purpose]**
  - [x] `pipeline_on_disk_mismatch` + `_ensure_synth_pipeline_snapshot` refreshes when stored `on_disk` disagrees with source-page file count. **[Agent: general-purpose]**
  - [x] Update `tests/test_synth_parallel.py` (and acceptance) for the new interrupt contract. Build/state tests: snapshot `on_disk: 0` with files on disk → refresh; matching counts → skip. CLI interrupt contract in `tests/test_synth_run_summary.py`. **[Agent: general-purpose]**
  - [x] Verify: `ruff check llmwiki tests scripts` and `python3 -m pytest tests/test_synth_parallel.py tests/test_state_widget.py tests/test_81_acceptance.py tests/test_synth_run_summary.py -q` (or the modules actually updated). **[Agent: general-purpose]**

- [x] **Slice 7: Docs, changelog, agent kit**

  > FR10. Lands after behaviour is final.
  - [x] `CHANGELOG.md` under `## [Unreleased]`: two LLM jobs per run; harvest/promote offline; `consolidate-topics` retired; interrupt harvest; Home counts on build. Reference `#147` and `#145`. **[Agent: general-purpose]**
  - [x] Update `docs/reference/cli.md`, `docs/reference/synthesis-cost.md`, `docs/UPGRADING.md` (next synth rewrites pages lacking parseable topic bullets; custom `wiki/prompts/source_page.md` must match), README, `llmwiki/agent_kit/commands/wiki-synth.md` and `wiki-candidates.md`. Do not edit `demo/raw/`. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/test_reference_coverage.py tests/test_docs_structure.py tests/e2e/test_cli_smoke.py -q` plus `ruff check llmwiki tests scripts`. **[Agent: general-purpose]**

- [x] **Slice 8: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 009-one-call-per-source-synth` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**

---

## Recommendations

| Task/Slice | Issue | Recommendation |
| --- | --- | --- |
| Slices 1–7 (implementation) | Assigned to `general-purpose` — no Python CLI specialist is registered (`hired-agents.md`) | Not blocking: contributing rules load on `llmwiki/` / `tests/` / `docs/`. Hire a Python specialist later if desired. |
| Slice 8 (QA) | Project-local `testing-expert` is assigned | No action. |
| All Verify tasks | CLI + pytest only; no browser MCP required | No action. |
