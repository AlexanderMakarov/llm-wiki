# Flow log: 273-mcp-wiki-add-cli-proxy

## fetch-ticket
- Issue #273 open; title: MCP wiki_add: match CLI raw-only bookkeeping and make source provenance explicit
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/273
- No existing PR; no prior matching spec
- Next: resume-detection / workspace

## resume-detection
- Not done; starting from specs
- Next: workspace

## workspace
- BRANCH: `feat/273-mcp-wiki-add-raw-only`
- WT: `/home/USER/code/llm-wiki/.claude/worktrees/feat-273-mcp-wiki-add-raw-only`
- TMP_VAULT: `$WT/.worktree-vault` (throwaway; worktree `config.json` points here)
- Next: specs (`/awos:spec`)

## specs (functional)
- Functional spec approved by operator (chat)
- Path: `context/spec/273-mcp-wiki-add-cli-proxy/functional-spec.md`
- Key decisions vs original issue text: MCP is CLI `add` proxy (default synthesize+build, opt-out params); CLI gains stdin/text with provenance `piped` (no temp as source of record); MCP pipes into CLI; chunking stays in CLI add only
- Next: `/awos:tech` (approval gate)

## specs (tech)
- Operator chose in-process shared `run_add` (not OS subprocess)
- Draft: `context/spec/273-mcp-wiki-add-cli-proxy/technical-considerations.md` (Status: In Review)
- Next: user approve tech → `/awos:tasks`

## specs (amend — default no synthesize)
- Operator: default CLI/MCP `add` = raw write + site rebuild; synthesize opt-in only (`--synthesize` / `synthesize: true`)
- Updated both `functional-spec.md` and `technical-considerations.md`
- `--no-synthesize` proposed as warn+no-op alias for one release
- Next: re-approve functional + tech → `/awos:tasks`

## specs (approved)
- Functional + tech Approved (operator chat)
- `tasks.md` written (5 slices; implement-feature suppresses tasks draft Approve)
- Next: commit-specs → `/awos:implement`

## commit-specs
- Commit `73433d1` on `feat/273-mcp-wiki-add-raw-only`: `docs: add spec for #273 MCP add as CLI proxy`
- Paths: `context/spec/273-mcp-wiki-add-cli-proxy/{functional-spec,technical-considerations,tasks,flow-log}.md`
- Next: `/awos:implement`

## implement
- All slices 1–5 complete (`tasks.md` fully `[x]`)
- Key deliverables: `llmwiki/add_pipeline.py` `run_add`; `convert_text` / piped; CLI+MCP default raw+build / `--synthesize` opt-in; MCP proxy; docs+CHANGELOG; `tests/test_mcp_add_cli_proxy.py`
- Next: verify → user smoke confirm

## local-review
- Smoke confirmed by operator; leftovers removed via `llmwiki remove smoke-273`
- Review written: `context/spec/273-mcp-wiki-add-cli-proxy/review.md` (session-only, not committed)
- Verdict: Request changes — 1 Blocker, 8 Nits
- Next: keep/drop with operator

## local-review keep/drop
- Operator keep: B1 expanded (build docs-or-sessions gate + MCP success on build-only fail + `build_failed` in `run_add`); N1+N5 (`writer` + `messages`); N2 (docs locale encoding, leave stdin as-is); N3 (drop `--no-synthesize` from refresh_demo); N4 (stale one-liners); N6 (`mcp.tool_timeouts` for wiki_add + wiki_sync, default 120); N7 (strengthen weak rglob asserts)
- Operator drop: N8
- Regression: real `build_site` on docs-only vault via MCP `wiki_add`; unit tests for build empty corpora
- Next: verify (ruff + focused pytest) → user smoke / PR refresh

## local-review (keep/drop applied)
- Operator: B1 expand — fix `build_site` docs-or-sessions gate + MCP success when doc landed; N2 docs locale encoding (no UTF-8 force); N6 `mcp.tool_timeouts.*` default 120; keep N1/N3/N4/N5/N7; skip N8
- Review file session-only (not staged)
- Next: commit-push → remote gates

## commit-push
- Pending push of review fixes + prior feat commits
