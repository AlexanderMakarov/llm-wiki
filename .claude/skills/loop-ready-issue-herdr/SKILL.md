---
name: loop-ready-issue-herdr
description: One-ticket herdr worker contract for the ready-issue loop — route a single GitHub issue to `/fix-bug` or `/implement-feature`, then finish with post-merge CI on main and a synced primary checkout. Driver-inlined only; use whenever the user or herdr driver delivers a labeled assigned issue, says loop ready issue, self-heal queue, or issue-N worker tab — not a user slash command.
disable-model-invocation: true
---

# Loop ready issue (herdr) — one ticket

`scripts/loop_ready_issue_herdr.py` reads this file and inlines it into each herdr worker prompt. Agents do not self-invoke this skill.

## Contract

1. **Input:** one GitHub issue number or URL (provided by the driver prompt).
2. **Route:** inspect issue labels on that ticket — if `bug` is present, run `/fix-bug <url>`; otherwise run `/implement-feature <url>`.
3. **Scope:** deliver **this issue only**. Do not start a second ticket, list the readiness queue, or advance to the next queued issue.
4. **Delivery:** follow the chosen command’s delivery flow through **Definition of Done** in that command (PR merge is not the end).
5. **Issue link:** link the PR with `Closes #N` when it delivers what this issue owns; if you deliver only part, use `Relevant to #N` and name what remains in your final report.

## Close-out (required — same bar as the herdr driver α gate)

The driver starts the **next** ticket only after **merge + green post-merge CI on `main`**, on its own poll interval (often 300s or 600s). Your job is still to **finish delivery in this worker** — do not stop when the user says “merged”, when the issue flips to CLOSED, or when PR-head CI was green.

After `gh pr merge` (or once you learn the PR merged):

1. **Post-merge CI (α)** — wait until every check run on the **merge commit** is completed and green (`success`, `skipped`, or `neutral`). PR-head `gh pr checks --watch` is necessary before merge but **not** sufficient after merge.
   ```bash
   cd /path/to/llm-wiki   # repository root you used for the change
   REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
   python3 scripts/wait_post_merge_ci.py --issue <N> --repo "$REPO"
   ```
   Or `--pr <PR>` / `--merge-sha <SHA>` if you already know them. Report green/red and merge SHA in chat.

2. **Sync primary checkout** — update the checkout you develop from (not only a throwaway worktree):
   ```bash
   git fetch origin main
   git pull --ff-only origin main
   git log -1 --oneline
   ```

3. **Final report** — PR URL, merge commit SHA, post-merge CI result, local-review verdict, and confirmation that `main` was pulled. Do not close or transition the GitHub issue (automation may close it via `Closes #N`).

Stopping after merge without α leaves the operator and the driver guessing; the driver may keep the `issue-N` tab open until its next poll sees green CI.
