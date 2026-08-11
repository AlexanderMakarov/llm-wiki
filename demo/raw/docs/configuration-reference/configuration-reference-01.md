---
title: "Configuration Reference (part 1/4)"
slug: configuration-reference-01
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/configuration-reference.md"
content_sha256: 7cc907826ce49fb66b474eaa7bcf6d0d7266d2ba89c92ce2acdfe2a0f97b84f5
---

> Part 1 of 4 of **Configuration Reference**.

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

### `llmwiki serve`

Start a local HTTP server for the built site.

```bash
python3 -m llmwiki serve [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--dir` | `path` | `./site` | Directory to serve |
| `--port` | `int` | `8765` | Port number |
| `--host` | `string` | `127.0.0.1` | Host to bind (use `0.0.0.0` to expose to network) |
| `--open` | flag | off | Open browser after starting |

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

Run the full pipeline: `[sync?]` → `[synthesize?]` → build → graph → lint. AI-consumable exports are written by `build`, not a separate step.

```bash
python3 -m llmwiki all [options]
```

| Flag | Type | Default | Description |
|---|---|---|---|
| `--out` | `path` | `./site` | Output directory |
| `--with-sync` | flag | off | Run `sync --no-auto-build` before synthesize/build |
| `--with-synth` | flag | off | Run `synthesize` before build |
| `--synth-force` | flag | off | With `--with-synth`: pass `--force` to re-synthesize all sessions |
| `--search-mode` | `auto/tree/flat` | `auto` | Forwarded to build |
| `--graph-engine` | `builtin/graphify` | `graphify` | Forwarded to graph |
| `--skip-graph` | flag | off | Skip the graph step |
| `--strict` | flag | off | Exit 2 on any lint error or warning (CI gate) |
| `--fail-fast` | flag | off | Stop at first non-zero step |

### `llmwiki version`

Print the current version.

```bash
python3 -m llmwiki version
```
