---
title: "CLI reference (part 18/19)"
slug: cli-reference-18
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 18 of 19 of **CLI reference**.

- `0` — the scheduler files were written (and activated unless `--no-activate`), or you answered **n** at the final confirmation (automation skipped; vault and config unchanged).
- `1` — scheduler activation failed (`--activate` default); status file records `scheduler_error`.
- `2` — the schedule is not an expression llmwiki can translate.

The installed wrapper script ends its log with `EXIT:<code>`, the scheduled command's real exit code, and exits with that same code — so the scheduler can tell a usage-limit stop (`75`) from a failure (`1`). Wrappers installed by an older release always logged `EXIT:0`; re-run `install-automation` to regenerate them.

**Status file fields** (under `<vault>/.llmwiki/automation-status.json`): in addition to job/schedule keys, activation adds `scheduler_activated` (bool), `scheduler_backend` (`systemd` / `launchd` / `schtasks`), `scheduler_units_dir` (install path), `scheduler_active` (read-back when available), and `scheduler_error` (string when activation failed).

---
