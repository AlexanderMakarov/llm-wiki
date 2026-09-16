Synthesize `wiki/sources/<slug>.md` pages from raw session transcripts and harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only behaviour.

Wraps: `python3 -m llmwiki synth`

Usage: `/wiki-synth`. Claude translates natural-language phrasing into flags.

A real sources pass is two language-model jobs (prepare known-names once at start, then one summary per queued raw file), then bookkeeping. Harvest is offline — parsers over Connections topic bullets; no classify call and no `consolidate-topics` step. Do **not** run `llmwiki consolidate-topics` (gone — known-names prepare is part of `synth`).

## Natural-language → flags

| You say | Runs |
|---|---|
| "just show me what it would cost" | `python3 -m llmwiki synth --estimate` |
| "check the backend is reachable" | `python3 -m llmwiki synth --check` |
| "force re-synthesize everything" | `python3 -m llmwiki synth --force` |
| "sources only, no candidates" | `python3 -m llmwiki synth --sources-only` |
| "candidates only" | `python3 -m llmwiki synth --candidates-only` |

## Interrupt / recovery

Ctrl+C — or a backend usage limit (`Stopped after N/M source(s) — backend usage limit (resets <time>)…`) — stops starting new sources, lets the pages in flight finish and get recorded, then harvests pending names from what was written. Sources that did not run are deferred and stay pending for the next run. Exit is **130** for Ctrl+C and **75** for a usage limit (retry after the reset). Every backend recognises the usage limit from its message text; a plain rate-limit 429 is a per-source error. A second Ctrl+C while pages finish kills the in-flight Claude / Cursor CLI processes and ends the run (those pages stay pending); Ollama waits for in-flight requests up to its timeout. If you used `--sources-only`, the CLI prints `llmwiki synth --candidates-only` instead — run that to collect stubs from the pages already on disk. `synth` does not rebuild `site/`; run `llmwiki build` afterwards.

## Expected output

First run on a fresh corpus (dummy backend):

```
Backend: DummySynthesizer
Scanned 785, new 785, synthesized 785, skipped 0
Candidates: N stub(s) at --min-refs 3 → …/wiki/candidates
```

Re-run on unchanged tree:

```
Backend: DummySynthesizer
Scanned 785, new 0, synthesized 0, skipped 0
Candidates: N stub(s) at --min-refs 3 → …/wiki/candidates
```

## When to use

- After `/wiki-sync` produces new `raw/sessions/*.md` files and you want their `wiki/sources/*.md` counterparts (and candidates) immediately.
- After updating the prompt template under `wiki/prompts/source_page.md` — pair with `--force` to re-synthesize everything using the new prompt (Connections must keep the topic / `fact:` shape).
- After switching synthesis backends (`dummy` → `ollama` → api).
- After an interrupted or usage-limited run: default `synth` already harvested; for sources-only stops, run `synth --candidates-only`.
