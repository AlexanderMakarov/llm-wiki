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
