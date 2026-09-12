# Tasks: Search command and findability checks (#197)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Work only in this worktree. Mutating `llmwiki` commands target `$TMP_VAULT` (worktree `config.json` / `.worktree-vault`). Never write `raw/`, `wiki/`, or `site/` under the operator live vault. Drive the package as `python3 -m llmwiki` from the worktree root.

The MCP refactor gate: leave the existing `wiki_search` suite green **with no edits to those tests** — a test that needs changing means behaviour moved.

---

- [x] **Slice 1: Extract `llmwiki/search/` and rewire MCP (byte-identical + deterministic ties)**

  > End state: MCP `wiki_search` (`match` / `extract`) calls `scan_corpus` + multi-query engine; equal scores order by `(-score, rel_path)`; existing MCP tests pass unchanged.

  - [x] Add `llmwiki/search/` package: `corpus.py` (`ScannedPage`, `CorpusScan`, `scan_corpus`), `scoring.py` (`ExtractQuery`, `score_extract`, `match_page`), `engine.py` (`search_extract` / `search_match` multi-query single-pass), `evaluate.py` stub or `rank_of` as needed by later slices, `__init__.py` public surface. No import-time state. Lift behaviour from `mcp/server.py` per technical-considerations §2.1–2.2. **[Agent: general-purpose]**
  - [x] Thin `_wiki_search_extract` / `_wiki_search_match` in `llmwiki/mcp/server.py` to scan → engine → render. Preserve `REPO_ROOT` seam, `_hits`, `truncated` / `budget_exhausted` / `skipped_oversize_files`, and rendered output shapes. Apply `(-score, rel_path)` extract tiebreak. **[Agent: general-purpose]**
  - [x] Unit/integration tests for the new package only: scoring arithmetic (hand-computed), multi-query isolation (N-together == each solo, including saturation + reduced caps), extract tiebreak / shuffled iteration order, reducer/engine `rank_of` agreement when `rank_of` lands. Do **not** edit existing MCP tests. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/test_mcp_enhanced.py tests/test_mcp_byte_cap.py tests/ -q -k 'search or mcp' --maxfail=20` then full `python3 -m pytest tests/ -q`; `ruff check llmwiki tests scripts`. Delete any ephemeral verify artifacts. **[Agent: general-purpose]**

- [x] **Slice 2: `llmwiki search` CLI**

  > End state: `llmwiki search` supports term/phrase, single + `--terms-file` / stdin bulk, `--vault`, `--include-raw`, `--kind`, `--max-pages`, `--format text|json`; always exit 0 on successful search; `cmd_query` untouched.

  - [x] Register `search` in `llmwiki/cli.py` per §2.3; reuse shared `--vault` / `_content_root`; wire to `llmwiki.search`. Bulk output groups per entry and states which returned nothing. **[Agent: general-purpose]**
  - [x] Integration tests: both modes, bulk file + stdin, `--vault` temp vault, `--format json`, non-vault path clear error, vault unchanged after run. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/ -q -k search`; `python3 -m llmwiki search --help`; `ruff check llmwiki tests scripts`. **[Agent: general-purpose]**

- [x] **Slice 3: Three lint rules + shared `SearchContext`**

  > End state: `page_findability` (error), `title_ambiguity` (warning), `search_consistency` (error) registered; `LintOptions` gains `content_root`, `search_context`, `findability_sample_max`; rules skip when options absent; sampling deterministic.

  - [x] Extend `LintOptions` and wire `content_root` / lazy `SearchContext` from `run_lint` / CLI lint path. Implement `SearchContext` (one `scan_corpus` per lint run). **[Agent: general-purpose]**
  - [x] Implement the three rules in `llmwiki/lint/rules/` per §2.4 (sample ≤300 evenly over sorted paths; `search_consistency` prints both term groups; survival share informational). Reuse `evaluate` / scoring — not lint's `pages` dict. **[Agent: general-purpose]**
  - [x] Tests: purpose-built temp vaults for each rule; skip when options absent; sampling/term-selection determinism (run twice). **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/ -q -k 'lint or findability or ambiguity or consistency'`; `ruff check llmwiki tests scripts`. **[Agent: general-purpose]**

- [x] **Slice 4: Demo planted terms/phrases + fixtures + acceptance gate**

  > End state: generator emits `tests/fixtures/demo_search_terms.json` (present/absent, term|phrase); maintainer baseline `demo_search_baseline.json` (four numbers + `_doc`); `tests/test_197_acceptance.py` reads-only and asserts exactly; demo corpus updated if generator re-run is required.

  - [x] Add `tool` turn role + static planted term/phrase table + fixture emission in `scripts/generate_demo_sessions.py` per §2.5–2.6. Invented plausible words that pass privacy grep. Regenerate or patch demo artifacts so fixtures match committed demo. **[Agent: general-purpose]**
  - [x] Commit `tests/fixtures/demo_search_terms.json` and `tests/fixtures/demo_search_baseline.json` (measure MRR/rank1 on demo after search package works; round MRR to 6dp). **[Agent: general-purpose]**
  - [x] Write `tests/test_197_acceptance.py` per §2.7: present/absent both modes, every titled demo page findable, exact MRR/rank1 vs baseline; report survival × placement × adapter without asserting it. Must leave working tree clean. **[Agent: general-purpose]**
  - [x] Verify: `python3 -m pytest tests/test_197_acceptance.py tests/ -q`; `git diff --exit-code` after tests; privacy test green; `ruff check llmwiki tests scripts`. **[Agent: general-purpose]**

- [x] **Slice 5: Docs, CHANGELOG, reference rows**

  > End state: user docs for `search` + three lint rules; `docs/benchmarks.md` findability section; maintainer rationale; CHANGELOG Unreleased; CLI/lint reference rows for CI coverage.

  - [x] Update user docs (`docs/reference/cli.md`, lint reference, tutorials as needed), `docs/benchmarks.md`, maintainer docs (DECLINED reading / metric rejection), `CHANGELOG.md`. No user-facing history narrative. **[Agent: general-purpose]**
  - [x] Verify: CLI/lint doc coverage greps that CI uses still pass; `ruff check` N/A for md; spot-check links. **[Agent: general-purpose]**

- [x] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.

  - [x] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 197-search-quality-eval` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [x] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
