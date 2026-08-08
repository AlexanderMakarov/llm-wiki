# Tasks: Trace wiki pages back to raw transcripts (#122)

- **Functional Spec:** [`functional-spec.md`](functional-spec.md)
- **Technical Spec:** [`technical-considerations.md`](technical-considerations.md)

Every slice leaves the package importable and the throwaway vault buildable. Run `ruff check llmwiki tests scripts` and `python3 -m pytest tests/ -q` before considering any slice done.

**Vault rule for every task:** mutating `llmwiki` commands target the worktree's throwaway vault only — `python3 -m llmwiki … --vault "$PWD/.worktree-vault"` from the worktree root. Never write `raw/`, `wiki/`, or `site/` under the operator's live vault. Always invoke `python3 -m llmwiki`, never PATH `llmwiki`.

---

- [ ] **Slice 1: Shared provenance walker**

  > Library core for FR1/FR3/FR4 — no CLI surface yet; unit-testable.
  - [ ] Add `llmwiki/trace.py` with `trace_page(vault, locator) -> TraceResult` (ordered hops: `role`, `title`, `location`, `status` ok|missing, optional `site_href`). Resolve path-or-name locators under `vault/wiki`. Walk `sources:` via existing candidates helpers (promote/export if needed) then each source’s `source_file:` to a vault-relative raw path. Mark missing hops; never invent body excerpts. Reject path traversal outside the vault. **[Agent: general-purpose]**
  - [ ] Write `tests/test_trace.py` covering full chain, missing source slug, missing raw file, page with no provenance, unresolvable start page, and traversal rejection. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_trace.py -q` and `ruff check llmwiki/trace.py tests/test_trace.py` green. Delete scratch files. **[Agent: general-purpose]**

- [ ] **Slice 2: CLI `llmwiki trace`**

  > FR1 operator/script surface.
  - [ ] Register `trace` in `llmwiki/cli.py` (`cmd_trace`, `--vault`, page arg). Print human-readable chain (titles, locations, missing markers); exit non-zero only when the starting page cannot be resolved. **[Agent: general-purpose]**
  - [ ] Add `## trace` to `docs/reference/cli.md` (reference-coverage CI). Add a focused CLI test using a tmp vault. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m llmwiki trace …` against the throwaway or tmp vault matches walker output; `pytest` for the new CLI test + `ruff` green. **[Agent: general-purpose]**

- [ ] **Slice 3: Lint `provenance_integrity` (errors)**

  > FR5 — report only; heal is #110.
  - [ ] Add `llmwiki/lint/rules/provenance_integrity.py` (`severity = "error"`), register in `rules/__init__.py`. Emit one issue per broken hop (missing source page or missing raw). Skip pages without provenance metadata. Issue/docs text may mention doctor (#110) for guided repair. **[Agent: general-purpose]**
  - [ ] Update lint registry tests (count/names) and add rule-focused cases in `tests/test_lint_rules.py` or a dedicated test module. List the rule under Rules in `docs/reference/cli.md`. **[Agent: general-purpose]**
  - [ ] Verify: rule fires on a broken fixture and stays silent on a clean one; registry tests + `ruff` green. **[Agent: general-purpose]**

- [ ] **Slice 4: Site Sources links (topics + sessions/documents)**

  > FR2 — prefer HTML; else raw marked “(raw)” `target="_blank"` `rel="noopener"`.
  - [ ] On topic pages (`topics_page.py`), render every Sources entry from the backing wiki page as an `<a>`: prefer built session/document (or other) HTML via walker/`site_href`; else link to the raw (or `site/sources/…` copy) with a visible “(raw)” mark and new-tab attributes. Omit any empty Sources block when there is nothing to show. **[Agent: general-purpose]**
  - [ ] On session (`build.py` `render_session`) and document renderers, apply the same Sources / wiki-summary linking rules without inventing `entities/*.html` URLs. **[Agent: general-purpose]**
  - [ ] HTML/unit tests asserting prefer-HTML vs raw+`target="_blank"` behaviour. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m llmwiki build --vault "$PWD/.worktree-vault"` (seed a fixture chain if needed) and assert the relevant HTML substrings; pytest + ruff green; delete scratch. **[Agent: general-purpose]**

- [ ] **Slice 5: Docs, CHANGELOG, and context notes**

  > CONTRIBUTING user-visible + product-path requirements.
  - [ ] Update `CHANGELOG.md` `[Unreleased]`, `docs/UPGRADING.md` (new lint errors; CLI `trace`; no new MCP tool; doctor #110 for heal), and any other touched `docs/reference/*`. Add a brief note under `context/` (spec flow-log and/or product note) about provenance + doctor handoff. **[Agent: general-purpose]**
  - [ ] Verify: reference-coverage still green; skim links to #110/#122 are accurate; ruff/pytest unaffected. **[Agent: general-purpose]**

- [ ] **Slice 6: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.
  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: [spec-directory]` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
