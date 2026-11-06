---
name: loop-ready-issue-herdr
description: Use when the loop-ready-issue herdr driver pastes one issue URL and optional MAIN= into a worker tab — not for delivery outside that driver prompt.
disable-model-invocation: true
---

# Loop ready issue (herdr) — one ticket

`scripts/loop_ready_issue_herdr.py` pastes this file into the worker’s first prompt. Agents do not self-invoke this skill.

## Before

- The driver supplied **one** issue URL (below the `---`). Listing the readiness queue or starting another issue is the driver’s job, not yours.
- **`MAIN=`** in the driver prompt, when present, names the **primary checkout** the delivery command uses for post-merge sync — not your implementation worktree.

## Route

- **`bug` label** on the issue → `/fix-bug <url>`
- **Otherwise** → `/implement-feature <url>`

Run that slash command for the URL below. All delivery steps live in that command only.

## What herdr needs to advance

The driver will **not** start the next ready issue until **this** ticket satisfies:

1. **Definition of Done** from the slash command you ran for this issue.
2. **Phase A:** `#N` appears in `git log -n 10 --oneline` on the driver’s main checkout (local poll only — the driver does not `git fetch` there).
3. **Phase B:** On the driver’s GitHub poll: issue **CLOSED**, closing PR **merged**, and every **completed** check run in that response is `success`, `skipped`, or `neutral`.

Path 2 (issue closed with no merged closing PR) advances without Phase A/B; see `docs/maintainers/LOOP_READY_ISSUE_HERDR.md`.
