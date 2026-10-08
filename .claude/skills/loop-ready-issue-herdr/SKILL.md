---
name: loop-ready-issue-herdr
description: One-ticket herdr worker contract for the ready-issue loop — route a single GitHub issue to `/fix-bug` or `/implement-feature`. Driver-inlined only; not a user slash command.
disable-model-invocation: true
---

# Loop ready issue (herdr) — one ticket

`scripts/loop_ready_issue_herdr.py` reads this file and inlines it into each herdr worker prompt. Agents do not self-invoke this skill.

## Contract

1. **Input:** one GitHub issue number or URL (provided by the driver prompt).
2. **Route:** inspect issue labels on that ticket — if `bug` is present, run `/fix-bug <url>`; otherwise run `/implement-feature <url>`.
3. **Scope:** deliver **this issue only**. Do not start a second ticket, list the readiness queue, or advance to the next queued issue.
4. **Delivery:** follow the chosen command’s delivery flow through PR merge. Do not restate or duplicate delivery-flow gates here — those live in `/fix-bug` and `/implement-feature`.
5. **Issue link:** the driver starts the next ticket only after this issue closes. Link the PR with `Closes #N` when it delivers what this issue owns; if you deliver only part, use `Relevant to #N` and name what remains in your final report so the operator can decide.
