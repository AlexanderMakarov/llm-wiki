# Tasks: MCP Add as CLI Add Proxy (#273)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Work from the feature worktree. Mutating `llmwiki` commands use `$TMP_VAULT` (worktree `.worktree-vault` / worktree `config.json`). Never write the operator live vault. Drive `python3 -m llmwiki` from the worktree root.

---

- [ ] **Slice 1: Piped / text conversion with `source: "piped"` provenance**

  > End state: CLI and library can convert in-memory/stdin text into raw docs whose frontmatter `source` is `piped` (never a `/tmp/…` path); long text still chunks via existing `add_doc` logic.

  - [ ] Add `convert_text` (or equivalent) and wire source sentinel `-` / text input into `add_sources` so path/URL provenance stays unchanged and text uses `source_label="piped"`. Reject mixing `-` with other sources in one batch. **[Agent: generalPurpose]**
  - [ ] Tests in `tests/test_add_doc.py`: piped provenance; multi-chunk long body shares piped `source`; path/URL labels unchanged. **[Agent: generalPurpose]**
  - [ ] Verify: `python3 -m pytest tests/test_add_doc.py -q`; `ruff check llmwiki/add_doc.py tests/test_add_doc.py`; delete any ephemeral fixtures under `/tmp` created only for the check. **[Agent: generalPurpose]**

- [ ] **Slice 2: Shared `run_add` orchestration + CLI default flip (raw + build, synth opt-in)**

  > End state: `_cmd_add_locked` delegates to a shared callable; bare `llmwiki add` writes raw, rebuilds site, does **not** synthesize; `--synthesize` opts in; `--no-synthesize` warn+no-op; `--no-build` still skips build; stdin `add -` works.

  - [ ] Extract lock-body orchestration into shared `run_add` / `add_pipeline` (module per tech spec). Invert defaults: synthesize off unless `--synthesize`; keep build on unless `--no-build`; `--no-synthesize` warn+no-op alias. Wire `add -` to stdin → text conversion. Update argparse help. **[Agent: generalPurpose]**
  - [ ] Update `tests/test_cli.py` (and related) for new defaults, `--synthesize`, stdin `-`, `--no-synthesize` warning. **[Agent: generalPurpose]**
  - [ ] Verify: against `$TMP_VAULT`, run add without `--synthesize` and confirm raw + site touch / no new `wiki/sources` for that doc; with `--synthesize` (dummy backend) confirm source page; `python3 -m pytest tests/test_cli.py -q`; `ruff check llmwiki/cli.py llmwiki/add_doc.py tests/test_cli.py`. **[Agent: generalPurpose]**

- [ ] **Slice 3: MCP `wiki_add` as thin proxy onto shared `run_add`**

  > End state: MCP default = raw + build; `synthesize` / `no_build` params; `content` uses piped path (no tempfile); tool description documents proxy + guardrail.

  - [ ] Rework `tool_wiki_add` to call shared orchestration; add `synthesize` / `no_build`; remove tempfile content path; update TOOLS schema/description. **[Agent: generalPurpose]**
  - [ ] Update `tests/test_mcp_wiki_add.py` for defaults, opt-in synth, `no_build`, piped provenance, parity with CLI text add. **[Agent: generalPurpose]**
  - [ ] Verify: `python3 -m pytest tests/test_mcp_wiki_add.py tests/test_cli.py -q`; `ruff check llmwiki/mcp tests/test_mcp_wiki_add.py`. **[Agent: generalPurpose]**

- [ ] **Slice 4: Docs, agent kit, CHANGELOG**

  > End state: CLI/MCP reference, ingest skill, and CHANGELOG describe new defaults, stdin/`piped`, and source-layer guardrail.

  - [ ] Update `docs/reference/cli.md`, `docs/reference/mcp.md`, `llmwiki/agent_kit/skills/llmwiki-ingest/SKILL.md`, `llmwiki/agent_kit/commands/wiki-ingest.md` as needed, and `CHANGELOG.md` (behavior change: default add no longer synthesizes). **[Agent: generalPurpose]**
  - [ ] Verify: spot-check docs mention `--synthesize` / default raw+build; `ruff` N/A for md; ensure CI doc-coverage expectations for new flags/params are satisfied if the repo greps them. **[Agent: generalPurpose]**

- [ ] **Slice 5: Feature Testing & Regression**

  > Verifies the whole feature end-to-end against functional-spec.md, run after all implementation slices are complete.

  - [ ] Read functional-spec.md acceptance criteria in full. Generate acceptance-level tests that verify the entire feature as a whole — not individual slices. Cover applicable layers (unit for pure logic, integration for service interactions, e2e for user flows) based on the project's testing stack. Write tests with RED validation (must fail before implementation is confirmed done). Annotate each test with `@spec: 273-mcp-wiki-add-cli-proxy` and `@regression` if suitable for long-term regression. **[Agent: testing-expert]**
  - [ ] Run all generated tests. All must pass. Fix any failures before proceeding. **[Agent: testing-expert]**
