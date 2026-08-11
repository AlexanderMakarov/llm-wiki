---
title: "CLI reference (part 7/8: migrate-page-kinds — retype pages off the removed question/comparison kinds (#109))"
slug: cli-reference-07
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 7 of 8 of **CLI reference** — migrate-page-kinds — retype pages off the removed question/comparison kinds (#109).

## `migrate-page-kinds` — retype pages off the removed question/comparison kinds (#109)

`llmwiki/schema.py` lists five knowledge kinds — `source`, `entity`, `concept`, `project`, `synthesis`. A hand-written page declaring `type: question` or `type: comparison` is a `frontmatter_validity` **error**, and this migration clears it: each such page is retyped to `concept` and moved into `wiki/concepts/` **keeping its filename**, then `wiki/questions/` and `wiki/comparisons/` lose their `_context.md` and are pruned once empty.

Inbound links are left alone on purpose. `[[wikilinks]]` resolve by filename, never by folder, so a page that keeps its name keeps every inbound link and no referring page needs editing.

Two safety rules: a page whose filename is already taken in `wiki/concepts/` is retyped where it stands and reported as a collision rather than overwriting anything, and a removed folder still holding other content is left in place and reported rather than deleted. A vault with no removed-kind page prints `nothing to migrate` and exits 0 without writing.

Implementation: `llmwiki/migrate_page_kinds.py` — in the package rather than under `scripts/`, so it runs from a pip or Homebrew install with no checkout. After migrating, rebuild so `site/` picks up the new locations: `llmwiki build --vault PATH`.

```bash
python3 -m llmwiki migrate-page-kinds --vault /path/to/vault --dry-run
python3 -m llmwiki migrate-page-kinds --vault /path/to/vault
python3 -m llmwiki lint --vault /path/to/vault --rules frontmatter_validity
```

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | **Required.** Vault root containing `wiki/`. |
| `--dry-run` | Report what would change; write nothing. |

Idempotent: a second run finds nothing to migrate. On a run that changed something the command reconciles `wiki/index.md` and appends `## [YYYY-MM-DD] migrate | page kinds` to `wiki/log.md`.

---

## `consolidate-topics` — dedupe + describe topics (#54)

One-time LLM pass over the topic list (not the sessions) that merges duplicate topic spellings (`LLM-Wiki` / `LLMWiki` / `llm wiki`) into one canonical node and writes short descriptions, caching the result in `.llmwiki-topics.json` for `llmwiki graph` / `llmwiki build`.

```bash
python3 -m llmwiki consolidate-topics                # emit the LLM prompt
python3 -m llmwiki consolidate-topics --complete reply.json
python3 -m llmwiki consolidate-topics --complete -    # read the reply from stdin
```

### Flags

| Flag | What |
|---|---|
| `--complete PATH` | Ingest the LLM's JSON reply (file path, or `-` for stdin) and write the topic cache. Without this flag, the prompt is printed instead. |
| `--vault PATH` | Read/write the topic cache inside the given vault instead of the repo. |

Re-run after large ingest batches so near-duplicate topic spellings don't fragment the knowledge graph.

---

## `version` — print the installed version

```bash
python3 -m llmwiki version
python3 -m llmwiki --version
```

Both print `llmwiki <version>`.

---

## `query` — search the knowledge graph

```bash
python3 -m llmwiki query "what projects is Pratiyush working on"
python3 -m llmwiki query "Flutter mobile" --depth 2 --budget 1000
```

### Flags

| Flag | What |
|---|---|
| `--depth N` | BFS traversal depth. Default: `3`. |
| `--budget N` | Max output tokens. Default: `2000`. |

Requires Graphify (`pip install llm-notebook[graph]`). Run `llmwiki graph` first to build the graph.

---

## `trace` — print downward provenance to raw transcripts (#122)

Walk a wiki page’s encoded chain to its source summaries and raw files. Uses only frontmatter (`sources:`, `source_file:`) — no body excerpts. Missing hops are marked; the walk still succeeds.

```bash
python3 -m llmwiki trace Demo --vault /path/to/vault
python3 -m llmwiki trace wiki/entities/Demo.md --vault /path/to/vault
```

### Positional

| Arg | What |
|---|---|
| `PAGE` | Vault-relative wiki path (`wiki/entities/Foo.md`) or a resolvable page name/stem under `wiki/`. |

### Flags

| Flag | What |
|---|---|
| `--vault PATH` | Trace under this vault (reads `wiki/` + `raw/`). Without it, uses `config.json` `vault.default_path` or the repo demo content. |

### Expected output

One line per hop: `role`, title, location; missing hops append ` (missing)`. A page with no provenance prints the page line plus `(no further provenance)`.

```
page    Demo  wiki/entities/Demo.md
source  Kickoff session  wiki/sources/kickoff.md
raw     Kickoff transcript  raw/sessions/2026-01-01T12-00-demo-kickoff.md
```

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Walk completed (including chains with missing hops). |
| `1` | Starting page could not be resolved (or locator unsafe / empty). |
| `2` | Configured `--vault` / default vault path is unusable. |

Guided repair of broken hops will live under `doctor` (#110); this command only prints the chain.

---

## `all` — run the full pipeline

Convenience entry point that runs `[sync?]` → `[synthesize?]` → `build` → `graph` → `lint` in order. AI-consumable exports (`llms.txt`, `sitemap.xml`, etc.) are written by `build`, not a separate step. This is the one command to run after agent sessions land to produce a CI-ready site.

```bash
python3 -m llmwiki all
python3 -m llmwiki all --with-sync              # convert sessions first
python3 -m llmwiki all --with-synth             # synthesize wiki/sources/ before build
python3 -m llmwiki all --with-sync --with-synth # full refresh from agent stores
python3 -m llmwiki all --graph-engine builtin   # skip optional graphify
python3 -m llmwiki all --skip-graph --strict    # fail CI on any lint issue
```

### Flags

| Flag | What |
|---|---|
| `--out DIR` | Output dir for `build`. Default: `site/`. |
| `--search-mode {auto,tree,flat}` | Forwarded to `build`. Default: `auto`. |
| `--graph-engine {builtin,graphify}` | Forwarded to `graph`. Default: `graphify`. |
| `--skip-graph` | Skip the graph step entirely (useful when graphify is not installed). |
| `--fail-fast` | Stop at the first non-zero step. Default: continue, report the worst exit code. |
| `--strict` | Exit `2` if `lint` reports any errors/warnings. |
| `--with-sync` | Run `sync --no-auto-build` before synthesize/build (convert agent sessions first). |
| `--with-synth` | Run `synthesize` before build (fills `wiki/sources/` from `raw/`; may invoke an LLM — default off for cost discipline, #383). |
| `--synth-force` | With `--with-synth`: pass `--force` to synthesize (re-synthesize all sessions). |
| `--vault PATH` | Run every step against this vault instead of the repo. |

Exit codes:

- `0` — every step succeeded.
- non-zero — forwarded from the first (or worst) failing step.
- `2` — `--strict` and lint reported issues.

---
