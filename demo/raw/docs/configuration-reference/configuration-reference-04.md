---
title: "Configuration Reference (part 4/8: Config file (config.json))"
slug: configuration-reference-04
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 4 of 8 of **Configuration Reference** — Config file (config.json).

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
