# Tasks: MCP tool surface consolidation (#196)

Spec: [`functional-spec.md`](./functional-spec.md) · [`technical-considerations.md`](./technical-considerations.md)

Mutating MCP tests use the worktree throwaway vault (`$TMP_VAULT`). Read-only telemetry probes may use `demo/usage/` or operator vault. Never write to the operator's live vault.

---

- [ ] **Slice 1: Telemetry maps retired tool names to the six canonical names**

  > End state: `aggregate()` folds `wiki_query` + `wiki_search` into one `per_tool["wiki_search"]` row; Analytics subtext says `search · read`.

  - [ ] Add `CANONICAL_TOOL_ALIASES` and `canonical_tool_name()` to `llmwiki/usage.py`. Update `aggregate()`, `day_buckets_from_records()`, `page_retrievals()`, `value_summary()` helpers (`is_entity_tool`, `is_retrieval_tool`) and `ENTITY_TOOLS` / `RETRIEVAL_TOOLS` to use canonical names. Remap `by_tool` in `_normalize_day_bucket` when loading folded daily data. **[Agent: general-purpose]**
  - [ ] Update `llmwiki/viz_wiki_value.py` retrieval subtext to `search · read`. **[Agent: general-purpose]**
  - [ ] Tests in `tests/test_mcp_usage.py`: retired names aggregate into canonical buckets; zero-hit and items_returned sum correctly. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_mcp_usage.py -q`; `ruff check llmwiki/usage.py llmwiki/viz_wiki_value.py tests/test_mcp_usage.py`. **[Agent: general-purpose]**

- [ ] **Slice 2: `wiki_health` replaces `wiki_lint` and `wiki_dashboard`**

  > End state: MCP exposes `wiki_health` with lint JSON + `totals`; `wiki_lint` and `wiki_dashboard` are unknown tools.

  - [ ] Rename tool schema and handler to `wiki_health` in `llmwiki/mcp/server.py`. Add `totals` (`wiki_pages`, `sources`, `pending_candidates`) to the JSON payload. Delete dashboard tool schema/handler. **[Agent: general-purpose]**
  - [ ] Update `tests/test_mcp_lint_parity.py`, `tests/test_v02.py`, `tests/test_archive_cold_storage.py` for `wiki_health`. **[Agent: general-purpose]**
  - [ ] Verify: parity test `tool_wiki_health({})` matches `lint --json` keys + `totals`; `handle_tools_call` for `wiki_lint` errors. **[Agent: general-purpose]**

- [ ] **Slice 3: Unified `wiki_search` absorbs five discovery tools**

  > End state: `wiki_search` supports `mode` match | extract | filter; retired search-family tools error on call.

  - [ ] Expand `wiki_search` schema with `mode`, `question`, `filter_by`, confidence/lifecycle/tag params, `project`. Implement dispatch in `tool_wiki_search` calling existing private implementations. Remove five tool entries from `TOOLS` / `TOOL_IMPLS`. **[Agent: general-purpose]**
  - [ ] Update `tests/test_mcp_enhanced.py`, `tests/test_archive_cold_storage.py`, `tests/test_v02.py`, `tests/test_page_kinds.py` for unified search. Add mode coverage: extract, filter confidence/lifecycle/tag, match+project for sources. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/test_mcp_enhanced.py tests/test_archive_cold_storage.py -q`; `len(TOOLS)==6`. **[Agent: general-purpose]**

- [ ] **Slice 4: Protocol, telemetry evidence, and docs**

  > End state: `docs/reference/mcp.md` exists; UPGRADING/CHANGELOG updated; PR records before/after payload size; issue has telemetry table.

  - [ ] Pull `llmwiki usage --json` from `demo/` or available vault; post summary to PR body. Measure after-state `len(json.dumps(TOOLS))`. **[Agent: general-purpose]**
  - [ ] Add `docs/reference/mcp.md`; update `docs/UPGRADING.md`, `CHANGELOG.md`, `docs/reference/ui.md`, `docs/reference/cli.md`, `llmwiki/exporters.py`, `llmwiki/mcp/__init__.py`, `server.py` module docstring. Fix `tests/test_mcp_protocol.py` (6 tools). **[Agent: general-purpose]**
  - [ ] Update `scripts/generate_demo_usage.py` canonical tool names if it seeds retired names for demo Analytics. **[Agent: general-purpose]**
  - [ ] Verify: `python3 -m pytest tests/ -q`; `ruff check llmwiki tests scripts`; grep docs for stale "12 tool" / "7 tool" MCP claims. **[Agent: general-purpose]**

- [ ] **Slice 5: Feature testing & regression**

  - [ ] Full test suite green; record final tool count (6) and serialized schema char count in PR body (baseline 12 / 7597). **[Agent: general-purpose]**
