# Phase A — log-only gate (2026-11-05)

Phase A no longer requires an empty `git status --porcelain` on the main checkout. Only `#N` in `git log -n 10 --oneline` after the worker pulls `MAIN`. Rationale: unrelated dirt (e.g. repo-local `.automation/`) blocked queue advance; new work always uses a fresh worktree.
