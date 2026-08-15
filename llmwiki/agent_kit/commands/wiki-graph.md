Generate a knowledge graph of the wiki — nodes are pages, edges are `[[wikilinks]]`.

Usage: /wiki-graph [format]

`$ARGUMENTS` is one of: `json`, `html`, or `both` (default: `both`).

The graph tool walks every file under `wiki/` looking for `[[wikilink]]` references, builds a node-and-edge list, and writes:

- `graph/graph.json` — canonical data: `{nodes: [...], edges: [...]}`
- `graph/graph.html` — interactive vis.js visualisation you can open in a browser

## Steps

1. Ensure the Python graph builder exists at `llmwiki/graph.py`. If it doesn't, create it (see "Fallback" below for a pure-agent version).

2. Run:
   ```bash
   python3 -m llmwiki graph $ARGUMENTS
   ```

3. Read `graph/graph.json` after it runs and report to the user:
   - Total node count (pages)
   - Total edge count (wikilinks)
   - Top 5 most-linked pages (entities or concepts with the highest in-degree)
   - Top 5 most-linking pages (sources with the highest out-degree)
   - Any orphan nodes (zero inbound edges)
   - Any broken edges (links to pages that don't exist) — cross-check with `/wiki-lint`

4. If the user asked for `html` or `both`, tell the user to open `graph/graph.html` in a browser — the viewer and its library are emitted beside it, so it works straight from disk.

5. Append to `wiki/log.md`:
   ```
   ## [YYYY-MM-DD] graph | <N> nodes, <M> edges
   ```

## Fallback (no graph.py)

If `llmwiki/graph.py` doesn't exist yet, build the graph manually using Grep and Read:

1. `grep -roh '\[\[[^]]*\]\]' wiki/ | sort -u` → unique wikilink targets
2. For each wiki page, list the wikilinks found in it (out-edges)
3. Compute the reverse index to find in-edges
4. Write `graph/graph.json` with the format:
   ```json
   {
     "nodes": [{"id": "slug", "label": "Display Name", "type": "source|entity|concept", "in_degree": N, "out_degree": M}],
     "edges": [{"source": "from-slug", "target": "to-slug"}]
   }
   ```
5. Write `graph/graph.html` — a single HTML file with an inline vis.js embed that reads `graph.json` via `fetch()`.

Report the same statistics as above.
