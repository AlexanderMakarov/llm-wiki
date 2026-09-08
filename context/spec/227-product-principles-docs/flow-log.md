# Flow log — 227-product-principles-docs

## fetch-ticket
- Source: plain prompt (implement-feature + prior chat design A with corrections)
- TICKET_ID: `prompt`
- Title: Product principles and maintainer doc clarity
- Next: resume-detection → workspace → specs

## resume-detection
- No prior completed artifacts for this SPEC_NAME; fresh chain
- Next: workspace

## workspace
- BRANCH: `feat/docs-product-principles`
- WT: `.claude/worktrees/feat-docs-product-principles`
- TMP_VAULT: absolute `.worktree-vault` under WT (relative path nesting fixed)
- Next: `/awos:spec` → user approval of `functional-spec.md`

## specs (functional)
- Wrote `functional-spec.md`; surfaced contradictions (triage file still on disk; Google Fonts CDN vs brand offline claim; DECLINED Python 3.9+ wording)
- Operator amendments: skip triage changes; leave CDN alone; remove Python version from DECLINED; alignment OK
- Status → Approved
- Next: tech gate — `technical-considerations.md`

## specs (tech)
- Wrote `technical-considerations.md`; operator approved after rebase onto fresh `origin/main` (1a9ccb3, includes #237 — triage already fixed on main)
- Status → Approved
- Next: tasks.md → commit specs → implement

## specs (tasks)
- Wrote `tasks.md` (5 slices; triage out of scope)
- Next: commit-specs

## commit-specs
- Commit `5ff18ac` — `docs: add spec for product principles and maintainer doc clarity`
- Next: implement

## implement
- Slices 1–4 implemented via general-purpose subagents; Slice 5 verify run in orchestrator (testing-expert hit usage limit)
- ruff green; full pytest exit 0; acceptance greps all PASS
- Operator feedback: README too static-site oriented — primary usage is MCP
- Rebased onto fresh `origin/main` (v2.3.0 + demo fix); CHANGELOG conflict resolved
- README + principles + getting-started reframed MCP-first; static site optional
- Next: user re-confirm smoke → local review

## verify / smoke
- Operator confirmed framing (MCP + human site + pyproject description) and said deliver
- Next: local review → commit implementation → push → PR

## commit-push (pre)
- Implementation commit pending after local review keep/drop
