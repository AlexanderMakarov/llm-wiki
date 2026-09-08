---
title: "CLI reference (part 3/15: usage — MCP tool-usage telemetry vs synthesis cost (#26))"
slug: cli-reference-03
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 3 of 15 of **CLI reference** — usage — MCP tool-usage telemetry vs synthesis cost (#26).

## `usage` — MCP tool-usage telemetry vs synthesis cost (#26)

```bash
python3 -m llmwiki usage              # human-readable report
python3 -m llmwiki usage --json       # machine-readable totals
python3 -m llmwiki usage --compact    # roll past months into rollup.json first
```

Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the "is this wiki earning its synthesis spend?" question is answerable at a glance.

The live MCP surface is six tools (`wiki_search`, `wiki_read_page`, `wiki_health`, `wiki_sync`, `wiki_export`, `wiki_add`); see [mcp.md](mcp.md) for parameters and migration from retired tool names (#196).

The MCP server logs one JSON record per tool call to a **per-process** file under `<vault>/usage/` (`mcp-<pid>-<start>.jsonl`), merged at read time. Several server processes run at once (one per editor session), so per-process files mean zero write contention and no lock on the hot path; telemetry never touches `llmwiki-state.json`. Each record carries `tool`, `query`, `hits` (`0` = a knowledge gap or noise; `null` = the tool can't report a count), `resp_bytes`, `duration_ms`, `caller_project`, `caller_source`, `server_pid`, `server_started`. Writes are best-effort — a telemetry failure never breaks a tool call. Opt out with `LLMWIKI_MCP_TELEMETRY=0`.

**Caller attribution.** `caller_project` is resolved per call and `caller_source` says where it came from:

| `caller_source` | Meaning |
|---|---|
| `project-dir-env` | The workspace path a client auto-injects into the server's environment. **Claude Code** sets `CLAUDE_PROJECT_DIR` (≥ v2.1.139) into every stdio MCP server — zero config — and spawns one server per session, so it is a stable per-caller signal available at the first call. |
| `client-root` | The client's own workspace directory, obtained via an MCP `roots/list` request. Attributed to the first root when a client reports several. |
| `path` | A path argument carrying the caller's working directory encoded into one segment (`…/-home-dev-code-my-app/…`), used for clients that offer neither of the above. |
| `unattributed` | No caller-scoped signal — `caller_project` is `unknown`. |

They are tried in that order. All three project sources feed one shared `slugs.project_slug_from_abs_path`, so a project resolves to the same slug whether it arrived through telemetry or through session ingestion (and thus keys onto its own project page).

**Client coverage.** Claude Code attributes every call with no setup, via `CLAUDE_PROJECT_DIR`. **Cursor** currently provides no zero-config signal — it advertises the `roots` capability but returns `Method not found` on the actual `roots/list` call, and injects no workspace env var — so its calls fall to the path heuristic where a path argument is present, else `unknown`, until it ships a fix. The server's own `os.getcwd()` is never used: a client may launch the server anywhere (Claude Code's desktop app uses `$HOME`), so it is unrelated to the caller's project.

Unattributed calls are counted in the totals but never presented as a project: they print as `(unattributed)` here and are excluded from the site's "Heaviest project by MCP usage" card. Records written by an earlier version carry no `caller_source` and are read as unattributed regardless of the project name they hold, because that name is the server process's own working directory rather than the caller's. The same applies to a `usage/rollup.json` written before this change — the raw records behind it are already deleted, so its labels are retracted rather than recomputed.

**Daily series (#52).** `usage/daily.json` stores per-day MCP call totals (`mcp_calls`, `retrievals`, `writes`, `session_reads`, `doc_reads`, `other_reads`, `by_tool`, attribution counts) so Analytics activity heatmaps survive `--compact`. Compact folds retiring JSONL files into `folded_days` before delete; each `llmwiki build` refreshes the live overlay from non-folded files without double-counting. The CLI report itself is unchanged — the Analytics page is the primary surface. See [State persistence](state-persistence.md).

Scope is MCP calls only — `file://` static-site browsing stays untracked.

### Flags

| Flag | What |
|---|---|
| `--json` | Emit the aggregated totals (`consumption` + `cost`) as JSON. |
| `--compact` | Fold whole past months into the kept-forever `usage/rollup.json` and delete their raw logs before reporting. |
| `--vault PATH` | Read telemetry from this vault instead of the repo root. |
| `--state-file PATH` | State file to read the synthesis-cost estimate from. |

---

## `configure-sources` — enable detected session stores

```bash
python3 -m llmwiki configure-sources
```

Interactive interview: **shared start date first** (Enter = today−30 or keep stored; or type `YYYY-MM-DD`). Then each shipped adapter: facts (`Sessions · Earliest · In last 30 days`, path found or not) → Enable (`[Y/n]` when a default path exists and ingest is ready, `[y/N]` otherwise) → path (suggested only if found) → start date (Enter = use shared, or `YYYY-MM-DD`). Writes `filters.since` and `adapters.<name>` to gitignored `config.json`.

Lookback quiz keys: shared **Enter** writes today−30 (or keeps stored); typed **`YYYY-MM-DD`** sets a custom shared floor. Per-source **Enter** on start date inherits shared (no `since` key); typed **`YYYY-MM-DD`** writes `adapters.<name>.since`. Merge-write touches only those `since` keys plus enable/path. Non-interactive `--yes` / skipped interview invents no dates. Config `"all"` on a per-adapter `since` key (hand-edited) still means no date gate for that source.

| Flag | What |
|---|---|
| `--yes` | Non-interactive: skip interview (no config writes). |

After pip or Homebrew install (no `setup.sh`), run this once after `llmwiki init`. Git clone `setup.sh` offers the same interview on a TTY before `install-automation`. Set `LLMWIKI_SKIP_CONFIGURE_SOURCES=1` to skip from `setup.sh`. Durable keys: [configuration-reference.md — Sync lookback](../configuration-reference.md#sync-lookback).

---

## `adapters` — list every adapter + its status

```bash
python3 -m llmwiki adapters
```

**Flags:** none.

**Expected output:**

```
Registered adapters:
  name              present   enabled   description
  ----------------  --------  --------  ------------------------------
  claude_code       yes       yes       Claude Code — reads ~/.claude/projects/
  openclaw          yes       yes       OpenClaw — reads configured roots …
  cursor_ide        yes       yes       Cursor IDE — Composer sessions (globalStorage state.vscdb)
  cursor_cli        yes       yes       Cursor Agent CLI — reads ~/.cursor/chats/
```

Columns: **present** (store path on disk), **enabled** (**yes** / **no** — included on the next bare `sync`). Set via `configure-sources`; use `sync --adapter <name>` for a one-off.

---
