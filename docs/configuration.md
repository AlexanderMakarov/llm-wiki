# Configuration

Every tuning knob in llmwiki, explained.

## Config file

Copy the default config and edit it:

```bash
cp examples/sessions_config.json config.json
```

`config.json` is gitignored so your settings stay local. The converter auto-loads it if present.

Minimal config:

```json
{
  "redaction": {
    "real_username": "your-unix-username",
    "replacement_username": "USER"
  }
}
```

> Replace `your-unix-username` with the output of `whoami`. The converter uses it to scrub paths like `/Users/<name>/…` or `/home/<name>/…` before writing to `raw/`.

## Full schema

```jsonc
{
  "filters": {
    // Skip sessions with a record younger than this many minutes.
    // Prevents the converter from reading a .jsonl mid-write.
    "live_session_minutes": 60,

    // If non-empty, only convert projects whose slug matches one of these.
    "include_projects": [],

    // Skip projects whose slug contains one of these substrings.
    "exclude_projects": [],

    // Record types to drop entirely (noise / hook progress / queue ops)
    "drop_record_types": [
      "queue-operation",
      "file-history-snapshot",
      "progress"
    ],

    // Skip headless `claude -p` / Agent-SDK sessions (entrypoint=sdk-cli
    // or promptSource=sdk). These are not coding sessions worth a wiki
    // page, and ingesting them creates a synthesis feedback loop when the
    // synthesizer itself shells out to `claude -p`.
    "exclude_headless": true,

    // Skip sessions whose cwd is a throwaway temp dir (/tmp, /var/folders,
    // …). Default OFF: a git worktree under /tmp is often real work, so we
    // don't silently drop it. Turn on only if your temp dirs hold nothing
    // but e2e/scratch junk.
    "exclude_temp_cwd": false
  },

  "redaction": {
    // Your OS username. Paths like /Users/<you>/ become /Users/USER/.
    // Auto-detected from $USER if left empty.
    "real_username": "",

    // What to replace real_username with.
    "replacement_username": "USER",

    // Additional regexes to redact (Python re syntax).
    // Anything matching → "<REDACTED>".
    "extra_patterns": [
      "(?i)(api[_-]?key|secret|token|bearer|password)[\"'\\s:=]+[\\w\\-\\.]{8,}",
      "sk-[A-Za-z0-9]{20,}",
      "[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\\.[a-zA-Z0-9-.]+"
    ]
  },

  "truncation": {
    // Max chars per tool result before truncation.
    "tool_result_chars": 500,

    // Max lines from a Bash stdout before truncation.
    "bash_stdout_lines": 5,

    // Max lines from a Write tool content preview.
    "write_content_preview_lines": 5,

    // Max chars per user prompt.
    "user_prompt_chars": 4000,

    // Max chars of assistant text rendered in the markdown body.
    "assistant_text_chars": 8000
  },

  // Drop <thinking> blocks from assistant messages entirely.
  // These are verbose and often redundant with the visible response.
  "drop_thinking_blocks": true,

  // Per-adapter config
  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"],
      "exclude_folders": [".obsidian", "Templates", "_templates", ".trash"],
      "min_content_chars": 50
    }
  }
}
```

## Synthesis backend

`llmwiki synth` turns each raw session/document into a
`wiki/sources/` page. Which LLM (if any) writes those pages is picked by
`synthesis.backend` in `config.json`:

```jsonc
{
  "synthesis": {
    // "dummy" (default) | "ollama" | "claude"
    "backend": "claude",
    "claude_model": "sonnet"
  }
}
```

| Backend | What it does | Needs |
|---|---|---|
| `dummy` | Canned stub page: metadata summary, one `[[ProjectEntity]]` link, plain-text `## Raw Mentions`. For previews/tests. | nothing |
| `ollama` | Local LLM over the Ollama HTTP API. Configure `synthesis.ollama.{model,base_url,timeout,max_retries}`. | running `ollama serve` |
| `claude` | Synchronous `claude -p` CLI calls (#16). Optional `claude_path` / `claude_model` (default `sonnet`) / `timeout` / `claude_lean`. Works from a plain terminal and nested inside agent sessions. | `claude` on `$PATH` (or `claude_path`) |

Calls run in **lean mode** by default: tool schemas, MCP servers, skills, `CLAUDE.md`, and the agent system prompt are stripped from each invocation, since a synthesis call only reads stdout and can't use any of them. That is ~9x cheaper per page, measured — see [reference/synthesis-cost.md](reference/synthesis-cost.md) for the numbers and for why `claude_model` defaults to `sonnet` rather than a cheaper model. Set `"claude_lean": false` to opt out.

The old `agent` / `agent_delegate` backend (pending-prompt files + `--list-pending` / `--complete`) was removed in v1.4.0 — use `claude` instead.

Sanity-check what's active and what a run would cost:

```bash
llmwiki synth --check      # prints the resolved backend + availability
llmwiki synth --estimate   # cached-vs-fresh token + dollar estimate (+ candidate backlog)
llmwiki synth --sessions-only   # pending sessions only (skip docs)
llmwiki synth --docs-only       # pending docs only (skip sessions)
```

**Synthesis is incremental.** `<vault>/llmwiki-state.json` (`synth.files`)
records an mtime per raw file; a nightly `sync`/`synthesize` only processes
files that are new or changed since the last run — the daily LLM bill is
proportional to new content, not to corpus size. `--force` re-runs
everything (use after switching backends, e.g. to replace dummy-stub
pages with real ones — pages with only stub links produce a topic
graph with no edges).

**Downgrade protection:** `dummy` is the resolved default when
`synthesis.backend` is unset (or a typo — unknown values warn and fall
back), so a `--force` run in that state used to overwrite every real
page with link-free stubs and silently empty the knowledge graph. The
pipeline now refuses that downgrade: stub output is never written over
a real page, even under `--force` — such pages are reported as
`protected` in the run summary. To deliberately re-synthesize a real
page, delete it first. (An unavailable backend does *not* fall back —
the run aborts with an error.)

## Environment variables

| Variable | What it does |
|---|---|
| `LLMWIKI_CONFIG` | Override the config file path. Defaults to `./config.json` then `examples/sessions_config.json`. |

Vault content root is **`vault.default_path` in `config.json`** (not an env var). The removed `LLMWIKI_ROOT` env var is no longer read.

## CLI flags

### `llmwiki sync`

```bash
python3 -m llmwiki sync [options]

--adapter <name...>       Only run the named adapter(s); default: all available
--since YYYY-MM-DD        Skip sessions with a last record older than this
--project <substring>     Only sync projects whose slug contains this substring
--include-current         Don't skip live (<60 min) sessions
--force                   Ignore the state file; reconvert everything
--fail-on-errors          Exit 1 if any file fails to convert
--vault PATH              Write into an external vault (also sets active state file)
--status                  Show last-sync + counters + quarantine (no sync)
```

Per-file conversion errors do not fail the run by default: each one is
counted in the summary, recorded in `llmwiki-state.json` quarantine
entries, and visible via `llmwiki sync --status`, while the rest of the
corpus still converts. Pass `--fail-on-errors` for a hard gate (CI,
scripted pipelines that must not proceed past a partial sync).

There is **no** `sync --dry-run` — use `add --dry-run` for document intake
previews, or inspect with `sync --status` / `synth --estimate`.

### `llmwiki build`

```bash
python3 -m llmwiki build [options]

--out <dir>               Output directory; default: ./site
--synthesize              Call the `claude` CLI once to generate an Overview
--claude <path>           Path to the claude binary; default: /usr/local/bin/claude
```

### `llmwiki serve`

```bash
python3 -m llmwiki serve [options]

--dir <dir>               Directory to serve; default: ./site
--port N                  Port number; default: 8765
--host H                  Host to bind; default: 127.0.0.1 (localhost only)
--open                    Open the browser after starting
```

### `llmwiki init`

No options. Scaffolds `raw/`, `wiki/`, `site/` and seeds `wiki/index.md`, `wiki/log.md`, `wiki/overview.md`.

### `llmwiki adapters`

No options. Lists every registered adapter and whether its session store is present on the current machine.

## `.llmwikiignore`

Gitignore-style file at the repo root. One pattern per line. Sessions matching any pattern are skipped during sync.

Example:

```
# Skip a whole project
confidential-client/*

# Skip anything before a date
*2025-11-*

# Skip a specific session
ai-newsletter/2026-04-04-*secret*
```

## Adapter configuration

### Claude Code

Default session store: `~/.claude/projects/`

Override via the adapter config block (above).

### Obsidian

Default vault locations checked:

1. `~/Documents/Obsidian Vault`
2. `~/Obsidian`

Override in `config.json`:

```jsonc
{
  "adapters": {
    "obsidian": {
      "vault_paths": [
        "~/Documents/Obsidian Vault",
        "~/work/second-vault"
      ],
      "exclude_folders": [".obsidian", "Templates"],
      "min_content_chars": 100
    }
  }
}
```

Files smaller than `min_content_chars` are skipped (mostly empty notes).

### Codex CLI

**v0.1 stub.** The adapter imports and registers but does not yet parse records. Configuration will land in v0.2.

## Changing the theme

Theme colours live in `llmwiki/build.py` inside the `CSS` string constant, under the `:root` block. The main tokens:

```css
--accent: #7C3AED;     /* primary accent (purple) */
--accent-light: #a78bfa;
--accent-bg: #f5f3ff;
```

Change these and rebuild. The dark-mode variants auto-derive unless you override them too.
