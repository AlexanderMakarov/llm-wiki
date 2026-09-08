---
title: "CLI reference (part 4/15: graph — build the knowledge graph)"
slug: cli-reference-04
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-09-08
source: "docs/reference/cli.md"
content_sha256: 186543f38f0258ea703f9ef68071d930f7135ea481068df5e5b46346e0f33e99
---

> Part 4 of 15 of **CLI reference** — graph — build the knowledge graph.

## `graph` — build the knowledge graph

```bash
python3 -m llmwiki graph                              # builtin wikilink graph
python3 -m llmwiki graph --engine graphify             # AI-powered graph (requires graphifyy)
python3 -m llmwiki graph --format json
python3 -m llmwiki graph --format html
```

### Flags

| Flag | What |
|---|---|
| `--format {json,html,both}` | Output format(s). Default: `both`. |
| `--engine {builtin,graphify}` | Graph engine. `builtin` = stdlib wikilink graph. `graphify` = AI-powered with community detection, confidence-scored edges, god nodes. Requires `pip install graphifyy`. Default: `builtin`. |

**Builtin engine:** Emits `graph/graph.json` (nodes + edges) and/or `graph/graph.html` (vis-network interactive viewer) plus sibling `graph-viewer.js` and `vis-network.min.js`. The interactive trio is also auto-copied into `site/` on every `build`, so the graph works offline from the built static site without a CDN fetch.

**Graphify engine:** Runs the [Graphify](https://github.com/safishamsi/graphify) pipeline: tree-sitter AST extraction for code, semantic analysis for docs, Leiden community detection, god-node analysis. Outputs to `graphify-out/` (graph.json, graph.html, GRAPH_REPORT.md) and copies to `graph/` for build compatibility. Install: `pip install llm-wiki-plus[graph]` or `pip install graphifyy`.

---

## `lint` — run 17 wiki-quality rules

```bash
python3 -m llmwiki lint
python3 -m llmwiki lint --json
python3 -m llmwiki lint --fail-on-errors --fail-on-warnings
python3 -m llmwiki lint --rules link_integrity,orphan_detection
python3 -m llmwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `<content root>/wiki`. Wins over `--vault`; the vault settings file is then read from its parent. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. An unrecognised name exits 2 and lists the valid names. |
| `--min-refs N` | How many distinct `wiki/sources/` pages must name a `[[wikilink]]` target before an unresolved link to it is reported. Default: `3` — the candidate harvest's own threshold, so a target the harvest deliberately declined is not a finding. `--min-refs 1` reports every unresolved link, and is the lowest accepted value: `0` and negatives exit 2. |
| `--json` | JSON output: `summary`, `issues`, `total_pages`, `disabled_rules`, `ran` — the last naming the checks that produced the report, so a run narrowed by `--rules` cannot read as a full one. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |
| `--fail-on-warnings` | Exit 1 if any warning-severity issues. Stricter than `--fail-on-errors`; pass both to gate on either. |
| `--vault PATH` | Lint the wiki under this vault root, and read that vault's `llmwiki.json`. |

A wiki can switch off the rules that cannot apply to it, in a committed `<vault>/llmwiki.json` — every report then names each skipped rule and its recorded reason. See [configuration-reference.md § Vault file](../configuration-reference.md#vault-file-llmwikijson) for the file's shape and the caution that goes with it.

### Rules

17 structural rules (all deterministic — no LLM): `frontmatter_completeness`, `frontmatter_validity`, `link_integrity`, `orphan_detection`, `content_freshness`, `duplicate_detection`, `index_sync`, `contradiction_detection`, `claim_verification`, `summary_accuracy`, `stale_candidates`, `tags_topics_convention`, `stale_reference_detection`, `frontmatter_count_consistency`, `tools_consistency`, `stub_source_pages`, `provenance_integrity`.

`contradiction_detection`, `claim_verification`, and `summary_accuracy` used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks: non-filler `## Contradictions` sections, entity/concept claims without sources, and empty `summary:` frontmatter. Filler bodies like `None identified.`, `None detected.`, and multi-sentence `None identified. …` elaborations are not findings (unless the section also contains an *unnegated* affirmative conflict cue such as `Contradicts earlier…`). Cues that appear only inside negation (`does not conflict with prior…`, `no claims that conflict…`) stay filler (#86).

`orphan_detection` counts inbound `[[wikilinks]]` and catalog markdown links (`[title](path.md)` that resolve to a wiki page), so pages listed only from `index.md` are not orphans. `link_integrity` resolves targets case- and punctuation-insensitively (`[[LLM-Wiki]]` → `llm-wiki.md`) but does not do substring matching. It honours the candidate harvest's significance threshold (#150): a target named by **no** source page is always reported, a target named **fewer** than `--min-refs` times is a deliberate decline and is not, and a target named **at least** that often with no page of its own is a genuine gap and is.

`stub_source_pages` (#24) flags pages under `wiki/sources/` whose body is machine-generated filler — a pending sentinel (`<!-- llmwiki-pending: … -->`) or the dummy backend's `Auto-synthesized from session` body. Those sources still count as unsynthesized backlog; refill them with `llmwiki synth` on a real backend.

`provenance_integrity` (#122) emits an **error** for each broken downward hop on pages that already carry `sources:` and/or `source_file:` — missing source-summary pages or missing raw files. Pages without those fields are skipped. The message names the missing hop and points at `llmwiki trace`, `synth`, or `migrate broken-provenance` as appropriate; this rule only reports.

`stale_reference_detection` (#303 / #87) flags living pages (entities, concepts, …) whose dated claim about a target predates that target's `last_updated`. Pages under `wiki/sources/` and pages with frontmatter `type: source` are skipped — they are dated session records and cannot be "un-staled" without rewriting history.

### Expected output

```
  scanned 31 pages
  28 issues: 0 errors, 22 warnings, 6 info

## link_integrity (22)
  [warning] entities/GPT5.md: broken wikilink [[MultimodalModels]]
  ...
```

---
