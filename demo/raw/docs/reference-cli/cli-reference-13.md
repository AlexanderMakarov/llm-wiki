---
title: "CLI reference (part 13/15: install-automation — set up the daily job)"
slug: cli-reference-13
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-07
source: "docs/reference/cli.md"
content_sha256: 68214fcdadc8d21482c73af718d17b4858152fb41607ffe75ccafc726af46640
---

> Part 13 of 15 of **CLI reference** — install-automation — set up the daily job.

## `install-automation` — set up the daily job

Sets up the job that keeps your wiki current so you do not have to run the steps by hand. Interactive by default: it asks what the daily job should do, when it should run, and shows you the exact command line before writing anything. Pass `--yes` with the flags below for an unattended install.

### What the daily job can do

| Job | What it does | Writes | Cost |
|---|---|---|---|
| **Ingest only** (default) | Collects new agent sessions into your vault and refreshes the site. | `raw/`, `site/` | Never contacts an AI provider — free. |
| **Maintain** | Collects new sessions, summarises each one into a wiki page, gathers candidate topics for review, refreshes the site, and reports wiki quality findings into the run log. | `raw/`, `wiki/sources/`, `wiki/candidates/`, `site/` | Sends session text to your AI provider — this costs money once a real provider is configured. Run `llmwiki synth --estimate` to see how much before the job first fires. |

### Optional extras (maintain only)

Nothing here is on by default; the wizard offers them as one comma-separated question and each has a flag.

| Extra | Flag | Effect |
|---|---|---|
| Build the knowledge graph | `--graph builtin` / `--graph graphify` | The job also builds the graph, with the built-in builder or the richer `graphify` one (`pip install llm-wiki-plus[graph]`; the job falls back to the built-in builder until that extra is installed). Writes `graph/`. |
| Fail the job on quality errors | `--lint-fail errors` | The scheduled job reports failure when the quality check finds errors. |
| Fail the job on quality warnings | `--lint-fail warnings` | The scheduled job reports failure on any warning or error. Stricter than `errors`. |

Without a failure policy the quality check still runs and its full report lands in the run log — findings simply never mark the job as failed.

### When it runs

The wizard offers presets and translates each into a cron expression; `--schedule` takes the same expression directly. Whatever the route, the schedule is validated before any unit file is written — an expression llmwiki cannot translate into your OS scheduler's own format is refused with the reason (exit code `2`).

| Preset | Cron | Example |
|---|---|---|
| Every day | `M H * * *` | `"0 8 * * *"` — every day at 08:00 (the default) |
| Weekdays only | `M H * * 1-5` | `"30 7 * * 1-5"` — weekdays at 07:30 |
| Once a week | `M H * * D` | `"0 18 * * 3"` — Wednesdays at 18:00 |
| Custom cron expression | as typed | `"0 */6 * * *"` — every six hours |

Supported grammar is standard 5-field cron: `*`, integers, lists (`1,15`), ranges (`1-5`), steps (`*/15`), day names `SUN`–`SAT`, month names `JAN`–`DEC`. Nicknames (`@daily`), Vixie/Quartz extensions (`L`, `W`, `#`), a seconds field, and any expression restricting both day-of-month and day-of-week are refused — the last one because cron ORs those two fields and no OS scheduler can express it.

Linux systemd timers use `Persistent=true` so a missed run catches up once after wake (not every skipped day while the laptop stayed off). By default the installer writes rendered units to `~/.automation/`, copies them into your OS scheduler (`~/.config/systemd/user` on Linux, `~/Library/LaunchAgents` on macOS), and enables the job. Pass `--no-activate` to write unit files only and print manual enable commands. Each run appends to `<vault>/.llmwiki/last-automation.log` (truncated each run). `.llmwiki/automation-status.json` under the vault drives the Home Automation panel and records scheduler activation state. The wizard defaults to **Maintain** on Enter; choose **1** for ingest-only. Re-running replaces the existing job rather than adding a second one.

```bash
python3 -m llmwiki install-automation
python3 -m llmwiki install-automation --yes --job maintain
python3 -m llmwiki install-automation --yes --job maintain --graph builtin --lint-fail errors --schedule "0 8 * * 1-5"
python3 -m llmwiki install-automation --yes --job ingest --schedule "30 7 * * *" --units-dir ~/.config/systemd/user
python3 -m llmwiki install-automation --yes --job maintain --synth-backend ollama --watch-enabled
python3 -m llmwiki install-automation --yes --no-activate
python3 -m llmwiki install-automation --vault ~/my-vault
```

### Flags

| Flag | What |
|---|---|
| `--yes` | Non-interactive: use the flags and defaults below; never installs hooks. |
| `--job {ingest,maintain}` | What the daily job does. Default: `ingest`. |
| `--graph {none,builtin,graphify}` | Build the knowledge graph, and with which builder. Default: `none`. |
| `--lint-fail {never,errors,warnings}` | Quality findings at this level report the scheduled job as failed. Default: `never`. Same spelling as the `all` flag. |
| `--schedule "<cron>"` | When the job runs, as a 5-field cron expression. Default: `"0 8 * * *"`. An expression that cannot be translated exits `2` with the reason. |
| `--synth-backend NAME` | Synthesis backend for automation status (interactive mode also writes `synthesis.backend` to `config.json`, after you confirm the summary). |
| `--units-dir PATH` | Staging directory for rendered unit files before OS activation. Default: `~/.automation/`. Linux/macOS still install into the platform scheduler location unless `--no-activate`. |
| `--watch-enabled` | Set `watch_enabled` in automation status so the site Automation panel shows Watch: on (does not install or start `llmwiki watch`). |
| `--force-platform {linux,macos,windows}` | Override platform detection for unit format. |
| `--activate` | Copy units into the OS scheduler location and enable the job (default). |
| `--no-activate` | Write unit files only; print copy-paste enable commands. |
| `--vault PATH` | Vault the job runs against: `automation-status.json` is written under it, and the scheduled command carries `--vault PATH` whenever it differs from `vault.default_path` in `config.json`, so the job and its status file always mean the same vault. Omitted, the job resolves its vault from config. |
| `--profile {A,B,C}` | **Deprecated** — use `--job`. `A` maps to `ingest`, `B` and `C` to `maintain`. Prints a notice; `--job` wins when both are given. |
| `--hour N` | **Deprecated** — use `--schedule`. Translated to `"{minute} {hour} * * *"`, and ignored with a notice when `--schedule` is given. |
| `--minute N` | **Deprecated** — use `--schedule`. See `--hour`. |

Exit codes:

- `0` — the scheduler files were written (and activated unless `--no-activate`), or you answered **n** at the final confirmation (automation skipped; vault and config unchanged).
- `1` — scheduler activation failed (`--activate` default); status file records `scheduler_error`.
- `2` — the schedule is not an expression llmwiki can translate.
