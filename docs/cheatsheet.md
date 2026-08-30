---
title: "Command cheatsheet"
type: navigation
docs_shell: true
---

# Command cheatsheet

Everything you need on one page. Slash commands work inside Claude Code / Codex CLI; CLI commands run at your terminal.

## 30-second setup

From Claude Code, run these slash commands in order:

1. `/wiki-init` — scaffold raw/ wiki/ site/
2. `/wiki-sync` — ingest sessions from every auto-detected agent
3. `/wiki-graph` — build the AI knowledge graph
4. `/wiki-build` — compile the static site
5. Open `site/index.html` — the site is plain files, nothing to run
6. `llmwiki install-automation` — hand that loop to a daily job so you never repeat it

## Keeping it current

Set the daily job up once and llmwiki keeps itself up to date. The wizard asks what the job should do (collect sessions only, or also summarise them), offers the optional extras, and shows you the exact command line before it writes anything.

```bash
llmwiki install-automation                                   # interactive wizard
llmwiki install-automation --yes --job ingest                # collect sessions + rebuild the site; no AI provider, no cost
llmwiki install-automation --yes --job maintain --schedule "0 8 * * 1-5"   # also summarise; weekdays at 08:00
llmwiki install-automation --yes --job maintain --graph builtin --lint-fail errors
```

`--job maintain` sends session text to your AI provider — run `llmwiki synth --estimate` first to see what a run costs. Re-running the command replaces the existing job instead of adding a second one. Full flag table: [CLI reference](reference/cli.md#install-automation--set-up-the-daily-job).

For a one-off run of the same pipeline by hand:

```bash
llmwiki all                            # sync → synth → build → graph → lint
llmwiki all --no-synth                 # same run, no LLM calls
llmwiki all --skip-graph --skip-lint   # sync → synth → build only
llmwiki all --lint-fail errors         # exit 2 when lint reports an error
```

## One step at a time

| What you want | Slash command | CLI equivalent |
|---|---|---|
| Convert new session transcripts | `/wiki-sync` | `llmwiki sync` |
| Ingest a source file into the wiki | `/wiki-ingest <path>` | -- |
| Ask the wiki a question | `/wiki-query <question>` | -- |
| Edit one page surgically | `/wiki-update <page>` | -- |
| Find orphans + broken links | `/wiki-lint` | `llmwiki lint` |
| Triage candidate pages | -- | `llmwiki candidates list` |
| Build / rebuild the site | `/wiki-build` | `llmwiki build` |
| Interactive graph | `/wiki-graph` | `llmwiki graph` |
| AI knowledge graph | `/wiki-graph` | `llmwiki graph --engine graphify` |
| Self-reflection on wiki gaps | `/wiki-reflect` | -- |

## CLI commands you'll use most

`llmwiki --help` lists all 25 subcommands, including the `migrate-*` one-offs and the maintenance helpers. These are the ones that carry the daily loop:

| Command | Purpose |
|---|---|
| `init` | Scaffold `raw/` `wiki/` `site/` + seed 9 nav files |
| `install-automation` | Set up the daily job that runs the loop for you |
| `all` | Whole pipeline in one run: sync → synth → build → graph → lint (opt out per stage) |
| `sync` | Convert `.jsonl` sessions -> markdown -> wiki -> site |
| `synth` | Synthesize sources + harvest entity/concept candidates |
| `candidates` | Approval workflow (list / promote / merge / discard) |
| `build` | Compile `wiki/` markdown into `site/` HTML + AI exports (`llms.txt`, `sitemap.xml`, …) |
| `graph` | Build the knowledge graph (Graphify default, builtin fallback) |
| `lint` | Run 17 wiki-quality rules |
| `query` | Search the knowledge graph with a question |
| `add` | Add a URL, file, or folder to the wiki |
| `watch` | Near-real-time sync → synth → build when a session finishes |
| `adapters` | List every adapter + its status |
| `synthesize` | *(deprecated)* alias for `synth --sources-only` |
| `version` | Print version |

## Knowledge graph

```bash
llmwiki graph                          # builtin wikilink graph (stdlib, zero deps)
llmwiki graph --engine graphify        # AI-powered: Leiden communities, confidence edges, god nodes
llmwiki graph --format json            # json only
llmwiki graph --format html            # interactive HTML only
```

Install Graphify: `pip install llm-wiki[graph]`

Graphify outputs to `graphify-out/`: `graph.json`, `graph.html`, `GRAPH_REPORT.md`.
Features: tree-sitter AST extraction, semantic analysis, community detection, confidence-scored edges.

## AI-consumable exports

`llmwiki build` writes every AI-consumable export into the output directory (default `site/`). There is no separate `export` subcommand — replace `llmwiki export all` with `llmwiki build`.

```bash
llmwiki build                          # HTML site + llms.txt, llms-full.txt, graph.jsonld, sitemap.xml, rss.xml, robots.txt, ai-readme.md
```

## Quality

```bash
llmwiki lint                           # 17 wiki-quality rules
llmwiki lint --json --fail-on-errors   # CI-friendly
llmwiki lint --rules link_integrity,orphan_detection
llmwiki lint --vault /path/to/vault --fail-on-warnings   # rules switched off in <vault>/llmwiki.json never run
```

## Candidate workflow

```bash
llmwiki candidates list                # show all candidates
llmwiki candidates list --stale        # only stale (>30 days)
llmwiki candidates promote --slug Foo  # promote to wiki
llmwiki candidates merge --slug A --into B
llmwiki candidates discard --slug X --reason "hallucinated"
```

## LLM synthesis

```bash
llmwiki synth                          # sources + candidates
llmwiki synth --sources-only           # legacy: sources only
llmwiki synth --check                  # probe backend (exit 0 if ok)
llmwiki synth --estimate               # cost (eligible sources) + Candidates (pre-run state)
llmwiki synth --force                  # re-synth everything, then harvest
llmwiki synthesize                     # deprecated → sources-only + warning
```

Auto-tags pages (up to 5 AI tags per page, near-dup rejection, stop-word filter).

## Adapters

```bash
llmwiki adapters                       # list every adapter + who fires on next sync
llmwiki adapters --wide                # untruncated descriptions
```

**Core** (auto-discovered, always loaded):

| Adapter | Source |
|---------|--------|
| `claude_code` | `~/.claude/projects/` |
| `codex_cli` | `~/.codex/sessions/` |

**Contrib** (load on-demand with `--adapter <name>`):

| Adapter | Source |
|---------|--------|
| `chatgpt` | `conversations.json` export |
| `copilot_chat` | VS Code workspaceStorage |
| `copilot_cli` | GitHub Copilot CLI |
| `cursor` | Cursor IDE workspaceStorage (limited — #2) |
| `cursor_cli` | `~/.cursor/chats/` (Agent CLI) |
| `gemini_cli` | `~/.gemini/` |
| `obsidian` | Obsidian vault `.md` files (notes intake) |
| `opencode` | OpenCode / OpenClaw app-config sessions |
| `openclaw` | `~/.openclaw/agents/` |

Support map + headless rules: [multi-agent-setup.md](multi-agent-setup.md).

## Obsidian integration

```bash
# Sync wiki into an Obsidian vault
llmwiki sync --vault "~/Documents/Obsidian Vault/my-wiki"

# Build site from a vault
llmwiki build --vault "~/Documents/Obsidian Vault/my-wiki"

# Use the obsidian adapter to read from a vault
llmwiki sync --adapter obsidian
```

## Flags you'll actually use

| Flag | Command | What |
|---|---|---|
| `--since YYYY-MM-DD` | `sync` | One-run lookback (overrides `filters.since` / `adapters.*.since`) |
| `--project <slug>` | `sync` | Restrict to one project |
| `--force` | `sync`, `synthesize` | Ignore state file, reconvert everything |
| `--force-resync` | `sync` | Override the newer-schema/corrupt-state guard (#29); implies `--force`, may duplicate `raw/` |
| `--fail-on-errors` | `lint` | Non-zero exit on error-severity issues |
| `--fail-on-warnings` | `lint` | Non-zero exit on warning-severity issues; pass both flags to gate on either |
| `--min-refs N` | `lint`, `synth`, `all` | How many distinct source pages must name a `[[wikilink]]` target before it earns a candidate page — and before an unresolved link to it is a finding (default: `3`) |
| `--no-sync`, `--no-synth` | `all` | Drop a stage from the run; `--no-synth` makes it LLM-free |
| `--lint-fail {never,errors,warnings}` | `all`, `install-automation` | Which quality findings end the run with exit `2` (default: `never`) |
| `--job {ingest,maintain}` | `install-automation` | What the daily job does — collect only, or also summarise |
| `--schedule "<cron>"` | `install-automation` | When the daily job runs, e.g. `"0 8 * * 1-5"` |
| `--vault <path>` | `sync`, `build`, `synthesize`, `lint`, `add`, `queue`, `all` | Operate on an external vault (also sets the active state file) |
| `--local-root <path>` | `build` | Value shown in place of a session's stored home directory (default: this machine's home) |
| `--engine graphify` | `graph` | AI-powered knowledge graph |
| `--status` | `sync` | Show last sync + per-adapter counters |

## Config files

| File | Purpose |
|---|---|
| `config.json` / `examples/sessions_config.json` | All settings (see below) |
| `.llmwikiignore` | Exclude patterns (git-ignore format) |
| `llmwiki-state.json` | Unified queue + sync + synth + quarantine state (auto; gitignored) |
| `llmwiki-state.js` | UI sidecar for the Home queue panel (vault root + copied into `site/` on build) |
| `.env` | Optional secrets for adapters that need them |

## All configurable settings (sessions_config.json)

| Section | Key | Default | What |
|---|---|---|---|
| `vault` | `default_path` | `""` (must pass `--vault`) | Default Obsidian/Logseq vault path |
| `vault.layout` | `entities` | `Wiki/Entities` | Vault subfolder for entity pages |
| `vault.layout` | `concepts` | `Wiki/Concepts` | Vault subfolder for concept pages |
| `vault.layout` | `sources` | `Wiki/Sources` | Vault subfolder for source pages |
| `vault.layout` | `syntheses` | `Wiki/Syntheses` | Vault subfolder for synthesis pages |
| `vault` | `allow_overwrite` | `false` | Allow clobbering existing vault pages |
| `graph` | `default_engine` | `builtin` | Graph engine: `builtin` or `graphify` |
| `graph` | `format` | `both` | Graph output: `json`, `html`, or `both` |
| `build` | `out_dir` | `site` | Build output directory |
| `build` | `search_mode` | `auto` | Search index mode: `auto`, `tree`, `flat` |
| `build` | `synthesize` | `false` | Auto-synthesize overview on build |
| `schedule` | `build` | `on-sync` | When to auto-build: `on-sync`, `daily`, `manual` |
| `schedule` | `lint` | `manual` | When to auto-lint: `on-sync`, `daily`, `manual` |
| `synthesis` | `backend` | `dummy` | LLM backend: `dummy`, `ollama` |
| `synthesis` | `model` | `llama3.1:8b` | Model for synthesis |
| `synthesis` | `base_url` | `http://127.0.0.1:11434` | Ollama server URL |
| `synthesis` | `timeout` | `60` | Synthesis timeout (seconds) |
| `filters` | `live_session_minutes` | `60` | Skip sessions younger than N minutes |
| `filters` | `since` | unset | Shared sync lookback (`YYYY-MM-DD`); omit = unlimited; see [configuration-reference.md](configuration-reference.md#sync-lookback) |
| `adapters.<name>` | `since` | unset | Per-source lookback (`YYYY-MM-DD` or `"all"`); omit = inherit shared |
| `truncation` | `tool_result_chars` | `500` | Max chars for tool results in output |

## Three-layer architecture

```
raw/     IMMUTABLE transcripts (source of truth, never modify)
wiki/    LLM-generated pages (you own this)
  sources/      one summary per raw source
  entities/     people, products, tools (TitleCase.md)
  concepts/     ideas, patterns, decisions (TitleCase.md)
  projects/     codebases and work streams (kebab-case slug)
  syntheses/    saved query answers
site/    GENERATED static HTML (don't edit by hand)
```

## Common recipes

```bash
# Daily, hands-off: schedule the whole loop
llmwiki install-automation --yes --job maintain --schedule "0 8 * * 1-5"

# Daily, by hand: the same loop as one run, then open site/index.html
llmwiki all

# Nightly cron (one project)
llmwiki sync --project my-project --no-auto-lint --since $(date -v-1d +%Y-%m-%d)

# AI knowledge graph
pip install llm-wiki[graph]
llmwiki graph --engine graphify

# CI quality gate
llmwiki lint --json --fail-on-errors

# Export wiki to Obsidian vault
llmwiki sync --vault "~/Documents/Obsidian Vault/my-wiki"

# Full site rebuild with AI synthesis (exports included)
llmwiki build --synthesize
```

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Operation failed |
| `2` | Usage error (bad flags) |

## See also

- [CLI reference](reference/cli.md) -- every flag of every subcommand
- [Slash commands reference](reference/slash-commands.md) -- what each `/wiki-*` does
- [UI reference](reference/ui.md) -- every screen on the compiled site
- [Upgrade guide](UPGRADING.md) -- what changes between releases
