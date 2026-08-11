---
title: "Configuration Reference (part 2/4: Config file (config.json))"
slug: configuration-reference-02
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/configuration-reference.md"
content_sha256: 7cc907826ce49fb66b474eaa7bcf6d0d7266d2ba89c92ce2acdfe2a0f97b84f5
---

> Part 2 of 4 of **Configuration Reference** — Config file (config.json).

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
