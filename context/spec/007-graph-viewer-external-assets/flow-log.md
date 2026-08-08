# Flow log — 007-graph-viewer-external-assets (#127)

## workspace
- Branch: `feat/127-graph-viewer-external-js`
- Worktree: `.claude/worktrees/feat-127-graph-viewer-external-js` (from `origin/main` @ 853faa6)
- Throwaway vault: `.worktree-vault` via worktree `config.json`
- Primary checkout left alone (user: no edits in main working tree)
- Next: specs (`functional-spec` approved → write done)

## specs — functional
- `functional-spec.md` Approved (user gate)
- Scope add vs issue text: ship canvas library locally for offline / `file://` (user chose)
- Open modes: disk (`file://`) + plain static HTTP; product serve/API out of scope
- Next: `/awos:tech`

## specs — technical
- `technical-considerations.md` Approved (user gate)
- Decisions: `render/graph_viewer.py`; inline GRAPH stub; commit `llmwiki/vendor/vis-network.min.js@9.1.9`; standalone emits html+viewer+vis only; CI size budget 32_000 on `GRAPH_VIEWER_JS`
- Next: tasks.md + commit specs

## specs — tasks
- `tasks.md` written (implement-feature suppresses draft Approve ask)
- Slices: (1) extract+emit viewer (2) vendor vis (3) docs/changelog (4) testing-expert regression
- Agents: general-purpose for impl; testing-expert for Slice 4
- Next: commit-specs then `/awos:implement`
