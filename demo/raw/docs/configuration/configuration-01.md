---
title: "Configuration (part 1/3)"
slug: configuration-01
project: configuration
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration.md"
content_sha256: 94ac6cbdc09d142adb44b67fe4e8fb1afc2956a82b7438f5476618e4ec72f3d8
---

> Part 1 of 3 of **Configuration**.

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

    // Skip automated / headless agent launches (default on). Claude: SDK
    // entrypoint / promptSource; Cursor Agent CLI: subagentInfo or
    // approvalMode=auto-review; OpenClaw: never skipped. Applies at ingest
    // and synthesis. See docs/multi-agent-setup.md § automated.
    "exclude_headless": true,

    // Skip sessions whose cwd is a throwaway temp dir (/tmp, /var/folders,
    // …). Default OFF: a git worktree under /tmp is often real work, so we
    // don't silently drop it. Turn on only if your temp dirs hold nothing
    // but e2e/scratch junk.
    "exclude_temp_cwd": false

    // Optional shared sync lookback as absolute YYYY-MM-DD (#192).
    // Omit (default) = unlimited history. Per-adapter override:
    // adapters.<name>.since as YYYY-MM-DD, or "all" for no date gate.
    // CLI --since overrides both for one run. See configuration-reference.md.
    // "since": "2026-07-31"
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

  // Per-adapter config. Optional since: YYYY-MM-DD override or "all" (no date gate).
  "adapters": {
    "obsidian": {
      "vault_paths": ["~/Documents/Obsidian Vault"],
      "exclude_folders": [".obsidian", "Templates", "_templates", ".trash"],
      "min_content_chars": 50
    }
  }
}
```
