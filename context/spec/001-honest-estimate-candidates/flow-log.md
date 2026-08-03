# Flow log: 001-honest-estimate-candidates

## fetch-ticket
- Ticket: #113 — bug: synth --estimate prints a candidate backlog that only reflects the pre-synth wiki
- URL: https://github.com/AlexanderMakarov/llm-wiki/issues/113
- State: OPEN; no owning PR
- Chosen over default roadmap #81 per user

## resume-detection
- No prior flow-log / spec artifacts; start from scratch

## workspace
- Branch: `feat/113-honest-estimate-candidates` from `origin/main`
- Working tree clean at branch create

## specs (functional)
- Approved via AskQuestion
- Written: `context/spec/001-honest-estimate-candidates/functional-spec.md`
- Noted on #81: cross-link comment about shared labelling convention (no #81 code in this PR)
- Next: `/awos-tech`

## specs (technical)
- Approved via AskQuestion
- Written: `context/spec/001-honest-estimate-candidates/technical-considerations.md`
- Decisions: post-run Candidates via `summarize_backlog`; share summary with `all --with-synth`; small shared reporting helper; omit live tokens/cost
- Next: `/awos-tasks`

## specs (tasks)
- Written: `context/spec/001-honest-estimate-candidates/tasks.md` (4 slices; implementation → general-purpose; QA → testing-expert)
- Next: commit-specs, then `/awos-implement`
