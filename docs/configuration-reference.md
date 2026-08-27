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
| `--since` | `YYYY-MM-DD` | none | Only sessions on or after this date |
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

### Section reference

| Section | Key | Type | Default | Description |
|---|---|---|---|---|
| `filters` | `live_session_minutes` | int | 60 | Skip sessions younger than this (prevents reading mid-write) |
| `filters` | `include_projects` | list | [] | If non-empty, only sync matching project slugs |
| `filters` | `exclude_projects` | list | [] | Skip projects containing these substrings |
| `filters` | `drop_record_types` | list | [3 types] | JSONL record types to discard |
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
| `adapters` | per-adapter | object | varies | Override adapter-specific settings |
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

| Adapter | Config key | Core / contrib | Configurable fields |
|---|---|---|---|
| Claude Code | `claude_code` | **core** (bare `sync`) | `roots` |
| Codex CLI | `codex_cli` | **core** (bare `sync`) | `roots` |
| Copilot Chat | `copilot_chat` | contrib (`--adapter`) | `roots` |
| Copilot CLI | `copilot_cli` | contrib (`--adapter`) | `roots` |
| Cursor IDE | `cursor` | contrib (`--adapter`) | `roots` |
| Cursor Agent CLI | `cursor_cli` | contrib (`--adapter`) | `roots` |
| Gemini CLI | `gemini_cli` | contrib (`--adapter`) | `roots` |
| OpenCode | `opencode` | contrib (`--adapter`) | `roots` |
| OpenClaw (native store) | `openclaw` | contrib (`--adapter`) | `roots` |
| ChatGPT | `chatgpt` | contrib + `enabled: true` | `enabled`, `conversations_json` |
| Obsidian | `obsidian` | contrib + `enabled: true` (notes, not agent chats) | `vault_paths`, `exclude_folders`, `min_content_chars` |
| Jira | `jira` | contrib + `enabled: true` | `server`, `email`, `api_token` / `api_token_env`, `jql`, `max_results` |
| Meeting transcripts | `meeting` | contrib + `enabled: true` | `source_dirs`, `extensions` |

**Core** adapters run on a bare `llmwiki sync` when their store exists. **Contrib** AI adapters need `--adapter <name>` (or an explicit enable where documented) until [#182](https://github.com/AlexanderMakarov/llm-wiki/issues/182). Non-AI intake (Obsidian, Jira, Meeting, ChatGPT export) also needs `enabled: true` (#326). Support map + headless rules: [multi-agent-setup.md](multi-agent-setup.md).

Example:

```json
{
  "adapters": {
    "copilot_chat": {
      "roots": ["/custom/path/to/vscode/workspaceStorage"]
    }
  }
}
```
