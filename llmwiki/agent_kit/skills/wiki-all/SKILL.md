---
name: wiki-all
description: Run the complete llmwiki pipeline from scratch — init, sync, graph, build, and lint. Use when the user says "run everything", "full pipeline", "wiki-all", or wants to rebuild the entire wiki from session history.
---

# wiki-all

## What this skill does

Runs the complete llmwiki pipeline in the correct sequence:

1. **init** — scaffold `raw/`, `wiki/`, `site/` directories
2. **sync** — convert `.jsonl` sessions to markdown
3. **graph** — build Graphify AI knowledge graph (communities, god nodes, hyperedges)
4. **build** — compile `wiki/` markdown into `site/` HTML
5. **lint** — run 14 quality rules, report issues

## Steps

Run each step in order. Report the result of each before proceeding to the next.

### Step 1: Init

```bash
python3 -m llmwiki init
```

Report what was created or confirmed.

### Step 2: Sync

```bash
python3 -m llmwiki sync --no-auto-build --no-auto-lint
```

Report: how many sessions converted, how many unchanged, any errors.

If new sessions were converted, follow `/wiki-ingest` for each new file (create/update entity + concept pages, cross-link, update index).

### Step 3: Graph

```bash
python3 -m llmwiki graph
```

Report: node count, edge count, community count, top 5 connected nodes.

Ask the user: **"Export graph to Obsidian vault?"** If yes:

```python
python3 -c "
from llmwiki.graphify_bridge import export_to_obsidian
from pathlib import Path
export_to_obsidian(Path.home() / 'Documents/Obsidian Vault/Temp/Graph')
"
```

### Step 4: Build

```bash
python3 -m llmwiki build
```

Report: HTML file count, total size, export formats written.

### Step 5: Lint

```bash
python3 -m llmwiki lint
```

Report: total issues by severity (errors, warnings, info). Highlight any errors that need immediate attention.

### Step 6: Open the site

Tell the user the site is ready and give them the path to open in a browser: `site/index.html` (or `<vault>/site/index.html` for a vault build). It is plain files — nothing needs to be running.

## After completion

Report a summary table:

| Step | Result |
|------|--------|
| init | N dirs, M seed files |
| sync | N converted, M unchanged |
| graph | N nodes, M edges, K communities |
| build | N HTML files, M MB |
| lint | N issues (E errors, W warnings) |
| open | site/index.html |
