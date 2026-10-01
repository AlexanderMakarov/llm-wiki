---
title: "CLI reference (part 15/19: search — literal term or phrase search (#197))"
slug: cli-reference-15
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 15 of 19 of **CLI reference** — search — literal term or phrase search (#197).

## `search` — literal term or phrase search (#197)

Pre-AI-era literal search: score-weighted matching of the characters you type, found anywhere including inside longer words — for example `cat` matches `concatenate`. No stemming, no spelling correction, no meaning-based matching. Same engine agents use via MCP `wiki_search`.

This is not `query`. `search` ranks pages by literal character overlap; `query` walks the knowledge graph in natural language via Graphify (`pip install llm-wiki-plus[graph]`).

**Result text.** Both modes use the same centred snippet window (~400 characters around the first hit via `extract_snippet`). Term mode still returns matching *lines* (each line previewed that way); phrase mode returns one *page* snippet per hit.
```bash
python3 -m llmwiki search RAG --vault /path/to/vault
python3 -m llmwiki search "reinforcement learning" --mode phrase --format json
python3 -m llmwiki search --terms-file terms.txt --mode term
python3 -m llmwiki search --terms-file phrases.txt --mode phrase
python3 -m llmwiki search --terms-file - --mode phrase < phrases.txt
```

### Positional

| Arg | What |
|---|---|
| `QUERY` | Single term (default `--mode term`) or phrase (`--mode phrase`). Omit when using `--terms-file`. |

### Flags

| Flag | What |
|---|---|
| `--mode {term,phrase}` | `term` → match mode (token-style); `phrase` → extract mode (multi-word / whole-phrase bonus). Default: `term`. |
| `--terms-file PATH` | Bulk input, one term or phrase per line; `#` comments and blanks skipped; `-` reads stdin. Use with `--mode term` for a term list or `--mode phrase` for a phrase list. |
| `--vault PATH` | Search this vault root read-only. Without it, uses `config.json` `vault.default_path` or the repo demo content. |
| `--include-raw` | Also scan `raw/sessions/` (term mode). |
| `--kind K` | Frontmatter `type` filter (term mode). |
| `--max-pages N` | Result cap in phrase mode. Default: `5`. |
| `--format {text,json}` | Text list or JSON payload matching the MCP tool shapes. Default: `text`. |

Bulk runs group hits per entry and state which entries returned nothing. Always exits `0` on a successful search (including zero hits). Does not interpret expectations — use lint findability rules (`page_findability`, `title_ambiguity`, `search_consistency`) for pass/fail. Read-only: never modifies the vault.

---

## `query` — natural-language knowledge-graph walk (Graphify)

```bash
python3 -m llmwiki query "what projects am I working on"
python3 -m llmwiki query "Flutter mobile" --depth 2 --budget 1000
```

Asks a natural-language question over the Graphify knowledge graph. Distinct from `search`, which does literal term/phrase matching with no semantics.

### Flags

| Flag | What |
|---|---|
| `--depth N` | BFS traversal depth. Default: `3`. |
| `--budget N` | Max output tokens. Default: `2000`. |

Requires Graphify (`pip install llm-wiki-plus[graph]`). Run `llmwiki graph` first to build the graph.

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

Use `trace` to inspect broken hops; repair them by hand or with `synth` / `migrate broken-provenance` as the lint message suggests. Guided repair under `doctor` (#110) is roadmap-only.

---
