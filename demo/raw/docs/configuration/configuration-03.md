---
title: "Configuration (part 3/3: CLI flags)"
slug: configuration-03
project: configuration
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-28
source: "docs/configuration.md"
content_sha256: c44e78c6153be900dabea562bac4d92c695a124f5e266068784df84392622af5
---

> Part 3 of 3 of **Configuration** — CLI flags.

## CLI flags

### `llmwiki sync`

```bash
python3 -m llmwiki sync [options]

--adapter <name...>       Only run the named adapter(s); default: all available
--since YYYY-MM-DD        One-run lookback (overrides filters.since / adapters.*.since)
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

Durable lookback (optional): set `filters.since` to an absolute `YYYY-MM-DD` in `config.json`, or `adapters.<name>.since` to a date / `"all"` (no date gate for that source). Unset = unlimited history. `llmwiki configure-sources` asks the shared date first (default today−30) and shows Sessions · Earliest · In last 30 days per source before Enable. See [configuration-reference.md — Sync lookback](configuration-reference.md#sync-lookback).

### `llmwiki build`

```bash
python3 -m llmwiki build [options]

--out <dir>               Output directory; default: ./site
--synthesize              Call the `claude` CLI once to generate an Overview
--claude <path>           Path to the claude binary; default: /usr/local/bin/claude
--local-root <path>       Value shown in place of a session's stored home directory;
                          default: this machine's home directory
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

**Production** core adapter. Default roots: `~/.codex/sessions` and `~/.codex/projects`. Override with `adapters.codex_cli.roots`. Included on a bare `llmwiki sync` when a root exists. Full detail: [adapters/codex-cli.md](adapters/codex-cli.md).

### Which agents + what “automated” means

Support map, core vs contrib (`--adapter` opt-in), Cursor Agent CLI vs IDE, and per-source headless rules: **[multi-agent-setup.md](multi-agent-setup.md)**.

## Changing the theme

Theme colours live in `llmwiki/build.py` inside the `CSS` string constant, under the `:root` block. The main tokens:

```css
--accent: #7C3AED;     /* primary accent (purple) */
--accent-light: #a78bfa;
--accent-bg: #f5f3ff;
```

Change these and rebuild. The dark-mode variants auto-derive unless you override them too.

## MCP tool timeouts

Long-running MCP tools (`wiki_add`, `wiki_sync`) default to a **120-second** wall-clock budget. Override per tool under `mcp.tool_timeouts` in `config.json`:

```json
{
  "mcp": {
    "tool_timeouts": {
      "wiki_add": 120,
      "wiki_sync": 120
    }
  }
}
```

See [reference/mcp.md](reference/mcp.md#tool-timeouts) and the [configuration reference](configuration-reference.md) table rows.
