---
title: "Scale ingredient quantities without mangling fractions"
type: source
description: "Doubling a recipe produced unreadable decimals instead of familiar fractions."
tags: [session]
date: 2026-08-07
source_file: raw/sessions/recipe-box/2026-08-07T14-03-recipe-box-ingredient-scaling.md
sessionId: d1e026e5-3bf5-bb25-9dc7-17baa1fc920a
slug: ingredient-scaling
project: recipe-box
started: 2026-08-07T14:03:00+00:00
ended: 2026-08-07T14:36:00+00:00
cwd: /home/USER/code/recipe-box
gitBranch: feat/scaling
permissionMode: default
model: claude-opus-5
user_messages: 2
tool_calls: 19
tools_used: [Read, Edit, Bash]
tool_counts: {"Read": 2, "Edit": 5, "Bash": 8}
token_totals: {"input": 21630, "output": 3945}
turn_count: 4
duration_seconds: 1980
is_subagent: false
entrypoint: cli
promptSource: typed
is_headless: false
agent: claude-code
---

# Session: ff564f56 — 2026-08-07

Doubling a recipe produced unreadable decimals instead of familiar fractions.

## Conversation

### Turn 1 — User

Doubling a recipe gives me 0.6666666666666666 cups.

### Turn 2 — Assistant

Quantities are now kept as exact fractions through the scaling arithmetic and only converted for display, snapping to the denominators people actually use in a kitchen.

Two thirds doubled now reads as one and a third rather than a decimal expansion.

### Turn 3 — User

What about something that does not divide nicely?

### Turn 4 — Assistant

It falls back to the nearest common fraction and marks the value approximate, which is what a written recipe does anyway.

## Subjects

- [[Web App]]
- [[Validation]]
