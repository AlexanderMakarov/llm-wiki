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
- Pending: commit `context/spec/273-mcp-wiki-add-cli-proxy/` on `feat/273-mcp-wiki-add-raw-only`
