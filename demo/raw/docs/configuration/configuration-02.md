---
title: "Configuration (part 2/2: CLI flags)"
slug: configuration-02
project: configuration
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/configuration.md"
content_sha256: 83084a996152be16bc5a9cca106ed2175024bb9c13f7b4f553956e83e5667975
---

> Part 2 of 2 of **Configuration** — CLI flags.

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
