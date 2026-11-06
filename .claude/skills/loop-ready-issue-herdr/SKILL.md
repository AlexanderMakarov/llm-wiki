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

1. **Your slash command’s Definition of Done** — whatever `/fix-bug` or `/implement-feature` requires for that issue (this skill does not list those steps).
2. **Merged closing PR** — GitHub shows the issue closed with a merged PR that closes it.
3. **Post-merge α** — required checks on the merge commit are green (see `docs/maintainers/LOOP_READY_ISSUE_HERDR.md`).
4. **Phase A on `MAIN`** — after the delivery command syncs the primary checkout, `git log` there includes `#N` for this issue (driver polls locally; no fetch in the driver itself).

Until all four hold, this worker tab may stay open while the driver polls; that is normal when review or merge is still pending.
