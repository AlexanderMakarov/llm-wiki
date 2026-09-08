---
title: "Configuration Reference (part 2/8: CLI subcommands)"
slug: configuration-reference-02
project: configuration-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/configuration-reference.md"
content_sha256: 037667c9a64c03e7e116aad5677fbb0f9c2a8a529294787eae7fbe5f06d78089
---

> Part 2 of 8 of **Configuration Reference** — CLI subcommands.

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
