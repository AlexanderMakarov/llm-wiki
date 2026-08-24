Synthesize `wiki/sources/<slug>.md` pages from raw session transcripts and harvest entity/concept candidates into `wiki/candidates/` (default). Use `--sources-only` for the legacy sources-only behaviour.

Wraps: `python3 -m llmwiki synth`

Usage: `/wiki-synth` (preferred) or `/wiki-synthesize` (deprecated alias). Claude translates natural-language phrasing into flags.

A real sources pass is two language-model jobs (prepare known-names once at start, then one summary per queued raw file), then bookkeeping. Harvest is offline — parsers over Connections topic bullets; no classify call and no `consolidate-topics` step. Do **not** run `llmwiki consolidate-topics` (retired; exits 2).

## Natural-language → flags

| You say | Runs |
|---|---|
| "just show me what it would cost" | `python3 -m llmwiki synth --estimate` |
| "check the backend is reachable" | `python3 -m llmwiki synth --check` |
| "force re-synthesize everything" | `python3 -m llmwiki synth --force` |
| "sources only, no candidates" | `python3 -m llmwiki synth --sources-only` |
| "candidates only" | `python3 -m llmwiki synth --candidates-only` |

## Interrupt / recovery

Ctrl+C drains in-flight pages, then harvests pending names from what was written (exit **130**). If you used `--sources-only`, the CLI prints `llmwiki synth --candidates-only` instead — run that to collect stubs from the pages already on disk.

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
- After an interrupted run: default `synth` already harvested; for sources-only interrupts, run `synth --candidates-only`.
