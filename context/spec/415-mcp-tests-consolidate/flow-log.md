# Flow log: 415-mcp-tests-consolidate (#316)

## fetch-ticket
- Issue: https://github.com/AlexanderMakarov/llm-wiki/issues/316 — test: consolidate MCP tests under tests/mcp/
- Labels: enhancement, minor, self-heal
- Open; no existing PR

## resume-detection
- No prior 316/415 spec artifacts; start from workspace

## workspace
- BRANCH=`feat/316-mcp-tests-consolidate`
- WT=`<repo>/.claude/worktrees/feat-316-mcp-tests-consolidate`
- MAIN=`<repo>`
- TMP_VAULT=`$WT/.worktree-vault`

## specs
- functional-spec.md: Approved (user chose option 1)
- technical-considerations.md: Approved (user chose option 1)
- tasks.md: drafted (informational; no draft Approve ask under /implement-feature)
- SPEC_NAME=`415-mcp-tests-consolidate`
- Next: commit-specs

## commit-specs
- Commit `1e4c9ed` — docs: add spec for #316 consolidate MCP tests under tests/mcp/
- Next: implement

## implement
- All tasks.md items `[x]` (Slices 1–4)
- Next: verify

## verify
- Functional + technical Status → Completed; ACs checked with layout/gates/suite/cov/contract evidence
- Next: local-review (smoke confirm first)

## local-review
- Smoke: pytest tests/mcp/ + test_quality_gates + ruff green; no flat test_mcp_*.py (user asked agent to run)
- Review file: context/spec/415-mcp-tests-consolidate/review.md
- Verdict: Approve; Blockers 0; Nits 2
- keep/drop: keep N1 (delete flat-file gate); N2 → remove ticket-only `tests/mcp/__init__.py` and stop requiring it in the MCP layout gate (not “stage the init”)
- Applied: deleted `test_no_flat_test_mcp_files_at_tests_root`; removed `__init__.py`; MCP gate is dir + `test_*.py` only
- Static gate: ruff clean; full `pytest tests/` exit 0
- Next: commit-push

## commit-push
- Issue link keyword: `Closes #316` — issue owns only the MCP unit-test mirror pass; adapters/synth/mutation are other tickets
- Staging: implementation + docs + AWOS notes; exclude `review.md` / vault / config
- Last committed flow-log state before PR open

## implement
- Moved 10 MCP modules into `tests/mcp/` (drop `test_mcp_` prefixes; `test_mcp_enhanced.py` → `test_tools.py`).
- Hygiene: removed 4 overlapping `wiki_add` default/synth unit cases from `tests/mcp/test_wiki_add.py` (owned by `test_add_cli_proxy.py`); kept timeout/poll, lock-holder, and CLI-proxy acceptance contracts.
- Coverage 87.34%; `python3 -m pytest tests/ -q` → 6813 passed.
- CHANGELOG `[Unreleased]`: extended existing #280/#315 standards + mirror-layout bullets with #316 / `tests/mcp/` (no separate “MCP tests moved” entry).
- AGENTS.md / CLAUDE.md: no edit — they point at CODING_STANDARDS for layout and do not list `tests/cli/` / `tests/render/` mirrors.
- Next: Slice 3 complete → commit / PR as orchestrator directs
