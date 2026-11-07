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

- **`bug` label** on the issue → `/fix-bug <url>`, defined in `.claude/commands/fix-bug.md`
- **Otherwise** → `/implement-feature <url>`, defined in `.claude/commands/implement-feature.md`

A slash command inside this pasted prompt is not expanded for you: **open that command file first and execute it completely, from its first stage**, for the URL below. Its isolated worktree is where you implement; never check out a branch or edit files in **`MAIN`**.

## What herdr needs to advance

Finish this ticket so GitHub and the driver’s **`MAIN`** checkout both show it as done:

1. **GitHub issue closed** — normally a **merged** closing PR with green **post-merge** checks (follow the slash command through merge and CI).
2. **Commits on `main` name the ticket** — include **`#N`** in delivery commit messages (e.g. `(#N)` / `Closes #N` when the issue is fully delivered).
3. **`MAIN` updated** — after merge, run the slash command’s post-merge sync on **`MAIN`** so the merge commit is in the primary checkout's history the driver polls.
