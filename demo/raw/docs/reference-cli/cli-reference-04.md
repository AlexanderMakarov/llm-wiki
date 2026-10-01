---
title: "CLI reference (part 4/19: graph — build the knowledge graph)"
slug: cli-reference-04
project: reference-cli
type: source
tags: [wiki-add, raw-doc]
date: 2026-10-01
source: "docs/reference/cli.md"
content_sha256: 8c1258c0faddb3eb988de6c7870bdada2b983cd07f6b325b78b35e680759efeb
---

> Part 4 of 19 of **CLI reference** — graph — build the knowledge graph.

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
