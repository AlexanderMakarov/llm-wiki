---
title: "CLI reference (part 3/8: adapters — list every adapter + its status)"
slug: cli-reference-03
project: cli-reference
type: source
tags: [wiki-add, raw-doc]
date: 2026-08-10
source: "docs/reference/cli.md"
content_sha256: c2fa4d275fde9cc72d3178206373fc46e586aec2e3b709417d7081afdcd15f4b
---

> Part 3 of 8 of **CLI reference** — adapters — list every adapter + its status.

## `adapters` — list every adapter + its status

```bash
python3 -m llmwiki adapters
```

**Flags:** none.

**Expected output:**

```
Registered adapters:
  name              default   configured    description
  ----------------  --------  ------------  ----------------------------------------
  chatgpt           no        -             ChatGPT — parses conversations.json …
  claude_code       yes       ✓            Claude Code — reads ~/.claude/projects/
  codex_cli         no        ✓            Codex CLI — reads ~/.codex/sessions/
  copilot           no        -             GitHub Copilot — reads VS Code …
  cursor            no        -             Cursor — reads VS Code workspaceStorage
  gemini_cli        no        -             Gemini CLI — reads ~/.gemini/
  jira              no        -             Jira — reads via REST API
  meeting           no        -             Meeting transcripts (VTT/SRT)
  obsidian          no        -             Obsidian — reads a vault
  opencode          no        -             OpenCode / OpenClaw sessions
  web_clipper       no        -             Obsidian Web Clipper intake
```

Columns: **default** (runs when you don't pass `--adapter`), **configured** (adapter sees a valid session store on this machine).

---

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

**Graphify engine:** Runs the [Graphify](https://github.com/safishamsi/graphify) pipeline: tree-sitter AST extraction for code, semantic analysis for docs, Leiden community detection, god-node analysis. Outputs to `graphify-out/` (graph.json, graph.html, GRAPH_REPORT.md) and copies to `graph/` for build compatibility. Install: `pip install llm-notebook[graph]` or `pip install graphifyy`.

---

## `lint` — run 17 wiki-quality rules

```bash
python3 -m llmwiki lint
python3 -m llmwiki lint --json
python3 -m llmwiki lint --fail-on-errors
python3 -m llmwiki lint --rules link_integrity,orphan_detection
python3 -m llmwiki lint --wiki-dir ~/another-wiki
```

### Flags

| Flag | What |
|---|---|
| `--wiki-dir PATH` | Wiki dir. Default: `./wiki`. |
| `--rules NAMES` | Comma-separated rule names. Default: all applicable. |
| `--json` | JSON output. |
| `--fail-on-errors` | Exit 1 if any error-severity issues. |

### Rules

17 structural rules (all deterministic — no LLM): `frontmatter_completeness`, `frontmatter_validity`, `link_integrity`, `orphan_detection`, `content_freshness`, `duplicate_detection`, `index_sync`, `contradiction_detection`, `claim_verification`, `summary_accuracy`, `stale_candidates`, `tags_topics_convention`, `stale_reference_detection`, `frontmatter_count_consistency`, `tools_consistency`, `stub_source_pages`, `provenance_integrity`.

`contradiction_detection`, `claim_verification`, and `summary_accuracy` used to hide behind `--include-llm` and advertise an LLM callback that was never wired. As of #72 they always run as structural checks: non-filler `## Contradictions` sections, entity/concept claims without sources, and empty `summary:` frontmatter. Filler bodies like `None identified.`, `None detected.`, and multi-sentence `None identified. …` elaborations are not findings (unless the section also contains an *unnegated* affirmative conflict cue such as `Contradicts earlier…`). Cues that appear only inside negation (`does not conflict with prior…`, `no claims that conflict…`) stay filler (#86).

`orphan_detection` counts inbound `[[wikilinks]]` and catalog markdown links (`[title](path.md)` that resolve to a wiki page), so pages listed only from `index.md` are not orphans. `link_integrity` resolves targets case- and punctuation-insensitively (`[[LLM-Wiki]]` → `llm-wiki.md`) but does not do substring matching.

`stub_source_pages` (#24) flags pages under `wiki/sources/` whose body is machine-generated filler — a pending sentinel (`<!-- llmwiki-pending: … -->`) or the dummy backend's `Auto-synthesized from session` body. Those sources still count as unsynthesized backlog; refill them with `llmwiki synth` on a real backend.

`provenance_integrity` (#122) emits an **error** for each broken downward hop on pages that already carry `sources:` and/or `source_file:` — missing source-summary pages or missing raw files. Pages without those fields are skipped. Repair is guided by `doctor` (#110); this rule only reports.

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
