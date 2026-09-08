---
title: "CLI reference (part 14/15)"
slug: cli-reference-14
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 14 of 15 of **CLI reference**.

- `0` — the scheduler files were written (and activated unless `--no-activate`), or you answered **n** at the final confirmation (automation skipped; vault and config unchanged).
- `1` — scheduler activation failed (`--activate` default); status file records `scheduler_error`.
- `2` — the schedule is not an expression llmwiki can translate.

**Status file fields** (under `<vault>/.llmwiki/automation-status.json`): in addition to job/schedule keys, activation adds `scheduler_activated` (bool), `scheduler_backend` (`systemd` / `launchd` / `schtasks`), `scheduler_units_dir` (install path), `scheduler_active` (read-back when available), and `scheduler_error` (string when activation failed).

---
