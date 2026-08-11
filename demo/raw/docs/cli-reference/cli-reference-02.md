---
title: "CLI reference (part 2/8: build — compile the static HTML site)"
slug: cli-reference-02
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 2 of 8 of **CLI reference** — build — compile the static HTML site.

## `build` — compile the static HTML site

Turns `wiki/` markdown into `site/` HTML. Also writes AI-consumable exports (`llms.txt`, `llms-full.txt`, `sitemap.xml`, `rss.xml`, `robots.txt`, `graph.jsonld`, `ai-readme.md`) into the output directory — there is no separate `export` subcommand.

```bash
python3 -m llmwiki build
python3 -m llmwiki build --out ~/public_html
python3 -m llmwiki build --search-mode tree
python3 -m llmwiki build --synthesize --claude /usr/local/bin/claude
python3 -m llmwiki build --vault ~/my-vault --out ~/site
```

### Flags

| Flag | What |
|---|---|
| `--out PATH` | Output directory. Default: `./site/`. |
| `--synthesize` | Call the `claude` CLI for overview synthesis (experimental). |
| `--claude PATH` | Path to the `claude` binary. Default: `/usr/local/bin/claude`. |
| `--search-mode {auto,tree,flat}` | Search routing mode (#53). `auto` picks tree vs flat from heading depth; `tree` / `flat` force the mode. Default: `auto`. |
| `--vault PATH` | Vault-overlay mode — build from an existing Obsidian / Logseq vault. Output still lands at `--out`. |

### Expected output (final lines)

```
  wrote search-index.json (7 KB meta) + 30 chunks (904 KB total) · tree mode · 64% deep pages
  wrote 7 AI-consumable exports: ai-readme.md, graph.jsonld, llms-full.txt, llms.txt, robots.txt, rss.xml, sitemap.xml
  wrote site/graph.html (interactive graph viewer)
  wrote site/prototypes/index.html (6 prototype states)
  wrote site/docs/ (94 editorial pages: hub + tutorials + style guide)
==> build complete: 703 HTML files, 61 MB
```

---

## `serve` — start a local HTTP server

```bash
python3 -m llmwiki serve
python3 -m llmwiki serve --port 9000
python3 -m llmwiki serve --dir ~/public_html
python3 -m llmwiki serve --open
```

### Flags

| Flag | What |
|---|---|
| `--dir PATH` | Directory to serve. Default: `./site/`. |
| `--port N` | Port. Default: `8765`. |
| `--host ADDR` | Bind address. Default: `127.0.0.1`. Use `0.0.0.0` to share on LAN. |
| `--open` | Open the browser at the root URL after starting. |

**Stdlib only** — it's `http.server` underneath. Safe for local use; don't expose to the public internet.

---

## `usage` — MCP tool-usage telemetry vs synthesis cost (#26)

```bash
python3 -m llmwiki usage              # human-readable report
python3 -m llmwiki usage --json       # machine-readable totals
python3 -m llmwiki usage --compact    # roll past months into rollup.json first
```

Folds the local MCP telemetry logs into totals and prints them next to the synthesis cost persisted in state — so the "is this wiki earning its synthesis spend?" question is answerable at a glance.

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
