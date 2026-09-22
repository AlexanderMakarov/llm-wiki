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

## verify
- `ruff check llmwiki tests scripts` — pass
- `python3 -m pytest tests/ -q` — exit 0 (~full suite)
- Live smoke (operator-requested): merged primary non-`vault` config into worktree `config.json`, then `add -` against live vault
  - `--no-build`: raw `source: "piped"`, no `/tmp` leak, exit 0
  - default build: site rebuilt, `wiki/sources` count unchanged (815), zero smoke-273 source pages, state mentions `smoke-273` pending
  - worktree `config.json` restored to throwaway vault after smoke
  - leftover raw docs under live `raw/docs/smoke-273/` (operator may remove)
- Next: user confirm smoke OK → local review
