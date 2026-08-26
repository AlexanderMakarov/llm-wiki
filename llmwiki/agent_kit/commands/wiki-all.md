Run the full llmwiki pipeline end-to-end: sync → synth → build → graph → lint.

Usage: /wiki-all [flags]

The default run includes the synth stage, which sends session text to the configured AI provider, so it can spend tokens; `--no-synth` keeps the whole run offline.

`$ARGUMENTS` is forwarded verbatim to `python3 -m llmwiki all`. Every stage runs by default; the flags below opt out of one or tune it. Common flags:

- `--no-sync` — skip the sync step (do not convert new agent sessions first)
- `--no-synth` — skip the synth step, so the run makes no LLM calls
- `--synth-force` — pass `--force` to synth (re-synthesize every session)
- `--graph-engine builtin` — skip optional Graphify (use when `pip install llm-wiki[graph]` has not been run)
- `--skip-graph` — skip the graph step entirely
- `--skip-lint` — skip the lint step entirely
- `--lint-fail {never,errors,warnings}` — exit `2` when lint reports issues at this level (default: `never` — findings are printed and the run still exits `0`)
- `--strict` — spelling for `--lint-fail warnings` (good for CI)
- `--fail-fast` — stop at the first non-zero step instead of continuing to the next
- `--out <dir>` — output directory (default: `site/`)

Run:

```bash
python3 -m llmwiki all $ARGUMENTS
```

The command runs these steps in order and surfaces their combined output:

1. **sync** — convert new agent sessions into `raw/sessions/` and reconcile `wiki/index.md`
2. **synth** — fill `wiki/sources/` from `raw/` via the configured LLM backend, then harvest candidate stubs into `wiki/candidates/`
3. **build** — compile the static HTML site from `raw/` + `wiki/`, including every AI-consumable export (`llms.txt`, `llms-full.txt`, `graph.jsonld`, `sitemap.xml`, `rss.xml`, `robots.txt`, `ai-readme.md`)
4. **graph** — build the knowledge graph (`graph/graph.json` + interactive `graph.html`)
5. **lint** — run every registered lint rule against the wiki

Report to the user:

- How many sessions were converted by the sync step
- How many sources were synthesized and how many candidates were harvested
- Output directory and total file / size count from the build step
- Graph stats (pages · edges · broken · orphans)
- Which export files were written
- Lint summary (errors / warnings / info)
- Overall exit code — `0` means every step succeeded

If any step fails, surface the failing step's output and the pipeline exit code.

Use this instead of chaining `/wiki-sync` + `/wiki-synth` + `/wiki-build` + `/wiki-graph` + `/wiki-lint` manually.
It is the canonical one-shot "CI-ready site" command.
