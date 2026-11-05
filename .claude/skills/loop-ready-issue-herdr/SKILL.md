---
name: loop-ready-issue-herdr
description: Use when the loop-ready-issue herdr driver starts a worker tab with one issue URL and MAIN= set — not for general feature delivery outside that driver.
disable-model-invocation: true
---

# Loop ready issue (herdr) — one ticket

`scripts/loop_ready_issue_herdr.py` reads this file and pastes it into the worker’s first prompt. Agents do not self-invoke this skill.

## Before you run an AWOS command

- **One ticket.** The driver gave exactly one issue URL below. Do not list the readiness queue, start another issue, or advance the queue — the driver owns that.
- **`MAIN=`** (when present in the driver prompt) is the **primary checkout** path. Use it only where `/fix-bug` or `/implement-feature` says to sync after merge — not as the implementation worktree.

## Route

1. **Input:** the GitHub issue number or URL in the driver prompt (below the `---`).
2. **Command:** if the issue has a `bug` label, run `/fix-bug <url>`; otherwise run `/implement-feature <url>`.
3. **Authority:** smoke confirm, local review keep/drop, commit/push, `gh pr create`, CI watch, and merge confirmation are defined **only** in that command and in `context/product/delivery-flow.md`. This skill does not repeat or shorten them — run the chosen command **completely**.

## After the AWOS command finishes merge (herdr-specific)

These are queue/driver expectations **outside** the AWOS step list:

- **Merge:** follow the command’s merge step — per-run operator confirmation before `gh pr merge`; never `gh pr merge --admin` unless the operator explicitly requests it in this chat; if `REVIEW_REQUIRED` blocks merge, stop at **ready-to-merge** (CI green, PR URL, human review needed). Do not self-approve your own PR.
- **Post-merge:** watch post-merge CI on `main` if the command requires it; then `git -C "$MAIN" fetch origin main` and `git -C "$MAIN" pull --ff-only origin main`. Optional helper: `python3 scripts/wait_post_merge_ci.py`.
- **Driver:** this tab stays open until the issue has a merged closing PR and post-merge checks (α) pass; waiting on you for review or merge is normal.
