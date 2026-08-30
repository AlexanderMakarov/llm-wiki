# Configuration Reference

Complete reference for all CLI subcommands, flags, environment variables, and configuration options.

## CLI subcommands

### `llmwiki init`

Scaffold the `raw/`, `wiki/`, `site/` directory structure and seed initial wiki files.

```bash
python3 -m llmwiki init
```

No options. Creates directories and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md` if they don't already exist.

### `llmwiki sync`

Convert agent session transcripts (`.jsonl`) into markdown under `raw/sessions/`.

```bash
python3 -m llmwiki sync [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--adapter` | `name...` | all available | Only run the named adapter(s) |
| `--since` | `YYYY-MM-DD` | none | One-run lookback: only sessions on or after this date. Overrides durable `filters.since` / `adapters.*.since` for every source in the run (#192) |
| `--project` | `substring` | none | Only sync projects whose slug contains this |
| `--include-current` | flag | off | Don't skip live sessions (< 60 min old) |
| `--force` | flag | off | Ignore state file, reconvert everything |
| `--force-resync` | flag | off | Override the newer-schema / corrupt-state guard (#29) and reconvert from scratch. Implies `--force`; may duplicate an already-populated `raw/` |
| `--dry-run` | flag | off | Preview what would be written |
| `--download-images` | flag | off | Download remote images in `.md` files to `raw/assets/` |
| `--fail-on-errors` | flag | off | Exit 1 if any file fails to convert; by default per-file errors are quarantined and the run exits 0 |

### `llmwiki build`

Compile the static HTML site from `raw/` and `wiki/`. Also writes AI-consumable exports into the output directory: `llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, and `ai-readme.md`. There is no separate `export` subcommand.

```bash
python3 -m llmwiki build [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--synthesize` | flag | off | Call `claude` CLI to generate an Overview synthesis |
| `--claude` | `path` | `/usr/local/bin/claude` | Path to the claude binary |
| `--local-root` | `path` | this machine's home | Value shown in place of a session's stored home directory (#109) |

### `llmwiki adapters`

List every registered adapter and whether its session store is present.

```bash
python3 -m llmwiki adapters
```

No options.

### `llmwiki graph`

Build the knowledge graph from `wiki/` wikilinks.

```bash
python3 -m llmwiki graph [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--format` | `json\|html\|both` | `both` | Output format |

### `llmwiki lint`

Run every registered quality rule against the wiki and print a report. Rules the wiki switched off in its [`llmwiki.json`](#vault-file-llmwikijson) never run, and every report names them.

```bash
python3 -m llmwiki lint [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--wiki-dir` | `path` | `<content root>/wiki` | Wiki directory to lint. Narrower than `--vault`, and wins over it; the vault settings file is then read from this directory's parent |
| `--rules` | `name,name` | all registered rules | Comma-separated rule names to run. An unrecognised name stops the run with exit 2 and lists the valid names |
| `--min-refs` | `N` | `3` | How many distinct `wiki/sources/` pages must name a `[[wikilink]]` target before an unresolved link to it is reported as broken (see below). Must be at least 1 — a value below that is rejected rather than silently treated as 1 |
| `--json` | flag | off | Print the machine-readable report — `summary`, `issues`, `total_pages`, `disabled_rules`, `ran` — instead of the text one |
| `--fail-on-errors` | flag | off | Exit 1 when any error-severity finding was reported |
| `--fail-on-warnings` | flag | off | Exit 1 when any warning-severity finding was reported. Stricter than `--fail-on-errors`; pass both to gate on either. A rule the wiki switched off cannot stop the gate — it never ran |
| `--vault` | `path` | `vault.default_path` from `config.json` | Lint the wiki under this vault root, and read that vault's `llmwiki.json` |

**Why `--min-refs` changes how many cross-reference findings you see.** `synth` writes a `[[wikilink]]` for every topic it names, and the candidate harvest materializes a page only for a target named by enough distinct source pages to look significant. Everything below that bar is left unmaterialized *on purpose*, so `link_integrity` honours the same threshold rather than reporting the product's own design decisions as defects. The gate is three-way:

| Distinct `wiki/sources/` pages naming a target with no page of its own | Reported? | Why |
|---|---|---|
| none | **yes**, at every threshold | Nothing was ever going to materialize it, so no decision was taken — it is simply a dangling reference |
| fewer than `--min-refs` | no | The harvest deliberately declined to give this target a page |
| `--min-refs` or more | **yes** | A genuine gap: named often enough to deserve a page, and it does not have one |

So lowering the threshold widens the middle band into the reported band: `--min-refs 1` reports every unresolved link, which on a mature wiki can be hundreds of findings that were all deliberate declines. Nothing is hidden permanently — the lower threshold always brings them back. The stock value lives in one place, `llmwiki.vault_settings.DEFAULT_MIN_REFS`, which the harvest reads too, so the step that declines to create a page and the check that reports the missing page cannot drift apart. `llmwiki all --min-refs N` sets it for the synth and lint stages of a pipeline run.

### `llmwiki all` (v1.2)

Run the full pipeline: sync → synth → build → graph → lint. Every stage runs by default; each has an opt-out flag. AI-consumable exports are written by `build`, not a separate step.

```bash
python3 -m llmwiki all [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--no-sync` | flag | off | Skip the sync step (do not convert new agent sessions first) |
| `--no-synth` | flag | off | Skip the synth step, so the run makes no LLM calls |
| `--synth-force` | flag | off | Pass `--force` to synth (re-synthesize every session) |
| `--search-mode` | `auto/tree/flat` | `auto` | Forwarded to build |
| `--graph-engine` | `builtin/graphify` | `graphify` | Forwarded to graph |
| `--skip-graph` | flag | off | Skip the graph step |
| `--skip-lint` | flag | off | Skip the lint step |
| `--lint-fail` | `never/errors/warnings` | `never` | Which lint findings end the run with exit 2 |
| `--strict` | flag | off | Spelling for `--lint-fail warnings` (CI gate); the stricter of the two wins |
| `--fail-fast` | flag | off | Stop at first non-zero step |
| `--with-sync`, `--with-synth` | flag | off | Deprecated and inert — the stages they name run by default. Accepted so an already-installed scheduled command keeps parsing; each prints a one-line notice |

### `llmwiki version`

Print the current version.

```bash
python3 -m llmwiki version
```

## Config file (`config.json`)

Copy the example and edit:

```bash
cp examples/sessions_config.json config.json
```

`config.json` is gitignored. The converter auto-loads it if present at the repo root.

### Full schema

```jsonc
{
  "filters": {
    "live_session_minutes": 60,
    "include_projects": [],
    "exclude_projects": [],
    "drop_record_types": ["queue-operation", "file-history-snapshot", "progress"],
    "exclude_headless": true,
    "exclude_temp_cwd": false
  },

  "redaction": {
    "real_username": "",
    "replacement_username": "USER",
    "extra_patterns": [
      "(?i)(api[_-]?key|secret|token|bearer|password)[\"'\\s:=]+[\\w\\-\\.]{8,}",
      "sk-[A-Za-z0-9]{20,}",
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+"
    ]
  },

  "truncation": {
    "tool_result_chars": 500,
    "bash_stdout_lines": 5,
    "write_content_preview_lines": 5,
    "user_prompt_chars": 4000,
    "assistant_text_chars": 8000
  },

  "drop_thinking_blocks": true,

  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 50
    },
    "codex_cli": {
      "roots": ["~/.codex/sessions", "~/.codex/projects"]
    },
    "gemini_cli": {
      "roots": ["~/.gemini"]
    },
    "openclaw": {
      "roots": ["~/.openclaw/agents", "<vault>/.openclaw-sessions-inbox"]
    }
  }
}
```

### Sync lookback

Optional absolute date gate so bare `llmwiki sync` does not ingest years of history (#192). Unset shared and per-adapter keys mean **unlimited** — same as today’s default.

| Key | Values | Meaning |
|---|---|---|
| `filters.since` | absent, `""`, or `YYYY-MM-DD` | Shared earliest session day; absent/empty = no shared floor |
| `adapters.<name>.since` | absent, `YYYY-MM-DD`, or `"all"` | Per-source override; absent = inherit shared; `"all"` = no date gate for that source only |

**Precedence** (per adapter, highest first): CLI `--since` → adapter `YYYY-MM-DD` → adapter `"all"` → `filters.since` → unlimited. `"all"` is valid only on the per-adapter key. An invalid date string exits **2** (same as a bad `--since`).

**How sync applies it**

- **Early prune** — file-based sources drop candidates whose `SessionRef.mtime` is before the effective lookback before loading; Cursor IDE filters on Composer header timestamps before any bubble payloads are loaded. A post-load `latest_record_time` gate still runs.
- **No state on lookback skip** — sessions skipped only because of lookback are **not** written into `llmwiki-state.json` `sync.files`, so widening the window later can reconsider them on a normal sync.
- **Lookback GC** — after a successful non-dry-run sync, for each **coding-agent** adapter with a *durable* lookback (config `filters.since` / `adapters.<name>.since`, not a one-run CLI `--since`), remove that adapter’s `sync.files` keys (`"<adapter>::…"`) whose stored mtime is before the lookback. Notes/export intake (`is_ai_session: false`, e.g. Obsidian) is not GC’d. Sources with no durable lookback are untouched. GC does not delete `raw/`, and does not touch queue / synth / quarantine / ops.
- **Sync hint** — every sync ends with a line pointing at `filters.since`, `adapters.<name>.since`, and `llmwiki configure-sources`.

**`configure-sources` quiz** — **shared start date first** (Enter = today−30, or keep a stored date; or type `YYYY-MM-DD`). Then each source: facts block (`Sessions · Earliest · In last 30 days`, path found or not) → Enable (`[Y/n]` when a default path exists *and* ingest is ready, `[y/N]` otherwise) → path → start date (Enter = use shared, or `YYYY-MM-DD`). Non-interactive / skipped interviews invent no dates. See [CLI `configure-sources`](reference/cli.md#configure-sources--enable-detected-session-stores).

### Section reference

| Section | Key | Type | Default | Description |
|---|---|---|---|---|
| `filters` | `live_session_minutes` | int | 60 | Skip sessions younger than this (prevents reading mid-write) |
| `filters` | `include_projects` | list | [] | If non-empty, only sync matching project slugs |
| `filters` | `exclude_projects` | list | [] | Skip projects containing these substrings |
| `filters` | `drop_record_types` | list | [3 types] | JSONL record types to discard |
| `filters` | `since` | string | unset (unlimited) | Shared sync lookback as absolute `YYYY-MM-DD`. Absent or empty = no shared date gate. Overridden per run by CLI `--since`. See [Sync lookback](#sync-lookback) |
| `filters` | `exclude_headless` | bool | true | Skip automated / headless launches across coding-agent adapters (Claude SDK markers; Cursor Agent CLI `subagentInfo` / `approvalMode=auto-review`; OpenClaw never skipped; others false until markers exist). Prevents the synthesis feedback loop. Applies at **both** ingest and synthesis. See [multi-agent-setup.md](multi-agent-setup.md#what-automated-headless-means) |
| `filters` | `exclude_temp_cwd` | bool | false | Opt-in: skip sessions whose `cwd` is a throwaway temp dir (`/tmp`, `/var/folders`, …). Off by default — a git worktree under `/tmp` is often real work |
| `redaction` | `real_username` | string | `$USER` | Your OS username (auto-detected if empty) |
| `redaction` | `replacement_username` | string | `USER` | Replacement in path redaction |
| `redaction` | `extra_patterns` | list | [3 regexes] | Additional Python regex patterns to redact |
| `truncation` | `tool_result_chars` | int | 500 | Max chars per tool result |
| `truncation` | `bash_stdout_lines` | int | 5 | Max lines from bash output |
| `truncation` | `write_content_preview_lines` | int | 5 | Max lines from Write tool preview |
| `truncation` | `user_prompt_chars` | int | 4000 | Max chars per user prompt |
| `truncation` | `assistant_text_chars` | int | 8000 | Max chars of assistant text |
| root | `drop_thinking_blocks` | bool | true | Drop `<thinking>` blocks from output |
| `adapters` | per-adapter | object | varies | Override adapter-specific settings (`roots`, `enabled`, optional `since`, plus adapter-specific fields) |
| `adapters.<name>` | `since` | string | unset (inherit) | Per-source lookback: `YYYY-MM-DD` override, or `"all"` for no date gate on that source. Omit the key to inherit `filters.since`. See [Sync lookback](#sync-lookback) |
| `schedule` | `build` | enum | `"on-sync"` | When `/wiki-build` runs. `on-sync` / `daily` / `weekly` / `manual` / `never`. |
| `schedule` | `lint` | enum | `"manual"` | When `/wiki-lint` runs. Same enum. |
| `synthesis` | `backend` | enum | `"dummy"` | Which synthesizer: `"dummy"` / `"ollama"` / `"claude"` (synchronous `claude -p` CLI). Unknown values warn and fall back to `"dummy"`. The old `"agent"` / agent-delegate backend was removed in v1.4.0. See [configuration.md § Synthesis backend](configuration.md#synthesis-backend). |
| `synthesis` | `claude_model` | string | `"sonnet"` | Model alias for the `claude` backend |
| `synthesis` | `claude_path` | string | `""` | Optional path to the `claude` binary |
| `synthesis` | `claude_timeout` | int (s) | 180 | Per-page timeout for the `claude` backend. Separate from `synthesis.ollama.timeout` — before v1.4.1 both backends shared one `timeout` key, so the Ollama default silently capped claude pages at 60s |
| `synthesis` | `claude_effort` | enum | unset | `--effort` for the `claude` backend (`low`/`medium`/`high`/`xhigh`/`max`). Extended thinking is billed as output at ~5x input; on Haiku it was 5,753 output tokens/page at the default vs 1,609 at `low`. Set `low` on small models |
| `synthesis` | `overview_model` | string | `"haiku"` | Model for the landing-page overview call in `build --synthesize`. Prose-from-JSON, so the small model is the default. See [reference/synthesis-cost.md](reference/synthesis-cost.md) |
| `synthesis` | `concurrency` | int | 2 | How many source pages `synth` synthesizes at once (range 1–16; `1` is strictly sequential). Bounds concurrent backend calls — for the `claude` backend that is concurrent subprocesses, which is why the ceiling exists. Unusable or out-of-range values warn and fall back to the default (out-of-range clamps to 16); a missing key is silent. `llmwiki synth --concurrency N` overrides it for one run |
| `synthesis` | `claude_lean` | bool | true | Strip agent scaffolding (tool schemas, MCP servers, skills, `CLAUDE.md`, agent system prompt) from each `claude` call — ~9x cheaper per page, measured. Only an explicit `false` opts out. See [reference/synthesis-cost.md](reference/synthesis-cost.md) |
| `synthesis.ollama` | `model` | string | `"llama3.1:8b"` | Ollama model name (pull via `ollama pull`). This nested block is canonical; the legacy flat `synthesis.model` / `timeout` / … still work but share a namespace with the other backends |
| `synthesis.ollama` | `base_url` | string | `"http://127.0.0.1:11434"` | Ollama HTTP endpoint |
| `synthesis.ollama` | `timeout` | int (s) | 60 | Per-request timeout |
| `synthesis.ollama` | `max_retries` | int | 3 | Exponential-backoff retry count on 5xx / timeout |
| `meeting` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `meeting` | `source_dirs` | list | `["~/Meetings"]` | Directories to scan |
| `meeting` | `extensions` | list | `[".vtt", ".srt"]` | File extensions to consider |
| `jira` | `enabled` | bool | false | Opt-in; non-AI adapter |
| `jira` | `server` | string | — | Jira Cloud/Server URL |
| `jira` | `email` | string | — | Account email |
| `jira` | `api_token` | string | `""` | Prefer `api_token_env` + `.env` |
| `jira` | `jql` | string | sensible default | Query for tickets to sync |
| `jira` | `max_results` | int | 50 | Pagination cap |
| `chatgpt` | `enabled` | bool | false | Opt-in; requires explicit `conversations_json` |
| `chatgpt` | `conversations_json` | string | — | Path to export file |
| `web_clipper` | `enabled` | bool | false | Obsidian Web Clipper intake path |
| `web_clipper` | `watch_dir` | string | `"raw/web"` | Directory to watch |
| `web_clipper` | `extensions` | list | `[".md"]` | File extensions to pick up |
| `web_clipper` | `auto_queue` | bool | true | Auto-enqueue into unified `llmwiki-state.json` queue |
| `site` | `github_repo` | string | `""` | Optional `owner/name` for CHANGELOG / edit-on-GitHub / source-code links in compiled docs. Empty = detect from `git remote get-url origin`, else `Pratiyush/llm-wiki` |

## Vault file (`llmwiki.json`)

`<vault-root>/llmwiki.json` holds the settings that belong to **the wiki itself** rather than to this install. It sits at the vault root beside `wiki/`, `raw/` and the vault's `llmwiki-state.json`, and it is meant to be committed: copying, sharing, or publishing the vault carries it along. The example wiki shipped with the project has one — [`demo/llmwiki.json`](../demo/llmwiki.json).

Two similarly-named JSON files, so keep them apart:

| | `config.json` | `llmwiki.json` |
|---|---|---|
| Lives at | the repo / install root | the vault root, beside `wiki/` |
| Describes | how *this install* behaves — adapters, redaction, truncation, synthesis backend | what is true of *this wiki* — today, the quality checks that cannot apply to it |
| Committed? | no, it is gitignored | yes, that is the point of it |
| Travels with a copied or published vault? | no | yes |
| Read by | `sync`, `synth`, `build`, … | `lint`, the `all` pipeline's lint stage, and the MCP `wiki_lint` tool |
| When missing | falls back to `examples/sessions_config.json` | the wiki declares nothing, and lint behaves exactly as it did before this file existed |

### `lint.disabled_rules`

Names the quality checks that do not apply to this wiki. A disabled rule is never constructed, never runs, and contributes no findings — and is named as skipped in every report, whether or not anything was found, so a short report can never be mistaken for a clean one. It is on/off only: a wiki cannot re-grade a finding's severity, and cannot switch a rule off for part of itself.

Two shapes are accepted. A bare list, when you do not want to record a reason:

```json
{
  "lint": {
    "disabled_rules": ["content_freshness"]
  }
}
```

Or an object mapping each rule to a written reason — preferred, because the reason is what you or a reviewer will read six months from now:

```json
{
  "lint": {
    "disabled_rules": {
      "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
    }
  }
}
```

Rule names are the ones the report prints as `## <rule>` headings; the full list is in [reference/cli.md](reference/cli.md#lint--run-17-wiki-quality-rules), and any run that rejects a name prints the valid ones.

Keep a reason to a sentence or two. It is printed **verbatim, on one line** of every report the wiki produces, so a paragraph-length reason wraps badly in a CI log.

### Worked example

Write the file at the vault root and run the check:

```bash
cat > /path/to/vault/llmwiki.json <<'JSON'
{
  "lint": {
    "disabled_rules": {
      "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
    }
  }
}
JSON

python3 -m llmwiki lint --vault /path/to/vault
```

The report names what it skipped, above the findings:

```
  scanned 3 pages
  2 issues: 1 errors, 1 warnings, 0 info
  skipped 1 of 17 rules (disabled in llmwiki.json):
    - content_freshness — This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages.

## index_sync (1)
  [error] index.md: page 'sources/demo-source.md' not listed in index.md

## link_integrity (1)
  [warning] entities/Widget.md: broken wikilink [[Gadget]]
```

`lint --json` carries the same declaration under `disabled_rules`, which is always present — empty when the wiki declares nothing — so a consumer can read it without probing for the key:

```json
{
  "summary": { "error": 1, "warning": 1 },
  "issues": [
    { "rule": "index_sync", "severity": "error", "page": "index.md", "message": "page 'sources/demo-source.md' not listed in index.md" },
    { "rule": "link_integrity", "severity": "warning", "page": "entities/Widget.md", "message": "broken wikilink [[Gadget]]" }
  ],
  "total_pages": 3,
  "disabled_rules": {
    "content_freshness": "This wiki is a committed snapshot, so this check measures elapsed calendar time rather than a defect in the pages."
  },
  "ran": ["frontmatter_completeness", "index_sync", "link_integrity", "orphan_detection"]
}
```

`ran` names the checks that actually produced the report, in registry order. `disabled_rules` covers only the narrowing the wiki declared; `--rules` (and the MCP tool's `rules` argument) narrows a run without declaring anything, so without `ran` a short report is indistinguishable from a full one.

### A declaration that cannot be honoured is an error, never a silent skip

| Situation | What happens |
|---|---|
| A name that is not a registered rule (a typo, or a rule since retired) | The run stops with **exit 2**, naming the file, the unrecognised entry, and every valid rule name |
| `llmwiki.json` that is not valid JSON, or whose top level is not a JSON object | **exit 2**, naming the file and the parse error |
| A `lint.disabled_rules` that is neither a list of names nor an object mapping names to reasons | **exit 2** |
| Every registered rule disabled | The report states that nothing was checked, instead of printing a clean summary |
| Every rule a narrowed run selected disabled | The same, counted against what the run would have used — `--rules content_freshness` on a wiki that disables it skipped 1 rule of 1, not 1 of 17 |

None of these fall back to "this wiki declares no opt-outs". A declaration nobody can read might be switching every check off, so reporting the wiki as clean would be a guess dressed up as a result — and a typo must never leave a check switched on that you believed you had switched off.

### Switching a check off hides real findings

This is not a noise filter. A disabled rule does not run, so anything it *would* have found is simply absent from the report — and the report will look shorter and healthier for it. Reserve the declaration for checks that **cannot apply** to a wiki, not for checks that are merely inconvenient.

`content_freshness` on a committed snapshot is the legitimate case, and the one the shipped example uses. That check asks whether a page has gone untouched for three months; on a frozen, published copy the answer is decided by the calendar rather than by anything wrong with the pages, so the check would redden on a date rather than on a defect. Where staleness is *real*, refreshing the content is the honest cure — switching the check off only removes the reminder that the content has aged.

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `LLMWIKI_CONFIG` | Override the config file path | `./config.json`, then `examples/sessions_config.json` |
| `COPILOT_HOME` | Override the Copilot CLI base directory | `~/.copilot` |

Vault content root is **`vault.default_path` in `config.json`**. The removed `LLMWIKI_ROOT` env var is no longer read.

## `.llmwikiignore`

Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync.

```
# Skip a whole project
confidential-client/*

# Skip anything before a date
*2025-11-*

# Skip a specific session
ai-newsletter/2026-04-04-*secret*

# Comments start with #
# Blank lines are ignored
```

## Per-adapter configuration

Each adapter can be configured in the `adapters` section of `config.json`. The key must match the adapter's registry name.

| Adapter | Config key | Default enablement | Configurable fields |
|---|---|---|---|
| Claude Code | `claude_code` | Auto when store present | `roots`, `enabled`, `since` |
| Codex CLI | `codex_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Copilot Chat | `copilot_chat` | Auto when store present | `roots`, `enabled`, `since` |
| Copilot CLI | `copilot_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Cursor IDE | `cursor_ide` | Bare sync when enabled / store present | `roots`, `enabled`, `since`, `global_db` |
| Cursor Agent CLI | `cursor_cli` | Auto when store present | `roots`, `enabled`, `since` |
| Gemini CLI | `gemini_cli` | Auto when store present | `roots`, `enabled`, `since` |
| OpenCode | `opencode` | Auto when store present | `roots`, `enabled`, `since` |
| OpenClaw | `openclaw` | Auto when store present | `roots`, `enabled`, `since` |
| ChatGPT | `chatgpt` | Opt-in (`enabled: true`) | `enabled`, `export_dirs`, `min_messages`, `since` |
| Obsidian | `obsidian` | Opt-in (`enabled: true`, notes intake) | `vault_paths`, `exclude_folders`, `min_content_chars`, `since` |
| Jira | `jira` | Opt-in (`enabled: true`) | `server`, `email`, `api_token` / `api_token_env`, `jql`, `max_results`, `since` |
| Meeting transcripts | `meeting` | Opt-in (`enabled: true`) | `source_dirs`, `extensions`, `since` |

Every adapter accepts optional `since` (`YYYY-MM-DD` or `"all"`) — see [Sync lookback](#sync-lookback). Bare `llmwiki sync` runs every ingest-ready coding-agent adapter whose store is present and not explicitly disabled. Notes/export intake needs `enabled: true` (#326). Run `llmwiki configure-sources` to probe paths, set lookbacks, and write settings. Support map: [multi-agent-setup.md](multi-agent-setup.md).

Example:

```json
{
  "filters": {
    "since": "2026-07-31"
  },
  "adapters": {
    "copilot_chat": {
      "roots": ["/custom/path/to/vscode/workspaceStorage"]
    },
    "openclaw": {
      "since": "all"
    }
  }
}
```
